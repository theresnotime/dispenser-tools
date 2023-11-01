#! /usr/bin/python
# -*- coding: utf-8  -*-
"""

bash:
export PYTHONPATH="$HOME/pywikipedia"
$HOME/pyscripts/glupt.py -page:Wikipedia:WikiProject_Geographical_coordinates/coordinates_search_tool
"""
# muslc - Matching User Specified list counter
# External Link 
# ghlump - GeoHack Links User Matched Pattern
# CLUPC - Coord link User Pattern Counter
# upelt - User Pattern External Link Tallier
# elupt - External Links User pattern Tailler
# glupt - Geo link user pattern tallier
import time, re, os
os.sys.path.append('/home/dispenser/pywikibot')
import wikipedia as pywikibot
import cgitb; cgitb.enable(logdir='/home/dispenser/public_html/cgi-bin/tracebacks/')

import oursql
connection={}
def getConn(dbname, host=None):
	if not dbname.endswith('_p'):dbname+='_p'
	if (host,dbname) not in connection:
		connection[host,dbname] = oursql.connect(
			db=dbname, 
			#host=host or dbname[:-2]+'.labsdb', 
			host=host or dbname[:-2]+'.analytics.db.svc.eqiad.wmflabs', 
			read_default_file=os.path.expanduser('~/.my.cnf'), 
			charset=None, 
			use_unicode=False
		)
	return connection[host,dbname]

def removeHtml(s):
	return re.sub(r'</?\w+[^<>]*>', '', s)

def el_index_convert(url):
	dBegin = 8 if url.startswith('https:') else 7
	dEnd = url.index('/', dBegin)
	return url[:dBegin]+'.'.join(reversed(url[dBegin:dEnd].split('.')))+'.'+url[dEnd:]

def main():
	page = None
	host = None
	dbName = ''
	limit = None
	for arg in pywikibot.handleArgs():
		if arg.startswith('-page:'):
			page=pywikibot.Page(pywikibot.getSite(), arg[6:])
		elif arg.startswith('-host:'):
			host = arg[6:]
		elif arg.startswith('-wiki:'):
			#dbName = arg[6:]
			pass
		elif arg.startswith('-limit:'):
			limit = int(arg[7:])
		else:
			pywikibot.output('Unknown argument: %s' % arg)

	if not page:
		pywikibot.showHelp()
		return
	begintime = time.time()
	try:site = page.site()
	except TypeError: site = page.site
	dbName = site.dbName()

	#filename = "/home/dispenser/public_html/logs/ghlump-%s-%s.log" % (dbName[:-2], page.title(underscore=True),)
	filename = "/home/dispenser/public_html/logs/glupt.log"
	regexRules = re.compile(r"""
<tr>
<td>(?P<desc>.*?)</td>(
<td>.*?</td>)*?
<td><code>(?P<regex>.*?)</code></td>
</tr>""")
	
	rules = []
	#path = site.family.page_action_address(site.language(), page.urlname(), "render")
	html = site.getUrl(site.nice_get_address(page.urlname())).encode('utf-8')
	#html = html[html.find('Portuguese Wikipedia')+1:] # XXX only the second table
	html = html[html.find('id="glupt-source"')+1:]
	for m in regexRules.finditer(html):
		try:
			regex = pywikibot.unescape(m.group('regex'))
			rules.append({
				"description": removeHtml(m.group('desc')),
				"search": regex,
				"regex": re.compile(regex, flags=re.U),
				"count": 0,
				"ids": [],
			})
		except re.error as errmsg:
			pywikibot.output("%r Error: %s"%(regex, errmsg,))
	
	conn   = getConn(dbName, host=host)
	cursor = conn.cursor()
	coord_urls = [
		"http://toolserver.org/~geohack/geohack.php?%",
		# {{fullurl:tools:~geohack/LANG/PARAMS}}
		"https://toolserver.org/\\%7Egeohack/__/_%",
		# Unoffical build on WMF Labs
		#"http://tools.wmflabs.org/geohack/geohack.php?%",
		"https://tools.wmflabs.org/geohack/geohack.php?%",
	]
	cursor.execute("SELECT @@hostname")
	(server_name,) = cursor.fetchall()[0]
	# Regarding [[Bug 10593]], the optimizing optimizes it correctly 
	cursor.execute("""/* glupt.py SLOW_OK LIMIT:7200 */
SELECT SQL_CACHE el_from, el_index
FROM externallinks
JOIN page ON page_id=el_from
-- JOIN toolserver.namespace ON ns_id=page_namespace AND dbname=(SELECT DATABASE())
WHERE page_namespace=0 AND (%s) %s"""%(
	" OR ".join(("el_index LIKE ?",)*len(coord_urls)),
	"LIMIT %d,%d"%(0,limit) if limit else '',
),	tuple(el_index_convert(url) for url in coord_urls))

	rows = 0
	for el_from, el_to in cursor.fetchall():
		rows += 1
		for rule in rules:
			if rule["regex"].search(el_to):
				#if rule["count"] < 250 and len(rule["ids"]) <= 25:
				if len(rule["ids"]) <= 32:
					rule["ids"].append(int(el_from))
				rule["count"] += 1
	
	with open(filename, 'w+b') as f:
		f.write(b' Count Problem description \n')
	#	f.write('Problem description \tMySQL regular expression query\tCount\n')
		for rule in rules:
		#	f.write("%(count)d\t%(description)s\t%(search)s\n" % rule)
		#	titles = []
			sample = ''
			linelen = 0
			page_ids = rule["ids"]
			cursor.execute('SELECT REPLACE(page_title,"_"," ") AS title FROM page WHERE page_id in (%s)'%','.join(('?',)*len(page_ids) or '""'), page_ids)
			# Weird wrapping system
			for title in cursor.fetchall():
				link = b"[[%s]]"%title
				linelen += len(link) + 2
				if not sample:
					sample = link
				elif linelen <= 120:
					sample += b', %s'%link
				else:
					sample += b',\n%s'%link
					linelen = len(link)
			#f.write("%s\t%s%s\t%d\n%s\n"% (rule["description"], rule["search"][:80], len(rule["search"])>80 and '...' or '', rule["count"], ', '.join(titles),))
			f.write((u"%(count)6d %(description)s\n"%rule).encode('utf-8'))
			if sample:
				f.write(b"\n%s\n%s\n\n"%(rule['search'].encode('utf-8'), sample,))
		f.write("Scanned %s main namespace external links in %4.1f minutes on %s\n" % (rows, (time.time()-begintime) / 60.0, server_name,))

if __name__ == "__main__":
	main()

