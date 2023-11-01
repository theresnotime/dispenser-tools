#!/usr/bin/env python
# -*- coding: utf-8  -*-
import re, time
import wikipedia, pagegenerators
import cgitb; cgitb.enable(logdir='./tracebacks/')

## Text for translation ##
#
summary = {
	'en': u"""<p><a href="//en.wikipedia.org/wiki/Wikipedia:Alternative_text_for_images" title="Wikipedia:Alternative text for images" class="extiw">Alternative text</a> (alt text) is meant for readers who cannot see an image, such as blind readers and readers who use a text or mobile browser. It should summarize an image's purpose, and should not duplicate its caption. Every image should have alt text, except for <a href="//en.wikipedia.org/wiki/Wikipedia:Alternative_text_for_images#Purely_decorative_images" title="Wikipedia:Alternative text for images" class="extiw">purely decorative images</a>, which should instead have "<code>|alt=|link=</code>".</p>""",
}
# Message for each page
# Magic words: %(title)s %(url)s %(parseddate)s
lead = {
	'en': u"""
<p>The following table shows images and captions on the left, and alt text and captions on the right: the right column is what a visually impaired reader will hear. This table was computed from the copy of <a href="%(url)s" class="extiw">%(title)s</a> cached on %(parseddate)s.</p>""",
	'simple':u"""
<p>Alternative text (alt text) is suppose to tell the important features to a person who cannot see the image due to non-graphical or mobile browser or blindness.</p>
<p>The following table shows pictures on the left and the alternative text for the picture on the right which a blind person might hear.  This table was computed from the copy of <a href="%(url)s" class="extiw">%(title)s</a> cached on %(parseddate)s.</p>""",
}
# Heading for image column
ImageDesc = {
                'en': "Image and thumbnail",
                'de': "Bild und miniaturbild",
                'simple': "Pictures",
            }
# Heading for alt column
AltDesc =   {
                'en': "Text description",
                'de': "alttext",
                'simple': "Text for the blind",
            }



# Regular expression for getting images
ImageR = re.compile(r'''(?six)
# Video posters
<div\ class="thumb[^"]*">\s*
<div[^<>]*>\s*
<div[^<>]*>\s*
<div>(?P<poster><a\ href="/w[^"]*"\ [^<>]*><img[^<>]*\ alt="(?P<videoalt>[^"]*)"\ /></a>)</div>\s*
<div.*?</div>\s*
</div>\s*
(?P<videocaption><div[^<>]*>(?P<videomagnify>\s*<div\ class="magnify">.*?</div>|).*?)</div>\s*
</div>\s*
</div>\s*
|
# Regex for border, frame, thumbnail/thumb, ogg video
<div\ class="thumb[^"]*">\s*
<div[^<>]*>(?P<image><a\ href="/w[^"]*"[^<>]*><img\ alt="(?P<thumbalt>[^"]*)"\ [^<>]*class="thumbimage"[^<>]*/></a>)\s*
(?P<thumbcaption><div[^<>]*>(?P<thumbmagnify>\s*<div\ class="magnify">.*?</div>|).*?)</div>\s*
</div>\s*
</div>
|
# Inline images
<a\ href="[^"]*"[^<>]*?><img\b[^<>]*?\ alt="(?P<imagealt>[^"]*)"[^<>]*?\ width="(?P<imagewidth>[^"]*)"\ [^<>]*?/></a>(?!\s*<div\ class="thumbcaption">)
|
# decorative images
<img\b[^<>]*?\ alt="(?P<decalt>[^"]*)"\ [^<>]*?/>
''')
# Image notes
# 	thumb	 class="thumbimage" with class="magnify"
# 	frame	 class="thumbimage" without class="magnify"
# 	border	 class="thumbborder"	
# 	link=	Removes class="image" from <a>

def main():
	genFactory = pagegenerators.GeneratorFactory()
	site = wikipedia.getSite()
	page = wikipedia.Page(site, '')
	for arg in wikipedia.handleArgs():
		if arg.startswith('-page:'):
			page = wikipedia.Page(site, arg[6:])
			site = page.site()
		#elif arg.startswith('-show:'):
		## values: all, default, thumb, thumbnails, videos, mixed, linked, unlinked
		#
		else:
			if not genFactory.handleArg(arg):
				wikipedia.output('Parameter "%s" not understood' % arg)
	generator = genFactory.getCombinedGenerator() or iter([page])
	
	print wikipedia.translate(site, summary).encode('utf-8')

	for page in generator:
		if not page.title():continue
		site = page.site()
		try:
			# We get address from the 
			html = site.getUrl(site.nice_get_address(page.urlname())+"?useskin=monobook"+time.strftime('&nocache=%Y%m%d%H%M%S'))

			# Check to see if there's a history tab, if not then the page does not exist
			if not re.search(r'<li id="ca-history"[^<>]*><a.*?</a></li>', html):
				wikipedia.output("%s does not exist on %s"%(page.aslink(), page.site().sitename()))
				continue	
		
			# 
			articleTitle = re.search(r'<h1 id="firstHeading"[^<>]*>([^<>]*)</h1>', html)

			# Strip to body content
			html = html[html.index("<!-- start content -->"):html.index("<!-- end content -->")]
		except Exception, e:
			wikipedia.output('Error: %r'%e)
			continue

		# For debugging purposes print all comments
		for cmt in re.findall('<!--.*?-->', html, re.DOTALL):
			print( cmt )
		
		# Translation substitutions
		wgServer = '%s://%s'%(site.protocol(), site.hostname(),)
		m = re.search(r'<!-- Saved in parser cache [^<>]* timestamp ([0-9]{14}) -->', html)
		metadata = {
			'title':		page.title(),
			'server':		wgServer,
			'url':			wgServer+site.nice_get_address(page.urlname()),
			'parseddate':	m and time.strftime("%d %B %Y at %H:%M", time.strptime(m.group(1), "%Y%m%d%H%M%S")),
		}
		
		#
		print '<h3>%s</h3>'%(articleTitle and articleTitle.group(1) or page.title().encode('utf-8'))
		if site.language() not in ('en', 'simple', ):
			print '<div class="mw-warning">This tool is not available in your language at the moment &mdash; <a href="//en.wikipedia.org/wiki/User_talk:Dispenser">you can help translate it</a>, see the <a href="../sources/altviewer.py">source code</a> for strings.</div>'
		print (wikipedia.translate(site, lead)%metadata).encode('utf-8')
		print '<table class="wikitable alt-compare">'
		print '<tr><th>%s</th><th>%s</th></tr>'%(wikipedia.translate(site, ImageDesc), wikipedia.translate(site, AltDesc))
		
		#
		images = ImageR.finditer(html)
		for image in images:
			# Default alt notes 
			# If no alt or caption is specificed then default to the filename
			imagesrc = re.search(r'(?<= src=")[^"]*(?=")', image.group()).group()
			imagetitle = re.search(r'(?<= title=")[^"]*(?="[^<>]*><img alt)', image.group())
			
			if imagetitle is not None:
				defaultalt = imagetitle.group()
			else:
				defaultalt = re.sub(r'.*?/[0-9a-f]/[0-9a-f]{2}/(.*?)(/.*|$)', r'\1', imagesrc.replace('_', ' '))
			
			# TODO: better support for galleries, <del>math equation</del>
			if image.group('decalt') is not None:
				if image.group('decalt') == '' and not re.search(r' (?:height|width)="\d{3,}"', image.group()):
					# Exclude images less than 100 pixels
					continue
				elif "/skins-1.5/" in image.group():
					continue
				elif "/w/extensions/" in image.group():
					continue
				elif ' class="tex"' in image.group():
					# Exclude tex equation since they will at some point will have machine generated alt text
					continue

			print '<tr><td align="center"><div>%s</div></td><td align="center"><div>'%(image.group().replace('href="/', 'href="%s/'%wgServer),)
			print '<!--', defaultalt, '\n', image.groups(), ' -->'
			# Thumbnails and videos, if no caption is provided it will fall back to filenames
			if image.group('videoalt') is not None:
				cssclass = 'defaultalt' if image.group('videoalt') in (defaultalt, '',) else ''
				print re.sub(r'<img src="[^"]+" width="\d+" height="\d+" alt="([^"]*)" />(?=</button>)', r'\1', image.group().replace(image.group('poster'), "<div class='alttext %s'>%s</div>"%(cssclass, image.group('videoalt'))).replace(image.group('videomagnify'), ''))#.replace('="/', '="%s/'%wgServer)
			elif image.group('thumbalt') is not None:
				print '<!--', image.group('thumbalt'), ' -->'

				cssclass = 'defaultalt' if image.group('thumbalt') in (defaultalt, '',) else ''
				print image.group().replace(image.group('image'), "<div class='alttext %s'>%s</div>"%(cssclass, image.group('thumbalt'))).replace(image.group('thumbmagnify'), '')#.replace('="/', '="%s/'%wgServer)
			elif image.group('imagealt') is not None:
				cssclass = image.group('imagealt') == defaultalt and (('titlealt' if ' href="/wiki/%s"'%defaultalt.replace(' ', '_') in image.group() else 'captionalt') if imagetitle else 'defaultalt') or ''
				print '<div class="alttext %s" style="width:%spx;">%s</div>' % (cssclass, image.group('imagewidth'), image.group('imagealt') and '<span class="wrapper">%s</span>' % image.group('imagealt') or '')
			elif image.group('decalt') is not None:
				cssclass = 'defaultalt' if image.group('decalt')==defaultalt else 'nolink'
				print '<div class="alttext %s">%s%s</div>' % (cssclass, image.group('decalt'), '<div class="notice">(Large unlinked image)</div>' if re.search(r' (?:height|width)="\d{3,}"', image.group()) else '')
			else:
				raise
			print '</div></td></tr>'
		print '</table>'

if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
    try:
        wikipedia.startContent(form=True, head="""<style type="text/css">
table.alt-compare {
	margin-left:auto;
	margin-right:auto;
	max-width:800px;
	table-layout:fixed;
	width:80%;
}
div.alttext {
	border:none;
	min-height:2em;
	min-width:90px; /* reasonable width */
	padding:0.1em;
}

/* Classes for alt types */
div.alttext,
div.alttext.titlealt,
div.alttext .wrapper {
	background:#444;
	color:#fff;
}
div.alttext.captionalt,
div.alttext.captionalt .wrapper{
	background:#903;
	color:#fff;
}
div.alttext.defaultalt,
div.alttext.defaultalt .wrapper{
	background:#c03;
	color:#fff;
}
div.alttext.nolink {
	background:#dcb;
	color:black;
}
div.alttext.nolink .notice {
	font-size:x-small;
}
table.alt-compare td>div {
	overflow:auto;
	padding:1px;
}
table.alt-compare div.tright, table.alt-compare div.tleft, table.alt-compare div.tnone {
	float:none;
	border:none;
	margin:0.5em 0.1em;
}

/* give subtle hint which side it floats */
table.alt-compare div.tleft .thumbinner{
	border-left:#444 1px solid !important;
}
table.alt-compare div.tright .thumbinner{
	border-right:#444 1px solid !important;
}
</style>""")
        main()
    finally:
        wikipedia.endContent()
        wikipedia.stopme()
