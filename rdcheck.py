#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
Good example
  http://dispenser.info.tm/~dispenser/cgi-bin/rdcheck.py?page=BioShock


/* If you want these results in a machine readable form */
SELECT page_namespace, page_title, rd_namespace, rd_title, rd_fragment
FROM redirect
JOIN page ON page_id=rd_from
WHERE rd_namespace=0 AND rd_title="Ebola_virus_disease"

"""
import re, difflib
import wikipedia, pagegenerators
import toolsql
import cgitb; cgitb.enable(logdir='tracebacks')

# FIXME properly implement localization
# allow {{flag}} : http://en.wikipedia.org/w/index.php?title=Supermarkets_in_Australia&redirect=no
# FIXME support full-wide wikitext characters
# https://ja.wikipedia.org/wiki/?curid=2264414&action=edit
redirect_R = re.compile(ur'^\s*[#＃](?:REDIRECT:?|\w+).*?\s*\[\[(?P<link>[^\n|[\]]*?)(\|[^\n[\]]*)?\]\]', re.U | re.DOTALL)

wikilink_R = re.compile(ur'\[\[(.*?)\]\]')
def printwt(format, values=()):
	#s = re.sub(r'\[\[([^<>{|}[\]]+)\]\]', r'[[\1|\1]]', s)
	def q(s):
		return wikipedia.escape(s) if isinstance(s, (str, unicode)) else s
	def linkme(m):
		return ur'<a href="https://%s/wiki/%s" title="%s :: linkme">%s</a>'%(
			site.hostname(),
			wikipedia.urllib.quote(m.group(1).replace(' ', '_').encode('utf-8'), safe=";@$!*(),/:"),
			m.group(1),
			m.group(1),
		)
	print wikilink_R.sub(linkme, format%tuple(q(s) for s in values)).encode('utf-8')

def heading(anchor, text):
	print('<h3 id="%s">%s<a class="headerlink" href="#%s" title="Permalink to this headline">§</a></h3>' % (anchor, text, anchor))

#def makelink(site, title, label=None):
#	return '<a href="https://%s%s" title="%s">%s</a>' % tuple(wikipedia.escape(s) for s in (site.hostname(), site.nice_get_address(wikipedia.urllib.quote(title.replace(' ', '_'), safe=";@$!*(),/:")), title, label or title))

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
	t = wikipedia.canonicalTitle(t, firstupper)
	if not t: return ''
	# Workaround for titles with an escape char
	if firstupper and t[0].upper() != t[0].lower() and not (t.isupper() and len(t) > 1):
		t = ur'[%s%s]%s' % (t[0].upper(), t[0].lower(), t[1:],)
	return re.sub(ur'[-()*+?.,\\^$"]', ur'\\\g<0>', t).replace(u' ', u'[ _]+')


def decode_fragment(fragment):
	fragment = re.sub(r'''
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
	''', lambda m: m.group().replace('.', '%'), fragment.encode('utf-8').replace('%', '.25'), flags=re.X)
	return wikipedia.urllib.unquote(fragment).decode('utf-8').replace('_', ' ')

def redirects_to(page):
	if not page.title():
		return
	global site # used by printwt()
	site = page.site()
	# Get the HTML from the site direct, redirects are dealt with 
	# by reading the target on one of the tab links
	try:
		html = site.getUrl(site.nice_get_address(page.urlname())).decode('utf-8')
		historytab = re.search(ur'<li id="ca-history"[^<>]*>.*?<a href="[^"]*?title=([^"&]*)', html)
	except Exception as e:
		wikipedia.output('Error: %r'%e)
		return
	else:
		# Check to see if there's a history tab, if not then the page does not exist
		if not historytab:
			wikipedia.output("%s does not exist on %s"%(page.aslink(), page.site().sitename()))
			return
	wikipedia.logtime("Got page html")

	target_title = wikipedia.urllib.unquote(historytab.group(1).encode('utf-8')).decode('utf-8')
	try:
		target_ns    = int(re.search(ur'\bwgNamespaceNumber\W+\b(\d+)\b', html).group(1))
	except ValueError:
		target_ns = 0
	# pywikipedia is crap
	target = wikipedia.Page(site, target_title.split(u':', 1)[1] if target_ns > 0 else target_title, defaultNamespace=target_ns)
	printwt(u'<h2 id="%s">%s<a class="headerlink" href="#%s" title="Permalink to this headline">¶</a></h2>', (wikipedia.sectionencode(target_title), target_title.replace('_', ' '), wikipedia.sectionencode(target_title), ) )

	
	contents_html = html[html.find(u' id="mw-content-text"')+1:html.find(u' class="printfooter')] # fault tolerant
	# create dictionary of IDs
	ids = {}
	page_anchors = {}
	unescaped_anchors = {} # Used as the prettist fragment
	citephpcount = 0
	for m in re.finditer(ur'<([a-z]+(?= ))[^<>]*? id="(?P<id>[^"]*)"[^<>]*?>[^<>]*(?:</\1>)?', contents_html):
		anchor = m.group('id')
		if anchor not in ids:
			ids[anchor] = m.group()
		else:
			pass
			#wikipedia.output("%s\nID \"%s\" is already defined \n"%(m.group().replace(anchor, '\03{lightred}%s\03{default}'%anchor), anchor, )) 
			#print ('<p><code>%s</code><br /><em>Line %d</em>: <span style="font-weight:bold;">ID "%s" is already defined here</span>:<br /><code style="margin-left:2em;">%s</code></p>'%(
			#	wikipedia.escape(m.group()).replace(anchor, '<span class="error">%s</span>'%anchor),
			#	contents_html[:m.start()].count('\n'),
			#	anchor,
			#	wikipedia.escape(ids[anchor]),
			#))

		if anchor in ('toc', 'toctitle', 'mw-normal-catlinks', 'mw-hidden-catlinks', ):
			pass
		elif anchor.startswith('cite_ref-') or anchor.startswith('cite_note-'):
			citephpcount += 1
		else:
			page_anchors[anchor] = anchor
			# Attempt to decode UTF-8 anchor
			if u'.' in anchor:
				decoded_anchor = decode_fragment(anchor)
				# Why this extra trouble?: GunName.B2.37
				if decoded_anchor in contents_html:
					unescaped_anchors[anchor] = decoded_anchor
	wikipedia.logtime("Processed page")


	cursor = toolsql.getConn(site.dbName(), cluster='web').cursor()
	cursor.execute('''
SELECT 
  page_namespace, 
  page_title,
  CONCAT(
 IF(page_namespace=0,   "",
 IF(page_namespace=1,   "Talk:", 
 IF(page_namespace=2,   "User:", 
 IF(page_namespace=3,   "User_talk:", 
 IF(page_namespace=4,   "Wikipedia:", 
 IF(page_namespace=5,   "Wikipedia_talk:", 
 IF(page_namespace=6,   "File:", 
 IF(page_namespace=7,   "File_talk:", 
 IF(page_namespace=8,   "MediaWiki:", 
 IF(page_namespace=9,   "MediaWiki_talk:", 
 IF(page_namespace=10,  "Template:", 
 IF(page_namespace=11,  "Template_talk:", 
 IF(page_namespace=12,  "Help:", 
 IF(page_namespace=13,  "Help_talk:", 
 IF(page_namespace=14,  "Category:", 
 IF(page_namespace=15,  "Category_talk:", 
 IF(page_namespace=100, "Portal:", 
 IF(page_namespace=101, "Portal_talk:", 
 IF(page_namespace=108, "Book:", 
 IF(page_namespace=109, "Book_talk:", 
 IF(page_namespace=118, "Draft:", 
 IF(page_namespace=119, "Draft_talk:", 
 IF(page_namespace=710, "TimedText:", 
 IF(page_namespace=711, "TimedText_talk:", 
 IF(page_namespace=828, "Module:", 
 IF(page_namespace=829, "Module_talk:", 
 CONCAT("{ns:",page_namespace,"}:")
  )))))))))))))))))))))))))),page_title) AS page_title_full,
  IFNULL(rd_fragment, '') AS fragment
FROM redirect
JOIN page ON page_id=rd_from
WHERE rd_namespace=? AND rd_title=?
ORDER BY 3 
''', (target.namespace(), target.titleWithoutNamespace(underscore=True),), max_time=60)
	wikipedia.logtime("Query redirect fragments")
	
	results = {}
	
	redirects = [] # Used for regex program
	for page_namespace, page_title, title, rd_fragment in cursor:
		#print page_namespace, page_title, rd_fragment
		
		fragment = wikipedia.sectionencode(rd_fragment)
		
		# Kill stray links
		if fragment not in results:
			results[fragment] = []
		results[fragment].append(title.replace('_', ' '))
		
		redirects.append(title)
		if fragment and len(unescaped_anchors.get(fragment, fragment)) >= len(fragment):
			unescaped_anchors[fragment] = rd_fragment.replace('_', ' ')
	
	if results and any(key not in ids for key in results.iterkeys() if key):
		print('<div class="ambox ambox-style notice">Redirects to <b>broken anchors</b> should be retargeted to the correct section or by re-adding the anchor: <code class="example" style="white-space:nowrap;">== Film {{<a href="https://en.wikipedia.org/wiki/Template:Anchor">anchor</a>|Movie}}==</code></div>')
	
	if results:
		if results.keys() == ['']:
			printwt('<p>The following %d pages redirect to <b>%s</b>.</p>', (len(redirects), page.aslink(),))
		else:
			printwt('<p>The following %d pages redirect to <b>%s</b>, grouped by <a href="https://en.wikipedia.org/wiki/Help:Anchors">anchor</a>.</p>', (len(redirects), page.aslink(),))
	else:
		printwt("<p>No redirects to <b>%s</b></p>", (page.aslink(),))

	
	if len(results.get('', {})) >= 6:
		results[''].append(target.title())

	for fragment in sorted(results.keys(), key=lambda k: re.sub(ur'(?<![,.])(\d+)', lambda m:m.group(1).zfill(7), k)):
		# Heading
		if fragment == '':
			if len(results) != 1:
				printwt('<h3><i class="nosections">No anchor</i></h3>')
		elif fragment in ids:
			printwt('<h3><a href="https://%s%s#%s">%s</a></h3>', (site.hostname(), site.nice_get_address(page.urlname()), fragment, unescaped_anchors.get(fragment, fragment),))
		else:
			printwt('<h3 class="brokenanchor"><a href="https://%s%s#%s">%s</a> <span class="error">(broken)</span></h3>', (site.hostname(), site.nice_get_address(page.urlname()), fragment, unescaped_anchors.get(fragment, fragment),))
			# Broken anchor.  Suggest similarily named anchors on the page.
			similar = {}
			# Alternate titles based on redirects base names (e.g. shimigami not finding Lord Death when lord death is a redirect)
			# But also avoid camouflage (domain) matching everything camouflage on the page
			myrds = []
			for rd_title in results[fragment]:
				rdt = rd_title[:rd_title.find(' (')+1 or None].strip()
				if len(rdt) >= 3 and rdt!=target.title() and rdt not in results.get('', {}):
					myrds.append(rdt)

			for existing_anchor in page_anchors.keys():
				if len(existing_anchor) <= 2:
					continue
				#existing_anchor = unescaped_anchors.get(existing_anchor, existing_anchor)
				# Compare anchor
				s = difflib.SequenceMatcher(None, decode_fragment(fragment), decode_fragment(existing_anchor))
				if s.ratio() >= 0.50:
					similar[existing_anchor] = s.ratio()
				# Compare redirect titles
				for alt_title in myrds:
					s = difflib.SequenceMatcher(None, alt_title, decode_fragment(existing_anchor))
					if s.ratio() >= 0.50 and s.ratio() > similar.get(existing_anchor, 0):
						similar[existing_anchor] = s.ratio()
						
			if similar:
				similar_sorted = sorted(similar.keys(), key=lambda k: similar[k], reverse=True)[:5] # Top 5
				print('<p>Possible replacement targets: %s</p>'%', '.join('<a href="https://%s%s#%s"><code>%s</code></a>'%tuple(wikipedia.escape(s).encode('utf-8') for s in (
					site.hostname(),
					site.nice_get_address(page.urlname()),
					anchor,
					unescaped_anchors.get(anchor, anchor),
				)) for anchor in similar_sorted ))
		
		print '<ul class="notarget">' if fragment=='' else '<ul class="target">'
		
		result = results[fragment]
		result.sort(key=unicode.lower)#lambda s: ''.join(c.upper()+c.lower() for c in s))
		for title in result:
			if title == target.title():
				printwt('<li><strong class="selflink">%s</strong></li>', (title,))
			else:
				urlname = wikipedia.urllib.quote(title.replace(' ', '_').encode('utf-8'), safe=";@$!*(),/:")
				printwt('<li{}><a href="https://%s%s">%s</a></li>'.format(
				' class="anchor_match"' if wikipedia.sectionencode(title) in page_anchors else ''
				), (
					
					site.hostname(),
					site.get_address(urlname),
					title,
				))

		print '</ul>'
	printwt(u"<!-- %d anchors, %d citation anchors -->", (len(ids), citephpcount,))
	
	# FIXME Check if sort unicode == sort binary
	# TODO Add MW API redirect information
	# TODO Add expliantion on regex and what this is for
	# TODO Add fancy animation
	# Print regular expression
	if results:
	#	regex = '|'.join(tuple(wikilinkregex(s).encode('utf-8') for s in ([target_title]+sorted(redirects))))
		regex = u''
		regexp_redirects = {}
		for s in [target_title]+redirects:
			i = s.find(':')+1
			if s[:i] not in regexp_redirects:
				regexp_redirects[s[:i]] = []
			regexp_redirects[s[:i]].append(s[i:])
		for p in sorted(regexp_redirects.keys()):
			regex += "|%s(?:%s)" % (wikilinkregex(p), '|'.join(wikilinkregex(s) for s in sorted(regexp_redirects[p], key=lambda s: s.upper().encode('utf-8').ljust(255, '\xFF') )),)
			
		print('''
<p><a href="javascript:" onclick="this.style.display='none'; var x=this.parentNode.nextSibling; x.style.display=''; x.getElementsByTagName('input')[0].focus()">
  Get regex for AutoWikiBrowser
</a>
</p><div style="display:none;">
<input type="text" value="%s" style="width:100%%; width:calc(100%% - 5em); " readOnly="readOnly" onfocus="this.select();" />
<div>

</div>
</div>''' % (wikipedia.escape(regex[1:].encode('utf-8')),))


def main():
	genFactory = pagegenerators.GeneratorFactory()
	for arg in wikipedia.handleArgs():
		if not genFactory.handleArg(arg):
			wikipedia.output(u'Parameter %r not understood' % arg)
	generator = genFactory.getCombinedGenerator() or None
	
	if not generator:
		wikipedia.showHelp('rdcheck')
		return

	wikipedia.logtime("Initialized")
	for page in generator:
		redirects_to(page)

if __name__ == "__main__" and wikipedia.handleUrlAndHeader(defaultRedirect="/~dispenser/view/Rdcheck"):
    try:
        wikipedia.startContent(form=True, head="""<style type='text/css'>
.notice {
  background:url(https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Icons8_flat_broken_link.svg/40px-Icons8_flat_broken_link.svg.png) 10px center no-repeat;
  padding-left:60px;
  min-height:40px;
}
code { background-color:#eee; }
.selflink{color:#666;}
.notarget .anchor_match::after {
	content: " †";
	color: green;
}
.notarget .anchor_match:hover::after {
	content: " (matches an anchor)";
}
.regex { } 
.regex.show { }
</style>
""")
        main()
    finally:
        wikipedia.endContent()
        wikipedia.stopme()
