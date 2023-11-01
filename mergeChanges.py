#!/usr/bin/env python
# -*- coding: utf-8  -*-

import cgi, re, time
import wikipedia
import cgitb; cgitb.enable(logdir='tracebacks')

#Dead_templates = r'[Dd]ead[ _]*link|[Dd]l|[Dd]l-s|404|[Bb]roken[ _]+link|[Cc]leanup-link'
Dead_templates = {
	'en': ur'[Dd]ead[- _]*(?:[Ll]inks?|cite|url|page|link|)|[Ll]ink[ _]*broken|[Dd][Ll]|[Dd]l-s|404|[Bb]roken[ _]*link|[Bb]ad[ _]*link',
	"af": ur"[Dd]ooie[ _]+skakel|[Dd]ead[ _]+link",
	"als": ur"[Tt]oter[ _]+Link|[Dd]ead[ _]+link",
	"ar": ur"وصلة[ _]+مكسورة|مرجع[ _]+مكسور|[Bb]roken[ _]+ref|مصدر[ _]+مكسور|[Dd]ead[ _]+link|[Dd]eadlink|[Ll]ien[ _]+brisé|[Dd]l",
	"ast": ur"[Ee]nllaz[ _]+rotu|[Dd]ead[ _]+link",
	"av": ur"[Хх]вараб[ _]+ссылка|[Dd]eadlink|[Хх]вараб[ _]+линк",
	"be": ur"[Нн]едаступная[ _]+спасылка|[Dd]ead[ _]+link|[Dd]eadlink",
	"bn": ur"অকার্যকর[ _]+সংযোগ|[Dd]l|[Dd]ead[ _]+link|[Bb]roken[ _]+link|[Dd]ead|404",
	"bs": ur"[Mm]rtav[ _]+link|[Dd]ead[ _]+link",
	"ca": ur"[Ee]nllaç[ _]+no[ _]+actiu|[Dd]ead[ _]+link|[Ee]nllaç[ _]+trencat|[Ee]nlllaç[ _]+trencat",
	"ce": ur"[Тт]Ӏе[ _]+цакхочу[ _]+хьажорг|[Dd]eadlink",
	"ckb": ur"بەستەری[ _]+مردوو|[Dd]ead[ _]+link",
	"cs": ur"[Nn]edostupný[ _]+zdroj|[Dd]ead[ _]+link",
	"cy": ur"[Dd]olen[ _]+marw|[Dd]ead[ _]+link|[Dd]eadlink",
	"da": ur"[Dd]ødt[ _]+link|[Dd]ead[ _]+link|[Dd]eadlink",
	"de": ur"[Tt]oter[ _]+Link|[Dd]ead[ _]+link",
	"el": ur"[Dd]ead[ _]+link|[Νν]εκρός[ _]+σύνδεσμος",
	"eo": ur"404|[Mm]alvalida[ _]+ligilo|[Dd]ead[ _]+link",
	"es": ur"[Ee]nlace[ _]+roto|[Rr]oto|[Dd]ead[ _]+link|[Ee]nlace[ _]+no[ _]+disponible|[Dd]eadlink|[Ee]nlaceroto",
	"et": ur"[Ss]urnud[ _]+link",
	"eu": ur"[Aa]purtutako[ _]+esteka",
	"fa": ur"پیوند[ _]+مرده|[Dd]ead[ _]+link|لینک[ _]+مرده|[Dd]eadlink|[Dd]l",
	"fi": ur"[Vv]anhentunut[ _]+linkki|[Kk]uollut[ _]+linkki|[Dd]ead[ _]+link|[Dd]eadlink|404",
	"fo": ur"[Dd]eyð[ _]+leinkja|[Dd]ead[ _]+link|404|[Dd]l|[Dd]ead|[Dd]eadlink|[Bb]roken[ _]+link",
	"fr": ur"[Ll]ien[ _]+brisé|[Ll]ien[ _]+mort|[Ll]ien[ _]+brise|[Ll]ien[ _]+cassé|[Ll]ien[ _]+rompu|[Ll]ien[ _]+web[ _]+brisé|[Ll]ien[ _]+Web[ _]+brisé|[Dd]eadlink",
	"gl": ur"[Ll]igazón[ _]+morta|[Dd]ead[ _]+link|[Dd]eadlink",
	"he": ur"קישור[ _]+שבור|[Dd]ead[ _]+link",
	"hr": ur"[Nn]eaktivna[ _]+poveznica|[Dd]ead[ _]+link|[Nn]p|[Nn]epostojeća[ _]+poveznica",
	"hu": ur"[Hh]alott[ _]+link|[Dd]ead[ _]+link|[Tt]örött[ _]+link",
	"hy": ur"[Չչ]աշխատող[ _]+արտաքին[ _]+հղում|[Dd]ead[ _]+link|[Нн]едоступная[ _]+ссылка",
	"id": ur"[Pp]ranala[ _]+mati|[Dd]eadlink|[Dd]ead\-link|[Dd]ead[ _]+link|[Ll]ink[ _]+rot|[Ll]inkrot",
	"ilo": ur"[Nn]atay[ _]+a[ _]+silpo|[Dd]ead[ _]+link|[Nn]atay[ _]+a[ _]+panilpo|[Dd]eadlink",
	"it": ur"[Cc]ollegamento[ _]+interrotto|[Dd]ead[ _]+link|404|[Dd]eadlink|[Cc]i",
	"ja": ur"リンク切れ|[Dd]ead[ _]+link|[Dd]L|[Dd]eadlink|404|[Dd]l|[Bb]roken[ _]+link",
	"ka": ur"მკვდარი[ _]+ბმული",
	"ko": ur"깨진[ _]+링크|[Dd]ead[ _]+link|죽은[ _]+링크|죽은[ _]+바깥[ _]+고리|깨진[ _]+고리|[Bb]roken[ _]+link|깨진[ _]+바깥[ _]+고리|죽은[ _]+고리",
	"lt": ur"[Nn]eveikianti[ _]+nuoroda|[Dd]ead[ _]+link",
	"lv": ur"[Nn]ovecojusi[ _]+saite|[Nn]ovecojusi[ _]+atsauce|[Dd]ead[ _]+link|[Dd]eadlink|[Dd]l",
	"mk": ur"[Мм]ртва[ _]+врска|[Dd]ead[ _]+link|[Мм]ртваврска",
	"ms": ur"[Dd]ead[ _]+link|[Pp]autan[ _]+luput",
	"nl": ur"[Dd]ode[ _]+link",
	"nn": ur"[Dd]ød[ _]+lenkje|[Dd]ød[ _]+lenke|[Dd]aud[ _]+lenkje|[Dd]ead[ _]+link",
	"no": ur"[Dd]ød[ _]+lenke|[Dd]l|[Dd]ead[ _]+link|404|[Dd]ød|[Dd]ød[ _]+link",
	"pl": ur"[Mm]artwy[ _]+link",
	"pt": ur"[Ll]igação[ _]+inativa|[Dd]ead[ _]+link|[Ll]ink[ _]+quebrado|[Dd]eadlink",
	"ro": ur"[Ll]egătură[ _]+nefuncțională|[Ll]egătură[ _]+nefuncţională|[Dd]ead[ _]+link|[Ll]nf|[Dd]eadlink",
	"ru": ur"[Нн]едоступная[ _]+ссылка|[Мм]ёртвая[ _]+ссылка|[Мм]ертвая[ _]+ссылка|[Dd]eadlink|[Dd]ead[ _]+link|[Dd]ead|[Бб]итая[ _]+ссылка|[Нн]ерабочая[ _]+ссылка|[Нн]едоступный[ _]+источник|[Bb]roken[ _]+link",
	"sco": ur"[Dd]ead[ _]+link|[Dd]aid[ _]+airtin|[Dd]l|[Dd]eadlink|[Dd]ead[ _]+Link",
	"sl": ur"[Ss]lepa[ _]+povezava|[Dd]ead[ _]+link|[Dd]eadlink|[Bb]roken[ _]+link",
	"sr": ur"[Мм]ртва[ _]+веза|[Мм]ртав[ _]+линк|[Mm]rtav|[Dd]ead|[Dd]ead[ _]+link|[Dd]eadlink",
	"sv": ur"[Dd]öd[ _]+länk|[Dd]ead[ _]+link|404|[Dd]ödlänk|[Dd]eadlink|[Tt]oter[ _]+Link",
	"te": ur"[Dd]ead[ _]+link|అచేతన[ _]+లింకు|[Dd]eadlink|[Bb]roken[ _]+link|[Bb]ad[ _]+link",
	"th": ur"ลิงก์เสีย|[Dd]ead[ _]+link",
	"tr": ur"[Öö]lü[ _]+bağlantı|[Dd]ead[ _]+link|[Kk]ırık[ _]+link|[Öö]B",
	"uk": ur"[Нн]едоступне[ _]+посилання|[Dd]ead[ _]+link|[Мм]ертве[ _]+посилання|[Нн]едієве[ _]+посилання|[Нн]ечинне[ _]+посилання|[Dd]eadlink|[Нн]едійсне[ _]+посилання|[Нн]едоступная[ _]+ссылка|[Tt]oter[ _]+Link|[Мм]ёртвая[ _]+ссылка",
	"ur": ur"مردہ[ _]+ربط|[Dd]ead[ _]+link|مرده[ _]+ربط",
	"vi": ur"[Ll]iên[ _]+kết[ _]+hỏng|[Dd]ead[ _]+link|[Ll]ink[ _]+chết|[Ll]iên[ _]+kết[ _]+chết|[Bb]roken[ _]+link|[Cc]itation[ _]+broken|[Dd]eadlink",
	"wuu": ur"[Dd]ead[ _]+link|死鏈",
	"zh": ur"[Dd]ead[ _]+link|[Dd]eadlink|失效链接|失效連結|失效|404|死链",
}
Citations_broken_P = {
 'en': ur'(?P<nl>\n)?\{\{\s*(?:[Tt]emplate:|)(?:[Dd]ead[ _]+link[ _]+header|[Dd]ead[ _]+links|[Dd]eadlinks)(?:\|[^{}]*|)\s*\}\}(?(nl)\n?)',
}
removeDeadTemplate = re.compile(ur'((\[XxNEEDLExX[^]]*?\]|\{\{[^{}]*XxNEEDLExX[^{}]*\}\})(\s*</ref>|))(\s*?\{\{[Dd]ead link[^}]*\}\})+', re.DOTALL)
MySite = wikipedia.getSite()

def html(string, data=[]):
	s = string%tuple(wikipedia.escape(s) if isinstance(s, (bytes,str,unicode)) else s for s in data)
	print (s.encode('utf-8') if isinstance(s, unicode) else s)

def getfirst(dict, name, defaultValue=None):
	return dict.get(name, [defaultValue])[0]
	
def removeDeadNote(text):
	# replaces the {{dead link}} template suceding the XxNEEDLExX value
	return removeDeadTemplate.sub(r'\g<1>', text)

def removeDuplicate(text):
	"""
	Remove the newest duplicate {{dead link}} tag
	"""
	m = re.compile('(\{\{(%s)[^}]*?\}\})+(?P<newest>(</ref>)?\{\{(%s)[^}]*?\}\})' % (
		wikipedia.translate(MySite, Dead_templates),
		wikipedia.translate(MySite, Dead_templates),
	))
	text = m.sub(r'\g<newest>', text)
	# Remove {{Citations broken}} if no {{dead link}} tags are found
	if not re.search(wikipedia.translate(MySite, Dead_templates), text):
		text = re.sub(wikipedia.translate(MySite, Citations_broken_P), '', text)
	return text

alphanum = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
def webCiteShortId(t):
	"""
	WebCite's short identifier is the time measure in microsecond since 1970
	of the date of the archive request stored as a base-62 number.
	"""
	base62 = ""
	while t > 0:
		base62 = alphanum[t%62] + base62
		t //= 62
	return base62

def webCiteTime(wc_id):
	t = 0
	for s in wc_id:
		t *= 62
		t += alphanum.index(s)
	return t

def main():
	# setup defaults
	submitbutton = 'wpDiff'

	print '''<head>
<title>mergeChanges.py</title>
<style type="text/css">
 textarea, input[type="text"]{width:80%; margin:auto;}
 .error {color: red;font-size: larger;}
 .warn {color: yellow; background:black;}
 #load-msg {display:none;}
</style>
<!-- load secure rewrite script -->
<script src="../resources/ajax.js" type="text/javascript"></script>
</head>'''
	# TODO replace query w/ form after testing
	#form = cgi.FieldStorage(keep_blank_values=True)
	query = cgi.parse(keep_blank_values=True)
	if query == {}:
		print "<body>No form fields given</body>"
		return
	page = wikipedia.Page( wikipedia.getSite(), getfirst(query, 'title', '') )
	global MySite; MySite = page.site()
	#page = wikipedia.Page( wikipedia.getSite(), form.getfirst('title', '') )
	print '<body>'
	html(u'<h1>%s [%s]</h1>', (page.title(), MySite.lang))
	
	# Some clients have trouble with the javascript submittion
	if page.title() == '':
		print '''
<h1>No page title has been given</h1>
<p>This may be cause by a bug in your browser or a misconfigured proxy or firewall.  Please <a href="//en.wikipedia.org/w/index.php?title=User_talk:Dispenser&action=edit&section=new">report this problem</a> if it continues.</p>
<h2>Your request data:</h2>'''
		html(u"<pre>%r</pre>", (query,))
		cgi.print_environ()
		return
	
	html(u'<p>Preparing diff, this page will auto submit with JavaScript.</p>')
	html(u'<img src="../resources/loadbar.gif" alt="loading..." width="200" height="19" />')
	html(u'<p></p>')
	
	# Should we run reflinks on this?
	reflinks = 'reflinks' in query.get('addons',[])
	#reflinks = 'reflinks' in form.getlist('addons')
	wpSummary = ''

	text = page.get()
	if 'commonfixes' in query.get('addons',[]):
	#if 'commonfixes' in form.getlist('addons'):
		import commonfixes
		text = commonfixes.fix(page=page, text=text)

	# Use "Dead link" for all the dead link templates, 
	# Capitlized since Smackbot/AWB "corrects" it
	text = re.sub(r'\{\{\s*(?:[Tt]emplate|)(%s)(?=\s*[|}])' % wikipedia.translate('en', Dead_templates), r'{{Dead link', text) 

	# Since we get the browser's normalized URL we need to proform the same normalization to properly match the two
	#TODO un-normalize?
	text = re.sub(r'(\[http[s]?://[A-Za-z0-9\-.:]+\w+)([ \]])', r'\g<1>/\g<2>', text) # adds / to the end of domains
	
	print '<xmp>%r</xmp>'%query
	#print '<xmp>%r</xmp>'%form
	for action, lst in query.iteritems():
	#for (action, lst) in form.iteritems():# FIXME
		try:
			needle = unicode(lst[0], 'utf-8')
		except UnicodeDecodeError:
			needle = unicode(lst[0], 'latin1')
		text =  text.replace(needle, 'XxNEEDLExX')

		repl = ''# None
		if len(lst)>1:
			if not 'XxNEEDLExX' in text and action not in ('addons',): #HACK
				html(u'<div class="error">Cannot find string: %s</div>', (needle,))
			try:  repl = unicode(lst[1], 'utf-8')
			except UnicodeDecodeError:	repl = unicode(lst[1], 'latin1')
			repl = wikipedia.html2unicode(repl)
			# \ is escaped as to avoid \1 in strings, \\ will be intrupited as \
			# Cannot use re.escape() since the escapement is not undone by re.sub()
			repl = repl.replace('\\', '\\\\')

		
		if   action == "wpSummary":
			try:	wpSummary = unicode(lst[0], 'utf-8')
			except:	wpSummary = unicode(lst[0], 'latin-1')
		elif action == "wpSection":
			pass
		# Which submit button should the javascript click
		elif action in ('wpSave', 'wpPreview','wpDiff'):
			submitbutton = action
		elif action in ("title", "ServerPath", "addons"):
			# actions are performed elsewhere
			pass

		# Regex
		elif action.startswith('regex'):
			p = re.compile(needle)
			if p.search(text):
				text = p.sub(repl, text)
			else:
				html(u'<div class="error">Append error: Not in template or bracketed link: %s</div>', (needle,))

		# {{dead link}}
		elif action.startswith('append'):
			#p = re.compile(r'(\[XxNEEDLExX.*?\]|\{\{[^{}]*=\s*XxNEEDLExX[^{}]*\}\}) *?(</ref>|)')
			p = re.compile(r'(\[XxNEEDLExX[^]\n]*?\]|\{\{[^{}]*=\s*XxNEEDLExX[^{}]*\}\})()')
			text = re.sub(r'(?<=[>])\s*XxNEEDLExX\s*(?=</\s*[Rr][Ee][Ff]\s*>)', r'[XxNEEDLExX]', text)
			text = re.sub(r'(\n[*#:;]+ *|[<>"\]] *)XxNEEDLExX(?=[][<>\s"])', r'\1[XxNEEDLExX]', text)
			if p.search(text):
				# Append repl
				text = p.sub(r'\g<1>\g<2>%s' % repl, text)
				# remove double {{dead link}}
				text = removeDuplicate(text)
			elif needle == '__START__':
				text = repl + text
			elif needle == '__END__':
				text = text.rstrip() + repl
			else:
				html(u'<div class="error">Append error: Not in template or bracketed link: %s</div>', (needle,))
		
		# {{fact}}
		elif action.startswith('replacereference'):
			p = re.compile(r'\[XxNEEDLExX( [^]\n]*|)\]|\{\{[^{}]*=\s*XxNEEDLExX[^{}]*\}\}|(?<=[>])\s*XxNEEDLExX\s*(?=</ref>)')
			if p.search(text):
				text = removeDeadNote(text)
				text = p.sub(repl or "", text)
			else:
				html(u'<div class="error">Replace link error: Not in template or bracketed link: %s</div>', (needle,))
				
		elif action.startswith("unlink"):
			text = re.sub(r'(?<=[>])\s*XxNEEDLExX\s*(?=</\s*[Rr][Ee][Ff]\s*>)', r'[XxNEEDLExX]', text)
			wikipedia.output( re.search(r'.{0,20}XxNEEDLExX.{0,20}', text).group())
			if "[XxNEEDLExX" in text:
				text = removeDeadNote(text)
				text = re.sub(r'\[XxNEEDLExX([^]\n]*)\]', r'\1', text)
			elif re.search(r'url\s*=\s*XxNEEDLExX', text):
				text = removeDeadNote(text)
				text = re.sub(r'\|\s*url\s*=\s*XxNEEDLExX\b\s*', r'', text)
				#TODO: added archiveurl remover (maynot be used much...)
				for m in re.finditer(r'\{\{\s*([Cc]ite[ \-_]*[Ww]eb|[Ww]eb[ _]*refernce|[Ww]eb cite|[Cc]ite|[Cc]itation)([^{}]*)\}\}', text):
					if not re.search('\|\s*url\s*=\s*(?![|}])', m.group()):
						# typically cite news will substitue
						text = text.replace(m.group(), m.expand(r'{{cite news\2}}'))
			else:
				#print '<xmp>%s</xmp>'% text.encode('utf-8')
				html(u'<div class="error">Unlink error: Not in template or bracketed link: %s</div>', (needle,))
				wikipedia.output( re.search(r'.{0,20}XxNEEDLExX.{0,20}', text).group())

		# Archive/Replace URL
		elif action.startswith('substitute') or action.startswith('replace') or action.startswith('archive') or action.startswith('replacelink'):
			# Archiveurl, just complicated
			archivedate = None
			# WebCite
			m = re.search(r'webcitation.org/([0-9A-Za-z]{9})', repl)
			if m:
				archivedate = time.strftime("%Y-%m-%d", time.gmtime(webCiteTime(m.group(1))/1000000))
			# Wayback Machine
			m = re.search(r'^https?://web\.archive\.org/web/(199[6-9]|20\d\d)(0[1-9]|1[0-2])([0-3]\d)[012]\d[0-5]\d\d\d/.*$', repl)
			if m:
				archivedate = m.expand(r'\1-\2-\3')

			if not archivedate and action.startswith('archive'):
				wikipedia.output('\03{darkred}Warning\03{default} : Bad archivedate, replacing with current date.')
				archivedate = time.strftime("%Y-%m-%d") # Current date

#			#FIXME replace multiple!
#			if archivedate and re.search(r'\[XxNEEDLExX(?=[<>"[\]\s])', text):
#					text = removeDeadNote(text)
#					text = re.sub(r'')
			R = re.compile(r'(?i)\{\{\s*(?!dead link)(?:[^{}]+)\|\s*url\s*=\s*XxNEEDLExX\s*(\}\}|\|)', re.I)
			if archivedate and R.search(text):
				if re.search(r'url\s*=\s*XxNEEDLExX[^}]*archive-?url\s*=\s*[^\s|}]|archive-?url\s*=\s*[^\s|}][^}]*url\s*=\s*XxNEEDLExX', text):
					wikipedia.output('\03{darkred}ERROR\03{default} archiveurl= already used, skipping (%s)' % repl)
				else:
					text = removeDeadNote(text)
					# If inside a template, use the archiveurl= feature
					# There is some weird bug in the regular expression engine, it seems to try and match double digit back references
					#wikipedia.output(str(re.search(ur'(?us)((\s*\|\s*)url(\s*=\s*)XxNEEDLExX)', text).groups()))
					#wikipedia.output(ur'\1\2archiveurl\3%s\2archivedate\3%s' % (repl, archivedate))
					text= re.sub(ur'(?us)((\s*\|\s*)url(\s*=\s*)XxNEEDLExX)(?=\s*[|}])', 
								 ur'\g<1>\g<2>archiveurl\g<3>%s\g<2>archivedate\g<3>%s' % (repl, archivedate),
								 text, 1)
			elif action.startswith('archive'):
				if "[XxNEEDLExX" in text:
					text = removeDeadNote(text)
					text = re.sub(ur'(?u)\[(XxNEEDLExX) *((?<= )[^\]\n]+?|)\]',
								  ur'{{cite web |url=\1 |title=\2 |archiveurl=%s |archivedate=%s}}' % (repl, archivedate), 
								  text)
					## needs code for other archiving resources
					#text = re.sub(r'\[(XxNEEDLExX)( +([^]]+))?\]', r'{{waybackdate|site=\1|title=\3|date=%s}}' % archivedate, text)
				else:
					if "XxNEEDLExX" in text:
						print  '''
						<div>
						<div class="error">Error: Could not substitute url.</div>
						This may happen because the URL is "free" (without a titlte) or something else.
						<pre>%s</pre>
						</div>'''%re.search(r'\b.{0,20}XxNEEDLExX.{0,20}\b', text).group().encode('utf-8')
					else:
						html(u'<div class="error">Error: Could not find url.</div>')
				
			else:
				# Substitute the current link with a new link
				text = removeDeadNote(text)

				# Python doesn't support (?<!\w://[^][<>\s"]*)
				# Bug we assume human review of the replace (hopefully, wont be human bots)
				text = re.sub(r'(?<![/])\bXxNEEDLExX([.,\:;!\[\]<>"\s\|\}])', r'%s\g<1>'%repl, text)

		# Update accessdate entries
		elif action.startswith("updateaccessdate"):
			#FIXME not quite correct - what is?
			for m in re.finditer(r'\{\{[^}]+XxNEEDLExX.*?\}\}', text, re.DOTALL):
				reftext = m.group()
				reftext = re.sub(r'(\|\s*accessdate\s*= ??)(?=\n* *[{|}])', time.strftime(r'\g<1>%Y-%m-%d'), reftext)
				if not re.search('\|\s*accessdate=\s*=\s*', reftext):
					reftext = re.sub(r'(\{\{[^{}]+?)((\s*\|\s*)[^[=\]{|}]+?(\s*= *)[^{|}]+?)(\s*)\}\}', time.strftime(r'\1\2\3accessdate\g<4>%Y-%m-%d\5}}'), reftext)
				text = text.replace(m.group(), reftext)
		# Print alerts if something was not used
		else:
			html(u'<pre class="error">Unused: %s\t= <input name="%s" size="40" value="%s" /></pre>', (action, action, wikipedia.unicode2html(needle),))
		text = text.replace('XxNEEDLExX', needle)

		# HACK
		text = text.replace('<ref> </ref>', '')
		
		## HACK
		text = re.sub(
			ur'''(\{\{(?:[Tt]emplate\:)?(?:
				[Cc]ite[ _]+web|[Cc]ite[ _]+Web|[Cc]it[ _]+web|[Cc]ite[ _]+url|[Cc]ite[ _]+w|[Cc]ita[ _]+web|[Cc]ite[ _]+blog|[Cc]ite[ _]+website|Web\-reference|[Cc][ _]+web|[Cc]ite[ _]+web|[Cc]ite\-web|Weblink|[Cc]ite[ _]+web\.|[Cc]ite[ _]+webpage|Web[ _]+citation|[Cc]ite[ _]+web\/lua|Web[ _]+reference|[Cc]w|[Cc]iteweb|Web|Web[ _]+cite|Wikipedia\:[Cc]ite[ _]+web|Lien[ _]+web|[Cc]ite[ _]+website[ _]+article|[Cc]iteweb|[Cc]itar[ _]+web
				|
				[Cc]ite[ _]+news|[Cc]ite\-news|[Cc]itenews|[Cc]ite[ _]+article\/lua|Wikipedia\:[Cc]ite[ _]+news|[Cc]ite[ _]+news\/lua|[Cc]itenewsauthor|[Cc]it[ _]+news|[Cc]ite[ _]+new|[Cc]ite[ _]+article|[Cc]ite[ _]+newspaper|[Cc]ite[ _]+news2|[Cc]ite[ _]+news\-q|[Cc]ite[ _]+News|[Cc]itenews|[Cc]ute[ _]+news|[Cc]ite[ _]+news|[Cc][ _]+news
			)[^{}]*?)
			(\s*\|\s*)url(\s*=\s*)
				(?P<archiveurl>https?://(?:wayback.archive.org|web.archive.org)/web/(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})\d{6}/(?P<url>https?://[^][{}|<>"\s]+))
			(?=\s*[{|}])''', 
			ur'\1\2url\3\g<url>\2archiveurl\3\g<archiveurl>\2archivedate\3\g<y>-\g<m>-\g<d>',
			text,
			flags=re.X
		)
	# Remove ajacent {{dead link}}
	text = removeDuplicate(text)

	if reflinks:
		try:
			import reflinks
			def my_reflinks_put_page(self, page, new):
				self.page = page
				self.new_text = new
			reflinks.ReferencesRobot.put_page=my_reflinks_put_page
		except ImportError:
			wikipedia.output('Unable to import reflinks')
			reflinks = None
		
		# Hackist hook
		page._contents = text
		if page.get() != text:
			wikipedia.output("Injected text wasn't returned with page.get() !")
		elif reflinks.linksInRef.search(text):
			reflinksbot = reflinks.ReferencesRobot(iter([page]))
			reflinksbot.run()
			if hasattr(reflinksbot, 'new_text'):
				if reflinksbot.page != page:raise 'pages not the same'
				text = reflinksbot.new_text
		
		# remove extra {{dead link}} added by reflinks
		text = removeDuplicate(text)

		page.put(text, wpSummary)
	else:
		page.put(text, wpSummary)
	
	# click the submit button
	html(u'<script type="text/javascript">setTimeout(\'document.getElementById("%s").click();\', 1500);</script>', (submitbutton,))
	
	html(u"</form>")
	html(u'</body>')

if __name__ == "__main__" and wikipedia.handleUrlAndHeader(connicalize=False):
	try:
		print '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
		print '<html>'
		main()
#	except:
#		f = open('./tracebacks/mergechanges.py', "a")
#		f.write("<pre>%r</pre>\n<hr/><pre>%r</pre>"%(cgi.os.environ, cgi.parse(keep_blank_values=True)))
#		raise
	finally:
		print '</html>'
