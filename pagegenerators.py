# This is hack together sub function for pagegenerators
import re, urllib, wikipedia

parameterHelp = '''
-cat:             Work on pages in a specific category

-headlinks:       Works on all links that are in heading tags (== [[link]] ==)

-links:           Works on all links on the given page

-new              Works on the 10 newest pages

-page:            name of the page you want to work on

-prefixindex:     Works on all pages with the given prefix

-ref:             Work on all pages linking to the given page

-subcat:          

-titles:          

-weblink:        Works on all pages with the given external link

'''

class GeneratorFactory():
	def __init__(self):
		self.site  = wikipedia.getSite()
		self.debug = wikipedia.Debug
		self.queryContinue = wikipedia.SysArgs.get('continue', '')
		try:	self.limit = int(wikipedia.SysArgs.get('limit', 10))
		except: self.limit = 10
		self.namespace = {
			'all':    [],
			'notalk': [str(n) for n in range(0, 16, 2) + range(100, 112, 2)],
			'talk':   [str(n) for n in range(1, 16, 2) + range(101, 112, 2)],
		}.get(wikipedia.SysArgs.get('namespaces'), wikipedia.SysArgs.get('namespaces', '').split('|'))

		self.pages = []
		self.gens = []
		self.namespaces = []
		if self.debug:
			print '<!--: spam'
			print 'Content-Type: text/html'
			print
			print '<body bgcolor="#f0f0f8"> -->'
			print '<div style="height:4em;"></div>'
			wikipedia.output('pagegenerators.py debug mode enabled')
			print 'Inputs arguments and cookies:<xmp>'
			for arg, value in wikipedia.SysArgs.iteritems():
				print "%s=%s"%(arg, value)
			print '</xmp>'

	def mwquery(self, query, nodeName, prefix=''):
		from xml.dom.minidom import parseString
		if not prefix:prefix = nodeName
		data = {
			'action':'query',
			'format':'xml',
		}
		if self.queryContinue:
			data[prefix+'continue'] = self.queryContinue.replace('_', ' ')
		if self.limit:		data[prefix+'limit'] = self.limit
		if self.namespace:	data[prefix+'namespace'] = '|'.join(self.namespace)
		data.update(query)

		if self.debug:
			print self.site.apipath(), '?',  '&'.join('%s=%s'%t for t in data.iteritems())
			print '<br/>'
			#print self.site.getUrl(self.site.apipath(), data=data)
		dom = parseString(self.site.getUrl(self.site.apipath(), data=data))
		if self.debug:
			print 'API equivalent request constructor: <br/><code>%s?%s</code></br>API input data:<br/>'%(self.site.apipath(),'&'.join(("%s=%s"%t for t in data.iteritems())))
			print data
			print '<br/>API output:<br/>'
			#for node in dom.documentElement.getElementsByTagName(nodeName):wikipedia.output(node.toxml())
			wikipedia.output(dom.toxml().replace('>', '>\n'))
			#print '"', self.site.getUrl(self.site.apipath(), data=data), '"'
		
		for node in dom.documentElement.getElementsByTagName(nodeName):
			title = node.getAttribute('title')
			if node.getAttribute('ns') == "0":
				self.pages.append(title)
			else: # XXX, change the namespace name to enwiki
				self.pages.append(wikipedia.namespaces[int(node.getAttribute('ns'))]+title[title.index(':'):])
		#XXX probably not the right way to do thing...
		qcontinue = dom.documentElement.getElementsByTagName('query-continue')
		if qcontinue:
			wikipedia.QueryContinue = "&%scontinue=%s"%('',qcontinue[0].firstChild.getAttribute(prefix+'continue').replace(' ', '_'),)
		return self.getCombinedGenerator()

	def handleArg(self, arg):
		gen = None
		site = self.site
		if arg.startswith(('-family:', '-lang:', '-dbname:')):
			# Handle inside wikipedia.py
			pass
		elif arg.startswith('-text'):
			#reserved
			pass
		elif arg.startswith('-continue'):
			pass
		elif arg.startswith('-wpTextbox1:'):
			page = wikipedia.Page(self.site, 'Special:Textbox1')
			page._contents = arg[12:]
		elif arg.startswith('-title:'):
			# Reserved for pages could be submitting to the script
			# and it will use that as input
			pass
		elif arg.startswith('-limit:'):
			self.limit = int(arg[7:])
			pass
		elif arg.startswith('-namespaces:'):
			pass
		elif arg.startswith('-namespace:'):
			# pywikipedia compatible?
			self.namespace += arg[11:].split('|')
		elif arg == '-help':
			wikipedia.showHelp()
			# Very hackist way of killing further output
			def dummy(*arg):pass
			wikipedia.showHelp = dummy
			return iter([])

		# ------------------------------------------------------
		# Should be separated out so order doesn't matter, i.e. -limit: after the page list
		# ------------------------------------------------------
		#elif arg == '-page:':
		#	return True
		elif arg.startswith(('-page:', '-pages:', '-titles:')):
			gen = iter((wikipedia.Page(site, page) for page in arg[arg.index(':')+1:].split('|') if page))
		# API allows:
		# 'links', 'images', 'templates', 'categories', 'allimages', 'allpages', 'alllinks', 'allcategories', 'backlinks', 'categorymembers', 'embeddedin', 'imageusage', 'search', 'watchlist', 'exturlusage', 'random'
		elif arg.startswith('-contribs:'):
			gen = self.mwquery({'list':'usercontribs',   'ucuser':arg[10:]}, 'item', prefix='uc')
		elif arg.startswith('-templates:'):
			gen = self.mwquery({'prop':'templates',      'titles':arg[11:]}, 'tl')
		elif arg.startswith('-cat:'):
			gen = self.mwquery({'list':'categorymembers','cmtitle':arg[5:] if ':' in arg[5:] else 'Category:'+arg[5:]}, 'cm')
		elif arg.startswith('-links:'):
			gen = self.mwquery({'prop':'links',          'titles':arg[7:]}, 'pl')
		elif arg.startswith('-new'):
			if arg[:5].isdigit():
				self.limit = int(arg[5:])
			gen = self.mwquery({
				'list': 'recentchanges',
				'rctype': 'new',
				'rcprop': '|'.join(['ids','title','timestamp','sizes','user','comment']),
				'rcshow': '|'.join(['!bot','!redirect']),
			}, 'rc', prefix='rc')
		elif arg.startswith('-random'):
			gen = self.mwquery({'list':'random', 'rnlimit':arg[8:] or 1}, 'page', prefix='rn')
		elif arg.startswith(('-ref:', '-backlinks:')):
			gen = self.mwquery({'list':'backlinks', 'bltitle':arg[arg.find(':')+1:]}, 'bl')
		elif arg.startswith('-prefixindex:'):
			# API seems to be broken
			gen = self.mwquery({'list':'allpages',       'apprefix':arg[13:]}, 'p', prefix='ap')
		elif arg.startswith('-subcat:'):
			pass
		elif arg.startswith(('-transcludes:', '-embeddedin:')):
			gen = self.mwquery({'list':'embeddedin',   'eititle':arg[arg.find(':')+1:]}, 'ei', prefix='ei')
		elif arg.startswith('-weblink:'):
			gen = self.mwquery({'list':'exturlusage',    'euquery':arg[9:]}, 'eu')
		elif arg.startswith('-watchlist'):
			gen = self.mwquery({
				'list': 'watchlistraw',
				'wrowner': wikipedia.SysArgs.get('username', arg[11:]),
				'wrtoken': wikipedia.SysArgs.get('wltoken', '')
#				'wrprop': '|'.join(['ids','title','timestamp','sizes','user','comment']),
			}, 'wr', prefix='wr')
		# custom for [[WP:FAC]]
		elif arg.startswith('-headlinks:'):
			p = wikipedia.Page(site, arg[11:])
			gen = iter((wikipedia.Page(p.site(), m.group('page')) for m in re.finditer(r'class="mw-headline"[^<>]*><a href="[^"]*?/wiki/(?P<page>[^"]*)"[^<>]*>', site.getUrl('/wiki/%s' % p.urlname() ))))
		elif arg.startswith('-boldlinks:'):
			# Does not quite work right yet, need to filter duplicated and namespaces
			p = wikipedia.Page(site, arg[11:])
			# FIXME Support namespaces
			gen = DuplicateFilterPageGenerator(NamespaceFilterPageGenerator(
					iter(wikipedia.Page(p.site(), m.group('page')) for m in re.finditer(r'(<b>)?<a href="[^"]*?/wiki/[^"]*" title="(?P<page>[^"]*)">(?(1)|<b>)', site.getUrl('/wiki/%s' % p.urlname())) ),
					tuple(int(s) for s in self.namespace if s.isdigit()) or (0,)
				  ))

		# Parse a URL for pages
		# WARNING:  This module should be used with caution as identifiable 
		# will be logged by the server
		elif arg.startswith('-file:http://'):
			# FIXME add more patterns
			for m in re.findall(r' title="(([^"]+))"', urllib.urlopen( arg[6:] ).read()):
				if m[1] not in self.pages:
					self.pages.append(m[1])
		elif arg.startswith('-file-random:') and './' not in arg and not arg[13:].startswith('/'):
			data = ''
			try:
				import random
				path = wikipedia.datafilepath('../', arg[13:])
				size = wikipedia.os.path.getsize(path)
				f = open(path)
				f.seek(int(random.uniform(0, max(0, size-256))))
				data = f.read(1024)
				start = data.index('[[')
				end   = data.index(']]', start)
				self.pages.append(data[start+2:end])
			except Exception, e:
				print "%r\nFile: %r\n----"%(e,path, )
				print data

				
		else:
			if self.debug:
				wikipedia.output('\nDEBUG: pagegenerator unhandled arg : %s'%arg)
			return False


		if self.debug:
			wikipedia.output('\nDEBUG: argument: %r; self.namespace=%r; self.pages = %r'%(arg, self.namespace, self.pages,))
		
		#if self.pages != []:
		#	#FIXME should be move with the -page: statement
		#	#return iter((wikipedia.Page(site, page) for page in self.pages))
		if gen:
			self.gens.append(gen)
			return self.getCombinedGenerator()
		else:
			return iter([])
			#return False # this probably breaks alot of things...

	def getCombinedGenerator(self, gen = None):
		if gen:
			self.gens.insert(0, gen)
		if self.gens:
			if len(self.gens) == 1:
				return self.gens[0]
			else:
				return CombinedPageGenerator(self.gens)
		elif self.pages:
			return iter((wikipedia.Page(self.site, page) for page in self.pages))
		else:
			return False



def CombinedPageGenerator(generators):
    for generator in generators:
		for page in generator:
			yield page

def DuplicateFilterPageGenerator(generator):
	seenPages = dict()
	for page in generator:
		_page = u"%s:%s:%s" % (page._site.family.name, page._site.lang, page._title)
		if _page not in seenPages:
			seenPages[_page] = True
			yield page

def NamespaceFilterPageGenerator(generator, namespaces, site = None):
	# TODO convert namespace string into numbers
	for page in generator:
		if page.namespace() in namespaces:
			yield page
def PreloadingGenerator(generator, pageNumber=60):
	return generator
def RedirectFilterPageGenerator(generator):
	return generator
	## Be careful using this with -page: as it will discard redirects
	#for page in generator:
	#	if not page.isRedirectPage():
	#		yield page
