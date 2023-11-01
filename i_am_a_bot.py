#!/usr/bin/env python
# -*- coding: utf-8  -*-
import re, sys, oursql
import wikipedia
import time; startTime=time.time()

connections = {}
def getConn(wiki):
	if not wiki.endswith('_p'): wiki+='_p'
	if wiki not in connections:
		# WMF's databases varbinary so it'll always be return in UTF-8 byte string
		# charset Option for wiktionary
		connections[wiki] = oursql.connect(db=wiki, host=wiki.replace('_', '-')+'.userdb.toolserver.org', read_default_file='/home/dispenser/.my.cnf', charset=None, use_unicode=False)
	return connections[wiki]

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
	t = canonicalTitle(t, firstupper)
	# Workaround for titles with an escape char
	if firstupper:
		t = ur'[%s%s]%s' % (t[0].upper(), t[0].lower(), t[1:],)
	t = re.escape(t).replace('\\[', '[', 1).replace('\\]', ']', 1)
	return t.replace('\\ ', '[ _]+').replace('\\|', '|')


def main():
	site = wikipedia.getSite()

	cursor = getConn(site.dbName()).cursor()
	cursor.execute("CREATE TEMPORARY TABLE u_dispenser.wildpage (wp_id INT NOT NULL PRIMARY KEY, title VARBINARY(255) NOT NULL, watchers INT NOT NULL) ENGINE = MEMORY;")
	cursor.execute("""
INSERT INTO u_dispenser.wildpage (wp_id, title, watchers)
SELECT DISTINCT page.page_id, page.page_title, COUNT(*) AS watchers
FROM page AS page

JOIN page AS talk   ON page.page_title=talk.page_title
JOIN categorylinks  ON talk.page_id=cl_from

LEFT JOIN templatelinks ON tl_from=page.page_id AND tl_namespace=10 AND tl_title IN ("Disambiguation_needed")
LEFT JOIN watchlist     ON wl_namespace=page.page_namespace AND wl_title=page.page_title

WHERE talk.page_namespace=1
AND page.page_namespace=0
AND cl_to = "Articles_tagged_by_WildBot_(dab)"
AND tl_from IS NULL

GROUP BY page.page_id
HAVING watchers < 5

LIMIT 2;
""")
	print time.time()-startTime
	cursor.execute("""
/* List disambiguation links */
SELECT title, GROUP_CONCAT(pl_title SEPARATOR '|') AS dablink, watchers
FROM u_dispenser.wildpage

JOIN pagelinks ON pl_from=wp_id
JOIN page AS pl      ON pl.page_namespace=pl_namespace AND pl.page_title=pl_title
LEFT JOIN redirect   ON rd_from=pl.page_id
LEFT JOIN page AS rd ON rd.page_namespace=rd_namespace AND rd.page_title=rd_title
JOIN categorylinks   ON cl_from=IFNULL(rd.page_id, pl.page_id) AND cl_to="All_article_disambiguation_pages"

WHERE pl_namespace=0
/* check for circular link */
AND NOT EXISTS (SELECT 1
FROM pagelinks
JOIN page ON page_namespace=pl_namespace AND page_title=pl_title
WHERE pl_from=pl.page_id AND page_id=wp_id)
/* See is_ambiguous() in disambig.py from wildbot source code */
AND pl_title NOT LIKE "%_(disambiguation)"
GROUP BY pl_from;
""")

	print time.time()-startTime
	
	print '''<button onclick="window.open('/~dispenser/', 'savewin')">Open targeting window</button>'''
	
	for (title, dabpiped, watchers) in cursor:
		print "<h2>%s</h2>"%title.replace('_', ' ')
		page = wikipedia.Page(site, title)
		dabpiped = canonicalTitle(dabpiped)
		text = page.get()
		text = re.sub(
			r'\[\[(%s)[|]?((?<=\|)[^=]*?|)\]\]'%(wikilinkregex(dabpiped),),
			time.strftime(r'\g<0>{{dn|date=%B %Y|bot={{subst:REVISIONUSER}}}}'),
			text
		)
		wikipedia.showDiff(page.get(), text)
		if text != page.get():
			page.put(text, comment="", minorEdit=False)


if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=True, head="""<script type="text/javascript">
addOnloadHook(function(){
	var forms = document.forms;
	for(var i=0; i<forms.length; i++){
		var form=forms[i];
		form.target="savewin";
	}
});
</script>""")
		main()
	finally:
		wikipedia.endContent()
		wikipedia.stopme()
