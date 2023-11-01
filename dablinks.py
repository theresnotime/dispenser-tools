#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
This script executes an SQL query which finds links needing disambiguation.  
It presents these links either human or machine readable formats.  It is able 
to be used across multiple languages and wikis when [[MediaWiki:
Disambiguationspage]] is setup.

These command line parameters can be used to specify which pages to work on:

&params;

   -format:X    Changes the output format, options are JSON, XML, and HTML.  
                HTML operates a little differently limiting to useful 
				information and require webpywikipedia to work.

   -callback:  When specified with format as JSON wraps the output into a given 
               function.
"""
import wikipedia, pagegenerators
import oursql
import toolsql
import cgitb; cgitb.enable(logdir='tracebacks')


def printu(s, data=None):
	print (s%data if data else s).encode('utf-8')

connections = {}
def getConn(dbname, host=None, reconnect=False):
	if not dbname.endswith('_p'): dbname+='_p'
	if (host,dbname) in connections:
		try:connections[host,dbname].ping()
		except:reconnect=True
	if (host,dbname) not in connections or reconnect:
		connections[host,dbname] = oursql.connect(
			db=dbname,
			#host=host or dbname.replace('_', '-')+'.rrdb',
			host=host or dbname[:-2]+'.labsdb',
			read_default_file="/home/dispenser/.my.cnf",
			local_infile=True,
			charset="utf8",
			use_unicode=False,
			raise_on_warnings=False
		)
	return connections[host,dbname]

def canonicalTitle(title, firstupper=True, underscore=False):
	"""
	Converts unicode or bytes string to mw titles
	support: percent-encoded UTF-8, HTML character references
	"""
	# TODO namespace support, e.g. [[WP: Foo]]
	if isinstance(title, unicode):
		title = title.encode('utf-8')
	# Unpercent-encode
	title = wikipedia.urllib.unquote(title)
	try:   title = unicode(title, 'utf-8')
	except:title = unicode(title, 'latin-1')
	# HTML character references
	title = wikipedia.html2unicode(title)
	# Remove ltr and rtl markers
	title = title.replace(u'\u200e', '').replace(u'\u200f', '')
	# Strip the section part
	if u'#' in title:
		title = title[:title.index(u'#')]
	# Underscore + &nbsp; to space and Strip space
	title = u''.join(u' ' if c.isspace() or c==u'_' else c for c in title).lstrip(u': ').strip()
	# Merge multiple spaces
	while u'  ' in title:
		title = title.replace(u'  ', u' ')
	# First uppercase
	if firstupper and title:
		title = title[0:1].upper() + title[1:]
	if underscore:
		title = title.replace(u' ', u'_')
	return title

def query(wiki, query, inputs):
	with getConn(wiki).cursor() as cursor:
		cursor.execute(query, tuple(t.encode('utf-8') if isinstance(t, unicode) else t for t in inputs))
		return cursor.fetchone()

def findTemplateLinksTo(page, ns, title):
	return query(page.site().dbName(), """/* dab_solver.findTemplateLinksTo LIMIT:1 NM */
SELECT CONCAT(ns_name, ':', tl_title)
FROM page AS dab
JOIN templatelinks ON tl_from = dab.page_id
JOIN page AS tl    ON tl.page_namespace=tl_namespace AND tl.page_title=tl_title
JOIN pagelinks     ON pl_from = tl.page_id
LEFT JOIN u2815__p.namespacename ON ns_id=tl_namespace AND dbname=(SELECT DATABASE()) AND ns_is_favorite=1
WHERE dab.page_namespace = ? AND dab.page_title = ?
AND pl_namespace = ?         AND pl_title = ?
/* Excluded self-transclusion */
AND NOT (tl_namespace=dab.page_namespace AND tl_title=dab.page_title)
LIMIT 1""",
		(page.namespace(),
		page.titleWithoutNamespace(underscore=True),
		ns,
		title.replace(' ', '_'),
		)
	)

def api_findTemplateLinksTo(page, ns, title):
	import json
	data = {
		'action':'query',
		'format':'json',
		'utf8': 'yes',
		'titles': title,
		'generator':'links',
		'redirects':'redirects',
		'prop':'pageprops',
		'ppprop':'disambiguation',
		'gpllimit':'500',
		'continue': '', # Use new Continuing Queries
	}
	site = wikipedia.Site(dbname)
	results = []
	return results
	
def getSelfRedirects(dbname, namespace, title):
	conn = toolsql.getConn(dbname)
	with conn.cursor() as cursor:
		cursor.execute("""
/* dablinks.getSelfRedirects */
SELECT pl.page_namespace, pl.page_title, rd_fragment
FROM page
JOIN pagelinks  ON pl_from=page.page_id
JOIN page AS pl ON pl.page_namespace=pl_namespace   AND pl.page_title=pl_title
JOIN redirect   ON rd_namespace=page.page_namespace AND rd_title=page.page_title AND rd_from=pl.page_id

WHERE page.page_namespace=? AND page.page_title=?
-- AND (rd_fragment IS NULL OR rd_fragment='')

ORDER BY pl.page_id;
""", (namespace, title.encode('utf-8'),), max_time=10)
		return cursor.fetchall()

def api_getSelfRedirects(dbname, namespace, title):
	import json
	#if namespace!=0:raise "Only works on main space pages"
	site = wikipedia.Site(dbname)
	request = {
		'action':'query',
		'format':'json',
		'utf8': 'yes',
		'titles': '%s:%s'%(wikipedia.namespaces.get(namespace), title) if namespace else title,
		'generator':'links',
		'gpllimit':'500',
		'redirects':'redirects',
	}
	lastContinue = {'continue': '' }
	results = []

	for i in xrange(10):
		req = request.copy()
		req.update(lastContinue)
		rsp_json=json.loads(site.getUrl(site.apipath(), data=req))
		if 'error' in rsp_json: raise Error(rsp_json['error'])
		if 'warnings' in rsp_json and wikipedia.Debug: print(rsp_json['warnings'])
		if 'query' not in rsp_json: break

		for redirect in rsp_json['query'].get('redirects', []):
			if redirect['to'].replace(' ', '_')==title:
#SELECT pl.page_namespace, pl.page_title, rd_fragment
# TODO for pages... find page get ns
				results.append((
				0, # wrong
				redirect['from'].encode('utf-8'),
				None, # Stub
				))
		
		# Query-Continue
		lastContinue = rsp_json.get('continue', {})
		if not lastContinue:
			break
	return results

def main():
	genFactory = pagegenerators.GeneratorFactory()
	return results

def getDabLinks(dbname, namespace, title):
	if isinstance(dbname, (bytes, str, unicode)):
		cursor = getConn(dbname).cursor()
	else:
		cursor = dbname
	cursor.execute("""/* dablinks.getDabLinks LIMIT:180 */
SELECT
  pl_namespace AS namespace,
  CONCAT(ns_name, IF(ns_name="", '', ':'), pl_title) AS title,
  EXISTS (
    SELECT 1 FROM pagelinks
    WHERE pl_from=pp_page AND pl_namespace=page.page_namespace AND pl_title=page.page_title
  ) AS linksback,
  NULL as tl_title,
  rd_namespace,
  rd_title

FROM page
JOIN pagelinks       ON pl_from = page.page_id
JOIN page AS pl      ON pl.page_namespace = pl_namespace AND pl.page_title = pl_title
JOIN s51892_toolserverdb_p.namespacename    ON ns_id = pl_namespace AND ns_is_favorite = 1 AND dbname = (SELECT DATABASE())
LEFT JOIN redirect   ON rd_from = pl.page_id
LEFT JOIN page AS rd ON rd.page_namespace = rd_namespace AND rd.page_title = rd_title
JOIN page_props      ON pp_page = IFNULL(rd.page_id, pl.page_id) 

WHERE page.page_namespace=? AND page.page_title=?
AND pp_propname="disambiguation"
GROUP BY pl.page_id
""", (namespace, title,))
	results = cursor.fetchall()
	return results


def api_getDabLinks(dbname, ns, title):
	import json
	#if ns!=0:raise "Only works on main space pages"
	site = wikipedia.Site(dbname)
	request = {
		'action':'query',
		'format':'json',
		'utf8': 'yes',
		'titles': '%s:%s'%(wikipedia.namespaces.get(ns), title) if ns else title,
		'generator':'links',
		'redirects':'redirects',
		'prop':'pageprops',
		'ppprop':'disambiguation',
		'gpllimit':'500',
	}
	lastContinue = {'continue': '' }
	results = []

	for i in xrange(10):
		req = request.copy()
		req.update(lastContinue)
		rsp_json=json.loads(site.getUrl(site.apipath(), data=req))
		if 'error' in rsp_json: raise Error(rsp_json['error'])
		if 'warnings' in rsp_json and wikipedia.Debug: print(rsp_json['warnings'])
		if 'query' not in rsp_json: break

		for page_results in rsp_json['query']['pages'].itervalues():
			if 'pageprops' in page_results:
				link_title = page_results['title']
				redir_title=None
				for redir in rsp_json['query'].get('redirects', []):
					if redir['to'] == link_title:
						link_title  = redir['from']
						redir_title = redir['to']
				
				results.append((
				page_results['ns'],
				link_title.encode('utf-8'),
				None, # Links back - Unavailable
				None, # Not Applicable
				page_results['ns'], # Incorrect
				redir_title.encode('utf-8') if isinstance(redir_title, bytes) else redir_title,
				))
		
		# Query-Continue
		lastContinue = rsp_json.get('continue', {})
		if not lastContinue:
			break
	return results

def main():
	genFactory = pagegenerators.GeneratorFactory()
	format = "html"
	callback = None
	# Up the limit for genFactory
	genFactory.limit = 500
	notunderstood = []
	for arg in wikipedia.handleArgs():
		if arg.startswith('-format:'):
			format = arg[8:]
		elif arg.startswith('-callback:'):
			callback = arg[10:]
		else:
			if not genFactory.handleArg(arg):
				notunderstood.append(arg)
	generator = genFactory.getCombinedGenerator() or iter([])
	
	# FIXME this has the nasty effect it will cause the genFactory to repopulate the results look into fixing genFactory or handleUrlAndHeader()
	if format=="html":
		if not wikipedia.handleUrlAndHeader(defaultRedirect="/~dispenser/view/Dablinks"):
			return 
		wikipedia.startContent(form=True)
		try:
			page = None
			for page in pagegenerators.DuplicateFilterPageGenerator(generator):
				site = page.site()
				#conn = getConn(site.dbName())
				#cursor = conn.cursor()
				def htmlLink(title, redirect=False, section=None):
					if isinstance(title, unicode):
						title = title.encode('utf-8')
					t = wikipedia.urllib.quote(title.replace(' ', '_'))
					title = title.replace('_', ' ')
					return '<a href="//%s%s%s" title="%s">%s%s</a>'%(
						site.hostname(), 
						site.get_address(t) if redirect else site.nice_get_address(t), 
						'#%s'%wikipedia.sectionencode(section) if section else '', 
						wikipedia.escape(title), 
						wikipedia.escape(title),
						'#%s'%wikipedia.escape(section.encode('utf-8')) if section else '', 
					)

				# TODO remove this casing & redirect hack
				# XXX hack to avoid checking if firstupper in enabled in the wiki
				title = page.titleWithoutNamespace(underscore=True).encode('utf-8')
				#exists = query(site.dbName(), "SELECT (SELECT page_is_redirect FROM page WHERE page_namespace=? AND page_title=?), (SELECT page_is_redirect FROM page WHERE page_namespace=? AND page_title=?)", (page.namespace(), title, page.namespace(), canonicalTitle(title, underscore=True).encode('utf-8'),))
				#if exists == (None, None):
				#	wikipedia.output("%s does not exist"%page.aslink())
				#	continue
				#elif exists == (None, 0):
				#	page._title = canonicalTitle(title, underscore=True)
				#elif 1 in exists:
				#	wikipedia.output("%s is a redirect page"%page.aslink())
				#	continue
				

				#results = tuple(result for result in getDabLinks(site.dbName(), page.namespace(), page.titleWithoutNamespace(underscore=True)) if not result[2])
				results = tuple(result for result in api_getDabLinks(site.dbName(), page.namespace(), page.titleWithoutNamespace(underscore=True)) if not result[2])
				if results:
					print('<p>%s links to %d %s (<a href="/~dispenser/cgi-bin/dab_solver.py?page=%s&%s" class="extiw" style="font-weight:bold;">fix&nbsp;links</a>).</p>'%(
						htmlLink(page.title()),
						len(results),
						'disambiguation page' if len(results)==1 else 'different disambiguation pages',
						page.title(asUrl=True, allowInterwiki=True, forceInterwiki=True).encode('utf-8'),
						'&amp;'.join(part for part in ('commonfixes=yes' if wikipedia.SysArgs.get("commonfixes", '')!='false' else '', 'client=Dablinks') if part),
					))
					print('<ul>')
					for result in results:
						if not result[5]:
							print '<li>%s</li>'%htmlLink(result[1])
						else:
							print '<li>%s (redirect page)<ul><li>%s</li></ul></li>'%(htmlLink(result[1], redirect=True), htmlLink(result[5]))
					print('</ul>')
				else:
					print '<p class="noresults">No disambiguation links on %s.</p>'%(htmlLink(page.title()),)
				results = api_getSelfRedirects(site.dbName(), page.namespace(), page.titleWithoutNamespace(underscore=True))
				if results:
					print '<p class="selfredirects">%s links to %d %s which point back.</p>'%(htmlLink(page.title()), len(results), 'redirect' if len(results)==1 else 'redirects')
					print '<ul class="selfredirects">'
					for tup in results:
						print '<li>%s (redirect page)<ul><li>%s</li></ul></li>'%(htmlLink(tup[1]), htmlLink(page.title(), section=tup[2].decode('utf-8') if isinstance(tup[2], bytes) else tup[2]))
					print '</ul>'
			else:
				if not page:
					if notunderstood:
						wikipedia.output(u'Not understood:'+u''.join(['\nNot understood: %r'%arg for arg in notunderstood]))
					else:
						printu(u'<img src="//bits.wikimedia.org/skins-1.5/common/images/redirectltr.png" alt="#REDIRECT " /><span class="redirectText"><a href="/~dispenser/view/Dablinks">tools:~dispenser/view/Dablinks</a></span>')
		except oursql.Error as (errno, strerror, extra):
			# Something went wrong with the database
			# 1040 "Too many connections":
			# 1226 "User %r has exceeded the %r resource": Too many user connections
			# 1267 "Illegal mix of collation": s3 is still running MySQL 4
			# 1290 "--read-only option"
			# 1317 "Query execution was interrupted" (query-killer)
			# 2006 "MySQL server has gone away":
			# 2013 "Lost connection to MySQL server during query":
			# 2014 "Commands out of sync; you can't run this command now":
			# 2027 "Malformed packet"
			if errno in (1040, 1226, 1317, 2006, 2013):
				from resources_dab_solver import NoOpenConnections
				printu(u'<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>')
				printu(u'<p>%s</p><blockquote>%r</blockquote>', (wikipedia.translate(wikipedia.getSite(), NoOpenConnections), (errno, strerror, extra),))
				pass
			else:
				print '<p class="errormsg">oursql Error (%d): %s</p>' % (errno, wikipedia.escape(strerror))
				raise
		finally:
			wikipedia.endContent()
	elif format=="python":
		out = {
			"query": {
					"pages": {
					}
				}
			}
		for page in generator:
			# should be pageid not pagetitle
			out["query"]["pages"][page.title()] = {
				"pageid":	None,
				"ns":	page.namespace(),
				"title":	page.title().encode('utf-8'),
				"disambiguationlinks":[],
			}
			results = getDabLinks(page.site().dbName(), page.namespace(), page.titleWithoutNamespace(underscore=True))
			for result in results:
				item = {
					"ns":result[0],
					"title":	result[1].replace('_', ' '),
					"linksback":	bool(result[2]),
					"template":	result[3],
				}
				if result[5]:
					item["targetns"]=result[4]
					item["target"]=result[5]

				out["query"]["pages"][page.title()]["disambiguationlinks"].append(item)

			#out["query"]["pages"][page.title()]["pageid"]=None
		print 'Content-type: application/python'
		print
		print "%r"%out

	elif format=="php":
		pass

	# FIXME json hack until wrapper works
	elif format=="json":
		output = '{"query":{"pages":{'
		pagenum = 0
		def js_row_escape(l):
			for x in l:
				# FIXME move this conversion step into the title conconalicazation
				yield wikipedia.jsescape(x).replace('_', ' ')
		# TODO add error messages
		for page in generator:
			results = getDabLinks(page.site().dbName(), page.namespace(), page.titleWithoutNamespace(underscore=True))

			if results:
				if pagenum: output+=','
				output += '"%s":{"pageid":%s,"ns":%d,"title":%s,"disambiguationlinks":[\n'%(pagenum, 'null', page.namespace(), wikipedia.jsescape(page.title()))
#				items = [dict(zip(('ns','title','linksback','template','targetns','target'),row)) for row in results]
#				for attr in items:
#					if item[attr] is None:
#						del item[attr]
#				output += wikipedia.jsescape(items)
				output += b',\n'.join(
					b'{"ns":%s,"title":%s,"linksback":%s,"template":%s,"targetns":%s,"target":%s}'%tuple(js_row_escape(row))
					if row[5] else 
					b'{"ns":%s,"title":%s,"linksback":%s,"template":%s}'%tuple(js_row_escape(row[0:4]))
					for row in results
				)
				output += '\n]}'
				pagenum += 1
			
		output += '}}}'
		output = output
		print "Status: 200 Done"
		print "Content-type: application/json; charset=utf-8"
		#print "Content-type: text/plain; charset=utf-8"
		print
		print "%s(%s)"%(callback, output) if callback else output
	# xml interface until wrapper works
	elif format=="xml":
		print "Content-type: application/xml; charset=utf-8"
		print
		print '<?xml version="1.0"?>'
		print '<api>'
		print '<query>'
		print '<pages>'
		def html_out(s_format, opts):
			print s_format % tuple(wikipedia.escape(bytes(x)) for x in opts)
		for page in generator:
			results = getDabLinks(page.site().dbName(), page.namespace(), page.titleWithoutNamespace(underscore=True))
			if results:
				html_out('<page ns="%s" title="%s">', (page.namespace(), page.title().encode('utf-8')))
				print '<disambiguationlinks>'
				for result in results:
					if not result[5]:
						html_out('<dl ns="%s" title="%s" linksback="%s" template="%s"/>', result[:-2])
					else:
						html_out('<dl ns="%s" title="%s" linksback="%s" template="%s" targetns="%s" target="%s" />', result)
				print '</disambiguationlinks>'
				print '</page>'
		print '</pages>'
		print '</query>'
		print '</api>'


if __name__ == "__main__":
	try:
		main()
	finally:
		wikipedia.stopme()
