#!/usr/bin/env python
# -*- coding: utf-8  -*-
import re, time
import wikipedia
import toolsql

import cgitb; cgitb.enable(logdir='tracebacks')


wikilink_r = re.compile(ur"\[\[([^{|}[\]<\n>]+)\|([^]]+)\]\]('??\w*)", flags=re.U)
autocomment_R = re.compile(ur'/\*\s*(.+?)\s*\*/', flags=re.U)
expandwlink_R = re.compile(ur'\[\[([^{|}[\]<\n>]+)\]\]', flags=re.U)
Entry_R = re.compile(ur'^\* <tt>(?P<tool>\w+).*?(?P<difflink><a href="(?:https?|)//(?P<domain>[a-z.\-]+)/[^<\n>]*?title=(?P<urlname>[^<>&]*?)&diff=next&oldid=(?P<revid>\d+|None)[^<\n>]*?>.*?&offset=(?P<starttime>\d{14}).*?</a>)\) \[\[(?P<title>[^<\n>[\]]*?)\]\] (<small>\(tags: (?P<tags>.*)\)</small>|)$', flags=re.M | re.U)
all_namespaces={
	'Special:':-1,
	'Talk':1,
	'User':2,
	'User_talk':3,
	'Wikipedia':4,
	'Wikipedia_talk':5,
	'File':6,
	'File_talk':7,
	'Template':10,
	'Template_talk':11,
	'Help':12,
	'Help_talk':13,
	'WP':4,
	'WT':4,
}
linkCache = {}
checklinks = 0 # 0-no check, 1-all, 2-only propulated
wikisummary_count = 0
wikisummary_time = 0
def wikisummary(domain, cursor, s, default=u'Main_Page'):
	# FIXME render [[:file:a|b|c]] as "c"
	firstCapitalize = True
	s = autocomment_R.sub(ur'<span class="autocomment">[[#\g<1>|→]] \g<1>: </span>', s, 1)
	s = expandwlink_R.sub(ur'[[\1|\1]]', s)
	def wikilinker(m):
		title = m.group(1).strip()
		if u'#' in title:
			title=title[:title.index('#')] or default
		title = title.replace(u' ', u'_').replace(u'&amp;', u'&').replace(u'&quot;', u'"').lstrip(u':')
		if firstCapitalize:
			title = title[0:1].upper() + title[1:]
		full_title = title
		ns = all_namespaces.get(title[:title.find(':')], 0)
		if ns:
			title=title[title.find(':')+1:]
		
		linktype=""
		if not title:
			pass
		elif ns==-1:
			pass
		elif ':' in title:
			linktype="extiw"
		else:
			if (ns, title) in linkCache:
				linktype = linkCache[ns, title]
			elif checklinks == 0 or checklinks == 2 and ns!=0:
				pass
			else:
				startTime = time.time()
				cursor.execute("SELECT page_is_redirect FROM page WHERE page_namespace=? AND page_title=?", (ns, title,), max_time=5)
				result = cursor.fetchall()# OurSQL bug: 718860
				if not result: linktype="new"
				elif result[0][0]: linktype="mw-redirect"
				else: pass
				linkCache[ns, title] = linktype
				global wikisummary_count; wikisummary_count += 1
				global wikisummary_time; wikisummary_time += time.time() - startTime
				#wikipedia.logtime("Looked up [[%s:%s]] (type:%s)"% (ns, title, linktype))
		return u'<a href="https://%s/wiki/%s" title="%s"%s>%s</a>'%(
			domain, 
			wikipedia.urllib.quote((('' if m.group(1)[0]!='#' else default) +m.group(1).replace(' ', '_')).encode('utf-8'), safe=";@$!*(),/:-_.").decode('utf-8'),
			wikipedia.escape(full_title.replace('_', ' ')),
			' class="%s"'%wikipedia.escape(linktype) if linktype else '',
			m.group(2),
		)
	s = wikilink_r.sub(wikilinker, s)
	return s

def main():
	site = wikipedia.getSite()
	day  = 0
	days = 1
	show_tags = []
	username = wikipedia.SysArgs.get('username', wikipedia.os.getenv("HTTP_X_FORWARDED_FOR"))
	for arg in wikipedia.handleArgs():
		if arg.startswith('-offset:'):
			try: day = int(arg[8:])
			except: pass
		elif arg.startswith('-days:'):
			try: days = int(arg[6:])
			except: pass
			global checklinks; checklinks = 0
		elif arg.startswith('-tags:'):
			show_tags = arg[6:].split('|')
		elif arg.startswith('-quick'):
			global checklinks; checklinks = 1 if arg[7:] == '0' else 0

	wikipedia.logtime("Initialized")
	namespaces = [
		('', 'all'),
		(0, 'article'),
		(1, 'talk'),
	]
#	with toolsql.getConn('u2815__p', host='tools.labsdb') as curs:
#		curs.execute('SELECT ns_id, ns_name, ns_is_favorite=1  FROM u2815__p.namespacename WHERE dbname=(SELECT DATABASE()) ORDER BY ns_id', max_time=10)
#		namespaces = [('', 'all')]
#		for ns_id, ns_name, ns_is_favorite in cursor.fetchall():
#			all_namespaces[ns_name.replace(' ', '_')] = ns_id
#			if ns_id >= 0 and ns_is_favorite:
#				namespaces.append((ns_id, ns_name))
#		wikipedia.logtime("Got namespaces")
	cursor = toolsql.getConn('u2815__p', host='tools.labsdb', raise_on_warnings=False).cursor()
	curs = toolsql.getConn(site.dbName()).cursor()
	wikipedia.logtime("Got database connection")
	replag = curs.replag()
	wikipedia.logtime("Replag is %r" % replag)

	defaultargs = {
		'dbname':      '',
		'from':        '',
		'days':       '1',
		'offset':     '0',
		'limit':    '5000',#'250',
		'hidebots':   '0',
		'hideanons':  '0',
		'hideliu':    '0',
		'hideminor':  '0',
		'hidemyself': '0',
		'namespace':   '',
		'invert':     '0',
		'quick':	  '1',
	}
	urlargs = defaultargs.copy()
	urlargs.update(dict(wikipedia.urllib.unquote(item).partition(b'=')[::2] for item in wikipedia.os.getenv("QUERY_STRING", b'').split(b'&')))
	def makelink(text, key, value, attr="", html=None):
		d = urlargs.copy()
		d.update({key: value}) # add function args
		return u'<a href="?%s"%s>%s%s%s</a>'%(
			'&amp;'.join('%s=%s'%(wikipedia.urllib.quote(k.encode('utf-8')), wikipedia.urllib.quote(v.encode('utf-8'))) for k,v in d.iteritems() if v and defaultargs.get(k, None)!=v),
			attr,
			'<strong>'  if urlargs.get(key, None)==value else '',
			html or wikipedia.escape(text),
			'</strong>' if urlargs.get(key, None)==value else '',
		)
	

	cursor.execute("""
CREATE TEMPORARY TABLE u2815__p.recentputs (
rp_rev_id    INT(8) UNSIGNED NOT NULL DEFAULT '0' PRIMARY KEY,
rp_tool      VARBINARY(32)   NOT NULL,
rp_timestamp VARBINARY(14)   NOT NULL,
rp_title     VARBINARY(255)  NOT NULL,
rp_domain    VARBINARY(32)   NOT NULL,
rp_tags      VARBINARY(255)
) ENGINE = MyISAM;
""", max_time=1)
	wikipedia.logtime("Table created")
	# We only store upto 91 days
	max_days_ahead = 90

	def iter_puts(start, stop):
		for i in range(start, stop):
			with open('./text/Put_pages|%d.html'%i if i>0 else './text/Put_pages.html') as f:
				tool = urlargs.get('tool')
				for match in reversed(tuple(Entry_R.finditer(f.read().replace(')</small>', ', )</small>').replace('<small>(tags: ', '<small>(tags: , ')))):
					if tool and tool != match.group('tool'):
						continue
					try:
						yield tuple(s.decode('utf-8') if isinstance(s, bytes) else s for s in match.group('revid', 'tool', 'starttime', 'title', 'domain', 'tags'))
					except UnicodeDecodeError as e:
						wikipedia.logtime('%s: %s (%r) in %s' % (type(e).__name__, e.reason, e.object, f.name))
			wikipedia.logtime("Parsed ./text/Put_page|%d.html"%(i,))
	# INSERT is 15x slower then LOAD DATA
	cursor.loaddata("""
LOAD DATA LOCAL INFILE '%(tmpfile)s'
IGNORE
INTO TABLE u2815__p.recentputs
(rp_rev_id, rp_tool, rp_timestamp, rp_title, rp_domain, rp_tags) 
""", iter_puts( day, min(day+days+1, max_days_ahead) ))
	wikipedia.logtime("Table loaded - %d rows"%cursor.rowcount)
	
			

	if checklinks:
		cursor.execute("""
SELECT DISTINCT page_namespace, page_title, page_is_redirect
FROM u2815__p.recentputs
JOIN revision ON rev_id = rp_rev_id 
JOIN page     ON (
	page_id = rev_page
 OR page_namespace IN (2,3) AND page_title=REPLACE(rev_user_text, " ", "_")
 )
""", max_time=20)
		for ns, title, result in cursor.fetchall():
			linkCache[ns, title] = "mw-redirect" if result == 1 else ""
		wikipedia.logtime("Populated linkCache dictionary (%s)"%len(linkCache))


	print (u'''<fieldset class="rcoptions">
<legend>Recent changes options</legend>
Show last %s changes in last %s days<br/>
%s<br/>
Show new changes starting from %s
; Show changes before %s days ago
<hr/>
<form action="%s">
<label>Tool <select name="tool">%s</select></label>
<label>Namespace <select name="namespace">%s</select></label>
<label for="nsinvert"><input name="invert" type="checkbox" value="1" id="nsinvert" %s/>&#160;Invert selection</label> <input type="submit" value="Go" />
%s
</form>
</fieldset>''' % (
		u' | '.join(makelink(i, 'limit', i) for i in ('50','100','250','500', '1000', '5000')),
		u' | '.join(makelink(i, 'days',  i) for i in ('1','3','7','14','30')),
		u' | '.join((makelink("Hide ", key, '1') if urlargs.get(key, '0')=='0' else makelink("Show ", key, '0'))+label for (key,label) in (
			('hideminor',  'minor edits'),
			('hidebots',   'bots'),
			('hideanons',  'anonymous users'),
			('hideliu',    'logged-in users'),
			('hidemyself', 'my edits'),
			('quick',      'colored links'),
		)),
		makelink(time.strftime('%H:%M %d %B %Y'), 'from', time.strftime('%Y%m%d%H%M%S')),
		u' | '.join(makelink({
			0: 'Today',
			1: 'Yesterday',
		}.get(i, '%d'%i) , 'offset', str(i)) for i in range(6)),
		wikipedia.escape(wikipedia.SysArgs.get('SCRIPT_NAME','?')),
		u'\n'.join('<option%s>%s</option>'%(' selected="selected"' if urlargs.get('tool')==tool else '', tool) for tool in 
			" altedit dab_solver dabfix mergeChanges reflinks useractivity webreflinks".split(' ')
		),
		u'\n'.join('<option value="%s"%s>%s</option>'%(
			ns_id,
			u' selected="selected"' if urlargs.get('namespace')==bytes(ns_id) else '',
			ns_name or '(Main)',
		) for ns_id, ns_name in namespaces),
		u'checked="checked" ' if urlargs.get('invert')=='1' else '',
		u''.join(('<input type="hidden" name="%s" value="%s" />'%(wikipedia.escape(bytes(k)), wikipedia.escape(bytes(v))) for k,v in urlargs.iteritems() if v and k not in ('namespace', 'tool', 'invert') and k in defaultargs and defaultargs.get(k, None)!=v)),
	)).encode('utf-8')
	if replag==None:
		print('<div class="mw-lag-warn-high">%s</div>'%("Replication lag could not be determined",))
	elif replag > 60*5:
		# See [[MediaWiki:lag-warn-normal]] and [[MediaWiki:lag-warn-high]]
		replag_m = replag // 60
		print('<div class="mw-lag-warn-high">%s</div>'%("Due to high database server lag, changes newer than %(replag_m)d minutes may not be shown in this list."%locals(),))
	else:
		pass # Replag OK
	print '''
<a href="javascript:void(appendCSS('.comment{display:none;}'));">Hide edit summaries</a> |
<a href="javascript:void(appendCSS('table{white-space:nowrap;}'));">Nowrap</a> | 
Jump to <a href="#Tag_cloud">Tag cloud</a>, <a href="#Statistics">Stats</a> |
<a href="https://en.wikipedia.org/wiki/Special:RecentChanges?tagfilter=OAuth+CID:+410">OAuth edits</a>
'''
	
	where_conditions = []
	where_data       = []
	def addWhere(condition, params=()):
		where_conditions.append(condition)
		for param in params:
			where_data.append(param)
	
	addWhere("rp_timestamp >= NOW() - INTERVAL ? DAY - INTERVAL ? DAY", (day, days))
	if urlargs.get('hideminor')!='0':	addWhere("rc_minor!= 1")
	if urlargs.get('hidebots')!='0':	addWhere("rc_bot  != 1")
	if urlargs.get('hideliu')!='0': 	addWhere("rc_user  = 0")
	if urlargs.get('hideanons')!='0':	addWhere("rc_user != 0")
	if urlargs.get('hidemyself')!='0':	addWhere("rc_user_text != ?", (username,))
	if urlargs.get('namespace'):		addWhere("rc_namespace != ?" if urlargs.get('invert')=='1' else "rc_namespace = ?", (urlargs['namespace'],))
	if urlargs.get('from'):     		addWhere("rc_timestamp >= ?", (urlargs['from'],))
	if urlargs.get('tool'):				addWhere("rp_tool = ?", (urlargs['tool'],))
	if urlargs.get('user'):             addWhere("rc_user_text = ?", (urlargs['user'].replace(u'_', ' '),))
	for tag in show_tags:
		if not tag:
			pass
		elif tag.startswith('-'):
			addWhere("rp_tags NOT LIKE ?", ("%% %s,%%"%tag[1:],))
		else:
			addWhere("rp_tags LIKE ?", ("%% %s,%%"%tag,))
	# Ignore Wikidata
	addWhere("(rc_type <= 4 OR rc_type IS NULL)")

	
	cursor.execute("SELECT rp_domain, COUNT(*) FROM recentputs GROUP BY 1 ORDER BY 2 DESC")
	print '<ul class="wikis %s">'% site.hostname()
	for rp_domain, count in cursor:
		print '<li class="wiki %s">%s</li>'%(' selected' if rp_domain == site.hostname() else '', makelink("{} ({:,})".format(rp_domain, count,),'hostname', rp_domain)) 
	print '</ul>'
	# 1390: Prepared statement contains too many placeholders
	param_limit = (65535 - 32) // 4
	cursor.execute("""
SELECT rp_rev_id, rp_tool, rp_timestamp, rp_tags 
FROM recentputs 
WHERE rp_domain=?
LIMIT ?
""", (site.hostname(), param_limit + 1,))
	stuff = cursor.fetchall()
	if cursor.rowcount >= param_limit:
		print '<div class="error">Input was limited to {:,} records</div>'.format(param_limit)

	# Changes list
	wikipedia.logtime("Prepared query")
	curs.execute("""
SELECT 
  rp_rev_id,
  rp_tool,
  rc_new,
  rc_minor,
  rc_bot,
  rp_timestamp AS starttime,
  rc_timestamp AS endtime,
--  rc_this_oldid,
--  rc_last_oldid,
  page_title AS rp_title,
  rc_user, /* IP formatting*/
  rc_user_text,
  rc_new_len,
  rc_old_len,
  comment_text,
  rc_this_oldid=page_latest AS top,
  IFNULL(rp_tags, ''),
  rev_id
FROM ("""+(
#('\nUNION '.join('SELECT {:d} AS rp_rev_id, "{}" AS rp_tool, "{}" AS rp_timestamp, "{}" AS rp_tags'.format(*tup) for tup in stuff))+"""
'\nUNION '.join('SELECT ? AS rp_rev_id, ? AS rp_tool, ? AS rp_timestamp, ? AS rp_tags'.format(*tup) for tup in stuff) or 
"SELECT NULL AS rp_rev_id, NULL as rp_tool, NULL AS rp_timestamp, NULL AS rp_tags"


)+""") AS recentputs
LEFT JOIN revision      ON rev_id=rp_rev_id
LEFT JOIN page          ON page_id=rev_page /* for "(top)" flag */
LEFT JOIN recentchanges ON rc_cur_id=rev_page AND rc_last_oldid=rp_rev_id 
                           /*Speed hack*/ 
                       AND rc_timestamp BETWEEN rp_timestamp AND DATE_FORMAT(rp_timestamp + INTERVAL 32 HOUR, "%Y%m%d%H%i%s")
LEFT JOIN comment       ON comment_id=rc_comment_id
WHERE """+' AND '.join(where_conditions)+"""
LIMIT ?
""", tuple(num for elem in stuff for num in elem)+tuple(where_data)+(urlargs.get('limit'),), max_time=300)
#""", tuple(where_data)+(urlargs.get('limit'),), max_time=300)
	wikipedia.logtime("Ran query with %d where_conditions" % len(where_conditions))
		
	users = {}
	tagsum = {}
	stats  = {}
	lastday = 0
	print '<table class="rctable lightrow sortable" style="font-size:92%;">'
	print '<tr style="vertical-align:bottom;"><th class="unsortable" style="width:0"></th><th>Tool</th><th></th><th>Title</th><th></th><th>User</th><th>Summary</th></tr>'
	for rp_rev_id, rp_tool, rc_new, rc_minor, rc_bot, starttime, endtime, rc_title, rc_user, rc_user_text, rc_new_len, rc_old_len, rc_comment, top, rp_tags, old_rev_exists in curs:
		rp_domain = site.hostname()
		rp_title = rc_title or ''
		# FIXME should be moved into the query:
		#if all(tag in rp_tags.split(', ') if tag.startswith('-') else tag not in rp_tags.split(', ') for tag in show_tags):
		#	print '<tr><td colspan="0">Skipping tags %r</td></tr>'%(rp_tags,)
		#	continue
		if rc_user_text:
			users[rc_user_text] = users.get(rc_user_text, 0) + 1
		for tag in rp_tags.split(', '):
			tagsum[tag] = tagsum.get(tag, 0) + 1
		if lastday != int(starttime[4:8]):
			print time.strftime('<tr><td colspan="7"><h3>%B %d</h3></td></tr>', time.strptime(starttime, "%Y%m%d%H%M%S"))
		elapsed = None
		if endtime:
			elapsed = time.mktime(time.strptime(endtime, "%Y%m%d%H%M%S"))-time.mktime(time.strptime(starttime, "%Y%m%d%H%M%S"))
			if 0 <= elapsed < 3600:
				if rp_tool not in stats: stats[rp_tool]=[]
				stats[rp_tool].append(elapsed)
		lastday = int(starttime[4:8])

	#'<attr title="%.1f minutes elapsed">%s:%s</attr>'%(elapsed/60.0, timestamp[8:10], timestamp[10:12]) if elapsed else '%s:%s' % (timestamp[8:10], timestamp[10:12]) if exists else ' ',
				# User

		newedit   = '<abbr class="newpage" title="This edit created a new page">N</abbr>' if rc_new else ' '
		minoredit = '<abbr class="minoredit" title="This is a minor edit">m</abbr>' if rc_minor else ' '
		botedit   = '<abbr class="botedit" title="This edit was performed by a bot">b</abbr>' if rc_bot else ' '
		patrolled = '<abbr class="unpatrolled" title="This edit has not yet been patrolled">!</abbr>' if False else ' '
		sizechng  = '<%(node)s class="%(plusminus)s" title="%(title)s">(%(change)+4d)</%(node)s>'%dict(
                    change=rc_new_len-rc_old_len,
                    node='span' if -500 < rc_new_len-rc_old_len < 500 else 'strong',
                    plusminus='mw-plusminus-pos' if rc_new_len-rc_old_len >=0 else 'mw-plusminus-neg',
					title="%d bytes after change"%rc_new_len,
                ) if rc_old_len and rc_new_len-rc_old_len else ''
		user_html = (
			'<span class="mw-userlink">[[User:%s|%s]]</span><span class="mw-usertoollinks"> ([[User talk:%s|t]] | [[Special:Contributions/%s|c]])</span>'%(4*(rc_user_text,))
		if rc_user else
			'<span class="mw-userlink">[[Special:Contributions/%s|%s]]</span><span class="mw-usertoollinks"> ([[User talk:%s|talk]])</span>'%(3*(rc_user_text,))
		) if rc_user_text != None else ''

		edittime = '%s:%s'%(endtime[8:10], endtime[10:12]) if endtime else ' '
		summary  = ' '.join(('<span class="comment">(%s)</span>'%wikipedia.escape(rc_comment) if rc_comment else '', '<b>(top)</b>' if top else '', '<small>(tag: %s)</small>'%wikipedia.escape(rp_tags.strip(', ')) if rp_tags else '',))
		className= wikipedia.escape('%s%s%s%s' % (
				rp_tool if rp_rev_id else 'deleted', 
				' ownedit' if rc_user_text == username else '',
				'' if old_rev_exists else ' invalid-rev',
				' offsite' if rp_domain!=site.hostname() else '',
		))
		rp_titlee = wikipedia.escape(rp_title.replace('_', ' '))
		rp_titleee = wikipedia.escape(rp_title)
		print wikisummary(rp_domain, cursor, u'''<tr class="%(className)s">
<td></td>
<td><tt>%(rp_tool)-12s%(minoredit)s%(botedit)s</tt></td>
<td style="" title="%(elapsed)s seconds">%(edittime)s</td>
<td>(<a href="https://%(rp_domain)s/w/index.php?title=%(rp_titleee)s&amp;diff=next&amp;oldid=%(rp_rev_id)s">diff</a> | <a href="https://%(rp_domain)s/w/index.php?title=%(rp_titleee)s&amp;action=history">hist</a>) [[%(rp_titlee)s]]</td>
<td>%(sizechng)s</td>
<td>%(user_html)s</td>
<td>%(summary)s</td>
</tr>''' % locals(), rp_title.replace(' ', '_')).encode('utf-8')
	print '</table>'
	wikipedia.logtime("Print changes (%d lookups in %d sec)"% (wikisummary_count, wikisummary_time))
		
	print '<h4 id="Tag_cloud">Tag cloud</h4>'
	print '<div id="wordcloud">'
	for tag in sorted(tagsum.keys(), key=unicode.lower):
		if tag==' ' or tag=='': continue
		count = tagsum[tag]
		print makelink(tag, "tags", tag, ' style="font-size:%dpx; line-height:100%%;" title="%s (%d)"' % (min(48, count + 4), tag, count)).encode('utf-8')
		print makelink(' (x)', "tags", "-%s"%tag, html=u'<img src="https://upload.wikimedia.org/wikipedia/commons/5/54/Delete-silk.png" width="16" height="16" alt="Remove" />').encode('utf-8')
	print '</div>'
	


	# def graph_activity(stats, users, limit=5):
	limit = 25
	toolcolors = {
		'mergeChanges': "DA3B15",
		'dabfix':	"FF9900",
		'dab_solver': 	"4582E7",
		'reflinks':	"80C65A",
		'commonfixes':	"990066",
		'':	"A2C180",
		'':	"FF0000",
	}
	'''
	print "<!-- "
	for key in stats:
		print " %s "%key
		print "\t".join("%s"%i for i in stats[key])
	print " -->"
	'''

	for key in stats.keys():
		if len(stats[key])<5:
			del stats[key]
	if stats=={}:return
	for key in stats: stats[key].sort()
	allstats = []
	for key in stats: allstats+=stats[key]
	avg = sum(allstats)/(1.*len(allstats))
	
	#allstats.sort()
	#stats['total']=allstats
	def joinsimple(list, scale):
		trans="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
		import binascii
		return ''.join(trans[int(n*scale)] for n in list)
	def joinextended(list, scale):
		trans="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-"
		import binascii
		return ''.join(trans[int(n*scale//64)]+trans[int(n*scale%64)] for n in list)
	
	if users:
		print '<table id="userlist" class="wikitable sortable">'
		print '<tr><th>User</th><th></th></tr>'
		for user, count in sorted(users.iteritems(), key=lambda x: x[1], reverse=True)[:limit]:
			print '<tr><td>%s</td><td>%d</td></tr>' % (makelink(user,'user',user).encode('utf-8'), count,)
		print '</table>'

	print """<div id="timespent" class="toccolours">
<h3 id="Statistics">Statistics</h3>
<img src="//chart.apis.google.com/chart?chxl=0:|Minutes|3:||Percentile|&amp;chxr=1,%(min)d,%(max)d&amp;chxt=t,y,x,x&amp;chs=400x500&amp;cht=lc&amp;chco=%(colors)s&amp;chds=%(scale)s&amp;chd=%(data)s&amp;chdl=%(labels)s&amp;chdlp=b&amp;chtt=Time+spent+tool+editing" width="400" height="500" alt="%(labels)s" style="clear:none;" /><br/>
Min: %(min)4.1f / Avg: %(avg)4.1f / Std: %(std)4.1f / Max: %(max)4.1f / Samples: %(len)s<br/>
The horizontal axis shows the percentage of edits completed in the given time period on the vertical axis.  Tools requiring more human intervention should have lines above those requiring less for most edits.
</div>
"""% {
	'min':	min(allstats) / 60.0,
	'avg':	avg / 60.0,
	'std':  (sum((i-avg)**2 for i in allstats)/(len(allstats)*1.0))**.5 / 60.0,
	'max':	max(allstats)/60.0,
	'len':	len(allstats),
	#'scale':	','.join('0,%d'% max(stats[key]) for key in stats),
	'scale': '0,%d'%max(allstats),
#	'data':	','.join("%d"%(s) for s in (v in stats.itervalues()) ),
	'data':	'e:'+','.join(joinextended(stats[key], 4095.0/max(allstats)) for key in stats) if len(allstats) < 800 else 's:'+','.join(joinsimple(stats[key], 61.0/max(allstats)) for key in stats),
#	'colors':	','.join(''.join('%X'%((ord(c)^0x04)&0x0F) for c in key[:6]) for key in stats),
	'colors':	','.join(toolcolors.get(key, '000000')    for key in stats),
	'labels':	'|'.join("%s+(%d)"%(key, len(stats[key])) for key in stats),
	#&chm=%(marker)s
	#'marker':	'|'.join('o,FF0000,%s,-1,5'%i for i in range(len(stats))),
}
	#
	print '<pre>%s</pre>'%wikipedia.timereport()

if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(title="Recent changes", form=False, head='''<style type="text/css">
#timespent { float:none; margin:auto; text-align:center; width:410px;}
#userlist { float:right; }
#wordcloud { border-bottom:1px solid gray; }
.mw-plusminus-pos { color: #006400; } /* dark green */
.mw-plusminus-neg { color: #8b0000; } /* dark red */
.mw-plusminus-null { color: #aaa; } /* gray */

span.comment {	font-style: italic;	}
.autocomment { color: gray; }
.newpage, .minoredit, .botedit { font-weight:bold;	}
.mw-redirect { background:#fff; }

tt { white-space:pre; }
small {	font-style: italic;	/* tags */ }

table { border-space:1px; }
tr { vertical-align:top; }
tr.deleted a { text-decoration: line-through; }

.mw-usertoollinks { white-space:nowrap; }

#Statistics { margin:0; }

/* mobile styles */
@media screen and (max-width: 720px) {
.rctable tr { display:block; margin-bottom:0.5em; }
.rctable th { display:none; }
.rctable td { display:inline; border:none!important;}
.rctable tr td:not(:last-child) { white-space:nowrap; }
.rctable td a, td span.comment { white-space:normal!important; }
#timespent { clear:both; margin:auto; width:auto;}
#timespent img { max-width:100%; height:auto; }
#userlist { float:none; margin:auto; }
#wordcloud { overflow:auto; }
} /* end @media */

.ownedit td:first-child { font-weight:bold; }

.invalid-rev td:first-child { border-left:#e36 solid 5px; }
.offsite td:first-child {
	border-style:solid;
	border-color: white #ec3;
	border-width: 0 0 0 5px;
}
ul.wikis li {
	display:inline-block;
	background-color:#ccc;
	color:#000;
	padding:0.1em;
	maring:0.1em;
}
</style>''')
		main()
	except toolsql.Error as (errno, strerror, extra):
		if errno in (1040, 1226, 1317, 2006, 2013):
		#if errno in (1040, 1226, 2013): # Too many connection / Max connections / Lost connection
			print '<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>'
			print('<p><strong class="errormsg">Query error %d: <code>%s</code></strong></p>' % (errno, wikipedia.escape(strerror),))
		else:
			raise
	finally:
		wikipedia.endContent()
		wikipedia.stopme()

