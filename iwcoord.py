#!/usr/bin/env python
# -*- coding: utf-8  -*-
import oursql, sys
import time; starttime=time.time()

# Simple connection pooling
connections = {}
def getCursor(dbname, host=None):
	if not host: host="sql-s%d-rr" % wikiservers[dbname] if dbname in wikiservers else "%s.rrdb"%dbname.replace('_', '-')
	if host not in connections:
		connections[host] = oursql.connect(host=host, read_default_file='~/.my.cnf', charset=None, use_unicode=False)
	cursor = connections[host].cursor()
	cursor.execute('USE '+dbname)
	return cursor
 
cursor = getCursor(dbname='toolserver', host='sql')
cursor.execute("SELECT dbname, server FROM toolserver.wiki WHERE domain IS NOT NULL")
wikiservers = dict( cursor.fetchall() )
langcorr = { # Corrects to the language codes in use
	'zh-classic':	'zh-classical',
	'zh-tw':		'zh',
	'nan':			'zh-min-nan',
	'nb':			'no',
	'dk':			'da',
}

def main():
	dbName = ''
	template = 'Coord_missing'
	maxresults = 5000
	baseUrl = "http://org.toolserver./~geohack/geohack.php?_%"
	for arg in sys.argv[1:]:
		if arg.startswith('-dbname:'):
			dbName = arg[8:]
		elif arg.startswith('-template:'):
			template = arg[10:]

	if not dbName:
		dbName = raw_input('Database [%s]:'%'enwiki') or 'enwiki'
		template = raw_input('Template [%s]:' % template) or template

	conn = oursql.connect(db=dbName+'_p', host=dbName.replace('_', '-')+'-p.rrdb', read_default_file="/home/dispenser/.my.cnf", use_unicode=False)
	
	cursor = conn.cursor()
	# TODO GROUP_CONCAT(ll_lang, ll_title)
	cursor.execute("""
/* iwcoord.py SLOW_OK */
SELECT page_title, ll_lang, ll_title
FROM templatelinks
JOIN page          ON tl_from=page_id 
JOIN langlinks     ON ll_from=tl_from /* AND ll_lang in ('de', 'fr') */
WHERE page_namespace=0
AND tl_namespace=? AND tl_title=?
LIMIT ?
""", (10, template, maxresults,))
	
	print '# title  \tinterwiki \tprimary\tparams'
	mising_coord_pages = 0
	count = 0
	last = ''
	for title, lang, ll_title in cursor:
		iwfindcoords(title.replace('_', ' '), lang, ll_title, baseUrl)
		if title != last:
			last=title
			mising_coord_pages += 1
		count += 1
	print 
	print "Looked at %(count)d interwikis of %(mising_coord_pages)d pages" % locals()
	#print "Examined %d, found %d"

def iwfindcoords(title, lang, ll_title, baseUrl):
		try:
			# Workaround for multiple language aliases not supported directly in the TS' DB
			cursor = getCursor(langcorr.get(lang, lang).replace('-', '_')+'wiki_p')
		except oursql.Error as (errno, strerror, extra):
			if errno == 2005:
				print "DEPRECATED: %s alias not in listed for [[%s:%s]] on [[%s]]" % (lang, lang, ll_title, title)
			elif errno == 1049: # Unknown database
				print "File a JIRA ticket to add %s to the Toolserver" % strerror
				return
			else:
				raise

		cursor.execute("""
/* iwcoord LIMIT:60 */
SELECT el_index
FROM page
JOIN externallinks ON page_id = el_from
WHERE page_namespace=? AND page_title = ?
AND el_index LIKE ?
""", (0, ll_title.replace(' ', '_'),  baseUrl,))

		for (el_index, ) in cursor:
			begin = el_index.find('params=')+7
			end   = el_index.find('&', begin)
			if begin > 8: # -1 + 7
				params = el_index[begin: end if end > begin else None]

				print '[[%s]]\t[[%s:%s]]\t%s\t%s' % (title, lang, ll_title, 'no' if 'title=' in el_index else 'yes', params)
		cursor.close()

if __name__ == "__main__":
	try:
		main()
	finally:
		print "Completed in %#3.2f minutes" %((time.time()-starttime)/60.0,)

