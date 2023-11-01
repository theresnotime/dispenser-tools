#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
This is a quick hack for generating HTML diff and form pages python using 
pywiki.  This is useful, if you perfer to submit changes manually or like 
looking at the MediaWiki differ over the python one.

How to use:

import wikipedia, htmlput
page = wikipedia.Page(wikipedia.getSite(), 'Left 4 Dead')
s = page.get().replace('Zombie', 'Vampire')
htmlput.put(page, s, comment="They're vampires")

"""
import wikipedia, difflib, webbrowser, os

# Configuration
# Place to store the diff files
diffDir = "../temp/diffs/"
# Set to wpDiff or wpPreview to load the MediaWiki's wikidiff
autosubmit = None #"wpDiff"

htmlHead= """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" dir="ltr">
<head>
  <title>%(title)s</title>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<style type="text/css">%(styles)s
</style>
</head>

<body class="mediawiki ltr">
"""

htmlFoot = """
</body>
</html>
"""

_styles = """
body {
	font-family:Arial, sans-serif;
	font-size:92%;
}
/*
 * Diff table support
 */
table.diff{background:white; border-spacing:4px; margin-top:2em; table-layout:fixed; width:98%;}
table.diff .diff_next { width:0; visibility:hidden /*hack*/; } 
table.diff col.diff-marker { width:2%; }
table.diff col.diff-content { width:48%; }
table.diff td{ font-size:85%; padding:0; vertical-align:top; }
table.diff td.diff-marker{text-align:right; }
table.diff td.diff-context{background:#eee; }
table.diff td.diff-addline{background:#cfc; }
table.diff td.diff-deleteline{background:#ffa; }
table.diff tbody tr:last-child td {border-bottom:16px solid white;}
.diff_chg, .diff_sub, .diff_add{color:red; font-weight:bold; text-decoration:none; white-space:pre-wrap; }

table.diff td div { word-wrap:break-word; overflow:auto; }
"""
_table_template = '''<table class="diff" id="difflib_chg_%(prefix)s_top">
<col class="diff_next" /><col class="diff-marker" /><col class="diff-content" />
<col class="diff_next" /><col class="diff-marker" /><col class="diff-content" />
%(header_row)s
<tbody>
%(data_rows)s
</tbody>
</table>'''

class HtmlDiff(difflib.HtmlDiff):
	_styles = _styles
	_table_template = _table_template
	def _format_line(self,side,flag,linenum,text):
		try:
			linenum = '%d' % linenum
			id = ' id="%s%s"' % (self._prefix[side],linenum)
		except TypeError:
			# handle blank lines where linenum is '>' or ''
			id = ''
		# replace those things that would get confused with HTML symbols
		text=text.replace("&","&amp;").replace(">","&gt;").replace("<","&lt;")
		return '<td class="diff-marker"%s>%s</td><td class="%s"><div>%s</div></td>' % (id, linenum, 
		((side and 'diff-addline' or 'diff-deleteline') if flag else 'diff-context') if linenum else '', text)



def escape(s):
	s = s.replace("&", "&amp;") # Must be first
	s = s.replace("<", "&lt;")
	s = s.replace(">", "&gt;")
	s = s.replace('"', '&quot;')
	return s

def put(page, newtext, comment=None, watchArticle=None, minorEdit=False, force=False):
	old = page.get() # cached
	def winfilename(s):
		invalidChars = '\/:*?"<>|'
		for c in invalidChars:
			s = s.replace(c, '~')
		return s

	filename = 	wikipedia.config.datafilepath(diffDir, winfilename(page.title())+".html")
	file = open(filename, 'w')
	# needed?
	file.truncate(0) 
	file.seek(0)
	file.write(htmlHead % dict(
		title = page.title(),
		styles = _styles
	))
	if autosubmit:
		file.write('<p>Preparing diff, this page will auto submit with JavaScript.</p>')
		file.write('<img src="http://toolserver.org/~dispenser/resources/loadbar.gif" alt="loading..." width="200" height="19" />')
		file.write('<p></p>')
	if True:
		# Show python diff, sometimes better
		file.write( 
			HtmlDiff().make_table(old.split('\n'), newtext.split('\n'), fromdesc="Current revision", todesc="Your text", context=True, numlines=1).encode('utf-8')
			)
	if True:
		if not comment:
			comment = "Too many secrets"
		site = page.site()
		print "%r%r%r%r%r"% (site.protocol(), site.hostname(), site.path(), page.urlname(), 'submit')
		file.write('<form id="editform" name="editform" method="post" action="%s://%s%s?title=%s&amp;action=%s" enctype="multipart/form-data">' % (site.protocol(), site.hostname(), site.path(), page.urlname(), 'submit'))
		file.write('<input type="hidden" name="wpAntispam" value="" />')
		file.write('<input type="hidden" value="" name="wpSection" />')
		file.write('<input type="hidden" value="%s" name="wpStarttime" />' % page._startTime or time.strftime('%Y%m%d%H%M%S', time.gmtime()))
		file.write('<input type="hidden" value="%s" name="wpEdittime" />' % page._editTime or time.strftime('%Y%m%d%H%M%S', time.gmtime()))
		file.write('<textarea tabindex="1" name="wpTextbox1" id="wpTextbox1" rows="25" cols="80" style="width:100%">')
		file.write(escape(newtext).encode('utf-8'))
		file.write('</textarea>')
		# IE8 XSS filter corrupts sent text
		file.write('<div class="editOptions">')
		file.write('<label for="wpSummary">Edit summary:</label>')
		file.write("<input tabindex='2' type='text' value=\"%s\" name='wpSummary' id='wpSummary' maxlength='200' size='60' />" % comment.encode('utf-8'))
		file.write('<input name="wpAutoSummary" type="hidden" value="d41d8cd98f00b204e9800998ecf8427e" /><br />')	# blank summary check
		file.write('<input name="wpMinoredit" value="1"%s tabindex="3" accesskey="i" id="wpMinoredit" type="checkbox" />&nbsp;<label for="wpMinoredit" title="Mark this as a minor edit [alt-shift-i]" accesskey="i">This is a minor edit</label>' % '')
		file.write('<input name="wpWatchthis" value="1"%s tabindex="4" accesskey="w" id="wpWatchthis" type="checkbox" />&nbsp;<label for="wpWatchthis" title="Add this page to your watchlist [alt-shift-w]" accesskey="w">Watch this page</label>' % '')

		file.write('<div class="editButtons">')
		file.write(' <input id="wpSave" name="wpSave" type="submit" tabindex="5" value="Save page" disabled="disabled" />')
		file.write(' <input id="wpPreview" name="wpPreview" type="submit" tabindex="6" value="Show preview" accesskey="p" />')
		file.write(' <input id="wpDiff" name="wpDiff" type="submit" tabindex="7" value="Show changes" accesskey="v" />')
		file.write('<span class="editHelp"><a href="%s://%s%s" title="%s" id="mw-editform-cancel">Cancel</a></span>' % (site.protocol(),  site.hostname(), escape(site.nice_get_address(page.urlname())), escape(page.title().encode('utf-8'))))
		file.write('</div>')
		file.write('<input type="hidden" value="+\\" name="wpEditToken" />')
		file.write('</div></form>')
	if autosubmit:
		# Autoclick the diff button
		file.write('<script type="text/javascript">document.getElementById("%s").click()</script>\n' % autosubmit)

	file.write(htmlFoot)
	file.close()

	if webbrowser:
		webbrowser.open(os.path.abspath(file.name))
	else:
		# print hyperlinks for terminals if they support it
		wikipedia.output("Click to open:  file://%s" %(file.name, ))
