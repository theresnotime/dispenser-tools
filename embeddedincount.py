#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
Provides a count of the number of transclusions of a page.

Parameters:
  db          - The name of the database.
                Examples: frwiki for the French Wikipedia, 
                          jawiktionary for Japanese Wiktionary
                Default: enwiki
  callback    - If specified, wraps the output into a given function call and changes Content-Type to application/json for script use.
  ns          - The assumed namespace of the page
                Default: 0
  title       - Title to search.

Examples:
  http://toolserver.org/~dispenser/cgi-bin/embeddedincount.py?title=Template:Stub
  http://toolserver.org/~dispenser/cgi-bin/embeddedincount.py?title=Stub&ns=10&callback=transclusionCount&db=enwikinews

Notes:
* The "What links here" page combines the results of both backlinks and embeddedin (transclusions).
* For a backlink count use backlinkscount.py tool.
* This tool does not support namespace localization, use English namespaces or the ns parameter instead.
* Source code is at http://toolserver.org/~dispenser/sources/embeddedincount.py
"""
# I, Dispenser, hereby release this program into the public domain
# November 2009
import oursql, os, cgi
import cgitb; cgitb.enable(logdir='tracebacks')

# FIXME use dynamic and localized namespaces
namespaces = {
	'Media':			-2,
	'Special':			-1,
	'':					0,
	'Talk':				1,
	'User':				2,
	'User_talk':		3,
	'Wikipedia':		4,
	'Wikipedia_talk':	5,
	'Image':			6,
	'Image_talk':		7,
	'Mediawiki':		8, # name fudged
	'Mediawiki_talk':	9, # name fudged
	'Template':			10,
	'Template_talk':	11,
	'Help':				12,
	'Help_talk':		13,
	'Category':			14,
	'Category_talk':	15,
	'Portal':                  100,
	'Portal_talk':             101,
	'Author':                  102,
	'Author_talk':             103,
	'Index':                   104,
	'Index_talk':              105,
	'Collection':              106,
	'Collection_talk':         107,
	'Book':                    108,
	'Book_talk':               109,
	'Wikisaurus':              110,
	'Wikisaurus_talk':         111,
	'Subject':                 112,
	'Subject_talk':            113,
	'Citations':               114,
	'Citations_talk':          115,
	'Sign_gloss':              116,
	'Sign_gloss_talk':         117,
	'Draft':                   118,
	'Draft_talk':              119,
	'Education_program':       446,
	'Education_program_talk':  447,
	'Timedtext':               710,
	'Timedtext_talk':          711,
	'Module':                  828,
	'Module_talk':             829,
	'Gadget':                 2300,
	'Gadget_talk':            2301,
	'Gadget_definition':      2302,
	'Gadget_definition_talk': 2301,
	'Topic':                  2600,
}
def main():
	form = cgi.FieldStorage(keep_blank_values=1)
	dbName   = form.getfirst('db', form.getfirst('dbname','enwiki'))
	ns       = form.getfirst('ns', '0')
	title    = form.getfirst('title', '').replace(' ', '_')
	callback = form.getfirst('callback')

	if title == '':
		print "Content-Type: text/plain"
		print __doc__
		return

	if not os.getenv("HTTP_USER_AGENT"):
		print 'Status: 419 No user agent'
		print 'Content-Type: text/plain; charset=utf-8'
		print
		print 'No user agent'
		print 'https://meta.wikimedia.org/wiki/User-Agent_policy'
		return

	if ':' in title:
		name, t = title.split(':', 1)
		ns = namespaces.get(name.capitalize().strip('_:'), ns)
		if ns != 0: title = t

	# Toolserver views hack
	if not dbName.endswith('_p'):
		dbName += '_p'

	conn = oursql.connect(
		db=dbName,
		host=dbName[:-2] + '.web.db.svc.eqiad.wmflabs',
		read_default_file="/home/dispenser/.my.cnf",
		charset=None,
		use_unicode=False
	)
	cursor = conn.cursor()
	# The redirect pages themselves aren't included if you combine these queries
	count = 0
	cursor.execute("""
/* embeddedincount LIMIT:60 NM */
SELECT COUNT(*)
FROM templatelinks
WHERE tl_namespace=? AND tl_title=?
""", (ns, title))
	count += cursor.fetchall()[0][0]
	conn.close()

	if callback is not None: # getfirst treats &callback=& as None anyway
		callback = ''.join(c for c in callback if (c.isalnum() or c=='.' or c=='_'))
		print 'Content-Type: text/javascript; charset=utf-8'
		print
		print '%s(%d)'%(callback, count)
	else:
		print 'Content-Type: text/plain; charset=utf-8'
		print
		print count
if __name__ == "__main__":
	try:
		main()
	except oursql.Error as (errno, strerror, extra):
		# FIXME this should be machine readable
		print 'Status: 500 SQL error'
		print 'Content-Type: text/plain; charset=utf-8'
		print
		print (errno, strerror)

