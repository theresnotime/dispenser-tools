#!/usr/bin/env python 
# -*- coding: utf-8  -*-
"""
TODO 
 * give edit counts for IP editors
 * Print stats of checking page 

"""
from __future__ import division
import wikipedia, pagegenerators
import re, urllib
import toolsql
import cgitb; cgitb.enable(logdir='tracebacks')
import time; StartTime=time.time()

dashboard_wikis = (
#"dewiki",
#"enwiki",
#"eswiki",
#"frwiki",
#"itwiki",
#"jawiki",
#"nlwiki",
#"plwiki",
#"ptwiki",
#"ruwiki",
)

def printu(s, data=None):
	print (s%data if data else s).encode('utf-8')

def sig_format2(host, user, nickname=None):
	import parser, re
	if nickname and u'[[' in nickname:
		# TODO sanitize
		# re.sub(r'[^<>]|<(font|span|sup|sub|b|i|u|small|)( (color|face|family|size|style)=("[^<>"]*"|[\w#+-]+))*[ /]*>
		remove_chars = u'-\u2012\u2012\u2014\u2015\u2053\u00A0 \u2022,.:;'
		nickname = nickname.replace(u'&nbsp;', u'\u00A0').strip(remove_chars)
		return parser.parser(nickname.strip(remove_chars), allowComments=True, allowHtml=True, sanitize=True).strip(remove_chars)
	return u'<a href="%s/wiki/User:%s" style="direction:ltr; white-space:nowrap;">%s</a>' % (
		host,
		urllib.quote(user.encode('utf-8')),
		user,
	)

def colorValue(subset, total, revert = False):
    "Gradient function in gamma space -- Not linear space!"
    v = min(255 * subset // max(subset, total), 255)
    if (revert):
        v = 255 - v;
    blue = 00
    if (v < 128):
        # Red to Yellow
        red = 255
        green = 2 * v
        #blue = v // 4
    else:
        # Yellow to Green
        red = 2 * (255 - v)
        green = 255
        if v>192: blue = v - 192
        # Colorblind
        #blue = v // 4 + 64
    return "#%02X%02X%02X"  % (red, green, blue)

def sig_format(self, user_id, user_name, nickname):
	if user_id:
		if nickname is None:
		# Untouched preferences
			return "[[User:%(user_name)s|%(user_name)s]]"%locals()
		elif '[[' in nickname and len(re.sub(r'<.*?>|\[\[[^[\]\|]*\|?|\]\]', r'', nickname))<50:
			# fancysig
			# TODO sanitize
			# re.sub(r'[^<>]|<(font|span|sup|sub|b|i|u|small|)( (color|face|family|size|style)=("[^<>"]*"|[\w#+-]+))*[ /]*>
			nickname = nickname.strip(u'-‒‒—―⁓ ')
			return nickname
		elif nickname and not any(c in nickname for c in "{|}[#]</>\n\r\t\0"):
			# fancysig is off
			return "[[User:%(user_name)s|%(nickname)s]]"%locals()
		else:
			return "[[User:%(user_name)s|%(user_name)s]]"%locals()
	else: # IP users
		return "[[Special:Contributions/%(user_name)s|%(user_name)s]] ([[User talk:%(user_name)s|talk]])"%locals()

class UserActivity:
	def __init__(self):
		self.page = wikipedia.MyPage
		self.days = 365
	def main(self):
		site = wikipedia.getSite()
		action = 0
		for arg in wikipedia.handleArgs():
			if arg.startswith('-page:'):
				self.page = wikipedia.Page(site, arg[6:])
				site = self.page.site()
			elif arg.startswith('-inactivetime:'):
				pass
			elif arg.startswith('-view:edit'):
				action = 2
			elif arg.startswith('-days:'):
				try:	self.days = int(arg[6:])
				except:	pass
		
		dayoptions = [
			(   1, 'a day'),
			(   7, 'a week'),
			(  30, 'a month'),
			(  90, '3 months'),
			( 180, '6 months'),
			( 365, 'a year'),
			( 730, '2 years'),
			(1095, '3 years'),
			(1461, '4 years'),
			(1826, '5 years'),
			(   0, 'Disabled (rename only)'),
		]
		if not any(self.days==k for k,v in dayoptions):
			dayoptions.append((self.days, "%s days"%self.days))
		printu(u'''
<form action="../cgi-bin/useractivity.py" style="text-align:left;">
<fieldset><legend>Member activity check</legend>
<div style="float:right; clear:right; border:1px solid #999; border-radius: 0.5em; background-color:#eee; background-image: background-image: linear-gradient(to bottom, #ddd,#eee); color:#000; text-align:center; padding:0.5em; width:12em">Faster watcher stats<br/><a href="//phabricator.wikimedia.org/T59617"><b>Task T59617</b></a></div>
<div style="float:right; clear:right; border:1px solid #999; border-radius: 0.5em; background-color:#eee; background-image: background-image: linear-gradient(to bottom, #ddd,#eee); color:#000; text-align:center; padding:0.5em; width:12em">Faster email status<br/><a href="//phabricator.wikimedia.org/T70876"><b>Task T70876</b></a></div>
<label for="page">Member list page</label>:  <input type="text" name="page" id="page" size="50" value="%s" onchange="fixTitle(this)" accesskey="f" placeholder="http://de.wikipedia.org/wiki/Project:Member_list" /><br/>
''' % (wikipedia.escape(self.page.title(allowInterwiki=True)),))
		#print '<label for="days">Inactive Flag: </label><input type="text" name="days" id="days" size="3" placeholder="365" value="%s" /> days <small>(0 to disable)</small><br/>'%(self.days if self.days!=365 else '')

		print '<label for="days">Mark inactive after </label><select name="days" id="days">\n%s\n</select><br />' % ('\n'.join(
			'<option value="%s"%s>%s</option>' % (k, ' selected="selected"' if k==self.days else '', v) for k,v in dayoptions
		),)
		
		#print '<select name="view"><option value="">Display table</option><option value="edit">Prepare update</option></select><br/>'
		print '<button type="submit">Check list of users</button>'
		print '<button type="submit" name="view" value="edit">Prepare update</button>'

		print '</fieldset></form>'

		if not self.page.title():
			print """
<p>Edit counters are virtually the Hello World of tool developement, but what if you want check more than single users?  This tool will print information interesting to people who manage projects.</p>

<h3>Examples</h3>
<ul>
<li><a href="../cgi-bin/useractivity.py?page=User_talk:Jimbo_Wales">People on Jimbo's page</a></li>
<li>WikiProjects Member lists:<ul>
<li><a href="../cgi-bin/useractivity.py?page=Wikipedia:WikiProject_Oklahoma/Active_participants">WikiProject Oklahoma</a> (~25 users, 15 seconds)</li>
<li><a href="../cgi-bin/useractivity.py?page=Wikipedia:WikiProject_Professional_wrestling/Members_list">WikiProject Professional wrestling</a> (~300 users, 3 minutes)</li>
<li><a href="../cgi-bin/useractivity.py?page=Wikipedia:WikiProject_Trains/Members">WikiProject Trains</a> (~500 users, 5 minutes)</li>
</ul></li>
<li><a href="../cgi-bin/useractivity.py?page=Wikipedia:Disambiguation_pages_with_links/Disambiguator_Hall_of_Fame">Disambiguator Hall of Fame</a>, a bit of a "Where are they now?" (60 users, 1 minute)</li>
<li><a href="../cgi-bin/useractivity.py?page=Wikipedia:Wikipedia_Signpost/Subscribe">Wikipedia Signpost Mail list</a> (~800 users, 10 minutes)</li>
</ul>
"""
			return

		# XXX Hack to get local namespace
		try:
			self.page.get() # first call, handles errors!
		except wikipedia.NoPage as errmsg:
			wikipedia.output('NoPage error encountered <br/><code>%s</code>', (errmsg,))
			return
		except wikipedia.IsRedirectPage:
			target = wikipedia.Page(site, self.page._redirarg)
			print('<img src="https://upload.wikimedia.org/wikipedia/commons/b/b5/Redirectltr.png" alt="#REDIRECT " /><a href="?page=%s" class="redirectText">%s</a>' % (target.title(asUrl=True, allowInterwiki=True), wikipedia.escape(target.title().encode('utf-8')),))
			return
		
		self.site = site
		self.dbname = site.dbName()
		
		self.cursor = toolsql.getConn(site.dbName(), cluster='labsdb').cursor()
		self.cursor.execute(u"""
SELECT page_is_redirect, CONCAT(ns_name, ':', rd_title)
FROM page 
LEFT JOIN redirect ON rd_from=page_id 
LEFT JOIN u2815__p.namespacename ON ns_id=rd_namespace AND ns_is_favorite=1 AND dbname=(SELECT DATABASE())
WHERE page_namespace=? AND page_title=?""",
			(self.page.namespace(), self.page.titleWithoutNamespace(underscore=True),),
			max_time=10
		)
		exists = self.cursor.fetchall()
		if not exists:
			wikipedia.output("%s does not exist"%self.page.aslink())
			return
		elif 1 in exists[0]:
			print '<img src="https://upload.wikimedia.org/wikipedia/commons/b/b5/Redirectltr.png" alt="#REDIRECT " /><a href="?page=%s" class="redirectText">%s</a>'% (
				wikipedia.escape(exists[0][1]),
				wikipedia.escape(exists[0][1]),
			)
			return
		else:
			pass

		print '<p style="font-size:1.2em;"><a href="/~dispenser/cgi-bin/contribslist.py?namespaces=2&links=%s&dbname=%s">Recent edits from these users</a></p>' % (self.page.title(asUrl=True), self.page.site().dbName(),)
		
		# TODO requested by [[User:Elitre]]: "my colleagues and I rely on categories such as the ones such as the ones generated by babel boxes (we often need to contact people able to translate to a given language)."
		wikipedia.logtime("Got database connection")
		#self.cursor.execute("CREATE DATABASE IF NOT EXISTS u2815__p")
		#self.cursor.execute('SET @ThirtyDays = (SELECT DATE_FORMAT(NOW()-INTERVAL 30 DAY, "%Y%m%d"))')
		self.cursor.execute("""/* useractivity.build_table */
CREATE TEMPORARY TABLE u2815__p.userlist (
  pl_name   VARBINARY(255) NOT NULL,
  pl_user   INT NOT NULL,
  last_edit VARBINARY(14) NULL,
  watchers  BIGINT NULL,
  active_watchers BIGINT NULL,
  emailable INT NULL,
  PRIMARY KEY (`pl_title`)
) ENGINE=MyISAM AS 
SELECT DISTINCT
  pl_title,
  REPLACE(pl_title, "_", " ") AS pl_name,
  IFNULL((SELECT user_id FROM user WHERE user_name=REPLACE(pl_title, "_", " ")),0) AS pl_user,
  NULL AS last_edit,
  IFNULL(watchers, 0) AS watchers
FROM page AS list
JOIN pagelinks            ON list.page_id=pl_from
LEFT JOIN watchlist_count ON wl_namespace=2 AND wl_title=pl_title
WHERE list.page_namespace=? AND list.page_title=?
AND   pl_namespace IN (2,3) AND pl_title NOT LIKE "%/%"
""", (self.page.namespace(), self.page.titleWithoutNamespace(underscore=True),), max_time=60)
		usercount = self.cursor.rowcount
		wikipedia.logtime("User list done (%d)" % usercount)
		
		# Get last edited dates
		# Even if killed MySQL autocommits
		try:
			self.cursor.execute("""/* useractivity.rc_last_edit */
UPDATE u2815__p.userlist
SET last_edit=(SELECT MAX(rc_timestamp) FROM recentchanges_userindex WHERE rc_user_text=pl_name)
""", max_time=60)
			self.cursor.execute("""/* useractivity.rev_last_edit */
UPDATE u2815__p.userlist
SET last_edit=(SELECT MAX(rev_timestamp) FROM revision_userindex WHERE rev_user_text=pl_name)
WHERE last_edit IS NULL
""", max_time=30)
		except toolsql.QueryTimedOut as e:
			wikipedia.logtime("Query timed out for last edits (%d users)"%self.cursor.rowcount)
		else:
			wikipedia.logtime("Revision last edits (%d users)"%self.cursor.rowcount)
		
		if action == 0: # Only run for infotable
			# Email status 
			try:
				batch_size = 50
				self.cursor.execute("SELECT pl_name FROM u2815__p.userlist")
				count = 0
				for iBegin in xrange(0, usercount, batch_size):
					if action != 0: # skip expensive API calls for updatePage()
						continue
					count += 1
					data = {
						'action':'query',
						'format':'json',
						'list':  'users',
						'usprop':'emailable',
						'ususers':'|'.join((x for (x,) in self.cursor.fetchmany(batch_size))),
					}
					import json
					rsp_json=json.loads(site.getUrl(site.apipath(), data=data))
					query_users = rsp_json['query']['users']
					if 'incontinue' in rsp_json:
						raise "Try setting the batch_size %d lower" % batch_size
					if wikipedia.Debug:
						print '<xmp>',data,'\n',rsp_json,'</xmp>'
						print '<br/>'.join(repr(x) for x in query_users)
					#self.cursor.executemany(
					#	"UPDATE u2815__p.userlist SET emailable=? WHERE pl_name=?",
					#	((prop.get(u'emailable', 'no')=="", prop['name'],) for prop in query_users if 'missing' not in prop)
					#)
					params = ()
					for prop in query_users:
						if 'missing' not in prop:
							params += prop['name'],
							params += prop.get(u'emailable', 'no')=="",
					if params:
						self.cursor.execute("""
UPDATE u2815__p.userlist
SET emailable = CASE pl_name
%s
ELSE emailable
END 
""" % '\n'.join(("WHEN ? THEN ?",) * (len(params) // 2)), params, max_time=10)
				#self.cursor.nextset() # "fetch None", empty results
				wikipedia.logtime("API email info (%d)"%count)
			except KeyError as e:
				wikipedia.logtime('%r' % (e,))
		
		if action == 0 and StartTime - time.time() < 3 * 60: # Only run for info table & < 3min
			# Get watcher counts
			try:
				batch_size = 50
				self.cursor.execute("""
SELECT pl_name
FROM u2815__p.userlist
WHERE watchers IS NULL OR watchers >= 30
""", max_time=10)
				mylist = self.cursor.fetchall()
				chunks = [mylist[x:x+batch_size] for x in xrange(0, len(mylist), batch_size)]
				count = 0
				for chunk in chunks:
					if action != 0: # skip expensive API calls for updatePage()
						continue
					count += 1
					data = {
						'action':'query',
						'format':'json',
						'prop':'info',
						'inprop':'watchers|visitingwatchers',
						'titles':'|'.join(("User:%s"%x for (x,) in chunk)),
					}
					import json
					rsp_json=json.loads(site.getUrl(site.apipath(), data=data))
					if u'error' in rsp_json:
						wikipedia.logtime('API Error (%s): %r' % (rsp_json[u'error'][u'code'], rsp_json[u'error'][u'info'],))
						continue
					query_pages = rsp_json['query']['pages']
					if 'incontinue' in rsp_json:
						raise "Try setting the batch_size %d lower" % batch_size
					if wikipedia.Debug:
						print '<xmp>',data,'\n',rsp_json,'</xmp>'
						print '<br/>'.join(repr(x) for x in query_pages.itervalues())
					#self.cursor.executemany(
					#	"UPDATE u2815__p.userlist SET watchers=?,active_watchers=? WHERE pl_name=?",
					#	((prop.get(u'watchers', None), prop.get(u'visitingwatchers', None),  prop['title'][prop['title'].index(':')+1:].encode('utf-8'),) for prop in query_pages.itervalues())
					#)
					params = ()
					for prop in query_pages.itervalues():
						params += prop['title'][prop['title'].index(':')+1:],
						params += prop.get(u'watchers', None), 
					for prop in query_pages.itervalues():
						params += prop['title'][prop['title'].index(':')+1:],
						params += prop.get(u'visitingwatchers', None),
					for prop in query_pages.itervalues():
						params += prop['title'][prop['title'].index(':')+1:],
					self.cursor.execute("""
UPDATE u2815__p.userlist
SET watchers = (CASE pl_name
%s
ELSE watchers
END), active_watchers = (CASE pl_name
%s
ELSE active_watchers
END)
WHERE pl_name IN (%s)
""" % ('\n'.join(("WHEN ? THEN ?",) * len(query_pages)), '\n'.join(("WHEN ? THEN ?",) * len(query_pages)), ','.join(('?',) * len(query_pages)),),
					params, max_time=10)
				wikipedia.logtime("API watcher info (%d)"%count)
			except KeyError as e:
				wikipedia.logtime('%r %r' % (e, rsp_json if 'rsp_json' in locals() else '',))

		
		# TODO Report recent engagement, Days edited in RC / 10 days (weekends+) max at 100%
		# TODO include babel box category info https://www.mediawiki.org/wiki/Extension:Babel "User __-_"
		# TODO i18n Retired templates
		#
		self.cursor.execute("""
SELECT /* main_query */
  REPLACE(pl_title,"_"," ") AS user_name,
  pl_title AS user_title,
  rd_title AS user_rd,
  user_editcount,
  IFNULL(DATE_FORMAT(user_registration, "%Y-%m-%d"), "") AS user_reg_text,
  user_registration,
  ipb_expiry,
  ipb_reason,
  /* user_email_authenticated has been disabled on Labs
   * https://phabricator.wikimedia.org/T70876
   */
  emailable /*user_email_authenticated*/,
  mail.up_value AS disablemail,
  IFNULL(gndr.up_value, "") AS user_gender,
  sig.up_value AS fancysig,
  watchers,
  active_watchers,
  /*SUM(ts_wl_user_touched_cropped>=@ThirtyDays) AS active_watchers,*/
  TIMESTAMP(last_edit),
  (SELECT TIMESTAMPDIFF(DAY, last_edit, NOW())) AS days_since,
  (SELECT tl_title
    FROM templatelinks
    WHERE tl_namespace=10 AND tl_from=page_id AND tl_title IN (
		/* TODO i18n */
		"Retired", "Grounded",
			"Користувач_покинув_проект", "Неактивен_потребител", "Повлечен_корисник", "Պաշտոնաթող", "جعبه_کاربر/بازنشسته", "سبک_دوش", "متقاعد", "పూర్తి_విరమణ", "විශ්‍රාමික", "永遠離開", "위키백과탈퇴", "Deaktiviert", "Jo_aktiv", "Pasitraukęs", "Retired", "Retraité", "Usuário_inativo", "Usuario_retirado", "Utente_ritirato", "Utilizator_retras", "Vertrokken", "Visszavonult"
	)
  ) AS tl_title,
  (SELECT log_params 
   FROM logging_logindex 
   WHERE log_type="renameuser" AND log_namespace=2 AND log_title=pl_title
   /*AND (last_edit IS NULL OR log_timestamp >= last_edit)*/
   LIMIT 1
  ) AS renameuser,
  (SELECT GROUP_CONCAT(ug_group SEPARATOR ", ") FROM user_groups WHERE ug_user=user_id) AS user_group

FROM u2815__p.userlist
LEFT JOIN page     ON page_namespace=2 AND page_title=pl_title
LEFT JOIN redirect ON rd_from=page_id  AND rd_namespace=2
LEFT JOIN user     ON user_name = pl_name
/* for performance we do not use ipb_address */
LEFT JOIN ipblocks_ipindex ON ipb_address=pl_name AND ipb_user=user_id
LEFT JOIN user_properties AS gndr ON gndr.up_user=user_id AND gndr.up_property="gender"
LEFT JOIN user_properties AS mail ON mail.up_user=user_id AND mail.up_property="disablemail"
LEFT JOIN user_properties AS sig  ON  sig.up_user=user_id AND  sig.up_property="nickname"
/* LEFT JOIN watchlist ON  wl_namespace=2 AND wl_title=pl_title */
GROUP BY pl_title
ORDER BY pl_title
""", max_time=120)
		wikipedia.logtime("Queries done")
		if action == 0:
			self.infoTable()
		else:
			self.updatePage()
	
	def updatePage(self):
		text = self.page.get()
		# Pipe trick: [[User:Example|]] => [[User:Example|Example]]
		text = re.sub(r'\[\[([^:]+:([^[\]{|}\n]*?))\|\2\]\](?![^<]*</ref>)', r'[[\1|]]', text)
		old_text = text

		msg_commented = 0
		msg_removed = 0
		msg_renamed = 0
		msg_blocked = 0


		for user_name, user_title, user_rd, user_editcount, userreg, user_registration, ipb_expiry, ipb_reason, user_email_authenticated, disablemail, gender, fancysig, watchers, active_watchers, last_edit, days_since, user_notes, renameuser, user_groups in self.cursor.fetchall():
			from dabfix import wikilinkregex
			p = re.compile(ur'''
^((?:[#*;:|].*)?(?:\[\[|\{\{)(?:User|User[ _]talk)[:|][ ]*)(%s)([ ]*(?=[]{|}[]).*)
''' % wikilinkregex(user_name), re.M | re.I | re.U | re.X)
			n = 0

			# List update logic
			if   user_editcount < 32 and user_rd:
					user_rd = user_rd.replace('_', ' ')
					wikipedia.output(u'Renaming [[User:%s]] → [[User:%s]]'%(user_name, user_rd,))
					text, n = p.subn(r'\g<1>%s\g<3>'%user_rd, text)
					msg_renamed += n
			elif user_editcount == 1 and days_since > 180:
					wikipedia.output('Comment out [[User:%s]] single edit account (%d months inactive)'%(user_name, days_since//30))
					text, n = p.subn(r'<!--single edit account: \g<0>-->', text)
					msg_commented += n
			elif user_editcount == 0:
				if not last_edit:
					wikipedia.output(u'Removing [[User:%s]] - No edits, possible [[wp:vanish]]ed'%user_name)
					text, n = p.subn(r'', text)
					msg_removed += n
				else:
					n = -1
					wikipedia.output(u'Bad edit info for [[User:%s]]'%user_name)
			elif ipb_expiry == "infinity":
				wikipedia.output(u'[[User:%s]] is indefinitely blocked: \03{lightblue}%s\03{default}'%(user_name, ipb_reason,))
				text, n = p.subn(r'<!--blocked: \g<0>-->', text)
				msg_blocked += n
			elif ipb_expiry:
				wikipedia.output(u'[[User:%s]] is blocked until %s: %s'%(user_name, ipb_expiry, ipb_reason, ))
				n = -1
			elif days_since > self.days:
				#if min(user_editcount/day_begun, 20) >= days_since * 1.5:
				#if days_since/user_editcount >=  user_editcount/day_begun * 0.20:
					wikipedia.output('Comment out [[User:%s]] (%d edits, %d months inactive)' % (user_name, user_editcount or -1, days_since and days_since//30, ))
					text, n = p.subn(last_edit.strftime(r"<!-- Inactive since %b %Y: \g<0>-->"), text)
					msg_commented += n
			else:
				n = -1
				pass
			if n == 0:
				wikipedia.output(u"\03{lightred}NOT successful\03{default}")

		wikipedia.showDiff(old_text, text)
		wikipedia.setAction(self.summary(parts={
			'remove':msg_removed,
			'renaming':msg_renamed,
			'comment out':msg_commented,
			'blocked': msg_blocked
		}))
		self.page.put(text)
	
	def summary(self, parts):
		msg = []
		advert = " with [[tools:~dispenser/cgi-bin/useractivity.py|Useractivity]]"

		wordform = ('user', 'users')
		for key, value in parts.iteritems():
			if key and value:
				msg.append("%s %s" % (key, wordform[0],) if value==1 else "%s %d %s" % (key, value, wordform[1],))

		if len(msg) == 0:
			return ''
		elif len(msg) < 3:
			return ' and '.join(msg).capitalize() + advert
		else:
			return (', '.join(msg[:-1]) + ', and '+msg[-1]).capitalize() + advert

	def infoTable(self):
		print '<table class="wikitable lightrow sortable" style="margin:auto; text-align:center;">'
		print '<tr><th>', '</th><th>'.join(
			#'User,Timeline,Registered,Notes,Active,Stalkers,Gender,Email,Last&nbsp;edit'.split(',')
			'User,Edits,Registered,Notes,Stalkers,Active,Gender,Email,Last&nbsp;edit'.split(',')
		), '</th></tr>'
		dbname = self.dbname
		hostname = self.site.hostname()
		host = 'https://%s' % (hostname, )
		editcount_template = '<td class="timeline"%(css)s><img src="/~wiki_researcher/dashboard/%(dbname)s/bar.php?width=500&amp;user=%(user_enc)s&amp;offset=%(user_registration)s" alt="%(user_editcount)s"/></td>' if dbname in dashboard_wikis else '<td class="editcount"%(css)s>%(user_editcount)s</td>'
		count = 0
		#print '<xmp>', self.cursor.fetchall(), '</xmp>'
		for user_name, user_title, user_rd, user_editcount, userreg, user_registration, ipb_expiry, ipb_reason, user_email_authenticated, disablemail, gender, fancysig, watchers, active_watchers, last_edit, days_since, user_notes, renameuser, user_groups in self.cursor.fetchall():
			css = ' style="background:black; color:silver;"' if days_since and self.days and user_editcount and days_since > self.days and days_since/user_editcount >= 7 else ''
			count += 1
			user_enc = urllib.quote(user_name.replace(' ', '_'))
			if ipb_expiry:
				block_end = 'Indefinite block' if ipb_expiry == 'infinity' else 'Blocked until %s-%s-%s'%(ipb_expiry[0:4], ipb_expiry[4:6], ipb_expiry[6:8],)
				notes = '<a class="ipb" href="%s/w/index.php?title=Special:Log&amp;page=User:%s&amp;type=block">%s</a><div class="overflow">%s</div>' % (
					host,
					user_enc,
					block_end,
					wikipedia.escape(ipb_reason),
				)
			elif user_rd and renameuser:
				notes = '<a href="%s/w/index.php?title=Special:Log/renameuser&amp;page=User:%s">User renamed</a><div class="overflow">%s</div>' % (host, user_enc, renameuser,)
			elif user_notes:
				notes = '<span style="color:#39f; font-weight:bold; font-size:1.4em;">%s</span>'%(user_notes,)
			elif user_groups:
				notes = '<a href="%(host)s/w/index.php?title=Special:Log&amp;type=rights&amp;page=%(user_enc)s">%(user_groups)s</a>'%locals()
			else:
				notes = ''

			if last_edit:
				last_active = '%s<span class="inactive-flag" style="background-color:%s"><!-- --></span>' % (last_edit.strftime("%Y-%m-%d"), colorValue(days_since, self.days or 1, revert=True), )
			else:
				last_active = ''

			#if user_email_authenticated:
			#	mailable = '<td style="background:#ffffbb">Disabled</td>' if disablemail else '<td style="background:#90ff90">Yes</td>'
			#else:
			#	mailable = '<td style="background:#ff9090">No</td>'

			mailable = '<td style="background:#ffffbb;color:#000">Disabled</td>' if disablemail else '<td>?</td>' if user_email_authenticated==None else '<td style="background:#90ff90;color:#000">Yes</td>' if user_email_authenticated==1 else '<td style="background:#ff9090;color:#000">No</td>'

			if watchers < 10: watchers = ''
			if active_watchers< 10: active_watchers = ''
			if user_editcount == None: user_editcount = ''
			
			user_sig = sig_format2(host, user_name, fancysig)
			i = re.sub(ur'<.*?>|\W+|_', '', user_sig, flags=re.U).lower().find(re.sub(ur'\W+|_', '', user_name, flags=re.U).lower())
			# Didn't full parse it
			if '&lt;' in user_sig or '&#60;' in user_sig or '}}' in user_sig or ']]' in user_sig or len(re.sub(r'<.*?>', r'', user_sig))>80: # my parser barfed 
				user_sig = '<a href="%(host)s/wiki/User:%(user_enc)s" style="color:green;">%(user_name)s</a>' % locals()
			# Should show their name somewhere
			elif re.sub(ur'<.*?>|\W+|_', '', user_sig, flags=re.U).lower().find(re.sub(ur'\W+|_', '', user_name, flags=re.U).lower()) == -1:
				user_sig = '%(user_sig)s<br/><a href="%(host)s/wiki/User:%(user_enc)s">User:%(user_name)s</a>' % locals()
			else:
				pass
				
# Group checkboxes don't work
#<td class="test"><input type="checkbox" name="removeuser[]" value="%(user_enc)s" checked="checked" /></td>
			printu('''<tr>
<td class="userentry">%(user_sig)s
<div class="userlinks hlist"><ul>
<li><a href="%(host)s/wiki/User_talk:%(user_enc)s">Talk</a>
<li><a href="%(host)s/wiki/Special:Contributions/%(user_enc)s">Contribs</a></li>
<li><a href="//meta.wikimedia.org/wiki/Special:CentralAuth/%(user_enc)s">CA</a></li>
<li><a href="//tools.wmflabs.org/xtools-ec/?user=%(user_enc)s&amp;project=%(hostname)s">Edit count</a></li>
</ul></div></td>'''+editcount_template+'''<td class="firstedit">%(userreg)s</td></li>
<td class="notes">%(notes)s</td>
<td>%(watchers)s</td>
<td>%(active_watchers)s</td>
<td class="gender %(gender)s">%(gender)s</td>
%(mailable)s
<td class="lastedit">%(last_active)s</td>
</tr>
''', locals())
		print '</table>'
		wikipedia.logtime("Wrote out table")
		print "Displaying %d users" % count
		print '<pre>%s</pre>' % wikipedia.timereport()

if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=False, 
			head=r"""<style type="text/css">
td.userentry {
	text-align:left;
}
div.userlinks {
	font-size:88%;
	text-transform:lowercase;
}
td.timeline {
	padding-top:0;
	padding-bottom:0;
}
td.notes {
	width: 20em;
}
tr td.notes div.overflow {
	background-color:#fff;
	color:#000;
	display:inline-block;
	overflow:hidden;
	text-overflow:ellipsis;
	white-space:nowrap;
	width:20em;
}
tr:hover td.notes div.overflow {
	overflow:visible;
	white-space:pre-wrap;
	overflow-wrap:break-word;
	word-wrap:break-word;
}
td.notes a.ipb {
	color:red;
	font-weight:bold;
}
td span.inactive-flag {
	border-radius:.5em;
	-moz-border-radius:.5em;
	-webkit-border-radius:.5em;
	display:inline-block;
	height:1em;
	margin-left:.5em;
	width:1em;
}
.gender.male {
	font-weight: bold;
	color: #1790ff;
}
.gender.female {
	font-weight: bold;
	color: #e740e7;
}
/* WikEd extra styles */
#wikEdInputWrapper {
 background:#eee;
 padding:2px 0.5em 0;
}
#wikEdDiffWrapper {
 display:none;
}
</style><script type="text/javascript">//<![CDATA[
// load WikEd
wikEd = {
	useWikEd: null,
	config: {
		/* disable jumping around */
		doCloneWarnings: false,
		focusEdit:      false,
		scrollToEdit:   false,
		//wikEdNoRearrange: true,

		/* disable AJAX functions */
		autoUpdate:		false,
		useAjaxPreview:	false,
	
		/* enable enhanced diff */
		loadDiff:		true,

		/* enable InstaView */
		loadInstaView:	true,
		LinkifyArticlePath: "//en.wikipedia.org/wiki/$1"
	}
}
if (navigator.appName != 'Microsoft Internet Explorer') {
	importScriptURI('//en.wikipedia.org/w/index.php?title=User:Cacycle/wikEd.js&action=raw&ctype=text/javascript');
	function FixInstaView(){
		if(typeof(InstaView)=="undefined" || !InstaView.conf)return;
		InstaView.conf.paths = {
			articles: wgServer+'/wiki/',
			math: wgServer+'/math/',
			images: '',
			images_fallback: '//upload.wikimedia.org/wikipedia/commons/',
			magnify_icon: wgServer+'/skins-1.5/common/images/magnify-clip.png'
		}
		clearInterval(fiv_timer)
	}
	var fiv_timer = setInterval("FixInstaView()", 1000)
}

//]]></script>""")
		ua = UserActivity()
		ua.main()
	finally:
		wikipedia.endContent()
		wikipedia.stopme()
