#!/usr/bin/env python 
# -*- coding: utf-8  -*-
"""
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, version 2 of the License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.


Test cases:
http://toolserver.org/~dispenser/cgi-bin/related.py?dbname=enwiki_p&title=Nei%20%28disambiguation%29&ref=Phantasy_Star_II
http://toolserver.org/~dispenser/cgi-bin/related.py?dbname=ruwiki_p&title=%D0%91%D1%80%D0%B0%D1%82%D1%81%D1%82%D0%B2%D0%BE&ref=%D0%98%D0%B4%D0%B5%D0%B0%D0%BB
http://toolserver.org/~dispenser/cgi-bin/related.py?title=Supergroup_%28music%29&ref=Mick_Jagger (Very large relate JOINs)


"Page title": {
	relateness: n,
	snippit : "String",
	biodates : " (bith-death)",
	dates : " something else "
}
"""
import time; StartTime = time.time()
timings = []
def logtime(event):
	global timings
	timings.append((event, time.time(),))
def timereport():
	last = StartTime
	lout = []
	for event, sec in timings:
		lout.append('%7.3f %7.3f    %s'%(sec-StartTime, sec-last, event, ))
		last = sec
	return '\n'.join(lout)

import cgi, oursql
from os.path import expanduser
# Since we aren't sending text/html, disable traceback display
import cgitb; cgitb.enable(logdir='tracebacks', display=0)

goutput=""
log_timings = False

namespaces = { # Just needs 2, 4, 6
	-2: 'Media',
	-1: 'Special',
	0: '',
	1: 'Talk:',
	2: 'User:',
	3: 'User talk:',
	4: 'Wikipedia:',
	5: 'Wikipedia talk:',
	6: 'File:',
	7: 'File talk:',
	8: 'MediaWiki:',
	9: 'MediaWiki talk:',
	10: 'Template:',
	11: 'Template talk:',
	12: 'Help:',
	13: 'Help talk:',
	14: 'Category:',
	15: 'Category talk:',
	100: 'Portal:',
	101: 'Portal talk:',
	108: 'Book:',
	109: 'Book talk:',
	118: 'Draft:',
	119: 'Draft talk:',
	446: 'Education Program:',
	447: 'Education Program talk:',
	710: 'TimedText:',
	711: 'TimedText talk:',
	828: 'Module:',
	829: 'Module talk:',
	2300: 'Gadget:',
	2301: 'Gadget talk:',
	2302: 'Gadget definition:',
	2303: 'Gadget definition talk:',
	2600: 'Topic:',
}

sicatlang = {
	'enwiki_p':	("All_set_index_articles", ),
	# SELECT CONCAT('\t\'',ll_lang,'wiki_p\': ("',REPLACE(SUBSTR(ll_title,INSTR(ll_title,':')+1),' ','_'),'", ),')
	# FROM page JOIN langlinks ON ll_from=page_id
	# WHERE page_namespace=14 AND page_title IN ("All_set_index_articles")
	# ORDER BY 1;
	'fawiki_p': ("همه_مقاله‌های_مجموعه‌نمایه", ),
	'zhwiki_p': ("全部設置索引條目", ), 
}

WiktRefQuote = {
	'en':(
    "citation",
	"citation/new",
	"cite",
	"cite meta",
	"cite news",
	"cite newsgroup",
	"cite paper",
	"cite video game",
	"cite web",
	"cite wikipedia",
	"cite-book",
	"cite-magazine",
	"cite-newspaper",
	"cite-paper",
	"cite-usenet",
	"citelink",
	"gbooks",
	"gmq-oda-timeline",
	"grc-cite-Plato-Laws-chapcon",
	"grc-cite-Plato-Republic-chapcon",
	"JSTOR",
	"la-timeline",
	"LDL",
	"pt-cite-peregrinaçam",
	"quote-book",
	"quote-Don Quixote",
	"quote-Fanny Hill",
	"quote-hansard",
	"quote-journal",
	"quote-magazine",
	"quote-news",
	"quote-newsgroup",
	"quote-song",
	"quote-us-patent",
	"quote-usenet",
	"quote-video",
	"quote-web",
	"reference-book",
	"reference-hansard",
	"reference-journal",
	"reference-journal/sandbox",
	"reference-newsgroup",
	"reference-song",
	"reference-video",
	"roa-opt-cite-cantigas",
	"seeCites",
	"seemoreCites",
	"SIC",
	"timeline",
	"vi-see nom cites",
	)
}
AltTemplates = { 'en': (
    "alternative_spelling_of",
	"obsolete_spelling_of",
	"alternative_form_of",
	"archaic_spelling_of",
	"plural_of",
	"alternative_name_of",
	"singulative_of",
	"inflection_of",
	"en-past_of",
)}

connections = {}
def getCursor(dbname, host=None, reconnect=False):
	try:
		connections[reconnect or host,dbname].ping()
	except: # KeyError,...
		for i in range(10):
			try:
				connections[host,dbname] = oursql.connect(
					db=dbname,
					host=host or dbname[:-2]+'.labsdb',
					read_default_file=expanduser('~/.my.cnf'),
					local_infile=False,
					charset='utf8',
					use_unicode=False,
					raise_on_warnings=False
				)
				break
			except oursql.Error as e:
				(errno, strerror, extra) = e.args
				global goutput; goutput += repr(strerror)+"\n"
				# Too many connection/Max user connections/'reading initial communication packet'
				if e.errno in (0, 1040, 1226, 2013) and i < 3:
					# retry
					import random
					time.sleep(random.randint(15,60))
				else:
					logtime('Too many retries')
					raise
		logtime('Database connection [%s%s]'%(dbname, ' on %s'%host if host else ''))
	return connections[host,dbname].cursor()

def dropCursor(dbname, host=None):
	if (host,dbname) in connections:
		try:connections[host,dbname].close()
		except:pass
		del connections[host,dbname]
	
js_escaped = dict((chr(i), chr(i) if i > 31 else b'\\x%02x'%i) for i in range(256))
js_escaped.update({
	b'\0':  b'\\0',
	b'\n':  b'\\n',
	b'\r':  b'\\r',
	b"'":	b"\\'",
	b'&':	b'\\x26',
	b'/':	b'\\/',
	b'>':	b'\\x3E',
	b'<':	b'\\x3C',
	b'\\':  b'\\\\',
})

from urllib import quote
def jsquote(s):
	return b"'"+b''.join(map(js_escaped.__getitem__, str(s)))+b"'"

def likeescape(s, escape='\\'):
	return s.replace('\\',r'\\').replace('_', r'\_').replace('%', r'\%')

def escape(s):
	return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', '&quot;')

prev_results = {}
def relate(dbname, ref, targ):
	"""
explain SELECT COUNT(*)
FROM pagelinks AS base
JOIN pagelinks AS target ON base.pl_from = target.pl_from
WHERE base.pl_namespace = 0 AND base.pl_title IN (
    SELECT page_title FROM page JOIN redirect ON page_id=rd_from WHERE  rd_namespace=0 AND rd_title="Y"
)
AND target.pl_namespace = 0 AND target.pl_title IN (
    SELECT page_title FROM page JOIN redirect ON page_id=rd_from WHERE page_namespace=0 AND rd_namespace=0 AND rd_title="X"
);
	"""
	cursor = getCursor(dbname)
	def getRedirects(ns, title):
		cursor.execute("/* related.getRedirects LIMIT:1 NM */ SELECT SQL_CACHE DISTINCT page_title FROM page JOIN redirect ON page_id=rd_from WHERE page_namespace=0 AND rd_namespace=? AND rd_title=? LIMIT 500", (ns, title))
		return [(title,),] + cursor.fetchall()

 	if ref not in prev_results:
		prev_results[ref] = getRedirects(0, ref)
	list1 = prev_results[ref]
	list2 = getRedirects(0, targ)
	cursor.execute("""
/* related.relate LIMIT:1 NM */
SELECT SQL_NO_CACHE COUNT(DISTINCT base.pl_from)
FROM pagelinks AS base
JOIN pagelinks AS target ON base.pl_from = target.pl_from
WHERE base.pl_namespace = 0 AND   base.pl_title IN (%s)
AND target.pl_namespace = 0 AND target.pl_title IN (%s)
"""%(','.join(('?',) * len(list1)), ','.join(('?',) * len(list2)),),
		zip(*(list1+list2)).pop() # (('page',),) -> ('page',)
	)
	(count,), = cursor.fetchall()
	#count = len(cursor.fetchall())
	#cursor.execute("SELECT COUNT(*) FROM pagelinks WHERE pl_namespace=? AND pl_title=?", (0, targ))
	#(xm,), = cursor.fetchall()
	#global goutput; goutput += repr(prev_results[ref])
	#global goutput; goutput += "\n%d/%s on set %r\n" % ( count, xm, list2)
	with open('../cgi-bin/generation_stats/relate_%s'%dbname, 'a') as f:
		f.write('%s\t%s\t%s\n'%(ref, targ, count))
	return count

def dabpage(dbname, title, relatedto, extralinks=[]):
	global goutput
	setindexcategory = sicatlang.get(dbname, ("",))
	cursor = getCursor(dbname)
	cursor.execute("""/* related.listlinks LIMIT:30 */
SELECT
  pl_namespace,
  pl_title,
  /*pl.page_id, /* red link test */ 
  rd_namespace,
  rd_title,
  /* CONCAT(ns_name, IF(ns_name="", '', ':'), pl_title) AS title */
  EXISTS (SELECT 1 FROM page_props
    WHERE pp_page=IFNULL(rd.page_id, pl.page_id) AND pp_propname="disambiguation"
  ) AS disambig,
  EXISTS (SELECT cl_to FROM categorylinks 
    WHERE cl_from = IFNULL(rd.page_id, pl.page_id) AND cl_to IN ("""+','.join(('?',) * len(setindexcategory))+""")
    LIMIT 1
  ) AS setindex,
  EXISTS (SELECT 1 FROM pagelinks 
    WHERE pl_from=IFNULL(rd.page_id, pl.page_id) AND pl_namespace=? AND pl_title=?
  ) AS circular,
  EXISTS (SELECT 1 FROM page, pagelinks AS a
    WHERE page_namespace=? AND page_title=? AND page_id=a.pl_from
	AND a.pl_namespace=lnk.pl_namespace AND a.pl_title=lnk.pl_title
  ) AS direct
FROM pagelinks AS lnk
/* LEFT JOIN u2815__p.namespacename ON ns_id=pl_namespace AND dbname=(SELECT DATABASE()) AND ns_is_favorite=1 */
LEFT JOIN page AS pl ON pl.page_namespace=pl_namespace AND pl.page_title=pl_title
LEFT JOIN redirect   ON rd_from = pl.page_id
LEFT JOIN page AS rd ON rd.page_namespace=rd_namespace AND rd.page_title=rd_title

WHERE pl_from IN (
SELECT IFNULL(rd.page_id, page.page_id)
FROM page
LEFT JOIN redirect   ON rd_from=page_id
LEFT JOIN page AS rd ON rd.page_namespace=rd_namespace AND rd.page_title=rd_title
WHERE page.page_namespace=? AND page.page_title=?
) AND pl_namespace=0

LIMIT ?
""", setindexcategory+(0, relatedto, 0, relatedto, 0, title, 500, ))
# Limit to 500 [TODO give limit rational]
	logtime('Blue link list')
	excessedtime = False
	# .fetchall() since cursor might be closed by a subcall
	for pl_namespace, pl_title, rd_namespace, rd_title, disambig, setindex, circular, direct in cursor.fetchall():
		similar = -4     # invalid/error
		if direct:
			similar = 7  # Already linked on page
		elif circular:
			similar = -3 # circular/loop icon
		elif setindex: 
			similar = -2 # set-index
		elif disambig:
			similar = -1 # dab
		elif pl_namespace==0 and rd_namespace in (0, None,):
			if time.time() - StartTime > 60:
				# Scrap any results after 60 seconds since the user's likely already gone anyway
				# Also avoids problem pages, e.g. Beyoncé_Knowles=4788 backlinks, Mick_Jagger=3272 backlinks
				excessedtime = True
				continue
			try: 
				count = relate(dbname, relatedto, rd_title or pl_title)
			except Exception as e:
				goutput += repr(e)+"\n"
				similar = -4	# invalid/error
			else:
				if   count < 0:
					pass
				elif count == 0:
					similar = 0 # 0/4 bars - empty  - 65.0%
				elif count <= 1:
					similar = 1 # 1/4 bar  - maroon - 12.0%
				elif count <= 4:
					similar = 2 # 2/4 bars - yellow - 10.8%
				elif count <= 18:
					similar = 3 # 3/4 bars - green  -  7.9%
				else:
					similar = 4 # max bars - blue   -  4.3%
		else:
			pass
		yield (pl_namespace, pl_title, similar)
	
	if excessedtime:
		goutput += "TimedOut: relate() excessed time limit\n"
	
	# TODO handle bluelink like disambiguation links
	for pl_namespace, pl_title, similar in extralinks:
			if similar:
				yield (pl_namespace, pl_title, similar)
				continue
			try: 
				count = relate(dbname, relatedto, pl_title)
				#goutput += "%r\n"%((pl_namespace, pl_title, ns_name, links, ns_links, log_deletes, example, trans_count),)
				if   count < 0:
					similar = -4
				elif count == 0:
					similar = 0
				elif count <= 1:
					similar = 1
				elif count <= 4:
					similar = 2
				elif count <= 18:
					similar = 3
				else:
					similar = 4
			except Exception as e:
				goutput += repr(e)+"\n"
				similar = -4	# invalid/error
			yield (pl_namespace, pl_title, similar)

def links_lifespans(dbname, title):
	cursor = getCursor(dbname)
	cursor.execute("SET SESSION group_concat_max_len = 20000")
	cursor.execute("""/* related._year_range LIMIT:12 */
SELECT pl.page_title, GROUP_CONCAT(cl_to SEPARATOR "|")
FROM page
LEFT JOIN redirect   ON      rd_namespace=0 AND rd_from=page.page_id
LEFT JOIN page AS rd ON rd.page_namespace=0 AND rd.page_title=rd_title
JOIN pagelinks       ON      pl_namespace=0 AND pl_from=IFNULL(rd.page_id, page.page_id)
JOIN page AS pl      ON pl.page_namespace=0 AND pl.page_title=pl_title
JOIN categorylinks   ON cl_from=pl.page_id
WHERE page.page_namespace=? AND page.page_title=?
AND IFNULL(rd_fragment, '') = ''
GROUP BY pl.page_title;
""", (0, title, ))
	def getYear(s):
		parts = s.split('_', 1)
		if parts[0].replace('s', '').isdigit(): return parts[0]
		else: return None
	debut_cat_suffixes = ("albums","architecture","books","films","live_albums","musicals","novels","operas","plays","poems","short_stories","EPs","songs","singles","soundtracks","television_episodes","television_films","video_games","works","manga","anime","paintings","sculptures","ships","in_spaceflight",)
	for (page_title, cl_to, ) in cursor.fetchall():
		birth = None
		death = None
		debut = []
		for cat in cl_to.split('|'):
			# TODO i18n
			if   cat.endswith("_births"): 		birth = getYear(cat) or birth
			elif cat.endswith("_deaths"):		death = getYear(cat) or death
			elif cat=="Living_people":			death = ""
			elif cat=="Missing_people": 		death = "" or death
			elif cat=="Possibly_living_people":	death = ""
			elif cat=="Year_of_death_missing":	death = "?"
			elif cat=="Year_of_death_unknown":	death = "?"
			elif cat=="Year_of_birth_missing":	birth = "?" 
			elif cat=="Year_of_birth_unknown":	birth = "?" 
			else:
				a = cat.partition('_')
				if a[0].isdigit() and a[2] in debut_cat_suffixes:
					debut.append(int(a[0]))

		# Mark people older than 125 as death data unknown (1600 is arbitrary)
		if birth and birth[0:4].isdigit() and 1600 < int(birth[0:4]) < time.gmtime().tm_year-125:
			death = death or '?'
		if birth and death:	yield (page_title, "%s–%s"   % (birth, death, ))
		elif birth: 		yield (page_title, "born %s" % (birth,))
		elif death: 		yield (page_title, "died %s" % (death,))
		elif debut:			yield (page_title, max(set(debut), key=debut.count))
		else:
			#if sum(c.isdigit() for c in cl_to) >= 4:
			#	global goutput; goutput += "getting years row: %s %s\n"%(page_title, cl_to, )
			pass
		


def redlink_fulltext_searcher(dbname, namespace, prefixes):
	return () # disable
	if namespace!=0 or dbname!='enwiki_p' or not prefixes:
		return ()
	try:
		cursor = getCursor(dbname)
		cursor.execute(' UNION DISTINCT '.join(("""(
/* related.redlink_fulltext_searcher LIMIT:1 NM */
SELECT REPLACE(rl_title_ft, ' ', '_')
FROM u2815__p.redlinks_enwiki_p
WHERE MATCH (rl_title_ft) AGAINST (? IN NATURAL LANGUAGE MODE)
/* ORDER BY is implicit */
LIMIT 10;
)""",)*len(prefixes)), tuple(prefix.replace('_', ' ') for prefix in prefixes))
		return zip(*cursor.fetchall()).pop()
	except Exception as e:
		global goutput; goutput += repr(e)+"\n"
		return ()


def suggest_redlinks(dbname, namespace, title, limit=12):
	cursor = getCursor(dbname)
	setindexcategory = sicatlang.get(dbname, ("",))
	name_regexp = ur"^[-\'`.[:alpha:]]+(_[[:upper:]][-\'`.[:alpha:]]*)?_[[:upper:]][-\'`[:alpha:]]+$"
	# ^WikiProject_Missing_encyclopedic_articles/  # Promote these
	metapages = ur'|'.join(( # Blacklist
	# User:
		ur"^[^:/]+[Bb][Oo][Tt]/",				# Bot generated lists, usually from deletion logs
	# Wikipedia:
		ur"^WikiProject_Spam/COIReports/",      # Reports from 2007-2009 referencing deleted pages, should crawl deletion logs instead
		ur"^WikiProject_Red_Link_Recovery/",    # Meta project mostly moved to TopBanana's Tool
		ur"^Most-wanted_articles",              # 
		ur"^Templates_with_red_links/",         # Meta project which collects red links on templates
		ur"^WikiProject_Academic_Journals/Journals_cited_by_Wikipedia/", # Self-referential/bot
		ur"^Suggestions_for_disambiguation_repair/", # Reminents of a style bot
		ur"/Article_alerts(/|$)",               # Created by WP:Article_alerts bot
	))
	if '(' in title:
		prefix_title = title[:title.index('(')].strip('_')
	else:
		prefix_title = title
	
	rle_list = redlink_fulltext_searcher(dbname, namespace, [prefix_title])

	cursor.execute("""/* related.suggest_bluelinks LIMIT:2 NM */
	SELECT IFNULL(rd_namespace, page_namespace), IFNULL(rd_title, page_title)
	FROM page
	LEFT JOIN redirect ON page_id=rd_from
	WHERE page_namespace=? AND page_title=?
	""", (namespace, title,))
	(dnamespace, dtitle), = cursor.fetchall()
	
	# FIXME deal with redirect pages better
	cursor.execute("""/* related.suggest_bluelinks LIMIT:2 NM */
	SELECT page_namespace, page_title
	FROM redirect
	JOIN page ON page_id=rd_from
	WHERE rd_namespace=? AND rd_title=?
	AND page_namespace=0
	UNION SELECT ?, ?
	""", (dnamespace, dtitle, namespace, title, ))

	lookfor = ()
	for ns, prefix in cursor:
		if '(' in prefix:
			prefix = prefix[:prefix.index('(')].strip('_')
		prefix = likeescape(prefix)
		lookfor += (prefix+'\\_(%)', prefix.capitalize()+'\\_(%)', prefix+'\\_(%),\\_%', prefix+',\\_%', prefix+':\\_%')
	# Instead of using a general wild search (PREFIX*), we use multiple narrower 
	# searches to reduce junk results.  Most of these narrow search are based on 
	# [[WP:Pipe trick]]s, [[WP:Subpages]], and Proper names.  Additionally, we 
	# filter out links from talk pages and disambiguation pages.
	# 
	# TODO add examples
	# TODO support pluralized pipes
	# TODO search for sub-pages in supported namespaces: prefix.rstrip('/')+'/%', 
	cursor.execute("""
/* related.suggest_redlinks LIMIT:15 NM */
SELECT 
  pl_namespace,
  CAST(pl_title AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci AS pl_title_ci,
  ns_name, /* text for pl_namespace above */
  COUNT(*) AS link_count, 
  SUM(ref.page_namespace = pl_namespace) AS ns_count,
  (SELECT GROUP_CONCAT(DISTINCT DATE_FORMAT(log_timestamp, "%b %Y") SEPARATOR ", ")
    FROM logging_logindex
    WHERE log_namespace = pl_namespace AND log_title = pl_title
    AND log_action = "delete"
  ) AS log_deletes, 
  ref.page_namespace,
  ref.page_title,
  /* STRAIGHT_JOIN since statistics are sometimes bad.  See TS-1190 */
  SUM((SELECT STRAIGHT_JOIN COUNT(*) FROM templatelinks 
    JOIN page AS trans ON trans.page_id=tl_from AND trans.page_namespace=0 
    WHERE tl_namespace=ref.page_namespace AND tl_title=ref.page_title
  )) AS trans_count,
  (SELECT GROUP_CONCAT(DISTINCT CONCAT("Q", ips_item_id)) 
    FROM wikidatawiki_p.wb_items_per_site
    WHERE ips_site_id LIKE "%wiki" /* Only Wikipedias */
	AND ips_site_page = REPLACE(pl_title, "_", " ")
	HAVING COUNT(DISTINCT ips_item_id) = 1
  ) AS wd_item
	-- ,SUM(ref.page_namespace = pl_namespace AND ref.page_title = ?)

	
FROM page AS ref
JOIN pagelinks              ON pl_from = ref.page_id
LEFT JOIN page_props        ON pp_page = ref.page_id AND pp_propname="disambiguation"
LEFT JOIN categorylinks     ON cl_from = ref.page_id AND cl_to IN ("""+','.join(('?',)*len(setindexcategory))+""")
JOIN u2815__p.namespacename ON dbname = (SELECT DATABASE()) AND ns_id = pl_namespace AND ns_is_favorite = 1
LEFT JOIN page AS pl        ON pl.page_namespace = pl_namespace AND pl.page_title = pl_title
WHERE pl.page_id IS NULL
AND (
       pl_title IN ("""+','.join(('?',)*len(rle_list) or ('""',))+""")
    OR """+' OR '.join(("pl_title LIKE ?",)*len(lookfor))+"""
    OR (pl_title LIKE ? /* CAST(...) here to match accent chars */
       AND CAST(pl_title AS CHAR CHARACTER SET utf8mb4) REGEXP ?)
)
AND   pl_namespace = ?
/* No talk pages */
AND   ref.page_namespace % 2 = 0
/* Avoid meta references */
AND   ref.page_title NOT REGEXP ?
/* No disambiguation pages (also hack to correct ns_count) */
AND   pp_page IS NULL
AND   cl_from IS NULL /* No Set-Index */

GROUP BY pl_namespace, pl_title
ORDER BY
  /* Parentheses terms first */
  INSTR(pl_title,'_(') OR INSTR(pl_title,',') DESC,
  /* Article backlink count in graduations */
  FLOOR(LOG2(SUM(ref.page_namespace=0))) DESC,
  /* Put deleted items at the bottom */
  log_deletes IS NOT NULL,
  /* Case-insensitive alphabetize */
  pl_title_ci ASC
  /* Example should be an article */
  /* ref.page_namespace != 0 */
LIMIT ?
""", setindexcategory + rle_list + lookfor + (likeescape(prefix_title)+'\\_%', name_regexp, namespace, metapages, limit+1,)
	)
	#global goutput; goutput=prefix.capitalize()+'\\_(%)\n'
	return cursor

def suggest_bluelinks(dbname, namespace, title, limit=12):
	setindexcategory = sicatlang.get(dbname, ("",))
	cursor = getCursor(dbname)
	lookfor = ()
	
	cursor.execute("""/* related.suggest_bluelinks LIMIT:2 NM */
	SELECT IFNULL(rd_namespace, page_namespace), IFNULL(rd_title, page_title)
	FROM page
	LEFT JOIN redirect ON page_id=rd_from
	WHERE page_namespace=? AND page_title=?
	""", (namespace, title,))
	(dnamespace, dtitle), = cursor.fetchall()
	
	# FIXME deal with redirect pages better
	cursor.execute("""/* related.suggest_bluelinks LIMIT:2 NM */
	SELECT page_namespace, page_title
	FROM redirect
	JOIN page ON page_id=rd_from
	WHERE rd_namespace=? AND rd_title=?
	AND page_namespace=0
	UNION SELECT ?, ?
	""", (dnamespace, dtitle, namespace, title, ))
	
	for ns, prefix in cursor:
		if '(' in prefix:
			prefix = prefix[:prefix.index('(')].strip('_')
		prefix = likeescape(prefix)
		lookfor += (prefix+'\\_(%)', prefix.capitalize()+'\\_(%)', prefix+'\\_(%),\\_%', prefix+',\\_%', prefix+':\\_%')
	
	#
	# Not linked from a disambiguation page
	# No redirects
	cursor.execute("""/* related.suggest_bluelinks LIMIT:4 NM */
SELECT
  page.page_namespace,
  page.page_title
FROM page AS page

/* FIXME exclude dabpages until dabpage() support them in extralinks */
LEFT JOIN page_props ON pp_page=page.page_id AND pp_propname="disambiguation"
LEFT JOIN categorylinks ON cl_from=page.page_id AND cl_to IN ("""+','.join(('?',) * len(setindexcategory))+""")
WHERE pp_page IS NULL and cl_from IS NULL

AND page.page_namespace=0 AND page.page_is_redirect=0
AND ("""+' OR '.join(("page.page_title LIKE ?",)*len(lookfor))+""")
AND NOT EXISTS (SELECT 1 /* TODO handle redirects as well */
  FROM pagelinks
  JOIN page AS ref ON ref.page_id=pl_from
  WHERE     pl_namespace=0 AND pl_title=page.page_title
  AND ref.page_namespace=? AND ref.page_title=?
)
AND NOT EXISTS (SELECT 1 /* Not linked from a dab */
  FROM pagelinks
  JOIN page_props ON pp_page=pl_from AND pp_propname="disambiguation"
  WHERE pl_namespace=0 AND pl_title=page.page_title
)
AND NOT EXISTS (SELECT 1 /* No links from redirect from a dab */
  FROM redirect 
  JOIN page AS pl ON pl.page_namespace=0 AND pl.page_id=rd_from
  JOIN pagelinks  ON      pl_namespace=0 AND pl_title=pl.page_title
  JOIN page_props ON pl_from=pp_page AND pp_propname="disambiguation"
  WHERE rd_namespace=0 AND rd_title=page.page_title
)
HAVING page.page_namespace IS NOT NULL
AND NOT (page.page_namespace=? AND page.page_title=?) /* skip own title */
LIMIT ?
""", setindexcategory + lookfor + (namespace, title, namespace, title, limit,))
	return cursor

def suggest_wiktionary(dbname, namespace, title, limit=None):
		cursor = getCursor(dbname)

		cursor.execute("""/* redirect LIMIT:2 NM */
		SELECT IFNULL(rd_namespace, page_namespace), IFNULL(rd_title, page_title)
		FROM page
		LEFT JOIN redirect ON page_id=rd_from
		WHERE page_namespace=? AND page_title=?
		""", (namespace, title,))
		(dnamespace, dtitle), = cursor.fetchall()
	
		cursor.execute("""/*LIMIT:1 NM*/
SELECT iwl_title
FROM page
JOIN iwlinks ON iwl_from=page_id
WHERE iwl_prefix IN ('wikt', 'wiktionary')
AND page_namespace=? AND page_title=?
""", (dnamespace, dtitle,))
		existing_links = [iwl_title for (iwl_title,) in cursor]

		cursor.execute("""/* LIMIT:1 NM */
SELECT page_title
FROM page
JOIN redirect ON page_id=rd_from
WHERE page_namespace=rd_namespace
  AND rd_namespace=? AND rd_title=?
""", (dnamespace, dtitle,))

		# Find more prefixe
		titles_to_look_for = []
		for (title,) in cursor.fetchall() + [(title,)] + list(zip(existing_links)):
			title = title.decode('utf-8')
			bookcase = title.replace('_',' ').title().replace(' ', '_').replace('Of', 'of').replace('The', 'the')
			# Include first uppercase and first lowercase variants
			# [[wikt:-san]], [[wikt:emo-]]
			for tcasing in (
					title,
					title.capitalize(),
					title.lower(),
					title.upper(),
					title.replace('_',' ').title().replace(' ', '_'),
					bookcase,
					bookcase[0:1].lower() + bookcase[1:],
			):
				for pattern in (u'-%s', u'%s', u'%s-', u'%ss', u'%sd',):
					titles_to_look_for += [
						pattern % tcasing,
						pattern % tcasing.replace('-', '_'),
						pattern % tcasing.replace('_', '-'),
						pattern % tcasing.replace('_', '-', 1),
					]
		titles_to_look_for = [t.encode('utf-8') for t in set(titles_to_look_for)]
		
		wiktquote = list(WiktRefQuote['en'])
		alttemplates = list(AltTemplates['en'])
		wiktlang_R = "^(Abkhaz|Afar|Afrikaans|Akan|Albanian|Amharic|Arabic|Aragonese|Armenian|Assamese|Avar|Avestan|Aymara|Azeri|Bambara|Bashkir|Basque|Belarusian|Bengali|Bihari|Bislama|Breton|Bulgarian|Burmese|Catalan|Chamorro|Chechen|Chichewa|Chinese|Chuvash|Cornish|Corsican|Cree|Czech|Danish|Dhivehi|Dutch|Dzongkha|English|Esperanto|Estonian|Ewe|Faroese|Fijian|Finnish|French|Fula|Galician|Georgian|German|Greek|Greenlandic|Guaraní|Gujarati|Haitian_Creole|Hausa|Hebrew|Herero|Hindi|Hiri_Motu|Hungarian|Icelandic|Ido|Igbo|Indonesian|Interlingua|Interlingue|Inuktitut|Inupiak|Irish|Italian|Japanese|Javanese|Kannada|Kanuri|Kashmiri|Kazakh|Khmer|Kikuyu|Kinyarwanda|Kirundi|Kongo|Korean|Kurdish|Kwanyama|Kyrgyz|Lao|Latin|Latvian|Limburgish|Lingala|Lithuanian|Luba-Katanga|Luganda|Luxembourgish|Macedonian|Malagasy|Malay|Malayalam|Maltese|Manx|Maori|Marathi|Marshallese|Mongolian|Nauruan|Navajo|Ndonga|Nepali|Northern_Ndebele|Northern_Sami|Norwegian|Norwegian_Bokmål|Norwegian_Nynorsk|Occitan|Ojibwe|Old_Church_Slavonic|Oriya|Oromo|Ossetian|Pali|Pashto|Persian|Polish|Portuguese|Punjabi|Quechua|Romanian|Romansch|Russian|Samoan|Sango|Sanskrit|Sardinian|Scottish_Gaelic|Serbo-Croatian|Shona|Sichuan_Yi|Sindhi|Sinhalese|Slovak|Slovene|Somali|Sotho|Southern_Ndebele|Spanish|Sundanese|Swahili|Swazi|Swedish|Tagalog|Tahitian|Tajik|Tamil|Tatar|Telugu|Thai|Tibetan|Tigrinya|Tongan|Tsonga|Tswana|Turkish|Turkmen|Ukrainian|Urdu|Uyghur|Uzbek|Venda|Vietnamese|Volapük|Walloon|Welsh|West_Frisian|Wolof|Xhosa|Yiddish|Yoruba|Zhuang|Zulu)"
		
		wiktcur = getCursor(dbname.replace('wiki_p', '')+'wiktionary_p')
		wiktcur.execute("""/* related.suggest_wiktionary LIMIT:1 NM */
SELECT 
  page_title,
  (SELECT COUNT(*) FROM imagelinks WHERE il_from=page_id AND LOWER(CONVERT(il_to USING utf8mb4)) REGEXP "\.(flac|wav|ogg|oga)$") AS "&#128266;",
  SUM(tl_title IN ("IPA")) AS IPA,
  page_len
   - IFNULL((SELECT SUM(LENGTH(ll_lang)  + LENGTH(ll_title)+6) FROM langlinks WHERE ll_from=page_id), 0)
   - IFNULL((SELECT SUM(LENGTH(iwl_prefix)+LENGTH(iwl_title)+6) FROM iwlinks WHERE iwl_from=page_id), 0)
  AS page_len_adj,
  MAX(page_title IN ("""+','.join(('?',)*len(existing_links) or ('""',))+""")) AS "WP2Wikt",
  (SELECT COUNT(*) FROM pagelinks WHERE pl_from=page_id AND pl_namespace=0 AND pl_title NOT IN ("Wikipedia")) AS Links,
  (SELECT pl_title FROM pagelinks WHERE pl_from=page_id AND pl_namespace=0 AND pl_title NOT IN ("Wikipedia") LIMIT 1) AS Example,
  (SELECT COUNT(*) FROM categorylinks WHERE cl_from=page_id) AS "Cats",
  (SELECT COUNT(*) FROM categorylinks WHERE cl_from=page_id AND cl_to REGEXP ?) AS Lang,
  (SELECT COUNT(*) FROM categorylinks WHERE cl_from=page_id AND cl_to LIKE "English%") AS "EN",
  SUM(tl_title IN ("""+ ','.join(('?',)*len(alttemplates) or ('""',))+""")) AS Alt_of,
  SUM(tl_title IN ("""+','.join(('?',)*len(wiktquote) or ('""',))+""")) AS Cited,
  SUM(tl_title IN ("wikipedia", "slim-wikipedia", "projectlink/Wikipedia")) AS "WPBox",
  (SELECT COUNT(*) FROM iwlinks WHERE iwl_prefix IN ('wikt', 'wiktionary') AND iwl_from=page_id) AS "Wikt2WP",
  (SELECT COUNT(*) FROM pagelinks WHERE pl_from=page_id AND pl_namespace=0 
          AND pl_title IN ("""+ ','.join(('?',)*len(titles_to_look_for) or ('""',))+""")) AS "Xlinks"
FROM page
LEFT JOIN templatelinks ON tl_from=page_id
WHERE page_id IN (
  SELECT DISTINCT IFNULL(rd.page_id, page.page_id) AS page_id
  FROM page
  LEFT JOIN redirect   ON rd_from=page.page_id
  LEFT JOIN page AS rd ON rd.page_namespace=rd_namespace AND rd.page_title=rd_title
  WHERE page.page_namespace=0 AND page.page_title IN ("""+ ','.join(('?',)*len(titles_to_look_for) or ('""',))+""")
)
GROUP BY page_title
ORDER BY FLOOR(LOG10(page_len_adj)) DESC, CAST(page_title AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci ASC
""", tuple(existing_links + [wiktlang_R,] + alttemplates + wiktquote + titles_to_look_for + titles_to_look_for))
		
		definitions = []
		# TODO deal with using redirects (e.g. plural name going to non-plural definition)
		# transactions (1 link, plural) combine to transaction
		rows = wiktcur.fetchall()
		items = []
		displayed = []
		exists = []
		for row in rows:
			dr = dict((wiktcur.description[i][0], row[i]) for i in range(len(row)))
			x = dr['page_len_adj'] - (500 if dr['Cited'] else 0) - (300 if dr['Links'] < 3 else 0) - 200 * dr['Alt_of']
			item = '\n<li><a class="extiw wiktlink" style="%s" href="//%s.wiktionary.org/wiki/%s" title="%s">%s</a> %s</li>'% (
				'color:gray;' if x <= 200 else '',
				dbname.replace('wiki_p', ''),
				escape(row[0]),
				escape(row[0].replace('_',' ')),
				escape(row[0].replace('_',' ')),
				' '.join(s for s in [
				# Is Audio or IPA available?
				'&#128266;'    if row[1] else '/<i>IPA</i>/' if row[2] else '',
				'(listed)'     if dr['WP2Wikt'] else '',
				'<code style="border:1px solid #AAA; background-color:#ddd; font-size:0.8em;">“Quotes„</code>' if dr['Cited'] else '',
#				'<code>Links2WP</code>' if dr['Wikt2WP'] else '',
#				'<code>WP&nbsp;Box</code>' if dr['WPBox'] else '',
#				'%s-links (e.g. [[%s]])' % (dr['Links'], dr['Example']),
				'{:,} bytes'.format(dr['page_len_adj']),
#				'{:} x-links'.format(dr['Xlinks']),
#				]+[', <code>%s:&nbsp;%s</code>'%(
#					escape(wiktcur.description[i][0]),
#					escape(str(row[i])).replace('_', ' '),
#				) for i in range(8, len(row)-4)
				] if s),
			)
			items.append(item)
			if dr['WP2Wikt'] and x > 0 and dr['Xlinks']!=dr['Links']:
				exists.append(item)
			elif x >= 200 and dr['Xlinks']!=dr['Links']:
				displayed.append(item)
		#global goutput; goutput+= output
		if len(displayed) > 2 * len(exists):
			# Page already contain an infobox
			return ''
		elif displayed:
			return '\n<ul>\n%s\n</ul>' % '\n'.join(displayed)
		elif items:
			return '\n<ul>\n%s\n</ul>' % '\n'.join(items)
		else:
			return ''

def main(environ, start_response):
	#form = cgi.FieldStorage(environ['wsgi.input'], environ=environ, keep_blank_values=0)
	form = cgi.FieldStorage(environ=environ, keep_blank_values=0)
	dbname    = form.getfirst('dbname', 'enwiki_p')
	# title => disambiguation page
	title     = form.getfirst('title', '').replace(' ', '_')
	# relatedto => referring page
	relatedto = form.getfirst('ref',  '').replace(' ', '_')
	callback  = ''.join(c for c in form.getfirst('callback',  'addRelevancy2') if c.isalnum())
	maxage    = ''.join(c for c in form.getfirst('maxage', '3600') if c.isdigit())

	global goutput; goutput=""
	suggested_links = []
	def phrase_link(title, label="", className=None):
		return ('<a href="/wiki/%s" class="%s" title="%s">%s</a>'%tuple(escape(s) for s in (quote(title.replace(' ', '_'), safe=";@$!*(),/:"), className or '', title.replace('_', ' '), label or title.replace('_', ' '), ))).replace(' class=""', '')
	
	def phrase_red(pl_namespace, pl_title, ns_name, links, ns_links, log_deletes, example_ns, example, trans_count, wd_item):
		suggested_links.append((pl_namespace, pl_title, 7 if example == relatedto else None))
		s = phrase_link(pl_title, className="new")
		# Experimental Wikidata
		if wd_item:
			s += ' <small>(%s)</small>'%phrase_link("d:%s"%wd_item, wd_item, className="extiw uilink nolink nofollow")
		# TODO i18n this function
		# XXX len is counting bytes not chars
		if links == ns_links and len(pl_title) + len(example) + len(log_deletes or '') <= 99:
			# Display first example
			s += ' from %s' % ( 
				phrase_link(example, className="follow"),
			)
			if ns_links > 1:
				s += ' and '
				s += phrase_link("Special:WhatLinksHere/%s"%pl_title, "%d more"%(ns_links-1,), className="extiw uilink nolink nofollow")
		elif example_ns==10 and ns_links>=trans_count and ns_links+1==links:
			s += ' from {{%s}} with %d %s' % (
				phrase_link(namespaces[10]+example, example.replace('_', ' '), className="follow"),
				trans_count,
				'transclusion' if trans_count==1 else 'transclusions',
			)
			if ns_links-trans_count > 0:
				s += ' and '
				s += phrase_link("Special:WhatLinksHere/%s"%pl_title, "%d more"%(ns_links-trans_count,), className="extiw uilink nolink nofollow")
		elif example_ns in (2, 4, 6) and links==1 and len(example) < 80:
			example_full = namespaces.get(example_ns, '')+example
			s += ' from <small>%s</small>' % phrase_link(example_full, className="follow")
		
		# TODO "Linked from [non-main namespace, e.g. User]:Page"
		else:
			s += ', ' 
			s += phrase_link("Special:WhatLinksHere/%s"%pl_title, "%s%d %s%s"%(
				'%d article link%s / '%(ns_links-trans_count if ns_links>=trans_count else ns_links, '' if ns_links==1 else 's') if links > ns_links > 0 else '',
				links, 
				'article link' if links == ns_links else 'link',
				'' if links==1 else 's',
				), className="extiw uilink nolink nofollow"
			)
			#s += repr(dict(example_ns=example_ns, example=example, links=links, ns_links=ns_links, trans_count=trans_count))
		if log_deletes:
			s += ', <b>deleted %s</b>' % log_deletes
		return s

	def phrase_blue(*args):
		suggested_links.append((args[0],args[1],None))
		return phrase_link(args[1])

	logtime('Initialization')
		
	try:
		#
		try:
			redprefix_html = '\n'.join('<li>%s</li>' % phrase_red(*tup) for tup in suggest_redlinks(dbname, 0, title))
			if redprefix_html:
				redprefix_html = "<ul>%s</ul>\n"%redprefix_html
		except Exception as e:
			goutput += "suggest_redlinks(): %r\n"%(e,)
			redprefix_html = '<code>%r</code><br/>The redlink suggester had an error, try using the <a href="/~dispenser/cgi-bin/redlinks.py?page=%s" class="extiw uilink nolink nofollow" target="_blank">redlink prefix</a> tool' % (
				e, 
				quote(title[:title.index('_(')] if '_(' in title else title),
			)
		logtime('Red suggest (%d)' % len(suggested_links) )
		
		# 
		try:
			blueprefix_html = '\n'.join('<li>%s</li>' % (phrase_blue(*tup),) for tup in suggest_bluelinks(dbname, 0, title))
			if blueprefix_html:
				blueprefix_html = "<ul>%s</ul>\n"%blueprefix_html
		except Exception as e:
			goutput += "suggest_bluelinks(): %r\n"%(e,)
			blueprefix_html = '<code>%r</code><br/>The bluelink suggester had an error, try using <a class="extiw uilink nolink nofollow" href="/wiki/Special:PrefixIndex/%s" target="_blank">Special:PrefixIndex</a>' % (
				e,
				quote(title[:title.index('_(')] if '_(' in title else title),
			)
		logtime('Blue suggest (%d)' % blueprefix_html.count('</li>'))
		try:
			blueprefix_html += suggest_wiktionary(dbname, 0, title)
		except Exception as e:
			goutput += "suggest_bluelinks(): %r\n"%(e,)
			blueprefix_html = '<code>%r</code><br/>Wiktionary suggester had an error, try searching <a class="extiw uilink nolink nofollow" href="//%s.wiktionary.org/wiki/Special:Search/%s" target="_blank">searching</a>' % (
				e,
				dbname.replace('wiki_p', ''),
				quote(title[:title.index('_(')] if '_(' in title else title),
			)
		logtime('Wiktionary suggest')

		
		# If this fails should we recompute?
		results = list(dabpage(dbname, title, relatedto, extralinks=suggested_links)) # run generator already
		logtime('Computed related pages')
		lifespans = {}
		try:
			lifespans = dict(links_lifespans(dbname, title))
		except Exception as e:
			goutput += repr(e)+"\n"
		logtime('Looked up lifespans')

		start_response('200 Good', [
			('Cache-Control', 'max-age=%s, public' % (maxage or 0,)),
			('Content-Type', 'text/javascript; charset=utf-8'),
		])
		output = '''cache_suggestions(%s, %s);
%s({%s\n});
%s
''' % (
			# Link suggestions (cache_redlink() => cache_suggestions after Nov 2015)
			jsquote(title.replace('_', ' ')),
			'\n+ '.join(jsquote(s+'\n' if s else '') for s in (redprefix_html + blueprefix_html ).split('\n')),
			# Relationship map
			callback, 
			','.join('\n%s:%s' % (jsquote(b.replace('_', ' ')), "null" if c is None else c) for (a,b,c) in results),
			# Extra metadata
			'\n'.join('%s(%s, "%s");'%('cache_date' if isinstance(b, int) else 'cache_lifespan', jsquote(a.replace('_', ' ')), b) for (a,b) in lifespans.iteritems() if bytes(b) not in a),
		)
		# The format we'd like to have
		#output +='\n\ncallback( \n[\n%s\n]\n);' % ',\n'.join('{"ns":%d,"title":%s,"relevancy": %d, "dates":%s}' % (a, jsquote(b),c, lifespans.get(b,'null')) for (a,b,c) in results)
		logtime('Finished')
		infos = '''
/* Timeline:
%s

%2s relations computed

callback: %s
dbname: %s
title (dab): %s
ref: %s

%s*/''' % (timereport(), len(results), jsquote(callback), jsquote(dbname), jsquote(title), jsquote(relatedto), goutput.replace('*', ' * '))
		#with open(time.strftime('/home/dispenser/temp/__related__.%Y-%m-%d:%H'), 'a') as f:
		#	f.write(infos)
		output += infos
		return output
	except Exception as inst:
		goutput += repr(inst)+"\n"
		start_response('503 Python exception', [
			('Content-Type', 'text/plain; charset=utf-8'),
			('X-Error', repr(inst)),
		])
		print "/* Timeline:"
		print timereport()
		print goutput
		print "*/"
		# Attempt to communicate to user the error [Untested]
		print 'cache_suggestions(%s, %s);' % (jsquote(title.replace('_', ' ')), jsquote("Major error in related.py: %r" % (inst,)))
		# Don't log common errors
		if isinstance(inst, oursql.Error) and inst.errno in (2003,1317):
			# ProgrammingError: (1317, 'Query execution was interrupted
			# InterfaceError: (2003, "Can't connect to MySQL server
			pass
		else:
			raise
	finally:
		dropCursor(dbname)
	
		if log_timings:
			mtime = time.gmtime(cgi.os.path.getmtime(environ.get('SCRIPT_FILENAME', __file__)))
			with open('../cgi-bin/generation_stats/related', 'a') as f:
				f.write('%s\t%s\t%s\t%s\n'% (time.strftime("%Y-%m-%d %H:%M:%S"), title, time.strftime("%Y-%m-%d %H:%M:%S", mtime), time.time()-StartTime,))
		# invalid db

if __name__ == "__main__":
	if cgi.os.environ.get('GATEWAY_INTERFACE','').startswith('CGI/'):
		def start_response(status, headers):
			print 'Status:', status
			print 'X-Mode: Non-WSGI'
			print '\n'.join(': '.join(h) for h in headers)
			print 
		print main(cgi.os.environ, start_response)
	else:
		from flup.server.fcgi import WSGIServer
		WSGIServer(main).run()

