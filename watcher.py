#!/usr/bin/env python
# -*- coding: utf-8  -*-
import wikipedia, pagegenerators
import toolsql

def trusted_user(site, wrowner, wrtoken):
	if not wrowner or not wrtoken:
		return False
	wikipedia.logtime('User watchlist authentication')
	# Let users
	conn = toolsql.getConn(site.dbName())
	cursor = conn.cursor()
	cursor.execute('''
SELECT 1
FROM user
WHERE user_name=? AND user_editcount >= ?
''', (wrowner, 500, ), max_time=10)
	has_enough_edits = cursor.fetchall()
	try:
		# Verify wrowner is on whitelist (~40 ms delay)
		conn = toolsql.getConn('metawiki_p')
		cursor = conn.cursor()
		cursor.execute('''
SELECT 1
FROM page
JOIN pagelinks ON pl_from=page_id
WHERE page_namespace=? AND page_title=?
AND pl_namespace IN (2,3) AND pl_title=REPLACE(?, " ", "_")
''', (0, 'Toolserver/watcher', wrowner,), max_time=10)
		whitelisted = cursor.fetchall() 
	except Exception, e:
		wikipedia.logtime(repr(e))
		whitelisted = False
	if not (whitelisted or has_enough_edits):
		wikipedia.logtime('User is not on [[m:Toolserver/watchlist]] whitelist')
		return False
	wikipedia.logtime('User is whitelisted')
	# Verify wrowner + wrtoken with Wikimedia (~300 ms delay)
	data = {
		'action':       b'query',
		'list':         b'watchlistraw',
		'format':       b'xml',
		'wrlimit':      b'1',
		'wrowner':      wrowner,
		'wrtoken':      wrtoken,
	}
	mw_xml=site.getUrl(site.apipath(), data=data)
	if '<error ' in mw_xml:
		wikipedia.logtime('User watchlist token wrong')
		return False
	wikipedia.logtime('User watchlist token authenticated')
	return True

def main():
	genFactory = pagegenerators.GeneratorFactory()
	# Up the limit for genFactory
	genFactory.limit = 500
	minwatchers = 30
	active_days = 30 # days
	for arg in wikipedia.handleArgs():
		genFactory.handleArg(arg)
	generator = genFactory.getCombinedGenerator() 
	
	if not generator:
		print('<img src="//bits.wikimedia.org/skins-1.5/common/images/redirectltr.png" alt="#REDIRECT " /><span class="redirectText"><a href="/~dispenser/view/Watcher">tools:~dispenser/view/Watcher</a></span>')
		return

	generator = pagegenerators.DuplicateFilterPageGenerator(generator)
	
#	try:
#		if trusted_user(wikipedia.getSite(), wikipedia.SysArgs.get('username'), wikipedia.SysArgs.get('wltoken')):
#			minwatchers = 0
#	except Exception, e:
#		wikipedia.logtime('trusted_user() error: %r'%(e,))

	def makelink(page, linktype, text=None):
		site = page.site()
		attr = '' if linktype==0 else ' class="mw-redirect' if linktype==1 else ' class="new"'
		return u'<a%s href="//%s%s" title="%s">%s</a>' % (
			attr,
			site.hostname(),
			(site.get_address if linktype==1 else site.nice_get_address)(page.urlname()),
			wikipedia.escape(page.title()),
			wikipedia.escape(text or page.title()),
		)
	
	print '<table class="wikitable sortable" style="margin: 1em auto; width:80%;">'
	print '<tr><th>Page</th><th>Watchers</th></tr>'
	for page in generator:
		site=page.site()
		cursor = toolsql.getConn(site.dbName()).cursor()
		db_title = page.titleWithoutNamespace(underscore=True)
		try:
			"""/* watcher LIMIT:3 NM */
SELECT
  (SELECT page_is_redirect FROM page WHERE page_namespace=? AND page_title=?) AS page_redirect,
  (SELECT page_is_redirect FROM page WHERE page_namespace=? AND page_title=?) AS talk_redirect,
  COUNT(*) AS watchers,
  IFNULL(SUM(ts_wl_user_touched_cropped>NOW()-INTERVAL ? DAY), 0) AS active
FROM watchlist
WHERE wl_namespace=? AND wl_title=?;
"""#(page.namespace() | 1 - 1, db_title, page.namespace() | 1, db_title, active_days, page.namespace(), db_title,)
			cursor.execute("""
SELECT
  (SELECT page_is_redirect FROM page WHERE page_namespace=? AND page_title=?) AS page_redirect,
  (SELECT page_is_redirect FROM page WHERE page_namespace=? AND page_title=?) AS talk_redirect,
  SUM(watchers),
  -1
FROM watchlist_count
WHERE wl_namespace=? AND wl_title=?;
""", (page.namespace() | 1 - 1, db_title, page.namespace() | 1, db_title, page.namespace(), db_title,), max_time=10)
		except toolsql.DatabaseError as (errno, strerror, extra):
			# Query timed out, use a degraded query that avoids cold tables like user
			if errno in (1317, 2006, 2013):
				cursor.execute(
					"SELECT 0, 0, COUNT(*), -1 FROM watchlist WHERE wl_namespace=? AND wl_title=?",
					(page.namespace(), db_title),
					max_time=30
				)
			else:
				raise
		(page_redirect, talk_redirect, watchers, active) = cursor.fetchone()
		exists = page_redirect!=None or talk_redirect!=None
		title = page.titleWithoutNamespace(underscore=True)

		if page.isTalkPage():
			talk = page
			page = wikipedia.Page(site, page.titleWithoutNamespace(), defaultNamespace=page.namespace()-1)
		else:
			talk = wikipedia.Page(site, page.titleWithoutNamespace(), defaultNamespace=page.namespace()+1)
		print ('<tr><td>%s (%s)</td><td>%s</td></tr>' % (
			makelink(page, page_redirect), 
			makelink(talk, talk_redirect, 'talk'), 
			#"" if exists and watchers < minwatchers else watchers, 
			"" if watchers < minwatchers else watchers, 
			#"" if active   < minwatchers else active, 
		)).encode('utf-8')
	print '</table>'

	if minwatchers:
		print '<p style="text-align:center;">Pages with fewer than %d watchers are hidden.</p>' % (minwatchers, )

if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=True, head='<style type="text/css">.mw-redirect{font-style:italic;}</style>')
		main()
	finally:
		wikipedia.endContent()
		wikipedia.stopme()
