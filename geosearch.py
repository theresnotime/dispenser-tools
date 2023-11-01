#!/usr/bin/env python
# -*- coding: utf-8  -*-
import cgi, urllib
import toolsql
import wikipedia
import cgitb; cgitb.enable(logdir='tracebacks')

DefaultBaseUrl = "http://toolserver.org/~geohack/geohack.php?"
DefaultBaseUrl = "https://tools.wmflabs.org/geohack/geohack.php?"

def urlencode(s):
	return urllib.quote(s.encode('utf-8') if isinstance(s, unicode) else bytes(s), safe="!$'()*,-./:;=?@^_{|}`~")

def printLinks(offset, limit, queryString):
	basehref=''.join(("/~dispenser/cgi-bin/geosearch.py","?",queryString))
	if offset > 0:
		print '<p>View (<a href="%s&amp;offset=%d&amp;limit=%d">previous %d</a>) '% (basehref, offset-limit >=0 and offset-limit or 0, limit, limit)
	else:
		print '<p>View (previous %d) '% (limit, )
	if True:
		print '(<a href="%s&amp;offset=%d&amp;limit=%d">next %d</a>)' % (basehref, offset+limit, limit, limit)
	else:
		print '(next %d)' % (limit,)
	print '(<a href="%(basehref)s&amp;offset=%(offset)d&amp;limit=20">20</a> | <a href="%(basehref)s&amp;offset=%(offset)d&amp;limit=50">50</a> | <a href="%(basehref)s&amp;offset=%(offset)d&amp;limit=100">100</a> | <a href="%(basehref)s&amp;offset=%(offset)d&amp;limit=250">250</a> | <a href="%(basehref)s&amp;offset=%(offset)d&amp;limit=500">500</a> | <a href="%(basehref)s&amp;offset=%(offset)d&amp;limit=5000">5000</a>)</p>'% locals()
	
def main():
	site	= wikipedia.getSite()

	form = cgi.FieldStorage()
	#SHOULDBE: /query -> ?regexp=query
	namespace = int(form.getfirst('namespace', 0))
	pattern	= form.getfirst('regexp', form.getfirst('page', "")).decode('utf-8')
	isRegex	= form.getfirst('type', 'like')=='regex'
	invert  = bool(form.getfirst('invert', False))
	limit	= int(form.getfirst('limit', 500))
	offset	= int(form.getfirst('offset', 0))
	baseUrl = form.getfirst('baseUrl', "")

	queryString = b'&'.join(b'%s=%s'%(k,v) for k,v in {
		'lang':	     site.language() if site.language()!='en' else '',
		'namespace': namespace if namespace else '',
		'regexp':    urlencode(pattern),
		'type':      'regex' if isRegex else '',
		'baseUrl':   urlencode(baseUrl) if baseUrl else '',
	}.iteritems() if v)

	def el_index_convert(url):
		dBegin = 8 if url.startswith('https:') else 7
		dEnd = url.index('/', dBegin)
		return url[:dBegin]+'.'.join(reversed(url[dBegin:dEnd].split('.')))+'.'+url[dEnd:]

	conn = toolsql.getConn(site.dbName(), cluster='web')
	cursor = conn.cursor()

	print '<form action="/~dispenser/cgi-bin/geosearch.py"><fieldset><legend>Search GeoHack external links</legend>'
	print '<table><tr>'

	print '</tr><tr>'
	print '<td><label>Site: </label></td>'
	print '<td><input type="text" name="lang" value="%s" size="%d" />.wikipedia.org</td>' % (site.language(), len(site.language()),)
	print '</tr><tr>'
	if baseUrl:
		print '<td><label>Base URL: </label></td><td><input type="text" name="baseUrl" value="%s" size="%d" /></td>' % (wikipedia.escape(baseUrl), len(baseUrl))
	baseUrl = baseUrl or DefaultBaseUrl
	
	print '<td><label for="namespace">Namespace:</label></td><td><select id="namespace" name="namespace" class="namespaceselector">'
	try:
		with toolsql.getConn(host='tools.labsdb') as curs:
			curs.execute('SELECT ns_id, ns_name FROM u2815__p.namespacename WHERE dbname=? AND ns_id>=0 AND ns_is_favorite=1 ORDER BY ns_id', (site.dbName()+'_p',), max_time=5)
			#cursor.execute('SELECT ns_id, ns_name FROM u2815__p.namespacename WHERE dbname=(SELECT DATABASE()) AND ns_id>=0 AND ns_is_favorite=1 ORDER BY ns_id', max_time=5)
			for ns_id, ns_name in curs:
				print (u'<option value="%d"%s>%s</option>'%(ns_id, ' selected="selected"' if ns_id==namespace else '', ns_name or "(Article)",)).encode('utf-8')
	except toolsql.ProgrammingError:
		for ns_id in range(0,16):
			print (u'<option value="%d"%s>%s</option>'%(ns_id, ' selected="selected"' if ns_id==namespace else '', "Namespace %s"%ns_id if ns_id else "(Article)",)).encode('utf-8')
	finally:
		print '</select></td>'
	print '</tr><tr>'
	print '<td><label for="regexp">Search expression</label>:</td>'
	print '<td><input type="text" name="regexp" id="regexp" size="50" value="%s" onkeyup="checkregex(this)" /></td>' % (wikipedia.escape(pattern).encode('utf-8'), )
	print '<td><input type="submit" value="Search" /></td>'
	print '</tr><tr>'
	print '<td></td><td><input type="checkbox" name="type" id="type" %s value="regex" onclick="Autocheck=this.checked" /><label for="type">Regular expression</label> (<a href="http://dev.mysql.com/doc/refman/5.0/en/regexp.html" class="external text">help</a>)' % ('checked="checked" ' if isRegex else '')\
	+'<input type="checkbox" name="invert" id="invert" %s /><label for="invert">Exclude links matching expression</label></td>' % ('checked="checked" ' if invert else '')
	print '</tr><tr>'
	print '</tr></table>'
	print r'<div style="font-size:small;" id="slashmatch"><a href="//en.wikipedia.org/wiki/Wikipedia:WikiProject_Geographical_coordinates/coordinates_search_tool" class="extiw">Examples</a>, Cheat sheet: <code>\w</code> &#8594; <code>[[:alnum:]]</code>, <code>\d</code> &#8594; <code>[[:digit:]]</code>, <code>\s</code> &#8594; <code>[[:space:]]</code>, <code>\b</code> &#8594; <code>[[:&lt;:]]</code>or <code>[[:&gt;:]]</code>, search of parameter values: params=[^&amp;=]+ </div>'
	print '</fieldset></form>'
	
	where_conditions = []
	where_data       = []
	def addWhere(condition, params=()):
		where_conditions.append(condition)
		for param in params:
			where_data.append(param)
	
	addWhere("page_namespace = ?", (namespace,))
	addWhere("el_index LIKE ?", (el_index_convert(toolsql.like_escape(baseUrl)+"_%"),))
	if isRegex:
		addWhere("el_index %s REGEXP ?"%('NOT' if invert else '',), (pattern,))
	else:
		addWhere("el_index %s LIKE ?" % ('NOT' if invert else '',), (u"%%%s%%"%toolsql.like_escape(pattern),))
	
	try:
		cursor.execute("""
SELECT el_from, el_to
FROM externallinks 
JOIN page ON page_id = el_from
WHERE """+' AND '.join(where_conditions)+"""
LIMIT ? OFFSET ?;
		""", tuple(where_data)+(limit+1, offset, ), max_time=1800)
	except toolsql.Error as (errno, strerror, extra):
		# 1139 Got error 'trailing backslash (\\)' from regexp
		if errno in (1139,):
			print '<p class="errormsg">%s</p>' % (strerror,)
			return
		elif errno in (1040, 1226, 1317, 2006, 2013):
			from resources_dab_solver import NoOpenConnections
			print '<p class="errormsg">%s</p><blockquote>%r</blockquote>'%(wikipedia.translate(wikipedia.getSite(), NoOpenConnections).encode('utf-8'), (errno, strerror, extra),)
			return
		else:
			raise

	#print cursor.rowcount
	#print cursor.fetchall()
	if cursor.rowcount > limit: printLinks(offset, limit, queryString)
		
	print '<table class="wikitable sortable">'
	print '<colgroup>'
	print '<col style="text-align:right;" />'
	print '<col style="" />'
	print '<col style="text-align:right;" />'
	print '<col style="" />'
	print '</colgroup>'
	print '<tr>'
	print '<th></th><th>Title</th><th>Coordinate</th><th> Parameters</th>'
	print '</tr>'
	idx = offset
	for el_from, el_to in cursor:#.fetchmany(limit):
		print '<tr>'
		#import re
		#el_to = re.sub(r'&(?=[^&=]*(&|$))', '%26', el_to)
		qs = el_to[len(baseUrl):].split('&')
		print type(el_to)
		pagename = u"{pageid:%s}"%el_from
		title    = u''
		params   = u''
		for s in qs:
			if s.startswith('pagename='):
				pagename = s[9:]
				title = wikipedia.urllib.unquote(s[9:].encode('utf-8')).decode('utf-8')
			elif s.startswith('params='):
				params = s[7:]
			elif s.startswith('title=') and pagename == u'':
				pagename = s[6:]
				title = wikipedia.urllib.unquote(s[6:].encode('utf-8')).decode('utf-8')
			else:
				print "<!-- unknown part", s, " -->"

		params += '_'
		plen = len(params)-1
		iProps = min(params.find('_W_')+1 or plen, params.find('_E_')+1 or plen, params.find('_O_')+1 or plen)+1
		idx+=1
		print (u'<td>%s</td><td><a href="//%s/w/index.php?curid=%s" class="extiw">%s</a></td><td><a href="%s" class="external">%s</a></td><td><code>%s</code></td>' % tuple(wikipedia.escape(unicode(s)) if s!=None else u"<i>empty</i>" for s in (
			idx,
			site.hostname(),
			el_from,
			title.replace('_', ' ') or None,
			el_to, 
			params[:iProps].replace('_', ' '), 
			params[iProps:].replace('_', ' '),
			))).encode('utf-8')
		print '</tr>'
	print '</table>'

	if cursor.rowcount > limit: printLinks(offset, limit, queryString)
	
	basehref=''.join(("/~dispenser/cgi-bin/geosearch.py","?",queryString))
	print '<a href="%s">Link to the query you just ran</a>' % basehref

		
if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=False, head='''
<script type="text/javascript">
var Autocheck = true;
function checkregex(n){
	if(Autocheck) {
		n.form.type.checked=(n.value.match(/%s/)!==null);
	}
	// Error on usage of Perl extended syntax
	document.getElementById('slashmatch').style.backgroundColor=((n.form.type.checked && n.value.match(/%s/)!==null)?"lightyellow":"");
}
</script>''' % (r'[\\[\]^$().*+?|]', r'(^|[^\\])(\\\\)*\\[bBdDsSwW]|[*+(}][?+]',))
		main()
	except toolsql.Error as (errno, strerror, extra):
		if errno in (1040, 1226, 2013): # Too many connection / Max connections / Lost connection
			print '<p class="errormsg">Database operational error (%d), retry in a few minutes.</p><blockquote>%s</blockquote>'%(errno, wikipedia.escape(strerror),)
			print '<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>'
		else:
			raise
	finally:
		wikipedia.endContent()
		wikipedia.stopme()
