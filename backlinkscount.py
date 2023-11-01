#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
Provides a count of the number of backlinks to a page.
                                                                               
Parameters:
  ns          - The assumed namespace of the page (default: 0)
  title       - The page title to look up
  db          - The name of the database (default: enwiki)
                Examples: frwiki for the French Wikipedia, 
                          jawiktionary for Japanese Wiktionary
  callback    - If specified, wraps the output into a given function call and 
                changes Content-Type to text/javascript for script use.
  filter      - Where to count the links (all, redirects, nonredirects):
                nonredirect - count pages directly linking
                redirect    - count pages linking to the redirects
                all         - count both (default)
  from_namespaces - The namespaces to count in. (default: all)
                    Example: 0|1 will count links from articles and talk pages
                    Namespace list at http://enwp.org/WP:NS

Examples:
  http://dispenser.info.tm/~dispenser/cgi-bin/backlinkscount.py?title=User:Jimbo%20Wales
  http://dispenser.info.tm/~dispenser/cgi-bin/backlinkscount.py?title=Jimbo_Wales&ns=2&callback=bragging_rights&filter=nonredirects&db=enwiki

Notes:
* Prior to 8 April 2018, &filterredir= returned the opposite of what the 
  documentation indicated.  This now raises an error.  Use &filter= instead.
* The "What links here" page combines the results of both backlinks and embeddedin (transclusions).
* For transclusions count use embeddedincount.py tool.
* This tool does not support namespace localization, use English namespaces or the ns parameter instead.
* Source code is at http://dispenser.info.tm/~dispenser/sources/backlinkscount.py

Monthly dump of backlinks:
http://dispenser.info.tm/~dispenser/dumps/
"""
# I, Dispenser, hereby release this program into the public domain
# November 2009
import oursql, os, cgi
import cgitb; cgitb.enable(logdir='tracebacks')

blocked_user_agents = set(
#	'libcurl/7.54.0 r-curl/3.1 httr/1.3.1',
)
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

def getConn(dbname):
	if not dbname.endswith('_p'): dbname += '_p'
	return oursql.connect(db=dbname,
		host=dbname[:-2]+'.web.db.svc.eqiad.wmflabs',
		read_default_file="/home/dispenser/.my.cnf",
		charset=None,
		use_unicode=False
	) 

def TooManyRequest():
	print "Status: 429 Too Man Requests"
	print "Content-type: text/html"
	print 
	print "Due to abuse this tool has been temporarily disabled. <br/>"
	print 'A dump of English Wikipedia\'s backlinks is available at <a href="/~dispenser/dumps/article_backlinkcount_enwiki.sql.gz">http://toolserver.org/~dispenser/dumps/article_backlinkcount_enwiki.sql.gz</a>'

def main():
	form = cgi.FieldStorage(keep_blank_values=1)
	dbname   = form.getfirst('db', form.getfirst('dbname','enwiki'))
	ns       = form.getfirst('ns', '0')
	title    = form.getfirst('title', '').replace(' ', '_')
	callback = form.getfirst('callback')
	filterredir  = form.getfirst('filterredir', 'all') # Deprecated
	redir_filter = form.getfirst('filter', 'all')
	from_namespaces   = form.getfirst('from_namespaces', 'all')
	
	user_agent = os.getenv("HTTP_USER_AGENT", '')
	if len(user_agent) < 16 or user_agent in blocked_user_agents:
		print 'Status: 419 Bad user agent'
		print 'Content-Type: text/plain; charset=utf-8'
		print
		print 'User agent is too short or blocked, see '
		print 'https://meta.wikimedia.org/wiki/User-Agent_policy'
		return
		
	if not title.strip(':_ '): 
		print "Content-Type: text/plain"
		print 
		print __doc__
		return
	
	def malformed(varname):
	  	print 'Status: 400 Malformed input'
		print "Content-Type: text/plain"
		print 
		print 'Your input appears to be malformed (%s), please consult the documentation:' % varname
		print __doc__
	if filterredir not in ('', 'all'): malformed('filterredir'); return
	if redir_filter not in ('', 'all', 'redirects', 'nonredirects'): malformed('filter'); return
	if any(c for c in '\n[]{|}' if c in title): malformed('title'); return
	for key in form.keys():
		if key not in ('db', 'dbname', 'ns', 'title', 'callback', 'filterredir', 'filter', 'from_namespaces'):
			malformed(key)
			return
	
	if ':' in title:
		name, t = title.split(':', 1)
		n = namespaces.get(name.capitalize().strip('_:'), 0)
		if ns != 0:
			ns = n
			title = t
	
	# 
	from_ns_query = ''
	if from_namespaces not in ('', 'all'):
		from_ns_query = 'AND pl_from_namespace IN (%s)' % (', '.join(n for n in from_namespaces.split('|') if n.isdigit()),)

	count = 0
	with getConn(dbname) as cursor:
		# The redirect pages themselves aren't included if you combine these queries
		if redir_filter != 'redirects':
			cursor.execute("""/* backlinkscount LIMIT:60 */ SELECT COUNT(*) FROM pagelinks WHERE pl_namespace=? AND pl_title=? %s""" % from_ns_query, (ns, title))
			count += cursor.fetchall()[0][0]
		if redir_filter != 'nonredirects':
			cursor.execute("""
/* backlinkscount LIMIT:60 */
SELECT COUNT(*) FROM redirect
JOIN page      ON rd_from=page_id
JOIN pagelinks ON pl_namespace=page_namespace AND pl_title=page_title
WHERE rd_namespace=? AND rd_title=? %s
""" % from_ns_query, (ns, title))
			count += cursor.fetchall()[0][0]
	
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
		#TooManyRequest()
		main()
	except oursql.Error as (errno, strerror, extra):
		# FIXME this should be machine readable
		print 'Status: 500 SQL error'
		print 'Content-Type: text/plain; charset=utf-8'
		print
		print (errno, strerror)

