#!/usr/bin/env python
# -*- coding: utf-8  -*-
import wikipedia, toolsql
import cgitb; cgitb.enable(logdir='tracebacks')

def heading(level, title, style="", className=""):
	wikipedia.sys.stdout.flush()
	wikipedia.html('<h%d id="%s"%s%s>%s<a class="headerlink" href="#%s" title="Permalink to this headline">&#182;</a></h%d>' % (
		level,
		wikipedia.sectionencode(title),
		' style="%s"'%style if style else '',
		' class="%s"'%className if className else '',
		wikipedia.escape(title),
		wikipedia.sectionencode(title), level),
	)

def printu(s, data=None):
	print (s%data if data else s).encode('utf-8')

def quote(s):
	return wikipedia.urllib.quote(s.encode('utf-8') if isinstance(s, unicode) else s, safe=";@$!*(),/:-_.")

def main():
	banners = []
	min_results = 100
	project_results = 0
	def createLink(title, label=None):
		return u'<a href="https://%s/wiki/%s" title="%s">%s</a>'%tuple(wikipedia.escape(s) for s in (
			u'en.wikipedia.org',
			quote(title.replace(' ', '_')),
			title.replace('_', ' '),
			label or title.replace('_', ' '),
		))

	for arg in wikipedia.handleArgs():
		if arg.startswith('-banner:'):
			try:	banners = arg[8:].decode('utf-8').split('|')
			except: banners = arg[8:].decode('latin-1').split('|')
	
	conn=toolsql.getConn('s51290__dpl_p', host='tools.labsdb')
	cursor = conn.cursor()
	wikipedia.logtime('Database connected')
	print """<fieldset>
<legend>Topic points</legend>
<form>
<label for="topic-banner">WikiProject:</label>"""
	try:
		cursor.execute("""
CREATE TEMPORARY TABLE u2815__p.dab_remain (
  dr_page INT(11) UNSIGNED NOT NULL PRIMARY KEY,
  dr_count SMALLINT UNSIGNED NOT NULL
) ENGINE=InnoDB AS 
SELECT DISTINCT adl.article_id AS dr_page, COUNT(*) AS dr_count
FROM s51290__dpl_p.all_dab_links AS adl
JOIN s51290__dpl_p.contest_dabs               ON c_id=dab_id
/* The above table isn't updated frequently */
LEFT JOIN s51290__dpl_p.ch_fixed_links AS cfl ON cfl.article_id=adl.article_id AND cfl.dab_id=adl.dab_id
WHERE cfl.article_id IS NULL
GROUP BY adl.article_id;
""", max_time=5)
		wikipedia.logtime('Built dab_remain table')
		# If a LEFT JOIN (to include 0 pointers), query time increases from 2 sec to 20 sec
		cursor.execute("""
SELECT pb_title, COUNT(*) AS pages, SUM(dr_count) AS points
FROM u2815__p.projectbanner
JOIN u2815__p.dab_remain ON dr_page=pb_page
GROUP BY pb_title
ORDER BY 
  FLOOR(LOG10(SUM(dr_count))) DESC, 
  -- Do this transform twice since CPU is cheaper than memory
  TRIM("_" FROM REPLACE(pb_title, "WikiProject", "")) ASC
""", max_time=30)
	except toolsql.QueryTimedOut as (errno, strerror, extra):
		banners_joined = '|'.join(banners).replace('_', ' ')
		printu('<input name="banner" id="topic-banner" value="%s" size="60" placeholder="%s" />', (wikipedia.escape(banners_joined), "WikiProject History",))
		wikipedia.logtime('Killed topic list %r'%(strerror,))
	else:
		print '<select name="banner" id="topic-banner" onchange="this.form.submit()">'
		group = None
		for pb_title, pages, points in cursor:
			if len(banners)==1 and banners[0]==pb_title:
				project_results=pages
			if len(str(points)) != group:
				if group != None:
					print '</optgroup>'
				group = len(str(points)) if points else 0
				print '<optgroup label="%s">' % ({
					0: 'No points',
					1: 'Less then ten points',
					2: 'Less than a hundred points',
					3: 'Over a hundred points', 
					4: 'Over a thousand points',
					5: 'Over ten thousand points',
					6: 'Over a hundred thousand points',
					7: 'Over a million points',
				}[group],)
			printu(u'<option value="%s"%s>%s\t%s</option>',(
				wikipedia.escape(pb_title), 
				u' selected="selected"' if pb_title in banners else u' disabled="disabled"' if pages > 5000 else u'',
				wikipedia.escape(pb_title.replace('WikiProject', '').replace('_', ' ').strip()), 
				u'(%d points)'%points if points else u'',
			))
		wikipedia.logtime('Generated topic list')
	finally:
		print '</optgroup></select>'
	print """
<button type="submit">Go</button><br/>
</form>"""
	wikipedia.sys.stdout.flush()

	try:
		cursor.execute("""
SELECT TIMESTAMPDIFF(MINUTE, CREATE_TIME, NOW())
FROM information_schema.tables
WHERE TABLE_SCHEMA=? AND TABLE_NAME=?
""", tuple('s51290__dpl_p.ch_fixed_links'.split('.')), max_time=5)
		update_touched = cursor.fetchall().pop()[0]
		printu(u'The list is updated hourly; the last update completed %s minutes ago.', (update_touched,))
		wikipedia.logtime('Table update time')
	except toolsql.QueryTimedOut:
		pass
	print '</fieldset>'

	for banner in banners:
		points_only = True
		#points_only = project_results > min_results 
		verify_links = False#points_only and project_results < 20
		cursor.execute("""
SELECT 
  adl.article_title AS "Article",
  GROUP_CONCAT(adl.dab_title SEPARATOR "|") AS "Dab links",
  COUNT(c_id) AS "Points",
  /*IF(tl_from IS NULL, "", "Yes") AS "{{dn}}",/*
  (SELECT COUNT(*)
    FROM pagelinks 
    JOIN page ON page_namespace=pl_namespace AND page_title=pl_title
    JOIN u2815__p.projectbanner AS plb ON plb.pb_page=page_id AND plb.pb_title=?
    WHERE pl_from=adl.dab_id
  ) AS "ProjChoice"
  /*-*/ "" AS "Tool"

FROM u2815__p.projectbanner
JOIN s51290__dpl_p.all_dab_links AS adl ON article_id=pb_page
%s   JOIN pagelinks ON pl_from=adl.article_id AND pl_namespace=0 AND pl_title=adl.redirect_title
%s   JOIN s51290__dpl_p.contest_dabs   ON c_id=dab_id
-- LEFT JOIN templatelinks            ON tl_from=pb_page AND tl_namespace=10 AND tl_title="Disambiguation_needed"
LEFT JOIN s51290__dpl_p.ch_fixed_links AS cfl ON cfl.article_id=adl.article_id AND cfl.dab_id=adl.dab_id

WHERE pb_title=? AND cfl.article_id IS NULL
GROUP BY pb_page
ORDER BY FLOOR(LOG(5, COUNT(c_id))) DESC, Article ASC;
""" % ("" if verify_links else "-- ", "" if points_only else "LEFT",), (banner,), max_time=180)
		wikipedia.logtime('Queried dablinks pages')
		#printu(u'<div><a class="mw-ui-button" href="../cgi-bin/tasker.py?action=new&banner=%s">Start disambiguating these contest links</a> <a href="#Related_disambiguation_pages">Related disambiguation pages</a></div>', (
		printu(u'<div><a class="mw-ui-button" href="../cgi-bin/tasker.py?action=new&banner=%s">Start disambiguating these contest links</a></div>', (
			quote(banner), #wikipedia.escape(banner)bb
		))
		print '<table class="wikitable lightrow sortable" style="margin:auto;">'
		print '<caption style="font-size:2em; line-height:1.5em;">'
		printu(createLink(u"Wikipedia:%s" % banner, banner.replace('_', ' ')))
		print '</caption>'
		print '<tr>'
		for tup in cursor.description:
			print '<th>%s</th>'%tup[0]
		print '</tr>'
		count = 0 
		for tup in cursor:
			# Cut off zero point articles after we've reached the minimum
			if tup[2] == 0 and count >= min_results:
				#cursor.nextset()
				break
			count += 1
			printu(u'''<tr>
<td>%s</td>
<td>%s</td>
<td>%d</td>
<td><a href="../cgi-bin/dab_solver.py?page=%s&amp;campaign=topic_points&amp;client=topic:%s&amp;fixlink=%s%s" class="mw-ui-button"><span >FIX</span></a></td>
</tr>''',  (
				createLink(tup[0], tup[0].replace('_', ' ')),
				', '.join(createLink(s, s.replace('_', ' ')) for s in tup[1].split('|')),
				tup[2],
				#wikipedia.escape(tup[3]),
				quote(tup[0]),
				quote(banner),
				quote(tup[1]).replace('%7C', '|'),
				'&amp;commonfixes=yes' if wikipedia.SysArgs.get('commonfixes', 'false')=='true' else '',
			))
		print '</table>'
		wikipedia.logtime('Generated HTML results table')
		print 'Displaying %(count)d pages'%locals()


"""
		heading(3, "Related disambiguation pages")
		cursor.execute('''
SELECT
  dab_title AS "Disambiguation page",
  COUNT(*) AS "Links",
  (SELECT COUNT(*) FROM s51290__dpl_p.all_dab_links AS sub WHERE sub.dab_id=main.dab_id) AS Total,
  COUNT(*)/(SELECT Total)*100 AS "%",
  -- c_id IS NOT NULL AS "DPL?",
  (SELECT COUNT(*) FROM s51290__dpl_p.all_dab_links 
/*  LEFT JOIN templatelinks ON tl_from=article_id AND tl_namespace=10 AND tl_title="Disambiguation_needed"*/
  WHERE dab_id=c_id /*AND tl_from IS NULL*/) AS "Points"
FROM  s51290__dpl_p.all_dab_links AS main
JOIN u2815__p.projectbanner ON pb_page=article_id
LEFT JOIN s51290__dpl_p.contest_dabs ON c_id=dab_id
WHERE pb_title=?
AND   c_id IS NOT NULL
GROUP BY dab_id
ORDER BY COUNT(*) * 1/ Total * Points DESC
limit 50;
''', (banner,))
		print '<table class="wikitable lightrow sortable" style="margin:auto;">'
		print '<tr>'
		for tup in cursor.description:
			print '<th>%s</th>'%tup[0]
		print '</tr>'
		for tup in cursor:
			printu(u'''<tr>
<td><a style="float:right;" class="mw-ui-button" href="//tools.wmflabs.org/dplbot/dab_fix_list.php?title=%s">Fix list</a> %s</td>
<td>%s</td>
<td>%s</td>
<td>%s%%</td>
<td>%s</td>
</tr>
''' % (
quote(tup[0]),
createLink(tup[0], tup[0].replace('_', ' ')),
wikipedia.escape(tup[1]) if isinstance(tup[1], (bytes, str, unicode)) else tup[1],
wikipedia.escape(tup[2]) if isinstance(tup[2], (bytes, str, unicode)) else tup[2],
wikipedia.escape(tup[3]) if isinstance(tup[3], (bytes, str, unicode)) else tup[3],
wikipedia.escape(tup[4]) if isinstance(tup[4], (bytes, str, unicode)) else tup[4],
))
	print '</table>'
#"""

if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=False)
		main()
	except toolsql.DatabaseError as (errno, strerror, extra):
		if errno in (1040, 1226, 2013): # Too many connection / Max connections / Lost connection
			print '<p class="errormsg">Database operational error (%d), retry in a few minutes.</p><blockquote>%s</blockquote>'%(errno, wikipedia.escape(strerror),)
			print '<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>'
		else:
			raise
	finally:
		wikipedia.endContent()
		wikipedia.stopme()

