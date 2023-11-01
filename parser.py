# -*- coding: utf-8  -*-
"""
wikiparser.py

MediaWiki text to HTML processor
Dispenser 2008
"""
import re
from htmlentitydefs import name2codepoint 
import cgitb; cgitb.enable()

autonumber = 0
refindex = 1
safe_map = {}
monthname = {
	'01':	'January',
	'02':	'February',
	'03':	'March',
	'04':	'April',
	'05':	'May',
	'06':	'June',
	'07':	'July',
	'08':	'August',
	'09':	'September',
	'10':	'October',
	'11':	'November',
	'12':	'December',
	}

def parser(text, hostname=None, allowComments=False, allowHtml=True, docroot=None, sanitize=True):
	if not docroot: docroot = "//%s/wiki/" % (hostname or "en.wikipedia.org")

	# Nowiki
	if '<nowik' in text:
		for m in re.finditer('<nowiki>(.*?)</nowiki>', text):
			text = text.replace(m.group(), nowiki(m.group(1)))
	
	# <references />
	if '<references' in text:
		dict = {}
		reflist = []
		global refindex
		for match in re.finditer(r'(?is)<ref(?P<params>[^/]*?)>(?P<content>.*?)</ref>', text):
			named = re.search(' name\s*=\s*(?P<quote>[\'"]?)(?P<name>.+)(?P=quote)', match.group('params'))
			if named:
				dict[named.group('name')] = refindex
				name = named.group('name')
			else:
				name = refindex

			text = text.replace(match.group(), '<sup id="cite_ref-%s" class="reference"><a href="#cite_note-%s">[%d]</a></sup>'%(name, name, refindex), 1)
			reflist.append('<li id="cite_note-%s"><a href="#cite_ref-%s">&#x2191;</a> '%(name, name) + match.group('content') + '</li>')

			refindex += 1

		for match in re.finditer(r'(?is)<ref(?P<params>[^/>]*?)/>', text):
			named = re.search(' name\s*=\s*(?P<quote>[\'"]?)(?P<name>.+)(?P=quote)', match.group('params'))
			try:
				name = named.group('name').strip()
				text = text.replace(match.group(), '<a href="#cite_ref-%s"><sup>[%d]</sup></a>'%(name,dict[name]))
			except:
				pass
		
		text = re.sub('<references .*?/>', '<ol class="references">'+('\n'.join(reflist))+'\n</ol>', text, 1)
	

	# Disable HTML
	if not allowHtml:
		text = text.replace('<', '&lt;').replace('>', '&gt;')

	else:
		# <PRE> blocks
		if '</pre>' in text:
			for m in re.finditer(r'(?is)<pre>(.*?)</pre>', text):
				text = text.replace(m.group(), "<pre>%s</pre>"%nowiki(m.group(1).strip()))
	
		# sanitize remaining HTML
		if sanitize:
			for m in re.finditer(r'</?(\w+).', text):
				if m.group(1) not in ("abbr", "b", "big", "blockquote", "br", "caption", "center", "cite", "code", "dd", "div", "dl", "dt", "em", "font", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "li", "ol", "p", "pre", "rb", "rp", "rt", "ruby", "s", "span", "small", "strike", "strong", "sub", "sup", "table", "td", "th", "tr", "tt", "u", "ul", "var",
				):
					text=text.replace(m.group(), '&lt;'+m.group()[1:])
		else:
			text = hideText(text)
		
		# Comments
		if '<!--' in text and not allowComments:
			text = re.sub(r'(?s)<!--.*?-->', r'', text.expandtabs()).strip()
	
	# #REDIRECT img rendering
	if '#REDIRECT' == text[:9]:
		text = re.sub(r'^#REDIRECT *(.*)', r'<img src="//bits.wikimedia.org/skins-1.5/common/images/redirectltr.png" alt="#REDIRECT " /><span class="redirectText">\1</span>', text)

	# <math>
	if '&lt;math' in text:
		text = re.sub(r'(?is)&lt;math>(.*?)&lt;/math>', r'<img class="tex" alt="Math tag" src="//upload.wikimedia.org/math/e/e/6/ee6329486d72b1cc1b8a0e2092ddd419.png" />', text)

	# Template (Fake)
	if '{{' in text:
		text = text.replace(r'{{FA-star}}', r'<img alt="Featured article" src="//upload.wikimedia.org/wikipedia/commons/thumb/b/bc/Featured_article_star.svg/16px-Featured_article_star.svg.png"  height="16" width="16" />')
		text = re.sub(r'(?s)\{\{\s*([^][{|}]+?)\s*(|\|[^{}]*)\}\}', r'{{[[Template:\1|\1]]}}', text)

	# Tables
	if '\n|}' in text:
		stack = [text.find('{|')]
		while 20 > len(stack) > 0:
			start = stack.pop()
			if start == -1:
				continue
			end   = text.find('|}', start+2)
			nextStart = text.find('{|', start+2)
			
			if end > nextStart > start:
				stack.append(start)
				stack.append(nextStart)
			elif end > start > nextStart or nextStart > end > start:
				table = text[start:end+2]
				table = re.sub(r'(?m)^\s*\{\| *(.*)',               r'<table \1><tr >', table)
				table = table.replace('\n|}',                      '\n</tr></table>')
				table = re.sub(r'(?m)^\s*\|-+ *(.*)',                r'</tr><tr \1>', table)
				table = re.sub(r'(?m)^\s*\|\+ *([^][\n|]*\||)(.*)', r'</tr><caption \1>\2</caption><tr>', table)
				#while re.findall(r'(?m)^([!|])(.*?)(\|\||!!)', table):
				for r in re.finditer(r'(?m)^([!|])(.*?)(\|\||!!)', table):
						table = table.replace(r.group(), r.group(1)+r.group(2)+'\n'+r.group(1))
				table = re.sub(r'(?m)^\! *([^][<>\n|]*(?=\|)|)\|* *(.*)',  r'<th \1>\2</th>', table)
				table = re.sub(r'(?m)^\| *([^][<>\n|]*(?=\|)|)\|* *(.*)',  r'<td \1>\2</td>', table)
				text = text[:start] + table + text[end+2:]
				if stack == [] or nextStart > end:
					stack.append(text.find('{|', start+2))
			elif end < 2:
				print '<!-- page rendering or wikitext is broken -->'
				break
			else:
				print '<!-- Indexes:'
				print 'start:%s  nextStart:%s  end:%s' %(start, nextStart, end)
				print text[start-8:start+8].replace('\n','\\n')
				print text[nextStart-8:nextStart+8].replace('\n','\\n')
				print text[end-8:end+8].replace('\n','\\n')
				print 'Stack dump:'
				for i in stack:
					print "%d\t%s" % (i, text[i-2:i+2].replace('\n','\\n'))
				print ' -->'
				raise '%r'%stack
		if len(stack) >= 20:
			print '<!-- Stack overflow -->'
		# remove whitespace
		text = text.replace(' >', '>')
		# Optimize <tr>s
		text = text.replace('<tr></tr>', '')
		text = text.replace('<tr>\n</tr>', '')

	# Headers
	if '\n=' in text:
		for m in re.finditer(r'(?m)^(?P<level>=+)(?P<head>.+?)(?P=level)?\s*$', text):
			lvl = len(m.group('level'))
			t = m.group('head').strip()
			anchor=escapeId(t)
			# char ref for ¶ since string maybe byte or unicode
			text = text.replace(m.group(), '<h%d id="%s">%s<a class="headerlink" href="#%s" title="Permalink to this headline">&#182;</a></h%d>\n\n' % (lvl, anchor, t, anchor, lvl), 1)

	# Lists and paragraphing 
	if '\n' in text:
		# space infront to <pre> (simple ver.)
		text = re.sub(r'\n ([^\n]*)', r'\n<pre>\n\1\n</pre>', text)
		text = text.replace('\n</pre>\n<pre>', '')

			## bullet and numbered lists
			#text = re.sub(r"(?m)^\* *(.*)", r'<ul>\n<li>\n\1</li>\n</ul>', text)
			#text = text.replace('</ul>\n<ul>\n', '')
			#text = text.replace('</li>\n<li>\n<ul>', '\n<ul>')
			#text = text.replace('</li></li>\n</ul>', '</li>\n</ul></li>')
			#
			## Numbered lists
			#text = re.sub(r"(?m)^\# *(.*)", r'<ol>\n<li>\n\1</li>\n</ol>', text)
			#text = text.replace('</ol>\n<ol>\n', '')
			#text = text.replace('</li>\n<li>\n<ol>', '\n<ol>')
			#text = text.replace('</li></li>\n</ol>', '</li>\n</ol></li>')
		
		while '\n#' in text or '\n*' in text or '\n:' in text or '\n;' in text:
			def makeListItem(m):
				if m.group(2) == ':':
					return "%s<dl><dd>%s</dd></dl>"%m.groups()[::2]
				elif m.group(2) == ';':
					return "%s<dl><dt>%s</dt></dl>"%m.groups()[::2]
				elif m.group(2) == '#':
					return "%s<ol><li>%s</li></ol>"%m.groups()[::2]
				else:
					return "%s<ul><li>%s</li></ul>"%m.groups()[::2]
			text = re.sub(r"(?m)^([#*:;]*)([*#:;]) *(.*)", makeListItem, text)
			text = re.sub(r'</(li|dd|dt)></(ol|ul|dl)>\n([#*:;]+)<\2><\1>', r'\n\3', text)
			text = text.replace('</ul>\n<ul>', '\n')
			text = text.replace('</ol>\n<ol>', '\n')
			text = text.replace('</dl>\n<dl>', '\n')

		## definition lists
		#text = re.sub(r'(?m)^;([^\n\r:]*) *',	r'<dl>\n<dt>\n\1</dt>\n</dl>\n', text)
		#text = re.sub(r'(?m)^:(.*)',			r'<dl>\n<dd>\n\1</dd>\n</dl>\n', text)
		#text = text.replace('</dl>\n<dl>\n', '')
		## regex as a regex that can handle both dl/ul/ol
		#text = text.replace('<dd>\n<dl>', '\n<dl>')
		#text = text.replace('</dd></dd>\n</dl>', '</dd>\n</dl></dd>')

		##text = text.replace('<li>\n', '<li>')
		#text = text.replace('<dl>\n', '<dl>')
	
		# Horizonal line
		text = re.sub(r"(?m)^----+ *", '<hr />\n', text)
			
		# New paragraphs
		text = re.sub(r"(?<=\n\n)(([^<>\n][^\n]*\n)+)", r'<p>\1</p>', text)
		text = text.replace('\n</p>', '</p>')
		
	# Bold and Illatics
	if '\'' in text:
		text = re.sub(r"(?m)'''(.*?'*)'''", r'<b>\1</b>', text)
		text = re.sub(r"(?m)''(.*?'*)''",   r'<i>\1</i>', text)	
	
	# Encode & -> &amp;
	if '&' in text:
		text = text.replace('&', '&amp;')
		#for m in re.finditer(r'&amp;(\w{2,8});', text):
		#	text = text.replace(m.group(), '&#%d;'%name2codepoint[m.group(1)])
		for (name, codepoint) in name2codepoint.iteritems():
			text = text.replace('&amp;%s;'%name, '&#%d;'%codepoint)
		text = re.sub(r'\&amp;#(\d+|[xX][0-9A-Fa-f]+);', r'&#\1;', text)
	
	# Internal links
	if '[[' in text:
		# Convert ISO dates
		#for l in re.finditer(r'\[\[(\d{4})-(0[1-9]|1[012])-([0-3]\d)\]\]', text):
		#	text = text.replace(l.group(), "[[%(month)s %(day)s]], [[%(year)s]]" % {'year':l.group(1), 'month':monthname[l.group(2)], 'day':l.group(3), })
		#	#text = text.replace(l.group(), "%(day)s %(month)s %(year)s" % {'year':l.group(1), 'month':monthname[l.group(2)], 'day':l.group(3), })
		for l in re.finditer(r'\[\[([^][{|}]+)(?:\|([^][]*)|)\]\](\w*)', text):
			link = l.group(1)
			if link.startswith(':'):
				link = link[1:]
			for illegalChar in '<>[]|{}\n':
				if illegalChar in link:
					break
			else:
				text = text.replace(l.group(), '<a href="%s%s" title="%s" class="extiw">%s</a>' % (docroot, quote(link.replace(' ', '_').strip('_:')), quote(link), (l.group(2) or link)+l.group(3)))
	
	# External links
	if '//' in text:
		def createLink(m):
			if m.group(3):
				return m.expand(r'<a href="\3" class="external free">\3</a>')
			elif m.group(2):
				return m.expand(r'<a href="\1" class="external text">\2</a>')
			else:
				global autonumber
				autonumber += 1
				return m.expand(r'<a href="\1" class="external autonumber">[%s]</a>'%autonumber)
		text = re.sub(r'\[([a-z:]*//[^][<>"\s]+) *((?<= ).*?]*)?\]|(?<!")(\b\w+://[^][<>"\s]+)(?=[^<\n>]*<)', createLink, text)

	# Images
	'''
	for wimg in re.finditer(r'(?s)\[\[Image:([^\[|\]]+)(\|.*?|)\]\]', text):
		file = 'Image:%s' % wimg.group(1).replace('_', ' ').strip()
		attribs = wimg.group(2).split('|')
		size = ''
		float = None
		thumb = False
		caption = ''
		captionText = ''
		for s in wimg.group(2).split('|'):
			sl = s.lower().strip()
			if sl.endswith('px'):
				try:
					size = (int(s[:-2])*64/250)
				except:
					pass
			elif sl=='left' or sl=='right':
				float = s
			elif sl=='thumb' or sl=='thumbnail':
				thumb = True
				size  = size or 64
				float = float or 'right'
			else:
				caption = s
				captionText = wikipedia.escape(re.sub(r'</?\w+[^<>]*>', '', s))
		if thumb:
			text = text.replace(wimg.group(), """
<div class="thumb" style="float:%s;clear:both;">
<div class="thumbinner" style="width:%spx"><a href="%s" class="image" title="%s"><img alt="%s" src="//upload.wikimedia.org/wikipedia/commons/8/82/Crystal_128_looknfeel.png" class="thumbimage" border="0" width="%s" /></a>
<div class="thumbcaption" style="width:auto;clear:both;">
%s</div>
</div>
</div>""" % (float, size+2, basehref + file.replace(' ', '_'), file, captionText, size, caption ))
		else:
			text = text.replace(wimg.group(), '<a href="%sImage:%s"><img src="%sSpecial:Filepath/%s" width="%s" style="float:%s;" alt="%s" /></a>' % (basehref, file, docroot, file, size, float, captionText))

		### '''
	
	#Hack
	text = showText(text)

	return text

def cleanAttribs(s):
	return s

def quote(s):
	return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def escapeId(s):
	return escapeUrl(s).replace('%', '.')

def escapeUrl(s):
	if not safe_map:
		# generate when first used
		safe = '-.0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz'
		for i in range(256):
			c = chr(i)
			safe_map[c] = (c in safe) and c or ('.%02X' % i)

	try:
		res = map(safe_map.__getitem__, s.replace(' ', '_'))
	except:
		res = []
	return ''.join(res)

def nowiki(s):
	nowiki_map = {}
	for i in range(256):
		c = chr(i)
		nowiki_map[c] = (c not in '{}[]<>\':;*#') and c or ('&#%d;'%i)
	try:
		res = map(nowiki_map.__getitem__, s)
	except:
		res = []
	return ''.join(res)
## 
hideTokens = {}
hideRegex = re.compile('|'.join([
	r'<!--.*?-->',
	r'<script.*?</script>',
	r'<style.*?</style>',
	r'<textarea.*?</textarea>',
	r'<html>.*?</html>',
]), re.I | re.S)

def hideText(text):
	global hideTokens
	n=111
	for m in hideRegex.finditer(text):
		n+=1
		hideTokens[n] = m.group()
		text = text.replace(m.group(), '⌊⌊⌊⌊%06d⌋⌋⌋⌋'%n)
	return text
	
def showText(text):
	global hideTokens
	for (key, value) in hideTokens.items():
		text = text.replace('⌊⌊⌊⌊%06d⌋⌋⌋⌋'%key, value)
	if re.search(r'⌊⌊⌊⌊\d{6,}⌋⌋⌋⌋', text):
		print("WARNING: Unable to replace all hidden tokens")
		raise  "Please report this problem at [[User talk:Dispenser]]"
	hideTokens = {} # Empty
	return text
