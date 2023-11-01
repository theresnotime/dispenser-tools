#!/usr/bin/env python
# -*- coding: utf-8  -*-
import cgi, urllib
import wikipedia
import toolsql
import cgitb; cgitb.enable(logdir='tracebacks')

def main():
	def get_form_int(name, defaultValue):
		try:
			return int(form.getfirst(name, defaultValue))
		except ValueError:
			return defaultValue
	form = cgi.FieldStorage()
	limit  = get_form_int('limit', 100)
	offset = get_form_int('offset', 0)
	page   = wikipedia.Page(
			wikipedia.getSite(),
			form.getfirst('prefix', form.getfirst('page', form.getfirst('title', 'Main_Page'))), 
			defaultNamespace=get_form_int('namespace', 0)
	)
	namespace = page.namespace()
	prefix = page.titleWithoutNamespace(underscore=True)

	def phrase_link(title, label="", className=None):
		return u'<a href="https://%s/wiki/%s" class="%s" title="%s">%s</a>'%tuple(wikipedia.escape(s) for s in (
			page.hostname(),
			urllib.quote(title.replace(' ', '_').encode('utf-8'), safe=";@$!*(),/:-_."),
			className or '',
			title.replace('_', ' '),
			label or title.replace('_', ' '),
		))
		
	
	conn   = toolsql.getConn(page.site().dbName(), cluster='web')
	cursor = conn.cursor()
	
	replag = cursor.replag()
	if replag > 60*5:
		# See [[MediaWiki:lag-warn-normal]] and [[MediaWiki:lag-warn-high]]
		replag_m = replag // 60
		print('<div class="mw-lag-warn-high">%s</div>'%("Due to high database server lag, changes newer than %d minutes may not be shown."%(replag_m,)))
	else:
		pass # Replag OK
	
	print '<p>Display redlinks with prefix: <code>%s</code></p>'%(page.title().encode('utf-8'),)
	cursor.execute("""
SELECT 
  pl_namespace,
  pl_title,
  "",-- ns_name, /* text for pl_namespace above */
  COUNT(*) AS link_count, 
  SUM(ref.page_namespace = pl_namespace) AS ns_count,
  (SELECT GROUP_CONCAT(DISTINCT DATE_FORMAT(log_timestamp, "%b %Y") SEPARATOR ", ")
    FROM logging_logindex
    WHERE log_namespace = pl_namespace AND log_title = pl_title
    AND log_action = "delete"
  ) AS log_deletes, 
-- XXX Hack until tables are added
--  (SELECT IF(ref.page_namespace=0, ref.page_title, CONCAT(ns_name,":",ref.page_title))
--    FROM u2815__p.namespacename
--    WHERE dbname = (SELECT DATABASE())
--    AND ns_id = ref.page_namespace AND ns_is_favorite = 1
--  ) AS example_title_full,
 CONCAT(
 IF(ref.page_namespace=0,   "",
 IF(ref.page_namespace=1,   "Talk:", 
 IF(ref.page_namespace=2,   "User:", 
 IF(ref.page_namespace=3,   "User_talk:", 
 IF(ref.page_namespace=4,   "Wikipedia:", 
 IF(ref.page_namespace=5,   "Wikipedia_talk:", 
 IF(ref.page_namespace=6,   "File:", 
 IF(ref.page_namespace=7,   "File_talk:", 
 IF(ref.page_namespace=8,   "MediaWiki:", 
 IF(ref.page_namespace=9,   "MediaWiki_talk:", 
 IF(ref.page_namespace=10,  "Template:", 
 IF(ref.page_namespace=11,  "Template_talk:", 
 IF(ref.page_namespace=12,  "Help:", 
 IF(ref.page_namespace=13,  "Help_talk:", 
 IF(ref.page_namespace=14,  "Category:", 
 IF(ref.page_namespace=15,  "Category_talk:", 
 IF(ref.page_namespace=100, "Portal:", 
 IF(ref.page_namespace=101, "Portal_talk:", 
 IF(ref.page_namespace=108, "Book:", 
 IF(ref.page_namespace=109, "Book_talk:", 
 IF(ref.page_namespace=118, "Draft:", 
 IF(ref.page_namespace=119, "Draft_talk:", 
 IF(ref.page_namespace=710, "TimedText:", 
 IF(ref.page_namespace=711, "TimedText_talk:", 
 IF(ref.page_namespace=828, "Module:", 
 IF(ref.page_namespace=829, "Module_talk:", 
 CONCAT("{ns:",ref.page_namespace,"}:")
 )))))))))))))))))))))))))),ref.page_title) AS example_title_full,
  ref.page_namespace,
  ref.page_title
FROM page AS ref
JOIN pagelinks              ON pl_from = ref.page_id
-- JOIN u2815__p.namespacename ON dbname = (SELECT DATABASE()) AND ns_id = pl_namespace AND ns_is_favorite = 1
LEFT JOIN page AS pl        ON pl.page_namespace = pl_namespace AND pl.page_title = pl_title
WHERE pl.page_id IS NULL
AND   pl_namespace = ?
AND pl_title LIKE ?
GROUP BY pl_namespace, pl_title
LIMIT ?, ?
""", (namespace, toolsql.like_escape(prefix)+'%', offset, limit+1), max_time=180)

	results = cursor.fetchmany(limit)
	print '<!-- results -->'
	if results:
		print '<ul>'
		for pl_namespace, pl_title, ns_name, links, ns_links, log_deletes, example_title_full, example_ns, example in results:
			title = ns_name+':'+pl_title if ns_name else pl_title
			ns_label = (ns_name or 'article').lower()
			# TODO merge with related.py article namespace only wording code
			if ns_links==0 or links==ns_links:
				desc = u"%d %s link%s" % (links, ns_label if ns_links else '', '' if links==1 else 's',)
			else:
				desc = u"%d link%s with %d from %s space" % (links, '' if links==1 else 's', ns_links, ns_label, )
			#if example_ns==0 and links==1:
			if links==1:
				s = u"%s from %s" % (phrase_link(title, className="new"), phrase_link(example_title_full))
			else:
				s  = phrase_link(title, className="new") + ' (' + phrase_link("Special:WhatLinksHere/%s"%title, desc) + ')'
			if log_deletes:
				s += u', <b>deleted %s</b>' % log_deletes
			print '<li>%s</li>'%s.encode('utf-8')
		print '</ul>'
		print '<!-- /results -->'
		if cursor.fetchone():
			print '<p>Showing results %d-%d, <a href="?page=%s&offset=%d&limit=%d">Next %d</a></p>'%(
				offset+1, limit+offset, 
				page.urlname(), limit+offset, limit,
				limit,
			)
	else:
		print '<!-- /results -->'
		print "There were no results"

if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=True)
		main()
	except toolsql.Error as (errno, errmsg, extra):
		if errno in (1040, 1317, 1226, 2013): # Too many connection / Query killed / Max connections / Lost connection
			print '<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>'
			print '<p class="errormsg">oursql.Error(%d, %r)<br/>Please try again in a few minutes.</p>' % (errno, errmsg,)
		else:
			raise
	finally:
		wikipedia.endContent()
		wikipedia.stopme()
