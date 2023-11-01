#!/usr/bin/env python
# -*- coding: utf-8  -*-
import wikipedia; from wikipedia import logtime
import re, requests, json
import cgitb; cgitb.enable(logdir='tracebacks')
import toolsql

class wlp_error(Exception): "Watchlist Points error"
class bad_oauth(wlp_error): "Invalid OAuth authorization"
class bad_wlowner(wlp_error): "wrbad_wlowner"
class bad_wltoken(wlp_error): "wrbad_wltoken"

def printu(s, data=None):
	print (s%data if data else s).encode('utf-8')

def html(string, data=[]):
	print((string%tuple(wikipedia.escape(s) if isinstance(s, (bytes,str,unicode)) else s for s in data)).encode('utf-8'))

def quote(s):
	return wikipedia.urllib.quote(s.encode('utf-8') if isinstance(s, unicode) else s, safe=";@$!*(),/:-_.")

def load_watchlist_loadfile(cursor, site, wrowner, wrtoken, max_api_requests=50, wrnamespace='0'):
	# max_api_requests increase to 50 by request of User:Doncram
	cursor.execute("""
	CREATE TEMPORARY TABLE u2815__p.watchlistraw (
	  wr_page      INT              NULL,
	  wr_touched   BINARY(14)       NULL,
	  wr_latest    INT              NULL,
	  wr_len       INT     UNSIGNED NULL,
	  wr_namespace TINYINT UNSIGNED NOT NULL,
	  wr_title     VARBINARY(255)   NOT NULL,
	  UNIQUE (wr_page),
	  PRIMARY KEY (wr_namespace, wr_title)
	) ENGINE = InnoDB""")
	# ?action=query&format=json&prop=info&list=&generator=watchlistraw&utf8=1&formatversion=2&inprop=subjectid%7Ctalkid
	data = {
		'action':       b'query',
		'format':       b'json',
		'formatversion':b'2',
		'utf8':         b'yes',
		'prop':         b'info',
		'inprop':       b'subjectid',
		'generator':    b'watchlistraw',
		'gwrlimit':     b'500',
		'gwrnamespace': wrnamespace,
	}
	# API request usually take 0.5 to 3 second
	logtime("Database connect, preparing to load watchlist data")
	def iter_watchedpages():
		if wikipedia.SysArgs.get('oaToken'):
			import requests_oauthlib, oauth_config
			consumer = oauth_config.consumers[0]
			auth1 = requests_oauthlib.OAuth1(consumer['key'], client_secret=consumer['secret'], resource_owner_key=wikipedia.SysArgs.get("oaKey"), resource_owner_secret=wikipedia.SysArgs.get("oaToken"))
			del oauth_config, consumer
			logtime("Setup OAuth")
		else:
			auth1 = None
			data.update({
				'gwrowner':     wrowner,
				'gwrtoken':     wrtoken,
			})
		for i in xrange(max_api_requests):
			req = requests.get("https://%s%s"%(site.hostname(), site.apipath()), params=data, auth=auth1)
			response = req.json()
			logtime("Watchlist loop %2d" % i)
				
			if 'error' in response:
				if response['error']['code'] == u'wrbad_wlowner':
					raise bad_wlowner(response['error']['info'])
				elif response['error']['code'] == u'wrbad_wltoken':
					raise bad_wltoken(response['error']['info'])
				elif response['error']['code'] == 'mwoauth-invalid-authorization':
					raise bad_oauth(response['error']['info'])
				else:
					print "Errror <xmp>%r</xmp>" % response
					raise wlp_error(response['error']['info'])
			#{"pageid","ns","title","contentmodel","pagelanguage","pagelanguagehtmlcode","pagelanguagedir","touched","lastrevid","length","talkid",
			for d in response['query']['pages']:
				touched = d.get('touched')
				if touched: touched = ''.join(c for c in touched if c.isdigit())
				yield (d.get('pageid'), touched, d.get('lastrevid'), d.get('length'), d['ns'], d['title'].split(':', d['ns']!=0)[-1],)
			
			if 'continue' in response:
				data.update(response['continue'])
				del response['continue']
			else:
				break
		else:
			logtime("Watchlist max_api_requests reached")
	cursor.loaddata("""
LOAD DATA LOCAL INFILE '%(tmpfile)s'
INTO TABLE u2815__p.watchlistraw
(wr_page, wr_touched, wr_latest, wr_len, wr_namespace, wr_title)
""", iter_watchedpages() )
	logtime("Watchlist loaded (%s rows)"%cursor.rowcount)

def main():
	site = wikipedia.getSite()
	SysArgs = wikipedia.SysArgs
	logtime("Initialize")
	def createLink(title, label=None, style=None):
		return u'<a href="https://%s/wiki/%s" title="%s"%s>%s</a>'%(
			site.hostname(),
			quote(title.replace(' ', '_')),
			wikipedia.escape(title.replace('_', ' ')),
			' style="%s"' % style if style else '',
			wikipedia.escape(label or title.replace('_', ' ')),
		)
	if not (SysArgs.get('username') and SysArgs.get('wltoken') or SysArgs.get('oaKey') and SysArgs.get('oaToken')):
		# TODO implement JS reload upon sign in
		printu(u'<p>Please sign in (top right) with your watchlist token and refresh the page.</p>')
		return
	elif not site.dbName().startswith('enwiki'):
		printu(u'<p>This tool is not support in your language, please use <a href="../view/Dablinks">Dablinks</a> instead (Last tab for watchlist)')
		return
	else:
		printu(u'<div id="contentSub">For %s <span class="mw-watchlist-toollinks">(%s | %s | %s)</span></div>'% (
			SysArgs.get('username', '<User>'),
			createLink('Special:Watchlist', 'View relevant changes'),
			createLink('Special:Watchlist/edit', 'View and edit watchlist'),
			createLink('Special:Watchlist/raw', 'Edit raw watchlist'),
		))

	conn = toolsql.getConn(host='tools.labsdb')
	cursor = conn.cursor(group_concat_max_len = 1024*1024)
	try:
		load_watchlist_loadfile(cursor, site, SysArgs.get('username',''), SysArgs.get('wltoken',''))
	except (bad_wlowner, bad_wltoken) as (errmsg,):
		printu(u'<strong class="error">%s</strong>'%wikipedia.escape(errmsg))
		return
	except toolsql.DatabaseError as (errno, strerror, extra):
		printu(u'<strong class="error">Database error: %s</strong>'%wikipedia.escape(strerror))
		return
	except Exception as e:
		printu(u'<strong class="error">Error: %s</strong>'%wikipedia.escape(repr(e)))
		raise	


	cursor.execute("SELECT COUNT(*) FROM u2815__p.watchlistraw")
	printu(u'<b>%d</b> articles on your watchlist.  ' % cursor.fetchall()[0])
	logtime("Count watchlisted articles")

	# replag
	cursor.execute("""
SELECT TIMESTAMPDIFF(MINUTE, CREATE_TIME, NOW())
FROM information_schema.tables
WHERE TABLE_SCHEMA=? AND TABLE_NAME=?
""", tuple('s51290__dpl_p.ch_fixed_links'.split('.')), max_time=5)
	update_touched = cursor.fetchall().pop()[0]
	printu(u'The last update was %s minutes ago.', (update_touched,))
	wikipedia.logtime('Table update time')
	
	cursor.execute("""
/* watchlist_points.articles-en */
SELECT
  adl.article_title AS "Article",
  GROUP_CONCAT(adl.dab_title SEPARATOR "|") AS "Dab link",
  COUNT(c_id) AS "Points",
  wr_touched < ? AS StrikedOut
FROM u2815__p.watchlistraw
JOIN s51290__dpl_p.all_dab_links_basic AS adl ON article_id=wr_page
LEFT JOIN s51290__dpl_p.contest_dabs   ON c_id=dab_id
LEFT JOIN s51290__dpl_p.ch_fixed_links AS cfl ON cfl.article_id=adl.article_id AND cfl.dab_id=adl.dab_id

WHERE wr_namespace=0 AND cfl.article_id IS NULL
GROUP BY adl.article_id
ORDER BY COUNT(c_id)=0, Article ASC
""", (update_touched,), max_time=120)
	
	print '<h2>Articles with links to disambiguation pages</h2>'
	print '<table class="wikitable sortable">'
	print '<tr>'
	for tup in "DAB page|Links|Points|Tools".split('|'):
		printu(u'<th>%s</th>'%tup)
	print '</tr>'
	for article_title, dab_titles, points, StrikedOut in cursor.fetchall():
		printu(u'''<tr>
<td>%s</td>
<td>%s</td>
<td>%s</td>
<td><a href="/~dispenser/cgi-bin/dab_solver.py?page=%s&amp;client=watchlist_points&amp;force=yes%s%s">FIX</a></td>
</tr>''' % (
			("<del>%s</del>" if StrikedOut else "%s") % createLink(article_title),
			', '.join(createLink(s) for s in dab_titles.split('|')),
			points,
			quote(article_title),
			'&amp;commonfixes=yes' if wikipedia.SysArgs.get('commonfixes', 'false')=='true' else '',
			'&amp;dbname=%s_p' % site.dbName() if site.dbName()!='enwiki' else '',
		))
		#print '</td><td>'.join(wikipedia.escape(str(i)) for i in tup)
		#print '</td><td>'.join(createLink(i) if isinstance(i, bytes) else wikipedia.escape(bytes(i)) for i in tup)
		#print '</td><td>'.join(createLink(i) if isinstance(i, bytes) else wikipedia.escape(bytes(i)) for i in tup)
		#print '</td></tr>'
	print '</table>'
	logtime("Articles w/ dablinks")
	import sys; sys.stdout.flush()
	
	cursor.execute("""
/* watchlist_points.dabpages-en */
SELECT
  adl.dab_title AS "Dab page",
  COUNT(*) AS "Links",
  COUNT(c_id) AS "Points"
FROM u2815__p.watchlistraw
JOIN s51290__dpl_p.all_dab_links AS adl ON dab_id=wr_page
LEFT JOIN s51290__dpl_p.contest_dabs   ON c_id=dab_id
LEFT JOIN s51290__dpl_p.ch_fixed_links AS cfl ON cfl.article_id=adl.article_id AND cfl.dab_id=adl.dab_id

WHERE wr_namespace=0 AND cfl.article_id IS NULL
GROUP BY adl.dab_id
ORDER BY COUNT(c_id)=0, "Dab page" DESC
""", (), max_time=120)
	print '<h2>Disambiguation pages</h2>'
	print '<table class="wikitable sortable">'
	print '<tr>'
	for tup in cursor.description:
		print '<th>%s</th>'%tup[0]
	print '</tr>'
	for dab_title, count, points in cursor.fetchall():
		printu(u'''<tr>
<td>%s</td>
<td><a href="//tools.wmflabs.org/dplbot/dab_fix_list.php?title=%s&amp;client=watchlist_points%s"%s>Fix list</a></td>
</tr>''' % (
			'</td><td>'.join(createLink(i) if isinstance(i, unicode) else wikipedia.escape(unicode(i)) for i in (dab_title, count, points)),
			quote(dab_title),
			'&amp;commonfixes=yes' if wikipedia.SysArgs.get('commonfixes', 'false')=='true' else '',
			' style="display:none;"' if site.dbName()!='enwiki' else '',
		))
		#print '</td><td>'.join(wikipedia.escape(str(i)) for i in tup)
		#print '</td><td>'.join(createLink(i) if isinstance(i, bytes) else wikipedia.escape(bytes(i)) for i in tup)
	print '</table>'
	logtime("Dab pages with points")
	import sys; sys.stdout.flush()

	if site.dbName().startswith('enwiki') and False:
		# Pages edited in the past 30 days
		cursor.execute("""
/* watchlist_points.recent */
SELECT DISTINCT
  adl.article_title AS "Article",
  GROUP_CONCAT(DISTINCT adl.dab_title SEPARATOR "|") AS "Dab link",
  COUNT(DISTINCT c_id) AS "Points",
  IF(tl_from IS NULL, "", "Yes") AS "{{dn}}"
FROM revision_userindex
JOIN s51290__dpl_p.all_dab_links AS adl ON article_id=rev_page
LEFT JOIN s51290__dpl_p.contest_dabs    ON c_id=dab_id
LEFT JOIN u2815__p.watchlistraw  ON wr_namespace=0   AND wr_title=article_title
LEFT JOIN templatelinks             ON tl_from=rev_page AND tl_namespace=10 AND tl_title="Disambiguation_needed"
LEFT JOIN s51290__dpl_p.ch_fixed_links  AS cfl ON cfl.article_id=adl.article_id AND cfl.dab_id=adl.dab_id

WHERE rev_user_text=? 
/* 4 hr lag - typical worst case for Dab Challenge */
AND rev_timestamp BETWEEN DATE_FORMAT(NOW()-INTERVAL ? DAY,  '%Y%m%d%H%i%S')
                      AND DATE_FORMAT(NOW()-INTERVAL 4 HOUR, '%Y%m%d%H%i%S')
AND wr_title IS NULL 
AND cfl.article_id IS NULL
GROUP BY rev_page
ORDER BY COUNT(c_id)=0, rev_timestamp DESC
LIMIT 20
""", (SysArgs.get('username', wikipedia.os.getenv('HTTP_X_FORWARDED_FOR', wikipedia.os.getenv('REMOTE_ADDR'))), 30), max_time=30)
		print '<h2>Recently edited</h2>'
		print '<table class="wikitable sortable">'
		print '<tr>'
		for tup in cursor.description:
			print '<th>%s</th>'%tup[0]
		print '</tr>'
		for page_title, dab_pages, points, tl_from in cursor.fetchall():
			#import time
			printu(u"""<tr>
<td>%s</td>
<td>%s</td>
<td>%d</td>
<td>%s</td>
<td><a href="/~dispenser/cgi-bin/dab_solver.py?page=%s&amp;client=watchlist_points&amp;force=yes%s">FIX</a></td>
</tr>""" % (
			createLink(page_title),
			#time.strftime("%d %B %Y", time.strptime(dab_date, "%Y%m%d%H%M%S")),
			', '.join(createLink(s) for s in dab_pages.split('|')),
			points,
			tl_from,
			quote(page_title),
			'&amp;commonfixes=yes' if wikipedia.SysArgs.get('commonfixes', 'false')=='true' else '',
		))
		print '</table>'
		logtime("Recently edited articles")

	if site.dbName().startswith('enwiki'):
		cursor.execute("""
SELECT 
  pb_title AS "WikiProject",
  COUNT(*) AS "Watched pages",
  100*(COUNT(*)-1)/(SELECT COUNT(*)
                    FROM u2815__p.projectbanner AS s 
					WHERE s.pb_title=projectbanner.pb_title) AS "Percentage"

FROM u2815__p.watchlistraw
JOIN u2815__p.projectbanner ON pb_page=wr_page
GROUP BY pb_title
HAVING Percentage > 0.005
ORDER BY 3 DESC
LIMIT 7
""", (), max_time=300)
		print '<h2>Suggested WikiProjects</h2>'
		print '<table class="wikitable sortable">'
		print '<tr>'
		for tup in cursor.description[:2]:
			print '<th>%s</th>'%tup[0]
		print '</tr>'
		for pb_title, count, percentage in cursor.fetchall():
			print '<tr>'
			html(u'<td><a href="/~dispenser/cgi-bin/topic_points.py?banner=%s">%s</a></td>', (quote(pb_title), pb_title.replace('_', ' '),))
			html(u'<td>%d</td>', (count,))
			print '<tr>'
		print '</table>'
		logtime("Dab pages with points")



if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=False)
		main()
	except toolsql.Error as (errno, strerror, extra):
		if errno in (1041, 1226, 2013): # Too many connection / Max connections / Lost connection
			print '<p class="errormsg">Database operational error (%d), retry in a few minutes.</p><blockquote>%s</blockquote>'%(errno, wikipedia.escape(strerror),)
			print '<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>'
		else:
			raise
	finally:
		wikipedia.endContent()
		wikipedia.stopme()

