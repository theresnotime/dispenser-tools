#!/usr/bin/env python
# -*- coding: utf-8  -*-
import cgi, urlparse, httplib, urllib
import re, sys
import toolsql
import cgitb; cgitb.enable(logdir='tracebacks')

# XXX Setup default proxy
if True:
	import socket, socks
	socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 8080)
	socket.socket = socks.socksocket

namespaces = {
	0:   "",
	1:   "Talk",
	2:   "User",
	3:   "User_talk",
	4:   "Wikipedia",
	5:   "Wikipedia_talk",
	6:   "File",
	7:   "File_talk",
	8:   "MediaWiki",
	9:   "MediaWiki_talk",
	10:  "Template",
	11:  "Template_talk",
	12:  "Help",
	13:  "Help_talk",
	14:  "Category",
	15:  "Category_talk",
	100: "Portal",
	101: "Portal_talk",
	108: "Book",
	109: "Book_talk",
	118: "Draft",
	119: "Draft_talk",
	710: "TimedText",
	711: "TimedText_talk",
	828: "Module",
	829: "Module_talk",
}

noarchive = (
	'archive.org',
	'toolserver.org',
	'wikipedia.org',
	'archive.org',
	'www.google.com',
	'youtube.com',
	'webcitation.org',
)

# Messages 
redirectmsg = """
<table style="font-size:.9em; background:#f9f9f9; border:1px solid #ddd;">
<tr>
<td><img src="https://upload.wikimedia.org/wikipedia/commons/c/c8/Ambox_notice.png" style="float:left;" alt="" /></td>
<td style="width:100%">Redirects or <tt>move</tt>s are normal operations of a server.  A well designed site will redirect users from older URLs to the newest URL of the month; as intentional with permalinks.  At times, however, they redirect to advertisement, login, soft 404, and error pages. <a href="//en.wikipedia.org/wiki/User:Dispenser/Checklinks#Redirects">Read more.</a></td>
</tr>
</table>
"""
webcitemsg = """
<p></p>
<table style="font-size:.9em; background:#f9f9f9; border:1px solid #ddd;">
<tr>
<td><img src="https://upload.wikimedia.org/wikipedia/commons/c/c8/Ambox_notice.png" style="float:left;" alt="" /></td>
<td style="width:100%">
<p>WebCite offers on demand archiving, allowing preservation of cited material the same as the day it was archived.  This service will not work for sites who have explicitly opted out using the robots.txt, no-cache / no-archive, or have blocked the WebCite robot.  <a href="http://www.webcitation.org/faq">Read more...</a></p>
<button onclick='location.href+=\"&amp;archivenow=1\";return false;'>Request to archive this link</button>
<p>Please view content <i>before archiving</i> to ensure there were no false negatives in Checklinks</p>
</td>
</tr>
</table>
"""
webcitearchivedmsg = """
<p></p>
<table style="font-size:.9em; background:#f9f9f9; border:1px solid #ddd;">
<tr>
<td><img src="https://upload.wikimedia.org/wikipedia/commons/c/c8/Ambox_notice.png" style="float:left;" alt="" /></td>
<td style="width:100%">
<p>An archive request was sent to WebCite.</p>$1
</td>
</tr>
</table>
"""

def wikiquote(s):
	return urllib.quote(s.replace(' ', '_'), safe=";@$!*(),/:-_.")

#		for m in re.finditer(r'http://web.archive.org/web/(\d{15})/[^<">]+', results):
# r'<a href="http://web.archive.org/web/([^0-9]+)/[^"]+">[^<>]*</a>'
# webcitation.org

class InternetArchiveConsulter:
	def __init__(self, url):
		self.url = url
	def getArchiveURL(self):
		import urllib2
		#print u'Consulting the Internet Archive for %s' % self.url
		archiveURL = 'http://classic-web.archive.org/web/20010101-*/%s' % self.url
		try:
			f = urllib2.urlopen(archiveURL)
		except urllib2.HTTPError, e:
			# The Internet Archive yields a 403 error when the site was not
			# archived due to robots.txt restrictions.
			if e.code == 403:
				return 'Internet Archive results are blocked'
			elif e.code == 404:
				return """No matches from the Internet Archive"""
			elif e.code == 501:
				return """Failed connection -- Internet Archive, <a href="http://www.archive.org/about/faqs.php#201">more</a>"""
			elif e.code == 503:
				print 'try: <a href="%s">%s</a>'%(archiveURL,archiveURL)
				return "503 error, do you know what it is?"
			else:
				return "Something when wrong, got error code %s" % e.code
		except urllib2.URLError, e:
			print 'We failed to reach a server (Internet Archive).', '<br/>'
			print 'Reason: <code>', e.reason, '</code>'
			return None
		except UnicodeEncodeError:
			return None
		if f.info().get('Content-Encoding') in ('gzip', 'x-gzip'):
			import StringIO, gzip
			text = gzip.GzipFile(fileobj=StringIO.StringIO(f.read())).read()
		else:
			text = f.read()

		# Update {{dead link}} to w/ history
		print """<script language="JavaScript"><!--
if(parent && parent.activeLink && parent.activeLink.action==4)
	parent.iframeSetAction(window.frameElement, 5);
--></script>"""
		print 'Internet Archive\'s Wayback Machine has some results <small>(* indicate changes)</small>'
		iBegin = text.index('<table border="0" width="100%">')
		iEnd =  text.index('</table>', iBegin) + len('</table>')
		return text[iBegin:iEnd].replace('<a ', '<button onclick=\'parent.iframeSetAction(window.frameElement, 1, this.nextSibling.nextSibling.href);\'>Use</button> &nbsp;<a ')
	def iterArchiveCopies(self):
		results = self.getArchiveURL()
		for m in re.finditer(r'http://classic-web.archive.org/web/(\d{15})/[^<">]+', results):
			yield m.group(1), m.group(0)

def printu(s, data=None):
	print (s % data if data else s).encode('utf-8')

def findothers(url, wiki='enwiki'):
	host = u'https://en.wikipedia.org'
	with toolsql.getConn(wiki, cluster='labsdb') as cursor:
		try:
			cursor.execute("""
SELECT (SELECT url FROM meta_p.wiki WHERE dbname=TRIM('_p' FROM DATABASE())) AS host, page_namespace, page_title
FROM externallinks 
JOIN page ON page_id=el_from
WHERE el_to=?
ORDER BY page_namespace
			""", (url,), max_time=10)
		except toolsql.QueryTimedOut as (errno, errmsg, extra):
			print '<div class="error">'
			print ('<a href="%s/wiki/Special:LinkSearch/%s">Link search</a> timed out (Err %d), please try again in a few minutes.' % (host, urllib.quote(url), errno,)).encode('utf-8')
			print '</div>'
		else:
			# Avoid listing our own article
			if cursor.rowcount < 2:
				return

			print '<div class="other-pages">'
			prev = None
			suppresseded = False
			for host, page_namespace, title in cursor:
				ns_name = namespaces.get(page_namespace, "{ns:%d}" % page_namespace)
				if page_namespace != prev:
					if page_namespace != None:
						print '</ul>'
					if page_namespace == 0:
						print '<p>Articles using this link:</p><ul>'
					else:
						printu('<p>In %s namespace:</p><ul>' % ns_name.replace('_', ' ').lower())
					prev = page_namespace
				printu('<li><a href="%s/wiki/%s:%s" class="extiw">%s%s</a></li>' % (host, ns_name, urllib.quote(title), ns_name+':' if ns_name else '', title.replace('_', ' ')))
			print '</ul>'
			# TODO alert there are domain.com/file?* URLs
			if suppresseded:
				printu('<p><a href="%s/wiki/Special:LinkSearch/%s" class="extiw">Some results were suppressed, see all</a></p>'% (host, urllib.quote(url)))
			print '</div>'

def accessdate(url):
	import os
	listofaccessed = '/home/dispenser/accessed/'
	files = os.listdir(listofaccessed)
	files.sort()

	for filename in files:
		if '\t'+url.encode('utf-8')+'\t' in open(listofaccessed + filename, 'r').read():
			print "<p style='font-size:x-small;'>Checklinks first sucessfully accessed this url on %s</p>"%filename[:-4]
			break

def linktrack(location, useHEAD = True, counter = 7, redirectChain = []):
	try:
		print '<pre>'
		print '<span class="request">HEAD %s</span>' % location
		while (counter >= 0 and location is not None):
			address = urlparse.urlsplit(location)
			if address.scheme == "http":
				conn = httplib.HTTPConnection(address.hostname)
			elif address.scheme == "https":
				conn = httplib.HTTPSConnection(address.hostname)
			else:
				return (None, 'Unsupported Protocol', redirectChain)
			conn.set_debuglevel(0)
			httplib.socket.setdefaulttimeout(20)
			
			path  = address.path or '/'
			query = address.query and '?' + address.query or ''

			# FIXME http://www.kurnik.pl/slownik/sp.phtml?sl=Gar%B3uch
			try:
		#	if type(path) == type(query) == type(''):
				request = path.encode('ascii') + query.encode('ascii')
			except UnicodeEncodeError:
				encoding = 'utf-8'
				noencode = '~!^*()_-=&/|,.?;'
				import urllib
				request = urllib.quote(path.encode(encoding) + query.encode(encoding), noencode)
			except UnicodeDecodeError:
				import urllib
				request = urllib.quote(path+query,  '~!^*()_-=&/|,.?;')
				print request
				
			conn.request(useHEAD and 'HEAD' or 'GET', request)
			
			response = conn.getresponse()
			redirect = response.msg.getheader('location')
			# It more failsafe if we use a try statement otherwise we could simply test if useHEAD was set
			if not useHEAD:
				text = response.read()
			else:
				text = ''
			conn.close()
			
			counter -= 1
			if redirect:
#				print '<span class="redirects">'
#				print 'HTTP %s Move: %s' % (response.status, redirect)
				print '''<span class="redirect protocol" onclick="with(this.nextSibling.style)display=(display==\'\'?\'none\':\'\');">HTTP/%g %d Move: %s</span><span class="redirect headers" style="display:none;">\n%s</span>''' % (response.version/10.0, response.status, redirect, response.msg, )
				if(redirect.startswith("http")):
					location = redirect
				else:
					location = urlparse.urljoin(location, redirect)
				redirectChain.append(location)
			else:
				location = None
		print '''<span class="response protocol" onclick="with(this.nextSibling.style)display=(display==\'\'?\'none\':\'\');">HTTP/%g %d %s</span><span class="response" style="display:none;">\n%s</span>''' % (response.version/10.0, response.status, response.reason, response.msg, )
		print '</pre>'
		return (response, text, redirectChain)
	except httplib.socket.error, arg:
		print 'Socket error: ', arg
		print '</pre>'
		return (None, "SOCKET %r" % arg, redirectChain)
	except Exception, e: # catches those weird ones

		print u'Exception raised: %s' % e
		print '</pre>'
		raise
		return (None, "Exception %s" % e, redirectChain)
	
def main():
	form = cgi.FieldStorage()
	url = form.getfirst('url', '')#.replace(' ', '+')
	if isinstance(url, bytes):
		try:
			url = url.decode('utf-8').encode('utf-8')
		except UnicodeDecodeError:
			url = url.decode('latin-1').encode('utf-8')
	useHEAD = (form.getfirst('method', "HEAD")=="HEAD")
	if not url:
		print '<form><input name="url" size="60" /><input type="submit" value="Get headers" /></form>'
		return
	
	try:
		(response, text, redirectChain) = linktrack(url, useHEAD)
	except AttributeError:
		print "Malformed URL: %s"%cgi.escape(url)
		return
	except httplib.BadStatusLine:
		print "Presumably, the server closed the connection before sending a valid response: %s"%cgi.escape(url)
		return

	if response is None:
		print text
	else:
		if len(response.msg.getheader('Content-Length', '')) > 6:
			print "File size is %4.3g MB" % (float(response.msg.getheader('Content-Length', 'error'))/1024.0/1024.0,)
	
# FIXME mOVE INTO THE RIGHT SPOT
	dbname = form.getfirst('dbname', 'enwiki')

	# diff view of redirect
	if redirectChain != []:
		import difflib
		d = difflib.Differ()
		p = re.compile(r'(\W)')
		redirect = redirectChain.pop()
		cmpr = d.compare(p.split(url), p.split(redirect) )
		
		htmlurl_1 =''
		htmlurl_2 =''

		for s in cmpr:
			if s[0] == '-':
				htmlurl_1 += '<b>%s</b>' % s[2:]
			elif s[0] == '+':
				htmlurl_2 += '<b>%s</b>' % s[2:]
			elif s[0] == ' ':
				htmlurl_1 += s[2:]
				htmlurl_2 += s[2:]
			elif s[0] == '?':
				htmlurl_1 += ''
			else:
				print list(cmpr)
				raise
		print ('<pre>\n%s\n redirects to\n%s</pre>' % (htmlurl_1, htmlurl_2)).replace('</b><b>', '')
		print redirectmsg

	sys.stdout.flush()

	#TODO add parameter to activate wayback search
	if response and (int(response.status/100) == 4 or response.status==0) or form.getfirst('archivesearch', '') in ('dead-4', 'dead-5', 'yes', 'true'):
		# Link is dead

		# Results from Internet Archive Wayback Machine
		print 
		iac = InternetArchiveConsulter(url)
		results = iac.getArchiveURL()
		print results
		print """
<script type="text/javascript">
var wayback_R = /.*?web\/(\d{4})(\d\d)(\d\d)(\d\d)(\d\d).*/;
window.onload = function() {
// TODO only select the wayback table
	var anchors =  document.getElementsByTagName("A");
	var accessdateM = location.href.match(/[&?]accessdate=([^&#=]+)/);
	if(!accessdateM)return;
	var accessdate = new Date(unescape(accessdateM[1].replace(/-/g, ' ')));

	// Best match stuff
	var bestNode = null;
	var bestTimeDiff = Infinity;

	// date away
	var dateawayM = location.href.match(/[&?]dateaway=(\d+)/);
	var dateaway = (dateawayM?dateawayM[1]:21)*24*60*60*1000;

	for(var a, i=0; (a=anchors[i])!=null; i++) {
		if(!a.href.match(wayback_R))continue;
		archive_date = new Date(a.href.replace(wayback_R, "$1 $2 $3 $4:$5"));
		timediff = archive_date.getTime() - accessdate.getTime();
		if(Math.abs(timediff) < Math.abs(bestTimeDiff)) {
			bestTimeDiff = timediff;
			bestNode = a;
		}
		a.title = Math.abs(Math.round(timediff/(24*60*60*1000))) + (timediff<0?" days before":" days after") + " the access date";
	}
	if(bestNode) {
		bestNode.className="close-archive";
		if(parent && parent.activeLink && (parent.activeLink.action==0 || parent.activeLink.action==4 || parent.activeLink.action==5))
			if(Math.abs(bestTimeDiff) < dateaway)
				parent.iframeSetAction(window.frameElement, 1, bestNode.href);
	}
}
</script>
"""
		print '<div>'
		# Results from WebCite
		import webcite
		wcu = webcite.WebCite(url)
		results = wcu.search()
		for result in results:
			if result['status'] == 'success':
				print '<button onclick=" parent.iframeSetAction(window.frameElement, 1, &quot;%s&quot;);">Use WebCite archive from %s</button><br/>' % (result['webcite_url'], result['timestamp'], )
			else:
				print '<code>', result, '</code>'
		#	if url.encode('utf-8')+'\n' in open('/home/dispenser/webcite_requests.txt','r'):
		#		print "<p>WebCite archive may exist -- <a href='http://www.webcitation.org/query.php?returnxml=false&url=%s'>Search</a></p>" % url
		print '</div>'


	if (redirectChain == [] and not vars().has_key('redirect') 
			and response and response.status == 200 
			and form.getfirst('archivesearch','') in ('dead-0', '0', ) 
			and not any(domain in url for domain in noarchive) 
			and response.msg.getheader('Cache-Control', '').lower().find('no-store') == -1
		):
		import webcite
		wcu = webcite.WebCite(url)
		results = wcu.search()
		if url+'\n' in open('/home/dispenser/webcite_requests.txt','rb'):
			s = ''
			for result in results:
				if result['status'] == 'success':
					
					s += '<li><button onclick=" parent.iframeSetAction(window.frameElement, 1, &quot;%s&quot;);">%s</button></li>' % (result['webcite_url'], result['timestamp'], )
				else:
					print '<code>', result, '</code>'
			print webcitearchivedmsg.replace('$1', "WebCite has archive this on: <ul>"+s+"</ul>")
		elif results != []:
			print "<code>%s</code>"%results
			f = open('/home/dispenser/webcite_requests.txt', 'a')
			f.write(url+'\n')
			f.close()
			print '<p>Adding WebCite status to internal list.  Click again to see new status</p>'
			print webcitearchivedmsg.replace('$1', "")
#		elif response.msg.getheader('Content-Type', '') == 'application/pdf':
#			if results == []:
#				f = open('/home/dispenser/webcite_requests.txt', 'a')
#				f.write(url+'\n')
#				f.close()
#
#				ema = "".join((chr(ord(s)^7) for s in 'cntwbitbuGshhktbuqbu)hu`'))
#				s = wcu.archive(ema).read()
#				print "Requesting archiving of Portable Document Format file<br/>"
#				print results
		elif form.getfirst('archivenow'):
			try:
				print 'Requesting archiving of url - WebCite'
				webcite.requestArchiving(url)

				f = open('/home/dispenser/webcite_requests.txt', 'a')
				f.write(url+'\n')
				f.close()
			except IOError as inst:
				print('<div class="errormsg" style="font-weight:bold; color:red;">%s</div>'% (repr(inst),))
		else:
			print webcitemsg

	sys.stdout.flush()

	findothers(url, dbname)
	accessdate(url)

	
if __name__ == "__main__":
	try:
		print 'Content-type: text/html; charset=UTF-8'
		print 
		print '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">'
		print '<html>'
		print """
<head>
<title></title>
<style type="text/css">
pre b { color:red;}
.request {color:sienna;}
.response {color:darkgreen;}
.protocol {cursor:pointer;}

/* section of other pages which use the link */
div.other-pages { font-size:normal; }
div.other-pages ul { margin:0 }
div.other-pages p { margin-bottom:0 }
a.extiw { color:#36b; text-decoration:none }
a.extiw:hover { text-decoration:underline }

/* */
.close-archive {
	font-weight:bold;
	}
</style>
</head>

<body>"""
		main()
	finally:
		print '</body></html>'
