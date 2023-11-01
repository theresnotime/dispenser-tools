# -*- coding: utf-8  -*-
"""
wc=WebCite(url)
wc.search()
	Returns list of status results, e.g.
	[{'id':...},{{'id':...}]


requestArchiving(url)
	Checks to see if the URL was already archived, if not 
	request archiving.
	Returns XXX if successful.
"""
import xml.sax, urllib
import time

#TODO add base62 de/encoding

class WebCiteHandler(xml.sax.handler.ContentHandler):
	def __init__(self):
		self.results = []
	def startElement(self, name, attrs):
		if name == "result":
			self.results.append({'status':attrs['status']})
		elif name in ('webcite_id', 'timestamp', 'original_url', 'webcite_url', 'webcite_raw_url',):
			self.element = name
		else:
			self.element = ''
	def endElement(self, name):
		pass
	def characters(self, chrs):
		if self.element:
			self.results[-1][self.element] = chrs

class WebCite:
	"""
		WebCite(url)
		search()
	"""
	def __init__(self, url, extra={}, proxies=None):
		self.url=url.encode('utf-8') if isinstance(url, unicode) else url
		self.data = {'client':'wikipedia-checklinks', 'url':self.url, 'returnxml':'true',}
		self.data.update(extra)
		self.proxies = proxies
	
	def search(self, date=None, id=None):
		qr = ''
		try:
			handler = WebCiteHandler()
			filehandler = self.query(date=date, id=id)
			# WebCite gives broken XML for errors
			#if '</error>' in qr:
			if filehandler.getcode() != 200:
				print "Bad response from WebCite (HTTP %d)" % filehandler.getcode()
				return []
			qr = filehandler.read()
			qr = qr.replace('&', '&amp;').replace('&amp;amp;', '&amp;')
			import StringIO
			xml.sax.parse(StringIO.StringIO(qr), handler)
			return handler.results
		except IOError as e: # webcite servers are down
			print 'Is WebCite up? %r' % (e, )
			return []
		except Exception as inst:
			print "<h3> Error in webcite module </h3>"
			print "<code><b>%s</b>: %s</code><br/>" % (type(inst), inst.args)
			print '%r'%self.url
			print '<xmp>', qr, '</xmp>'
			raise
	
	def query(self, date=None, refdoi=None, id=None):
		if date:	self.data['date']=date
		if refdoi:	self.data['refdoi']=refdoi
		if id:  	self.data['id']=id
		return urllib.urlopen("http://www.webcitation.org/query", urllib.urlencode(self.data), proxies=self.proxies)
	
	def archive(self, email):
		self.data['email']=email
		if any(s in self.url for s in  ('web.archive.org', 'webcitation.org', 'nytimes.com', 'wikimedia.org', 'ec.europa.eu', 'yahoo.com', 'google.com',)):
			print 'Blacklisted URL: %s' % self.url
			return ''
		time.sleep(5)
		return urllib.urlopen("http://www.webcitation.org/archive", urllib.urlencode(self.data), proxies=self.proxies).read()

def testsax(url, date):
	print '<xmp>'
	try:
		webcite = WebCite(url)
		results = webcite.search()
		if results == []:
			print 'Request archiving'
		print date
		# FIXME remove the need for dateutil
		import dateutil.parser
		reqtime = time.mktime(dateutil.parser.parse(date or 'today', fuzzy=True).timetuple())
		best = None
		for result in results:
			diff = reqtime - float(result['webcite_id'][:-6])
			if diff < 0:diff*=-2
			if (not best or diff < best[0]) and result['status']=='success':best = (diff, result)
			print diff, result
		print best

	finally:
		print '</xmp>'
debug=False
#TODO update and return the archive ID
def requestArchiving(url, data={}, proxies=None):
	webcite = WebCite(url, proxies=proxies)
	results = webcite.search()
	if [i for i in results if i['status']=='success'] == []:
		# Valid email address (XOR with 0x0F)
		ema = "".join((chr(ord(s)^7) for s in 'cntwbitbuGshhktbuqbu)hu`'))
		try:
			s = webcite.archive(ema)
			if '</error>' in s or debug:
				print '<xmp>'
				print s
				print '</xmp>'
			else:
				return True
		except urllib.socket.timeout:
			return False
		except urllib.socket.error, arg:
			raise


