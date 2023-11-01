#!/usr/bin/env python
# -*- coding: utf-8  -*-
'''
webchecklinks.py
 A web wrapper around the checklinks library
 (c) Dispenser, 2007-2008
'''
import cgi, sys, time
import checklink, wikipedia

def printu(ustr):
	print ustr.encode('utf-8') if isinstance(ustr, unicode) else ustr
	
def printFile(name, arg1="$1"):
	with open('./text/%s.html' % name ) as f:
		print f.read().replace('$1', arg1.encode('utf-8'))

def printEntry(self, page, url, refId, context, status, reason, redirect, rank, comment):
	#printu(u'%s %s - %s' % (status, reason, wikilink))
	classes = 'dead-%s'%rank
	if url.encode('utf-8')+'\n' in open('/home/dispenser/webcite_requests.txt','r'):
		classes += ' webcite'
	if redirect:
		classes += ' redirect'
	printu('<tr class="%s"><td>%s</td><td>%s</td><td><abbr title="%s">%s</abbr></td><td>%s</td></tr>' % (classes, refId or '', context.replace('[[', '[&#91;'), reason, status, rank and (comment or reason) or ''))

	# flush to user
	sys.stdout.flush()
def html(string, data=[]):
	printu(string%tuple(wikipedia.escape(s) if isinstance(s, (bytes,str,unicode)) else s for s in data))
	
def textbox(name, value, label = None, attrib=''):
	if label == None:
		label = '%s: ' % name.capitalize()
	html(u'<label for="%s">%s</label><input type="text" name="%s" value="%s" id="%s"'+attrib+' />', (name, label, name, value, name,))

def checkbox(name, checked, label = None, attr=''):
	if checked:
		attr += ' checked="checked"'
	html(u'<input type="checkbox" name="%s" id="%s"'+attr+' /><label for="%s">%s</label>', (name, name, name, label or name.capitalize(),))

def main():
	wikipedia.logtime("Initialized")
	form = cgi.FieldStorage()
	use_cache = form.getfirst('cache')
	htmlmode  = form.getfirst('html', 'off')!='off'
	checklink.DEBUG	 = form.getfirst('debug', 'off')!='off'
	checklink.SOURCE = form.getfirst('source', 'off')!='off'
	checklink.config.max_external_links	= int(form.getfirst('threads',   30))
	checklink.config.defaulttimeout 	= int(form.getfirst('timeout',   30))
	checklink.config.httpDebug      	= int(form.getfirst('httpDebug',  0))
	checklink.config.useGET				= form.getfirst('alwaysUseGet', 'off')!='off'
	checklink.config.threaded           = form.getfirst('nothread', 'off')=='off'
	site = wikipedia.getSite()
	page = wikipedia.Page(site, form.getfirst('page', wikipedia.os.getenv("PATH_INFO", '/')[1:].replace('wikipedia:en:','') ))
	
	wikipedia.startContent(u'Checklinks: %s' % page.sectionFreeTitle(), form=False, head='''<script src="/~dispenser/resources/checklinks.js" type="text/javascript"></script>''')
	html(u'<form action="webchecklinks.py" style="text-align:center;" onsubmit="hideViewer()">')
	textbox('page', page.title(allowInterwiki=True), '', ' size="40" onchange="fixTitle(this)" accesskey="f" ')
	if checklink.DEBUG:
		print '<br/>'
		textbox('httpDebug', checklink.config.httpDebug, 'HTTP debug level: ', ' size="3"')
		textbox('threads',   checklink.config.max_external_links, attrib=' size="2"')
		textbox('timeout',   checklink.config.defaulttimeout, attrib=' size="3"')
		print '<br/>'
		print 'Cache: <select name="cache">%s</select>'%''.join(['<option%s>%s</option>'%(' selected="selected"' if use_cache==opt else '', opt or 'default') for opt in ('yes', None, 'no')])
		checkbox('alwaysUseGet', checklink.config.useGET, 'Always download')
		checkbox('debug',    checklink.DEBUG, 'Debug')
		checkbox('nothread', not checklink.config.threaded, 'Disable threading')
		checkbox('html',     htmlmode, 'Use HTML input')
		checkbox('source',   checklink.SOURCE, 'Print source')
	html(u'<input type="submit" value="Check page" />')
	print '</form>'
	wikipedia.logtime("Printed form")
	
	if use_cache != 'yes':
		try:
			page.get() # first call, handles errors!
		except wikipedia.NoPage as errmsg:
			html(u'NoPage error encountered <br/><code>%s</code>', (errmsg,))
			return
		except wikipedia.IsRedirectPage:
			target = wikipedia.Page(site, page._redirarg)
			html(u'<img src="//bits.wikimedia.org/skins-1.5/common/images/redirectltr.png" alt="#REDIRECT " /><a href="?page=%s" class="redirectText">%s</a>', (target.title(asUrl=True, allowInterwiki=True), target.title(),))
			return
	
	# Cache = yes, display cached version
	# Cache = Update, display cached version if the page hasn't been edited since [new default]
	# Cache = no,  Always rerun chechklinks [old default]
	cache_age = checklink.cacheAge(page)
	if cache_age == float("inf"):
		use_cache = 'no'
	if use_cache not in ('yes', 'no'):
		cachetime = time.gmtime(time.time() - cache_age)
		page.get() # get wpEdittime
		edittime = time.strptime(page.wpEdittime, "%Y%m%d%H%M%S")
		# Figure out mode
		use_cache = 'yes' if edittime < cachetime else 'no'
		wikipedia.logtime("Checked last edited time")
	
	printFile('checklinks-header')

	print '<p>'
	if cache_age < float('inf'):
		cachetime = time.gmtime(time.time() - cache_age)
		if use_cache == 'no':
			print time.strftime('Previously cached on  %d %B %Y at %H:%M', cachetime)
		else:
			print time.strftime('Displaying cached version from %d %B %Y at %H:%M.', cachetime)
			html(u' <a href="%s">Regenerate cache</a>.', ("?page=%s&cache=no"%page.title(asUrl=True, allowInterwiki=True),))
	print '</p>'

	print '<table id="linktable" class="">'
	html(u'<tr class="page"><th colspan="6"><a id="%s" href="//%s%s" title="%s" class="extiw">%s</a></th></tr>', (
		wikipedia.sectionencode(page.sectionFreeTitle()),
		page.site().hostname(),
		page.site().nice_get_address(page.urlname()),
		page.title(allowInterwiki=True),
		page.sectionFreeTitle(),
	))
	printFile('checklinks-tableHead')
	try:
		wikipedia.logtime("Heading done, start display of content")
		if use_cache != 'yes':
			if htmlmode:
				checklink.checkMWhtml(page, printEntry)
			else:
				checklink.checkMediaWikiPage(page, printEntry)
		else:
			f = open(checklink.ResultsCachePath%dict(
				sitename=page.site().sitename().encode('ascii'),
				title=page.title(underscore=True).replace('/', '|').encode('utf-8'),
			))
			for line in f:
				cells = line.split('\t')
				(url, refId, context, status, reason, redirect, junk1, junk2, rank, comment) = cells
				printEntry(None, page, url, refId, context, status, reason, redirect, rank, comment)
			f.close()
	except Exception as e:
		print '</table>'
		print 'Checklinks had an error <code>%s</code>' % (e,)
		if checklink.DEBUG: import cgitb; cgitb.enable(); raise
	else:
		print '</table>'
	wikipedia.logtime("Displayed page results")

if __name__ == "__main__":
	if wikipedia.SysArgs.get('redirect')=='no':
		print 'Content-Type: text/html; charset=utf-8'
		print
	else:
		wikipedia.handleUrlAndHeader(allowBots=(wikipedia.SysArgs.get('cache')=='yes'), defaultRedirect="/~dispenser/view/Checklinks")
	try:
		main()
	finally:
		wikipedia.endContent()
		wikipedia.stopme()


