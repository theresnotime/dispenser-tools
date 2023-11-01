#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
"""
import re, time
import wikipedia, pagegenerators
import toolsql

monthnames={
	'': '',
	'01': u'January',
	'02': u'Febuary',
	'03': u'March',
	'04': u'April',
	'05': u'May',
	'06': u'June',
	'07': u'July',
	'08': u'August',
	'09': u'September',
	'10': u'October',
	'11': u'November',
	'12': u'December',
}

wikilink_r = re.compile(ur"\[\[([^{|}[\]<\n>]+)\|([^]]+)\]\]('??\w*)", flags=re.U)
autocomment_R = re.compile(ur'/\*\s*(.+?)\s*\*/', flags=re.U)
expandwlink_R = re.compile(ur'\[\[([^{|}[\]<\n>]+)\]\]', flags=re.U)

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
checklinks = 1 # 0-no check, 1-all, 2-only propulated
wikisummary_count = 0
wikisummary_time = 0
def wikisummary(domain, cursor, s, default=u'Main_Page'):
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

def htmlout(s, data=[]):
	out = s % tuple(wikipedia.escape("%s"%value) if isinstance(value, (bytes, str, unicode)) else value for value in data)
	print out.encode('utf-8')

def main():
	genFactory = pagegenerators.GeneratorFactory()
	# Up the limit for genFactory
	genFactory.limit = 500
	page = wikipedia.MyPage
	site = wikipedia.getSite()
	username = wikipedia.SysArgs.get('username', wikipedia.os.getenv("HTTP_X_FORWARDED_FOR"))
	for arg in wikipedia.handleArgs():
		genFactory.handleArg(arg)
	generator = genFactory.getCombinedGenerator() 
	users = ()
	for page in generator or []:
		if '/' not in page.title():
			users += (page.titleWithoutNamespace(underscore=True),)
	limit = 1000
	wikipedia.logtime("Initialized")
	wikipedia.logtime("Got database connection")
	with toolsql.getConn(site.dbName()) as curs:
		curs.execute('SELECT ns_id, ns_name, ns_is_favorite=1 FROM u2815__p.namespacename WHERE dbname=(SELECT DATABASE()) ORDER BY ns_id', max_time=8)
		namespaces = [('', 'all')]
		for ns_id, ns_name, ns_is_favorite in curs:
			all_namespaces[ns_name.replace(' ', '_')] = ns_id
			if ns_id >= 0 and ns_is_favorite:
				namespaces.append((ns_id, ns_name))
		wikipedia.logtime("Got namespaces")
	cursor = toolsql.getConn(site.dbName(), cluster='web').cursor()
	if not users:
		htmlout('''
<fieldset>
<legend>Linked users</legend>
<form>
<input type="hidden" name="namespace" value="2">
<input type="text"   name="links" value="Wikipedia:WikiProject Dungeons &amp; Dragons/Participants" size="60">
<input type="submit" value="Go">
</form>
</fieldset>
<!-- Use &page=User:Jimbo_Wales for just that user or<br/>-->
''')
		return

	if checklinks:
		cursor.execute("""
SELECT DISTINCT page_namespace, page_title, page_is_redirect
FROM page
WHERE page_namespace=2 AND page_title IN ("""+(','.join(('?',)*len(users)) or "NULL")+""")
UNION
SELECT DISTINCT page_namespace, page_title, page_is_redirect
FROM page
WHERE page_namespace=3 AND page_title IN ("""+(','.join(('?',)*len(users)) or "NULL")+""")
UNION 
SELECT DISTINCT page_namespace, page_title, page_is_redirect
FROM page
JOIN (
  SELECT rc_cur_id
  FROM recentchanges
  WHERE rc_user_text IN ("""+(','.join(('?',)*len(users)) or "NULL")+""")
  AND rc_type=0	
  ORDER BY rc_id DESC
  LIMIT ?
) AS x ON page_id=x.rc_cur_id
""", users+users+users+(limit,), max_time=60)
		for ns, title, result in cursor.fetchall():
			linkCache[ns, title] = "mw-redirect" if result == 1 else ""
		wikipedia.logtime("Populated linkCache dictionary (%s)"%len(linkCache))
	
	print "<div><b>Users:</b><br/>%s</div>"%(
		u' &#8226; '.join(wikisummary('en.wikipedia.org', cursor, u"[[User:%s|%s]]"%(user,user)) for user in users).encode('utf-8'),
	)

	cursor.execute("""
SELECT rc_timestamp, rc_user_text, rc_namespace, rc_title, rc_new, rc_minor, rc_bot, rc_id, rc_old_len, rc_new_len, rc_comment, rc_user, rc_cur_id, rc_this_oldid, rc_last_oldid 
FROM recentchanges 
WHERE rc_user_text IN ("""+(','.join(('?',)*len(users)) or "NULL")+""")
  AND rc_type=0
ORDER BY rc_id DESC 
LIMIT ?""", users+(limit,), max_time=300)

	wikipedia.logtime("Ran query")

	def ptitle((ns, title)):
		return (wikipedia.namespaces[ns]+':'+title if ns else title).replace('_', ' ')

	def dump(hdate, values):
		domain= 'en.wikipedia.org'
		def makelink(title, query):
			return "http://%s/w/index.php?title=%s&%s" % (domain, title.replace(' ', '_'), query)
		htmlout("<h4>%s %s</h4>", (monthnames[hdate[4:6]], hdate[6:8],))
		print '<ul>'
		for rc_timestamp, rc_user_text, rc_namespace, rc_title, rc_new, rc_minor, rc_bot, rc_id, rc_old_len, rc_new_len, rc_comment, rc_user, rc_cur_id, rc_this_oldid, rc_last_oldid in values:
			title = ptitle((rc_namespace, rc_title))
			change = rc_new_len-rc_old_len if rc_new_len else 0
			print wikisummary(domain, cursor,
				u'<li>(<a href="%s">diff</a>&nbsp;| <a href="%s">hist</a>) . . [[%s]]; %s:%s . . %s . . %s %s</li>' % (
					makelink(title, u"curid=%s&diff=%s&oldid=%s" % (rc_cur_id, rc_this_oldid, rc_last_oldid,)),
					makelink(title, u"curid=%s&action=history" % (rc_cur_id,)),
					title,
					rc_timestamp[8:10], rc_timestamp[10:12], 
					u'<%(node)s class="%(plusminus)s">(%(change)+4d)</%(node)s>'%dict(
						node='span' if -500 < change < 500 else 'strong', 
						plusminus='mw-plusminus-null' if change==0 else 'mw-plusminus-pos' if change>=0 else 'mw-plusminus-neg',
						change=change, 
					) if rc_new_len else '',
					# User
					('<span class="mw-userlink">[[User:%s|%s]]</span><span class="mw-usertoollinks"> ([[User talk:%s|talk]] | [[Special:Contributions/%s|contribs]])</span>'%(4*(rc_user_text,))
					if rc_user else
					'<span class="mw-userlink">[[Special:Contributions/%s|%s]]</span><span class="mw-usertoollinks"> ([[User talk:%s|talk]])</span>'%(3*(rc_user_text,))
					),
					# summary
					'<span class="comment">(%s)</span>'%wikipedia.escape(rc_comment) if rc_comment else ''),
				title
			).encode('utf-8')
		print '</ul>'
	
	date=''
	changes=[]
	prevdate = None
	for tup in cursor.fetchall():
		# YYYYMMDDHHMMSS
		date=tup[0][0:8]
		if date!=prevdate:
			if prevdate:
				# Execute
				dump(prevdate, changes)
			changes=[]
			prevdate=date
		changes.append(tup)
	else:
		dump(date, changes)
	
	wikipedia.logtime("Print changes (%d lookups in %d sec)"% (wikisummary_count, wikisummary_time))
	print '<pre>%s</pre>'%wikipedia.timereport()

	
if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=False, head='''<style type="text/css">
.mw-plusminus-pos { color: #006400; } /* dark green */
.mw-plusminus-neg { color: #8b0000; } /* dark red */
.mw-plusminus-null { color: #aaa; } /* gray */

span.comment {	font-style: italic;	}
.autocomment { color: gray; }
.newpage, .minoredit, .botedit { font-weight:bold;	}

.mw-usertoollinks { white-space:nowrap; }
</style>''')
		main()
	finally:
		wikipedia.endContent()
		wikipedia.stopme()

