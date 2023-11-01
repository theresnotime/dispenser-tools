#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""


TODO
* Remove duplicate links (including if they redirect to the same place)
* detect self links (i.e. warn about unintended circular links)
* Add/remove prefixes/suffix, e.g. untether -> tether -> tethering or "Lifetime" -> "A lifetime"/"The lifetime"
-------

Test cases:
* [[IOS]]
* [[Riku]], [[Lulu]], [[Yuna]]
* [[Sandy]] (birth dates, suggest prefix index?)
* [[Pepe]] - better auto date formatting
* [[Dreamweaver (disambiguation)]] - Primary links
* [[Ikeda]]
* [[Rashomon]] incorrect primary link
* Dates: [[Julia]]

Acid tests:
* [[( ) (disambiguation)]]
"""
import re, sys, oursql, time, os 
import wikipedia
from wikipedia import canonicalTitle
import cgitb; cgitb.enable(logdir='tracebacks')
import sys; sys.path.append('/user-data/mosdab/');
import json
import toolsql
from toolsql import like_escape
try:
	import mosdab_auditor as mosdabbot
except ImportError as e:
	mosdabbot = None
	wikipedia.logtime('ImportError %r' % (e,))

# SELECT CONCAT("\t\'", ips_site_id, "_p': ('", REPLACE(SUBSTRING_INDEX(ips_site_page, ":", -1)," ","_"), "',),") AS "sicatlang"
# FROM wb_items_per_site WHERE ips_item_id = 8235738 ;
sicatlang = {
	'enwiki_p': ('All_set_index_articles',),
	'fawiki_p': ('همه_مقاله‌های_مجموعه‌نمایه',),
	'zhwiki_p': ('全部設置索引條目',),
	'ukwiki_p': ('Всі_статті_визначеного_індексу',),
	'scowiki_p': ('Aw_set_index_airticles',),
	'srwiki_p': ('Сви_чланци_са_индексом',),
	'urwiki_p': ('جملہ_فہرست_نما_اشاریے',), 
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


#######################################
# Print functions
#######################################
wikilink_R = re.compile(ur'\[\[([^{|}[\]<\n>]*)\|*((?<=\|)[^[\n\]|]+)?\]\]', flags=re.U)
def wikify(s, escape=True):
	if escape: s = wikipedia.escape(unicode(s))
	return wikilink_R.sub(lambda m: CreateLink(m.group(1), m.group(2)), unicode(s)).replace('\n', '<br/>')

def debug(s):
	print '<div class="info debug">', wikify(s).encode('utf-8'), '</div>'
	
def info(s):
	print '<div class="info">', wikify(s).encode('utf-8'), '</div>'
	
def warn(s):
	print '<div class="warn"> <span>Warning</span>', wikify(s).encode('utf-8'), '</div>'
	
def error(s):
	print '<div class="error"> <span>Error:</span> ', wikify(s).encode('utf-8'), '</div>'
	
def printu(s):
	print (s.encode('utf-8') if isinstance(s, unicode) else s)

def html(s, data=[]):
	if isinstance(data, dict):
		return s % dict(zip(data.keys(), (wikipedia.escape(value) if isinstance(value, (bytes, str, unicode)) else value for value in data.values())))
	else:
		return s % tuple(wikipedia.escape("%s"%value) if isinstance(value, (bytes, str, unicode)) else value for value in data)

def htmlout(string, data=[]):
	printu(html(string, data))




#######################################
# Article title functions
#######################################
# TODO move to commonfixes
import unicodedata
replacementset = {
	# Unicode to ASCII
	u'−': u'-',  # minus sign
	u'–': u'-',  # en dash
	u'—': u'-',  # em dash
	u'…': u'...',# ellipsis
	u'×': u'X',  # times
	u'“': u'"',  # curly quote
	u'”': u'"',
	
	# ASCII approximations and substitutions
	u' -': u'-',
	u'- ': u'-',
	u'--': u'-',
	u'_':  u' ',
	u'`':  u"'",
	u'/':  u'-',
	u'*':  u'X',
	
	# Titles
	u' DR. ': u'',
	u' MR. ': u'',
	u' MRS. ':u'',
	u' MS. ': u'',
	u' DR ':  u'',
	u' MR ':  u'',
	u' MRS ': u'',
	u' MS ':  u'',

	# language approximations
	u'AE': u'A',
	u'EY': u'EI',
	u'OH': u'O',
	u'OU': u'O',
	u'UU': u'U',
	u" 'N": ' AN',
	u' AND ': ' & ',
	u' THE ': ' ',
	u' OF ': ' IN ',
	u'K':  u'C',
}
def strip_variations(s, remove_qualifer=True):
	# returns 
	i = None
	if remove_qualifer and u' (' in s:
		i = s.find(' (')
	#if ', ' in s: i = s.rfind(', ')
	s = u" %s " % s[:i].replace('_', ' ').upper()
	# Remove diacritics/accents marks
	s = u''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
	# Own substitution table
	for c1, c2 in replacementset.iteritems():
		s=s.replace(c1, c2)
	# Remove punctuation and duplicate letters
	s = u''.join(c for i, c in enumerate(s) if c not in ' !"\',-.:;?' and (i==0 or c!=s[i-1]))
	return s
			
def skipredirect(cursor, match, prefixes):
	# TODO consider [[Aude (river)]] the same as [[Aude River]]
	# TODO add variable for acceptable changes to qualifier [0,1], where 1 allow complete change
	title = match.group()
	cursor.execute("""
SELECT rd_namespace, rd_title, rd_fragment 
FROM page 
JOIN redirect ON page_id=rd_from 
WHERE page_namespace=? AND page_title=? 
AND rd_namespace = page_namespace
AND rd_interwiki = "" /* Do not process interwikis */
""", (0, canonicalTitle(title, underscore=True),), max_time=10)
	for rd_namespace, rd_title, rd_fragment in cursor.fetchall():
		target = rd_title.replace('_', ' ')
		return_target = target[0].lower() + target[1:] if title[0].islower() else target
		doit = any(a.lower() in rd_title.lower() for a in prefixes) # Keep [[J John Amy]] => [[J J Amy]] from happening on [[John (disambiguation]] 
		if rd_fragment or rd_namespace:
			# avoid bypassing section redirects and cross-namespace
			return match.group()
		
		if strip_variations(target, remove_qualifer=False)==strip_variations(title, remove_qualifer=False):
			info("Redirect: [[%s]] to [[%s]] (automatically bypassed)" % (title, target, ))
			return return_target
		elif any(c in title for c in '(,') and not any(c in target for c in '(,'):
			if not title.endswith(('(disambiguation)',)): # Make [[User:Boleyn]] happy
				info("Redirect: [[%s]] to [[%s]] (no subject)" % (title, target, ))
			# don't lose the qualifier
			pass
		elif strip_variations(target)==strip_variations(title):
			info("Redirect: [[%s]] to [[%s]] (automatically bypassed)" % (title, target, ))
			return return_target
		elif strip_variations(re.sub(ur'^(\w+\.?) (\w+\.?) (\w+)$', r'\1 \3', target, flags=re.U)) ==  strip_variations(re.sub(ur'^(\w+\.?) (\w+\.?) (\w+)$', r'\1 \3', title, flags=re.U)) and doit:
			info("Redirect: [[%s]] to [[%s]] (Middle name changed/eliminated)" % (title, target, ))
			return return_target

		else:
			debug('Comparing %r to %r' % (strip_variations(title), strip_variations(target),))
			info("Redirect: [[%s]] to [[%s]]" % (title, target, ))
			debug('') # for visual clarity
	return match.group()


def wikilinkregex(t, firstupper=True, italic=False):
	t = canonicalTitle(t, firstupper)
	# Workaround for titles with an escape char
	if firstupper:
		t = ur'[%s%s]%s' % (t[0].upper(), t[0].lower(), t[1:],)
	t = re.escape(t)
	if firstupper:
		t = t.replace('\\[', '[', 1).replace('\\]', ']', 1)
	t = t.replace('\\|', '|')
	# Link text ''Dark Angel'' (film)
	if italic:
		t = re.sub(r"([^|]+?)(\\ \\\([^|]+)(?=\||$)", r"''\1''\2|\"\1\"\2|\1\2", t, flags=re.U)
	return t.replace('\\ ', '[ _]+')



def CreateLink(link, title=None, className="", addAttribute='', action='view', target=None):
	meta = linkInfo.get(canonicalTitle(link, underscore=True))
	if not className and meta:
		className = "new" if meta['missing'] else ""
	if not title: title = link.replace('_', ' ')
	attributes = ' class="'+className+'"' if className else ''
	if addAttribute:
		attributes += ' '+addAttribute
	if target:
		attributes += ' target="%s"' % target
	if isinstance(title, bytes):
		title = title.decode('utf-8')
	if isinstance(link, bytes):
		link = link.decode('utf-8')
	link_url = wikipedia.urllib.quote(link.replace(' ','_').encode('utf-8'), safe=b";@$!*(),/:-_.")
	return html(u'<a href="https://%s%s" title="%s"__ATTR__>%s</a>', (
		site.hostname(),
		site.nice_get_address(link_url) if action=='view' else site.page_action_address(link_url, action),
		link.replace('_',' '),
		title,
	)).replace('__ATTR__', attributes)

def heading(level, title, style="", className=""):
	sys.stdout.flush()
	printu('<h%d id="%s"%s%s>%s<a class="headerlink" href="#%s" title="Permalink to this headline">&#182;</a></h%d>' % (
		level,
		wikipedia.sectionencode(title),
		' style="%s"'%style if style else '',
		' class="%s"'%className if className else '',
		wikipedia.escape(title),
		wikipedia.sectionencode(title), level),
	)
	headings.append(title) # For Table of Contents

def wikibulleted(links, sortkey=None):
	return '\n'.join("* [[%s]]"%s.replace('_',' ') for s in links)


def EnglishJoin(lst, distinct=False, joined="or"):
	if distinct:
		lst = list(set(lst))
	if len(lst) <= 2:
		return (' '+joined+' ').join(lst)
	else:
		return ', '.join(lst[:-1]) + ', '+joined+' ' + lst[-1]


shown_diffs = []
def blame(page, added_text=None, removed_text=None):
	text = page.get()
	api_url = 'https://%s/%s' % (page.site().hostname(), page.site().apipath(),)
	import requests
	data = requests.get(api_url, params={
			'format': 'json',
			'formatversion': 2,
			'action': 'query',
			'prop': 'revisions',
			'titles': page.title(),
			'rvprop': 'ids|flags|timestamp|user|size|sha1|parsedcomment|content|flagged|tags',
			'rvlimit': 50,
	}).json()
	
	revisions = data['query']['pages'][0]['revisions']
	found = None
	for i, rev in enumerate(revisions):
		rev['match_found'] = added_text in rev['content']
		
		#print '<xmp>', rev, '</xmp>'
		#if isinstance(added_text, unicode) and added_text in rev['content']:
		if rev['match_found']:
			found = True
		else:
			if found == True:
				old_rev = revisions[i-1]
				global shown_diffs
				if old_rev in shown_diffs:
					found = False
					continue
				shown_diffs.append(old_rev)
				printu(u'<div class="blame">')
				htmlout((u'<a href="/w/index.php?title=%s&diff=%s&oldid=%s">%s</a> <a href="/wiki/User:%s">%s</a> (<a href="/wiki/User_talk:%s">talk</a>) (%s bytes) <span class="comment">('+old_rev['parsedcomment'].replace('%','%%')+')</span>').replace('="/w', '="https://%s/w'%page.site().hostname()), (
# minor
					page.urlname(),
					old_rev['revid'],
					old_rev['parentid'],
					old_rev['timestamp'],
					old_rev['user'],
					old_rev['user'],
					old_rev['user'],
					old_rev['size'],
				))
				wikipedia.showDiff(
					rev['content'],
					revisions[i-1]['content'],
					fromdesc="%s (%s)" % (rev['user'], rev['parsedcomment'],),
					todesc="%s (%s)" % (old_rev['user'], old_rev['parsedcomment'],),
				)
				printu(u'</div>')
			found = False

	return ''

parse_cache = {}
def make_description(site, title):
	extract_description_R = re.compile(ur'''<p>
	(?:
		  .{0,250}?</b>
		| .{0,500} </b> (?= ['",) ]*? (?: is | was | were | are | or ))
		| \w*\s*(?:%s)
	)
	(
		  ''
		| "
		| ,
		| [ ]\( [^(\n)]* \)
		| [\w ]*\'*<b>.*?</b>\'*
		# to next date (
		| .{0,100}\b1\d\d\d [)]
		| [ ](?: is | was | were | are | or )
	)*
	# Summary
	[ ]*(?P<desc>.+?)[,.:;]?
	\n?</p>''' % (wikilinkregex(title),), flags=re.X)

	title = canonicalTitle(title, underscore=True)
	if title not in parse_cache:
		text = site.getUrl(site.apipath(), data={
			'action': 'parse',
			'format': 'json',
			'page':   title,
			'utf8':   'yes',
			#'formatversion': '2', # TODO check for enabling
		})
		data = json.loads(text)
		if 'error' in data:
			error('API error in make_description(): %r' % (data['error'],))
			return ''
		parse_cache[title] = data[u'parse']
	parse = parse_cache[title]
	html  = parse[u'text'][u'*']

	# Avoid section redirects, rd_fragment isn't complete yet
	if 'redirects' in parse and parse['redirects']['tofragment']:
		# redirectToFragment("#Corkscrew_Senton");
		info("[[%s]] is a section redirect"%title)
		return ''
	elif ' id="disambigbox"' in html: # TODO use 'disambiguationpages'
		info("[[%s]] disambiguation page"%title)
		return ''
	elif ' id="setindexbox"' in html:
		info("[[%s]] set-index article"%title)
		return ''
	else:
		pass

	# Condition HTML for wiki text
	html = re.sub(ur'[^\S\n]+', ' ', html, flags=re.U) # convert emsp
	html = html.replace('<br />\n', ' ')
	html = html.replace('<i>', "''").replace('</i>', "''")
	# Strip reference notes and html tags
	html = re.sub(ur'<(\w{2,}\b)[^<>]+class="(?:reference|noprint)[^"]*"[^<>]*>(?:(?!<\1).)*?</\1>|</?(?![bip]\b)\w+\b.*?>|<!--.*?-->', '', html, flags=re.DOTALL)

	m = extract_description_R.search(html)
	if not m:
		error("Unable to get extract from [[%s]]'s HTML" % title)
		htmlout('<pre class="debug" style="white-space:pre-wrap;">%s</pre>', (html.strip(),))
		return ''
	s = m.group('desc')
	if len(s) > 250:
		#debug('Reduction, over 250 bytes %s' % s)
		s = re.sub(ur'(.{10,250}?)(?<! [Ee]tc|. Sr|. Jr|. Dr|. St| Ave|. Co| Inc| Ltd|.U\.S|..[. ].)\.((?:"|\'\'|) +[A-Z].*|$)', ur'\1', s)
	if len(s) > 250:
		#debug('Reduction, over 250 bytes %s' % s)
		s = re.sub(ur'(.{10,250}?)\.((?:"|\'\'|) +[A-Z].*|$)', ur'\1', s)
	if s.strip(',. '):
		# Show the parts we've taken out
		print '<div class="debug">'
		wikipedia.output(wikipedia.unescape("\03{lightsilver}%s\03{default}"%m.group().replace(s, '\03{default}%s\03{lightsilver}'%s)))
		print '</div>'
		s = u', %s'%wikipedia.unescape(s).strip()
		return s
	else:
		return ''

wdsite = wikipedia.Site('wikidata', 'wikidata')
def wikidata_description(site, item, lang='en'):
	from datetime import datetime
	def strptime(s):
		try:
			return datetime.strptime(s, "+%Y-%m-%dT%H:%M:%SZ")
		except ValueError:
			return datetime(int(s[1:5]), 1, 1)
	if item.isdigit():
		item = 'Q' + item
	text = wdsite.getUrl(wdsite.apipath(), data={
		'action': 'wbgetentities',
		'format': 'json',
		'utf8':   'yes',
		'formatversion': '2',
		'ids':    item,
	}) 
	data = json.loads(text)
	if u'error' in data:
		raise Exception("%s for %s"%(data[u'error'][u'code'], item))
	d = data[u'entities'][item][u'descriptions']
	descriptions = dict((d[key]['language'], d[key]['value']) for key in d)
	#  date of birth (P569) 
	#  date of death (P570) 
	claims = data[u'entities'][item].get('claims', {})
	births = deaths = []
	def get_dates(claim):
		# FSCK Wikibase, 
		# {u'datatype': u'time', u'property': u'P569', u'snaktype': u'somevalue'}
		z = [] 
		for x in claim:
			if 'datavalue' in x['mainsnak']:
				# return only first
				z.append(strptime(x['mainsnak']['datavalue']['value']['time']))
		return z
	if 'P569' in claims:
		births = get_dates(claims['P569'])
	if 'P570' in claims:
		births = get_dates(claims['P570'])
	#print '<xmp class="debug">', json.dumps(claims, indent=4, sort_keys=True), '</xmp>'
	return births[0] if births else None, deaths[0] if deaths else None, descriptions.get(lang, descriptions.get('en', descriptions.get('simple')))

	

def api_search(site, search_query, namespaces=[0], limit=10):
	page_json = site.getUrl(site.apipath(), data={
		'format': 'json',
		'utf8': 'yes',
		'formatversion': '2',
		#
		'action': 'query',
		'list': 'search',
		'srwhat': 'text',
		'srsearch': search_query,
		'srnamespace': '|'.join(str(ns) for ns in namespaces),
		'srlimit': limit,
		'srprop': 'sectiontitle|redirecttitle',
		'srinfo': '',
	})
	results = json.loads(page_json)[u'query'][u'search']
	#print '<xmp>',results, '</xmp>'
	for result in results:
		yield ("%(title)s#%(sectiontitle)s"%result if "sectiontitle" in result else result[u'title']).replace(' ', '_')

def scrape_search(site, search_query, namespaces=[0], limit=5000):
	"""
	# API Limited to 50 results!?  https://phabricator.wikimedia.org/T119189
	page_json = site.getUrl(site.apipath(), data={
		'action': 'query',
		'list': 'search',
		'srwhat': 'text',
		'srsearch': 'intitle:%s'%prefixes,
		'srprop': 'sectiontitle|redirecttitle',
		'srinfo': '',
	})
	html = json.loads(page_json)
	"""
	# TODO strip header + footer
	data = dict(('ns%d'%ns, '1') for ns in namespaces)
	data.update({
		'title':	'Special:Search',
		'search':	search_query,
		'limit':	limit,
		'offset':	'0',
		'useskin':	'monobook', # has start/end content
	})
	for i in range(3):
		html = site.getUrl(site.path(), data=data)
		if b'<!-- end content -->' in html:
			break
		# else: HTTP 500 retry 
	for m in re.finditer(br' href="/wiki/([^"]*?)"', html[html.index(b'<!-- start content -->'):html.index(b'<!-- end content -->')] ):
		yield canonicalTitle(wikipedia.unescape(m.group(1)), underscore=True)











headings = []
linkInfo = {}

CatPlaces = ur'_places_|_communities_|_constituencies_|_Country,_|_counties$|^Barangays_of_|^Cities_|^Plantations_|^Suburbs_of_|^Towns_|^Townships_in_|^Villages_|^Wards_of_|^Woredas_of_|micropolitan_area$|parishes$|_geography_stubs$'
CatPerson = ur"^(Living_people|Year_of_birth_uncertain|Year_of_death_missing|Year_of_death_unknown|Date_of_death_missing)$|^[^_]{2,200}_(deaths|births)$"

RelinkText = ur"^([*#]+[ '\"]*)(%s)([ '\"]*(?:[,\-—–−]|''|\"| is | were | \((?:1\d\d\d|20\d\d|[\-—–−]| )+\)|$))"


def parseline(self, cursor, line, prefixes):
	def getYear(s):
		# 47 BC
		# 2nd-century BC
		m = re.match(ur'(\d+)(s(?= )|)((?:st|nd|rd|th)[ -]century|)( BC|)', s.replace('_', ' '), flags=re.U)
		if m:
			return "%s%s%s%s"%(
				#'c. ' if m.group(2) else '',
				m.group(1),
				m.group(2),
				m.group(3),
				" BC" if m.group(4)==" BC" else ''
			)
		return None
	def yearRange(birth, death, born="born", died="died"):
		"""
		Formats birth and death years so "AD" is hidden for the modern era
		Accepts: 17 century/1860s/c. 1867/1867 [BC|AD]
		"""
		def n(tup):
			return " BC" if tup[1] else "" if tup[0]=="?" or len(tup[0])>=3 else " AD"
		death = death.partition(' BC') if death else None
		birth = birth.partition(' BC') if birth else None
		if   birth and not death:	return u"%s %s%s" % (born, birth[0], n(birth),)
		elif birth and death:
			if birth[1]==death[1]:	return u"%s–%s%s" % (birth[0], death[0], n(death),)
			else:					return u"%s BC–%s AD"%(birth[0], death[0],)
		elif not birth and death:	return u"%s %s%s" % (died, death[0], n(death),)
		else:						return u""

	def cmpr(a, b):	# A a subset of B
		#printu("Comparing %s to %s<br/>"%(a,b))
		if ''.join(re.split(ur'[^A-Z0-9]+', b, flags=re.U)) == a.upper(): # Initialisms
			return True
		else:
			return strip_variations(a) in strip_variations(b)
	
	# Skip if...
	if re.match(ur'^[*#]+\s*\{\{[^{|}]+\}\}$', line):
		debug('Skip parseline: %s'%line)
		return line, u''
	
	# Fix formatting of primary link
	mosfixes = [
	# ?
	(ur"^\* *(''|\")\[\[([^{|}[\]\n]+)( \([^{|}[\]\n]+\))\]\]([, ]*)\1", ur"* [[\2\3|\1\2\1\3]]\4"),
	# Expand templates (redirects handled by template_redirect() )
	(ur'\{\{(Em dash)\}\}',                               ur' \u2014 '),
	(ur'\{\{(En dash)\}\}',                               ur' \u2013 '),
	(ur'\{\{(Spaced en dash)\}\}',                        ur' \u2013 '),
	# Hyphen to en dash (html2unicode() already applied)
	(ur'(?:(?<=\W)\* *|)\b(1[6789]\d\d|2[012]\d\d|\?) *([-—–−]+|[;,. ]*†) *((?:1[6789]|2[012]|)\d\d|\?)\b(?![-]|[^[\]\n]*\]\])',   ur'\1\u2013\3'),
	# " - " to ", "
	(ur'^([^,\n]*?\]\]\'*( *\([^()\n]+\)|))( +[-—–−]+ +)(.+)$', ur'\1, \4'),
	# ?
	(ur'\(([\w\s]*)\) +\(([\w\s]*)\)(?![^[\]\n]*\]\])',   ur'(\1, \2)'),
	 # Link [[floruit|fl.]] per [[WP:APPROXDATE]]
	(ur'\[\[fl\.\]\]',                                    ur'[[floruit|fl.]]'),
	(ur'(?<=\() *\bfl\.?(?!\w|[^[\]]*\]\])',              ur'[[floruit|fl.]]'),
	# Remove bolding per [[MOS:DABENTRY]]
	(ur"'''(.*?)'''",                                     ur'\1'),
	# Remove trailing punctuation per [[MOS:DABENTRY]].  See also: mosdab_checker.js
	(ur"^([^.;]*?(?! [Ee]tc|. Sr|. Jr|. Dr|. St| Ave|. Co| Inc| Ltd|.U\.S|..\..)[^\n.,;]{4})[.,;]( or|)(?=\"? *$)", ur'\1'),
	# reformat German style dates (* 1905; † 1974) per [[MOS:DOB]]
	(ur"\((\*|born|b\.|b)(?:&nbsp;| )*(1[2-9]\d\d|20\d\d)(\)| in )(?![^[\]|]*\]\]|[^{}]*\}\})",            ur"(born \2\3"),
	(ur"\((†|died|d\.|d)(?:&nbsp;| )*(1[2-9]\d\d|20\d\d)(\)| in )(?![^[\]|]*\]\]|[^{}]*\}\})",             ur"(died \2\3"),
	# [[:lang:article]] => {{interlanguage link|article|lang}}
	(ur'^([* \w\']{1,20})\[\[:([a-z-]{2,3}):([^{|}[\]]+)(?:\|\3|)\]\]', ur'\1{{ill|\3|\2}}'),
	(ur'^([* \w\']{1,20})\[\[([^{|}[\]:|]+)\]\]([^[\]]*) \(\[\[w?:([a-z-]{2,}):([^{|}[\]|]+)(\|\4)?\]\]\)', ur'\1{{ill|\2|\4|\5}}\3'),
	# Un-subst: {{look from}}
	(ur'^(\* *)\[\[Special:Allpages/([^{|}[\]\n]+)\|.*?\]\]', ur'\1{{look from|\2}}'),
	(ur'\{\{look from\|%s\}\}'%(re.escape(self.page.title()),), ur'{{look from}}'),
	]
	# html2unicode() already applied
	# TODO add a not match against link system https://en.wikipedia.org/?diff=786852175
	for pattern, repl in mosfixes:
		line = re.sub(pattern, repl, line, flags=re.U | re.I)
		
	# TODO, improved by checking for an AfD subpage
	# WP:CSD#G11 - Blatant advert; AfD - consensus to delete
	remove_log_reason_R = re.compile(ur'''(^|\{\{|\[\[|/wiki/)(Project:|Wikipedia:|WP:|^)(AFD|HOAX|PROD|BLPPROD|Articles[_ ]+for[_ ]+deletion/[^{|}[\]]*|(CSD\#|SD\#|CSD[ _]+|CSD\]\]\ |^)(A7|G5|G11))($|[)]|\b)''', flags=re.I | re.U | re.X)

	# We now build the dictionary `links` telling us what is safe to unlink
	# This is done marking links which are or have a redirect that is a subset
	# of the `prefixes` list
	#
	links   = {}
	redlink = None
	primarylink = None
	datecat = set()
	titles_R = re.compile(ur'(?<=\[\[)[^{|}[\]\n]+?(?=\s*(?:\|.*?|)\]\])')
	titleSpec = [# TODO format pattern for ships
		('No format',	ur'^(\d+)_(architecture)$', ''),
		#('Italics',	ur'^(\d+)_(albums|books|films|live_albums|musicals|novels|operas|plays|soundtracks|television_films|video_games)$', "''"),
		('Quote',   	ur'^(\d+)_(songs|singles|short_stories|television_episodes)$', '"'),
	]
	debut_cat_suffixes = ("albums","architecture","books","films","live_albums","musicals","novels","operas","plays","poems","short_stories","EPs","songs","singles","soundtracks","television_episodes","television_films","video_games","works","manga","anime","paintings","sculptures","ships","in_spaceflight","audio_plays")
	for title in titles_R.findall(line):
		if not primarylink:
			primarylink = title
		cursor.execute("""
SELECT  page.page_namespace, page.page_title,
        rd.page_namespace,   rd.page_title,   rd_fragment,
		GROUP_CONCAT(cl_to SEPARATOR '|') as cl_to_group,
		GROUP_CONCAT(pp_value IS NOT NULL SEPARATOR '|') as cl_hidden_group,
		(SELECT pp_value FROM page_props WHERE pp_page=cl_from AND pp_propname="displaytitle") AS displaytitle,
		EXISTS (SELECT 1 FROM page_props WHERE pp_page=cl_from AND pp_propname="disambiguation") AS dabpage,
		EXISTS (SELECT 1 FROM redirect AS a JOIN page AS b ON a.rd_from=b.page_id 
		WHERE a.rd_namespace=page.page_namespace AND a.rd_title=page.page_title
		AND b.page_namespace=0 AND b.page_title=CONCAT(page.page_title, "_(disambiguation)")) AS disambiglink,
  		MAX(cl_to REGEXP ?) AS Geography,
		(SELECT rev_timestamp FROM revision WHERE rev_id=IFNULL(rd.page_latest, page.page_latest)) AS LastEdited,
		( /* Find Q for our blue link */
			SELECT GROUP_CONCAT(DISTINCT CONCAT("Q", ips_item_id) SEPARATOR " ")
			FROM wikidatawiki_p.wb_items_per_site
			WHERE ips_site_page=REPLACE(page.page_title, "_", " ")
			AND ips_site_id=TRIM("_p" FROM DATABASE())
			HAVING COUNT(DISTINCT ips_item_id) = 1
		) AS wikidata_item

FROM page
LEFT JOIN redirect   ON rd_from = page.page_id
LEFT JOIN page AS rd ON rd.page_namespace = rd_namespace AND rd.page_title = rd_title
JOIN categorylinks   ON cl_from = IFNULL(rd.page_id, page.page_id)
LEFT JOIN page AS catpage  ON catpage.page_namespace = 14 AND catpage.page_title = cl_to
LEFT JOIN page_props ON pp_page = catpage.page_id AND pp_propname = "hiddencat"


WHERE page.page_namespace=?
AND   page.page_title = ?
GROUP BY page.page_title
LIMIT 1
""", (CatPlaces, 0, canonicalTitle(title, underscore=True),), max_time=10)
		result = cursor.fetchone() or (None,)*15
		# purge empty results
		try:cursor.fetchall()
		except:pass
		# Notes:
		# displaytitle isn't updated after a move, see [[Victory (1996 film)]]
		# TODO extend wikipedia page class
		d = dict(
			ns  		= result[0],
			title		= result[1],
			rd_ns		= result[2],
			rd_title	= result[3],
			rd_fragment = result[4],
			categories	= (result[5] or '').split('|'),
			cathidden   = (result[6] or '').split('|'),
			displaytitle= result[7],
			dabpage 	= result[8],
			suffixlink  = result[9],
			geo         = result[10],
			wd_item     = result[12],


			# derived 
			redirects	= [],
			overlapping	= any(cmpr(prefix, title) for prefix in prefixes),
			# principle should be better defined, it use to be both primary and principle
			# * The '''''[[main link]]''''', description
			# * Song, performed by [[Support link]]
			principle   = line.find(title) < line.find(', ') < len(line)*2//3 or line.find(title) < 15,
			isRedirect  = result[3] != None,
			exists      = result[1] != None,
			sortkey     = None,  # TODO
			label       = '', # TODO
			lastedited  = result[11],
			interwiki   = result[1] == None and re.match(ur'^[qwsb]:|^:[a-z-]+:', title, flags=re.U), # [[:ja:北原亞以子]]
		)
		# get all redirect titles
		cursor.execute("""
SELECT page_namespace, page_title FROM page JOIN redirect ON page_id=rd_from WHERE page_namespace=0 AND rd_namespace=0 AND rd_title=?
UNION
SELECT   rd_namespace,   rd_title FROM page JOIN redirect ON page_id=rd_from WHERE page_namespace=0 AND rd_namespace=0 AND page_title=?
""", (canonicalTitle(title, underscore=True),)*2, max_time=30)
		for my, s in cursor:
			d['redirects'].append(s)
			d['overlapping'] |= any(cmpr(prefix, s) for prefix in prefixes)
		# debugging
		#print "title key: %r<br/>" % (title,)
		#print 'prefix list: ', prefixes, '<br/>'
		#print result, '<br/>'
		#print '<code>%r</code><br/>' % (d,)
		
		# Add to WikEd
		linkInfo[canonicalTitle(title, underscore=True)] = {
			"updated":  True,
			"redirect": d['isRedirect'],
			"target":   d['rd_title'],
			"missing":  not d['exists'],
			"sortkey":  d['sortkey']
		}
		
		links[title] = d
		if not d['interwiki']: # [[:ja:北原亞以子]]
			if not redlink and not d['exists']:
				if not title.startswith('Special:'): # [[Special:PrefixIndex/...]]
					redlink = title
	
	def formatLink(m):
		# Test cases
		# [[A (b)|"A" (b)]] DONE
		# "[[A]]"			DONE
		# "[[A (b)|A]]"		
		# [[A (b)|A (b)]]
		# [[A (b)|"A" (''b'')]] DONE
		# [[The Dismissal (Dynasty)#ep137|]] => [[The Dismissal (Dynasty)]] DONE
		# [["Episode" (''Doctor Who'' series)]] ...?

		mark = m.group(4) or m.group(1) # " or ''
		title  = m.group('title') # key in links dictionary
		target = canonicalTitle(title, underscore=True)
		label  = "%s%s%s"%(m.group(1), m.group('label') or m.group('title'), m.group(1),)
		new_label = label
		linkinfo = links.get(title)

		# FIXME remove # hack, problems on [[Principles of art#Unity]] (redirects to Art)
		if target=="": # [[#section link]]
			return m.group()
		elif not linkinfo:
			# Program screwed up somewhere
			error("%s\n\nDoes not contain %s \n %r" % (repr(links).replace('{', '{\n').replace(',', ',\n'), m.group(), title, ))
			raise KeyError("%r missing" % title)
			return m.group()
		elif linkinfo['rd_title'] or '#' in title or linkinfo['title']==None:
			# Skip these as {{DISPLAYTITLE:}} or Category matching are 
			# incorrect.  This is probably not necessary with good title comparer.
			# TODO [[Category:Redirected_episode_articles]]?, links->categories contains target page
			rd_title    = linkinfo['rd_title']
			rd_fragment = linkinfo['rd_fragment']
			if '#' in title:
				if rd_fragment == title.split('#', 1)[-1]:
					title = title.split('#', 1)[0]
				warn("[[%s]] links to a section" % (target.replace('_', ' '),))
			elif linkinfo['rd_title']:
				debug("[[%s]] redirects to [[%s]]" % tuple(t.replace('_', ' ') for t in (target, rd_title+('#'+rd_fragment if rd_fragment else ''),)))
			else:
				# TODO add separate flag for red links, see above with Special:...
				printu(u'<div class="info debug">'+CreateLink(target)+u' is a red link</div>')
		else:
			displaytitle = ''
			if linkinfo['displaytitle']:
				# Use {{DISPLAYTITLE:}} whenever available
				if mark == "''":
					mark = ''
				displaytitle = wikipedia.html2unicode(linkinfo['displaytitle']).replace('<i>', "''").replace('</i>', "''")
				# First lowercase issue
				firstletter = re.compile(ur"^((''|</?\w+[^<>]*>| )*)(.)", flags=re.U)
				if firstletter.search(label).group(3).islower():
					displaytitle = firstletter.sub(lambda m: m.group(1) + m.group(3).lower(), displaytitle)
				if '<' in displaytitle or '>' in displaytitle:
					debug("{{DISPLAYTITLE:%(displaytitle)s}}" %linkinfo)
			# Otherwise fall back to category match
			for rulename, pattern, c in titleSpec:
				if displaytitle and c=="''":
					continue
				for cat in linkinfo['categories']:
					if re.search(pattern, cat, flags=re.U):
						if mark and mark != c:
							warn(u"Formatting conflict (%s \u2192 %s) with [[Category:%s]]" % ('quote' if mark=='"' else 'italics', rulename.lower(), cat,))
						else:
							mark = c
							debug("%s rule %r matches [[Category:%s]]" % (rulename, pattern, cat,))
			# Clobber label if...
			if displaytitle and mark == "''":
				new_label = displaytitle
			else:
				(subject, qualifier) = re.search(ur'^(.+?)([ _]*\([^()]+\)|)$', displaytitle if displaytitle else title, flags=re.U).groups()
				new_label = ''.join((mark, subject, mark, qualifier)).replace('_', ' ')
		
		def test(s):
			" Strip all wiki syntax "
			s = canonicalTitle(re.sub(ur"''|'''|\"|</?\w+\b[^<>]*>", '', s, flags=re.U))
			# Remove diacritics/accents marks
			s = u''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
			# Own substitution table
			for c1, c2 in replacementset.iteritems():
				s=s.replace(c1, c2)
			# Remove punctuation and duplicate letters
			s = u''.join(c for i, c in enumerate(s) if c not in ' !"\',-.:;?' and (i==0 or c!=s[i-1]))
			return s
		# XXX how is [[w (x), y (z)]] handled?
		x = re.compile(ur'^(.+?)([ _]*\([^(\n)]+\)|)$', flags=re.U)
		(o_subject, o_qualifier) = x.search(label).groups()
		(n_subject, n_qualifier) = x.search(new_label).groups()
		(t_subject, t_qualifier) = x.search(target).groups()
		#debug("\ntarget: <%s>\nnew_label: <%s>"%(target,new_label,))
		#debug('\n'.join(["%s <%s>"%(varname, locals().get(varname)) for varname in "t_subject t_qualifier o_subject o_qualifier n_subject n_qualifier target displaytitle".split() ]))
		
		if test(o_subject) == test(n_subject):
			# Copy qualifier styling
			# XXX Hack to copy extra formatting from displaytitle while keeping original formatting
			if test(o_qualifier) == test(n_qualifier) and len(n_qualifier) <= len(o_qualifier):
				n_qualifier = o_qualifier

			# [[Flash (Chuck)|Flash (''Chuck'']]
			if '#' not in title and test(n_subject) == test(t_subject):
				if linkinfo['principle']:
					if len(links) > 1:
						printu(u'<div class="info debug">'+CreateLink(title)+u' is the principle link</div>')
					# If the target qualifier is not the same 
					# e.g. (''Buffy'' episode) => (Buffy: The Vampire Slayer episode)
					if test(n_qualifier) != test(t_qualifier):
						n_qualifier = t_qualifier.replace('_', ' ')
				else:
					# TODO 
					if m.start() > re.search(ur'(\[\[.*?\]\]|),|', line, flags=re.U).end():# and linkinfo['overlapping']:
						n_qualifier = ''


			new_label = u"%s%s" % (n_subject, n_qualifier)
			repl = u'[[%s]]'%new_label if u'#' not in title and target==canonicalTitle(new_label) else u'[[%s|%s]]'%(title, new_label)
			# TODO [[lower|"Lower"]] => "[[Lower]]"
			repl = re.sub(ur"\[\[(.*?)\|(''|\")([^{|}[\]\n]+)\2\]\]", ur'\2[[\1|\3]]\2', repl, flags=re.I | re.U)
			repl = re.sub(ur"\[\[( *([^{|}[\]]+?) *)\| *\2 *\]\]",    ur'[[\1]]',        repl, flags=re.I | re.U)
			#TODO rename keys when changing titles 
			return repl
		else:
			return m.group()
	
	# \g<title> needs to be the same as the dictionary building one
	line = re.sub(ur"(''|\"|)\[\[(?P<title>[^{|}[\]\n]+?)[ |]*(?P<label>(?<=\|)(''|\"|).*?|)\]\],??\1", formatLink, line)
	
	if redlink:
		# Add debuggin context
		htmlout('<div class="debug"><samp>')
		wikipedia.output(line, newline=False)
		htmlout('</samp></div>')

		setindexcategory = sicatlang.get(self.site.dbName()+'_p', ("",))
		
		# Experiemental wikidata
		# Find English transliterations: e.g. https://www.wikidata.org/wiki/Q11653946
		cursor.execute("""
SELECT CONCAT("Q", ips_item_id), lang, ips_site_id, ips_site_page, COUNT(DISTINCT lang) AS ips_cnt
FROM wikidatawiki_p.wb_items_per_site
LEFT JOIN meta_p.wiki ON dbname = ips_site_id AND family = "wikipedia" AND dbname!=TRIM("_p" FROM DATABASE())
WHERE ips_site_page=REPLACE(?, "_", " ")
GROUP BY ips_item_id
""", (canonicalTitle(redlink, underscore=False),))
		otherwiki = cursor.fetchall()
		ips_item_id = None
		if cursor.rowcount > 1:
			warn('More than one row returned')
			print otherwiki
		elif cursor.rowcount:
			ips_item_id, lang, ips_site_id, ips_site_page, ips_cnt = otherwiki[0]
			ill_p2 = lang if lang and ips_cnt < 10 else 'WD=%s' % ips_item_id
			#ill_p3 = 
			line = re.sub(ur'\[\[(%s)\]\]' %  wikilinkregex(redlink), ur'{{ill|\1|%s}}' % (ill_p2,), line, 1, flags=re.U)

		if not ips_item_id: # TODO Merge with above query, split WD_item getting and {{ill}} thingy
			cursor.execute("""
/* Exact term match, [[Richard Maxwell Fox]] (Q26328565) */
SELECT GROUP_CONCAT(DISTINCT term_full_entity_id SEPARATOR " ")
FROM wikidatawiki_p.wb_terms
WHERE term_text      = REPLACE(?, "_", " ")
AND term_language    = REPLACE((SELECT DATABASE()), "wiki_p", "")
AND term_entity_type = "item" 
HAVING COUNT(*) = 1
""", (canonicalTitle(redlink, underscore=False),))
			if cursor.rowcount:
				ips_item_id = cursor.fetchall()[0][0]
		if ips_item_id:
			birth, death, desc = wikidata_description(site, ips_item_id, lang=self.site.language())
			debug("[[Wikidata:%s]] (born %s; died %s): %s"%(ips_item_id, birth, death, desc))
			if re.search(ur'^\W+\{\{ill\|[^{|}[\]]+\|[^{|}]*\}\}(?: \([\w\s]*[\d\u2013]*\)|)\W*$', line):
				if birth or death:
					biotext = yearRange(unicode(birth.year) if birth else None, unicode(death.year) if death else None)
					if biotext not in line: 
						line += u' (%s)' % biotext
				if desc:
						line += u', %s'%desc
			else:
				debug("Could not use description %r / %r"% (line, desc,))
	

		cursor.execute("""/* dabfix red backlinks */
SELECT page_namespace, page_title,  page_is_redirect, 
  EXISTS (SELECT 1 FROM categorylinks WHERE cl_from=page_id AND cl_to IN ("""+','.join(("?",)*len(setindexcategory))+""")) AS si,
  EXISTS (SELECT 1 FROM page_props WHERE pp_page=page_id AND pp_propname="disambiguation") AS dab
FROM page
JOIN pagelinks ON pl_from=page_id
WHERE pl_namespace=? AND pl_title=?
ORDER BY page_namespace, page_title
""", setindexcategory+(0, canonicalTitle(redlink, underscore=True), ), max_time=30)
		results = cursor.fetchall()
		blcount = cursor.rowcount # avoid overide
			
		# TODO create summary from page with highest concentration of red links
		if blcount:
			printu('<p class="debug">The following %s to <b>%s</b>:</p>' % (CreateLink("Special:WhatLinksHere/%s"%redlink, "pages link"), CreateLink(redlink),) )
			printu('<ul class="debug %s">' % ('columns' if blcount>10 else '',))
			for ns, title, redirect, sipage, dab in results:
				printu(u'<li>%s%s</li>' % (
					CreateLink(wikipedia.namespaces[ns]+':'+title if ns else title),
					u' <b>(redirect page)</b>' if redirect else u' <b>(disambiguation)</b>' if dab else u' <b>(set-index article)</b>' if sipage else u'',
				))
			printu('</ul>')
		else:
			warn("No pages link to [[%s]]" % (redlink,))

		if any(ns for (ns, title, redirect, sipage, dab) in results if ns<0):
			wikipedia.output("Special page")
		else:
			# Display information about deletion
			cursor.execute('''
SELECT DATE_FORMAT(log_timestamp, "%H:%i, %d %b %Y"), IFNULL(user_name,''), comment_text AS log_comment
FROM logging_logindex
LEFT JOIN comment ON comment_id = log_comment_id
LEFT JOIN user ON user_id=log_user
WHERE log_namespace=? AND log_title=? AND log_type="delete"
ORDER BY log_timestamp DESC
''', (0, canonicalTitle(redlink, underscore=True),), decode_errors='ignore', max_time=10)
			
			if cursor.rowcount:
				print '<div class="mw-warning-with-logexcerpt">'
				print '<p class="debug">Deletion log:</p>'
				print '<ul>'
			m = None
			for log_timestamp_text, log_user_text, log_comment, in cursor:
				m = m or remove_log_reason_R.search(log_comment)
				printu(u'<li class="mw-logline-delete">%s %s deleted %s (<span class="comment">%s</span>)</li>' % (
					wikipedia.escape(log_timestamp_text),
					CreateLink("User:%s" % log_user_text, log_user_text),
					CreateLink(redlink),
					wikify(re.sub(
						r'(\[\[)?%s(?(1)\)*\]\])'%re.escape(wikipedia.escape(m.group()).strip('[]{} ')),
						ur'<b>\g<0></b>',
						wikipedia.escape(log_comment)
					), escape=False) if m else wikify(log_comment),
				))
			if cursor.rowcount:
				print '</ul>'
				print '</div>'
			
			if not links[redlink]['principle']:
				printu('<div class="info debug">'+CreateLink(redlink)+' is a principle red link</div>')
			elif not any(1 for (ns, title, redirect, sipage, dab) in results if ns==0 and sipage==0 and dab==0):
				# No links, should we remove it?
				
				# Check Wikidata
				wd_site = wikipedia.Site('wikidata', 'wikidata')
				cursor.execute('''
SELECT 1
FROM wikidatawiki_p.wb_items_per_site
WHERE ips_site_page=REPLACE(?, "_", " ")
  AND ips_site_id IN (SELECT dbname FROM meta_p.wiki WHERE dbname != ?)
''', (redlink, site.dbName(),), max_time=10)
				searcher = redlink.replace('_', ' ')
				# No Wikidata interlangs, try different searcher
				searcher = '"%s"'%searcher if cursor.rowcount else re.sub(r'([^(]+)(.*)', r'"\1" \2', searcher)
				# TODO look for "sectiontitle" {"ns":0,"title":"List of Samurai Champloo characters","sectiontitle":"Kariya_Kagetoki"}
				wd_results = list(api_search(wd_site,   searcher, limit=100))
				wp_results = list(api_search(self.site, searcher, namespaces=range(0,16), limit=100))
				print '<div>'
				for x in wp_results:
					if "#" in x:
						printu('<div>'+CreateLink(x.replace('_', ' '))+'</div>')
				if m and "{{interlanguage link" not in line and "{{ill|" not in line: # matches remove_log_reason_R and no interlanguage
					line = ""
					printu(u'<div class="delete"><b>Removing '+CreateLink(redlink)+u'</b> Deletion log match: '+wikipedia.escape(m.group().strip('[]{}'))+u'</div>')
				#elif redlink.strip('#* [].:;') == line.strip('#* [].:;') != "": # no description, Avoid * [[***]].
				#	printu(u'Removing red link <b>'+CreateLink(redlink)+'</b> per '+CreateLink('MOS:DABRL')+': No article links to it')
				elif len(wd_results) == 0 and len(wp_results) <= 1 and line.count(']]') <= 1:
					# Not mentioned anywhere, no supporting links
					line = ""
					printu(u'<div class="delete"><b>Removing '+CreateLink(redlink)+'</b>: '+CreateLink('MOS:DABMENTION', 'No mentioned in Wikipedia')+' or Wikidata</div>')
				else:
					# TODO add branch to comment out links
					line = "%s"%line
					printu(u'Consider removing <b>'+CreateLink(redlink)+'</b> per '+CreateLink('MOS:DABRL')+'.')
				
				searcher = wikipedia.urllib.quote(searcher.encode('utf-8'))
				htmlout('Tools: <span class="toollinks"><a href="%s">WikiBlame</a>, <a href="https://%s%s">What links here (%d)</a>, <a href="%s">Wikipedia search (%d)</a>, <a href="%s">Wikidata (%d)</a>, <a href="%s">Bing</a>, <a href="%s">DuckDuckGo</a>, <a href="%s">Google</a> (<a href="%s">News</a>, <a href="%s">Scholar</a>) </span>', (
					#'http://wikipedia.ramselehof.de/wikiblame.php?searchmethod=lin&limit=30&force_wikitags=on&article=%s&needle=%s' % (
					'http://wikipedia.ramselehof.de/wikiblame.php?force_wikitags=on&article=%s&needle=%s' % (
						self.page.title(asUrl=True),
						redlink.replace('_', ' '),
					),
					self.site.hostname(),
					self.site.nice_get_address("Special:WhatLinkshere/%s"%redlink),
					blcount,
					'https://en.wikipedia.org/w/index.php?search=%s&profile=all' % searcher,
					len(wp_results),
					'https://www.wikidata.org/w/index.php?search=%s' % searcher,
					len(wd_results),
					'https://www.bing.com/search?q=%s%%20-wikipedia' % searcher,
					'https://www.duckduckgo.com/?q=%s%%20-wikipedia' % searcher,
					'https://www.google.com/search?q=%s%%20-wikipedia%%20-wikimedia' % redlink.replace('_', '-'),
					'https://www.google.com/search?q=%s&tbm=nws' % searcher,
					'https://scholar.google.com/scholar?q=%s' % searcher,
				))
				#if line == "":
				print blame(self.page, added_text = redlink)
				print '</div>'
			elif cursor.rowcount == 0:
				debug('[[%s]] was never created' % (redlink,))
			else:
				debug("%s pages link here"% (blcount,))
		
	else: # not redlink
		# Per MOS:DAB, we unlink non-relevant links
		# TODO This should be possibly move above the link removal code
		if not links:
			pass
		elif not any(link['overlapping'] for link in links.itervalues()):
			debug("No overlap with "+EnglishJoin(["[[%s]]"%key for (key, link) in links.iteritems() if not link['overlapping']]))
		else:
			if len(links) > 1 and self.page.is_disambig: # FIXME some bug on [[CB]] on line  [[concrete masonry unit]] 
				def f(match):
					t = match.group('title').strip()
					# TODO Avoid delinking interwikis for redlinks
					if t in ('floruit', 'Floruit', 'fl.', 'Fl.'):
						del links[t]	# Pretend it does not exist
						return match.group()
					elif t.lower().startswith(('wikt:', 'wiktionary:')):
						# Keep wiktionary links
						del links[t]	# Pretend it does not exist
						return match.group()
					#TODO Add interlanguage support
					#elif 
					elif t not in links:
						# [[again]] then [[again]] (already deleted)
						return match.group('label') or match.group('title')
					elif links[t]['overlapping']:
						return match.group()
					else: 
						# Unlink text
						del links[t]
						return match.group(2) or match.group(1)
				line = re.sub(ur'\[\[(?P<title>[^{|}[\]\n]+?)[ |]*(?P<label>(?<=\|).*?|)\]\]', f, line)
				# FIXME re-run matching algorithm?
				if primarylink not in links:
					primarylink = links.keys()[0] if links else None
		
		# Break down line into parts
		# old version:
		ur'''^
(?P<subject>(?:
     [^'"[\],(){}]
    |,\ [^[\]|(){}, ]*(?=,)
    |\[\[[^[\]]+\]\]
    | "[^'[\],{}]+"
    |''[^'"[\],{}]+''
    |"
    |''
    |'(?!')
)+)
    (?P<spacer1>(?:\ -|[-,:]\ |\s)*?)
(?:\(+(?P<meta>[^(\n)]+)\)+)?
    (?P<spacer2>[-,.: ]*)
(?P<description>.*)
'''
		# ^^^ Old code for reference
		# FIXME allow [[title]]'s IATA code
		mline = re.search(ur'''
(?P<subject>
 ^(?:
  # subject [[title]] or second title
  (?:^ [;:]* [#*]+ :* \s* [^'"[\]{|},()]{0,40} # 20/30 char title + 10 chars for "and with"
  | \ or\  
  )
	(?:
	    (?:"|'')*
		  \[\[ [^[\]]+ \]\]'??\w*
		(?:"|''|'(?!'))*

	|   "[^'"[\]{|},]+"
	|"?''[^'"[\]{|},]+ (?:'\w*)?? ''"?
    |    (?<=[#*]) [^'"[\]{|},()\-\u2013\u2014]{5,20} $ # Only text on line
    |    [^'"[\]{|},()]+
		# Village, Country???
		(?: ,\s* [^\W0-9a-z] [^[\]{|}(),\s]+ |)
		(?= [-,:]\s | \s\(.*?\) )
	)
	(?:[^'"[\]{|},()]{0,40}(?=[-,:]\s))? # or Other Name
 )+
)
	(?P<spacer1>(?:\ -]|[-,:]\ |\s)*)
(?:\(+(?P<meta>[^(\n)]+)\)+)?
	(?P<spacer2>[-,.: \u2012-\u2015]*)
(?P<spacer3> \bis\b | \bwas\b |)
(?P<description>.*)
''', line, flags=re.X | re.U)
		newDesc = False
		if mline:
			htmlout('<div class="debug">%s</div>' % ''.join('<samp title="%s">%%(%s)s</samp>'%(k, k) for k in sorted(mline.groupdict(' ').keys(), key=mline.re.groupindex.get)), mline.groupdict(' '))
			subject, spacer1, meta, spacer2, spacer3, description = mline.groups()
			# don't add ]], in place / ]], from article
			description = "%s%s"%(spacer1 if spacer1.strip() else spacer2 if spacer2.strip() else " " if description.startswith(('in ', 'from ', 'for ', 'of ', 'by ', 'or ', 'also known as ')) else ", " if description else '', description)
		else:
			subject, meta, description = line, '', ''
			error('Unable to parse: %s'%line)
		if primarylink in links and links[primarylink]['wd_item']:
			htmlout('<div class="debug"><a href="http://www.wikidata.org/wiki/%s">%s</a></div>', (links[primarylink]['wd_item'],links[primarylink]['wd_item'],))
			
		if len(links)==1 and not links[primarylink]['dabpage'] and not links[primarylink]['rd_title']:
			# FIXME
			# Comics characters introduced in 1977
			# 2006 comic debuts
			# https://en.wikipedia.org/w/index.php?title=Firefly_(disambiguation)&diff=424199591&oldid=424193235
			def isExact(s):
				return s in (None, "", "?") or s.isdigit()
			debut = []
			birth = None
			death = None
			biotext = None
			date = []

			### print "%r"%(links,)
			# category regex for ", a X blah"
			# TODO Handle the case when all we have are missing dates
			descript_R = re.compile(ur'^([ ,-]*)(a |an |\b(?=album |building |book |comic book |film |musical |novel |novella |opera |play |short story |single |song |soundtrack |story |video game |manga |anime |sculpture |painting ))')
			for cat in links[primarylink]['categories']:
				# FIXME Less hardcoding
				#len('1570s births')=12
				if   cat.endswith("_births") and len(cat)<=12: 	birth = getYear(cat) or birth
				elif cat.endswith("_deaths") and len(cat)<=12:	death = getYear(cat) or death
				elif cat=="Living_people":          death = ""
				elif cat=="Missing_people":         death = death or ""
				elif cat=="Possibly_living_people": death = ""
				elif cat=="Year_of_death_missing":  death = "?"
				elif cat=="Year_of_birth_missing":  birth = "?" 
				elif cat=="Year_of_death_unknown":  death = "?"
				elif cat=="Year_of_birth_unknown":  birth = "?"
				elif cat=="Year_of_birth_uncertain":birth = "?"
				elif cat=="Year_of_death_uncertain":death = "?"
				else:
					a = cat.partition('_')
					if a[0].isdigit() and a[2] in debut_cat_suffixes:
						debut.append(a[0])
					else:
						# Highlist good dates in category listings
						vague_date = re.search(ur'(_|^)(1\d\d\d|20[0-4]\d)(_|$)', cat)
						if vague_date and not re.search(r'(^Article|^Use|^Wikipedia_articles|^Wikipedia_pages)', cat):
							date.append(vague_date.group(3))
							datecat |= set([cat])
			
			# Format Date of Birth (DOB) info
			if birth!=None or death!=None:
				current_year = time.gmtime().tm_year
				# People
				if birth and birth.isdigit() and 1600 < int(birth) < current_year - 125:
					# Mark people older than 125 as death data unknown (1600 is arbitrary)
					death = death or '?'
				if birth=='?':
					# (died 1598) and (?-2015) MoS is unclear about missing birth years.
					# We'll assume if they died recently that the information just hasn't been sourced
					if death in ('', '?', None):
						# Avoid (?-?) or (born ?), clear 'em
						birth = ''
						death = ''
					elif 'BC' in death:
						pass
					elif int(death.replace('s','').replace('\'','')) < current_year - 10:
						# A hard cutoff of 1996-2002 when newspapers went online with searchable
						# archives seemed like a good demarcation point, if they weren't going 
						# bankrupt since 2008 and shuttering their archives
						birth = '' 
					else: 
						#raise "Bad year"
						pass
				if not birth and death=='?': # 17th-century births => '', Year of death missing => '?'
					death = ''
				biotext = yearRange(birth, death, "born", "died")
				debug('Lifespan: %s' % (biotext or 'Living as of %s' % (links[primarylink]['lastedited'] or ' N/A')[0:4],))
				
				# Add improved suggestions
				if mosdabbot: # Module exists
					mosdabbot.lifespan_cache[primarylink] = biotext
			
			# Subject (Metadata), Description
			#if (line.find(primarylink) < 15 or (line.find(primarylink) < line.find(', ') < len(line)*2//3)) and '#' not in primarylink:
			if links[primarylink]['principle'] and '#' not in primarylink:
				# Add description if missing
				if not description.strip():# and re.match(ur'^.{0,8}\[\[.*\]\].{0,3}$', subject):
					if links[primarylink]['geo']:
						debug("Geographical places like [[%s]] don't need descriptions" % primarylink)
					elif links[primarylink]['dabpage'] or links[primarylink]['rd_fragment']:
						pass
					else:
						description = make_description(self.site, primarylink)
						newDesc = True
			

				if birth!=None or death!=None:
					if biotext and biotext not in primarylink:
						if not meta:
							meta = biotext
						elif isExact(birth) and isExact(death): # Avoid century and decade approximates overriding
							meta = re.sub(ur'''
(
	(\b(born|born in|b|died|d)\b([. \u00A0]|&nbsp;)*|[*†]([. \u00A0]|&nbsp;)*|)
	(\b(c|ca|circa|about|aft|after|before)\b[. ]*|)
	(([0-3]?[0-9][ ]|)\b(Jan|Feb|Mar|May|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z.]*([ ][0-3]?[0-9]|)[, ]*|)
	[\d?]+
	((?:st|nd|rd|th)[ -]century|)
	([ ]*(CE|BCE|BC|AD)|)
	([ ]*([\u002D\u2013\u2014]|&\w+;|[; ]*(?=†)|\ to\ )[ ]*|)
){1,2}''', biotext, meta, 1, flags=re.I | re.X | re.U)
							# Add to if failed
							if biotext not in meta:
								meta = "%s, %s"%(meta, biotext,)
						else:
							# XXX Avoid our 1660s-1720s until we get something that can get 1664/5-c. 1723 working
							biotext = ''
							pass
						# remove lifespans
						#description = description.replace(biotext, '').replace(', ()', '').replace(' ()', '').replace(', , ', ', ')
						description = re.sub(r'(,? \(|)?%s(\)|)'%(re.escape(biotext),), '', description).replace(', , ', ', ')
					# Do NOT include these per [[MOS:DAB#People]]
					description = re.sub(ur'^([-,: ]*)\b(?:a |an |the |is |was )*', ur'\1', description, flags=re.I)
				elif debut:
					m_has_year = re.search(ur'\b\d{3,4}\b', subject+description)
					if not m_has_year:
						# Use the most frequent year
						description = descript_R.sub(ur'\1a %s '%max(set(debut), key=debut.count), description, 1)
					if not any(year in (subject+description) for year in debut):
						if m_has_year:
							warn("[[%s]]: Conflicting year?: %s"%(primarylink, EnglishJoin(debut, distinct=True)))
						else:
							warn("[[%s]]: Missing year?: %s"%(primarylink, EnglishJoin(debut, distinct=True)))
				else:
					pass
		
		line = subject.strip()
		if meta:
			line += " (%s)"%meta.strip()
		if description:
			line += description
			if newDesc:
				print '<script type="text/javascript">AddedDescription(%s, %s);</script>' % (
					wikipedia.jsescape(primarylink),
					wikipedia.jsescape(description),
				)
		line = line.rstrip(', ')
			


	# Make clear that it's a disambiguation link by appending "(disambiguation)"
	def toDisambiguation(m):
		try:
			mylink = links[m.group(1)]
		except KeyError:
			return m.group()
		if not mylink['dabpage']:
			return m.group()
		elif not mylink['suffixlink']:
			if not m.group(1).endswith("(disambiguation)") and not mylink['isRedirect']:
				# Doesn't exists; suggest creating it
				printu(u'<p>Please create <b>%s</b></p>' % CreateLink(m.expand(ur'\1 (disambiguation)'), className="external link", action='edit&preload=Template:R_to_disambiguation_page/preload&summary=Redirected%20page%20to%20%5B%5B'+m.group(1).replace(u'_', u' ')+'%5D%5D&preview=yes', addAttribute=' target="_blank"'))
			return m.group()
		elif mylink['principle'] and (not m.group(2) or m.group(1)==m.group(3)):
			return m.expand(ur'[[\1 (disambiguation)]]')
		else:
			return m.expand(ur'[[\1 (disambiguation)|\3]]' if m.group(2) else ur'[[\1 (disambiguation)|\1]]')
	line = re.sub(ur'\[\[([^{|}[\]<\n>]+)(\|(.*?)|)\]\]( *\(disambiguation\)|)', toDisambiguation, line, flags=re.U)
	
	extra = u''
	if not redlink and primarylink and 'categories' in links[primarylink]:
		# Print categories to 'close' function
		extra = u'<div class="catlinks debug">Categories: %s</div>'%' | '.join(CreateLink("Category:"+cat, cat.replace('_', ' '), addAttribute=' title="Is this a good date category to add to the whitelist?" style="font-weight:bold;"' if cat in datecat else "") for cat,hidden in zip(links[primarylink]['categories'],links[primarylink]['cathidden']) if hidden!='0')
	return line, extra






class Robot(object):
	def __init__(self):
		self.page   = wikipedia.MyPage
		self.site   = self.page.site()
		self.cursor = toolsql.getConn(self.site.dbName()).cursor()
		global site;   site   = self.site
		#global cursor; cursor = self.cursor
		cursor = self.cursor
		self.html_json = None
		
		self.redirects = []
		self.target = None # Redirect target 
		self.existingLinks = [(self.page.namespace(),self.page.title(underscore=True),)]
		self.prefixes = set()
		self.parselinecounter = 0
		self.text   = ''
		self.preview = False
		self.add_section = {}
		self.primelinks = {}
		self.summaryflags = {}
		# Language constants
		self.hatnotes = ("Hatnote",)
		self.usecommonfixes   = wikipedia.SysArgs.get("commonsfixes") != 'no' # '#' in self.text
		self.setindexcategory = sicatlang.get(self.site.dbName()+'_p', ("",))
		
		# XXX Legacy: self.disambiguationcategory
		if self.site.dbName() == 'enwiki':
			self.disambiguationcategory = ("All_set_index_articles", "All_disambiguation_pages", )
		else:
			with toolsql.getConn('enwiki') as encurs:
				encurs.execute("""
SELECT ll_title
FROM page JOIN langlinks ON ll_from=page_id
WHERE page_namespace=14 AND page_title IN ("All_disambiguation_pages", "Disambiguation_pages") AND ll_lang=?
""", (self.site.dbName()[:-4], ))
				self.disambiguationcategory = tuple(cat[cat.index(':')+1:] for (cat,) in encurs.fetchall())
				if not any(self.disambiguationcategory):
					self.disambiguationcategory = ("",)
					error("No disambiguation category found!")
		

	def __repr__(self):
		return 'dabfix.py '+' '.join(tuple("-%s:%s" % t for t in wikipedia.SysArgs.items()))

	def set_summary(self, flag, performed_on):
		if flag not in self.summaryflags:
			self.summaryflags[flag] = []
		self.summaryflags[flag].append(performed_on)
	def edit_summary(self):
		if 'create' in self.summaryflags:
			return "Creating disambiguation using [[tools:~dispenser/cgi-bin/dabfix.py|Dabfix]]"
		elif 'redirect' in self.summaryflags:
			return "Converting to disambiguation using [[tools:~dispenser/cgi-bin/dabfix.py|Dabfix]]"
		else:
			return "Cleanup per [[WP:MOSDAB]] using [[tools:~dispenser/cgi-bin/dabfix.py|Dabfix]]"
	def addsection(self, section_head, section_text):
		# Head
		if section_head in self.add_section:
			raise KeyError('Section titles must be unique')
		# Smart level 3 header
		#repl = u"\n== %s ==\n%s\n" if re.search(ur'(?m)^==[^=]+==$', self.text) else u"\n=== %s ===\n%s\n"
		repl = u"\n== %s ==\n%s\n"
		# Body 
		section_text = section_text.strip()
		if not section_text:
			return
		#
		self.text = re.sub(ur'''(?= (\n
			# Avoid empty section (e.g. == References ==\n {{reflist}}) 
			(=+ .+ =+ \s*)? 
			# Insert section before the last template
			\{\{(?!subst:)[^{}]+\}\} \s*
			)+
			# Categories
			[^{}]*? \Z )
			# Fallback to end
			| \Z''',
			repl % (section_head, section_text,), 
			self.text, 
			count=1,
			flags=re.X | re.M
		)
		# Add so we can remove it
		self.add_section[section_head] = section_text
		debug('Adding %r section (%d lines)' % (section_head, section_text.count('\n') + 1, ))

	def parseline(self, match):
		if self.parselinecounter: # skip first
			print '<hr style="margin:1em 0;" />'
		self.parselinecounter += 1
		
		printu(u'<div class="parseline">')
		line = wikipedia.html2unicode(match.group())
		line = re.sub(ur'\s+', ' ', line, flags=re.U)
		line = line.rstrip()
		
		# Change bullet style without dirtying diffs ( > 3/5 or < 1/5)
		if  not 0.60 > self.bullet_space_ratio > .20:
			# Add spaces (per [[MOS: ]]) or remove to keep uniform
			line = re.sub(ur'^([#*]+:*) *', ur'\1 ' if self.bullet_space_ratio > 0.5 else ur'\1', line, flags=re.M)
	
		# music specific fixes
		#pline= re.sub(ur"^[*]([^,\n]*),(['\"]*) *a? *(song|signle) by ([\w [\]]* band |)(?P<group>[\w [\]]+)(?<!'s) from (his|her|their)(first |second |third |)(?P<year> \d+|)(?P<album> album .*?) *$",
		#              ur"\1\2, a song on \g<group>'s\g<year>\g<album>", pline, flags=re.U | re.I | re.M)
		try:
			pline,extra = parseline(self, self.cursor, line, self.prefixes)
		except toolsql.QueryTimedOut as (errno, strerror, extra):
			printu(u'</div>')
			error(u'Routine parseline(): Database query timed out (%d seconds)\nLine:%s' % (self.cursor.elapsedtime, line))
			return match.group()
		pline = pline.rstrip()
		
		# If description / lifespan are the only differences, that has already been printed
		if pline != line and not pline.startswith(line):
			print '<div class="debug linediff">'
			wikipedia.output(u"\03{lightred}%s\03{default}"%match.group().rstrip())
			wikipedia.output(u"\03{lightgreen}%s\03{default}"%pline)
			print '</div>'
		
		printu(extra)
		printu(u'</div>')
		
		# Remove line and \n
		if pline == "": 	return ""
		# Use original to avoid trailing space removal from breaking the diff
		elif pline == line:	return match.group()
		# Modify line
		else:             	return pline + '\n'
		
	def skipredirect(self, match):
		return skipredirect(self.cursor, match, self.prefixes)

	def addprefix(self, t):
		if t: # skip blank
			iEnd=t.find('_(')
			if iEnd==-1: iEnd=None
			self.prefixes.add(t[:iEnd])

	def cleanprefixes(self):
		self.prefixes |= set([s.replace('_&_', '_and_') for s in self.prefixes])
		self.prefixes |= set([s.replace('_and_', '_&_') for s in self.prefixes])
		x = ('The_', 'A_')
		self.prefixes = set([(b.replace(a, '', 1) if b.startswith(a) else b) for a in x for b in self.prefixes])
		self.prefixes |= set([a+b for a in x for b in self.prefixes])

	def getprefixes(self):
		print '<div class="debug">' 
		heading(2, "Inbound links")
		self.addprefix(self.page.title(underscore=True))
		self.cursor.execute("""
SELECT page_title
FROM page
JOIN redirect ON page_id=rd_from
WHERE page_namespace=0 and rd_namespace=? and rd_title=?
""", (0, self.page.titleWithoutNamespace(underscore=True),))

		if self.cursor.rowcount:
			print '<ul class="columns">' if self.cursor.rowcount>10 else '<ul>'
			for (redirect,) in self.cursor:
				self.redirects.append(redirect)
				printu("<li>%s (redirect)</li>"%CreateLink(redirect))
				self.addprefix(redirect)
			print "</ul>"
		else:
			print '<p>There are no redirects</p>'
		if len(self.prefixes) >= 2: # XXX it complains: Unknown column 'x.title' in 'field list'
			self.cursor.execute("""/* dabfix */
SELECT x.title
FROM (%s) AS x
LEFT JOIN page ON page_namespace=0 AND page_title=x.title
WHERE page_id IS NULL
""" % ' UNION '.join(("SELECT ? AS title",)*len(self.prefixes)), tuple(t[0:1]+t[1:].lower() for t in self.prefixes))
			for (t,) in self.cursor:
				self.addprefix(t)
		info('Prefixes used for matching: %s' % (EnglishJoin(sorted(self.prefixes)),))
		print '</div>'
		
		# Pre-materialize sub-query for use in Blue and Red link finder
		self.cursor.execute("""
/* List of links on the page */
SELECT IFNULL(rd_title, pl_title)
FROM page
JOIN pagelinks       ON pl_from = page.page_id
LEFT JOIN page AS rd ON rd.page_namespace = pl_namespace AND rd.page_title=pl_title
LEFT JOIN redirect   ON rd_from = rd.page_id AND rd_namespace = 0
WHERE page.page_namespace = ? AND page.page_title = ?
AND pl_namespace=0
UNION SELECT ?
""", (self.page.namespace(),)+(self.page.title(underscore=True),)*2, max_time=30)
		self.existingLinks = self.cursor.fetchall()

		self.median = 0
		try:
			self.cursor.execute("""
SELECT COUNT(*) AS FREQ
FROM page AS dab
JOIN pagelinks AS p ON p.pl_from = dab.page_id
JOIN pagelinks AS s ON      s.pl_namespace=p.pl_namespace AND      s.pl_title=p.pl_title
JOIN page AS blue   ON blue.page_namespace=p.pl_namespace AND blue.page_title=p.pl_title

WHERE dab.page_namespace=? AND dab.page_title=?
AND p.pl_namespace=?

GROUP BY blue.page_namespace, blue.page_title
-- GROUP BY p.pl_namespace, p.pl_title
ORDER BY FREQ;
""", (self.page.namespace(), self.page.title(underscore=True), 0,), max_time=30)
			results = self.cursor.fetchall()
			if results:
				self.median, = results[self.cursor.rowcount//2]
				debug('The median linktivity is %d (sample %d links)'%(self.median, self.cursor.rowcount,))
		except oursql.OperationalError as e:
			self.median = 20
			warn('Unable to determine median linktivity (%s), assuming %d'%(e, self.median))


	def doubleredirect(self):
		'''
		List double redirects
		Vestigal thanks to double redirect bots
		'''
		self.cursor.execute("""
SELECT link.page_title, targt.page_title, dbl.rd_title
FROM page AS dab
JOIN pagelinks  	ON pl_from = dab.page_id
JOIN page AS link	ON link.page_namespace=pl_namespace AND link.page_title=pl_title
JOIN redirect		ON redirect.rd_from = link.page_id
JOIN page AS targt 	ON targt.page_namespace=redirect.rd_namespace AND targt.page_title=redirect.rd_title
JOIN redirect AS dbl ON dbl.rd_from = targt.page_id
WHERE dab.page_namespace = 0
AND dab.page_title = ?
AND targt.page_is_redirect = 1
""", (self.page.title(underscore=True),), max_time=30)
		if self.cursor.rowcount:
			heading(3, "Double redirects")
			print '<ul class="error">'
			for t in self.cursor.fetchall():
				printu(u"<li>%s → %s → %s</li>"%tuple(CreateLink(title) for title in t))
			print '</ul>'

	def primary_entry(self):
		# TODO Determine which topics go where on multi-topic primary pages
		self.cursor.execute("""
SELECT 
  IFNULL(GROUP_CONCAT(DISTINCT rdpagein.page_title SEPARATOR "|"), "") AS inrd,
  pagein.page_title,
  dab.page_title, /* center point */
  pageout.page_title,
  EXISTS (SELECT 1
    FROM templatelinks
    WHERE tl_from = pagein.page_id
    AND tl_namespace IN (10, 828) /* Template: and Module: */
    AND tl_title IN ("""+','.join(("?",)*len(self.hatnotes))+""")
  ) AS hatnote
FROM page AS dab /* center point */

/* Links and redirects to center point */
JOIN pagelinks AS linkin    ON linkin.pl_title  = dab.page_title      AND   linkin.pl_namespace    = 0
JOIN page      AS pagein    ON pagein.page_id   = linkin.pl_from      AND   pagein.page_namespace  = 0
LEFT JOIN redirect AS rdin  ON rdin.rd_title    = pagein.page_title   AND     rdin.rd_namespace    = 0 AND rdin.rd_fragment=""
LEFT JOIN page AS rdpagein  ON rdpagein.page_id = rdin.rd_from        AND rdpagein.page_namespace  = 0

/* Links and redirects from center point */
JOIN pagelinks AS linkout   ON linkout.pl_from  = dab.page_id         AND   linkout.pl_namespace   = 0
JOIN page      AS pageout   ON pageout.page_title = linkout.pl_title  AND   pageout.page_namespace = 0
LEFT JOIN redirect AS rdout ON rdout.rd_from    = pageout.page_id     AND     rdout.rd_namespace   = 0 AND rdout.rd_fragment=""
LEFT JOIN page AS rdpageout ON rdpageout.page_title = rdout.rd_title  AND rdpageout.page_namespace = 0

WHERE dab.page_namespace = ? AND dab.page_title = ?
AND (
    pagein.page_id = pageout.page_id
OR  pagein.page_id = rdpageout.page_id
OR  rdpagein.page_id = pageout.page_id
OR  rdpagein.page_id = rdpageout.page_id
)
GROUP BY pagein.page_title
LIMIT 20 /* enough primary topics */
""", self.hatnotes+(self.page.namespace(), self.page.title(underscore=True),), max_time=30)

		if self.cursor.rowcount:
			heading(2, "Primary topic", className="debug")

		def checkTitle(a, b):
			" Does title a match title b "
			if a == b:# or a.find(b+'_(')==0 or a.find(b+',')==0:
				return True
			return False
		for inrd, inpage, dabpage, outpage, hatnote in self.cursor:
			oldprefixes = self.prefixes.copy()
			
			#debug(u' → '.join('[[%s]]'%s.replace('_', ' ') for s in (inrd, inpage, dabpage, outpage,) if s))
			debug(u'[[%s]]%s → [[%s]] → [[%s]]%s' % (inpage, ' (%+d redirects)'%(inrd.count('|')+1,) if inrd else '', dabpage, outpage, ' (hatnote)' if hatnote else '',))
			# XXX What are we doing here?
			if any(checkTitle(inpage, prefix) or any(checkTitle(s, prefix) for s in inrd.split('|')) for prefix in self.prefixes):
				if not hatnote: # is {{dablink}} on the page?
					warn("Missing a hatnote on [[%s]]" % (inpage,))
				else:
					self.primelinks[inpage] = True
					#
					self.addprefix(inpage)
					for x in inrd.split('|'): # + redirects
						self.addprefix(x)
			
					# Check/Set primary topic
					if re.search(ur"^[^'\n]*(?:''|)'''[^'\n]*\[\[(?:%s)(?=\]\]|\|)" % wikilinkregex(inpage), self.text, flags=re.M | re.U):
						debug('[[%s]] is already bolded' % inpage.replace('_', ' '))
					else:
						self.text, n = re.subn(ur"""
((?:\{\{[^{}:]+\}\}\s*?)*)
^(.*)
^[#*]+[ ]*((?:'''|)('{0,2}\[\[%s\]\]'{0,2})(?:'''|)*[-,: ]*?(\ \([^(\n)]*?\)|)[-,: ]*([^\n]*?))[,.]*$\n
""" % wikilinkregex(inpage),
							lambda m: m.expand(ur"\1'''\4'''\5 %s \6.\n\n\2"%("was" if re.search(ur'(died |d\. |[-\u2013\u2014]) *\d{3,4}\)', m.group(5)) else "is")),
							self.text,
							flags=re.DOTALL | re.M | re.U | re.X
						)
						if n==0:
							error("[[%s]] should be listed as a primary topic" % inpage.replace('_', ' '))

			# Show users what we've added
			newprefixes = sorted(self.prefixes.difference(oldprefixes))
			if newprefixes:
				printu("From %s adding prefix%s: %s<br/>" % (
					CreateLink(inpage),
					'' if len(newprefixes)==1 else 'es',
					EnglishJoin(['<code>%s</code>'%wikipedia.escape(t) for t in newprefixes], joined='and'),
				))
	
		if not self.page.is_disambig:
			debug('skip removal, not a disambig')
			return
		# self.disambiguadioncategory 
		self.cursor.execute('''
SELECT REPLACE(page.page_title, "_(disambiguation)", "")
FROM page AS page
LEFT JOIN redirect   ON rd_from = page_id
LEFT JOIN page AS rd ON rd.page_namespace=rd_namespace AND rd.page_title=rd_title
JOIN page_props      ON pp_page = IFNULL(rd.page_id, page.page_id) AND pp_propname="disambiguation"
WHERE pp_page != ?
AND page.page_namespace=0
AND page.page_title IN ('''+','.join(('?',)*2*len(self.prefixes))+')',
		(self.page.id,)+
		tuple(self.prefixes) + tuple("%s_(disambiguation)"%t for t in self.prefixes))
		oldprefixes = self.prefixes.copy() # Save for hack
		if self.cursor.rowcount:
			# TODO merge with cleanprfixes
			for title, in self.cursor.fetchall():
				for x in ('The_', 'A_', ''):
					if title.startswith(x):
						self.prefixes -= set([title.replace(x, '', 1)])
					self.prefixes -= set(["%s%s"%(x, title)])
					if not title.isupper():
						self.prefixes -= set([("%s%s"%(x, title,)).capitalize()])

			printu("Remove %s linked to other disambiguation pages" % (
				EnglishJoin(["<code>%s</code>"%wikipedia.escape(t) for (t,) in self.cursor.fetchall()]),
			))
			debug("list is %r"%(self.prefixes,))
		if not self.prefixes: # HACK See [[User talk:Dispenser#Dabfix SQL error]]
			self.prefixes = oldprefixes 
			


	def redlinks(self):
		# TODO "Shape up" should find "Shape Up with Nancy Larson"
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
			ur"/Article_alerts(/|$)",                   # Created by WP:Article_alerts bot
		))
		missing_P = ur'|'.join(( # TODO Promote these
			ur'missing|encyclopedia|redlinks',
			ur'wikiproject(?!.*Red_Link_Recovery|.*COIReports|.*Templates_with_red_links)|/Villages_in_',
			ur'^WikiProject_Missing_encyclopedic_articles/',  
			ur'^Missing_science_topics',              # [[Wikipedia:Missing science topics]]
			ur'^List_of_encyclopedia_topics',         # [[Wikipedia:List of encyclopedia topics]]
			ur'/Article_requests',                    # [[Wikipedia:WikiProject Birds/Article requests]]
			ur'/Missing',                             # Subpage pattern [[User:Skysmith/Missing topics about Surgery]], [[Wikipedia:WikiProject Medicine/Missing]]
			ur'/List_of_missing_',
		))
		name_regexp = ur"^[-\'`.[:alpha:]]+(_[[:upper:]][-\'`.[:alpha:]]*)?_[[:upper:]][-\'`[:alpha:]]+(_[(][^()]+[)])?$"
		addlinks = {}
		addnames = {}
		addmissing = {}
		addmisname = {}
		addtemplatelinks = {}
		title_search = ()
		name_search  = ()
		for prefix in self.prefixes:
			title_search += (
				# begins
				like_escape(prefix)+'\\_(%)',
				like_escape(prefix)+',\\_%',
				like_escape(prefix)+':\\_%',
				like_escape(prefix)+'\\_(%),\\_%',
				# trails
				'%:\\_'+like_escape(prefix),
				'%\\_'+like_escape(prefix)+'\\_(%)',
				'%\\_'+like_escape(prefix)+'\\_(%),\\_%',
				# name matching 
				like_escape(prefix)+'\\_%\\_(%)',
				like_escape(prefix)+'\\_v.\\_%', # Court cases
			)
			# 
			if prefix.count('_') > 1 or not re.search(ur'[\W\d]', prefix, flags=re.U):
				name_search += (
					like_escape(prefix)+'\\_%',
					'%\\_'+like_escape(prefix),
				)
				# Two names
			elif prefix.count('_') == 1: # First_Last
				# TODO X_FIRST_LAST
#				#FIXME X_(Y) does not work
				name_search += (
					like_escape(prefix).replace('\\_', '\\_%\\_'), 
				)
				# Names take 2
				title_search += (
					like_escape(prefix).replace('\\_', '\\_%')+'\\_(%)',
				)
			elif prefix.isupper() and prefix.isalpha(): # Initials + no underscore
				name_search += (
					'%\\_'.join(prefix)+'%', like_escape(prefix)+'\\_%',
				)
				# XXX what's the last test for? numbers and symbols? does it match the unicode chars?
				# 
		# Remove FULLTEXT special symbols 
		ft_prefixes = tuple('"%s"'%re.sub('["+\-~*]', '', p).replace('_',' ') for p in self.prefixes)

		def redlink_fulltext_searcher(dbname, namespace, prefixes):
			"""
			Cron runs ~/scripts/redlinks.sql updater weekly
			creating FULLTEXT INDEX 
			"""
			if namespace!=0:
				error('Only main namespace suported')
				return ()
			if not dbname.startswith('enwiki'):
				error('No redlinks fulltext table exists for %s' % (dbname,))
				return ()
			if len(ft_prefixes) == 0:
				return ()
			with toolsql.getConn('u2815__p', host='tools.labsdb') as curs:
				try:
					curs.execute("""
						SELECT DATE_FORMAT(IFNULL(UPDATE_TIME, CREATE_TIME), "%d %b %Y") AS updated
						FROM information_schema.tables
						WHERE TABLE_SCHEMA=? AND TABLE_NAME=?
						AND IFNULL(UPDATE_TIME, CREATE_TIME) + INTERVAL 30 DAY < NOW()
					""", ('u2815__p', 'redlinks_%s_p' % dbname.rstrip('_p'),))
					if curs.rowcount:
						warn('Redlinks Fulltext Table is out of date (%s)' % curs.fetchall()[0])
					
					#
					curs.execute("""/* related.redlink_fulltext_searcher */
						SELECT rl_namespace, rl_title 
						FROM (%s) AS redlink_fulltext_results
						WHERE %s OR %s""" % (
' UNION DISTINCT '.join(("""(
SELECT 0 AS rl_namespace, REPLACE(rl_title_ft, " ", "_") AS rl_title
FROM u2815__p.redlinks_enwiki_p
WHERE MATCH (rl_title_ft) AGAINST (? IN BOOLEAN MODE)
/* ORDER BY is implicit */
LIMIT 100
)""",)*len(ft_prefixes)), 
	(    ' OR '.join( ('rl_title LIKE ?',)*len(title_search) or ('FALSE',) )),
	("("+' OR '.join( ('rl_title LIKE ?',)*len(name_search)  or ('FALSE',) )+") AND CAST(rl_title AS CHAR CHARACTER SET utf8mb4) REGEXP ?"),
), ft_prefixes + title_search + name_search + (name_regexp,), max_time=10)
					return tuple(title for (ns, title) in curs.fetchall())
				except oursql.OperationalError as e:
					error('Redlink FullText search: %r'%(e,))
					wikipedia.output("Variables %r" % ((dbname, namespace, prefixes),))
					return ()
		extra = redlink_fulltext_searcher(self.site.dbName(), 0, self.prefixes)
		#printu('<div class="debug">Redlinks FULLTEXT searcher:<br/> %s </div>' % '<br/>'.join(CreateLink(rl_title, className="new") for rl_title in extra))

		red_params = 'pl_title LIKE ? OR pl_title LIKE ? OR pl_title LIKE ? OR (pl_title LIKE ? AND CAST(pl_title AS CHAR CHARACTER SET utf8mb4) REGEXP ?)'
		def redLinkParameters(prefixes, suffixSearch=False):
			list = ()
			# Redlinks FULLTEXT searcher
			for p in prefixes:
				list += (like_escape(p)+'\\_(%)', like_escape(p)+',\\_%', like_escape(p)+'\\_(%),\\_%', like_escape(p)+'\\_%', name_regexp)# '%\\_'+like_escape(p),)
			return list
		self.cursor.execute("""
SELECT 
  pl_namespace,
  pl_title, 
  "",/*ns_name, /* text for pl_namespace above */
  COUNT(*)                                                        AS links,
  SUM(ref.page_namespace = pl_namespace)                          AS ns_links,
  (SELECT GROUP_CONCAT(DISTINCT DATE_FORMAT(log_timestamp, "%b %Y") SEPARATOR ", ")
	FROM logging_logindex
	WHERE log_namespace = pl_namespace AND log_title = pl_title
	AND log_action = "delete"
  ) AS log_deletes,
  /* ORDER BY reverses original randomish order :-( */
  GROUP_CONCAT(ref.page_namespace ORDER BY ref.page_namespace = 10 DESC SEPARATOR "|") AS ns_context,
  GROUP_CONCAT(ref.page_title     ORDER BY ref.page_namespace = 10 DESC SEPARATOR "|") AS context,
  -- (GROUP_CONCAT(DATE_FORMAT(log_timestamp, "%b %Y") SEPARATOR "|") AS lastmod,
  /* STRAIGHT_JOIN since statistics can screw up.  See https://jira.toolserver.org/browse/TS-1190 */
  SUM((SELECT STRAIGHT_JOIN COUNT(*) FROM templatelinks 
	JOIN page AS trans ON trans.page_id=tl_from AND trans.page_namespace=0 
	WHERE tl_namespace=ref.page_namespace AND tl_title=ref.page_title
  )) AS trans_count,
  (SELECT GROUP_CONCAT(DISTINCT ips_item_id SEPARATOR " ")
    FROM wikidatawiki_p.wb_items_per_site
    WHERE ips_site_id IN (SELECT dbname FROM meta_p.wiki WHERE dbname != TRIM("_p" FROM DATABASE()) AND family="wikipedia")
    AND ips_site_page IN (
		REGEXP_REPLACE(REPLACE(pl_title, "_", " "), "(.+) \\\\(([0-9]+),? (.+)\\\\)",	"\\\\1 (\\\\3 \\\\2)")
	)
  ) AS wikidata_items_A,
  (
    SELECT GROUP_CONCAT(DISTINCT ips_item_id SEPARATOR " ")
    FROM wikidatawiki_p.wb_items_per_site
    WHERE ips_site_id IN (SELECT dbname FROM meta_p.wiki WHERE dbname != TRIM("_p" FROM DATABASE()) AND family="wikipedia")
    AND ips_site_page IN (
		REGEXP_REPLACE(REPLACE(pl_title, "_", " "), "(.+) \\\\((.+),? ([0-9]+)\\\\)",	"\\\\1 (\\\\3 \\\\2)")
	)
  ) AS wikidata_items_B,
  (/* Exact term match, [[Richard Maxwell Fox]] (Q26328565) */
  	SELECT GROUP_CONCAT(DISTINCT SUBSTR(term_full_entity_id, 2) SEPARATOR " ")
	FROM wikidatawiki_p.wb_terms
	WHERE term_entity_type="item" 
	AND term_text = REPLACE(pl_title, "_", " ")
	AND term_language=REPLACE((SELECT DATABASE()), "wiki_p", "")
  ) AS wikidata_items_C


FROM page AS ref
JOIN pagelinks  			ON pl_from = ref.page_id
LEFT JOIN page_props        ON pp_page = ref.page_id AND pp_propname="disambiguation"
LEFT JOIN categorylinks     ON cl_from = ref.page_id AND cl_to IN ("""+','.join(('?',)*len(self.setindexcategory))+""")
AND pl_namespace=0
/*JOIN u2815__p.namespacename ON dbname = (SELECT DATABASE()) AND ns_id = pl_namespace AND ns_is_favorite = 1 /*-*/
LEFT JOIN page AS pl 		ON pl.page_namespace = pl_namespace AND pl.page_title = pl_title
WHERE pl.page_id IS NULL
AND pl_title NOT IN ("""+','.join(("?",)*len(self.existingLinks))+""")
AND (
	"""+' OR '.join((red_params,)*len(self.prefixes)+("pl_title=?",)*len(extra))+"""
)
AND pl_namespace=0 /* Until u2815__p.namespacename is fixed */
AND   pl_namespace = ?
/* Content namespaces only */
AND   ref.page_namespace IN (0, 2, 4, 6, 8, 10, 12, 14)
/* Avoid meta references */
AND   ref.page_title NOT REGEXP ?
/* No disambiguation pages (also hack to correct ns_links) */
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
  -- pl_title_ci ASC
  pl_title ASC
""", self.setindexcategory+zip(*self.existingLinks).pop()+redLinkParameters(self.prefixes)+extra+(0, metapages), max_time=90)

		rowcount = self.cursor.rowcount
		heading(2, "Red link finder", className="debug")
		if not rowcount:
			debug('No results')
			return 
		shownlinks = 0
		print('<ul class="columns">' if rowcount>10 else '<ul>')
		for pl_namespace, pl_title, ns_name, links, ns_links, log_deletes, ns_context, context, trans_count, wikidata_items_A, wikidata_items_B, wikidata_items_C in self.cursor:
			# will we add the link?
			# TODO create blacklist for Wikipedia:Templates with red links/xxx
			hasqualifier = any(c in pl_title for c in [',_','_(','-',]) # )
			intext  = re.search(RelinkText % wikilinkregex(pl_title, italic=True), self.text, flags=(re.I if hasqualifier else 0) | re.M | re.U)
			missing = re.search(missing_P, context.replace('|', '\n'), flags=re.I | re.M)
			wd_items = set((wikidata_items_A or '').split()) | set((wikidata_items_B or '').split()) | set((wikidata_items_C or '').split())
			#wd_item = wd_items.pop() if len(wd_items) == 1 else None
			
			success = False
			if intext and ns_links > 0:
				# https://en.wikipedia.org/wiki/Wikipedia:Redirects_for_discussion/Log/2015_December_7#Inferno_.281973_film.29
				self.text, success = intext.re.subn(ur'\1[[%s|\2]]\3' % pl_title.replace('_', ' ').replace('\\', '\\\\'), self.text, 2)
			# Demarcate where the link is coming from
			if success:
				extra_info_html = u'<b>(Linking text)</b>'
			elif log_deletes:
				# FIXME Combine with better code from other places to classify deleted links
				extra_info_html = u', <b>deleted %s</b>' % log_deletes
				if ns_links==0:
					continue
			#FIXME parseline() removes links without article links
			elif missing and ns_links >= 2 and links * 0.50 > trans_count:
				extra_info_html = u'<b>(Missing article)</b>'
				if not hasqualifier or '_' in pl_title:
					addmisname[pl_title] = True
				else:
					addmissing[pl_title] = True
				'''
			elif links>=4 and ns_links >= 2 and links * 0.50 > trans_count :
				if '10' in ns_context.split('|'):
					try:
						addtemplatelinks[pl_title] = context.split('|')[ns_context.split('|').index('10')]
					except IndexError:
						addtemplatelinks[pl_title] = ''
				else:
					extra_info_html = u'<b>(Recover)</b>'
					if hasqualifier or '_' not in pl_title:
						addlinks[pl_title] = True
					else:
						addnames[pl_title] = True
				#'''
			elif wd_items and ns_links >= 2 and links * 0.50 > trans_count:
				extra_info_html = u''
				if not hasqualifier or '_' in pl_title:
					addmisname[pl_title] = True
				else:
					addmissing[pl_title] = True
			else:
				extra_info_html = u''
			
			if trans_count:
				extra_info_html = u'(%d transclusions) %s' % (trans_count, extra_info_html)
			if pl_namespace==0 and pl_title not in extra: # U+2020 (†) dagger
				extra_info_html = u'<abbr title="Live search results">\u2020</abbr> ' + extra_info_html 
			# Get Wikidata info
			if len(wd_items) == 1:
				birth, death, desc = wikidata_description(site, list(wd_items)[0], lang=self.site.language())
				if extra_info_html:
					extra_info_html += u','
				if birth and not death:
					extra_info_html += ' (born %s)'%(birth.year,)
				elif not birth and death:
					extra_info_html += ' (died %s)'%(death.year,)
				elif birth and death:
					extra_info_html += ' (born %s; died %s)'%(birth.year, death.year)
				else:
					pass
				if desc:
					extra_info_html += ' ' + desc
			# Render HTML list
			showNode = 1#(ns_links-trans_count>=2 and links-trans_count>=4 or links>=rowcount//5) or intext or missing 
			shownlinks += 1
			printu('<li class="%s"><span>%s' % ('' if shownlinks <= 20 or intext or missing else 'debug', CreateLink(pl_title, className="new"),))
			if ns_context == '0':  # Avoid "1 article link"
				printu(u'%s%s</span> from %s</li>'% (
					''.join((', <small>(<a class="wikidata" href="https://www.wikidata.org/wiki/Q%s">Q%s</a>)</small>' % (x, x) for x in wd_items)), 
					extra_info_html,
					CreateLink(context),
				))

			else:
				printu(u' (%s%s) %s' % (
					''.join(('<a class="wikidata" href="https://www.wikidata.org/wiki/Q%s">Q%s</a>, ' % (x, x) for x in wd_items)), 
					CreateLink(
						'Special:WhatLinksHere/%s'%pl_title,
						'%s%d %s%s'%(
							'%d article link%s / '%(ns_links-trans_count if ns_links>=trans_count else ns_links, '' if ns_links==1 else 's') if links > ns_links > 0 else '',
							links, 
							'article link' if links==ns_links else 'link',
							'' if links==1 else 's',
						),
						addAttribute=' onclick="toggleNode(this.parentNode.nextSibling);return false;"', className='rl_expand'
					),
					extra_info_html,
					)
				)
				try:
					printu(u'</span><ul class="whatlinkshere" style="display:none">%s</ul>'% (
						'\n'.join(u'<li>%s</li>' % CreateLink(t if n=='0' else (wikipedia.namespaces[int(n)] or '')+':'+t) for n,t in zip(ns_context.split('|'), context.split('|'),)),
					))
				except Exception as e: # FIXME specific exception
					printu('</span>')
					error('excessed max packet size (%r)' % (e,))
				print '</li>'
		print '</ul>'

		for (addlist, listname, maxcount) in (
			(addlinks,  "RED LINKS",		            25),
			(addnames,  "RED LINKS: name-like",	        10),
			(addmissing,"RED LINKS: missing articles",	10),
			(addmisname,"RED LINKS: missing names",     10),
		):
			if not addlist:
				continue
			elif len(addlist) <= maxcount:
				self.addsection('%s' % listname, wikibulleted(addlist.keys()))
			else:
				wikipedia.output('Too many %s to add (%d/%d)' % (listname, len(addlist), maxcount))

		if addtemplatelinks:
			if len(addtemplatelinks)<=5 and addnames and addlinks:
				self.addsection('templated red links', 
					''.join(("* [[%s]], [[Template:%s|]]\n"%(link, template)).replace('_',' ') for link, template in addtemplatelinks.items())
				)
			else:
				wikipedia.output('Not adding %d templated red links' % len(addtemplatelinks))
	
	def bluelinks(self):
		def parameters_links(prefixes):
			pf_list = ()
			for prefix in prefixes:
				prefix_esc = like_escape(prefix)
				# try yeild
				pf_list += (prefix_esc+ur'\_(%)', prefix_esc+ur',\_%', prefix_esc+ur'\_(%),\_%',)
			return tuple(pf_list)

		def parameters_names(prefixes):
			names = ()
			for prefix in prefixes:
				if isinstance(prefix, bytes):
					prefix = prefix.decode('utf-8')
				prefix_esc = like_escape(prefix)
				# Acronym
				if prefix.isupper() and prefix.isalpha(): # No spaces/digits/_ = Initials
					names += ('%\\_'.join(prefix)+'%', prefix+'\\_%',)
				elif prefix.count('_') > 2 or re.search(ur'[\W\d]', prefix, flags=re.U):
					# Multiple spaces or [0-9], puncuation, symbols
					pass
				# Two names
				elif prefix.count('_') == 1: # First_Last
					# TODO X_FIRST_LAST
					# FIXME X_(Y) should not work
					xnames = (prefix.replace('_', ur'\_%\_'), prefix.replace('_', ur'\_%\_')+ur'\_(%)', )
					# TODO long way for r',?_[SJ]r[.]?$'
					for a in (',',''):
						for b in ('Jr', 'Sr'):
							for c in ('.', ''):
								xnames += ('%s%s\\_%s%s' % (prefix.replace('_', ur'\_%\_'),a,b,c),)
					names += xnames
					for a in ('Sir', 'Dame', 'Lord', 'Lady'):
						names += tuple('%s\\_%s'%(a, b) for b in xnames)
						names += ('%s\\_%s' % (a, prefix.replace(u'_', ur'\_'),),)
					#print '<p>', tuple('%s\\_%s'%(a, b) for b in xnames)
				elif prefix.count('_') == 2:
					names += (prefix.replace('.', '').replace('_', ur'\_%\_'), prefix.replace('_', ur'%\_')+ur'\_(%)', )
				else:	# First or Last
					names += (prefix_esc+'\\_%', '%\\_'+prefix_esc,)
			#print 'parameters_names() = ', names
			return names
		
		def query_candidates(name='query_candidates', prefix_search=[], title_search=[], name_search=[], regexp_search=[], use_api_search=False, max_time=30):
			possible_titles = set()
			if use_api_search:
				possible_titles |= set("") # XXX Dummy title to prevent SQL errors
				for prefix in self.prefixes:
					searcher = [u"intitle:%s"%s for s in prefix.replace('_', ' ').split() if len(s)>3]
					if not searcher: continue
					possible_titles |= set(scrape_search(site, ' '.join(searcher), namespaces=[0]))
				if not possible_titles:
					raise StopIteration
				#print '<pre>', list(possible_titles), '</pre>'
			name_regexp = ur"^[-\'`.[:alpha:]]+(_[[:upper:]][-\'`.[:alpha:]]*)?_[[:upper:]][-\'`[:alpha:]]+(_[(][^()]+[)]|,?_[SJ]r[.]?)?$"
			query = """-- %s
SELECT page_title
FROM page
WHERE page_namespace=0
AND (%s OR %s OR %s OR %s)
%s
LIMIT 100;
""" % (
name,
"page_title IN ("+','.join(("?",)*len(prefix_search) or ('""',))+")",
' OR '.join(('page_title LIKE ?',)*len(title_search) or ('FALSE',)),
' OR '.join(('page_title REGEXP ?',)*len(regexp_search) or ('FALSE',)),
"(("+' OR '.join(('page_title LIKE ?',)*len(name_search) or ('FALSE',))+") AND CAST(page_title AS CHAR CHARACTER SET utf8mb4) REGEXP ? )",
'AND page_title IN (%s)'%','.join(("?",)*len(possible_titles)) if use_api_search else '',
)
			try:
				self.cursor.execute(query, tuple(prefix_search)+tuple(title_search)+tuple(name_search)+(name_regexp,)+tuple(possible_titles), max_time=max_time)
			except toolsql.QueryTimedOut as (errno, strerror, extra):
				wikipedia.logtime('bluelink(): %s search: Timed out (%d sec)' % (name, self.cursor.elapsedtime))
			#except oursql.DatabaseError as (errno, strerror, extra):
			#	wikipedia.logtime('bluelink(): %s search: oursql.DatabaseError(%r)' % (name, strerror))
			except:
				print '<p>Query:</p><xmp>', query, '</xmp>'
				print '<p>Data:</p><xmp>', prefix_search, title_search, name_search, regexp_search, possible_titles, '</xmp>'
				raise
			else:
				wikipedia.logtime('bluelink(): %s search' % name)
			for page_title, in self.cursor:
				yield page_title


		# Find candidates
		heading(2, 'Blue link finder', className='debug')
		candidates = []
		candidates += query_candidates(
			name="API",
			use_api_search=True,
			prefix_search=self.prefixes,
			title_search=parameters_links(self.prefixes),
			name_search=parameters_names(self.prefixes),
			max_time=10
		)
		candidates += query_candidates(
			name="regular",
			prefix_search=self.prefixes,
			title_search=parameters_links(self.prefixes),
			max_time=90
		)
		candidates += query_candidates(
			name="Prefix name",
			name_search=[s for s in parameters_names(self.prefixes) if not s.startswith('%')],
			max_time=30
		)
		# This query is too slow
		#candidates += query_candidates(
		#	name="Suffix name",
		#	name_search=[s for s in parameters_names(self.prefixes) if s.startswith('%')],
		#	max_time=1
		#)
		# Prune existing pages
		candidates = list(set(candidates) - set(self.existingLinks))
		
		# Get more information about the candidates
		self.cursor.execute("""
SELECT 
  page_namespace,
  page_title,
  rd_namespace,
  rd_title,
  rd_fragment,
  (SELECT COUNT(*)
    FROM pagelinks
    JOIN categorylinks ON cl_from=pl_from
    WHERE pl_namespace=page_namespace AND pl_title=page_title
    AND cl_to IN ("""+','.join(('?',)*len(self.disambiguationcategory))+""")
  ) AS "dabcount",
  backlinks,
  EXISTS (SELECT 1
	FROM categorylinks
	WHERE cl_to REGEXP ?
	AND cl_from = page_id
  ) AS People,
  EXISTS (SELECT 1
	FROM categorylinks
	WHERE cl_to REGEXP ?
	AND cl_from = page_id
  ) AS Geography,
  EXISTS (SELECT 1
  	FROM page_props
	WHERE pp_page = page_id
	AND pp_propname="disambiguation"
  ) AS disambig,
  (SELECT NOT People AND NOT Geography AND (LOCATE("_(", page_title) OR LOCATE("-", page_title))) AS Blue,
  (SELECT NOT Blue AND LOCATE(',_', page_title)) AS places,
  EXISTS (SELECT 1 FROM revision WHERE rev_page=page_id AND rev_timestamp < ?) AS new,
  IFNULL(pp_value, page_title) AS Sortkey
FROM (
SELECT page_id, page_namespace, page_title,
       rd_namespace, rd_title, IFNULL(rd_title, page_title) AS target, rd_fragment,
	   COUNT(pl_from) AS "backlinks", pp_value
FROM page AS searched_pages
LEFT JOIN pagelinks  ON pl_namespace=0  AND pl_title=page_title
LEFT JOIN redirect   ON rd_from=page_id AND rd_namespace=0
LEFT JOIN page_props ON pp_page=page_id AND pp_propname="defaultsort"

WHERE page_namespace=0 AND page_title IN ("""+",".join(("?",)*len(candidates) or ('""',))+""")

GROUP BY page_id
ORDER BY 
    /* Parentheses terms first */
	INSTR(target, '_(') OR INSTR(target, ',') DESC,
	target, 
	rd_title IS NOT NULL ASC,
	backlinks DESC
LIMIT 25000
) AS r
GROUP BY target, rd_fragment
HAVING target NOT IN ("""+','.join(('?',)*len(self.existingLinks))+""")
ORDER BY LOCATE('_(', page_title) AND rd_title IS NULL DESC, FLOOR(LOG10(backlinks)) DESC, Geography DESC, People DESC, Sortkey ASC
LIMIT 500
""", self.disambiguationcategory+(CatPerson, CatPlaces, self.page.wpEdittime,)+tuple(candidates)+zip(*self.existingLinks).pop(), max_time=30)
		
		if self.cursor.rowcount==0:
			debug('No links found')
		linksets = [
		# code name      Header        maxcount
			('blue',	"Links",        	25,),
			('geo', 	"Places",   		40,),
			('people',	"People",   		40,),
			('disambig',"Disambiguation",   10,),
			('places',	"place-like name",	15,),
			('names',	"name-like",		20,),
		]
		addlinks = dict((key, {}) for key, x,y in linksets)
		for page_ns, title, rd_ns, rd_target, rd_fragment, dabcount, count, people, geography, disambig, blue, places, new, sortkey in self.cursor:
			# Re-link removed links
			title_R = re.compile(RelinkText % wikilinkregex(title, italic=True), flags=re.I | re.M | re.U)
			title_text_count = len(title_R.findall(self.text))
			#if title_text_count == 1 and not people: # Avoid relinking "John Smith, my Lab mate"
			if title_text_count == 1:# and (',_' in title or '_(' in title):
				self.text = title_R.sub(ur'\1[[%s|\2]]\3' % title.replace('_', ' ').replace('\\', '\\\\'), self.text)
				continue
			if disambig:     listkey = 'disambig'
			elif people:     listkey = 'people'
			elif geography:  listkey = 'geo' 
			elif blue:       listkey = 'blue' 
			elif places:     listkey = 'places'
			else:            listkey = 'names'
			#
			rd_target_full = rd_target+'#'+rd_fragment if rd_fragment else rd_target
			addlinks[listkey][rd_target_full or title] = (title, dabcount, count, people, geography, sortkey)
	
		for listkey, listname, maxcount in linksets:
			if addlinks[listkey] == {}:
				continue
			addlist = addlinks[listkey]
			# XXX better if sorted by link count (c)
			# TODO Split list into redirects
			# addsort = sorted(addlist, key=lamdba tup: tup[2], reverse=True)
			most = sorted([t for k,(t,d,c,p,g,s) in addlist.iteritems()], key=lambda t:addlist.get(t, (t,))[-1])
			good = sorted([t for k,(t,d,c,p,g,s) in addlist.iteritems() if k==t and d==0], key=lambda k:addlist[k][5])
			top  = sorted([t for k,(t,d,c,p,g,s) in addlist.iteritems() if k==t and c>=self.median and d==0], key=lambda k:addlist[k][5])
			debug(u"%s pages found: %d (%d redirects/dab-linked, links ≥ median backlinks(%d): %d)"\
					%(listname.capitalize(), len(most), len(addlist)-len(good), len(top), self.median,))
			
			extra = set(addlist.keys())
			if   0 < len(most) <= maxcount // 2:
				if len(good)==0: # All redirects
					self.addsection('BLUE LINKS: %s (%d redirects)'%(listname, len(most)), wikibulleted(most))
				else:
					self.addsection('BLUE LINK: %s'%listname if len(most)==1 else '%d BLUE LINKS: %s'%(len(most), listname), wikibulleted(most))
				extra -= set(addlist.keys())
				extra -= set(most)
			elif 0 < len(good) <= maxcount:
				self.addsection('BLUE LINKS: %s (%d articles)'%(listname, len(good)), wikibulleted(good))
				extra -= set(good)
			elif 0 < len(top)  <= maxcount:
				self.addsection('BLUE LINKS: %s (%d articles w/ %d+ incoming links)'%(listname, len(top), self.median), wikibulleted(top))
				extra -= set(top)
			else:
				wikipedia.output('Too many %s to add (%d/%d)' % (listname, len(addlist), maxcount))
		
			if len(extra):
				info('Skipped from %s set' % listname)
				print('<ul class="columns">' if len(extra)>10 else '<ul>')
				samePrefix = 0
				for key in sorted(extra):
					for listkey in addlinks:
						if key in addlinks[listkey]:
							(title, dabcount, count, people, geography, sortkey) = addlinks[listkey][key]
					x = []
					if title!=key:
						x.append(u'redirects to %s' % CreateLink(key))
					if dabcount:
						x.append(u'linked from %d disambiguation pages' % dabcount)
					if count != dabcount and dabcount > 0:
						x.append(u'%d links' % count)
					if any(title.startswith(p) for p in self.prefixes):
						samePrefix += 1
					printu('<li>%s%s</li>'%(CreateLink(title, className='mw-redirect' if title!=key else ''), ' (%s)'%EnglishJoin(x) if x else '',))
				print('</ul>')

				# Template links
				# 
				# TODO avoid {{in title|one_(disambiguation)}}
				# TODO when finding lots of blue links with the same prefix suggest these template
				if listname in ('geography', 'blue') or samePrefix:
					if '{{look from}}' not in self.text.lower():
						try:
							self.addsection('See also : Begins with', '* {{look from|%s}}' % self.PAGENAMEBASE)
						except KeyError:
							pass # We're in a loop
				if listname in ('people', 'names'):
					if '{{in title}}' not in self.text.lower():
						try:
							self.addsection('See also : Partial match', '* {{in title|%s}}' % self.PAGENAMEBASE)
						except KeyError:
							pass # We're in a loop


	
	def getdefinitions(self, maximum=5):
		# get existing links
		self.cursor.execute("""
SELECT iwl_title
FROM page
JOIN iwlinks ON iwl_from=page_id
WHERE iwl_prefix IN ('wikt', 'wiktionary')
AND page_namespace=? AND page_title=?
""", (self.page.namespace(), self.page.title(underscore=True),), max_time=1)
		existing_links = [iwl_title for (iwl_title,) in self.cursor]

		# Build a list of title permutation from prefixes list
		titles_to_look_for = []
		for title in self.prefixes:
			title = title.replace('_', ' ')
			bookcase = title.title().replace('Of', 'of').replace('The', 'The')
			# Include first uppercase and first lowercase variants
			# [[wikt:-san]], [[wikt:emo-]]
			# [[Special:Search/well known]] finds well-known
			# TODO cips should find čips
			for tcasing in (
					title,
					title.capitalize(),
					title.lower(),
					title.upper(),
					title.title(),
					bookcase,
					bookcase[0:1].lower() + bookcase[1:],
			):
				tcasing = tcasing.replace(' ', '_')
				for pattern in (u'-%s', u'%s', u'%s-', u"%s'", u"'%s"):
					titles_to_look_for += [
						pattern % tcasing,
						pattern % tcasing.replace('-', '_'),
						pattern % tcasing.replace('_', '-'),
						pattern % tcasing.replace('_', '-', 1),
					]
		titles_to_look_for = [t for t in set(titles_to_look_for) | set(existing_links)]
		#print '<!-- ', '\n'.join(tuple(titles_to_look_for)), ' -->'

		alttemplates = list(AltTemplates['en'])
		wiktquote = list(WiktRefQuote['en'])
		conn = toolsql.getConn("%swiktionary"%self.site.language())
		wiktcur = conn.cursor()
		try:
			wiktcur.execute("""
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
  (SELECT COUNT(*) FROM categorylinks WHERE cl_from=page_id AND cl_to REGEXP
    "^(Abkhaz|Afar|Afrikaans|Akan|Albanian|Amharic|Arabic|Aragonese|Armenian|Assamese|Avar|Avestan|Aymara|Azeri|Bambara|Bashkir|Basque|Belarusian|Bengali|Bihari|Bislama|Breton|Bulgarian|Burmese|Catalan|Chamorro|Chechen|Chichewa|Chinese|Chuvash|Cornish|Corsican|Cree|Czech|Danish|Dhivehi|Dutch|Dzongkha|English|Esperanto|Estonian|Ewe|Faroese|Fijian|Finnish|French|Fula|Galician|Georgian|German|Greek|Greenlandic|Guaraní|Gujarati|Haitian_Creole|Hausa|Hebrew|Herero|Hindi|Hiri_Motu|Hungarian|Icelandic|Ido|Igbo|Indonesian|Interlingua|Interlingue|Inuktitut|Inupiak|Irish|Italian|Japanese|Javanese|Kannada|Kanuri|Kashmiri|Kazakh|Khmer|Kikuyu|Kinyarwanda|Kirundi|Kongo|Korean|Kurdish|Kwanyama|Kyrgyz|Lao|Latin|Latvian|Limburgish|Lingala|Lithuanian|Luba-Katanga|Luganda|Luxembourgish|Macedonian|Malagasy|Malay|Malayalam|Maltese|Manx|Maori|Marathi|Marshallese|Mongolian|Nauruan|Navajo|Ndonga|Nepali|Northern_Ndebele|Northern_Sami|Norwegian|Norwegian_Bokmål|Norwegian_Nynorsk|Occitan|Ojibwe|Old_Church_Slavonic|Oriya|Oromo|Ossetian|Pali|Pashto|Persian|Polish|Portuguese|Punjabi|Quechua|Romanian|Romansch|Russian|Samoan|Sango|Sanskrit|Sardinian|Scottish_Gaelic|Serbo-Croatian|Shona|Sichuan_Yi|Sindhi|Sinhalese|Slovak|Slovene|Somali|Sotho|Southern_Ndebele|Spanish|Sundanese|Swahili|Swazi|Swedish|Tagalog|Tahitian|Tajik|Tamil|Tatar|Telugu|Thai|Tibetan|Tigrinya|Tongan|Tsonga|Tswana|Turkish|Turkmen|Ukrainian|Urdu|Uyghur|Uzbek|Venda|Vietnamese|Volapük|Walloon|Welsh|West_Frisian|Wolof|Xhosa|Yiddish|Yoruba|Zhuang|Zulu)"
  ) AS Lang_cats,
  (SELECT COUNT(*) FROM categorylinks WHERE cl_from=page_id AND cl_to LIKE "English%") AS "EN",
  COUNT(DISTINCT tl_title) AS "{{&#x00A0;}}",
  SUM(tl_title IN ("""+ ','.join(('?',)*len(alttemplates) or ('""',))+""")) AS Alt_of,
  IFNULL(GROUP_CONCAT(DISTINCT IF(tl_title IN ("""+ ','.join(('?',)*len(alttemplates) or ('""',))+"""), tl_title, NULL) SEPARATOR ", "), "") AS "Alt_of:",
  SUM(tl_title IN ("also")) AS also,
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
""", tuple(existing_links + alttemplates + alttemplates + wiktquote + titles_to_look_for + titles_to_look_for), max_time=30)
		except toolsql.QueryTimedOut as (errno, strerror, extra):
			error("Wiktionary database did not response in time (%d seconds)" % (wiktcur.elapsedtime,))
			wikipedia.logtime("Wiktionary timed out")
			raise
		except oursql.DatabaseError as e:
			error("Wiktionary %r" % (e,))
			self.addsection('Wiktionary', "* FAILED %r" % (e,))
			wikipedia.logtime("Failed Wiktionary links")
			return # Abort
		else:
			wikipedia.logtime("Got Wiktionary links")
		
		# Output table test/reference purposes
		output = '\n<div class="table-overflow">'
		output += '\n<table id="wiktionarylinks" class="wikitable %s">' % ('' if wiktcur.rowcount > 1 else 'debug')
		output += '<caption>Wiktionary</caption>'
		output += '\n<tr>'
		for row in wiktcur.description:
			output += '<th>%s</th>'%row[0].replace('_',' ')
		output += '</tr>'
		definitions = []
		valid_links = []
		# TODO deal with using redirects (e.g. plural name going to non-plural definition)
		# transactions (1 link, plural) combine to transaction
		escape = wikipedia.escape
		for row in wiktcur:
			output += '\n<tr>'
			dr = dict((wiktcur.description[i][0], row[i]) for i in range(len(row)))
			if 0:
				print '<!--'
				for i in range(len(row)):
					print (wiktcur.description[i][0], row[i])
				print '-->' 

			# Weights were arbitrary
			x = dr['page_len_adj'] - (500 if dr['Cited'] else 0) - (300 if dr['Links'] < 3 else 0) - 200 * (dr['Alt_of'] or 0)
			output += '\n<td><a class="extiw" style="font-weight:bold; %s" href="https://%s.wiktionary.org/wiki/%s" title="%s">%s</a></td>'% (
				'color:gray;' if x <= 200 and wiktcur.rowcount > 1 else '',
				self.site.language(),
				escape(row[0]),
				escape(row[0].replace('_',' ')),
				escape(row[0].replace('_',' ')),
			)
			output += '\n'.join('<td>%s</td>'%wikipedia.escape(unicode(item)).replace('_', ' ') for item in row[1:])
			
			valid_links.append(row[0])
			if x <= 200 and wiktcur.rowcount > 1:
				output+='<td>Not used %s</td>' % x
			else:
				output+='<td>Use (%s)</td>'%x
				definitions.append(row[0])
			
			output += '<tr>'
		output += '</table>'
		output += '</div>'
		if wiktcur.rowcount: 
			printu(output)
		conn.close()
		
		if definitions:
			if len(definitions) > maximum:
				warn('Excluding %s since {{Wiktionary}} is limit to %s definitions' % (
					EnglishJoin(["[[wikt:%s]]"%page_title for page_title in definitions[maximum:]]),
					maximum,
				))
			return definitions[0:maximum]
		else:
			# Fallback - still remove invalid links http://enwp.org?diff=778296351
			return valid_links # existing_links

	def addWiktionary(self):
		heading(2, 'Wiktionary links', className="debug")
		# FIXME Doesn't work with multiple boxes
		
		definitions = self.getdefinitions(maximum=5)
		def istitle(s):
			return s.upper()==self.page.title(underscore=True).upper() or self.page.title(underscore=True).upper().startswith(s.upper()+'_(')
		# Sort case-insensitive, but have Moon before moon and before Moonax
		definitions.sort(key=lambda s: u'%s%s %s'%('1' if istitle(s) else '2', s.lower(), s))
		
		if definitions:
			wiktionarylinks = '{{wiktionary|%s}}\n' % '|'.join(definitions).replace('_', ' ')
			htmlout('<div class="debug">Wiktionary definitions box: <code>%s</code></div>', (wiktionarylinks,))
		else:
			wiktionarylinks = ""
			debug("No definitions from wiktionary")
		
		# Add/Move {{wiktionary}} to {{Infobox given name}}
		self.text = re.sub(ur'(\{\{(?:Infobox given name)(?:[^{|}]|\{\{[^{}]+?\}\}|\|(?!\s*wikt))*?)(?:\s*\|\s*wikt\s*=|)(\s*)\}\}', ur'\1\2| wikt  = {{wiktionary}}\2}}', self.text, flags=re.I)
		# combine {{wiktionary}}
		self.text = re.sub(ur'\{\{wiktionary((?:\|[^{|}[\]|]+)*)\}\}\s*?\{\{wiktionary((?:\|[^{|}[\]|]+)*)\}\}', ur'{{wiktionary\1\2}}', self.text)
		self.text = re.sub(ur'\{\{wiktionary((?:\|[^{|}[\]|]+)*)\}\}\s*?\{\{wiktionary((?:\|[^{|}[\]|]+)*)\}\}', ur'{{wiktionary\1\2}}', self.text) # and again

		# 
		m = re.search(ur'\{\{([Ww]iktionary)(\s*\|.*?|)\}\}[ ]*\n?', self.text, flags=re.DOTALL | re.X)
		if m:
			# TODO Do not rearrange ordering
			self.text = m.re.sub(wiktionarylinks, self.text, 1)
		else:
			self.text = wiktionarylinks + self.text
	

	def seealso(self):
		try:
			self.cursor.execute("""
SELECT page_title, page_title IN (
  SELECT IFNULL(rd_title, pl_title)
  FROM page
  JOIN pagelinks     ON pl_from = page.page_id 
  JOIN page AS pl    ON pl.page_namespace=pl_namespace AND pl.page_title=pl_title
  LEFT JOIN redirect ON rd_namespace=pl_namespace      AND rd_from=pl.page_id 
  WHERE pl_namespace=0 
  AND page.page_namespace=? AND page.page_title = ?
) AS Linked
FROM (
  SELECT page.page_title
  FROM page
  JOIN categorylinks  ON cl_from = page.page_id
  JOIN pagelinks      ON page.page_id = pl_from
  JOIN page AS rd     ON rd.page_namespace = pl_namespace AND rd.page_title = pl_title
  JOIN redirect       ON rd_from = rd.page_id
  WHERE page.page_namespace = 0
  AND   rd_namespace = ? AND rd_title = ?
  AND   cl_to IN ("""+",".join(("?",)*len(self.disambiguationcategory))+""")
UNION
  SELECT page_title
  FROM page
  JOIN categorylinks ON cl_from = page.page_id
  JOIN pagelinks     ON pl_from = page.page_id
  WHERE page.page_namespace = 0
  AND   pl_namespace = ? AND pl_title = ?
  AND   cl_to IN ("""+",".join(("?",)*len(self.disambiguationcategory))+""")
) AS subquery;
""", (self.page.namespace(), self.page.title(underscore=True),)+((self.page.namespace(), self.page.title(underscore=True),)+self.disambiguationcategory)*2, max_time=30)
		except oursql.DatabaseError as e:
			error("See also: %r"%(e,))
			self.addsection('Auto-See also', "* FAILED %s" % e)
			raise
		if self.cursor.rowcount:
			heading(2, "See also links", className="debug")
			#wikipedia.output("Other disambiguation pages which link here")
			addlinks = {}
			printu('<ul class="%s">' % ('columns debug' if self.cursor.rowcount > 6 else 'debug',))
			for title, exists in self.cursor:
				printu('<li>%s (%s)</li>' % (CreateLink(title), "already linked" if exists else "may need to be linked"))
				if not exists:
					addlinks[title] = title.replace('_', ' ')
			printu('</ul>')
			self.addsection('See also : Disambiguation pages linking here', wikibulleted(addlinks.values()))
	
	def mosfixes(self):
		# Use actual headings instead of bolding
		def makeheading(m):
			# Highest level header until match (BUG: if used inconsisently)
			if '\n====='  in self.text[:m.end()]: hl = '====== %s ======' # H6
			elif '\n====' in self.text[:m.end()]: hl = '===== %s ====='   # H5
			elif '\n==='  in self.text[:m.end()]: hl = '==== %s ===='     # H4
			elif '\n=='   in self.text[:m.end()]: hl = '=== %s ==='       # H3
			else:                                 hl = '== %s =='         # H2
			title = m.group('title').replace("'''", "")
			return hl % (title[0:1].upper()+title[1:],)
		self.text = re.sub(ur"""^(
		# Semi-colon fake heading
		  ;\ *(In\ |As\ a?\ *|the\ )*
		# Introductions
		| (In\ |As\ a?\ *|An?\ |the\ )* '''
		# Lazy
		| (?<=\n\n)(?=[\w ]{4,20}:$)
		)
		\ *
		(the\ |)
		(?P<title>([\w ]|'''\ and\ ''')+?)
		('''|[ :])*
		$""", makeheading, self.text, flags=re.X | re.M | re.I)
		
		# Fix badly indented lists
		#self.text = re.sub(r'^((:*)([*#]).+)\n\2:(?=\3.+)', r'\1\n\2\3', self.text, flags=re.M)
		self.text = re.sub(r'^:([*#])(?=.+$)', r'*\1', self.text, flags=re.M)

		# Add 1 empty line after bullet list
		# XXX allow comments even though the list actually restarts
		self.text = re.sub(ur'((^[:*#].*$\n?|^<!--.*?-->)+)\s*', ur'\1\n', self.text, flags=re.M)

		# Convert numbered/ordered lists into bullets per [[MOS:ENTRY]]
		if not re.search(ur'^\*', self.text, flags=re.M): 
			self.text = re.sub(ur'^[#*\-\u00B7\u2022]', ur'*', self.text, flags=re.M)
		# copied from [[MediaWiki:Disambiguationspage]]
		setindex_templates = ("SIA", "Given name", "Hawaiiindex", "Mountainindex",
			"Plant common name", "Disambig-plants", "Roadindex", "Shipindex",
			"Sportindex", "Surname",
		)
		disambig_template = (
			"Disambiguation",
		)
		# SIA or DAB
		self.cursor.execute("""
SELECT 1 FROM page
JOIN page_props ON pp_page=page_id AND pp_propname="disambiguation"
WHERE page_namespace=? and page_title=?
""", (self.page.namespace(), self.page.title(underscore=True)), max_time=30)
		if self.cursor.rowcount:
			pass
		elif not re.search(ur'\{\{(%s)'%'|'.join(wikilinkregex(title) for title in (disambig_template + setindex_templates)), self.text):
			if 'given names]]' in self.text:
				addtemplate = "{{given name}}"
			elif 'surnames]]' in self.text:
				addtemplate = "{{surname}}"
			else:
				addtemplate = "{{disambiguation}}"

			self.text = re.sub(ur'\n*((\n\[\[[^[\]]+\]\]\s*|\n\{\{[^{|}[\]]+\}\}\s*)*)$', ur"\n\n%s\n\1"%(addtemplate,), self.text, flags=re.I | re.DOTALL)
		
		# Unhard code {{look from}}
		self.text = re.sub(ur'((?:All|Wikipedia|pages|beginning|with| )*)\[\[Special:Prefixindex/([^[\]{|}]*)\|((?:All|Wikipedia|pages|beginning|with| )*[^[\]{|}]*)\]\]', ur'{{look from|\2||\1\3}}', self.text, flags=re.I)
		def lookfrom_repl(match):
			title = match.group(2)
			m = re.match(ur'^(All |Wikipedia |pages? |that |begin |beginning |prefixe?d? |with )*[\'" ]*(?P<label>%s)+[\'" ]*' % wikilinkregex(title), match.group(3)) 
			if m:
				return "{{%s|%s}}" % (match.group(1), m.group('label'))
			else:
				return match.group(0)
		self.text = re.sub(ur'{\{(look from)\|([^{|}]*)\|\s*\|([^{|}]*)\}\}', lookfrom_repl, self.text, flags=re.I)
		
		# Rename headings
		for old, new in (
			('Real people',            'People'),
			('Historical persons',     'People'),
			('Persons',                'People'),
			('People with the name',   'People'),
			('Personal name',          'People'),
			('Fictional characters',   'Characters'),
			('Movies',                 'Films'),
			('Computer gaming',        'Video gaming'),
			('Computer games',         'Video games'),
			('First name',             'Given name'),
			('Last name',              'Surname'),
			('Geography',              'Places'),
			('Geographical locations', 'Places'),
			('Locations',              'Places'),
			('Place names',            'Places'),
			('Miscellaneous',          'Other uses'),
			('Ohter usages',           'Other uses'),
			#('Other', 'Other uses'), # Disable--no check for {{disambig}}
		):
			self.text = re.sub(ur'^(=+ *)%s(?= *=+ *$)'%re.escape(old), ur'\g<1>%s'%new, self.text, flags=re.M | re.I)
		
		# If === Places === exists w/ 2+ bullet, then list as a {{disambig|geo}} page
		m = re.search(r'^(=+) *Places *\1 *\n+(^[#*].*\n*|^\1=+\n*){3,}', self.text, flags=re.M | re.I)
		if m and m.group().count('\n*') >= 2:
			self.text = re.sub(r'\{\{disambig[^{|}]*(\|(?!geodis|geography|geographical|place name|place names|place|places|geo)[^{|}]+)*(?=\}\})', r'\g<0>|geo', self.text, flags=re.I)
		

	def template_redirect(self):
		" Fixes template issues "
		# List template redirects (target name)
		IgnoreTemplate = ( 
			# Supress "transclusion redirect"
			"Disambiguation/cat",
			"Human_name_disambiguation",
			"PAGENAMEBASE",
		) # destination
		BypassTemplateRedirect = (
			# Used by our software
			"FORCETOC", "TOC_left", "TOC_right", 
			"Look_from",
			"In_title",
			"Disambiguation_cleanup",
			# parseline()
			"Em_dash",
			"En_dash",
			"Spaced_en_dash",
			# into()
			"Refer",
			# Footers for intro()
			"Disambiguation",
			"Hndis",
			"Geodis",
			# addWiktionary()
			"Infobox_given_name",
			"Infobox_surname",
			"Wiktionary",
			# Other footers
			"School_disambiguation",
			"Airport_disambiguation",
			"Road_disambiguation",
			"Hurricane_disambiguation",
		)
		# Bypass template redirect from [[Wikipedia:AutoWikiBrowser/Template redirects]] and our own list above
		self.cursor.execute("""
SELECT rd_title, tl_title, EXISTS (
	SELECT 1
	FROM page
	JOIN pagelinks ON pl_from=page_id 
	WHERE pl_namespace=10 AND   pl_title=rd_title
	AND page_namespace=? AND page_title=?
) AS awb_bypass
FROM page
JOIN templatelinks  ON tl_from=page_id     AND tl_namespace=10
JOIN page AS tpl    ON tpl.page_namespace=tl_namespace AND tpl.page_title=tl_title
JOIN redirect       ON rd_from=tpl.page_id AND rd_namespace=10
WHERE page.page_namespace=? AND page.page_title=?
""", (4, "AutoWikiBrowser/Template_redirects", self.page.namespace(), self.page.title(underscore=True)), max_time=30)
		for template, redirect, awb_bypass in self.cursor:
			if template in IgnoreTemplate:
				pass
			elif awb_bypass or template in BypassTemplateRedirect or strip_variations(template)==strip_variations(redirect):
				def repl_func(m):
					repl = template.replace(u'_', u' ').replace(u'\\', u'\\\\')
					# Capitalize multilined templates or uses uppercase in the name
					if repl[1:].islower() and u'\n' not in m.group():
						repl = repl[0:1].lower()+repl[1:]
					return repl + m.group(3).lstrip(' \t')
				self.text = re.sub(ur'(?<=\{\{)\s*([Tt]emplate\s*:\s*|)(%s)(\s*)(?=\||\}\})' % wikilinkregex(redirect), repl_func, self.text)
			else:
				wikipedia.output(u"Transclusion redirect: [[Template:%s]] to [[Template:%s]]" % (redirect.replace('_', ' '), template.replace('_', ' '),))

		# Substitute template from [[Category:Wikipedia substituted templates]], like {{refer}}
		self.cursor.execute("""
SELECT tl_title
FROM categorylinks
JOIN page AS tl    ON tl.page_id=cl_from
JOIN templatelinks ON tl_namespace=page_namespace AND tl_title=page_title
JOIN page AS dab   ON dab.page_id=tl_from
WHERE cl_to=? AND dab.page_namespace=? AND dab.page_title=?
""", ("Wikipedia_substituted_templates", self.page.namespace(), self.page.title(underscore=True),), max_time=10)
		for template, in self.cursor:
			self.text = re.sub(ur'\{\{\s*(?:[Tt]emplate\s*:\s*|)(%s)(?=\s*[{|}])'%wikilinkregex(template), ur'{{subst:\1', self.text)
			wikipedia.output(u"Substituting {{%s}}" % template)

		# Remove TOCs and correctly added back with JS
		self.text = re.sub(ur'\n?\{\{(TOC[_ ]+left|TOC[_ ]+right|tocright)\}\}\n?|\n?__(TOC|NOTOC|FORCETOC)__\n?', '\n', self.text)
		# Request of many users to stop making the name less complex
		if '{{TOC right}}\n' in self.page.get(): # \n= <- Only if not removing empty lines
			printu(u'<script type="text/javascript">window.tocright=%s;</script>' % wikipedia.jsescape("TOC right"))
			
		# TODO implement sort key 
		#self.text = re.sub(ur'\{\{hndis\s*(\|(?:\s*name\s*=\s*|(?=[^{|}=]*[|}]))([^{|}]*?))\s*\}\}', ur'{{hndis|\2}}', self.text)
		# |name=Last, First

		# Use {{dismabig}} paramter features
		# See https://en.wikipedia.org/wiki/Template:Disambiguation/cat
		for param, cat in [
			('callsign','Broadcast call sign disambiguation pages'),
			('church',  'Church building disambiguation pages'),
			('county',  'County name disambiguation pages'),
			('fish',    'Fish common name disambiguation pages'),
			('genus',   'Genus disambiguation pages'),
			('geo',     'Place name disambiguation pages'),
			('given name','Disambiguation pages with surname-holder lists'),
			('hospital','Hospital disambiguation pages'),
			('human name','Human name disambiguation pages'),
			('latin',   'Latin name disambiguation pages'),
			('letter number', 'Letter-number combination disambiguation pages'),
			('math',    'Mathematical disambiguation'),
			('number',  'Lists of ambiguous numbers'),
			('plant',   'Plant common name disambiguation pages'),
			('political','Political party disambiguation pages'),
			('road',    'Road disambiguation pages'),
			('school',  'Educational institution disambiguation pages'),
			('ship',    'Ship disambiguation pages'),
			('surname', 'Disambiguation pages with given-name-holder lists'),
			('township','Township name disambiguation pages'),
			('uscounty','United States county disambiguation pages'),
			# Old
			('surname', 'Surnames'),
			('given name', 'Given names'),
		]:
			self.text = re.sub(ur'\{\{(disambig.*?)\}\}(.*?)\n?\[\[Category:%s\]\]'%(wikilinkregex(cat),), ur'{{\1|%s}}\2'%(param,), self.text, flags=re.I | re.S)



	def intro(self):
		# TESTCASES:
		# It may also refer to:
		# '''X''' refers
		# '''X''' can mean:
		# '''X''' can mean the following things.
		# '''X''' can refer to:
		# '''X''' can refer to either:
		# '''X''' can refer to several things:
		# '''X''' can refer to the following:
		# '''X''' can be used to refer to:
		# '''X''' can mean or refer to:
		# '''X''' could mean:
		# '''X''' is the name of:
		# '''X''' is a name and may refer to following persons:
		# '''X''' are the names of:
		# '''X''' may also signify:
		# '''X''' may be:
		# '''X''' may denote to:
		# '''X''' may mean:
		# '''X''' may refer to any of the following:
		# '''X''' may represent
		# '''MM''' or variants may refer to:
		# '''X''' may refer to more than one thing:
		# '''X''' means following
		# '''X''' might refer to one of the following:
		# '''X''' most commonly refers to:
		# '''X''' has several meanings
		# '''X''' has various meanings:
		# '''X''' has the following meanings:
		# A '''X''' can be:
		# The term '''X''' may refer to any one of the following:
		# The word '''X''' can refer to:
		# The expression '''X''' can refer to:
		# Do you mean...
		# '''X''' may refer to several places:
		# '''X''' may refer to several places in [[COUNTRY]]
		# '''X''' may refer to the following places:
		# '''X''' may refer to several villages in COUNTRY:
		# '''X''' may be an abbreviation for:
		# '''X''' is an abbreviation for:
		# '''X''' is a [[three-letter acronym]] that may refer to:
		# '''X''' is a [[TLA|three-letter abbreviation]] and represents
		# '''X''' is an abbreviation that may stand for:
		# '''X''' as an [[abbreviation]] may refer to:
		# '''X''' is associated with placename articles:
		# '''X''' can stand for:
		# '''X''' is an acronym with different meanings. It may refer to:
		# '''X''' is an abbreviation used by:
		# The [[abbreviation]] '''X''' can be:
		# '''X''' is an acronym which may stand for:
		# The name '''X''' could refer to:
		# '''X''' has two principal meanings:
		# '''X''', '''Y''' and '''Z''' may also refer to:
		def refer(m):
			also = ' also' if self.primelinks else m.group('also') or ''
			#if   re.search(ur'\{\{ *[Hh]ndis', self.text)  or ' the name of' in m.group():
			if ' the name of' in m.group():
				return m.expand(ur'\g<subject> is%s the name of:' % also)
			elif re.search(ur'\{\{ *[Gg]eodis', self.text) or ' to several places' in m.group():
				return m.expand(ur'\g<subject> may%s refer to several places:' % also)
			elif re.search(ur'\b(acronym|abbreviation|initial|stand)s?\b', m.group(), flags=re.I):
				# or self.page.title().isupper():
				return m.expand(ur'\g<subject> may%s stand for:' % also)
			else:
				return m.expand(ur'\g<subject> may%s refer to:' % also)
		self.text = re.sub(ur"^(?:A |And |As an? |The |expression |name |term |word |\[*three[ -]letter acronym\]* |\[*acronym\]* |\[*abbreviation\]* )*(?P<subject>('''[^{|}[\]\n']+?''',?( or|)( \(.*?\)?(?#{{lang-en|example}})|) *?)+|^It|Did you|Do you) *( can| could| is| is an?| are| are an?| as| as an?| has| may| might|)(?P<also> also|)([ \-]+(\[\[|\[\[[^{|}[\]<\n>]+\||)(be|be an?|means?|meanings?|refers?|associate[sd]?|represents?|signify|denote|the names?|various|used to|used by|with|which|different|several|an?|abbreviation|two|three|four|five|letter|acronym|initialism|stand|to|of|for|and|that|may|one of|any of|any one of|either|two|three|four|following|the following|several things|more than|one thing|several persons|several people|meanings?|several places|placename|principal|articles?|have|usually)(\]\]|\b))+( in \[\[[^{|}[\]\n]+\]\]|)( \w+|)[:;. ]*?(?= *$)", refer, self.text, flags=re.M | re.U | re.I)

		refer_type = {
			"may refer to":     "|type=",
			"may also refer to":"|type=also",
			"may refer to several places":   "|type=place",
			"may stand for":    "|type=stand",
			"is the name of":   "|type=name",
			"is a surname. Notable people with the surname include":	"|type=surname",
			"is a given name. Notable people with the name include":	"|type=givenname",
		}
		def referTemplate(m):
			titles = re.findall(ur"'''((?:'{0,2}[^'])+'{0,2})'''", m.group('subject'))
			if m.group('subject') in ('It',):
				# Invalid title, make our own
				titles = [re.sub(ur' \(.*\)', ur'', self.page.title())]
			if 0 < len(titles) <= 2 and not any(1 for title in titles if "'''" in title):
				return '{{subst:refer|%s%s}}'%('|'.join(titles), refer_type.get(m.group('refer')),)
			else:
				return m.group()
		self.text = re.sub(ur"(?P<subject>^It|('''('{0,2}?[^{|}[\]<\n>'])+'{0,2}'''[ ,]*( or )?)+) (?P<refer>%s):" % '|'.join(refer_type.keys()), referTemplate, self.text, flags=re.M)
		
		if "{{subst:refer" not in self.text and sum([u"'''" in line.group() for line in re.finditer(ur'^[^#*].*', self.text, flags=re.M | re.U)]) - len(self.primelinks) < 1:
			wikipedia.output('Adding {{refer}}')
#			#TODO should discard minor case variants
#			terms = {}
#			for prefix in self.prefixes:
#				term = u"'''%s'''" % prefix.replace('_', ' ')
#				base = strip_variations(term)
#				if base not in terms:
#					terms[base]=term
#			termstext = EnglishJoin(sorted(terms.values()))
#			self.text = "%s may refer to:\n\n"%(termstext, self.text,)
			self.text = re.sub(ur"(\A.*?)^(?=[=#*;:])", ur"\1{{subst:refer|type=%s}}\n\n"%('also' if self.primelinks else '',), self.text, flags=re.DOTALL | re.M | re.U)
		
		# Keep it easy for users to modify (ex: casing http://enwp.org/?diff=777818984 )
		self.text = self.text.replace('{{subst:refer|type=', '{{subst:refer|%s|type=' % self.PAGENAMEBASE)

	def longcomment(self, add_only=False):
		# Wikipedia template hack for [[Special:ShortPages]]
		# Nothing really standardized.  Template suggests <120 bytes (20 words),
		# but I've found 250 bytes to work better
		#     Added  under 250 bytes (40 words, 300-550 bytes expanded)
		#     Removed over 300 bytes (50 words,   600+  bytes expanded)
		# Note: commonfixes will match and update {{long comment}}
		# FIXME doesn't account for auto descriptions
		addsection_len = sum(len(section_head)+8+len(section_text) for section_head, section_text in self.add_section.iteritems())
		longcmt_tpl = '{{subst:long comment}}' # BTW, this expands to ~300 bytes
		if len(self.text) - addsection_len > 300 + len(longcmt_tpl) and not add_only:
			self.text = self.text.replace(longcmt_tpl, '')          # Remove
		if len(self.text) - addsection_len < 250 and longcmt_tpl not in self.text:
			self.text += "\n\n%s" % longcmt_tpl                     # Add
		
	def removeAutoSections(self, text):
		return re.sub(
			ur"\n(=+) (%s) \1\n+((?![{=}]).*\n*)*$"%'|'.join(re.escape(x) for x in self.add_section.keys()),
			'',
			text,
			flags=re.M
		)
		
	def check_mosdab(self):
		def getParsed(title, text=None):
			import requests
			api_url = 'https://%s/%s' % (self.site.hostname(), self.site.apipath(),)
			params = {
				'action':'parse',
				'format':'json',
				'utf8': 'yes',
			}
			if text==None: 
				params['page'] = title
				return requests.get(api_url, params=params).json()
			else:
				params['title'] = title
				return requests.post(api_url, params=params, data={'text':text}).json()
		
		if not mosdabbot:
			error('ImportError: mosdabbot module not found')
			return
		
		# Avoid Redlink related (F N O), Dating (D), or description length (X)
		problems_mask = set('B C E M P R S H L U'.split()) 
		
		# Run check to see what we've changed
		oldp = getParsed(self.page.title())
		if 'error' in oldp:
			if oldp['error']['code']!='missingtitle':
				error("%s: %s" % (oldp['error']['code'], oldp['error']['info'],))
			return 
		old = mosdabbot.enwiki_mosdab(oldp[u'parse'], 'enwiki_p')
		old_mos = set(old['issues'])
		# Query anyway to always show preview
		self.html_json = getParsed(self.page.title(), self.removeAutoSections(self.text))
		new = mosdabbot.enwiki_mosdab(self.html_json[u'parse'], 'enwiki_p')
		new_mos = set(new['issues']) - set(['X']) # Remove auto-description effects
		
		# XXX Should use <ins>/<del> and function to generate the difference
		combined_html = re.sub(
			ur'<li >([^<:>]+)',
			lambda m: m.expand(ur'<li style="text-decoration:line-through">\1') if m.group() not in new['mbox'] else m.group(),
			old['mbox']
		)
		#print mosdabbot.lifespan_cache
		printu(combined_html.replace('<ul style="max-width:35em;">', '<ul>'))
		if new_mos-old_mos:
			debug("New MOS:DAB errors were introduced (%s)" % ', '.join(new_mos-old_mos))
		
		# TODO support {{hndis}}
		if '{{disambiguation cleanup' in self.text:
			oldcleanuptag = "{{disambiguation"
		else:
			problems = new_mos & problems_mask
			oldcleanuptag = '{{disambiguation cleanup|date=%s%s' % (time.strftime('%B %Y'), '|mosdab=%s' % ','.join(problems) if problems else '',)
		printu(u'<script type="text/javascript">window.oldcleanuptag=%s;</script>' % wikipedia.jsescape(oldcleanuptag))
		htmlout(u'<input type="hidden" id="oldcleanuptag" value="%s" />', (oldcleanuptag,))

		if old_mos - new_mos:
			printu(u'<!-- edit summary: %s -->' % (','.join(old_mos-new_mos),))

	def run(self):
		def runsection(func, suppress_errors = () ):
			try:
				func()
				wikipedia.logtime('%s()' % func.__name__)
				sys.stdout.flush()
			except toolsql.QueryTimedOut as e:
				wikipedia.logtime('%s() -- %r' % (func.__name__, e,))
				error(u'Routine %s(): Database query timed out (%d seconds)' % (func.__name__, self.cursor.elapsedtime, ))
			except oursql.OperationalError as (errno, strerror, extra):
				wikipedia.logtime('%s() -- %r' % (func.__name__, strerror,))
				error(u'Routine %s(): Database operational error %s\n%s' % (func.__name__, errno, strerror,))
			except suppress_errors as e:
				wikipedia.logtime('%s() -- %r' % (func.__name__, e))
				error(u'Routine %s() failed\n%r' % (func.__name__, e))
				if wikipedia.Debug:
					raise
		
		title = self.page.title()
		# {{PAGENAME}} produces &#39; so it doesn't interfere with bold/italic markup
		self.PAGENAMEBASE = re.sub(ur'[_ ]+\(.*\)$', ur'', self.page.title()).replace("'", '&#39;')
		if not title:
			wikipedia.output(__doc__)
			return
		if title.startswith(('Special:WhatLinksHere/',)):
			target = wikipedia.Page(site, title[title.index('/')+1:])
			htmlout(u'<img src="//bits.wikimedia.org/skins-1.5/common/images/redirectltr.png" alt="Redirect" /><a href="?page=%s" class="redirectText">%s</a>', (target.title(asUrl=True, allowInterwiki=True), target.title(),))
			return
		try:
			wikipedia.logtime('Prep done')
			self.text = self.page.get()
			wikipedia.logtime('page.get()')
		except wikipedia.IsRedirectPage as (target,):
			self.summaryflags['redirect'] = True
			htmlout('<p><big>Converting redirect <b><a href="https://%s/%s">%s</a></b> to a disambiguation page </big> <br />', (
				self.site.hostname(),
				self.site.get_address(self.page.title(asUrl=True)),
				self.page.title(),
			))
			self.target = wikipedia.Page(self.site, target)
			htmlout('Run Dabfix instead on <b><a href="%s/%s">%s</a></b></p>', (
				"/~dispenser/cgi-bin/dabfix.py",
				self.target.title(asUrl=True),
				self.target.title(),
			))
			self.text = re.sub(ur'.*?(\[\[[^[\]\n]*?\]\]).*', ur'{{subst:refer|type=}}\n\n* \1\n', self.page.get(get_redirect=True), flags=re.DOTALL)
		except wikipedia.BadTitle:
			raise
		except wikipedia.NoPage as e:
			# FIXME subclass NoPage in wikipedia.py 
			if e.message in ("Page does not exist.", ):
				# XXX Messing with pywikipedia internals
				self.page._contents = ""
				self.summaryflags['create'] = True
				self.text = "{{subst:refer|type=}}"
			else:
				wikipedia.output(u'%s: NoPage( %s )' % (self.page.aslink(), e.message))
				return


		#except Exception as e:
		#	wikipedia.output('Exception: %r' % (e,))
		#	return
		# Load WikEd after initializing wgPageName
		print '<script type="text/javascript">importScriptURI("//en.wikipedia.org/w/index.php?title=User:Cacycle/wikEd.js&action=raw&ctype=text/javascript");</script>'
	
		print '<a id="Hide_details" href="#Hide_details" class="bigbutton" onclick="toggleDebug(this); return false"><span style="float:left">&#9660;</span> Show details <span style="float:right">&#9660;</span></a>'
		print '<div style="clear:both;"></div>'
		headings.append("Hide details")
		if self.page.wpEdittime:
			htmlout('<p>Last edited on %s</p>', (
				time.strftime('%d %B %Y', time.strptime(self.page.wpEdittime, '%Y%m%d%H%M%S')),
			))
		
		# Setup: Majority vote on bullet style, see parseline()
		self.bullet_space   = sum(1 for m in re.finditer(r'^[#*]+ ',  self.page.get(), flags=re.M))
		self.bullet_nospace = sum(1 for m in re.finditer(r'^[#*]+\S', self.page.get(), flags=re.M))
		#if self.page.isRedirectPage():
		if self.target: # if redirect
			self.bullet_nospace = 0
		self.bullet_space_ratio = 1 - self.bullet_nospace / float(self.bullet_nospace + self.bullet_space or 1)
		#if 0 < min(self.bullet_nospace, self.bullet_space) < (self.bullet_space + self.bullet_nospace) // 20:
		#	# Add spaces (per [[MOS: ]]) or remove to keep uniform
		#	# Overwheling single sided
		#	self.text = re.sub(ur'^([#*]+:*) *', ur'\1 ' if self.bullet_space_ratio > 0.5 else ur'\1', self.text, flags=re.M)

		# Determine ruleset
		self.cursor.execute("""
SELECT 1
FROM page_props 
WHERE pp_propname="disambiguation"
AND pp_page = ?
""", (self.page.id,))
		self.page.is_disambig = self.cursor.fetchall()

		# setup
		# Operations before text is changed
		runsection(self.template_redirect)
		runsection(self.doubleredirect)
		
		runsection(self.getprefixes) # initialize
		runsection(self.primary_entry)
		runsection(self.cleanprefixes)
		runsection(self.intro)
		runsection(self.mosfixes)

		# Generate links
		runsection(self.addWiktionary)
		runsection(self.bluelinks)
		runsection(self.redlinks)
		runsection(self.seealso)

		## Commonfixes
		if self.usecommonfixes:
			heading(2, 'Common fixes', className="debug")
			import commonfixes
			self.text = commonfixes.fix(self.text, page = self.page, verbose = False)
			import cgitb; cgitb.enable(logdir='tracebacks')
			#import cgitb; cgitb.enable(logdir=None, display=1, format="html")#logdir='tracebacks')
			wikipedia.logtime("Applied common fixes")
		else:
			# Unpipe text
			self.text = re.sub(ur'\[\[([^{|}[\]]+)\s*\|\s*\1\s*\]\]', ur'[[\1]]', self.text)
			self.text = re.sub(ur'(?i)\[\[([^{|}[\]\n]+)([^{|}[\]\n]+)\|\1\]\]\2', ur'[[\1\2]]', self.text)
		
		# run after creating blue links
		self.text = re.sub(ur'(?<=\[\[)[^{|}[\]\n#]+(?=(?:#[^{|}[\]\n]*|) *(?:\|.*?|)\]\])', self.skipredirect, self.text)
		
		self.longcomment() # XXX because parseline adds text unaccounted for 
		
		print '<div class="entry">' 
		heading(2, "Entry cleanup", className="debug")
		self.text = re.sub(ur'^:*[#*\-\u00B7\u2022]+.*$\n?', self.parseline, self.text, flags=re.M)
		wikipedia.logtime("parseline() %dx"%(self.parselinecounter,))
		print '</div>'

		self.text = re.sub(ur"(m)^(?P<subject>('''[^{|}[\]\n']+?''',?( or|) *)+) may be an abbreviation for[:;]? *$", ur"\g<subject> may stand for:", self.text)
		# Create wikEd.linkInfo for WikEd to color links
		printu('<script type="text/javascript">window.linkInfo=%s;</script>' % wikipedia.jsescape(linkInfo).replace('},"', '},\n"'))
		# Keep track in JavaScript for removal
		for section_head in self.add_section.keys():
			printu(u'<script type="text/javascript">AddedSection(%s, /%s/);</script>' % (
				wikipedia.jsescape(section_head),
				ur"[\r\n]+(=+) %s \1[\r\n]+((?![{=}]).*[\r\n]*)*"%re.escape(section_head),
			))
	
		self.longcomment(add_only=True)
	
		heading(2, "Diff", className="debug")

		runsection(self.check_mosdab, ValueError)

		difftext = re.sub(
			ur"^(=+) (%s) \1\n+((?![{=}]).*\n*)*$"%'|'.join(re.escape(x) for x in self.add_section.keys()),
			# 1 header + 2 sample entries = 3, +2 to avoid single/plural
			lambda m: '\n'.join(m.group().split('\n')[0:3] + ['    + %d more entries' % (m.group().count('\n')-3), '']) if m.group().count('\n') + 1 > 3+2 else m.group(),
			self.text,
			flags=re.M
		)
		template_replacements = [
			[u'{{subst:refer|%s|type=' % self.PAGENAMEBASE,  u'{{subst:refer|type='],
			[u'{{subst:refer|type=also}}',  u"'''{{subst:PAGENAMEBASE}}''' may also refer to:"],
			[u'{{subst:refer|type=stand}}', u"'''{{subst:PAGENAMEBASE}}''' may stand for:"],
			[u'{{subst:refer|type=name}}',  u"'''{{subst:PAGENAMEBASE}}''' is the name of:"],
			[u'{{subst:refer|type=place}}', u"'''{{subst:PAGENAMEBASE}}''' may refer to several places:"],
			[u'{{subst:refer|type=}}',      u"'''{{subst:PAGENAMEBASE}}''' may refer to:"],
			[u'{{subst:PAGENAME}}',         self.page.title()],
			[u'{{subst:PAGENAMEBASE}}',     self.PAGENAMEBASE],
			[u'{{subst:long comment}}', u'{{Short pages monitor}}<!-- This long comment was added to the page to prevent it from being listed on Special:Shortpages. It and the accompanying monitoring template were generated via Template:Long comment. Please do not remove the monitor template without removing the comment as well.-->'],
		]
		printu('<script type="text/javascript">window.template_replacements = %s;</script>' % (wikipedia.jsescape(template_replacements),))
		for old, new in template_replacements:
			difftext = difftext.replace(old, new)
		wikipedia.showDiff(self.page.get(), difftext.rstrip())
		wikipedia.logtime("Diff")
		
		if self.page.revisionid:
			self.cursor.execute("SELECT page_latest FROM page WHERE page_namespace=? AND page_title=?", (self.page.namespace(), self.page.titleWithoutNamespace(underscore=True),), max_time=3)
			if self.cursor.fetchall() != [(self.page.revisionid,)]:
				#print '<!--', self.site.dbName(), self.page.namespace(), self.page.titleWithoutNamespace(underscore=True), self.cursor.fetchall(), '-->'
				from resources_dab_solver import OutOfSync
				printu(u'<div class="mw-warning">%s</div>' % (wikipedia.translate(self.site, OutOfSync),))
			wikipedia.logtime("check revisionid")
	
		MyButtons = [
			("btnAutoDesc",   "removeDescriptions();", "Remove Description Start"),
			("btnAutoSec",    "removeSections();",     "Remove Link Suggestions"),
			("btnCleanupTag", "toggleCleanup();",      "Un/tag for cleanup"),
		]
		print('<div id="toolbar">%s</div>' % '\n'.join('<input type="button" id="%s" onclick="%s; return false" value="%s" />'%tup for tup in MyButtons))
		headings.append("editform") 
		self.page.put(self.text, comment={
			'topic:outdated_dabs-enwiki.log': 'Update lifespans',
			'topic:invalid_wiktionary_links.log': 'Fix invalid Wiktionary link',
		}.get(wikipedia.SysArgs.get('client'), ''), minorEdit=False)
		print('<script type="text/javascript">document.getElementById("wpSummary").placeholder = %s;</script>' % wikipedia.jsescape(self.edit_summary()))
		wikipedia.logtime("page.put()")
		
	
		if self.html_json:
			heading(2, "Preview")
			printu('<div id="WikiPreview">%s</div>' % self.html_json[u'parse']['text']['*'].replace(u' href="/w', u' href="https://%s/w'%self.site.hostname()))
			printu('''<script type="text/javascript">
(function(){
var WikiPreview=document.getElementById("WikiPreview"); 
var instaView=WikiPreview.innerHTML;
for(var adesc, i=0; (adesc=autodescript[i]); i++) {
	instaView = instaView.split(adesc.text).join('<span class="autodesc '+(adesc.text.length > autodesc_max?'remove':'')+'">' + adesc.text + '</span>');
}
WikiPreview.innerHTML = instaView;
})();
</script>''')
		
		#
		#runsection(self.print_related_projects)

		heading(2, "Timeline", className="debug")
		print '<pre class="debug">%s</pre>' % (wikipedia.escape(wikipedia.timereport()),)

		# Floating ToC
		print '<div class="portlet quickjump debug">'
		print '<h5>Table of contents</h5>'
		print '<div class="pBody"><ul>'
		for section in headings:
			print '<li><a href="#%s">%s</a></li>' % ( wikipedia.sectionencode(section), section)
		print '</ul></div></div>'
	
	def print_related_projects(self):
		if not self.site.dbName().startswith('enwiki'):
			return
		self.cursor.execute('''/* dabfix */
SELECT 
  COUNT(*) AS "Links",
  REPLACE(pb_title, "_", " ") AS "Project",
  pl_title AS "Example"
FROM pagelinks
JOIN u2815__p.projectbanner ON pb_page = pl_from
WHERE pl_namespace=0 AND pl_title IN (%s)
GROUP BY 2
ORDER BY COUNT(*) DESC
LIMIT 10
''' % ','.join(('?',)*(1+len(self.redirects))), tuple([self.page.titleWithoutNamespace(underscore=True)]+self.redirects))
		if self.cursor.rowcount:
			print '<div class="debug" style="clear:both;">'
			printu(cursor.htmltable(caption='Links covered by WikiProjects'))
			print '</div>'
		
def main():
	print '''<div style="margin:0 auto 3em; max-width:40em; text-align:center;">
	<form action="../cgi-bin/dabfix.py">
	<input accesskey="f" id="page" name="page" value="" onchange="fixTitle(this)" style="margin:1em 0; width:99%; padding:0.2em; box-sizing:border-box;" placeholder="Page title or URL"><br>
	<button class="mw-ui-button" style="width:15em">Run Dabfix</button><a class="mw-ui-button" style="width:15em;" href="../cgi-bin/godab.py?tool=dabfix.py&amp;file-random=temp/logs/invalid_wiktionary_links.log&amp;wpSummary=Fix/Remove_invalid_Wiktionary_link_and_cleanup_using_[[tools:~dispenser/cgi-bin/dabfix.py|Dabfix]]">Random Cleanup</a>
	</form>
</div>'''
	robot = Robot()
	robot.run()

if __name__ == "__main__" and wikipedia.handleUrlAndHeader(defaultRedirect='/~dispenser/view/Dabfix'):
	try:
		wikipedia.startContent(form=False,
			head=r"""<style type="text/css">
#mw_portlets { z-index:1; }
a.bigbutton {
	background:#eee;
	border:1px solid;
	color:#777;
	display:block;
	font:bold 2em/200% sans-serif;
	padding:0 3em;
	text-align:center;
	text-decoration:none;
}
a.bigbutton:hover {
	color:#000;
}
html.theme-dark a.bigbutton {
	background:#333;
	color:#fff;
}
html.theme-dark a.bigbutton:hover {
	color:yellow;
}
.quickrelated {
	padding:0.5em;
	float:right;
	text-align:center;
}
.quickjump {
	position:fixed;
	_position:absolute;
	background-color:#fff;
	background-color:rgba(255, 255, 255, .8);
	border:1px solid #ccc;
	right:1em;
	top:16em;
	width:13em;
}
table.wikitable {
	overflow:hidden;
	margin:auto;
}
.info  { background:url(//upload.wikimedia.org/wikipedia/commons/7/75/Information-silk.png) no-repeat right; }
.warn  { background:url(//upload.wikimedia.org/wikipedia/commons/4/49/Error.png) no-repeat right; }
.error { background:url(//upload.wikimedia.org/wikipedia/commons/c/c0/Exclamation.png) no-repeat right; }
.warn span, .error {
	font-weight:bold;
}
.warn span {
	color:orange;
}
.delete {
	background-color:#ffdbdb;
}
html.theme-dark .delete {
	background-color:#621;
}
.toollinks {
	background:#eee;
	color:#000;
}
html.theme-dark .toollinks {
	background:#333;
	color:white;
	border-bottom:0.1em dotted;
}

@media screen and (max-width:600px) {
	a.bigbutton { padding:0 10%; }
	.quickrelated, .quickjump { display:none; }
	.quickjump { position:static; }
	.table-overflow { overflow-x:auto; width:100vw; }
	.table-overflow th { white-space:nowrap; }
}

#toolbar {
	clear:both;
	text-align:center;
}
.columns {
	-webkit-column-width:30em;
	-moz-column-width:30em;
	list-style-position:inside;	/* WebKit bug #23053 */
}
.columns ul, .columns ol {
	-webkit-column-span:1;
	-moz-column-span:1;
	column-span:1;
	-webkit-break-inside:avoid;
	-moz-break-inside:avoid;
	break-inside:avoid;
}
span.mw-editsection {
 display:none;
}
samp {
	background:#eee;
	color:#000;
	border:1px solid navy;
	border-radius:4px;
	padding:2px;
}
a.rl_expand {
	border-bottom:1px dotted blue;
}
dl.mosdab dt {
	display:none;
}
dl.mosdab dd {
	display:list-item; 
}
/* Highlight years in preview */
.year { background-color:#fff; color:#000; -border:1px dashed #ccc;}
.autodesc { background-color: #ffd700; color: black; }
.sistersitebox { border:1px solid #aaa;background-color:#f9f9f9; float:right; width:238px;}
/* WikEd extra styles */
#wikEdInputWrapper {
 -background:#eee;
 padding:2px 0.5em 0;
}
.wikEdPreviewArticle {
  background:#C0C0C0;
  color:#000;
}
html.theme-dark iframe.wikEdFrame {
  background-color:white;
  color:black;
  filter:invert(1) hue-rotate(180deg);
}
html.theme-dark .wikEdPreviewArticle {
  background:none;
  color:inherit;
}
html.theme-dark .wikEdConsoleWrapper {
	background-color:#000;
}
html.theme-dark .blame {
	background-color:#125;
	color:#ccc;
}

.blame {
 background-color:#def;
 color:#000;
 border:3px solid gray;
 margin:0.2em 2em;
 padding:0.2em;
}
.blame table.diff { width:100%; }
/* Having fun */
.blink {
  animation:blink-animation 1.5s steps(15, start) infinite;
}
@keyframes blink-animation {
  to {
    /*visibility:hidden;*/
	opacity:0;
  }
}


/* Imported from MediaWiki */
div.mw-warning-with-logexcerpt, div.mw-lag-warn-high,
div.mw-cascadeprotectedwarning, div#mw-protect-cascadeon,
div.titleblacklist-warning, div.locked-warning {
    clear: both;
    margin: 0.2em 0px;
    border: 1px solid #BB7070;
    background: #FFDBDB none repeat scroll 0% 0%;
    padding: 0.25em 0.9em;
}


</style>
<style type="text/css" id="debugstyle">.debug, hr { display:none; }</style>
<link rel="icon" type="image/png" href="https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/Edit-clear.svg/16px-Edit-clear.svg.png" />
<!-- InstaView (local preview) -->
<script src="https://en.wikipedia.org/w/index.php?title=User:Pilaf~enwiki/include/instaview.js&amp;action=raw&amp;ctype=text/javascript" type="text/javascript"></script>
<script type="text/javascript">//<![CDATA[
"use strict";
// WikEd mw stub
var mw = {hook: function(){return this}, add:function(){return this}}

//
var autosection = []; // Regex
var autosectionname = []; // Section name
var autodescript = [];
var autodesc_max = 100; // Max 100 characters
var tocright = "tocright";

function AddedSection(sectionname, sectionregex) {
	autosection.push(sectionregex);
	autosectionname.push(sectionname);
}
function removeSections() {
	if(wikEd.useWikEd) {
		wikEd.UpdateTextarea();
		wikEd.textareaUpdated = true;
	}
	try { suggestSummary(); } catch(e) {}
	var editbox = document.getElementById('wpTextbox1');
	var failList = [];
	for (var sec_R, i=0; (sec_R=autosection[i]); i++) {
		if(!editbox.value.match(sec_R)) {
			failList.push(autosectionname[i]);
		}
		editbox.value = editbox.value.replace(sec_R, "\r\n\r\n");
	}
	if(wikEd.useWikEd) {
		wikEd.UpdateFrame();
	}
	if(failList.length > 0) {
		window.alert("Unable to remove the following sections:\n\n"+failList.join('\n') );
	}
}
function AddedDescription(title, s) {
	autodescript.push({
		"title": title,
		"text": s,
	});
}
function removeDescriptions() {
	if(wikEd.useWikEd) {
		wikEd.UpdateTextarea();
		wikEd.textareaUpdated = true;
	}
	try { suggestSummary(); } catch(e) {}
	var editbox = document.getElementById('wpTextbox1');
	var failList = [];
	editbox.value = editbox.value.replace(/\r?\n|\r[^\n]/g, '\n');
	for(var adesc, i=0; (adesc=autodescript[i]); i++) {
		var exists = (editbox.value.indexOf(adesc.text + '\n') == -1);
		if(!exists) {
			failList.push([ "* [[", adesc.title, "]]", adesc.text ].join(''));
		}
		editbox.value = editbox.value.split(adesc.text + '\n').join('\n'); // replace all
	}
	if(wikEd.useWikEd) wikEd.UpdateFrame();
	/* This code may not be need anymore
	if(failList.length) {
		window.alert([
			"Failed to removed "+(failList.length)+" of "+(i),
			'',
			'',
			failList.join('\n') 
		].join('\n'));
	} else {
		window.alert("Removed all ($1)".replace('$1', i));
	} /*-*/
}
/*

/* Crap code */
var AutoSummaries = false;
function suggestSummary() {
	var wpSummary = document.getElementById('wpSummary');
	var editbox = document.getElementById('wpTextbox1');
	var summaryUsing = ' using [[tools:~dispenser/cgi-bin/dabfix.py|Dabfix]]';

	try {
		if(!AutoSummaries) return;
		if(editbox.value.length > 12*1024) return;
	} catch(e) {
		return;
	}

	var link_R = /\[\[([^[\]{|}]+)(?:\|[^[\]{|}]+)?\]\]/g;
	var orig_lines = {};
	var suggested_links = {};
	var kept_links = [];
	var is_dirty = false;
	var text, link;
	var old_text = editbox.defaultValue.replace(/\r?\n/, "\n");
	var new_text = editbox.value.replace(/\r?\n/, "\n");
	// Figure out what was suggested
	for (var sec_R, i=0; (sec_R=autosection[i]); i++) {
		text = old_text.match(sec_R);
		link_R.lastIndex = 0; // Fix design bug
		while(text && (link = link_R.exec(text[0])) !== null) {
			suggested_links[link[1]] = true;
		}
		old_text = old_text.replace(sec_R, "\n\n");
		new_text = new_text.replace(sec_R, "\n\n");
	}
	for(var adesc, i=0; (adesc=autodescript[i]); i++) {
		if(old_text.indexOf(adesc.title) != -1)
			old_text = old_text.split(adesc.text).join('');
	}
	for(var line, j=0; (line=old_text.split('\n')[j])!=null; j++){
		orig_lines[line] = true;
	}
	// Mark what was kept
	for(var line, j=0; (line=new_text.split('\n')[j])!=null; j++) {
		if( orig_lines.hasOwnProperty(line) ) {
			// Line unchanged
		} else {
			var link_added = false;
			link_R.lastIndex = 0; // Fix design bug
			while((link = link_R.exec(line)) !== null) {
				if(suggested_links.hasOwnProperty(link[1])) {
					kept_links.push(link[1]);
					link_added = true;
				}
			}
			if(!link_added) is_dirty = true;
		}
	}

	wpSummary.placeholder =	( 
	0 < kept_links.length && kept_links.length <= 5 ? 
		'Adding [[' + kept_links.join(']] and [[') + ']]'
		+ ( is_dirty ? ' and cleanup' : '')
	:
		'Cleanup per [[WP:MOSDAB]]'
	) + summaryUsing;
}

/*-*/


addOnloadHook(function(){
	var editform = document.getElementById('editform');
	if(editform) {
		AutoSummaries = editform.wpSummary.placeholder == "Cleanup per [[WP:MOSDAB]] using [[tools:~dispenser/cgi-bin/dabfix.py|Dabfix]]";
		editform.onsubmit = function() {
			var editbox = document.getElementById('wpTextbox1');
			var unmodified = editbox.defaultValue===editbox.value;
			function countAD() {
				var count = 0;
				for(var adesc, i=0; (adesc=autodescript[i]); i++)
					if(editbox.value.indexOf(adesc.text + '\n')!==-1)
						count++;
				return count;
			}
			var adTotal = autodescript.length - countAD();  // Adjust because ?
			
			// Remove autosections
			for(var sec_R, i=0; (sec_R=autosection[i]); i++) {
				var m=editbox.value.match(sec_R);
				if(m) {
					// Skip if section is empty
					if((m[2] || "").match(/^\s*$/)) { // XXX $2 is only the first line
						editbox.value = editbox.value.split(m[0]).join("\r\n\r\n");
					 	continue;
					}
					if(window.confirm("Remove Link Suggestions")) {
						removeSections();
					} else {
						return false;
					}
					break;
				}
			}
			if(wikEd.useWikEd) wikEd.UpdateFrame();
			
			// Remove long autodescriptions
			for(var adesc, i=0; (adesc=autodescript[i]); i++) {
				if(adesc.text.length > autodesc_max && editbox.value.indexOf(adesc.text + '\n')!==-1) {
					if(window.confirm("Descriptions should be terse.\nRemove Description Starts?")) {
						removeDescriptions();
					} else {
						return false;
					}
					break;
				}
			}
			if(wikEd.useWikEd) wikEd.UpdateFrame();
			
			// Useful bug: Undercount?, Doesn't work right after removeSections()
			var count = countAD();
			var ratio = Math.round(1000.0 * count / (adTotal + count)) / 10.0; // Format ##.#
			var msg = [
				(ratio==100.0 ? "All" : (ratio >= 90.0 ? "Most" : ratio+"% of")) +" descriptions ("+count+") remain in their automatic form.",
				"Use 'Remove Description Start' button to remove unmodified Description Starts.",
				"",
				"Continue anyway?"
			].join('\n');
			if(ratio > 80.0 && !window.confirm(msg)) {
				return false;
			}
			
			// Check {{disambiguation cleanup|mosdab=}}
			var cleanuptpl = editbox.value.match(cleanup_tpl_R);
			if(cleanuptpl && // Has template
				// We added or was originally there
			   (window.autocleanup || editbox.defaultValue.match(cleanup_tpl_R)) &&
			   !window.confirm("Keep {{$1}} tag?\n\n[OK=Keep] [Cancel=Remove]".replace('$1', cleanuptpl[1]))){
				toggleCleanup();
			}


			editbox.value = editbox.value.replace(/\n+(?=\n\n)/g, "");  // remove double newlines
			editbox.value = editbox.value.replace(/^\s+|\s+$/g, "");    // Trim field
			editbox.value = editbox.value.replace(/\{\{(refer|refers|May refer to|Mayreferto|Mayrefer|Disambiguation lead|Disambiguation lead name|ftq|fti)(?=\s*\||\s*\}\})/gi, "{{subst:$1"); // subst: templates

			// {{tocright}}
			if((editbox.value.match(/[\n\r](=+).*?\1/g)||"").length<=3) {
				// Zero to two headings
				// Avoid {{tocright}} with infoboxes
				if(!editbox.value.match(/\{\{Infobox/i)) { //}} fix IDE highter
					editbox.value = editbox.value.replace(/\n?\{\{tocright\}\} *\n?/,"\n");
				}
			} else if(editbox.value.indexOf("{{"+window.tocright+"}}")==-1) {
				editbox.value = editbox.value.replace(/^([\s\S]*?)([\r\n]=+.*?=+ *[\r\n])/, "$1\n{{"+window.tocright+"}}$2");
			} else {
				// exists
			}
			
			// Remove {{long comment}} over 300 bytes
			var longcmt_tpl = '{{subst:long comment}}';
			if(editbox.value.length > 300 + longcmt_tpl.length)
				editbox.value = editbox.value.replace(longcmt_tpl, "");
			
			// Set edit summary
			try { suggestSummary(); } catch(e) {}
			var wpSummary = document.getElementById('wpSummary');
			if(wpSummary.value == "")
				wpSummary.value = wpSummary.placeholder || wpSummary.defaultValue;

			var summaryUsing = ' using [[tools:~dispenser/cgi-bin/dabfix.py|Dabfix]]';
			if(wpSummary.value.indexOf(' using [[') == -1 && wpSummary.value.length + summaryUsing.length < 250) {
				wpSummary.value += summaryUsing;
			}

			warnOnLeave=false;
			return true;
		};
	}

	// Update Tag for cleanup
	updateCleanupBtn() 

	// XXX Override WikEd UpdateFrame to add our own coloring code
	wikEd.MyUpdateFrame = wikEd.UpdateFrame;
	wikEd.UpdateFrame = function(html) {
		if(html === undefined) {
			html = wikEd.EscapeHtml(wikEd.textarea.value);
		}
		// convert \xa (nbsp) to character entities so they do not get converted to blanks
		html = html.replace(/\xa0/g, '&amp;nbsp;');

		for(var adesc, i=0; (adesc=autodescript[i]); i++) {
			var desc = wikEd.EscapeHtml(adesc.text);
			//var desc_R = new RegExp(regex_escape(desc) + '$', 'gm');
			// Hack because "]]'', description" screws up WikEd
			html  = html.replace(desc.replace(/^[, ]?/, '')+'\n', '<span class="wikEdKeep autodesc '+(adesc.text.length > autodesc_max?'remove':'')+'">$&</span>').replace(/\n<\/span>/g, '</span>\n');
		}
		html = html.replace(/^((=+) *)(.+?)( *\2 *)$/gm, function(match, p1, p2, p3, p4) {
			for(var secname, i=0; (secname=autosectionname[i]); i++) {
				if(p3==secname) return p1+'<span class="wikEdKeep autosechead">'+p3+'</span>'+p4;
			}
			return match;
		});
		// Highlight no link lines
		html = html.replace(/^([*#]+)([^{|}[\]<\r\n>]+?)$/gm, '$1<span class="wikEdKeep wikEdHtmlUnknown">$2</span>');
		// Highlight years for easier reading
		html = html.replace(/\b1[6-9]\d\d\b|\b20\d\d\b/g, '<span class="year">$&</span>');
		wikEd.MyUpdateFrame(html);
	};
	// X-domain POSTs aren't possible, settle for InstaView
	wikEd.MyLocalPreview = wikEd.LocalPreview;
	wikEd.LocalPreview   = function() {
		// prepare a local preview (Pilaf's InstaView)
		if(typeof InstaView == 'object') {
			InstaView.conf.user = {
				name: window.wgUserName, 
				signature: '[[User:$1|$1]]'.replace(/\$1/g, window.wgUserName)
			};
			InstaView.conf.paths = {
				articles:   window.wgServer+'/wiki/',
				math:       window.wgServer+'/math/',
				images:     '//upload.wikimedia.org/wikipedia/'+window.wgContentLanguage+'/',
				images_fallback: '//upload.wikimedia.org/wikipedia/commons/',
				magnify_icon: window.wgServer+'/skins-1.5/common/images/magnify-clip.png'
			};
			InstaView.conf.locale.image = "File";
			wikEd.UpdateTextarea();
			wikEd.textareaUpdated = true;
			try { suggestSummary(); } catch(e) {}
			var text = wikEd.textarea.value;
			// Templates
			for(var repl, i=0; (repl=window.template_replacements[i])!==undefined; i++) {
				text = text.split(repl[0]).join(repl[1]);
			}
			text = text.replace(/\{\{(?:Disambiguation|Hndis|Given name|Surname)(\|[^{|}]*)*\}\}/gi, [
				'<table id="disambigbox" style="border:solid #ccc;border-width:1px 0; margin:0.9em 1em; width:100%;"><tr>',
				'<td class="mbox-image">[[File:Disambig_gray.svg|30px]]</td>',
				'<td class="mbox-text" style="padding: 0.25em 0.4em; font-style: italic;">$&</td>',
				'</tr></table>'
			].join('\n'));
			text = text.replace(/\{\{(?:[Ww]iktionary)\|*([^{|}]*)*\}\}/g, [
				'<table class="mbox-small plainlinks sistersitebox" style=""><tr>',
				'<td class="mbox-image">[[File:Wiktionary-logo-v2.svg|40px]]</td>',
				'<td class="mbox-text plainlist">Look up <i><b><a href="//en.wiktionary.org/wiki/$1" class="extiw">$1</a></b></i> in Wiktionary, the free dictionary.</td>',
				'</tr></table>'
			].join('\n'));
			text = text.replace(/\{\{(?:Interlanguage link|ill|link|link-interwiki)(\|[^{|}]+)\|([^{|}]+)(\|[^{|}]+)?\}\}/gi, function(match, p1, p2, p3) {
				if(p2.indexOf('WD=Q')==0) // Wikidata
					return '[['+p1.substring(1)+']] <small>([[d:'+p2.substring(3)+'|]])</small>';
				else // Language
					return '[['+p1.substring(1)+']] <small>([[w:'+p2+':'+(p3 || p1).substring(1)+'|'+p2+']])</small>';
			});
			//// Pipe trick
			//text = text.replace(/\[\[(([^{|}[\]]*:)?([^{|}[\]]+?)(\([^{|}[\]]+\))?)\|\]\]/g, "[[$1|$3]]");
			// Run instaview
			var instaView = InstaView.convert(text);
			// Make redlinks
			instaView = instaView.replace(/(<a href='[^"']*\/wiki\/([^']*)')>/g, function(m, p1, p2){
				var link = decodeURIComponent(p2).replace(/(^|:)(.)/g, function (p, p1, p2) { return p.toUpperCase(); });
				var x = wikEd.linkInfo[link.replace(/ /g, '_')]
				return p1 + (x && x.updated && x.missing ? ' class="new"' : '') + '>';
			});
			// Highlight autodescriptions
			for(var adesc, i=0; (adesc=autodescript[i]); i++) {
				instaView = instaView.split(adesc.text).join('<span class="autodesc '+(adesc.text.length > autodesc_max?'remove':'')+'">' + adesc.text + '</span>');
			}
			// Highlight years
			instaView = instaView.replace(/(?:\b1[6-9]\d\d\b|\b20\d\d\b)(?![^<>]*>)/g, '<span class="year">$&</span>');
			wikEd.previewArticle.innerHTML = instaView;
			
			// init sortable tables (wikibits.js)
			if (typeof sortables_init == 'function')
				sortables_init();
			
			// init collapsible tables (common.js)
			if (typeof createCollapseButtons == 'function')
				createCollapseButtons();

			// Show elemenet (Why didn't Cacycle make a function?)
			wikEd.previewArticle.style.display = 'block';
			wikEd.previewDiff.style.display = 'none';
			wikEd.localPrevWrapper.style.display = 'block';
		}
	};
});

function toggleNode(node) {
	node.style.display = (node.style.display!=='' ? '' : 'none');
}
function toggleDebug(node) {
	var debugstyle = document.getElementById("debugstyle");
	if(debugstyle.disabled){
		node.innerHTML = node.innerHTML.replace('Hide details', 'Show details');
		debugstyle.disabled = false;
	} else {
		node.innerHTML = node.innerHTML.replace('Show details', 'Hide details');
		debugstyle.disabled = true;
	}
}
function updateCleanupBtn() {
	var btn = document.getElementById('btnCleanupTag');
	if(btn){
		if(!window.oldcleanuptag.match(cleanup_tpl_R)) {
		btn.value = "Untag for cleanup";
		btn.style.fontWeight="bold";
		} else {
		btn.value = "Tag for cleanup";
		btn.style.fontWeight="normal";
		}
	}
}
var cleanup_tpl_R = /\{\{([\w \-]*cleanup)/; // }}
var oldcleanuptag = "{{disambiguation cleanup";
function toggleCleanup() {
	var useWikEd = wikEd.useWikEd && wikEd.frameBody;
	if(useWikEd) {
		wikEd.UpdateTextarea();
		wikEd.textareaUpdated = true;
	}
	try { suggestSummary(); } catch(e) {}
	var editbox = document.getElementById('wpTextbox1');
	// TODO support hndis
	editbox.value = editbox.value.replace(/\{\{(?:disam|\w+[ _]+disambig)(?:[^{|}]+|\|\s*date|\|\s*mosdab)*/i, function(s) {
		//var oldtag = window.oldcleanuptag;
		var oldtagdom = document.getElementById('oldcleanuptag');
		var oldtag = oldtagdom ? oldtagdom.value : window.oldcleanuptag;
		if(oldtagdom) {
			oldtagdom.value = s;
		}
		window.oldcleanuptag = s;
		return oldtag;
	});
	updateCleanupBtn();
	if(useWikEd) {
		wikEd.UpdateFrame();
	}
}
function sortByYear(obj) {
	function getYear(text) {
		return (text.match(/\b1\d\d\d\b|\b20\d\d\b/) || ['9999'])[0];
	}
	wikEd.GetText(obj, 'selectionLine');
	obj.changed = obj.selectionLine;

	var lines = obj.changed.plain.split('\n');
	lines.sort(function(a,b) {
		if     (getYear(a) > getYear(b))
			return  1;
		else if(getYear(a) < getYear(b)) 
			return -1;
		else
			return  0;
	});
	obj.changed.plain = lines.join('\n');
	obj.changed.keepSel = true;
	return;
}
function FixRedirectReplace(obj) {
	wikEd.GetText(obj, 'selectionLine');
	obj.changed = obj.selectionLine;
	
	//                1 2[[ 2   3  3   4                45   #            5 6    |78    8  76 9 ]] 91
	var regExpLink = /((\[\[)\s*(:?)\s*([^\n#<>\[\]{}|]+)(\s*#[^\n\[\]|]*?)?(\s*\|((.|\n)*?))?(\]\]))/g;
	// Copied from wikEd.js and fixed
	function matchLinks(p, p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14, p15, p16, p17, p18) {
		var tag = p1;
		var openTag = p2;
		var prefix = p3;
		var article = p4;
		var fragmentId = p5 || '';
		var linkText = p7 || '';
		var closeTag = p9;

		var link = wikEd.CleanLink(article);
		if ( (Object.prototype.hasOwnProperty.call(wikEd.linkInfo, link) === true) && (wikEd.linkInfo[link].redirect === true) ) {
			var target = wikEd.linkInfo[link].target;

			// lowercase link target if link text starts with lowercase (main space only)
			if (wikEd.config.articlesCaseSensitive === false) {
				if (/:/.test(target) !== true) {
					if (article.charAt(0).toLowerCase() == article.charAt(0)) {
						target = target.charAt(0).toLowerCase() + target.substr(1);
					}
				}
			}

			// remove link text if identical to new target
			if (openTag == '[[') {
				if (linkText !== '') {
					if (linkText.replace(/_/g, ' ') == target) {
						linkText = '';
					}
				}

				// keep replaced link as link text
				else if (linkText === '') {
					if (target != article) {
						linkText = article;
					}
				}
			}

			// return fixed link
			var wikiLink = openTag + prefix + target + fragmentId;
			wikiLink = wikiLink.split('_').join(' ');
			if (linkText !== '') {
				wikiLink += '|' + linkText;
			}
			wikiLink += closeTag;
			return wikiLink;
		}
		return tag;
	}
	obj.changed.plain = obj.changed.plain.replace(regExpLink, matchLinks);
	obj.changed.keepSel = true;
}

function sortByDefaultSort(obj) {
	function getYear(text) {
		return (text.match(/\b1\d\d\d\b|\b20\d\d\b/) || ['9999'])[0];
	}
	wikEd.GetText(obj, 'selectionLine');
	obj.changed = obj.selectionLine;

	var lines = obj.changed.plain.split('\n');
	lines.sort(function(a,b) {
		if     (getYear(a) > getYear(b))
			return  1;
		else if(getYear(a) < getYear(b)) 
			return -1;
		else
			return  0;
	});
	obj.changed.plain = lines.join('\n');
	obj.changed.keepSel = true;
	return;
}

function CommentHandler(obj) {
	wikEd.GetText(obj, 'selection, cursor');
	obj.changed = (obj.selection.plain!=='' ? obj.selection : obj.cursor);
	
	// make the changes to the plain target text
	if( /&lt;!--([\s\S]*?)--&gt;/g.test(obj.changed.plain) ) {
		// remove formatting		
		obj.changed.plain = obj.changed.plain.replace(/&lt;!--([\s\S]*?)--&gt;/g, '$1');
	} else {
		// add formatting
		obj.changed.plain = '&lt;!--' + obj.changed.plain + '--&gt;';
	}
	// keep the changed text selected, needed to remove the formatting with a second custom button click
	obj.changed.keepSel = true;
	return;
}

// Configure WikEd
var wikEd = {
	useWikEd: null, // Default test condition if nothing loaded
	//GetText: function(){}, // stub
	config: {
		frameCSS: {
			// CSS for our custom elements
			'.autosechead': 'background-color: #333; color: #ffd700;',
			'.autodesc':    'background-color: #ffd700; color: black;',
			'.year':        'background-color: #fafafa;',
			// Make redirects visisble to users
			'.wikEdLink[title~="redirect"]': 'background-color:#dde; outline:1px dotted navy;'
		},
		comboPresetOptions: {summary: [ // Most " per [[MOS:DABENTRIES]]"
			'Update lifespans',
			'one blue link per line',
			'remove red link without blue',	// [[MOS:DABRL]]
			'remove punctuation',
			'unpiping',							// [[MOS:PIPING]]
			'no external links',
			'cleanup per [[WP:MOSDAB]]',
			'order entries alphabetically',
			'shorten bios, per [[MOS:DAB]]; there should only be enough to differentiate',
			'format with quotation marks and italics',
			'disambig page style repair'
			//'{wikEdUsing}'
		]},
		summaryUsing: ' using [[tools:~dispenser/cgi-bin/dabfix.py|Dabfix]]',
		linkifyArticlePath: "http://www.wikipedia.org/wiki/$1", /* Incorrect default, fix in setupHook() */

		/* disable jumping around */
		doCloneWarnings: false,
		focusEdit:      false,
		scrollToEdit:   false,

		/* WikEd customize buttons */
		closeToolbarPreset: false,
		buttonBar: {
			'format': ['wikEdButtonBarFormat',		'wikEdButtonBarFormat', 	'wikEdButtonsFormat',	'wikEdButtonsFormat',	44, 'wikEdGripFormat', [
//Undo/redo
13, 1, 2,14,  17,24,80,'br',
 3, 4, 7,15,  19,21,12
				] ],
			'textify':   ['wikEdButtonBarTextify',   'wikEdButtonBarTextify',   'wikEdButtonsTextify',   'wikEdButtonsTextify',   44, 'wikEdGripTextify', [
26,27, 101, 100, 'br',
102//, 110, 111, 112
				] ],
			'fix':       ['wikEdButtonBarFix',		'wikEdButtonBarFix',		'wikEdButtonsFix',		'wikEdButtonsFix',		44, 'wikEdGripFix', [
52,53,56,'br',
58,59,181
				] ],
			'control': ['wikEdButtonBarControl',	'wikEdButtonBarControl',	'wikEdButtonsControl',	'wikEdButtonsControl',	44, 'wikEdGripControl', [
29,35,30,37,'br',
77,34,33
				] ]
		},
		button: { // Define extra buttons
			100: ['wikEdComment',  'wikEdButton', 'Comment out', '//upload.wikimedia.org/wikipedia/en/3/34/Button_hide_comment.png', '23', '23', 'DIV', 'wikEd.EditButton(this, this.id, null, CommentHandler);' ],
			101: ['wikEdHighDesc', 'wikEdButton', 'Highlight Description Start', '//upload.wikimedia.org/wikipedia/commons/c/cb/Button_S_yellow_author.png', '23', '23', 'Descriptions', 'wikEd.UpdateTextarea();wikEd.UpdateFrame();suggestSummary();' ],
			102: ['wikEdSortYear', 'wikEdButton', '', null, null, null, 'Sort by year', 'wikEd.EditButton(this, this.id, null, sortByYear);' ],
			103: ['wikEdSortYear', 'wikEdButton', '', null, null, null, 'Default sort', 'wikEd.EditButton(this, this.id, null, sortByDefaultSort);' ],
			// More
			110: ['wikEdAutoDesc', 'wikEdButton', '', null, null, null, 'Remove Description Start', 'removeDescriptions()' ],
			111: ['wikEdAutoSect', 'wikEdButton', '', null, null, null, 'Remove Link Suggestions', 'removeSections()' ],
			112: ['wikEdCleanup',  'wikEdButton', '', null, null, null, 'Un/tag for cleanup', 'toggleCleanup()' ],
			// Copy of WikEd's Bypass Redirect
			181: ['dfRedirect', 'wikEdButton', '', '//upload.wikimedia.org/wikipedia/commons/f/f8/WikEd_fix_redirect.png', '16', '16', 'Bypass redirects',      'wikEd.EditButton(this, this.id, null, FixRedirectReplace);' ]

		},

		setupHook: [function() {
			// Move our preview box to WikEd
			var oldP = wikEd.previewArticle;
			var newP = document.getElementById('WikiPreview');
			if(oldP && newP) { // Check if both exist
				newP.className = oldP.className;
				newP.id = oldP.id;
				oldP.parentNode.replaceChild(newP, oldP);
				wikEd.previewArticle = newP;
				newP.style.display="";
				document.getElementById('wikEdLocalPrevWrapper').style.display='';

				// Remove the Preview header
				var PreviewH2 = document.getElementById('Preview');
				PreviewH2.parentNode.removeChild(PreviewH2);
			}
			var wpSummary = document.getElementById('wpSummary');
			// Disable double click scroll jump
			wikEd.WikiPreviewHandler = function(event) {};
		}, function(){ // Loads after wikEd initializes
			wikEd.config.linkifyArticlePath = window.wgServer+window.wgArticlePath;
			// Update redlink
			if(window.linkInfo) {
				wikEd.linkInfo = window.linkInfo;
				wikEd.UpdateFrame();
			}
		}],

		loadDiff:		true,	// enable enhanced diff
		/* disable non-functional AJAX */
		autoUpdate:		false,
		useAjaxPreview:	false
	}
};
//]]></script>
""")
		main()
	except oursql.DatabaseError as e:
		# See dab_solver
		if e.errno in (1040, 1053, 1226, 1317, 2003, 2006, 2013): # Automatically retry for operational 
			htmlout('<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>')
			htmlout('<p>Database operational error, retry in a few minutes.</p><blockquote>oursql.DatabaseError(%s)</blockquote>', (repr(e),))
		else:
			raise
			
	finally:
		wikipedia.endContent()
		wikipedia.stopme()
