#!/usr/bin/env python
# -*- coding: utf-8  -*-
'''
Reduced function set pywikibot for use as a CGI script

Notes:
  While reading through parts of the pywikibot code I have noticed that it underultaizes itself

== Converting scripts into tools==
Add to top:  #!/usr/bin/env python
Change the loader to the following:
if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
    try:
        wikipedia.startContent()
        main()
    finally:
        wikipedia.endContent()
        wikipedia.stopme()
'''
#from __future__ import unicode_literals
#from __future__ import print_function
import time; StartTime = time.time()
import os, re, sys, urllib
## pywikipedia imports
#import config
# HTML debugging
import cgitb; cgitb.enable(logdir='tracebacks')
## Python on Solaris handle SIGPIPE different than it does under bash linux
#import signal; signal.signal(signal.SIGPIPE,signal.SIG_DFL)

QueryContinue = ""
# SELECT GROUP_CONCAT("'", SUBSTRING_INDEX(domain, ".", 1), "'," ORDER BY domain SEPARATOR "")
# FROM toolserver.wiki
# WHERE domain LIKE "%.wikipedia.org"
# AND is_closed=0 AND is_meta=0 AND size > 100
# GROUP BY CEIL(LOG10(size)) DESC;
supported_languages = (
# 1,000,000+ content pages
'ceb','de','en','es','fr','it','ja','nl','pl','ru','sv','vi','war',

# 100,000+ content pages
'ar','az','be','bg','ca','ce','cs','da','el','eo','et','eu','fa','fi','gl','he','hi','hr','hu','hy','id','ka','kk','ko','la','lt','min','ms','nn','no','pt','ro','sh','simple','sk','sl','sr','ta','th','tr','uk','ur','uz','vo','zh','zh-min-nan',



# 10,000+ content pages
'af','als','am','an','arz','ast','azb','ba','bar','bat-smg','be-tarask','bn','bpy','br','bs','bug','cdo','ckb','cv','cy','fo','fy','ga','gd','gu','hsb','ht','ia','ilo','io','is','jv','kn','ku','ky','lb','li','lmo','lv','mai','map-bms','mg','mk','ml','mn','mr','mrj','my','mzn','nap','nds','ne','new','oc','or','os','pa','pms','pnb','qu','sa','sah','scn','sco','si','sq','su','sw','te','tg','tl','tt','vec','wa','xmf','yi','yo','zh-yue',

# 1,000+ content pages
'ab','ace','ang','arc','as','av','ay','bcl','bh','bi','bjn','bo','bxr','cbk-zam','co','crh','csb','diq','dsb','dv','eml','ext','fiu-vro','frp','frr','fur','gag','gan','glk','gn','gom','gv','ha','hak','haw','hif','ie','ig','jbo','kaa','kab','kbd','kg','ki','kl','km','koi','krc','ksh','kv','kw','lad','lbe','lez','lg','lij','ln','lo','lrc','mdf','mhr','mi','mt','mwl','myv','na','nah','nds-nl','nov','nrm','nso','nv','pag','pam','pap','pcd','pdc','pfl','pi','ps','rm','roa-rup','roa-tara','rue','rw','sc','sd','se','sn','so','srn','stq','szl','tet','tk','to','tpi','ty','tyv','udm','ug','vep','vls','wo','wuu','xal','za','zea','zh-classical',

# 100+ content pages
'ak','bm','ch','chr','chy','cr','cu','dz','ee','ff','fj','got','ik','iu','ks','ltg','ny','om','pih','pnt','rmy','rn','sg','sm','ss','st','ti','tn','ts','tum','tw','ve','xh','zu',

# Hack for weird families (also present in pywikibot)
'm', 'meta', 'c', 'commons', 'mediawiki', 'd', 'wikidata',

# TODO language redirects
)

def datafilepath(*filename):
	path = os.path.normpath(os.path.join('../resources/', *filename))
	dirs = os.path.dirname(path)
	if not os.path.exists(dirs): os.makedirs(dirs)
	return path

families = {
	'w': 'wikipedia',
	'wikt': 'wiktionary',
	'n': 'wikinews',
	'b': 'wikibooks',
	'd': 'wikidata',
	'q': 'wikiquote',
	's': 'wikisource',
	'v': 'wikiversity',
	'voy': 'wikivoyage',
	'wmf': 'wikimediafoundation',
	# See supported_languages above for the working version
	'c': 'commons',
	'm': 'meta',
	'mw': 'mediawiki',
	'commons': 'commons',
	'wikidata': 'wikidata',
	#'wikimedia': 'wikimedia',
}

namespaces = {
	-2:	u'Media',
	-1:	u'Special',
	0:	None,
	1:	u'Talk',
	2:	u'User',
	3:	u'User talk',
	4:	u'Wikipedia',
	5:	u'Wikipedia talk',
	6:	u'File',
	7:	u'File talk',
	8:	u'Mediawiki',  # XXX Capitlization hack
	9:	u'Mediawiki talk',
	10:	u'Template',
	11:	u'Template talk',
	12:	u'Help',
	13:	u'Help talk',
	14:	u'Category',
	15:	u'Category talk',
	# Extensions
	90:	u'Thread',
	91: u'Thread talk',
	92: u'Summary',
	93:	u'Summary talk',
	# Custom NS
	100: u'Portal',
	101: u'Portal talk',
	102: u'Author',
	103: u'Author talk',
	104: u'Index',
	105: u'Index talk',
	106: u'Collection',
	107: u'Collection talk',
	108: u'Book',
	109: u'Book talk',
	110: u'Wikisaurus',
	111: u'Wikisaurus talk',
	112: u'Subject',
	113: u'Subject talk',
	114: u'Citations',
	115: u'Citations talk',
	116: u'Sign gloss',
	117: u'Sign gloss talk',
	118: u'Draft',
	119: u'Draft talk',
	446: u'Education program',
	447: u'Education program talk',
	710: u'Timedtext',
	711: u'Timedtext talk',
	828: u'Module',
	829: u'Module talk',
	2300: u'Gadget',
	2301: u'Gadget talk',
	2302: u'Gadget definition',
	2301: u'Gadget definition talk',
	2600: u'Topic',
}

class Family(object):
	def __init__(self, name):
		if name in families:
			self.name = families[name]
		elif name:
			self.name = name
		else:
			raise LookupError
		self.shortname = name
		# FIXME
		self.namespaces = namespaces
	
	def __repr__(self):
		return '%s.Family(%r)'%(__name__, self.name)
	
	def dbName(self, code):
		# MySQL database name
		return '%s%s' % (code, 'wiki' if self.name=='wikipedia' else self.name)

class Site(object):
	dbname_R = re.compile(r'^(?P<lang>[a-z_]{2,})(?P<family>wiki|wikibooks|wikimedia|wikinews|wikipedia|wikiquote|wikisource|wikiversity|wiktionary)(?:_p|)$')
	def __init__(self, code, fam=None):
		"""
		Accepts:
			lang:family     	Interiwki
			lang.family.org 	Domain name
			langfamily_p    	Database name
			Site()				Site objects (returns itself)
		"""
		if isinstance(code, unicode):
			code = code.encode('ascii', 'replace')
		elif code == None:
			code = 'en'
		else:
			pass
		host = code.lower().split(':' if ':' in code else '.')
		dbname_M = self.dbname_R.match(code)
		if dbname_M:
			lang, project = dbname_M.group('lang','family')
			lang = lang.replace('_', '-')
			if project == 'wiki': project = 'wikipedia'
		elif host[0].replace('-', '').isalpha():
			lang = host[0]
			project = host[1] if len(host) > 1 else None
		else:
			raise ValueError
		if lang in supported_languages:
			self.lang = lang
		else:
			raise KeyError

		# XXX fam will always override
		if fam:
			if isinstance(fam, bytes):
				self.family = Family(fam)
			else:
				self.family = fam
		elif project:
			self.family = Family(project)
		else:
			try:
				self.family = MySite.family
			except NameError:
				# MySite hasn't been defined yet
				self.family = Family('wikipedia')
	
	def __repr__(self):			return "'%s:%s'"%(self.family.name, self.lang)
	
	def getUrl(self, path, data = {}, retry = True, compress = True):
		data_enc = dict((
			k.encode('utf-8') if isinstance(k, unicode) else bytes(k),
			v.encode('utf-8') if isinstance(v, unicode) else bytes(v)
		) for k, v in (data or {}).iteritems())
		if Debug: print('<!-- retrieving https://%s%s?%s -->' % (
			self.hostname(),
			path.encode('utf-8'),
			'&'.join('%s=%s'%(k, v) for k,v in data_enc.iteritems()),
		))
		uo = MyURLopener()
		if os.getenv("X-Forwarded-For"):
			uo.addheader("X-Forwarded-For", os.getenv("X-Forwarded-For"))
		if compress: uo.addheader("Accept-Encoding", "gzip")
		url = 'https://%s%s' % (self.hostname(), path)
		f = uo.open(url, urllib.urlencode(data_enc) or None)
		# if status.code != 200:
		# 	raise ServerError
		# TODO: include magic number check '\x1f\x8b' at bytes 0-1
		if f.info().get('Content-Encoding') in ('gzip', 'x-gzip'):
			import StringIO, gzip
			return gzip.GzipFile(fileobj=StringIO.StringIO(f.read())).read()
		else:
			return f.read()
	
	def protocol(self):			return 'http'
	def hostname(self):
		if self.lang in ('commons', 'meta'):
			return '%s.wikimedia.org' % (self.lang,)
		elif self.lang in ('wikidata', 'wikisource'):
			return "www.%s.org" % (self.family.name,)
		else:
			return '.'.join((self.lang, self.family.name, 'org'))
	def path(self):				return '/w/index.php'
	def apipath(self):			return '/w/api.php'
	def encoding(self):			return 'utf-8'  # used in reflinks
	def language(self):			return self.lang
	def sitename(self):			return ':'.join([self.family.name, self.lang])
	def isInterwikiLink(self, s):
		return any([s.startswith('%s:'%iw) or s.startswith(':%s:'%iw) for iw in supported_languages])
	def namespace(self, num):
		return namespaces[num] or ''
	def category_namespaces(self):
		return (namespaces[14], )
	def page_action_address(self, s, action):
		return '%s?title=%s&action=%s' % (self.path(), s, action)
	def put_address(self, s):
		return '%s?title=%s&action=submit' % (self.path(), s)
	def get_address(self, s):
		return '%s?title=%s&redirect=no' % (self.path(), s)
	def nice_get_address(self, s):
		return '/wiki/%s' % (s)
	def dbName(self):
		"""Return MySQL database name."""
		return self.family.dbName(self.lang.replace('-', '_'))


class Page(object):
	def __init__(self, site, title, insite=None, defaultNamespace=0):
		# FIXME %23 (#) titles can slip through
		self._site = Site(site) if isinstance(site, (bytes, unicode)) else site
		self._namespace = None
		self.revisionid = None
		self.id         = None
		# UTF-8 for precent decoding to work
		if isinstance(title, unicode):
			title = title.encode('utf-8')
		# Percent decode
		title = urllib.unquote(title)
		# Convert back to Unicode
		try:
			title = unicode(title, 'utf-8')
		except UnicodeDecodeError:
			title = unicode(title, 'latin-1')
		# HTML character references
		title = html2unicode(title)
		# Remove ltr and rtl markers
		title = title.replace(u'\u200e', '').replace(u'\u200f', '')
		# Underscore to space and Strip space
		title = title.replace('_', ' ').strip()
		# Merge multiple spaces
		while '  ' in title:
			title = title.replace('  ', ' ')

		# Interwiki and namespace parse
		for part in title.split(':')[:-1]:
			prefix = part.lower().strip()
			# FIXME support other languages namespaces
			if prefix == '':
				self._namespace = 0
				title = title[len(prefix)+1:]
				break
			elif prefix.capitalize() in namespaces.values():
				self._namespace = namespaces.keys()[namespaces.values().index(prefix.capitalize())]
				break
#			elif prefix.lower() == self._site.family.name:
#				self._namespace = 4  # Project namespace
#				title = title[len(prefix)+1:]
#				break
#			elif prefix.lower() == self._site.family.name + ' talk':
#				self._namespace = 5  # Project talkspace
#				title = title[len(prefix)+1:]
#				break
			elif prefix in supported_languages:
				# Changing Languages
				if prefix!=self._site.lang:
					self._site = Site(prefix, self._site.family)
				title = title[len(prefix)+1:]
			elif prefix in families.keys():
				# Changing Families
				if prefix!=self._site.family.shortname:
					self._site = Site(self._site.lang, Family(prefix))
				title = title[len(prefix)+1:]
			else:
				break
		# Clean up title
		# FIXME better code
		if self._namespace is None:
			self._namespace = defaultNamespace
			if defaultNamespace:
				title = namespaces[defaultNamespace]+':'+title
		# First uppercase
		# FIXME firstupper can be namespace dependent, ouch
		firstupper = self._site.family.name in ('wikipedia', 'wikimedia')
		if title and firstupper:
			title = title[0:1].upper() + title[1:]
		self._title = title.strip()# is this needed now??? -> .replace('_', ' ').strip('\t :')

	def __str__(self):			return self.title(asLink=True, forceInterwiki=True).encode('utf-8')
	def __unicode__(self):		return self.title(asLink=True, forceInterwiki=True)
	def __repr__(self): 		return '%s(%r, %r)'%(self.__class__.__name__, self._site, self._title)
	def __hash__(self): 		return hash(unicode(self))
	def site(self):				return self._site
	def latestRevision(self):	return 0
	def isIpEdit(self): 		return False
	def canBeEdited(self):		return True
	def isTalkPage(self):		return self._namespace % 2 == 1
	def protocol(self): 		return self._site.protocol()
	def namespace(self):		return self._namespace
	def hostname(self): 		return self._site.hostname()
	def path(self):				return '/w/index.php'
	def urlname(self):			return self.title(asUrl=True, allowInterwiki=False)
	def exists(self):
		try:   return self.get() and True
		except:return False
	def getReferences(self, follow_redirects=True, withTemplateInclusion=True, onlyTemplateInclusion=False, redirectsOnly=False):
		pass
		import pagegenerators
		gf = pagegenerators.GeneratorFactory()
		gf.limit=500
		return gf.api({'list':'backlinks','bltitle':self.title(),}, 'bl')
	def linkedPages(self):
		try:					return [Page(self._site, m.group(1)) for m in re.finditer(ur'\[\[([^][|<>#\n]+)[#|][^][\n]*\]\]', self.get())]
		except NoPage:			raise
		except IsRedirectPage:	raise
		except SectionError:	return []
	def isRedirectPage(self):
		try:
			self.get()
		except IsRedirectPage:
			return True
		except (NoPage, SectionError):	
			pass
		return False
	def title(self, underscore=False, asUrl=False, asLink=False, allowInterwiki=False, forceInterwiki=False):
		if allowInterwiki and (forceInterwiki or self._site != getSite()):
			if self._site.family != getSite().family:
				title = u'%s:%s:%s' % (self._site.family.shortname, self._site.lang, self._title)
			else:
				title = u'%s:%s' % (self._site.lang, self._title)
		else:
			title = self._title
		if asUrl:
			title = urllib.quote(title.replace(u' ', u'_').encode('utf-8'), safe=";@$!*(),/:-_.")  # see wfUrlencode() in GlobalFunctions.php and PHP's urlencode
		if underscore:
			title = title.replace(u' ', u'_')
		if asLink:
			return u'[[%s]]'%(title,)
		else:
			return title
	def sectionFreeTitle(self, underscore=False):
		return self.title(underscore=underscore)[:self.title().index(u'#') if '#' in self.title() else None]
	def titleWithoutNamespace(self, underscore=False):
		if self.namespace() == 0:
			return self.title(underscore=underscore)
		else:
			return self.title(underscore=underscore).split(':', 1)[1]
	def aslink(self, forceInterwiki=False):
		return self.title(asLink=True, allowInterwiki=True, forceInterwiki=forceInterwiki)
	def get(self, force=False, get_redirect=False, follow_redirects=False, change_edit_time=True):
		# all NoPage exception are contained here for convience
		for illegalChar in u'#<>[]|{}\n\ufffd':
			if illegalChar in self.sectionFreeTitle():
				raise BadTitle(u'Illegal character in %r!' % self.aslink())
		# XXX Hack for bookmarks
		if self._title.startswith(('Special:WhatLinksHere/',)):
			self._redirarg = self._title[self._title.index('/')+1:]
			raise IsRedirectPage, self._redirarg
		if self.namespace() < 0:
			raise NoPage('%s is in a virtual namespace!' % self.aslink())
		if not self._title:
			raise BadTitle("No title")
			
		if not hasattr(self, '_contents') or force:
			params = {
				'format':  'xml',
				'action':  'query',
				'prop':    'info|revisions',
				'inprop':  'protection|watched',
				'rvprop':  'content|timestamp',
				'titles':  self.title(),
				'meta':    'tokens',
			}
			if 'oldid' in SysArgs:
				params['rvstartid'] = SysArgs.get('oldid')
				params['rvendid'] = SysArgs.get('oldid')
			if SysArgs.get('oaKey') and SysArgs.get('oaToken'):
				try:  # OAuth fetch
					import requests, requests_oauthlib, oauth_config
					consumer = oauth_config.consumers[0]
					auth1 = requests_oauthlib.OAuth1(
						consumer['key'],
						client_secret=consumer['secret'],
						resource_owner_key=SysArgs.get('oaKey'),
						resource_owner_secret=SysArgs.get('oaToken'),
					)
					del oauth_config, consumer
				except:
					exec "requests_oauthlib.OAuth1 failed()"  # throw exception
				req  = requests.get('https://%s%s'%(self._site.hostname(), self._site.apipath(),), params=params, auth=auth1)
				if Debug: print('<!--', repr(req.url), '-->')
				text = req.content
				self.watched = ' watched=""' in text
				# Edit token
				tnBegin = text.find(' csrftoken="')
				if tnBegin > 0:
					self.edittoken = text[tnBegin+12:text.index('"', tnBegin+12)]
			else:
				text = self._site.getUrl(self._site.apipath(), params)
			self._html = text

			if not '</pages>' in text:
				if Debug: print(text)
				if '<interwiki>' in text:
					raise NoPage("Please use offical correct interwiki")
				else:
					raise ServerError("API server error (%r)"%text[:80])
			self.protection = None
			# get values for put()
			self.wpEdittime = ''
			etBegin = text.find(' timestamp="')
			if etBegin > 0 and text[etBegin+32] == '"':
				self.wpEdittime = ''.join(c for c in text[ etBegin+12:etBegin+32] if c.isdigit())

			# XXX hack to set namespace after downloading
			nsBegin = text.find(' ns="')
			if nsBegin > 0:
				self._namespace=int(text[nsBegin+5:text.index('"', nsBegin+5)])
			
			idBegin = text.find(' pageid="')
			if idBegin > 0:
				self.id=int(text[idBegin+9:text.index('"', idBegin+9)])

			rvBegin = text.find(' lastrevid="')
			if rvBegin > 0:
				self.revisionid=int(text[rvBegin+12:text.index('"', rvBegin+12)])

			# Used to check against deletion timestamps
			stBegin = text.find(' starttimestamp="')
			if text[stBegin+37] == '"':
				self.wpStarttime= ''.join(c for c in text[ stBegin+17:stBegin+37] if c.isdigit())
			else:
				self.wpStarttime = time.strftime('%Y%m%d%H%M%S')
			if not '</revisions>' in text:
				if ' missing=""' in text:
					self._contents = u""
					raise NoPage("Page does not exist.")
				#elif ' invalid="' in text:
				# XXX? remove no history tab check
				# history tab check is ... what again?
				# I think is was the title blacklist
				#	raise NoPage("Invalid")
				else:
					raise ServerError("No textarea found")
			else:
				iBegin	= text.index('>', text.index('<rev ')) + 1
				try:
					iEnd	= text.index('</rev>')
				except ValueError:
					if text[iBegin-2:iBegin]=="/>":
						iEnd = iBegin
					else:
						raise ServerError("Data: %s"%text)
				except Exception as e:
					with open('./tracebacks/wikilistraw', "a") as f:
							f.write("From wikipedia.get\n<br/>SysArgs:<pre>%r</pre>\n<hr/>Page object:<pre>%r</pre>\n<hr/><pre>%r</pre>Received text<xmp>%s</xmp>"%(e, SysArgs, self, text))
			# Return the default otherwise
				text = unescape(text[iBegin:iEnd])
				self._contents = unicode( text, 'utf-8', errors='replace' )

			try:  # KEEP MAINTENANCE UP TO DATE
				import maintainer
				maintainer.update(self, self._contents)
			except ImportError:	pass
		
			# Get the protection status
			#if 'mw-protectedpagetext' in self._html:
			#elif 'mw-semiprotectedpagetext' in self._html or 'semiprotectedpagewarning' in self._html:
				# They can't seem to mak up their mind on what to call it
			# FIXME improve
			if '<pr type="edit" level="sysop"' in self._html:
				self.protection = "sysop"
			elif '<pr type="edit" level="autoconfirmed"' in self._html:
				self.protection = "autoconfirmed"

			# TODO internationalize
			if u'#REDIRECT' == self._contents.upper().strip()[0:9]:
				#print '<pre>%s</pre>'%escape(self._contents.strip())
				i1 = self._contents.find('[[') + 2
				i2 = (self._contents.find('#', i1)+1 or self._contents.find(']]', i1)+1)-1
				self._redirarg = self._contents[i1:i2]
				if get_redirect:
					pass
				elif follow_redirects:  # follows by changing page title
					self._title = self._redirarg
					return self.get(follow_redirects=False)
				else:
					raise IsRedirectPage, self._redirarg
		return self._contents

	def put_async(self, newtext, comment=None, watchArticle=None, minorEdit=True, force=False, callback=None):
		self.put(newtext, comment=comment, minorEdit=minorEdit)
		if callable(callback):callback()
	
	def put(self, newtext, comment=None, watchArticle=None, minorEdit=None, force=False):
		if not hasattr(self, '_html'):
			# get wpStarttime and wpEdittime and csrftoken
			self.get(force=True)
		
		if comment is None:
			comment = EditMsg.strip()
		#	# Append using filename to edit summaries
		#	#comment = ('%s using [[tools:%s|%s]]' % (EditMsg.strip(), os.getenv('SCRIPT_URL')[1:], sys.argv[0][:-3]))
		#	comment = ('[[tools:~dispenser/view/|%s]]: %s' % (sys.argv[0][2:-3], EditMsg.strip(), ))
		if not comment:
			comment = SysArgs.get('summary', '').decode('utf-8').replace('_',' ')
		if 'wpSummary' in SysArgs:
			comment = SysArgs.get('wpSummary').decode('utf-8').replace('_',' ')
		
		edittoken = getattr(self, 'edittoken', SysArgs.get('wpEditToken',''))
		
		def isWatched(page):
			if hasattr(self, 'watched'):
				return self.watched
			# TODO cleanup and generalize
			if SysArgs.get('wltoken') and SysArgs.get('username'):
				data = {
					'action':       'query',
					'list':         'watchlistraw',
					'format':       'xml',
					'wrlimit':      '1',
					'wrnamespace':	'%d'%page.namespace(),
					'wrowner':      SysArgs.get('username'),
					'wrtoken':      SysArgs.get('wltoken'),
					# XXX: limit only to the page we're looking for
					'wrcontinue':   '%d|%s'%(page.namespace(), page.titleWithoutNamespace(underscore=True)),
					'rawcontinue': '',
				}
				wr_data = page.site().getUrl(page.site().apipath(), data=data)
				try:
					if Debug:print('<xmp>', wr_data, '</xmp>')
					if "<error " not in wr_data:
						wrBegin	= wr_data.find(' title="', wr_data.find('<wr '))
						if wrBegin > 0:
							wr_data_page = unescape(wr_data[wrBegin+8:wr_data.index('"', wrBegin+8)]).decode('utf-8')
							#if wr_data_page < page.titleWithoutNamespace(underscore=True): raise
							return wr_data_page == page.title()
						else:  # beyond the end of the list
							return False
				except Exception as e:
					print('<!-- %r -->' % (e,))
					#print "ERROR %r<br/>"%(e,)
					#raise
					with open('./tracebacks/wikilistraw', "a") as f:
						f.write("From wikipedia.isWatched\n<br/><pre>%r</pre>\n<hr/><pre>%r</pre>\n<hr/><pre>%r</pre><xmp>%s</xmp>"%(e, SysArgs, page, wr_data))
					pass
			# Return the default otherwise
			return SysArgs.get('watchdefault', '1') in ('1', 'true')

		taskid = SysArgs.get('task', '')
		actionurl = "https://%s%s?title=%s&amp;action=%s&amp;editintro=Template:XSS-editnotice" % (self.hostname(), self.path(), self.urlname(), 'submit')
		#if re.search(r' Mobile/\d+', os.getenv('HTTP_USER_AGENT', '')):
		#	#actionurl = actionurl.replace('.wikipedia.org/', '.m.wikipedia.org/')
		#	actionurl += "&amp;useskin=minerva"
		if re.search(r' Trident/| Edge/|MSIE [89]', os.getenv('HTTP_USER_AGENT', '')):
			actionurl = "/~dispenser/cgi-bin/save.py?title=%s&amp;action=%s&amp;domain=%s" % (self.urlname(), 'submit', self.hostname(),)
		if taskid:
			actionurl = "/~dispenser/cgi-bin/save.py?title=%s&amp;action=%s&amp;domain=%s&amp;task=%s" % (self.urlname(), 'submit', self.hostname(), taskid)
			
		returnto = SysArgs.get('returnto')
		if returnto != None:
			actionurl = "/~dispenser/cgi-bin/save.py?title=%s&amp;action=%s&amp;domain=%s&amp;returnto=%s" % (self.urlname(), 'submit', self.hostname(), returnto)
			
		print('<form id="editform" name="editform" method="post" action="%s" enctype="multipart/form-data">'%actionurl)
		if   self.protection == "sysop":
			print('<p><strong style="font-size:130%">This page is currently protected, and can be edited only by administrators.</strong>\n</p>')
		# Don't show logged in users -- Fully logged in since I'm lazy
		elif self.protection == "autoconfirmed" and len(edittoken)!=34:
			print('<div class="fmbox" style="padding: .5em 1em; vertical-align: middle; border: solid #aaaaaa 1px"><strong>Warning</strong>: This page is currently semi-protected, and can be edited only by established registered users.</div>')
		else:
			pass
			if time.time() < 1491091200:
				print('<div class="fmbox" style="padding: .5em 1em; vertical-align: middle; border: solid #aaaaaa 1px; font-weight:bold;">Your free trial ends in %s hours, <a href="https://en.wikipedia.org/wiki/User:Dispenser/Tools_subscription">Learn more</a></div>' % (("%s"%((1491091200 - time.time())/3600.0))[0:3].strip('.'),))
			
		print('<input type="hidden" name="wpAntispam" value="" />')
		print('<input type="hidden" name="wpUnicodeCheck" value="ℳ𝒲♥𝓊𝓃𝒾𝒸ℴ𝒹ℯ" />')
		print('<input type="hidden" value="" name="wpSection" />')
		print('<input type="hidden" value="%s" name="wpStarttime" />' % (self.wpStarttime,))
		print('<input type="hidden" value="%s" name="wpEdittime" />' % (self.wpEdittime,))
		print('<textarea tabindex="1" name="wpTextbox1" id="wpTextbox1" rows="25" cols="80" style="width:100%;box-sizing:border-box;">' +
		      escape(newtext).encode('utf-8') +
		      '</textarea>')
		# IE8 XSS filter corrupts sent text
		# Examples:  http://enwp.org/?diff=454843408
		if not edittoken and re.search(r' Trident/| Edge/|MSIE [89]', os.getenv('HTTP_USER_AGENT', '')):
			print("""
<div id="xssfilter-workaround" class="fmbox xssfilter-workaround" style="padding:.5em 1em; border:solid #f4c430 1px;">
<img alt="" src="//upload.wikimedia.org/wikipedia/commons/thumb/7/74/Ambox_warning_yellow.svg/40px-Ambox_warning_yellow.svg.png" width="40" height="34" style="float:left; margin:0.8em 1em 0.8em 0; "/>
Please <strong>connect</strong> (top right) and click "Save page" below when done. <br/>
If you get a blank screen or an edit box you did something wrong. <br/>
If you do not want to create an account, use Firefox or Chrome. (<a href="https://phabricator.wikimedia.org/T34013" class="extiw">Bug T34013</a>)
</div>""")
		print('<div class="editOptions">')
		print('<label id="wpSummaryLabel" for="wpSummary">%s</label>'%('Edit summary:',))
		print('<input tabindex="2" type="text" value="%s" name="wpSummary" id="wpSummary" maxlength="200" size="60" />' % (escape(comment.encode('utf-8')),))
		print('<input name="wpAutoSummary" type="hidden" value="d41d8cd98f00b204e9800998ecf8427e" /><br />')	# blank summary check
		print('<input name="wpMinoredit" value="1"%s tabindex="3" accesskey="i" id="wpMinoredit" type="checkbox" />&nbsp;<label for="wpMinoredit" title="Mark this as a minor edit [alt-shift-i]" accesskey="i">%s</label>' % (' checked="checked"' if minorEdit == True or minorEdit == None and SysArgs.get('minordefault', "0") in ("1", "true") else '', 'This is a minor edit',))
		print('<input name="wpWatchthis" value="1"%s tabindex="4" accesskey="w" id="wpWatchthis" type="checkbox" />&nbsp;<label for="wpWatchthis" title="Add this page to your watchlist [alt-shift-w]" accesskey="w">%s</label>' % (' checked="checked"' if isWatched(self) else '', 'Watch this page'))

		print('<div class="editButtons">')
		# Disable the Save button for logged in users (Test: Nov 2011)
		# SysArgs.get('username')
		print(' <input id="wpSave" name="wpSave" type="submit" tabindex="5" value="%s" accesskey="s" %s%s/>' % (
			'Save page' if self.revisionid else 'Create page',
			'disabled="disabled" ' if not edittoken else '',
			r' onclick="if(getCookie(&quot;oaKey&quot;))this.form.action=this.form.action.replace(/^https?:\/*([^/]+)\/w\/index.php\?/,&quot;save.py?domain=$1&amp;&quot;)"',
		))
		print(' <input id="wpPreview" name="wpPreview" type="submit" tabindex="6" value="%s" accesskey="p" />'%('Show preview',))
		print(' <input id="wpDiff" name="wpDiff" type="submit" tabindex="7" value="%s" accesskey="v" />'%('Show changes',))
		if taskid:
			print('<span class="" style="font-weight:bold"><a href="%s">%s</a></span> | ' % (actionurl, 'Skip page',))
			
		print('<span class="editHelp"><a href="//%s%s" title="%s" id="mw-editform-cancel">%s</a></span>' % tuple(escape(s) for s in (self.hostname(), self._site.nice_get_address(self.urlname()), self.title().encode('utf-8'), 'Cancel',)))
		print('</div>')
		# Disable problematic buttons with IE's XSS Filter
		if 'save.py' not in actionurl:
			print("""
<script type="text/javascript">
// Detect IE8+ even with compatibility mode
if(typeof(document.documentMode)==='number') {
	document.getElementById('wpSave').disabled = false;
	document.getElementById('wpPreview').disabled = true;
	document.getElementById('wpDiff').disabled = true;
}
</script>""")
		# XXX '_' -> '+' should fix bookmarklet instead
		print('<input type="hidden" value="%s" name="wpEditToken" />' % (escape(edittoken.replace('_\\','+\\') or '+\\'),))
		print('<input value="1" name="wpUltimateParam" type="hidden">')
		print('</div></form>')
		if newtext != self._contents:
			try:  # Log
				import maintainer
				maintainer.processPage(self)
			except ImportError:	pass

def unescape(s):
	if '&' not in s:
		return s
	s = s.replace("&lt;", "<")
	s = s.replace("&gt;", ">")
	s = s.replace("&apos;", "'")
	s = s.replace("&quot;", '"')
	s = s.replace("&amp;", "&")  # Must be last
	return s

def escape(s):
	s = s.replace("&", "&amp;")  # Must be first
	s = s.replace("<", "&lt;")
	s = s.replace(">", "&gt;")
	s = s.replace('"', '&quot;')
	return s

inf = float('inf')
js_escaped = dict((chr(i), chr(i) if i > 31 else b'\\x%02x'%i) for i in range(256))
js_escaped.update({
	# IE < 9 doesn't support \v
	b'\b':  b'\\b',
	b'\t':  b'\\t',
	b'\n':  b'\\n',
	b'\f':  b'\\f',
	b'\r':  b'\\r',
	b'"':	b'\\x22',  # \" may confuse the HTML parser
	b'&':	b'\\x26',
#	b'/':	b'\\x2F',  # May break regular expressions
	b'>':	b'\\x3E',
	b'<':	b'\\x3C',
	b'\\':  b'\\\\',
})
def jsescape(s, encoding='utf-8'):
	if s is None:
		return b'null'
	elif isinstance(s, bool):
		return b'true' if s else b'false'
	elif isinstance(s, float):
		if s != s:
			return b'NaN'
		elif s == inf:
			return b'Infinity'
		elif s == -inf:
			return b'-Infinity'
		else:
			return bytes(s)
	elif isinstance(s, (int, long)):
		return bytes(s)
	elif isinstance(s, bytes):
		return b'"'+b''.join(map(js_escaped.__getitem__, s))+b'"'
	elif isinstance(s, unicode):
		# XXX Incorrect, just avoid Unicode control characters
		return b'"'+b''.join(map(js_escaped.__getitem__, s.encode('utf-8')))+b'"'
	elif isinstance(s, list):
		return b'['+b','.join(jsescape(item, encoding) for item in s)+b']'
	elif isinstance(s, dict):
		return b'{'+b','.join("%s:%s"%(jsescape(key, encoding), jsescape(value, encoding)) for key, value in s.iteritems())+b'}'
	else:
		raise TypeError("Not implemented for %s"%type(s))

def unquote(s):
	return urllib.unquote(s if isinstance(s, bytes) else s.encode('utf-8')).decode('utf-8')

def removeDisabledParts(text, tags=['*']):
	regexes = {
			'comments':		r'<!--.*?-->',
			'includeonly':	r'<includeonly>.*?</includeonly>',
			'nowiki':		r'<nowiki>.*?</nowiki>',
			'pre':			r'<pre>.*?</pre>',
			'source':		r'<source .*?</source>',
			'gallery':		r'<gallery.*?</gallery>',
			'math':			r'<math>.*?</math>',
	}
	if '*' in tags:
		tags = regexes.keys()
	return re.compile('|'.join([regexes[tag] for tag in tags]), re.IGNORECASE | re.DOTALL).sub('', text)
def setAction(s):
	global EditMsg
	EditMsg = s
def showDiff(old, new, fromdesc=u"Current revision", todesc=u"Your text"):
	import difflib
	class HtmlDiff(difflib.HtmlDiff):
		_table_template = u'''<table class="diff" id="difflib_chg_%(prefix)s_top">
<col class="diff_next" /><col class="diff-marker" /><col class="diff-content" />
<col class="diff_next" /><col class="diff-marker" /><col class="diff-content" />
%(header_row)s
<tbody>
%(data_rows)s
</tbody>
</table>'''
		def _format_line(self, side, flag, linenum, text):
			try:
				linenum = '%d' % linenum
				id = ' id="%s%s"' % (self._prefix[side],linenum)
			except TypeError:
				# handle blank lines where linenum is '>' or ''
				id = ''
			# replace those things that would get confused with HTML symbols
			text=text.replace("&","&amp;").replace(">","&gt;").replace("<","&lt;")
			return u'<td class="diff-marker"%s>%s</td><td class="%s"><div>%s</div></td>' % ( 
				id,
				linenum,
				((side and 'diff-addedline' or 'diff-deletedline') if flag else 'diff-context') if linenum else '',
				text
			)
	# difflib can't do <ins> nor <del> out of the box
	print(HtmlDiff().make_table(
			old.split('\n'),
			new.split('\n'),
			fromdesc=fromdesc,
			todesc=todesc,
			context=True,
			numlines=1
	).encode('utf-8'))

def sectionencode(text, encoding='utf-8'):
    """Encode text so that it can be used as a section title in wiki-links."""
    return urllib.quote(text.replace(" ","_").encode(encoding), safe=':').replace("%",".")
	# Note there a bug in pywikipedia, it include '/' as a safe charater

######### Unicode library ###########
def UnicodeToAsciiHtml(s):
	return s.encode('ascii', 'xmlcharrefreplace')
def url2unicode(title, site, site2 = None):
#try:
	return urllib.unquote(title.encode('utf-8') if isinstance(title, unicode) else title).decode('utf-8')
#	except UnicodeDecodeError:
#		return urllib.unquote(title).decode('latin-1')
def unicode2html(x, encoding):
	try:
		x.encode(encoding)
	except UnicodeError:
		x = UnicodeToAsciiHtml(x)
	return x
def html2unicode(t, ignore = []):
	t = unicode(t)
	start = t.find('&#', 0)
	while start != -1:
		end = t.find(';', start)
		if end < 0:  # unterminated
			start = t.find('&#', start+2)
			continue
		if t[start+2:start+3] in ('X', 'x'):
			try: t=t[:start]+unichr(int(t[start+3:end], 16))+t[end+1:]
			except ValueError: start += 3
		else:
			try: t=t[:start]+unichr(int(t[start+2:end], 10))+t[end+1:]
			except ValueError: start += 2
		start = t.find('&#', start)
	#FIXME DoubleEscapeProblems &#16;&amp;lt;
	if not ignore:
		t = unescape(t)  # Decode xhtml elements
	if '&' in t and ';' in t:
		import htmlentitydefs
		for (name, codepoint) in htmlentitydefs.name2codepoint.iteritems():
			if codepoint not in ignore:
				t = t.replace('&%s;'%name, unichr(codepoint))
			
	return t
def translate(code, dictText):
	# If a site is given instead of a code, use its language
	if hasattr(code,'lang'): code = code.lang
	return dictText.get(code, dictText.get('en'))

#TODO sort me
def getCategoryLinks(text, site):								return []
def removeCategoryLinks(text, site, marker = ''):				return text
def replaceCategoryInPlace(oldtext, oldcat, newcat, site=None):	return oldtext
def replaceCategoryLinks(oldtext, new, site=None):				return oldtext
def getLanguageLinks(text, insite = None, pageLink = "[[]]"):	return {}
def removeLanguageLinks(text, site = None, marker = ''):		return text
def replaceLanguageLinks(oldtext, new, site = None):			return oldtext

def handleArgs():
	return tuple(u'-'+unquote(s).replace(u'=', u':', 1) for s in os.getenv("QUERY_STRING", '').split("&") if s)
def getSite(code = None, fam = None, user=None, persistent_http=None):
	return MySite
def stopme():
	pass
def showHelp(moduleName = None):
	moduleName = moduleName or sys.argv[0][2:sys.argv[0].rindex('.')]
	exec('import %s as module' % moduleName)
	helpText = module.__doc__
	if hasattr(module, 'docuReplacements'):
		for key, value in module.docuReplacements.iteritems():
			helpText = helpText.replace(key, value.strip('\n\r'))
	print('<div id="showHelp" style="float:right; font-size:0.75em; margin:1em 0 0;">Information or features may not work in HTML mode.</div>')
	print('<pre>%s</pre>' % escape(helpText.strip()))
def inputChoice(question, answers, hotkeys, default = None):
	output('%s [%s] %s'%(question, ', '.join(answers), default))
	return default.lower()
def input(text):
	output(text)
	return ''
def output(s='', decoder = None, newline = True, toStdout = False):
	print re.sub(
		ur'\[\[([^[\]{|}<\n>]*?)\]\]',
		lambda m: ur'[[<a href="//%s%s" title="%s">%s</a>]]'%(
			MySite.hostname(),
			MySite.nice_get_address(urllib.quote(unescape(m.group(1).replace(' ','_')).encode('utf-8'), safe=";@$!*(),/:-_.")),
			m.group(1).replace('_', ' '),
			m.group(1),
		),
		re.sub(
			r'\03\{(light|)([^{}]*)\}(.*?)\03\{default\}',
			r'<span style="color:\2;">\3</span>',
			escape('%s\n'%s if newline else s).replace('\n', "<br />\n").rstrip()
		)
	).encode('utf-8'),
	## FIXME either there's an XSS venerablity or & isn't encoded right
	#print re.sub(r'\03\{(light|)([^{}]*)\}(.*?)\03\{default\}', r'<span style="color:\2;">\3</span>', escape('%s\n'%s).replace('\n', "<br />\n")).encode('utf-8')
def html(string, data=None):
	if data == None:
		s = string
	else:
		s = string%tuple(escape(s) if isinstance(s, (bytes, unicode)) else s for s in data)
	print(s.encode('utf-8') if isinstance(s, unicode) else s)

# Local exceptions
class Error(Exception):			"""Wikipedia error"""
class NoPage(Error):			"""Page does not exist"""
class BadTitle(NoPage):			"""Server responded with BadTitle."""
class IsRedirectPage(Error):	"""Page is a redirect page"""
class LockedPage(Error):	    """Page is locked"""
class NoSuchSite(Error):		"""Site does not exist"""
class SectionError(Error):		"""The section specified by # does not exist"""
class ServerError(Error):		"""Got unexpected server response"""
# Cannot save
class PageNotSaved(Error):				"PageNotSaved"
class EditConflict(PageNotSaved):		"""There has been an edit conflict while uploading the page"""
class SpamfilterError(PageNotSaved):	"""PageNotSaved due to MediaWiki spam filter"""



#
# Extra API for web programming
#
timings = []
def logtime(event_name):
	global timings
	timings.append((event_name, time.time(),))

def timereport():
	last = StartTime
	lout = []
	for event_name, sec in timings:
		lout.append('%7.3f %7.3f    %s'%(sec-StartTime, sec-last, event_name, ))
		last = sec
	return '\n'.join(lout)

def startContent(title=None, form=True, notice="", page=None, submitLabel='&#x21B5;', head=None):
	"""
	More or less a work in progress
	title - Application title
	page - Processed page's title
	notice - Application notice, displays above the title
	form - bool display input form
	submitLabel - label for submit button on form defaults to cartage return symbol
	"""
	if not page: page = MyPage
	site = page._site
	tool = sys.argv[0]
	tool = tool[tool.rfind('/')+1:tool.rfind('.')].replace('_', ' ')
	langdir = 'rtl' if site.language() in ('ar', 'fa', 'hu') else 'ltr'
	if not title:
		title = tool[0:1].upper()+tool[1:]
		if page.title():
			title += ' - %s'%page.title()
	print '<!DOCTYPE html>'
	print '<html lang="%s" dir="%s">' % (site.language() if len(site.language()) == 2 else 'en', langdir)
	with open('./text/head.html') as f:
		print f.read().replace('$1', escape(title.encode('utf-8'))).replace('$2', head or '<!-- wikipedia.startContent() -->')
	print """<body class="mediawiki %(langdir)s %(tool)s">
<div id="mw_header"><h1 class="firstHeading">%(title)s</h1></div>
	<div id="mw_main">
	<div id="mw_contentwrapper">

	<!-- content -->
	<div id="mw_content">
	<!-- contentholder does nothing by default, but it allows users to style the text inside
	     the content area without affecting the meaning of 'em' in #mw_content, which is used
	     for the margins -->
	<div id="mw_contentholder">
		<div class='mw-topboxes'>
<noscript>
<div class="tsnotice noscriptbar" onclick="location.href='/~dispenser/view/Help#XSS'" style="cursor:pointer;">
Most tools require the use of JavaScript.  If you are using Firefox with the NoScript addon, please mark dispenser.info.tm as trusted.  See the <a href="/~dispenser/view/Help#XSS"><b>Help page</b></a> for details.
</div>
</noscript>
""" % dict(langdir=langdir, tool=escape(tool), title=escape(title.encode('utf-8')))
	
	if page.title():
		print """<script type="text/javascript">
var skin="modern",
stylepath="/~dispenser/resouces/",
wgArticlePath="/wiki/$1",
wgScriptPath="/w",
wgScript=%s,
wgServer=%s,
wgCanonicalNamespace=%s,
wgNamespaceNumber=%s,
wgPageName=%s,
wgTitle=%s,
wgArticleId=%s,
wgUserLanguage=%s,
wgContentLanguage=%s,
wgCurRevisionId=%s,
wgDBname=%s,
wgUserName=%s;
</script>"""%tuple(jsescape(s) for s in (site.path(), "https://"+site.hostname(), site.namespace(page.namespace()), page.namespace(), page.title(underscore=True), page.titleWithoutNamespace(), None, site.language(), site.language(), None, site.dbName(), SysArgs.get('username'),))

	if notice:
		print notice.encode('utf-8')
	else:
		try: print open('./text/notice.html', 'rb').read()
		except IOError: pass
	print '</div>'
	print '<div id="contentSub"></div>'

	print '<!-- start content -->'
	if form:
		print '<form action=""><div style="text-align: center;">'
		print '<code id="cgi_cmd">%s -page:</code>' % sys.argv[0][sys.argv[0].rfind('/')+1:]
		print '<input accesskey="f" id="page" name="page" size="40" title="%s" value="%s" onchange="fixTitle(this)" placeholder="Page title or URL" />' % ("Paste or enter a URL or page title [alt-shift-f]", escape(page.title(allowInterwiki=True).encode('utf-8')))
		print '<input value="%s" type="submit" /></div></form>' % submitLabel
	# Web server buffer size might cause a blank page to appear until a chunk large enough is sent
	# So we flush what we already have
	sys.stdout.flush()

def endContent(*notes):
	if QueryContinue:  # FIXME
		print '<p><a href="%s">Continue to next set of results</a></p>' % escape(os.getenv("REQUEST_URI", '')+QueryContinue.encode('utf-8'))
	print """
<!-- end content -->
		<div class='mw_clear'></div>
	</div><!-- mw_contentholder -->
	</div><!-- mw_content -->
	</div><!-- mw_contentwrapper -->
"""
	print "<!-- generated in %s seconds -->" % time.clock()

	try:	mtime = time.gmtime(os.path.getmtime(os.getenv("SCRIPT_FILENAME")))
	except: mtime = (0,)*9
	with open('./text/footer.html') as f:
		print f.read().replace("$1", '<br />'.join(notes + (
			time.strftime('This script was last modified on %d %B %Y at %H:%M (UTC)', mtime),
			'Page generated in %#4.2f seconds' % (time.time()-StartTime,),
		) ))
	print '</body>'
	print '</html>'
	if timings:
		logtime("endContent() done")
		print "<!--\n%s\n-->"%(escape(timereport()),)
#	title = sys.argv[0]
#	with open('./generation_stats/%s'%title[title.rfind('/')+1:title.rfind('.')], 'a') as f:
#		#f.write('%s\t%s\t%s\t%s\n'% (time.strftime("%Y-%m-%d %H:%M:%S"), SysArgs.get('page', SysArgs.get('prefix', '')), time.strftime("%Y-%m-%d %H:%M:%S", mtime), time.time()-StartTime,))
#		f.write('\t'.join((os.getenv("HTTP_X_FORWARDED_FOR", ''), os.getenv("HTTP_USER_AGENT", ''), os.getenv("QUERY_STRING", ''),)))
#		f.write('\n')

def handleUrlAndHeader(connicalize=True, allowBots=False, defaultRedirect=None):
	"""
	Redirects the URL to a better format and prints an HTTP header
	"""
	# prog.py/pagename -> prog.py?page=pagename
	# FIXME prog.py/?page=
	if os.getenv("PATH_INFO", '/') != '/':
		redirect = os.getenv("SCRIPT_NAME", '') + "?page=" + os.getenv("PATH_INFO", '/')[1:].replace('&', '%26').replace('+', '%2B')
		if os.getenv("QUERY_STRING", ''):
			redirect += "&"+os.getenv("QUERY_STRING")
	else:
		redirect = os.getenv("REQUEST_URI", '')

	# if os.getenv("HTTP_UPGRADE_INSECURE_REQUESTS") and not os.getenv("HTTPS"):
	# 	#redirect = "https://" + os.getenv("HTTP_HOST") + redirect
	# 	redirect = "https://dispenser.info.tm" + redirect

	if connicalize:
		# %7E isn't deferred since cookies stored at /~dispenser/ can't be read at /%7Edispenser/
		redirect = redirect.replace('%20', '_').replace('+', '_').replace('%3A', ':').replace('%2F', '/').replace('%7E', '~')
		while "__" in redirect:
			redirect = redirect.replace("__", "_")

	if defaultRedirect and ('?' not in redirect or not any(s.split('=')[-1] for s in redirect[redirect.index('?')+1:].split('&'))) and not os.getenv("PATH_INFO", ''):
		redirect = defaultRedirect
	
	if not os.getenv("HTTP_ACCEPT"):
		# run from the command line
		return True
	elif not allowBots and '?' in redirect and (
		any(s in os.getenv("HTTP_USER_AGENT", 'unknown crawler').lower() for s in ('crawler', 'http://', 'https://', 'robot', 'spider', 'http-client'))
		or os.getenv("HTTP_X_FORWARDED_FOR", '') in ('111.13.8.126', )
	) and not os.getenv("HTTP_USER_AGENT", '').startswith(("W3C_Validator", "Validator.nu/LV")):
		# Prevent bots indexing dynamicly generated pages
		print 'Status: 403'
		print 'Content-Type: text/html; charset=utf-8'
		print
		print """
<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>403 Forbidden</title>
</head><body>
<h1>Forbidden</h1>
<p>Crawling dynamicly generated pages is not allowed
</p>
<hr>
<address>Requesting agent: %s</address>
</body></html>""" % os.getenv("HTTP_USER_AGENT", '[empty]')
		sys.exit()
	elif "translate.google.com" in os.getenv("HTTP_VIA", ''):
		# Viewing through proxy, needlessly breaks JavaScript
		print 'Content-Type: text/html; charset=utf-8'
		print
		print '<!DOCTYPE HTML><html><body>'
		print '<p>This document cannot be translated.  Please view directly at:</p>'
		# Can be self or top.  Top makes the most navigational sense.
		print '<p class="notranslate" onclick="top.window.location.assign(this.innerHTML);" style="color:blue;cursor:pointer;">%s</p>'%(escape('http'+'://'+'dispenser.info.tm'+redirect))
		#print '\n'.join(("%r:\t%r"%(k,v) for (k,v) in os.environ.iteritems()))
		print '</body></html>'
	elif redirect != os.getenv("REQUEST_URI", ''):
		# http://turbo-technical-report.blogspot.com/2006/11/server-side-301-302-http-response.html
		# Saved me quite a bit of trouble. Thanks!
		print "Status: 301"
		print 'Location: ' + redirect
		print 'Content-Type: text/html; charset=utf-8'
		print 
		print """
<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>301 Moved Permanently</title>
</head><body>
<h1>Moved Permanently</h1>
<p>The document has moved <a href="%s">here</a>.
</p>
</body></html>""" % redirect
		sys.exit()
	elif os.getenv("REQUEST_METHOD", "GET") not in ('GET', 'POST'):
		print 'Status: 405 Method not allowed'
		print 'Content-Type: text/html; charset=utf-8'
		print
		print "Method is not allowed, only GET and POST methods are accepted"
		sys.exit()
	else:
		print 'Status: 200 OK'
		#print 'Content-Type: application/xhtml+xml; charset=utf-8'
		print 'Content-Type: text/html; charset=utf-8'
		print
		return True

# Setup the default values
# Unquoting is too early, restrict params/cookies names to ASCII letters/numbers
SysArgs =      dict(urllib.unquote(item).partition("=")[::2] for item in os.getenv("HTTP_COOKIE", "").split("; ") if item)
SysArgs.update(dict(urllib.unquote(item).partition("=")[::2] for item in os.getenv("QUERY_STRING", "").split("&") if item))
try:
	MySite = Site(SysArgs.get('lang', SysArgs.get('hostname', SysArgs.get('dbname', SysArgs.get('site')))), SysArgs.get('family') or SysArgs.get('project'))
except:
	MySite = Site('en', 'wikipedia')
MyPage = Page(MySite, SysArgs.get('page', ''))
Debug  = bool(SysArgs.get('debug'))
if Debug:
	cgitb.enable(logdir=None)
#MySite = Site(([s for s in handleArgs() if s.startswith('-lang:')] or ['-lang:en']).pop()[6:] or 'en', Family(([s for s in handleArgs() if s.startswith('-family:')] or ['-family:w']).pop()[8:] or '-family:w'))
#MyPage = Page(MySite, ([s for s in handleArgs() if s.startswith('-page:')] or ['-page:']).pop()[6:])
#Disable since it breaks tools which assume English default
#MySite = MyPage.site()


setAction('To lazy to use a better edit summary')
class MyURLopener(urllib.FancyURLopener):
	version="DispenserTools (Dispenserbot; +http://dispenser.info.tm/~dispenser/)"



# functions to manipulate wikitext strings (by default, all text arguments
# should be Unicode)
# All return the modified text as a unicode object

def replaceExcept(text, old, new, exceptions, caseInsensitive=False,
				  allowoverlap=False, marker = '', site = None):
	"""
	Return text with 'old' replaced by 'new', ignoring specified types of text.

	Skips occurences of 'old' within exceptions; e.g., within nowiki tags or
	HTML comments. If caseInsensitive is true, then use case insensitive
	regex matching. If allowoverlap is true, overlapping occurences are all
	replaced (watch out when using this, it might lead to infinite loops!).

	Parameters:
		text			- a unicode string
		old			 - a compiled regular expression
		new			 - a unicode string (which can contain regular
						  expression references), or a function which takes
						  a match object as parameter. See parameter repl of
						  re.sub().
		exceptions	  - a list of strings which signal what to leave out,
						  e.g. ['math', 'table', 'template']
		caseInsensitive - a boolean
		marker		  - a string that will be added to the last replacement;
						  if nothing is changed, it is added at the end
	"""

	exceptionRegexes = {
		'comment':	 re.compile(r'(?s)<!--.*?-->'),
		'includeonly': re.compile(r'(?is)<includeonly>.*?</includeonly>'),
		'math':		re.compile(r'(?is)<math>.*?</math>'),
		'noinclude':   re.compile(r'(?is)<noinclude>.*?</noinclude>'),
		# wiki tags are ignored inside nowiki tags.
		'nowiki':	  re.compile(r'(?is)<nowiki>.*?</nowiki>'),
		# preformatted text
		'pre':		 re.compile(r'(?ism)<pre>.*?</pre>'),
		'source':	  re.compile(r'(?is)<source .*?</source>'),
		# inline references
		'ref':		 re.compile(r'(?ism)<ref[ >].*?</ref>'),
		'timeline':	re.compile(r'(?is)<timeline>.*?</timeline>'),
		# lines that start with a space are shown in a monospace font and
		# have whitespace preserved.
		'startspace':  re.compile(r'(?m)^ (.*?)$'),
		# tables often have whitespace that is used to improve wiki
		# source code readability.
		# TODO: handle nested tables.
		'table':	   re.compile(r'(?ims)^{\|.*?^\|}|<table>.*?</table>'),
		# templates with parameters often have whitespace that is used to
		# improve wiki source code readability.
		# 'template':	re.compile(r'(?s){{.*?}}'),
		# The regex above fails on nested templates. This regex can handle
		# templates cascaded up to level 3, but no deeper. For arbitrary
		# depth, we'd need recursion which can't be done in Python's re.
		# After all, the language of correct parenthesis words is not regular.
		'template':	re.compile(r'(?s){{(({{(({{.*?}})|.)*}})|.)*}}'),
		'hyperlink':   re.compile(r'(?P<url>http[s]?://[^\]\s<>]*?[^\]\s\)\.:;,<>"](?=[\]\s\)\.:;,<>"]*\'\')|http[s]?://[^\]\s<>"]*[^\]\s\)\.:;,<>"])'),
		'gallery':	 re.compile(r'(?is)<gallery.*?>.*?</gallery>'),
		# this matches internal wikilinks, but also interwiki, categories, and
		# images.
		'link':		re.compile(r'\[\[(?P<title>[^\]\|]*)(\|[^\]]*)?\]\]')
	}

	# if we got a string, compile it as a regular expression
	if isinstance(old, (bytes, unicode)):
		if caseInsensitive:
			old = re.compile(old, re.IGNORECASE | re.UNICODE)
		else:
			old = re.compile(old, re.UNICODE)

	dontTouchRegexes = []
	for exc in exceptions:
		if isinstance(exc, bytes) or isinstance(exc, unicode):
			# assume it's a reference to the exceptionRegexes dictionary
			# defined above.
			if not exceptionRegexes.has_key(exc):
				raise ValueError("Unknown tag type: " + exc)
			dontTouchRegexes.append(exceptionRegexes[exc])
		else:
			# assume it's a regular expression
			dontTouchRegexes.append(exc)
	index = 0
	markerpos = len(text)
	while index < len(text):
		match = old.search(text, index)
		if not match:
			# nothing left to replace
			break

		# check which exception will occur next.
		nextExceptionMatch = None
		for dontTouchR in dontTouchRegexes:
			excMatch = dontTouchR.search(text, index)
			if excMatch and (
					nextExceptionMatch is None or
					excMatch.start() < nextExceptionMatch.start()):
				nextExceptionMatch = excMatch

		if nextExceptionMatch is not None and nextExceptionMatch.start() <= match.start():
			# an HTML comment or text in nowiki tags stands before the next valid match. Skip.
			index = nextExceptionMatch.end()
		else:
			# We found a valid match. Replace it.
			if callable(new):
				# the parameter new can be a function which takes the match as a parameter.
				replacement = new(match)
			else:
				# it is not a function, but a string.

				# it is a little hack to make \n work. It would be better to fix it
				# previously, but better than nothing.
				new = new.replace('\\n', '\n')

				# We cannot just insert the new string, as it may contain regex
				# group references such as \2 or \g<name>.
				# On the other hand, this approach does not work because it can't
				# handle lookahead or lookbehind (see bug #1731008):
				#replacement = old.sub(new, text[match.start():match.end()])
				#text = text[:match.start()] + replacement + text[match.end():]

				# So we have to process the group references manually.
				replacement = new

				groupR = re.compile(r'\\(?P<number>\d+)|\\g<(?P<name>.+?)>')
				while True:
					groupMatch = groupR.search(replacement)
					if not groupMatch:
						break
					groupID = groupMatch.group('name') or int(groupMatch.group('number'))
					replacement = replacement[:groupMatch.start()] + match.group(groupID) + replacement[groupMatch.end():]
			text = text[:match.start()] + replacement + text[match.end():]

			# continue the search on the remaining text
			if allowoverlap:
				index = match.start() + 1
			else:
				index = match.start() + len(replacement)
			markerpos = match.start() + len(replacement)
	text = text[:markerpos] + marker + text[markerpos:]
	return text

def isDisabled(text, index, tags = ['*']):
	"""
	Return True if text[index] is disabled, e.g. by a comment or by nowiki tags.

	For the tags parameter, see removeDisabledParts() above.
	"""
	# Find a marker that is not already in the text.
	marker = '@@'
	while marker in text:
		marker += '@'
	text = text[:index] + marker + text[index:]
	text = removeDisabledParts(text, tags)
	return (marker not in text)

# MediaWiki specific function that are too useful
def canonicalTitle(title, firstupper=True, underscore=False):
	"""
	Converts unicode or bytes string to mw titles
	support: percent-encoded UTF-8, HTML character references
	"""
	# TODO namespace support, e.g. [[WP: Foo]]
	if isinstance(title, bytes):
		title = title.decode('utf-8')
	# Unpercent-encode
	title = urllib.unquote(title.encode('utf-8'))
	try:   title = unicode(title, 'utf-8')
	except:title = unicode(title, 'latin-1')
	# HTML character references
	title = html2unicode(title)
	# Remove ltr and rtl markers
	title = title.replace(u'\u200e', '').replace(u'\u200f', '')
	# Strip the section part
	if u'#' in title:
		title = title[:title.index(u'#')]
	# Underscore + &nbsp; to space and Strip space
	title = u''.join(u' ' if c.isspace() or c==u'_' else c for c in title).lstrip(u': ').strip()
	# Merge multiple spaces
	while u'  ' in title:
		title = title.replace(u'  ', u' ')
	# First uppercase
	if firstupper and title:
		title = title[0:1].upper() + title[1:]
	if underscore:
		title = title.replace(u' ', u'_')
	return title

