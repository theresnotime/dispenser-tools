#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
Create test from:
http://en.wikipedia.org/w/index.php?title=Harry_Potter_and_the_Half-Blood_Prince_%28film%29&diff=next&oldid=359652716
"""
import re
import difflib
from xml.dom.minidom import parseString
import wikipedia, pagegenerators
import cgitb; cgitb.enable(logdir='tracebacks')
# FIXME [[Akira (manga)#Characters|Akira]] should select [[Akira (Akira)]] not [[Kei (Akira)]]

# FIXME properly implement localization
redirect_R = re.compile(r'^\s*#(REDIRECT:?|\w+).*?\s*\[\[(?P<link>[^{|}[\]]*?)(\|[^[\]]+)?\]\]', re.U)

link_r = re.compile(r"\[\[([^{|}[\]<\n>]+)\|(.+?)\]?\]\]('??\w*)")

resultsCache = {}
def getRedirects(site, page_title):
		if page_title in resultsCache:
			return resultsCache[page_title]
		if isinstance(page_title, unicode):
			page_title = page_title.encode('utf-8')
		results = {}
		unescaped_anchors = {}
		gblcontinue = None
		count = 0
		while True:
			data = {
				"format": "xml",
				"action": "query",
				"generator": "backlinks",
				"gblfilterredir": "redirects",
				"gblnamespace": "",
				"gbllimit": "50", # API limits to 50 full text pages
				"gbltitle": wikipedia.urllib.unquote(page_title),
				"prop": "revisions",
				"rvprop": "content",
			}
			if gblcontinue:
				data["gblcontinue"] = gblcontinue
				print '<!-- query continue: %s -->' % gblcontinue
			dom = parseString(site.getUrl(site.apipath(), data=data))
			#print '<xmp>', dom.toxml(), '</xmp>'
	
			for node in dom.documentElement.getElementsByTagName('page'):
				count += 1
				text = node.getElementsByTagName('rev')[0].firstChild.nodeValue
				rdtarget = redirect_R.search(text)
				if not rdtarget:print '<xmp>', text, '</xmp>' # for debugging
				title, sep, section = rdtarget.group('link').partition("#")
				
				key = wikipedia.sectionencode(section, 'utf-8')
				if key not in results:
					results[key] = []
				results[key].append(node.getAttribute('title'))
				if len(unescaped_anchors.get(key, key)) >= len(key):
					unescaped_anchors[key] = section.replace('_', ' ')

			gblcontinue = None
			for n in dom.documentElement.getElementsByTagName('backlinks'):
				gblcontinue = n.getAttribute('gblcontinue').encode('utf-8')

			if gblcontinue is None:
				break
			if count >= 250:
				wikipedia.output(u"Too many redirects to [[%s]], aborting" % page_title.decode('utf-8')) 
				break
		resultsCache[page_title] = results
		return results

f = open('/home/dispenser/public_html/temp/logs/simplify_links.log', 'a')
def simplifyAnchors(site, text, label=None):
	for linkmatch in link_r.finditer(text):
		title, sep, section = linkmatch.group(1).partition("#")
		if section and len(section) > 1: # Avoid processing #M glossaries 
			results = getRedirects(site, title)

			redirects = results.get(wikipedia.sectionencode(section, 'utf-8'), [])
			repl = ''
			score = 0
			for redirect in redirects:
				# XXX Redirect namespace the same as orginal link?
				if ':' in redirect and ':' not in linkmatch.group():
					continue
				
				#
				for test in (section, linkmatch.group(2)+linkmatch.group(3), linkmatch.group(),):

				#s = difflib.SequenceMatcher(lambda x: x=="Final Fantasy", linkmatch.group(), redirect)
				#if __name__ == '__main__':
			#	#	print '<pre>%4.3f\t%4d\t%6.6f\t%s</pre>'% ( s.ratio(),  len(redirect), s.ratio()/len(redirect), redirect.encode('utf-8'))
				#if s.quick_ratio() > score and s.ratio() > score:
				#	score = s.ratio()
				#	repl = linkmatch.group().replace(linkmatch.group(1), redirect)

				# try matching the link titlea
				# FIXME [[Sonic the Hedgehog (series)#Chaos Emeralds|Chaos Emerald]]
				# FIXME [[List of Mortal Kombat characters#Kabal|Kabal]]
				# FIXME [[List of Mortal Kombat characters#Smoke|Smoke]]
				# Improve? [[Wii Remote#Nunchuk|Nunchuk]]
					s = difflib.SequenceMatcher(None, test, redirect)
					if s.quick_ratio() > score and s.ratio() > score:
						if __name__ == '__main__':
							print '<pre>%4.3f\t%4d\t%6.6f\t%s [Title match]</pre>' % (s.ratio(), len(redirect), s.ratio()/len(redirect), redirect.encode('utf-8'))
						score = s.ratio()
						repl = linkmatch.group().replace(linkmatch.group(1), redirect)
				repl = re.sub(r"\[\[([^{|}[\]]+)\|\1(\w*)\]\]", r'[[\1]]\2', repl)
			if repl and score > 0:
				wikipedia.output("Using redirect %s for %s" % (repl, linkmatch.group(), ))
				if score < 0.8:
					f.write(("Using redirect %s for %s on %s (%4.3f)\n" % (repl, linkmatch.group(), wikipedia.MyPage and wikipedia.MyPage.title(asLink=True) or None, score,)).encode('utf-8'))
				if(len(redirects)>1 and score < 0.8):
					wikipedia.output("Other redirects: [["+ ']], [['.join(redirects) +"]]")
					f.write(("Other redirects [["+ ']], [['.join(redirects) +"]]\n").encode('utf-8'))
				text = text.replace(linkmatch.group(), repl)
	return text

def main():
	genFactory = pagegenerators.GeneratorFactory()
	for arg in wikipedia.handleArgs():
		if not genFactory.handleArg(arg):
			wikipedia.output('Parameter "%s" not understood' % arg)
	generator = genFactory.getCombinedGenerator() or []
	
	for page in generator:
		wikipedia.output('== %s ==' % page.title(asLink=True))
		try:
			text = page.get()
		except wikipedia.IsRedirectPage:
			text = wikipedia.Page(page.site(), page._redirarg).get(follow_redirects=True)
		
		new_text = simplifyAnchors(page.site(), text)
		if text != new_text:
			wikipedia.showDiff(text, new_text)


if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
    try:
        wikipedia.startContent(form=True)
        main()
    finally:
        wikipedia.endContent()
        wikipedia.stopme()
