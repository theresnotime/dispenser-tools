#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""

Require scripts:
	wikipedia.py (MW integration)
	related.py   (Suggest links and ratings)

"""
import wikipedia; from wikipedia import logtime
import re, sys
import toolsql
from dablinks import api_getDabLinks, query, canonicalTitle, api_findTemplateLinksTo, findTemplateLinksTo
from dablinks import getDabLinks, api_getDabLinks, query, getConn, canonicalTitle, api_findTemplateLinksTo, findTemplateLinksTo
import cgitb; cgitb.enable(logdir='tracebacks')

redlinks = {}

def printu(s):
	sys.stdout.write(s.encode('utf-8'))

def quote(s):
	return wikipedia.urllib.quote(s.encode('utf-8') if isinstance(s, unicode) else bytes(s), safe=";@$!*(),/:-_.")

def html(markup, params=(), encoding='utf-8'):
	if params:
		out = markup % tuple(wikipedia.escape(unicode(s)) if isinstance(s, (bytes,str,unicode)) else s for s in params)
	else:
		out = markup
	sys.stdout.write(out.encode(encoding) if isinstance(out, unicode) else out)
	

# Import translation strings
# TODO This should be a classed
from resources_dab_solver import *

# Notes:
# .{80}[^\n]+ sometimes the second part lands on a \n
# \0| matches nothing
# begin + end need to be bounded for it to work
NewestOmitR = re.compile(ur'''\A(?P<begin>\0
#
| .{255,1200}?              (?=\s*^=+ [^\n]+ =+\s*$)        # Heading
#|(?:[^\n]|\n(?!\{\|))+     \|\}                            # Table end
| (?:[^\n]|\n(?!\|\}|\{\|)){255,1200}?\n\|-[^\n]*           # Table row
| .{0,  1200}?              (?=^\s*$)                       # Paragraph
| .{0,   255}[^\n]*                                         # Full line
)$

(?P<removed>.{1500,}?)                                      # Text to remove (at least 1,500)

# 
^(?P<end>\0
| =+ [^\n]+ =+\s*\n     .{255,1200}                         # Heading
#|\{\|                  (?:[^\n]|\n(?!\|\})){255,1200}      # Table start
| \|-                   (?:[^\n]|\n(?!\|\}|\{\|)){255,1200} # Table row
| (?<=\n\n)             .{255,1200}                         # Paragraph
|                       [^\n]*.{0,255}                      # Full line
)\Z''', re.I | re.DOTALL | re.VERBOSE | re.MULTILINE)
OmitR = re.compile(ur'''^(?P<begin>\0
| .{512,2048}?               (?=\n=+ [^\n]+ =+\s*\n)        # Heading
#|(?:[^\n]|\n(?!\{\|)){512,2048}  \|\}                      # Table end
| (?:[^\n]|\n(?!\|\}|\{\|)){1024,2048}?\n\|-[^\n]*          # Table row
| .{256,2048}?               (?=\n[ ]*\n)                   # Paragraph
| .{512}[^\n]*                                              # Full line
)\n
(?P<removed>.{1500,}?)                                      # Text to remove (at least 1,500 characters)
\n(?P<end>\0
| =+ [^\n]+ =+\s*\n     .{500,1500}                         # Heading
| \{\|                  (?:[^\n]|\n(?!\|\})){800,5120}      # Table start
| \|-                   (?:[^\n]|\n(?!\|\}|\{\|)){500,2048} # Table row
| (?<=\n\n)             .{250,1500}                         # Paragraph
|                       [^\n]*.{250}                        # Full line
)$''', re.I | re.DOTALL | re.VERBOSE)


def skiptask():
	taskid = wikipedia.SysArgs.get('task', '')
	if taskid:
		actionurl = "/~dispenser/cgi-bin/save.py?task=%s" % (taskid,)
		print '<div class=""><a href="%s">%s</a></div> ' % (actionurl, 'Next page',)
		print '<script type="text/javascript">location.assign(%s)</script> ' % (wikipedia.jsescape(actionurl), )

def prettify(text):
	# remove refs
	# TODO use numbered references
	text = re.sub(r'(?is)<ref[^/>]*>.*?</ref>', '<sup>ref</sup>', text)
	text = re.sub(r'(?is)<ref [^/>]+/>', '<sup>ref</sup>', text)
	# pipe tricks
	text = re.sub(r'(?i)\[\[(([^{|}[\]]+?) +\([^{|}[\]]*\))\|\2\]\]', r'[[\1|]]', text) # link (type)
	text = re.sub(r'(?i)\[\[(([^{|}[\]]+?), [^{|}[\]]*)\|\2\]\]',     r'[[\1|]]', text)	# city, state
	text = re.sub(r'(?i)\[\[([^{|}[\]]+?: *([^{|}[\]]*))\|\2\]\]',    r'[[\1|]]', text)	# WP:PIPETRICK
	text = re.sub(r'(?i)\[\[([^{|}[\]]+?: *([^{|}[\]]*) *\([^{|}[\]]*\))\|\2\]\]',    r'[[\1|]]', text)	# WP:PIPETRICK (TM)
	text = re.sub(r'(?i)\[\[(#([^{|}[\]]+?)(?: +\([^{|}[\]]+?\)|))\|\2\]\]', r'[[\1|]]', text)	# [[#History (pre-war)|]]
	# remove bolding/italics
	text = re.sub(r"'''?", '', text)
	# remove simple HTML (non-blocks)
	text = re.sub(r'</?(big|nowiki|small|span|code)[^<|>]*?>', '', text)
	# HACK add \n\n to headers
	text = re.sub(r'\n+((=+) *[^\n]+ *\2)( *\n)+', r'\n\n\1\n\n', text)
	# Remove triple spaces
	text = re.sub(r' {3,}', ' ', text)

	return text

def printfmt(text):
	# TODO template replace {{n}} => bgcolor=red |, etc
	# Escape HTML
	html = wikipedia.escape(text)
	allowedAttr = re.compile(r'\b(align|bgcolor|border|valign|rowspan|colspan|class|style) *= *(&quot;[^<&"\'>]*?&quot;|\'[^<&"\'>]*?\'|[^{|}<=>"\' ]+)')
	
	# Tables 
	if wikipedia.SysArgs.get('username','') == 'Dispenser' or 1:
		def fmt_row(match):
		#	cells = m.group(1)
		#	cells = re.sub(r'(\n\||\|\|)(([^|\n]|\|[^|])*)', r'\n| \2', cells)
		#	cells = re.sub(r'^\|(.*)', r'<td>\1</td>', cells, flags=re.M)
		#	return '<table class="wikitable"><tr>%s</tr></table>' % (cells,)
			if not match.group(2).strip(): # Double |-\n|-
				return ''
			row = []
			cells = re.split(r'\n*(^[!|]|\|\||!!)([^{|}[\]<\n>]*\|(?!\|)|)', match.group(2), flags=re.M)[1:]
			for cell_pipe, cell_fmt, cell_cont in zip(cells[0::3], cells[1::3], cells[2::3]):
				cell_type = 'th' if cell_pipe.endswith('!') else 'td'
				cell_fmt2 = ''
				for m in allowedAttr.finditer(cell_fmt):
					if 'url' in m.group(2) and 'http' in m.group(2):
						continue
					cell_fmt2 += ' %s="%s"' % (m.group(1), m.group(2).replace('&quot;', '"').strip(' \"\'\n\r'))
				row.append(r'<%s%s>%s</%s>' % (cell_type, cell_fmt2, cell_cont, cell_type,))
			
			return ur'<table class="wikitable"><tr>' + '\n'.join(row) + '</tr></table>\n'
			#while '\n\n' in row: row.replace('\n\n', '\n')
			#return row
		html = re.sub(ur'(?:^\|-|^\{\|)(.*)(\n*(^(?!\|[-}])[!|].*(\n(?![!|]).*)*\n*)*)(?=^\|[-}])', fmt_row, html, flags=re.M)
		html = html.replace('</table>\n<table class="wikitable">', '')

	# Template
	html = re.sub(ur'\{\{([^{|}[\]<\n>]+)([^<">{}]*?)\}\}', ur'<span class="tpl">{{<span class="lnk">\1</span>\2}}</span>', html)

	# Expose selective elements without attributes
	html = re.sub(ur'&lt;(%s)[^<&>/]*&gt;([^&]+)&lt;/\1&gt;' % '|'.join(["sup","sub"]), ur'<\1>\2</\1>', html)
	# Kill junk tags
	html = re.sub(r' *\b(align|bgcolor|border|valign|rowspan|colspan|class|style|cellpadding|cellspacing) *= *(&quot;[^&]*&quot;|\'[^\']*\'|[^{|}<=>"\' \n]+)', '', html)
	## Highlight HTML-like tags
	#html = re.sub(ur'(&lt;)(/?\w+)([^<\n>]*?)(?=&gt;)', ur'<span class="tag">&lt;<span class="tagname">\2</span>\3</span>', html)
	# Bold headings
	html = re.sub(ur'(?m)^(=+)(.*?)\1(?=\s*$)', ur'<div class="heading">\1<b> \g<2> </b>\1</div>', html)

	# Links
	def fmtLnk(m):
		lnkns=m.group(1).strip(' :').capitalize()
		if lnkns.startswith(('File', 'Image')):
			return m.expand(ur'<span class="img">[[<span class="lnk">\1\2</span>\3\4]]</span>\5')
		elif lnkns.startswith(('Category')):
			return m.expand(ur'<span class="cat">[[<span class="lnk">\1\2</span>\3\4]]</span>\5')
		#else:
		# s = m.expand(ur'
		# if m.group(5): s += m.expand(ur'<span class="lbl">\5</span>')
		# return ''.join('[['
		else:
			title = m.group(1) + m.group(2)
			label = m.group(4)
			suffix = m.expand(ur'<span class="lbl">\5</span>') if m.group(5) else u''
			cssClass=" new" if canonicalTitle(title, underscore=True) in redlinks else ""
			#print  canonicalTitle(title, underscore=True) ,' in ',redlinks
			if m.group(3) == '':
				return u'[[<a onclick="openMiniBrowser(event, this);return false" class="lnk lbl%s">%s</a>]]%s' % (cssClass, title, suffix) 
			elif label == '':
				return u'[[<a onclick="openMiniBrowser(event, this);return false" class="lnk%s">%s</a>|]]%s' % (cssClass, title, suffix)
			else:
				# remove link targets (long strings only)
				return u'[[<a onclick="openMiniBrowser(event, this, this.title);return false" title="%s"><span class="lnk%s">%s</span>|%s</a>]]%s' % (
					wikipedia.escape(title),
					cssClass,
					title if len(title) <= 25 else u'…',
					u'<span class="lbl%s">%s</span>'%(cssClass, label if label else u'', ),
					suffix,
				) 
	html = re.sub(ur'\[\[ *([^{|}[\]<\n>:]+:|)([^{|}[\]<\n>]{1,255})(\|?)((?<=\|)[^{}[\]<\n>]+|)\]\](\'?\w*)', fmtLnk, html)
	
	# shadow [[ ]] {{ }} &#enity; |parameter=
	html = re.sub(ur'(?m)^\|-+|^\{\|[^<=>[\]{|}]*|\|[^<=>[\]{|}]*?=|&amp;(?:#\d+|#[Xx][0-9A-F]+|[a-z]{4,6});', ur'<code>\g<0></code>', html)
	# Save bytes
	html = re.sub(ur'</code>(\s*)<code>', ur'\1', html)
	# shadow [[target|of link]]
	html = re.sub(ur'\[\[</code>([^<>{|}[\]\n]+)<code>\|(?!\]\])', ur'[[\1|', html)
	# <!-- comments -->
	html = re.sub(ur'&lt;!--.*?--&gt;', ur'<span class="cmt">\g<0></span>', html, flags=re.DOTALL)

	# TODO add reveal button
	printu('<span class="context">%s</span>'%(html\
	  .replace('\n&lt;removed&gt;',   u'</span><div class="removed"><span>')\
	  .replace('&lt;/removed&gt;\n',  u'</span></div><span class="context">')\
	  .replace('\n&lt;removed2&gt;',  u'</span><div class="removed2" style="display:none;"><span>')\
	  .replace('&lt;/removed2&gt;\n', u'</span></div><span class="context">'),))


def findTemplateLinksTo(page, ns, title):
	with toolsql.getConn(page.site().dbName(), cluster='web') as cursor:
		cursor.execute("""
SELECT CONCAT(
 IF(tl_namespace=0,   "",
 IF(tl_namespace=1,   "Talk:", 
 IF(tl_namespace=2,   "User:", 
 IF(tl_namespace=3,   "User_talk:", 
 IF(tl_namespace=4,   "Wikipedia:", 
 IF(tl_namespace=5,   "Wikipedia_talk:", 
 IF(tl_namespace=6,   "File:", 
 IF(tl_namespace=7,   "File_talk:", 
 IF(tl_namespace=8,   "MediaWiki:", 
 IF(tl_namespace=9,   "MediaWiki_talk:", 
 IF(tl_namespace=10,  "Template:", 
 IF(tl_namespace=11,  "Template_talk:", 
 IF(tl_namespace=12,  "Help:", 
 IF(tl_namespace=13,  "Help_talk:", 
 IF(tl_namespace=14,  "Category:", 
 IF(tl_namespace=15,  "Category_talk:", 
 IF(tl_namespace=100, "Portal:", 
 IF(tl_namespace=101, "Portal_talk:", 
 IF(tl_namespace=108, "Book:", 
 IF(tl_namespace=109, "Book_talk:", 
 IF(tl_namespace=118, "Draft:", 
 IF(tl_namespace=119, "Draft_talk:", 
 IF(tl_namespace=710, "TimedText:", 
 IF(tl_namespace=711, "TimedText_talk:", 
 IF(tl_namespace=828, "Module:", 
 IF(tl_namespace=829, "Module_talk:", 
 CONCAT("{ns:",tl_namespace,"}:")
 )))))))))))))))))))))))))),tl_title) AS Template_name
FROM page AS dab
JOIN templatelinks ON tl_from = dab.page_id
JOIN page AS tl    ON tl.page_namespace=tl_namespace AND tl.page_title=tl_title
JOIN pagelinks     ON pl_from = tl.page_id
WHERE dab.page_namespace = ? AND dab.page_title = ?
AND pl_namespace = ?         AND pl_title = ?
/* Excluded self-transclusion */
AND NOT (tl_namespace=dab.page_namespace AND tl_title=dab.page_title)
LIMIT 1""", (
	page.namespace(), page.titleWithoutNamespace(underscore=True),
	ns,title.replace(' ', '_'),
), max_time=1)
		return cursor.fetchone()

def get_dpl_links(page):
	try:
		with toolsql.getConn('s51290__dpl_p', host='tools.labsdb') as cursor:
			cursor.execute("""
SELECT DISTINCT redirect_title
FROM all_dab_links
JOIN contest_dabs ON c_id=dab_id
WHERE article_id=?
""", (page.id,), max_time=1)
			return tuple(link for (link, ) in cursor.fetchall())
	except (toolsql.InterfaceError, toolsql.OperationalError) as e: # Cannot connect
		return []



def main():
	site = wikipedia.getSite()
	page = None
	verbose = False
	usecommonfixes = False
	disambig_links = {}
	editintro = None
	ignoreCircularLinking = True
	summarytrail = None
	useapi = True
	wysiwyg=False
	for arg in wikipedia.handleArgs():
		if arg.startswith('-page:') and arg[6:]:
			page = wikipedia.Page(site, arg[6:])
			site = page.site()
		elif arg.startswith('-commonfixes'):
			usecommonfixes = bool(arg[12:])
		elif arg.startswith(('-all', '-force',)):
			ignoreCircularLinking = True
		# TODO change fixlinks to something better
		elif arg.startswith(('-link:', '-fixlinks:',)):
			for link in arg[arg.index(':')+1:].split('|'):
				disambig_links[canonicalTitle(link)] = 0
		elif arg.startswith('-editintro:'):
			editintro = arg[11:]
		elif arg.startswith('-summarytrail:'):
			summarytrail = arg[14:].replace('_',' ')
		elif arg.startswith('-wysiwyg'):
			wysiwyg = True
			

	# TODO this probably should be integrated with canonicalTitle
	def htmllink(title, label=None):
		if not label: label=title
		return '<a href="//%s%s">%s</a>' % (site.hostname(), site.nice_get_address(quote(title.replace(' ', '_'))), label)

	if not page: # -page: not used
		html(u'<img src="//bits.wikimedia.org/skins-1.5/common/images/redirectltr.png" alt="#REDIRECT " /><span class="redirectText"><a href="../view/Dab_solver">tools:~dispenser/view/Dab solver</a></span>')
		return

	logtime("args read in")
	try:
		text = page.get()
		logtime("Page text gotten")
	except wikipedia.IsRedirectPage:
		skiptask()
		taskid = wikipedia.SysArgs.get('task', '')
		target = wikipedia.Page(site, page._redirarg)
		html(u'<img src="https://upload.wikimedia.org/wikipedia/commons/b/b5/Redirectltr.png" alt="#REDIRECT " /><a href="?page=%s&taskid=%s" class="redirectText">%s</a>' % (target.title(asUrl=True, allowInterwiki=True), taskid, target.title(),))
		return
	except wikipedia.NoPage:
		skiptask()
		wikipedia.output(u'Page %s not found ' % page.aslink())
		return
	except wikipedia.ServerError:
		wikipedia.output(u'Wikimedia server error.  Please try again later.')
		return
	except Exception, e:
		wikipedia.output('Error: %r'%e)
		raise
	
	if not useapi:
		with toolsql.getConn(site.dbName(), cluster='web') as cursor:
			cursor.execute("SELECT page_latest FROM page WHERE page_namespace=? AND page_title=?", (page.namespace(), page.titleWithoutNamespace(underscore=True),), max_time=20)
			page_latest = cursor.fetchone()
			print '<!--', 'DB rev:', page_latest, 'Page rev:', page.revisionid, '-->'
			if (page.revisionid, ) != page_latest and page.revisionid:
				#print '<div class="mw-warning">%s</div>'%wikipedia.translate(site, OutOfSync).encode('utf-8')
				# Use API instead
				useapi = True
			logtime("Database (rrdb) loaded and checked")

	# Translation stuff
	if site.language() not in NoLinksInText.keys():
		html(u'<div class="mw-warning">The interface is not translated into your language [%s] &mdash; <a href="//en.wikipedia.org/wiki/User:Dispenser/Dab_solver#Translation">you can help translate it</a></div>', (site.language(),))
	
	printu(r'<script type="text/javascript">window.dn_R = /\{\{(?:%s)(?:\|[^{|}=]*=[^{|}]*)*\}\}/g;</script>' % (wikipedia.translate(site, dnTags),))

	if summarytrail:
		html('<script type="text/javascript">window.summarytrail=%s;</script>' % (wikipedia.jsescape(summarytrail),))
	
	if editintro:
		print site.getUrl(site.page_action_address(editintro, "render"))
		printu('<div style="float:right;">%s</div>' % (htmllink(canonicalTitle(editintro), "Edit notice"),))
		logtime("Database: Loaded editintro")

	dpl_links = []
	if site.dbName().startswith("enwiki"):
		try:
			dpl_links = get_dpl_links(page)
			print '<div class="mw-warning dplinfobox">%s&emsp;/&emsp;<span id="dpl_info">%s</span>%s</div>' % (
				'<a href="//tools.wmflabs.org/dplbot/ch/dab_challenge.php" style="background-color:#ffd;"><b>%d</b> %s</a> on this page'%(
					len(dpl_links),
					'point' if len(dpl_links)==1 else 'points',
				),
				'<a href="../cgi-bin/watchlist_points.py">Disambiguate pages on your watchlist</a>',
				# addOnloadHook so it doesn't delay onload
				'<script type="text/javascript">addOnloadHook(importScriptURI(%s));</script>' % (
					wikipedia.jsescape('../cgi-bin/dplinfo.py?user='+quote(wikipedia.SysArgs.get('username',''))),
				),
			)
			logtime("Database: DAB challenge displayed")
		except toolsql.Error as e:
			logtime("Failed to retrieve DAB challenge score")


	# Get disambiguation pages
	if useapi:
		dab_query = api_getDabLinks(site.dbName(), page.namespace(), page.titleWithoutNamespace(underscore=True))
	else:
		dab_query = getDabLinks(site.dbName(), page.namespace(), page.titleWithoutNamespace(underscore=True))
	
	for tup in dab_query:
		# pl_namespace, ns_name+pl_title, linksback, tl_title, rd_namespace, rd_title
		if tup[0] == 0: # XXX look at main namespace only
			if not tup[2] or ignoreCircularLinking:
				disambig_links[canonicalTitle(tup[1])] = 0
	logtime("Database: found disambig links (%d)" % len(dab_query))
	
	try:
		with toolsql.getConn(page.site().dbName(), cluster='web') as cursor:
			cursor.execute("""
SELECT pl_title
FROM pagelinks
LEFT JOIN page ON page_namespace=pl_namespace AND page_title=pl_title
WHERE pl_from=? AND page_id IS NULL
""", (page.id, ), max_time=20)
			for red_title, in cursor.fetchall():
				redlinks[red_title] = True
			logtime("Got red links")
	except toolsql.DatabaseError:
			logtime("Fail red links")
		
#	# Shortcut: No links found - always "disambiguate" {{dn}} links
#	if disambig_links == {} and not re.search(ur'\{\{'+wikipedia.translate(site, dnTags), text):
#		printu('<pre class="workarea" id="workarea"></pre>')
#		wikipedia.output(wikipedia.translate(site, NoLinksInText)%dict(title=page.title()))
#		return
	
	# Prettify links (_ -> (space), unprecent encode)
	if usecommonfixes:
		logtime("Running commonfixes branch")
		print '<div style="max-height:5em; overflow:auto;">'
		import commonfixes
		text = commonfixes.fix(text, page = page, verbose = verbose)
		print '</div>'
		# If commonfixes had an effect, include the marker in the edit summary
		if text != page.get():
			print '<span id="commonfixes:yes"></span>'
		logtime("Finish commonfixes branch")
	
	## change {{dn|link|title}} to [[link|title]]{{dn}}
	replacements = []
	for pattern, repl in wikipedia.translate(site, ReplaceTemplates):
		for match in re.finditer(pattern, text):
			# XXX Avoid back-converting existing text in second phase
			if match.expand(repl) not in text:
				text = text.replace(match.group(), match.expand(repl))
				replacements.append((match.group(), match.expand(repl)))

	# Regular expression for finding bracketed links
	InternalLinksR = re.compile(r"(?<=\[\[)(?P<link>[^{|}[\]\n<>]+?)(?=(?:\|.*?|)\]\])")
	
	# Build list of [[regular links]]
	bracketLinks = {}
	for match in InternalLinksR.finditer(text):
		bracketLinks[canonicalTitle(match.group('link'))] = True

	# Regular expression for finding [[links]] and |authorlink=link}}
	pagelinkR = re.compile(ur"(?:\[\[|(?P<tpl>\|[^{|}[\]]+=\s*|\|))(?P<link>[^{|}[\]\n<>]+?)(?(tpl)(?=\s*\||\s*\}\})|(?:\|(?:[^\n\[]|\[(?!\[))*?)?\]\]'??\w*(?P<dnTag>[\"',.:; ]*?{\{(?:"+wikipedia.translate(site, dnTags)+ur")(?:(?:\|\s*)+date\s*=[^{}]*|)\}\})?)")
	logtime("Pre-initialize link matching")
			
	def byHowMuch(m):
		# TODO Add thousand separator locale.format()
		if wikipedia.SysArgs.get('username','') != 'Dispenser' or 1:
			return wikipedia.translate(site, RemovedText) % (
			m.group('begin'),
			m.group('removed').count('\n'),
			len(m.group('removed')),
			m.group('end'),
		)
		else:
			return '|||||||||||||||||||||||||||||||||||||||||||||||||'.join((
			m.group('begin'),
			'<div style="background:#ddf">',
			m.group('removed'),
			'</div>',
			m.group('end'),
		))

	count   = 0
	offset  = 0
	newtext = ""
	printu('<pre class="workarea" id="workarea">')
	for match in pagelinkR.finditer(text):
		start, end = match.span()
		mwtitle = canonicalTitle(match.group('link')) 
		if match.group('dnTag'):
			pass
		elif mwtitle in disambig_links:
			if match.group('tpl') and mwtitle in bracketLinks:
				continue
			pass
		else:
			continue
		
		printfmt(OmitR.sub(ur'\g<end>' if count==0 else byHowMuch, prettify(text[offset:start])))
		newtext += text[offset:start]
		
		# Picker drop down
		link_id = u"<<link:%d>>"%count
		html(u'<span class="inputbox%s"><select><option></option></select><input class="match inactive" id="%s" title="%s" value="%s" size="%d" /></span>', (
			u" dpl_link" if mwtitle.replace(' ', '_') in dpl_links else "",
			link_id,
			mwtitle,
			match.group(),
			len(match.group()),
		))
		newtext += link_id
		if mwtitle in disambig_links:
			disambig_links[mwtitle] += 1
		count += 1
		offset = end
	else:
		if count > 0: # print the rest
			printfmt(OmitR.sub(ur'\g<begin>', prettify(text[offset:]) ))
			newtext += text[offset:]
	html('</pre>')
	html('''<a id="dblscrollbtn" href="javascript:" onclick="with(document.getElementById('workarea')){style.height=(style.height!='30em'?'30em':'auto');setCookie('doublescroll', 'false', style.height=='30em'?(new Date()).toUTCString():null, window.location.pathname); this.firstChild.nodeValue=(style.height!='30em'?'Double scrollbars':'Single scrollbar');}">Single scrollbar</a>''')
	logtime("Link matching complete")

	if wysiwyg: # Test mode
		logtime('begin wysiwyg mode')
		wys_api_call = {
			'action': 'parse',
			'format': 'json',
			'title':  page.title(),
			'text': re.sub(r'<<link:(\d+)>>', r'[[Special:DisambiguationPages/\1]]', newtext),
			'prop': 'text|headitems|headhtml', # Only get HTML
			'disableeditsection': 'true',
		}
		import json
		logtime('wysiwyg api call start')
		json_data = site.getUrl(site.apipath(), wys_api_call)
		dict_data = json.loads(json_data)
		logtime('wysiwyg json loaded')
		print '<xmp>', repr(dict_data), '</xmp>'
		print dict_data['parse']['text']['*'].encode('utf-8')
		logtime('wysiwyg printed')

	# after the main elements
	# setTimeout was used to let browser's throbber reset
	#html('<script type="text/javascript">if(window.initFields) setTimeout("initFields()"); else alert("initFields() is not defined.  Please refreshing the page.");</script>')
	html('<script type="text/javascript">if(window.initFields) initFields(); else alert("initFields() is not defined.  Please refreshing the page.");</script>')
	sys.stdout.flush()

	# Undo ReplaceTemplates which weren't used
	for pattern, repl in replacements:
		newtext = newtext.replace(repl, pattern)

	logtime("Form created")

	if count > 0:
		page.put(newtext, comment='', minorEdit=True)
		html('<script type="text/javascript">if(window.initForm)initForm(); else alert("initForm() is not defined.  Please refreshing the page.");</script>')
		logtime("Created edit box")
	else:
		skiptask()
		wikipedia.output(wikipedia.translate(site, NoLinksInText)%dict(title=page.title()))
	
	try:
		for mwtitle, count in disambig_links.iteritems():
			# Skip working non-template links
			if count > 0 and mwtitle in bracketLinks:
				continue
			transcludes = findTemplateLinksTo(page, 0, mwtitle)
			if transcludes and transcludes[0]:
				printu((wikipedia.escape(wikipedia.translate(site, LinkTranscluded))) % dict(
					disambig=htmllink(mwtitle),
					page=htmllink(canonicalTitle(transcludes[0])),
					fixlink=u'<a href="../cgi-bin/dab_solver.py?page=%s%s%s">%s</a>'%(
						quote(transcludes[0]),
						u'&amp;dbname='+quote(site.dbName()) if site.dbName() != 'enwiki' else u'',
						u'&amp;commonfixes=yes' if usecommonfixes else u'',
						# TODO i18n
						u'fix\u00A0link',
					)
				))
				printu('<br/>')
			else:
				if count == 0:
					printu((wikipedia.translate(site, LinkNotInText)) % (htmllink(mwtitle),))
					printu('<br/>')
			wikipedia.logtime('findTemplateLinksTo([this page], 0, %r)'%(mwtitle,))
	except toolsql.QueryTimedOut as e:
		print("<div>findTemplateLinksTo() took too long</div>")
	
if __name__ == "__main__" and wikipedia.handleUrlAndHeader(defaultRedirect="/~dispenser/view/Dab_solver"):
	logtime("Program loaded")
	try:
		wikipedia.startContent(form=True, head='\n'.join((
			'<link rel="stylesheet" href="../resources/dab_solver.css" type="text/css" />',
			'<script src="../resources/dab_solver.js" type="text/javascript"></script>',
			'<script src="../resources/mosdab_checker.js" type="text/javascript" async="async"></script>',
			'<link href="https://upload.wikimedia.org/wikipedia/commons/thumb/3/38/Disambig_azure_Broom_icon.svg/152px-Disambig_azure_Broom_icon.svg.png" rel="apple-touch-icon" />',
			'<link rel="icon" type="image/png" href="https://upload.wikimedia.org/wikipedia/commons/thumb/3/38/Disambig_azure_Broom_icon.svg/32px-Disambig_azure_Broom_icon.svg.png" />',
		)))
		main()
	except toolsql.DatabaseError as (errno, strerror, extra):
		# Something went wrong with the database
		# 1040 "Too many connections":
		# 1053 "Server shutdown in progress": Connected too long?
		# 1226 "User %r has exceeded the %r resource": Too many user connections
		# 1267 "Illegal mix of collation": s3 is still running MySQL 4
		# 1290 "--read-only option"
		# 1317 "Query execution was interrupted" (query-killer)
		# 2006 "MySQL server has gone away":
		# 2013 "Lost connection to MySQL server during query":
		# 2014 "Commands out of sync; you can't run this command now":
		# 2027 "Malformed packet"
		if errno in (1040, 1053, 1226, 1317, 2006, 2013):
			html('<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>')
			html('<p>%s</p><blockquote>%s</blockquote>', (wikipedia.translate(wikipedia.getSite(), NoOpenConnections), repr((errno, strerror, extra)),))
			pass
		else:
			html('<p class="errormsg">Database Error (%d): %s</p>', (errno, wikipedia.escape(strerror),))
			raise
	finally:
		wikipedia.endContent()
		wikipedia.stopme()

