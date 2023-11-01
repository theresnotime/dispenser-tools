#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
&params;

    -test          Test the routines used for regession testing

    -namespace:n   Number or name of namespace to process. The parameter can be
                   more than one to add additional namespaces

commonfixes applied fixes which are general and specific to the English Wikipedia
"""
# TODO
# TIP: use "%(dictname)s" % groupdict() a
#  better ref combining , combine urls and on ignoring a list of character (matching)
#  Seperate English from generic wikisyntax
#  Seperate enwiki sepefic
# steel stuff from 
# http://en.wikipedia.org/wiki/User:Polbot/source/Reffix.pl


# FIXME:
#  	http://en.wikipedia.org/w/index.php?title=London&diff=prev&oldid=253531178 (infobox)
# 	http://en.wikipedia.org/w/index.php?title=Hoover_Dam&diff=prev&oldid=253529821
# FIXME:
# http://en.wikipedia.org/w/index.php?title=Rolls-Royce_RR300&diff=190562064&oldid=175311735
# http://www.nationaltrust.org/magazine/archives/arc_news_2007/010807.htm
# http://scholarworks.umass.edu/cgi/viewcontent.cgi?article=1186&context=theses
from __future__ import unicode_literals
import re, urllib
import wikipedia, pagegenerators
from interwiki_map import interwiki_map
try:
	import noreferences
except ImportError:
	print("Unable to import noreferences.py")
	noreferences = None

docuReplacements = {
    '&params;':     pagegenerators.parameterHelp,
}


ignoreAsNames = (
'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
)

# NOT IMPLEMENTED PROPERLY
# Will change work/publisher cite news and |agency="dictvalue"
agencies = {
	"AP": 		"Associated Press",
	"The Associated Press": "Associated Press",
	"Associated Press": "Associated Press",
	"AP News":	"Associated Press",
#	"DPA":		"Deutsche Presse-Agentur",
#	"AFP":		"Agence France-Presse",
}
# "The" will be stripped if it exist
# So don't include Edge case e.g. "People" and "The People"
commonPublishers = (
"American Journalism Review",
"Associated Press",
"BBC News",
"BBC",
"Boston Globe",
"Chicago Tribune",
"CNN",
"Daily Telegraph",
"Economist",
"Guardian",
"Huffington Post",
"International Herald Tribune",
"MTV",
"New York Times",
"NY Times",
"Observer",
"The Times",
"The Register",
"San Francisco Chronicle",
"Scientific American",
"Seattle Times",
"Reuters",
"Rolling Stone",
"Wall Street Journal",
"Washington Post",
"Wired",

# Web only sources
"IGN",
"GameStop",
"Electronic Gaming Monthly",
"Kotaku",
"Ars Technica",
"Joystiq",
"Tom's Hardware",
"Salon",

"United Press International",	# since 1907
)

# template choser
# not implemented yet
tpl_cite = (
	# Match templates, replace template, regex condition
	('cite web', 'cite encyclopedia',	r'\|\s*url\s*=\s*https?://(www\.)?(encarta.com|encarta.msn.com|betanitca.com)'),
	('cite web', 'cite news',			r'\|\s*url\s*=\s*https?://(www\.)?(nytimes.com|ap.google.com|news\.bbc\.co\.uk|time\.com|economist\.com|timesonline\.co\.uk|channelonline\.tv|cnn\.com|independent\.co\.uk|cbc.ca|theglobeandmail.com)/'),
	('cite web', 'cite paper',			r'\|\s*url\s*=\s*https?://(www\.)?(havard.edu)'),
	('cite web', 'cite news',			r'\|\s*agency\s*='),
	('cite web', 'cite book',			r'\|\s*isbn\s*=\s*[^\s{|}[\]]'),
)

htmltags = (
# Tags that must be closed
    'b', 'del', 'i', 'ins', 'u', 'font', 'big', 'small', 'sub', 'sup', 'h1',
    'h2', 'h3', 'h4', 'h5', 'h6', 'cite', 'code', 'em', 's',
    'strike', 'strong', 'tt', 'var', 'div', 'center',
    'blockquote', 'ol', 'ul', 'dl', 'table', 'caption', 'pre',
    'ruby', 'rt' , 'rb' , 'rp', 'p', 'span', 'u', 'abbr',
# Single
    'br', 'hr', 'li', 'dt', 'dd',
# Elements that cannot have close tags
    'br', 'hr',
# Tags that can be nested--??
    'table', 'tr', 'td', 'th', 'div', 'blockquote', 'ol', 'ul',
    'dl', 'font', 'big', 'small', 'sub', 'sup', 'span',
# Can only appear inside table, we will close them
    'td', 'th', 'tr',
# Tags used by list
    'ul','ol',
# Tags that can appear in a list
    'li',
## pairs
#			"b", "i", "u", "font", "big", "small", "sub", "sup", "h1",
#			"h2", "h3", "h4", "h5", "h6", "cite", "code", "em", "s", "span",
#			"strike", "strong", "tt", "var", "div", "center",
#			"blockquote", "ol", "ul", "dl", "table", "caption", "pre",
#			"ruby", "rt" , "rb" , "rp",
## single
#			"br", "p", "hr", "li", "dt", "dd",
## nest
#			"table", "tr", "td", "th", "div", "blockquote", "ol", "ul",
#			"dl", "font", "big", "small", "sub", "sup",
## table tags
#			"td", "th", "tr",
)
htmlattrs = (
			"title", "align", "lang", "dir", "width", "height",
			"bgcolor", "clear", "noshade", 
			"cite", "size", "face", "color",
			"type", "start", "value", "compact",
			#/* For various lists, mostly deprecated but safe */
			"summary", "width", "border", "frame", "rules",
			"cellspacing", "cellpadding", "valign", "char",
			"charoff", "colgroup", "col", "span", "abbr", "axis",
			"headers", "scope", "rowspan", "colspan", 
			"id", "class", "name", "style" 
		)

# CSS HEX color values to named (<9 chars) color table
namedColors = {'#00FFFF': 'aqua', '#F0FFFF': 'azure', '#F5F5DC': 'beige', '#FFE4C4': 'bisque', '#000000': 'black', '#0000FF': 'blue', '#A52A2A': 'brown', '#FF7F50': 'coral', '#FFF8DC': 'cornsilk', '#DC143C': 'crimson', '#00FFFF': 'cyan', '#00008B': 'darkBlue', '#008B8B': 'darkCyan', '#A9A9A9': 'darkGray', '#A9A9A9': 'darkGrey', '#8B0000': 'darkRed', '#FF1493': 'deepPink', '#696969': 'dimGray', '#696969': 'dimGrey', '#FF00FF': 'fuchsia', '#FFD700': 'gold', '#808080': 'gray', '#808080': 'grey', '#008000': 'green', '#F0FFF0': 'honeyDew', '#FF69B4': 'hotPink', '#4B0082': 'indigo', '#FFFFF0': 'ivory', '#F0E68C': 'khaki', '#E6E6FA': 'lavender', '#00FF00': 'lime', '#FAF0E6': 'linen', '#FF00FF': 'magenta', '#800000': 'maroon', '#FFE4B5': 'moccasin', '#000080': 'navy', '#FDF5E6': 'oldLace', '#808000': 'olive', '#FFA500': 'orange', '#DA70D6': 'orchid', '#CD853F': 'peru', '#FFC0CB': 'pink', '#DDA0DD': 'plum', '#800080': 'purple', '#FF0000': 'red', '#FA8072': 'salmon', '#2E8B57': 'seaGreen', '#FFF5EE': 'seaShell', '#A0522D': 'sienna', '#C0C0C0': 'silver', '#87CEEB': 'skyBlue', '#FFFAFA': 'snow', '#D2B48C': 'tan', '#008080': 'teal', '#D8BFD8': 'thistle', '#FF6347': 'tomato', '#EE82EE': 'violet', '#F5DEB3': 'wheat', '#FFFFFF': 'white', '#FFFF00': 'yellow',
}


def fixStyle(text):
	pass


def fix(text="", page=None, verbose = True):
	if not page:
		page = wikipedia.Page(wikipedia.getSite(), 'Special:Snippet')
	if not text:
		text=page.get()
	if page.namespace() in (108,):
		return text
	if page.namespace() >= 0 and page.namespace() % 2 == 1:
		return text

	#
	## Hacks
	#
	text = text.replace('http://www.news.bbc.co.uk', 'http://news.bbc.co.uk')

# TODO: Fix accessyear/acessdate mismatch
	# Peer Reviewer script had for sometime time convert URL into the following bad form
	text = re.sub(r'\{\{[Cc]ite web\s*\|\s*url\s*=\s*http://(?P<title>[^{|}]+)\s*\|\s*title\s*=\s*(http://)?(?P=title)\s*(<!--[^<>]+-->)?\s*((\|format=(PDF|DOC))|(\|\s*accessdate *= *[^{|}]+))*\}\}', r'[http://\g<title>]', text)
	# a second time since we seem to hittings limits
	text = re.sub(r'\{\{[Cc]ite web\s*\|url=(https?://[^{|}]+)\s*\|title=([^{=}]+<!--[^<=>/]+-->)(\|format=(PDF|DOC))?\}\}', r'[\1 \2]', text)

	# Following the collapse of MiB preference PDFbot converts to the new format when saving
	text = re.sub(r'\{\{(PDF(?:link)?\|[^{|}]+\|[\d\.]+)&nbsp;\[\[[^|]+\|([KMG])iB\]\]<!--[^<>]+-->\}\}', r'{{\1&nbsp;\2B}}', text)

	# EN MOS -- Format Retrieved \g<date>.</ref>', text)

	# deprecated date linking, remove in citations
	text =  re.sub(r'\[\[(\d+ (?:January|February|March|April|May|June|July|August|September|October|November|December))\]\],? \[\[(\d{4})\]\](?=[^<>]*</ref>)', r'\1 \2', text)
	text =  re.sub(r'\[\[((?:January|February|March|April|May|June|July|August|September|October|November|December) \d+)\]\],? \[\[(\d{4})\]\](?=[^<>]*</ref>)', r'\1, \2', text)
	
	#
	## Comments
	#

	# Update {{NoMoreLinks}}
	text = re.sub(r'<!--=+\(\{\{No ?More ?Links\}\}\)=+([^<>]+|-->(\n*<!--.*?-->\n)+<!--)=+\(\{\{No ?More ?Links\}\}\)=+-->', '{{subst:NoMoreLinks}}', text)
	# Update {{Long comment}}
	text = re.sub(r'(?i)(\{\{Short pages monitor\}\}\s*|)<!--[^</">-]+long[ ]?comment[^</">-]+-->', r'{{subst:long comment}}', text)
	# Remove comment from the instroduction of footnotes
	text = re.sub(r"\n?<!--[^<>]*[Ss]ee +https?://en.wikipedia.org/wiki/Wikipedia:Footnotes +[^<>]+generate([^<>]|<(?=/?ref)[^<>]*>)+-->", '', text)
	# Remove outdated comments
	text = re.sub(r'\n?<!--\s*Categories\s*-->', '', text)

	# Now that we got all the stuff that deals with comments out the way we can hide them to prevent mismatching
	text = hideText(text)
	
	if page.site().sitename() == 'wikipedia:en' and page.namespace() in (0, 2, 6) and '{{disambig' not in text:
		wikipedia.output("Applying English Wikipedia commonfixes")
		text = formatEnglishWikipediaTemplate(page, text)

	#
	## HTML ## 
	#
	
	# <b> & <i> to ''' & ''
	text = re.sub(r"(?<!')<b>([^{|}<>\n']*?)</b>(?!')", r"'''\1'''", text)
	text = re.sub(r"(?<!')<i>([^{|}<>\n']*?)</i>(?!')", r"''\1''", text)

	# Standardize tables
	text = re.sub(r'\n\|-+(?=[^{|}\n]*\n)', r'\n|-', text)
	text = re.sub(r'\n\|-(?=\w)', r'\n|- ', text)
	text = re.sub(r'\n\|-[^{}|<>\n]*(?=\n\|-)', r'', text)
	text = re.sub(r'(\n\{\|[^][{}|<>\n]*)\n+(?=[|!][^+\-{}\n]+\n)', r'\1\n|-\n', text)
	text = re.sub(r'\n\|-[^{}|<>\n]*\n*(?=\n\|\})', r'', text)

	text = fixHTML(page,text)

	saved = text # saved state

	# Merge styles in a table
	for property in ['text-align', 'vertical-align', 'font-size', 'font-family', 'font-weight', 'font-style', 'color', 'background','background-color']:
		text = re.sub(r'''
\|-([^\n{|}[\]]*?)( *
\|[^{|}[\]]*style="[^"]*('''+property+r''':[^;"]+;)[^"]*"[^{|}[\]]*\|[^|\n]*?((?:\n\|(?!-)|\|\|)[^{|}[\]]*style="[^"]*\3[^"]*"[^{|}[\]]*\|[^|\n]*)+)(?=
\|[-}])''', r'\n|-\1 style="\3" \2', text)
		p = re.compile(r'''(
\|-[^\n{|}[\]]*? style="[^"]*?('''+property+r''':[^";]+;)[^"]*?"[^\n{|}[\]]*(
\|(?!-)(?:[^[\]{|}]*\|[^\n]*?))*?
\|(?!-)[^{|}[\]]*style="[^"]*)\2 *(?=[^"]*"[^[\]{|}]*\|[^\n])''')
		while p.search(text):
			text = p.sub(r'\1', text)
	if saved != text:
		text = fixHTML(page,text)



	#
	## Hyperlinking ##
	#
	
	# Remove url junk (tracking, referrers, client info)
	for i in range(0,9):
		text = re.sub(r'(https?://[^][<>\s"|])(&client=firefox-a|&lt=)(?=[][<>\s"|&])', r'\1', text)

	text = text.replace('[{{SERVER}}{{localurl:', '[{{fullurl:')		# Use magic words instead
#	text = re.sub(r'\[http://en.wikipedia.org/w/index.php\?title=([^][<>"\s&=?]+)&?([^][<>"\s]*)', r'[{{fullurl:\1|\2}}', text)

	# convert (see http://...) into <http://...>, which is better handled by software
	text = re.sub(r'(?i)[(](?:see|) *(https?://[^][<>"\s(|)]+[\w=/&])\s?[)]', r'<\1>', text)

	# From fixes.py
	# external link in double brackets
	text = re.sub(r'\[\[(?P<url>https?://[^\]\n]+?)\]\]',   r'[\g<url>]', text)
	# external link starting with double bracket
	text = re.sub(r'\[\[(?P<url>https?://.+?)\]',         r'[\g<url>]', text)
	# pipe in url (unlikely to go wrong)
	text = re.sub(r'\[(?P<url>https?://[^][<>\s"\|;?]+?\.(aspx?|doc|f?cgi|html?|jsp|pdf|php|pl|ppt|rtf|txt|xml)) *\| *(?P<label>[^\|\]]+?)\]', r'[\g<url> \g<label>]', text)
	# Use of Image:
	#if '[[Image:' in text:
	#	text = re.sub(r'(?i)\[\[(:?)File:([^][{|}]+\.(djvu|jpe?g|png|gif|svg|tiff))(?=\||\]\])', r'[[\1Image:\2', text)
	text = re.sub(r'(?i)\[\[(:?)Image:([^][{|}]+\.(pdf|midi?|ogg|ogv|xcf))(?=\||\]\])', r'[[\1File:\2', text)

	# Commons fixes for URLs
	# TODO: remove domain name titles [http://example.com/aboutus.pdf example.com]
	# | url= http://www.statcan.ca/english/sdds/instrument/3901_Q2_V2_E.pdf]  (fx by removing the invalid [])
	text = re.sub(ur'((https?):/* *){2,}(?=[a-z0-9:.\-]+/)', r'\2://', text)  # Silently correct http://http:/
	text = re.sub(ur"(\[\w+://[^][<>\"\s]+?)''", r"\1 ''", text) # corrects [http://''title''] (nospaces) -> [http:// ''title'']
	text = re.sub(ur'\[\n*(\w+://[^][<>"\s]+ *(?:(?<= )[^\n\]<>]*?|))\n([^[\]<>{}\n=@/]*?) *\n*\]', ur'[\1 \2]', text)	# Fix some links which were broken with a line break
	text = re.sub(ur'\[(\w+://[^][<>"\s]+) +([Cc]lick here|[Hh]ere|\W|→|[ -/;-@]) *\]', ur'\2 [\1]', text)	# remove unhelpful titles for screen readers

	# Embedded images with bad anchors
	text = re.sub(r'(?i)(\[\[(?:File|Image):[^][<>{|}]+)#(|filehistory|filelinks|file)(?=[\]|])', r'\1', text)
	
	text = ext2intLinks(page, text)
	try:
		text = simplifyLinks(page, text)
	except Exception, e:
		wikipedia.output("\03{lightred}ERROR\03{default}: simplifyLinks exception: %s" % e )
		#if isinstance(e, UnicodeDecodeError):raise
		raise

	## References ##
	# This is need because of <gallery>Image1.jpg|caption<ref>this is hidden</ref></gallery>
	text = fixReferences(page, text)
	text = showText(text)
	
	# Last part required for webreflinks
	if noreferences and page.namespace() != 10 and page.title() != 'Special:Snippet':
		norefbot = noreferences.NoReferencesBot(None, verbose=False, site=page.site())
		if norefbot.lacksReferences(text):
			text = norefbot.addReferences(text)
	return text


def formatEnglishWikipediaTemplate(page, text):
	# merge all variant of cite web
	# make into {'dictname':(t1, t2, t3),}
	text = re.sub(r'(?i)\{\{\s*(cite[_ \-]*(url|web|website)|Web[_ \-]*(citation|reference|reference[_ ]4))(?=\s*\|)', '{{cite web', text) 


	# Aug2011 per request, detransclude URL (which are blacklisted anyway)
	text = re.sub(r'\{\{\s*((http|https|ftp)://[^{|}<\s">][^{}]+)\}\}', r'\1', text, flags=re.I)
	
	# XXX needs review, Jan 2011
	### Unlink
	## Remove formatting on certian parameters
	#text = re.sub(r"(\|\s*(?:agency|author|first|format|language|last|location|month|publisher|work|year)\s*=\s*)(''|'''|''''')((?:\[\[[^][|]+|\[\[|)[][\w\s,.~!`\"]+)(''+)(?=\s*\|[\w\s]+=|\s*\}\})", r'\1\3', text)

	# Unlink well known publisher parameters (add work=?)
	text = re.sub(r'(?i)(\|\s*(?:publisher|newpaper)\s*=\s*)\[\[((?:[Tt]he |)(?:'+('|'.join(commonPublishers))+'))\]\]', r'\1\2', text)

	# Unlink PDF in format parameters
	text = re.sub(r'(?i)(\|\s*format\s*=\s*)\[\[(adobe|portable|document|file|format|pdf|\.|\s|\(|\)|\|)+\]\]', r'\1PDF', text)
	text = re.sub(r'(?i)(\|\s*format\s*=\s*)(\s*\.?(adobe|portable|document|file|format|pdf|\(|\)))+?(\s*[|}])', r'\1PDF\4', text)

	# No |format=HTML says {{cite web/doc}}
	text = re.sub(r'(?i)(\{\{cite[^{}]+)\|\s*format\s*=\s*(\[\[[^][|]+\||\[\[|)(\]\]| |html?|world|wide|web)+\s*(?=\||\}\})', r'\1', text)

	## Fix parameters
	# Fix accessdate tags [[WP:AWB/FR#Fix accessdate tags]]
	text = re.sub(r'(\|\s*)a[ces]{3,8}date(\s*=\s*)(?=[^{|}]*20\d\d|\}\})',  r'\1accessdate\2', text)
	text = re.sub(r'accessdate(\s*=\s*)\[*(200\d)[/_\-](\d{2})[/_\-](\d{2})\]*', r'accessdate\1\2-\3-\4', text)
	text = re.sub(r'(\|\s*)a[cs]*es*mou*nthday(\s*=\s*)', r'\1accessmonthday\2', text)
	text = re.sub(r'(\|\s*)a[cs]*es*daymou*nth(\s*=\s*)', r'\1accessdaymonth\2', text)
	text = re.sub(r'(\|\s*)accessdate(\s*=\s*[0-3]?[0-9] +(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*)([^][<>}{]*accessyear[\s=]+20\d\d)', r'\1accessdaymonth\2\3', text)
	text = re.sub(r'(\|\s*)accessdate(\s*=\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w* +[0-3]?[0-9])([^][<>}{]*accessyear[\s=]+20\d\d)', r'\1accessmonthday\2\3', text)
	text = re.sub(r'(\|\s*)accessdaymonth(\s*=\s*)\s*([^{|}<>]+?)\s*(\|[^][<>}{]*accessyear[\s=]+)(20\d\d)', r'\1accessdate\2\3 \5', text)
	text = re.sub(r'(\|\s*)accessmonthday(\s*=\s*)\s*([^{|}<>]+?)\s*(\|[^][<>}{]*accessyear[\s=]+)(20\d\d)', r'\1accessdate\2\3, \5', text)

	# Fix improper dates
	text = re.sub(r'(?i)(\{\{cit[ea][^{}]+\|\s*date\s*=\s*\d{2}[/\-.]\d{2}[/\-.])([5-9]\d)(?=\s*[|}])', r'\g<1>19\2', text)
	text = re.sub(r'(?i)(\{\{cit[ea][^{}]+\|\s*date\s*=\s*)(0[1-9]|1[012])[/\-.](1[3-9]|2\d|3[01])[/\-.](19\d\d|20\d\d)(?=\s*[|}])', r'\1\4-\2-\3', text)
	text = re.sub(r'(?i)(\{\{cit[ea][^{}]+\|\s*date\s*=\s*)(1[3-9]|2\d|3[01])[/\-.](0[1-9]|1[012])[/\-.](19\d\d|20\d\d)(?=\s*[|}])', r'\1\4-\3-\2', text)
	
	# Fix URLS lacking http://
	text = re.sub(r'(\|\s*url\s*=\s*)([0-9a-z.\-]+\.[a-z]{2,4}/[^][{|}:\s"]\s*[|}])', r'\1http://\2', text)

	# Fix {{citation|title=[url title]}}
	text = re.sub(r'(?i)(\{\{cit[ea][^{}]*?)(\s*\|\s*)(?:url|title)(\s*=\s*)\[([^][<>\s"]*) +([^]\n]+)\](?=[|}])', r'\1\2url\3\4\2title\3\5', text)

	# Associated Press is usually the agency, not the work or publisher
	text = re.sub(r'(?i)\{\{\s*[Cc]ite\s*(?:web|news|newpaper|article)([^{}]+?)(\s*\|\s*)(?:publisher|work|author)(\s*=\s*)(\[\[[^[\]|]+\||\[\[|)(?P<agency>%s)(\]\])?(?=\s*\|[^][{}]+=|\s*\}\})' % '|'.join(agencies), r'{{cite news\1\2agency\3Associated Press', text)
	text = re.sub(r'(?i)(\{\{[^{}]+\|\s*url\s*=[^][{|}]+\.ap\.org/[^{}]+\|\s*)agency(\s*=\s*)Associated Press', r'\1work\2Associated Press', text)
	text = re.sub(r'(?i)(\{\{[^{}]+\|\s*)agency(\s*=\s*)Associated Press([^{}]+\|\s*url\s*=[^][{|}]+\.ap\.org/)', r'\1work\2Associated Press\3', text)

	# Fix pages=1 and page=20-44 and page=p. 22 , corner p. 23 section 5
#	text = re.sub(r'(\{\{\s*(?:[Cc]ite (journal|news))[^{}]*\| *pages?\s*=\s*)(p[pg]?[. ]|pages?\b) *(?=[\d\-]+\s*[|}])', r'\1', text)
	text = re.sub(r'(?i)(\{\{\s*(?:cite (?:journal|news|book|web)|citation)[^{}]*?\|\s*)pages(?=\s*=\s*(p|pp|pg|page|pages|)\b[.:]?\s*\d+\s*(\||\}\}))', r'\1page', text)
	text = re.sub(r'(?i)(\{\{\s*(?:cite (?:journal|news|book|web)|citation)[^{}]*?\|\s*)page(?=\s*=\s*(p|pp|pg|page|pages|)\b[.:]?\s*\d+\s*[\-]\s*\d+\s*(\||\}\}))', r'\1pages', text)

	# \n in title causes links to break
	for m in re.finditer(r'\|\s*(?:title)\s*=\s*([^{|}]*?)\s*\|',text):
		text = text.replace(m.group(), m.group().replace(m.group(1), m.group(1).replace('\n', ' ').replace('\r', ' ')))

	# Change infoboxes from trailing pipes (likely stems from {{qif}} days)
	p = re.compile(r'(\{\{[\w\s_]*[Ii]nfobox([^{}]*?\{\{[^{}]+\}\})*[^{}]*?[^{|}](= )?) *\| *\n ?(?=[\s\w]+=)', re.U)
	while p.search(text):
		text = p.sub(r'\1\n| ', text)
		text = text.replace('|\n}}', '\n}}')

	# Fix web.archive.org links
	# TODO |url= web.archive -> url+archiveurl
	# Note: correct web.archive.org/2008/en.wikipedia.org/page format
	text = re.sub(ur'''
	(\{\{ (?:[Cc]ite web|[Cc]ite news|[Cc]ite|[Cc]itation) [^{}]*? )
	(\|\s*) url (\s*=\s*)
	(?P<archiveurl>https?://(?:wayback.archive.org|web.archive.org)/web/(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})\d{6}/(?P<url>https?://[^[\]<>"\s]+?))
	(\s*) (?=\||\}\})
	''', ur'\1\2url\3\g<url>\9\2archiveurl\3\g<archiveurl>\9\2archivedate\3\g<y>-\g<m>-\g<d>\9', text, flags=re.I | re.X)

	# Proper Capitilize ALL UPPERCASE names and titles
	for m in re.finditer(r'(\|\s*(?:title|last|first|author)\s*=\s)([A-Z"\'\s.:;\-+0-9]{10,})(?=[{|}])', text):
		s = m.group(2)
		s = s.capitalize()
		text=text.replace(m.group(), m.group(1)+s)
	
	# basic implemnt of tpl_cite
	for (find_template, replace_template, condition) in tpl_cite:
		text = re.sub(ur'(\{\{\s*)(?:%s)((?=\s*\|)[^{}]*(%s)[^{}]*\}\})' % (find_template, condition), r'\g<1>%s\g<2>' % replace_template, text)

	return text



def fixHTML(page, text):
	'''
	'''
	# Remove old {{prettytable}} header row formatting
	text = re.sub(r'(?i)(\n\{\| class="wikitable[^\n]+\n\|-[^\n]*)(bgcolor\W+CCC+|background\W+ccc+)(?=\W+\n!)', r'\1', text)

	# <br/> has no visible effect on output next to a block level item
	text = re.sub(r'(\n([^<\n]|<(?!br[^>]*>))+\w+[^\w\s<>]*)<br[ /]*>(?=\n[*#:;]|\n?<div|\n?<blockquote)', r'\1', text)

	# Fix br
	text = re.sub(r'(?i)(<br[^</>]*>)\n?</br>', r'\1', text)
	text = re.sub(r'(?i)<[/]?br([^{/}<>]*?/?)>', r'<br\1>', text)
	#text = re.sub(r'(?i)<[/]?br([^{/}<>]*?)>', r'<br\1 />', text)
# Arrg! people are using this is templated tables as a way to visually align items! See [[Battle of Stalingrad]]
#	text = re.sub(r'(<br[\s/]*>|\n *\n *){4,}',	r'\n{{clear}}\n', text)
	text = re.sub(r'(?i)<br\s\S*clear\S*(all|both)\S*[\s/]*>', r'{{-}}', text)
	text = re.sub(r'<br\s\S*clear\S*(left|right)\S*[\s/]*>', r'{{clear\1}}', text)
	
# class is not in all skins
#	# Use class="center" instead of <center>
#	text = re.sub(r'(?i)<center\b([^<>]*)>((?:[^<]|<(?!/?\s*center\s*>))*)</center>', r'<div class="center"\1>\2</div>', text)

	# combine font tags
	text = re.sub(r'(?i)(<font\b[^<>]*)> *\n?<font\b([^<>]*>)((?:[^<]|<(?!/?font))*?</font> *\n?)</font>', r'\1\2\3', text)
	#
	text = re.sub(r'(?i)<font ([^<>]*)>\[\[([^[\]{|}]+)\|([^[\]\n]*?)\]\]</font>', r'[[\2|<font \1>\3</font>]]', text)

	#TODO look for single character entiys such as ; \ in markup, but ignore /
	text = re.sub(r'(<(?P<tag>\w+)(?= +)|\n\{\||(?<=\n)\|-|(?P<cell>\n[!|]|!!|\|\|))(?P<attr>[^<>[\]{|}\n]+(?(tag)(?=>)|(?(cell)(?=[!|][^!|])|(?=\n))))', fixAttributes, text)

	# Convert simple <font> to <span>
	# NOTE: <font>[[link|text]]</font> transforms to [[link|<font>text</font>]] by tidy
	text = re.sub(r'<font(( +style="[^"]+")+)>(?!\[\[)((?:[^<]|<(?!/?font))*?)(?<!\]\])</font>', r'<span\1>\3</span>', text)
	
	
	# Removed elements in HTML5 spec
	HTML5_removed = (
		"acronym", # Use <abbr>
		"dir",     # Use <ul>
		"center",  # Use <div style="text-align:center">
		# Text styling
		"tt",      # Use <code>, <kbd>, or <var>
		"strike",  # Use <s> or <del>
		# Font modifier
		"font", "basefont",
		# Misc
		"center", "dir"
	)
	removed_tags = {}
	for tag in re.finditer(r'(?<=<)\w+(?=[^<>]*>)', text):
		if tag in HTML5_removed:
			removed_tags[tag] = removed_tags.get(tag, 0) + 1
	
	if removed_tags:
		wikipedia.output("\03{lightred}DEPRECATED TAG\03{default} : %s %s removed in the HTML5" % (
			' and '.join('<%s> (%d)' % t if t[1] > 1 else '<%s>'%t[0] for t in removed_tags.iteritems()),
			'are' if len(removed_tags)>1 else 'is',
		))

	return text

def fixAttributes(node):
	tag = node.group('tag')
	attr = node.group('attr')
	if tag:
		tag = tag.lower()
	elif '{|' in node.group(1):
		tag = "table"
	elif '|-' in node.group(1):
		tag = "tr"
	if tag not in htmltags + (None, ):
		return node.group()

	# HACKS
	attr = re.sub(r'border="2" cellpadding="4" cellspacing="0" style="margin: *1em 1em 1em 0; background: *#f9f9f9; border: *1px #aaa+ solid; *border-collapse: *collapse(; *font-size: *[89]\d%)?', r'class="wikitable" style="', attr)
	# un-subst: {{prettytable}} and it dirvatives
	attr = re.sub(r'(?i)([^<>\n]*)border\W+2\W+cellpadding\W+4\W+cellspacing\W+0"?', r' class="wikitable" \1', attr)
#	p = re.compile(r'(class="wikitable[^<>\n]+ style="[^<>"\n]*?)(margin\W+1em\W+|1em\W+1em\W+0\W+|background\W+f9f9f9\W+|border\W+1px\W+#aa+a\W+solid\W+|border-collapse\W+collapse\W+|font-size\W+(100%|95%|1em)\W+)+(?=[^<>"\n]*")', re.I)
#	while p.search(text):
#		text = p.sub(r'\1', text)
	# WHERE DID I GET THIS!?!: ([^][{}<>|="\'\s]*[0-9a-zA-Z%._]+[^][{}<>|="\'\s]*)

	def quoteAttrib(m):
		# r' \g<attribute>="\g<value>"'
		if '"' in m.group('value'):
			return ' %s=\'%s\''%(m.group('attribute').lower(), m.group('value').strip())
		else:
			return ' %s="%s"'%(m.group('attribute').lower(), m.group('value').strip())
	# Quote attributes
	#FIXME: | param = ''italtic''
	attr = re.sub(r"""(?x)[ ]*
		\b(?P<attribute>\w{2,}) [ ]*=[ ]* ["']?(?P<value>
		(?<=") [^"]*? (?=") |
		(?<=') [^']+? (?=') |
		[^<=>"' [\]{|}]+(?=[<> ]|$)
		)["']?""", quoteAttrib, attr)

	# Remove malformed attribute
	for m in re.finditer(r' [\w:;\-]+="[^"]+"[\w:;\-@.,_](?=[<> ]|$)', attr):
		attr = attr.replace(m.group(), '')
		wikipedia.output("\03{lightred}MALFORMED ATTRIBUTE\03{default} : Removing: %s" % (m.group(),))

	# Deprecated classes
	attr = attr.replace(' class="prettytable', ' class="wikitable')
	# Repair broken HTML
	attr = re.sub(r'(?i) bgcolor="([A-Fa-f0-9]{6})"', r' bgcolor="#\1"', attr) # add hash to colors
	attr = re.sub(r'(?i) colspan="1"', r'', attr)
	attr = re.sub(r'(?i) rowspan="1"', r'', attr)

#	# move class= to the front
#	attr = re.sub(r'^(\s*)( [^][{|}<>]+)?( class="[^"]+"(?=\s|\Z))', r'\1\3\2', attr)
	if tag == 'table':
		# TODO move me
		# Tables
		attr = re.sub(r'(?i) align="(left|right)"', r' style="float:\1;" ', attr)
		attr = re.sub(r'(?i) align="center"', r' style="margin:auto;" ', attr)
		attr = re.sub(r'(?i) align="(\w+)"', '', attr)
	elif tag == 'div':
		attr = re.sub(r'(?i) align="(left|right)"', r' style="float:\1;"', attr)
		#attr = re.sub(r'(?i) align="center"', r' class="center"', attr)
		
	if tag == 'table':
		attr = re.sub(r'(col|row)span=("1"|1)(?=\D)', r'', attr)
		#attr = attr.replace('cellspacing="0"', 'style="border-collapse:collapse; "')
		if 'border=' not in attr:
			# See [[MediaWiki talk:Common.css# Wikitable borders without CSS]]
			attr = re.sub(r'class="wikitable([^"\'{|}]*)"( *border="?1"?)*', r'class="wikitable\1" border="1"', attr)
		if re.search('float: *right', attr) and 'toccolours' in attr and node.start() < 400:
			# floats right, and near the top, gotta be a infobox
			attr = re.sub(r'class="toc(colours|)', r'class="infobox', attr)
			attr = re.sub(r'float: *right;|margin[^:;="]*:[^:;="]+|border="1"', r'', attr)
		# border-collapse is not exactly the same but it's close enough
		#attr = re.sub(r' cellspacing="0"', r' style="border-collapse:collapse;"', attr)
	if 'class="wikitable' in attr:
		attr = re.sub(r'(?i)(border:)( 1px| #aaa+| solid)+',r'\1', attr)
		attr = re.sub(r'(?i) border="?([0-9])"?',   		r'', attr)
		attr = re.sub(r'(?i) cellspacing="?([0])"?',		r'', attr)
		attr = re.sub(r'(?i) cellpadding="?([2-4])"?',		r'', attr)
		attr = re.sub(r'(?i)margin: ?1em 1em 1em 0',		r'', attr)
		attr = re.sub(r'(?i)background: ?#f9f9f9',  		r'', attr)
		attr = re.sub(r'(?i)border-collapse: ?collapse',	r'', attr)
		attr = re.sub(r'font-size: ?(100%|1em)',		r'', attr)
		#if  # avoid float: position: etc..
		#attr = re.sub(r'font-size: ?\.?9\d(%|em)',		r'', attr)
	
	# replace with CSS 
	attr = re.sub(r'(?i) align="(left|center|right|justify)"', 	r' style="text-align:\1;"', attr)
	attr = re.sub(r'(?i) bgcolor="([^"]+?)"',			r' style="background-color:\1;"', attr)
	#attr = re.sub(r'(?i) border="?([1-9])"?',			r' style="border:\1px;"', attr)
	attr = re.sub(r'(?i) color="([^"]+?)"', 			r' style="color:\1;"', attr)
	attr = re.sub(r'(?i) clear="(left|right|none)"',	r' style="clear:\1;"', attr)
	attr = re.sub(r'(?i) clear="(all|both)"',  			r' style="clear:both;"', attr)
	attr = re.sub(r'(?i) clear="[^"]*"',		     	r' ', attr)
	attr = re.sub(r'(?i) face="([^"]+?)"',				r' style="font-family:\1;"', attr)
	attr = re.sub(r'(?i) height="([^"]+?)"',			r' style="height:\1;"', attr)
	attr = re.sub(r'(?i) nowrap(="(nowrap|yes|true)"|(?= )|$)',	r' style="white-space:nowrap;"', attr)
	attr = re.sub(r'(?i) size="(\d+(em|%|px|pt))"', 	r' style="font-size:\1;"', attr)
	attr = re.sub(r'(?i) valign="(top|middle|bottom|baseline)"',	r' style="vertical-align:\1;"', attr)
	attr = re.sub(r'(?i) valign="[^"]*"',				r' ', attr)
	attr = re.sub(r'(?i) width="([^"]+?)"', 			r' style="width:\1;"', attr)
	
	# font size="#" render browser dependent, W3C leaves it open
	fontSizeConvert = {'1':'0.8em','2':'1em','3':'1.2em','4':'1.4em','5':'1.9em','6':'2.4em','7':'3.7em',
	'-4':'50%','-3':'60%','-2':'70%','-1':'80%','0':'100%','+0':'100%',
	'+1':'120%','+2':'140%','+3':'160%','+4':'180%','+5':'200%','+6':'250%','+7':'300%',}
	for n in re.finditer(r' size="([1-7]|[+-][0-6])"', attr):
		attr = attr.replace(n.group(),	r' style="font-size:%s;"'%fontSizeConvert[n.group(1)])
	
	# merge style attributes together
	stylemerge = re.compile(r' style="([^"{|}\n]+?);* *" *(.*?) style="([^"{|}\n]+)"')
	while stylemerge.search(attr):
		attr = stylemerge.sub(r' \2 style="\1; \3"', attr)
	
	# Fix up style parameters
	for styleMatch in re.finditer(r' style="([^[\]{|}\n]*?)"', attr):
		styleText = fixCSS(styleMatch.group(1))
		attr = attr.replace(styleMatch.group(), styleText and ' style="%s"'%styleText or '')
		if '=' in styleText:
			wikipedia.output("\03{lightyellow}WARNING\03{default} : U+003D EQUALS SIGN (=) character found in style attribute")
	
	# Remove all non approved attributes
	for m in re.finditer(r'(?<= )([\w:;\-]+)(="[^"]+"| +(?=\w)| *$| *>)', attr):
		if m.group(1).lower() not in htmlattrs and tag:# HACK remove when proper table support is in
			wikipedia.output("\03{lightred}INVALID ATTRIBUTE\03{default} : Removing: %s" % (m.group(),))
			attr = attr.replace(m.group(), '')
		elif m.group(2) == '=""':
			wikipedia.output("Empty attribute")
		else:
			attr = attr.replace(m.group(), m.group(1).lower() + m.group(2))
		
		# Alert user about deprecated html attributes
		# FIXME this should be split up into General, Table, Font
		if m.group(1).lower() in "align|alink|axis|background|bgcolor|border|cellspacing|cellpadding|char|charoff|clear|compact|color|face|frame|height|hspace|link|noshade|nowrap|rules|size|start|text|type|valign|vlink|width|vspace".split('|'):
			wikipedia.output("\03{lightred}DEPRECATED ATTRIBUTE\03{default} : %s"%''.join((node.group(1).lower(), attr.replace(m.group(), '\03{lightred}%s\03{default}'%m.group()))).strip())
	
	# put back in
	if re.sub(r'[ ;"]', '', node.group('attr').lower()) != re.sub(r'[ ;"]', '', attr.lower()) and len(attr) < len(node.group('attr')) * 2:
		return ''.join((node.group(1).lower(), attr.rstrip() ))
	else:
		return node.group()
	
def fixCSS(styleText):
#TODO
# add filter for value and dictionary units
	# Stylistics changes
	styleText += ';' # add then remove
	styleText = re.sub(r' *: *', ':', styleText)
	styleText = re.sub(r' *(; *)+', '; ', styleText)
	# Remove "float; ..." and "float:;"
	styleText = re.sub(r'(\A *|;)([^;:=]*:? *;)+', r'\1', styleText)
	styleText = re.sub(r'[\w\-\s]:; ', '', styleText)

	#styleText = re.sub(r'(background|color):([a-fA-F0-9]{6});', r'\1:#\2', styleText)
	# removed, we should check in the color list before trying HEX values
	if styleText.count('background') == 1:
		styleText = styleText.replace('background-color:', 'background:')

	# Background:none is shorter than background-color:transparent, but resets image related properties
	# We also assume that people will not set anything else since background-image: is filtered out
	# See: [[User:Chris Chittleborough/CSS-notes]]
	styleText = re.sub(r'background:[^:;]*transparent[^:;]*;', r'background:none;', styleText)

	# Assumed units
	styleText = re.sub(r'(width|height):(\d{2,});', r'\1:\2px;', styleText)
	styleText = re.sub(r'((?:background|border|border|color)(?:-color)?):([a-fA-F0-9]{3,6})(?=[ ;])', r'\1:#\2', styleText)

	# Fix units
	styleText = re.sub(r'\b(width|height|border|margin|padding):(\d{2,}|[1-9])(?=[; ])', r'\1:\2px;', styleText)
	styleText = re.sub(r'(?<=[ :]0)(em|%|px|pt)(?=[ ;])', "", styleText)

	# IE color compatiblity
	styleText = re.sub(r'(?i)\bgrey\b', r'gray', styleText)
	styleText = re.sub(r'(?i)(dark|dim|light|lightslate|slate)gr[ae]y', r'\1grey', styleText)

	# Shorten CSS color values
	for m in re.finditer(r'#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?=[ ;!])', styleText):
		if re.search(r'(?i)#(00|11|22|33|44|55|66|77|99|aa|bb|cc|dd|ee|ff){3}', m.group().lower() ):
			styleText = styleText.replace(m.group(), re.sub(r'(?ui)#([0-9a-f])[0-9a-f]([0-9a-f])[0-9a-f]([0-9a-f])[0-9a-f]', r'#\1\2\3', m.group().lower() ))
		elif m.group().upper() in namedColors:
			styleText = styleText.replace(m.group(), namedColors[m.group().upper()])
		else:
			styleText = styleText.replace(m.group(), m.group().lower())

	# use mirroring
	styleText = re.sub(r'(margin|padding):(?P<v>-?[\.0-9]+[a-zA-z]+|0)( (?P=v))+;', r'\1:\2;', styleText)
	styleText = re.sub(r'(margin|padding):(-?[\.0-9]+[a-zA-z]+|0) (-?[\.0-9]+[a-zA-z]+|0) \2 \3;', r'\1:\2 \3;', styleText)
	styleText = re.sub(r'(margin|padding):(-?[\.0-9]+[a-zA-z]+|0) (-?[\.0-9]+[a-zA-z]+|0) (-?[\.0-9]+[a-zA-z]+|0) \3;', r'\1:\2 \3 \4;', styleText)
	
	return styleText.strip()

def ext2intLinks(page, text):
	text = re.sub(r'\[https?://upload.wikimedia.org/wikipedia/(?:commons|%s)/[0-9A-Fa-f]/[0-9A-Fa-f]{2}/([^[\]<>\s?]+) *((?<= )[^\n\]]+)\]' % (page.site().language()), r'[[Media:\1|\2]]', text)
	text = re.sub(r'\[https?://upload.wikimedia.org/wikipedia/(?:commons|%s)/[0-9A-Fa-f]/[0-9A-Fa-f]{2}/([^[\]<>\s?]+)\]' % (page.site().language()), r'<ref>[[Media:\1]]</ref>', text)

	text = re.sub(r'\[https?://(www\.toolserver\.org|toolserver\.org|tools\.wikimedia\.org|tools\.wikimedia\.de)/([^][<>"\s;?]*)\?? ([^]\n]+)\]', r'[[tools:\2|\3]]', text)
	if page.namespace() == 0:
		# [[WP:SELF]] states that we shouldn't cross link from the main namespace
		text = re.sub(r'''(?ix)\[https?://([a-z]{3}(?:-[a-z]+)*)\.(?:
			(wikt)ionary|
			wiki(n)ews|
			wiki(b)ooks|
			wiki(q)uote|
			wiki(s)ource|
			wiki(v)ersity)\.(?:com|net|org)/wiki/
			(?![_ :]*(?:Talk|Help|User|Wikipedia|Wikinews|Wikibooks|wikiquote|wikisource|wikiversity|Portal|MediaWiki)(?:[ _]talk)?:)
			([^][{|}\s"]*)[| ]+([^\n\]]+)\]''', r'[[\2\3\4\5\6\7:\1:\8|\9]]', text)
		text = re.sub(r'''(?ix)\[https?://(meta|commons|incubator|quality)
			\.wikimedia\.(?:com|net|org)/wiki/
			(?![_:]*(?:Talk|Help|User|Meta|commons|incubator|quality|Portal|MediaWiki)(?:_talk)*:)
			([^][{|}\s"]*)[| ]+([^\n\]]+)\]''', r'[[\1:\2|\3]]', text)
	else:
		text = re.sub(r'''(?ix)\[[https:]*//([a-z]{3}(?:-[a-z]+)*)\.(?:
			(wikt)ionary|
			wiki(n)ews|
			wiki(b)ooks|
			wiki(q)uote|
			wiki(s)ource|
			wiki(v)ersity)\.(?:com|net|org)/wiki/
			([^][{|}\s"]*)[| ]+([^\n\]]+)\]''', r'[[\2\3\4\5\6\7:\1:\8|\9]]', text)
		text = re.sub(r'''(?ix)\[https?://(meta|commons|incubator|quality)
			\.wikimedia\.(?:com|net|org)/wiki/
			([^][{|}\s"]*)[| ]+([^\n\]]+)\]''', r'[[\1:\2|\3]]', text)
		text = re.sub(r'''(?ix)\[https?://([a-z0-9\-]+)\.wikia\.(?:com|net|org)/wiki/
			([^][{|}\s"]*)[| ]+([^\n\]]+)\]''', r'[[wikia:\1:\2|\3]]', text)
		# Reverse interwiki map
		# [0-9A-Za-z\-.:_] not escaped
		# [;:@$!*(),/] are converted back in GlobalFunctions.php
		# [_#\'\\^`~] are assumed to be safe
		#conflict = {}
		for iw_prefix, iw_url in interwiki_map.iteritems():
			# Expensive overlap test
			#if iw_url in conflict:
			#	print("Collision in interwiki map [[%s:]] and [[%s:]] on %s<br/>" % (iw_prefix, conflict[iw_url], iw_url))
			#else:
			#	conflict[iw_url] = iw_prefix
			#for a,b in interwiki_map.iteritems():
			#	if b.find(iw_url) == 0 and a != iw_prefix:
			#		print("Overlap between interwiki map [[%s:]] (%s) and [[%s:]] (%s)<br/>" % (iw_prefix, iw_url, a, b))
			# re.escape(iw_url).replace(\\$1', r'
			text = re.sub(r'\[%s +([^\n\[\]]+)\]'%re.escape(iw_url).replace('\\$1', r'([0-9A-Za-z\-.;;:@$!*(),/_#\'\\^`~]*)'), r"[[%s:\1|\2]]"%iw_prefix, text)
	return text

def canonicalTitle(title, firstupper=True, underscore=False):
	"""
	Converts unicode or bytes string to mw titles
	support: percent-encoded UTF-8, HTML character references
	"""
	# TODO namespace support, e.g. [[WP: Foo]]
	if isinstance(title, unicode):
		title = title.encode('utf-8')
	# Unpercent-encode
	title = wikipedia.urllib.unquote(title)
	try:   title = unicode(title, 'utf-8')
	except:title = unicode(title, 'latin-1')
	# HTML character references
	title = wikipedia.html2unicode(title)
	# Remove ltr and rtl markers
	title = title.replace(u'\u200e', '').replace(u'\u200f', '')
	# Underscore to space and Strip space
	title = title.replace('_', ' ').strip().lstrip(':')
	# Merge multiple spaces
	while '  ' in title:
		title = title.replace('  ', ' ')
	# First uppercase
	if firstupper and title:
		title = title[0:1].upper() + title[1:]
	# Strip the section part
	if '#' in title:
		title = title[:title.index('#')]
	if underscore:
		title = title.replace(' ', '_')
	return title

def wikilinkregex(t, firstupper=True):
	t = canonicalTitle(t, firstupper)
	# Workaround for titles with an escape char
	if firstupper:
		t = ur'[%s%s]%s' % (t[0].upper(), t[0].lower(), t[1:],)
	t = re.escape(t).replace('\\[', '[', 1).replace('\\]', ']', 1)
	return t.replace('\\ ', '[ _]+').replace('\\|', '|')

def simplifyLinks(page, text):
	# 
	import simplify_links
	text = simplify_links.simplifyAnchors(page.site(), text)

	# Prettify links, remove underscore and decode characters
	for m in re.finditer(ur'\[\[([^[\]{|}\n]+)\|([^\n|]*?)\]\]', text):
		link = m.group(1).replace(u'_', u' ').encode('utf-8')
		if b'#' in link:
			title, anchor = link.split(b'#', 1)
			anchor = re.sub(br'''
			# Single byte character (Printable ASCII)
			# we make that [0-9A-Za-z\-.:_] and [[\]{|}] are not included
			 \.2[1-9A-CF]
			|\.3[BD-F]
			# Avoid encoding <tag and </tag
			|\.3C(?!\w|/|\.2F)
			|\.40
			|\.5[CE]
			|\.60
			|\.7E
			# skip .8-B\h
			#  Two  byte UTF-8 character U+0080-U+07FF
			|\.[CD][0-9A-F]\.[89AB][0-9A-F]
			# Three byte UTF-8 character U+0800-U+FFFF
			|\.E[0-9A-F]\.[89AB][0-9A-F]\.[89AB][0-9A-F]
			# Four  byte UTF-8 character U+10000-U+10FFFF
			|\.F[0-7]\.[89AB][0-9A-F]\.[89AB][0-9A-F]\.[89AB][0-9A-F]
			''', lambda m: m.group().replace(b'.', b'%'), anchor.replace(b'%', b'.25'), flags=re.X)
			link = b''.join((title, b'#', anchor))
		link = urllib.unquote(link) 	# unescape %xx
		# Specific formating
		if link.startswith(b'tools:'):
			link = link.replace(b' ', b'_')
		link = link.replace(b'# ', b'#')  # Remove copy & paste space
		link = link.decode('utf-8')
		#if m.group(2)[0:1].islower():
			#if m.group(1) != link 
		#if not any((s.isupper() for s in link[1:])) and not any((s.isupper() for s in m.group(2))):
		#	if re.search(r'(?i)\[\[(\w{3,})\w{0,3}[()_ |[\]].*?\b\1', m.group()):
		#		# Come up with better huristics
		#		# issue: [[Internet|the internet]]
		#		link = link[0].lower() + link[1:]
		text = text.replace(m.group(), '[[%s|%s]]'%(link, m.group(2)))

	# Simplify links
	# FIXME use canonicalTitle
	# [[A|AB]] -> [[A]]B
	text = re.sub(ur'\[\[([^{|}[\]]+)\|\1(\w*)\]\]', ur'[[\1]]\2', text)
	## A[[ABC|B]]C -> [[ABC]]
	#text = re.sub(ur'(?u)([^{|}[\]]* *) *\[\[ *\1([^{|}[\]]+ *)( *[^{|}[\]]*) *\| *\2\]\]\3', ur'[[\1\2\3]]', text)
	# disabled: "by [[experimental music|experimental]] musician"
	# TODO
	#  unbypass redirect change [[Light_cycle#Light_cycles]] and [[Tron_(film)#Light_cycles]] to the redirect [[Light cycle]]
	#  find redirect such that A [[Article |B]] C to [[A B C]]
	return text
	
def fixReferences(page, text):
	# Standardize to lowercase reference name, makes things easier for everyone
	text = re.sub(r'(?i)<(/?)REF\b([^>]*)>', r'<\1ref\2>', text)
	# it should be name = " or name=" NOT name   ="
	text = re.sub(r'<ref +name(= *| *=)"', r'<ref name="', text)


	# Remove puncutation between start/end of ref/templates  (}}.</ref>)
	text =re.sub(r'(<ref[^/>]*>\s*)[,.?:;~!]+\s*(?=\{\{)', r'\1', text)
	text = re.sub(r'(\{\{[^{}]{40,}\}\})\s*[,.?:;~!]+(?=\s*</ref>)', r'\1', text)

	# Leaving out the http://
	text = re.sub(r'(?<=<ref>)\s*([a-z0-9\-\.]*?[a-z0-9\-]+\.[a-z\.]{2,6}/[^][<>\s"]+)\s*(?=</ref>)', r'http://\1', text)
	text = re.sub(r'(?<=<ref>)\s*\[?(?:http://)?([a-z0-9\-\.]*?[a-z0-9\-]+\.[a-z\.]{2,6}/[^][<>\s"|]+) +([^][{|}<>\n/]+?)\]?\s*(?=</ref>)', r'[http://\1 \2]', text)

	# TODO: Fix the below [ref] to <ref>[url]</ref> conversion 
	text = re.sub(r'(?is)<ref\s*>\s*(\[\w+://[^][<>"\s]+\s*\])\s*(\[\w+://[^][<>"\s]+\s*\])\s*</ref\s*>', r'<ref>\1</ref><ref>\2</ref>', text)

	## Badly formed references
	# Fake reference (<sup>[url]</sup>)
	text = re.sub(r'(?i)<sup *>\s*\[(\w+://[^][<>"\s]+) *\]\s*</sup>', r'<ref>\1</ref>', text) 
	# Bracket to reference conversion
	# BUG matches <!-- [http://link/index ] -->
	def extToRef(m):
		try:
			referencesTemplates = noreferences.referencesTemplates[
                wikipedia.getSite().family.name][wikipedia.getSite().lang]
		except KeyError:
			referencesTemplates = []

		if referencesTemplates:
			reflist = '</?references|\{\{(' + '|'.join(referencesTemplates) + ')'
		else:
			reflist = '</?references'

		reflistM = re.compile(reflist).search(text, m.end())
		if reflistM and m.end() < reflistM.end():
			return m.expand(r'\1<ref>\2</ref>')
		return m.group()
	for i in range(8):
		#text = re.sub(r'(?miu)(^[^*#;:= ]{1,4}.{4,}?)(?<![*#]{3})(?<!PDFlink\|)(?<!PDF\|)(?<![(])\[((?:http|https|ftp)://[0-9a-z\-\.:]+/[^[\]<>\s"]{8,})\s*\](?![^-]*-->)(?!([^<]|<(?!ref))*</ref>)', extToRef, text)
		# testing
		text = re.sub(r'(?mi)(^[^#;:= ]{1,4}.{4,}?)(?<=[^*#]{15})(?<!PDFlink\|)(?<!PDF\|)(?<![(])\[((?:http|https|ftp)://[0-9a-z\-\.:]+/[^[\]<>\s"]{8,})\s*\](?![^-]*-->)(?!([^<]|<(?!ref))*</ref>)', extToRef, text)
	# remove invalid references
	text = re.sub(r'(?i)<ref> *</ref>', '', text)

	## Format Punctuation
	# Applied if "[,.;:]<ref/>" is dominate
	if len(re.findall(r'[.,;:] *\s?<ref', text)) > len(re.findall(r'(?:</ref>|<ref [^</>]+/>) *\s?[.,;:]', text)):
		# Move punctuation left and space right but before \n
		text = re.sub(r'(?s)(?<=[\w")\]])( *)((?: *\s??<ref [^>]+?/>| *\s??<ref[^>]*?>(?:[^<]|<(?!/?ref))*?</ref>)+)( *)\n?([.,]|(?<!\n)[;:])(?![.,;:])(\s??)( *)', r'\4\2\1\6\5\3', text)
		# Move space to the right, if there's text to the right
#u		text = re.sub(r'(?s)(?<=[.,;:"])( +)((?: *\s??<ref [^>]+?/>| *\s??<ref[^>]*?>(?:[^<]|<(?!/?ref))*?</ref>)+)(?= *\s?[^\s<>])', r'\2\1', text)
		# Remove duplicate punctuation
		text = re.sub(r'(?s)(?P<punc>[.,;:])(["]?(?:<ref [^>]+?/> *\s?|<ref[^>]*?>([^<]|<(?!/?ref))*?</ref> *\s?)+)(?!(?<=\n)[:;]|[.,;:]{2,})(?P=punc)', r'\1\2', text)
		# Remove spaces between references
		text = re.sub(r'(</ref>|<ref [^>]+?/>) +(<ref)', r'\1\2', text)
		# Add two space if none, reduce to two if more
		# trim or add whitespace after <ref />
		text = re.sub(r'(</ref>|<ref [^>]+?/>)()((\'{2,5}|)[\w"(\[])', r'\1 \3', text)
		text = re.sub(r'(</ref>|<ref [^>]+?/>)( {3,})([\w(\[])', r'\1  \3', text)
# October 2010-[[WP:REFPUNCT]] now states to always place before
#	elif len(re.findall(r'(?:</ref>|<ref [^</>]+/>) *\s?[.,;:]', text)) > 10:
#		wikipedia.output('\03{lightyellow}ALERT\03{default}: Punctuation after the references is the dominate format!')
#		wikipedia.output('\03{lightyellow}ALERT\03{default}: The majority of references have commas and periods after the reference entry.\n When editing you should preserve this formatting.')

	# Merge duplicate refs
	# TODO seperate reference group from naming
	for m in re.finditer(r'(?si)(<ref>)(.*?)(</ref>)', text):
		# Skip single references 
		if text.count(m.group()) <= 1:
			continue
		# Get a meaningful word part
		for p in (r'\|\s*last\s*=(\w+)',			# Reference template: | last = LASTNAME
				r'[Bb][Yy] +[A-Z][a-z]+ +([A-Z][a-z]+)[.,\'"]',
				r'^((?:Mc|)[A-Z][a-z])[,.]',		# First word, must be capitalized and followed by punctuation
				r'(?s)\w+://[a-z0-9\-\.]*?([a-z0-9\-]+)\.[a-z\.]{2,6}[ /|=!]',		# Website DOMAIN
				r'(?s)^(?:\[\[[^][]+\|)?((?<![{])(?<=\W)\b\w+)[,. ].*?(\d{2,4}\b)',		# [[Author|McAuthor]] p. 25

				r'(?si)\{\{.*?\|(\w*?)\|.*\}\}', 	# EXPERIMENTAL: {{Harvnb|McCann|1999|p=247}}
				):	
			match = re.search(p, re.sub(r'accessdate\s*=[^{|}]*|Retrieved [\s\w\[\],]+', ' ', m.group(2)), re.UNICODE)
			if match and len(match.group(1)) > 4 and match.group(1).lower() not in ignoreAsNames: 
				refname = match.group(1)
				break
		else:
			refname = 'autogenerated'		# Default name

			# try for the longest Capitalized word
			for n in re.findall(r'\b(?:Mc)?[A-Z][a-z]+\b', re.sub(r'\|[^{|}=]+=|\{\{[^{|}]+\||\[\[^][|]+\|', ' ', m.group(2) )):
				if len(n) > len(refname):
					refname = n

		# Remove non-letters to avoid names like "rescue007"
		refname = refname.strip('\t\r\n 0123456789-').lower()
		
		# Get a number
		for p in (r'\|\s*(?:pages|page|p|pp)\s*=\s*(\d+)', 
				r'\b(?:pages|page|p|pp|pg)[.:= ]*(\d{1,4})\b[\w\s\.\-<&\]]*', 
				r'\|\s*year\s*=\s*(\d{4})', 
				r'\b(19\d\d|200[0-7])\b',
				r'\b([mclxvi]*[clxvi]{2,6})(?:\b|\.)' ):
			match = re.search(p, re.sub(r'accessdate\s*=[^{|}]*|Retrieved [\s\w\[\],]+', ' ', m.group(2)) )
			if match and refname+match.group(1) not in text:
				refname = refname+match.group(1)
				break
		else:
			i = 1
			while refname+str(i) in text:	i+=1
			else: refname += str(i)
		# the replacement name should be 50% smaller
		if len(m.group(2)) * 0.50 > len(refname) + 8:
			text = text.replace(m.group(), '<ref name="%s">%s</ref>' % (refname, m.group(2)), 1)
			text = text.replace(m.group(), '<ref name="%s"/>' % refname)

	# remove formatting wrappers (adapted from AWB)
	m = re.search(r'(?i)(<(span|div)( class="(references-small|small|references-2column)"|)>\s*){1,2}\s*<references[\s]?/>(\s*</(span|div)>){1,2}', text)
	if m and m.group().count('<div') == m.group().count('</div'):
		cols = re.search(r'((?!-)column-count|-moz-column-count):\s*?(\d+)', m.group())
		if "references-2column" in m.group():
			text = text.replace(m.group(), '{{reflist|2}}')
		elif cols:
			text = text.replace(m.group(), '{{reflist|%s}}' % cols.group(2))
		else:
			text = text.replace(m.group(), '{{reflist}}')
	
	# Multicolumn {{Reflist}}
	# If more than 30 refs, make sure the reference section is multi column
	if text.count('</ref>') > 30:
		text = re.sub(r'(?is)(=\s+(<!--.*?-->)*\s*)(\{\{Cleanup-link rot[^{}]*\}\}\s*)?(<references />|\{\{(?:Listaref|Reference|Refs|Reflist|Refs)\|?[134]?\}\})', r'\1{{reflist|colwidth=30em}}', text)
	elif text.count('</ref>') < 8:
		text = re.sub(r'(?is)(=\s+)\{\{reflist\|(\d+|colwidth=\d+\w+)\}\}', r'\1{{reflist}}', text)
	else:
		pass

	return text
	

def correctdate(s):
	pass
def wiki_table(match):
	return match.group()

def html_attrib(match):
	return match.group()

## 
hideTokens = {}
hideRegex = re.compile('|'.join([
	r'<!--.*?-->',
	r'<includeonly>.*?</includeonly>',
	r'<math>.*?</math>',
	r'<nowiki>.*?</nowiki>',
	r'<source .*?</source>',
	r'<pre.*?</pre>',
	r'<timeline>.*?</timeline>',
	r'<gallery.*?>.*?</gallery>',
]), re.I | re.S)

def hideText(text):
	global hideTokens
	n=111
	for m in hideRegex.finditer(text):
		n+=1
		hideTokens[n] = m.group()
		text = text.replace(m.group(), u'⌊⌊⌊⌊%06d⌋⌋⌋⌋'%n)
	return text
	
def showText(text):
	global hideTokens
	for (key, value) in hideTokens.items():
		text = text.replace(u'⌊⌊⌊⌊%06d⌋⌋⌋⌋'%key, value)
	if re.search(ur'⌊⌊⌊⌊\d{6,}⌋⌋⌋⌋', text):
		wikipedia.output("WARNING: Unable to replace all hidden tokens")
		raise  "Please report this problem at [[User talk:Dispenser]]"
	hideTokens = {} # Empty
	return text

def main():
	gen = None
	namespaces = []
	genFactory = pagegenerators.GeneratorFactory()
	summary = "Applying general fixes for links, HTML, and/or references"

	for arg in wikipedia.handleArgs():
		if arg == '-test' or arg.startswith('-test:'):
			f = open('../cgi-bin/text/%s'%(arg[6:].replace('/', '|') or 'Tests.html'))
			test = unicode(f.read(), 'utf-8')
			site = wikipedia.getSite()
			page = wikipedia.Page(site, 'Special:Snippet')
			page._namespace=0
			# Disable cgitb disk loggging
			import cgitb; cgitb.enable()
			wikipedia.output("Default site: %s"%site.sitename())
			result = fix(text=test, page=page)
			wikipedia.showDiff(test, result)
			import parser
			print(b'''
<table style="table-layout:fixed; width:100%%;">
<tr style="vertical-align:top;">
<td>%s</td>
<td>%s</td>
</tr>
</table>''' % (parser.parser(test).encode('utf-8'), parser.parser(result).encode('utf-8')))
			wikipedia.output('\n----\n== Double pass text ==')
			wikipedia.showDiff(result, fix(text=result, page=page))
			return
		else:
			genFactory.handleArg(arg)

	if not gen:
		gen = genFactory.getCombinedGenerator()
	if not gen:
		wikipedia.showHelp('commonfixes')
		return
	for page in gen:
		try:
			page.get()
		except wikipedia.NoPage:
			wikipedia.output('%s does not exist!' % page.aslink())
			continue
		except wikipedia.IsRedirectPage:
			wikipedia.output(u'Page %s is a redirect' % page.aslink())
			continue
		text = fix(page=page)
		if text != page.get():
			wikipedia.showDiff(page.get(), text)
			wikipedia.setAction(summary)
			page.put(text)
		else:	
			print(b'No changes necessary')
	
if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
    try:
        wikipedia.startContent()
        main()
    finally:
        wikipedia.endContent()
        wikipedia.stopme()
