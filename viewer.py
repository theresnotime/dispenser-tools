#!/usr/bin/env python
# -*- coding: utf-8  -*-
import time; StartTime=time.time()
import cgi, os
import cgitb; cgitb.enable(logdir='tracebacks')

root = "/~dispenser";
docroot= "/home/~dispenser/public_html/cgi-bin/text";

def print_tsnotice():
	try:
		notice = open('/var/www/sitenotice', 'r').read()
		if notice:
			print '<div class="tsnotice" id="tsnotice">%s</div>'%notice
	except IOError:
		pass

def timeago(sec):
	if   sec < 120:		return '%.2g seconds' % (sec/1.0)
	elif sec < 7200:	return '%.2g minutes' % (sec/60.0)
	elif sec < 172800:	return '%.2g hours'   % (sec/3600.0)
	elif sec < 1209600:	return '%.2g days'    % (sec/86400.0)
	elif sec < 4838400:	return '%.2g weeks'	  % (sec/604800.0)
	elif sec < 63072000:return '%.2g months'  % (sec/2419200.0)
	else:				return '%.2g years'   % (sec/31556926.0)

	return 
def printWikiFile(name):
	import parser
	try:
		with open('./text/%s.html' % name.replace('/', '|')) as f:
			print parser.parser(f.read(), allowComments=True, allowHtml=True, sanitize=False)
	except IOError:
		print '<p>%s.html does not exist.</p>	' % name
	
def printFile(name, arg1=b'$1', arg2=b'$2', arg3=b'$3'):
	# never allow user input for name!
	with open('./text/%s.html' % name) as f:
		print f.read().replace(b'$1', arg1).replace(b'$2', arg2).replace(b'$3', arg3)
	
def startContent(response, title, head=None):
	print 'Status: '+response
	if 'modifiedtime' in globals():
		print time.strftime('Last-Modified: %a, %d %b %Y %H:%M:%S +0000', time.gmtime(modifiedtime))
	#print 'Content-Type: application/xhtml+xml; charset=utf-8'
	print 'Content-Type: text/html; charset=utf-8'
	print 	
	print '<!DOCTYPE html>'
	print '<html lang="%s" dir="ltr">' % ('en', )
	printFile('head', title, ('<base href="/~dispenser/view/Main_Page" />' if '/' in title else '') + (head or '<!-- startContent() -->'))
	print '<body class="mediawiki ltr action-view">'
	print '<div id="mw_header"><h1 class="firstHeading">%s</h1></div>' % title
	print '<div id="mw_main">'
	print '<div id="mw_contentwrapper">'

	if False:
		print """
	<!-- navigation portlet -->
<div id="p-cactions" class="portlet">
  <div class="pBody">
  	<h3>Views</h3>
    <ul>"""
		for tab in viewtabs:
			print """<li%s><a href="%s">%s</a></li>""" % (' class="selected"' if len(tab)>2 and tab[2] else '', tab[0], tab[1], )
		print """\
      </ul>
  </div>
</div>"""

	print """
	<!-- content -->
	<div id="mw_content">
	<!-- contentholder does nothing by default, but it allows users to style the text inside
	     the content area without affecting the meaning of 'em' in #mw_content, which is used
	     for the margins -->
	<div id="mw_contentholder">
	<div class='mw-topboxes'>"""
	print_tsnotice()
	printFile('notice')
	print '</div>'
	'''
	print """
<body class="mediawiki ltr">
	<div id="globalWrapper">
		<div id="column-content">
	<div id="content">
		<a name="top" id="top"></a>"""
#	printWikiFile('siteNotice')
	print """
		<div id="bodyContent">
			<h3 id="siteSub"></h3>
			<div id="contentSub"></div>
<!-- start content -->""" '''
	
def endContent(notes):
	print """
<!-- end content -->
		<div class='mw_clear'></div>
	</div><!-- mw_contentholder -->
	</div><!-- mw_content -->
	</div><!-- mw_contentwrapper -->
"""
	printFile('footer', '<br />'.join(notes + ("Page rendered in %.2f seconds"%(time.time()-StartTime,),)))
	# Works since << notes >> is global right now
	print '</body>'
	print '</html>'

def printHelpLinks():
	print '''
<div class="toptext"><a href="//en.wikipedia.org/wiki/User:Dispenser/Checklinks" class="extiw">Documentation</a><a id="feedback" href="//en.wikipedia.org/wiki/User_talk:Dispenser/Checklinks" class="extiw">Report bug / Feedback</a></div>
''' 
 
def printReportSummary(reportname):

	pagecount = 0
	rankstats = {'0':0,'1':0,'2':0,'3':0,'4':0,'5':0,'6':0}
	barelinks = {}
	agehistogram = {}
			
	counter = 0
	print '<table class="linksummary wikitable sortable">'
	print '<tr><th>Article</th><th style="width:5.5em;">Suspicious</th><th style="width:3em;">Dead</th><th style="width:9em;">Cached on</td><th class="unsortable" style="width:10em">Tools</th></tr>'
	for page in open('./reports/%s' % reportname.replace('/', '|')):
		pagecount += 1
		pagename = page.strip('\n').split('\t')[1]
		urlname = pagename.replace(' ', '_').replace('%', '%25').replace('?', '%3F').replace('&', '%26')
		filename = page.replace(' ', '_').replace('/', '|').replace('\t', '/').strip('\n')

		laststats = {'0':0,'1':0,'2':0,'3':0,'4':0,'5':0,'6':0}
		try:
			for linkentry in open('./cache/'+filename):
				items = linkentry.split('\t')
			#	print '<xmp>', items, '</xmp>'
				rankstats[items[8]] = rankstats.get(items[8], 0) + 1
				laststats[items[8]] = laststats.get(items[8], 0) + 1
				if '"external autonumber"' in linkentry:
					barelinks[pagename] = barelinks.get(pagename, 0) + 1
		except IOError:
			print '<tr><td colspan="5"><a href="//en.wikipedia.org/wiki/%s" class="extiw">%s</a> was not cached (<a href="../cgi-bin/webchecklinks.py?page=%s">run now</a>)</td></tr>'%(urlname, pagename, urlname)
			continue
		except Exception, e:
			print '<p class="error">Error processing %s (<a href="../cgi-bin/webchecklinks.py?page=%s&cache=no">purge</a>)</p>'%(pagename, urlname)
			raise

		modtime = os.path.getmtime('./cache/'+filename)
		key = int(time.time()/60.0/60.0/24.0) - int(modtime/60.0/60.0/24.0)
		agehistogram[key] = agehistogram.get(key, 0) + 1

		if laststats['4'] or laststats['5']:
			counter+= 1
			print '<tr>'
			print '<td><a href="//en.wikipedia.org/wiki/%s" class="extiw">%s</a></td>'%(urlname, pagename)
			for num in (laststats['4'], laststats['5']):
				print num and '<td>%d</td>'%num or '<td></td>'
			# Cache age
		#	print '<td>%s</td>' % timeago(time.time() - modtime)
			print time.strftime('<td><!-- %Y-%M-%d -->%d %b %Y</td>', time.gmtime(modtime))
			print '<td><a href="%(toolbase)s?page=%(urlname)s&cache=yes">View links</a>, <a href="%(toolbase)s?page=%(urlname)s">Rerun</a></td>'%dict(
				urlname = urlname,
				toolbase= '/~dispenser/cgi-bin/webchecklinks.py',
			)
			print '</tr>'

	if pagecount == 0: 
		# avoid divide by zero errors
		print '</table>'
		return 
	else:
		print '<tr class="sortbottom"><td colspan="5" style="text-align:center;">Showing %d out of %d pages (%.2g%%)</td></tr>' % (counter, pagecount, counter/(pagecount*0.01))
		print '</table>'
	
	linkcount = sum(rankstats.values()) + 0.1
	print """
<div style="">
<table class="wikitable" style="white-space:pre; margin:auto;">
<caption>Overview</caption>
<tr><th></th><th>Links</th><th>Avg per page</th><th>Percent total</th><td rowspan="9" ><img alt="" style="float:right;" 
src="http://chart.apis.google.com/chart?cht=p3&amp;chs=400x180&amp;chf=bg,s,f7f7f7&amp;chts=ffffff&amp;chco=eeeeee|CFEEB2|EEEEB2|B2CFEE|EED0B2|EEB2B2|9596E9&amp;chl=Good|Status|Warn|Connection|Suspicious|Error&amp;chd=t:%s&amp;chp=%.4f" 
/></td></tr>
<tr><td>Good:      </td><td>%6d </td><td>%5.3g </td><td>%5.1f%%</td></tr>
<tr><td>Status:    </td><td>%6d </td><td>%5.3g </td><td>%5.1f%%</td></tr>
<tr><td>Warn:      </td><td>%6d </td><td>%5.3g </td><td>%5.1f%%</td></tr>
<tr><td>Suspicious:</td><td>%6d </td><td>%5.3g </td><td>%5.1f%%</td></tr>
<tr><td>Error:     </td><td>%6d </td><td>%5.3g </td><td>%5.1f%%</td></tr>
<tr><td>Conection: </td><td>%6d </td><td>%5.3g </td><td>%5.1f%%</td></tr>
<tr><td>Badlinks:  </td><td>%6d </td><td colspan="2">-</td></tr>
<tr><td>Total:     </td><td>%6d </td><td> %#.3g</td><td> %2.2f%%</td></tr>
</table>
</div>""" % (
','.join(["%d"%(rankstats[c]*100/linkcount) for c in '012345']),
3.14159-(3.14159*rankstats['0']/linkcount),
rankstats['0'], (rankstats['0']/float(pagecount)), (rankstats['0']*100/float(linkcount)),
rankstats['1'], (rankstats['1']/float(pagecount)), (rankstats['1']*100/float(linkcount)),
rankstats['2'], (rankstats['2']/float(pagecount)), (rankstats['2']*100/float(linkcount)),
rankstats['4'], (rankstats['4']/float(pagecount)), (rankstats['4']*100/float(linkcount)),
rankstats['5'], (rankstats['5']/float(pagecount)), (rankstats['5']*100/float(linkcount)),
rankstats['3'], (rankstats['3']/float(pagecount)), (rankstats['3']*100/float(linkcount)),
rankstats['6'],
linkcount, (linkcount/float(pagecount)), 100,
)
	
	if barelinks:
		import parser
		print parser.parser("<p>These pages appear to have bare links: "+', '.join(sorted(["[[%s]] (%d)"%(k,v) for k,v in barelinks.items()]))+"</p>")
	
	output = '<div style="border:1px solid gray; overflow:auto; padding:1px; text-align:right; " class="histo"><div style="background:#eee; white-space:nowrap;" class="histodata">'
	output += '<div class="histolabel" style="text-align:left; font-weight:bold;">Cache age</div>'
	for i in range(max(agehistogram.keys()), -1, -1):
		output += '<div class="bar" style="width:8px; height:%dpx; %s" title="%d items %s days ago"><!-- --></div>' % (agehistogram.get(i,0), i%7==0 and "margin-left:2px;" or "", agehistogram.get(i,0), i)
	print output + "</div></div>"
	print "<style>.histo .bar { background:lightblue; border:1px solid; border-color:#ccc #333 #000 #999; cursor:help; display:inline-block; } </style>"
	#print agehistogram


def main(environ, start_response):
	form = cgi.FieldStorage(environ=environ, keep_blank_values=0)
	action = form.getfirst('action', 'view')
	urlname  = form.getfirst('title', os.getenv("PATH_INFO", '/Main_Page')[1:])
	title    = urlname.replace('_', ' ')
	filename = urlname.replace('/', '|')
	urlname  = urlname.replace('?', '%3F')
	global viewtabs
	viewtabs = [("../%s/%s"%(action, urlname), action.capitalize(), True)]
	global notes
	notes = ()
	# TODO make less hackist
	if len(filename) > 255:
		start_response("413 Request title too long", [])
		return ["413 Request title too long"]
	def modNotes(f):
		global notes, modifiedtime
		modifiedtime = os.path.getmtime(f)
		notes = (time.strftime('This page was last modified on %d %B %Y at %H:%M (UTC)', time.gmtime(modifiedtime)),)
		# HACK
		#if os.getenv('HTTP_IF_MODIFIED_SINCE', '') and time.gmtime(modifiedtime) <=  time.strptime(os.getenv('HTTP_IF_MODIFIED_SINCE')):
		if os.getenv('HTTP_IF_MODIFIED_SINCE') == time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime(modifiedtime)):
			print 'Status: 304 Not Modified'
			print 
			raise Done
#		print os.getenv('HTTP_IF_MODIFIED_SINCE', 'NO HTTP_IF_MODIFIED_SINCE')
#		notes = ('This page was last modified on %s' % time.ctime(modifiedtime),) 
#				try:modified = time.strftime("%d %B %Y at %H:%M", time.gmtime(os.path.getmtime("./reports/"+t[0].replace('/', '|'))))
#				except OSError:modified = 'Unknown'
#				t.append(modified)
		#notes = ('Updated %s ago on %s (UTC)' % (timeago(time.time() - modifiedtime), time.ctime(modifiedtime), ),) #time.strftime('%A, %Y %d, %B at %H:%M (UTC)', time.gmtime())
		
	
	# Text files
	if action in ('view', 'source', 'edit',):
		viewtabs = [
			("/~dispenser/view/%s" % urlname, "Page", action=='view',),
			("/~dispenser/edit/%s"%urlname, "View source", action=='source' or action=='edit', ),
		]
		try:
			f = open('./text/%s.html'%filename)
			modNotes('./text/%s.html'%filename)
			redirect = f.read(10) == '#REDIRECT '
			f.seek(0)
			if action == 'view' and redirect:
				data  = f.read()
				begin = data.index('"')+1
				end   = data.index('"', begin)
				start_response('Status: 303', [
				('Location', data[begin:end]),
				('Content-Type', 'text/html; charset=utf-8'),
				])
				return [data, 'Location: %s' % data[begin:end]]

			if action == 'view':
				startContent('200 Successful', title)
				import parser
				print parser.parser(f.read(), allowComments=True, allowHtml=True, sanitize=False)
			else:
				startContent('200 Successful', 'View source: %s' % title)
				print '<div id="viewsourcetext">You can view and copy the source of this page:</div>'
				print '<textarea id="wpTextbox1" name="wpTextbox1" cols="80" rows="25" readonly="readonly">'
				print cgi.escape(f.read())
				print '</textarea>'
			f.close()
		except IOError:
			startContent('404 Not found', "Not found %s"%title)
			print '<p>%s does not exist</p>' % title

	# Checklinks specific
	elif action in ('list',):
		try:
			modNotes('./list/'+filename)
			startContent('200 Successful', title)
			print '<i>See also: <a href="%s%s" title="%s">%s</a></i>' % ("//en.wikipedia.org/wiki/", "Category:"+urlname, "Category:"+title, "Category:"+title, )
			print '<table class="wikitable sortable">'
			print '<tr><th>Report</th><th>Pages</th><th>List updated</th></tr>'
			for line in file('./list/%s' % (filename, )):
				t = line.split('\t')
				try:
					updated  = os.path.getmtime('./reports/'+t[0].replace('/', '|'))
					update_formatted = time.strftime('%H:%M, %b %d', time.gmtime(updated))
				except OSError as (errno, errmsg):
					update_formatted = errmsg
				print '<tr><td><a href="/~dispenser/summary/%s">%s</a></td><td>%s</td><td>%-4s</td></tr>' % (t[0].replace('|', '/'), t[1], '</td><td>'.join(t[2:]), update_formatted, )
			print '</table>'
			printHelpLinks()
		except OSError as (errno, errmsg):
			startContent('404 Not found', title)
			print "<!-- Error %d: %s -->" % (errno, errmsg)
			printWikiFile('no_report')

	elif action in ('report', 'summary',):
		try:
			modNotes('./reports/'+filename)
			startContent('200 Successful', 'Summary of %s' % title, head='<meta name="robots" content="nofollow" />')
			printReportSummary(urlname)
			printHelpLinks()
		except OSError:
			startContent('404 Not found', 'Not found %s' % title)
			printWikiFile('no_report')

	elif action == 'cache':
		n = filename.split(':', 2)
		filename = "%s:%s/%s"%tuple(n) if len(n)==3 else "wikipedia:en/"+filename
		try:
			modNotes('./cache/'+filename)
			f = open('./cache/%s' % filename)
			startContent('200 Successful', "Cache of %s" % title, head='<meta name="robots" content="noindex, nofollow" />\n  <script src="/~dispenser/resources/checklinks.js" type="text/javascript"></script>')
			def jsescape(s):return s.replace('&', '\\x26').replace('"', '\\"')
			print """
<script type="text/javascript">
var wgScript="/w/index.php",
wgServer="//en.wikipedia.org",
wgNamespaceNumber=0,
wgPageName="%s",
wgTitle="%s",
wgContentLanguage="%s",
wgDBname="enwiki";
</script>"""%(
	jsescape(title.split(':', 2)[2] if ':' in title else title),
	jsescape(title.split(':', 2)[2] if ':' in title else title),
	jsescape(title.split(':', 2)[1] if ':' in title else 'en'),
)
			printFile('checklinks-header')
			printFile('checklinks-cache-warning', urlname.replace('wikipedia:', ''), title, time.strftime('%d %B %Y at %H:%M (UTC)', time.gmtime(os.path.getmtime('./cache/'+filename))))
			print '<table id="linktable" class="">'
			print '<tr class="page"><th colspan="4"><a href="//en.wikipedia.org/wiki/%(urlname)s" title="%(title)s">%(title)s</a></th></tr>' % {
				'urlname':	urlname.replace('wikipedia:', ''), 
				'title':	title,
			}
			printFile('checklinks-tableHead')
			for line in f:
				cells = line.split('\t')
				print '<tr class="dead-%s">'%cells[8]
				print "<td>%s</td>"%cells[1]
				print "<td>%s</td>"%cells[2]
				print '<td><abbr title="%s">%s</abbr></td>'%(cells[4],cells[3])
				print "<td>%s</td>"%cells[9]
				print '</tr>'
			print '</table>'
			printHelpLinks()
		except OSError:
			startContent('404 Not found', "No cache for %s" % title)
			print 'No cached result exist of <a href="//meta.wikimedia.org/wiki/%s">%s</a>' % (filename, title)
			#raise
		except IOError:# Open a directory
			startContent('404 Not found', "Title not specified")
			print 'Please specify a title'

	else:
		startContent('400 No action', 'No action')
		print 
		print 'No action by that name specified (%s)'%action

	endContent(notes)

def HandleRedirect():
	redirect = os.getenv("REQUEST_URI", '')
	redirect = redirect.replace('%20', '_').replace('%7E', '~')
	redirect = redirect.rstrip('_')
	redirect = redirect.replace('|', '/')

	if redirect != os.getenv("REQUEST_URI", ''):
		# http://turbo-technical-report.blogspot.com/2006/11/server-side-301-302-http-response.html
		# Saved me quite a bit of trouble. Thanks!
		print "Status: 301"
		print 'Location: ' + redirect
		print 'Content-Type: text/html; charset=utf-8'
		print 
		print """
<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>301 Moved Permanently</title>
</head><body>
<h1>Moved Permanently</h1>
<p>The document has moved <a href="%s">here</a>.
</p>
</body></html>""" % redirect
		return False
	elif os.getenv("REQUEST_METHOD", "GET") != "GET" :
		print 'Status: 405'
		print
		return False
	else:
		return True

# Hack
class Done(Exception):			"""Done"""

if __name__ == "__main__" and HandleRedirect():
	if cgi.os.environ.get('GATEWAY_INTERFACE','').startswith('CGI/'):
		def start_response(status, headers):
			print 'Status:', status
			print '\n'.join(': '.join(h) for h in headers)
			print 
		try:
			print ''.join(main(cgi.os.environ, start_response) or [''])
		except Done:
			pass
	else:
		from flup.server.fcgi import WSGIServer
		WSGIServer(main).run()
