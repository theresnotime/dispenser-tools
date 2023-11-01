#!/usr/bin/env python
# -*- coding: utf-8  -*-
import cgitb; cgitb.enable(logdir='./tracebacks/')
# (C) 2008 - Nicolas Dumazet ( en:User:NicDumZ )
#
# Distributed under the terms of the GPL

# TODO:
#  DONE: Add a force option to convert links with title to {{cite web}}
#  DONE: Fix issues with <Ref> and <REF>
#  NO: Maybe identify unbalanced <ref> tags
#  DONE:	Reject title with HTML tags (look for </...>)
#  DONE:	Add date parameter to {{dead link}}
#  NO:	Add |pages= to PDFs</s>
#  DONE:	override <!-- INSERT TITLE -->
#  Add the safari like alogrithm that shows only the differences betweeen titles
#   If multiplue titles on a page are the same, but from different links then skip title
#  DONE:	Add check for PDF so Micrsoft Word -... isn't a valid title
#  Add checks for DE: where the <h1> element need to partically match the title
#  Fix issues with title which are less than 6 characters
#  Fix language Icon issues (lang -> latin (la), assumed character encoding == language)
#  Parse DB dump and throw into a database of domain - publisher parings
#  Warn on |format = something publisher =
#
# If "IMMEDIATE RELEASE" or "PRESS RELEASE" is in the text use {{press release


######
# allow for more flexable domains like .mil, .gov, .edu, etc..
# avoid <ref>{{cite news|last=by |first=Written |url=
"""
Feature list:
    * Basic PDF support
    * Intelligent dead link detection and support for {{dead link}}
    * Language icon, based on Content-Language HTTP header
    * Create references section with <references /> if one does not exists
    * Adds titles to bare external links
    * Statistical based character encoding using chardet for non-standards compliant pages
    * Combining duplicate references
    * English, French, and German translations
    * Convert [1] inline links to <ref>
    * Citation template support
    * In page editing interactions -- never open a new tab to view a page
"""
from BeautifulSoup import UnicodeDammit
import re, urllib2, httplib, socket, codecs
import wikipedia, pagegenerators, noreferences
import subprocess, tempfile, os
import time
import StringIO, gzip
try:
	import commonfixes
except ImportError:
	commonfixes = None

# Web version of the bot does more as it has human review of its edits
msg = { 'fr':u'Correction des refs. mal formatées',
		'de':u'Korrektes Referenzformat',
		'hu':u'Robot: Forráshivatkozások kibővítése a hivatkozott oldal címével',
		'ko':u'봇: url만 있는 주석을 보강, (영문) 참조',
		'es':u'Formateando las referencias que no tuvieran titulos ',
		'en':u'Filling in %(refsupdate)s references'}

lang_template = { 'fr':u'{{%s}}',
				  'en':u'{{%s icon}}'}

deadLinkTag = {'fr':u'{{Lien mort}}',
			   'de':u'',
			   'hu':u'{{halott link}}',
			   'ko':u'{{죽은 바깥 고리}}',
			   'es':u'{{enlace roto2}}',
			   'en': time.strftime("{{dead link|date=%B %Y}}")
			   }

comment = {}

stopPage = {'en':u'User:DumZiBoT/EditThisPageToStopMe'}

soft404   = re.compile(ur'\D404(\D|\Z)|error|errdoc|Not.{0,3}Found|sitedown|eventlog', re.IGNORECASE)
dirIndex  = re.compile(ur'^\w+://[^/]+/((default|index)\.(asp|aspx|cgi|htm|html|phtml|mpx|mspx|php|shtml|var))?$', re.IGNORECASE)
domain	= re.compile(ur'^(\w+)://(?:www.|)([^/]+).*?')
#TODO check for domain equivalents
#Bad title source list:
# Radio-Locator: Radio Station Finder: Search Results
# Toa Com - Home
# This page has moved!
# WebCite query result
# NY Times Advertisement
# http://www.skatteetaten.no/upload/skd%20sm03_engelsk.pdf
# new ideas: http://labs.google.com/sets
# Access Denied
# Nothing found for  S Subspecies
# E! Online - Sorry, the page you requested is not available.
# 404&nbsp;-&nbsp;MuslimWays&nbsp;-&nbsp;MuslimWays
# The resource cannot be found.
# Yahoo! - 404 Not Found
# FOXSports.com - Page Not Found
# ESPN - Sitemap
# Error!
# N-Gage | Website Error
# Error Occurred While Processing Request
# Missing - New York Post
# The article you&#39;ve requested is no longer available.
# The United States Army Error Page
# Untitled Document 
# Document sans titre
# Search Results - THOMAS (Library of Congress)
# Article Not Found! 
# The article requested can not be found! Please refresh your browser or go back. 
# Main Page
# Variety.com - This article does not exist
# 403 Forbidden
# Apply Redirect
# Redirecting
# Redirection
# TODO: Adobe Photoshop PDF
globalbadtitles = r"""
# is
(^(test|help|JSTOR.[ ]*Accessing[ ]*JSTOR|(Home|Main)[ ]*Page)$
# starts with
    |\W*(
            register
            |registration
            |(sign|log)[ \-]*(in|on|up)
            |subscribe
            |(untitled|new)[ ]*(document|page|$)
			|my\b
			|your\b
			|404\b
			|redirect
			|connecting to
        ).*
# anywhere
    |.*(\b40[134]|page|file|story|article|resource).*(not?([ ]*(be|longer)?)?[ ]*(found|available|exist)|moved|forbidden)
	|.*search[ ]*results
# bad words
	|.*\b(error|cookie|advertisement|cart|checkout)[s]?\b
# ends with
    |.*(
            (?<!The )register
            |registration
            |(sign|log)[ \-]*(in|on|up)
            |subscribe
			|result[s]?
			|search
			|untitle[d]?
			|account[s]?
			|redirect
        )\W*$
)
"""
badtitles = { 'en':'',
              'fr': '.*(404|page|site).*en[ ]+travaux.*',
              'es': '.*sitio.*no[ ]+disponible.*'
            }
# FIXME <ref name=autogenerated1>[http://www.himalayanacademy.com/resources/lexicon/#Shaktism%20(Shakta). Hinduism's Online Lexicon<!-- Bot generated title -->]</ref> 
# anchor tag?...
linksInRef = re.compile(
	# bracketed URLs
	ur'<ref(?P<name>[^>]*)>\s*\[*(?P<url>(?:http|https|ftp)://(?:' +
	# unbracketed with()
	ur'[^\[\]\s<>"]+\([^\[\]\s<>"]+[^\[\]\s\.:;\\,<>\?"]+|'+
	# unbracketed without ()
	ur'[^\[\]\s<>"]+[^\[\]\s\)\.:;\\,<>\?"]+|[^\[\]\s<>"]+))[!?,.\s]*(?P<title>(?<= )[^]\n]*?(?=\]|<!--)|)(?P<bot><!-+ *Bot[- ]generated title *-+>(?=\])|)\]*\s*</ref>', re.S | re.I)
#'http://www.twoevils.org/files/wikipedia/404-links.txt.gz'
listof404pages = '404-links.txt'
useTemplates = False
overrideBotTitles = False
overrideSimpleTitles = False
refsupdate = 0


# Notes:
# page - Not good as it is used for some sort of body text
# Date are typically preceed by "Post", "Post by ... on "
mdClass = (
	# Byline?
	'post_credit',
	'by-line', 
	r'\S*by\S*line', 
	'articleHead', 

	# date?
	'dateposted',
	'post-timestamp', 
	r'\w+date',
	r'date\w+',
	'blogs-article-date',
	'timedate', # Yahoo AP news
	'updated',
	'pubtime',

	#  rescured
	'dat',
	'pdate',


	'subtitle', 
	'geo', 
	'dat', 
	'post_info',
	'credit',
	r'\S+lastupdate'
	'location', 
	'feed_details',
	'postinfo',


	# Agancy
	'serviceName',	# DNAindia.com?

	# Headline
	'headline',			# 1wrestling.com
	'storyheadline',	# niagara-gazette.com
	'inside-head', 		# usatoday.com, 
	'reportHeadLine',	# DNAindia.com
	'chptitle',			# cbo.gov
	'mainarttitle',		# members.forbes.com
	'heading1',			# economictimes.indiatimes.com
	
	# Headline + date/byline
	'page-title',		# animenewsnetwork.com

)
bylClass = (
	# Byline
	# TODO
	# Last resort look for "By UPPERCASE NAME"
	# Correct McSomething
	'storycredit',		# niagara-gazette.com
	'articleBy',		#variety.com
	'articleAuthorName',# globalresearch.ca
	'writer', 			# OhmyNews.com,
	'storybyline',		# money.cnn.com
	'writerName',		# DNAindia.com
	'b_author',			# drownedinsound.com
	'author',			# abc.net.au - Broadcast program
	'byl',				# news.bbc.co.uk - From Our Own Correspondent 
	'vitstorybyline',	# pe.com
	'byline_name',		# charleston.net
	'authorsource',		# pcmag.com
	'contributor',		# wired.com
	'f12px',			# greenocktelegraph.co.uk
	'articleAuthor',	# thestar.com
	'byLine',			# france24.com
	'byAuthor', 	# blogs.telegraph.co.uk
	'bylineR',			# pcmag.com
	'articleByline', 	# denverpost.com

# word "by ":	'bylineBy',			# pcmag.com

	# Generic
	'posted',			# paidcontent.org,
	'post',				# forargyll.com
	'name',				# time.com

	#Byline+date
	'byline',			# online.wsj.com, ign.com, time.com, washingtonpost.com
	'sb1',				# rediff.com
	'articleheaddate',	# bollywoodmantra.com
	'ft-story-header',	# ft.com
	'authorname',		# thinkprogress.org
	'byln',				# cleveland.com
	'node_by',			# next-gen.biz
	'readArticleTopRight', # palgn.com.au
	'editorName',		# pc.gamespy.com
	'mainartauthor',	# forbes.com/businesswire
	'post_subheader_left',	# techcrunch.com
	'bylineDiv',		# Politico.com
	'TIME',				# nintendods
	'Byline',			# lwn.net
	'StoryHeadlineDetails',	# marketwatch.com
	'cs',				# wired.com
	'postedBy',			# businessweek.com
)
pubClass = (
	# Publisher
	'publisher', 	#old
	'publication',	# old
	'srcline', # publisher, dispatch.com
)
dateClass = (
	# Date/time
	# TODO
	# Function should be able to handle the follow and pick the best
	# Dates should be formatted to the standard
	# And should ignore dates within +/- 1 week (Throw warning)
		# Posted: Friday November 4, 2005 2:47PM; Updated: Tuesday November 8, 2005 2:22PM
		# 11/23/2004 - Updated 12:56 PM ET
		# Posted 11/23/2004 11:28 PM 
		# Last Updated: 4:46PM BST 25 Sep 2008
	'Date',				# roadtransport.com
	'date', 			# 1wrestling.com, pcworld.com, time.com, news.bbc.co.uk
	'datestamp',	 	# USAToday.com
	'titledate',		# sports-central.org,
	'storydate',		# bizjournals.com
	'articleTimeStamp',	# icq.nba.com,
	'article_date_time',	# garoweonline.com
	'cnnTimeStamp',		# sportsillustrated.cnn.com
	'blogdatetext', 	# usmagazine.com
	'storytimestamp',	# money.cnn.com
	'story_lastupdate',	# post-gazette.com,
	'story_first_published', # post-gazette.com,
	'displayDate',		# DNAindia.com
	'cnnGryTmeStmp',	# edition.cnn.com
	'mainartdate',		# members.forbes.com
	'dateStamp',		# online.wsj.com
	'createdate',		# iesb.net
	'timestampHeader',	# reuters.com
	'newsdate', 		# out-law.com
	'date-header',		# igdmlgd.blogspot.com 
	'broadcast',		# abc.net.au - Broadcast program
	'issueDate',		# money.cnn.com/magazines/fortune
	'timestamp',		# eurogamer.net
	'story_dateline',	# businesswire.com
	'mainartdate',		# forbes.com/businesswire
	'vitstorydate', 	# pe.com
	'MBSubLine',		# sportingnews.com
	'post-calendar',	# kloover.com
	'cbstv_article_date_header', # cbs3.com
	'entry_date',		# blogs.computerworld.com
	'descr',			# sampablokuper.com
	'cnnGryTmeStmp',	# cnn.com
	'dateline',			# imf.org
	'articleProperty',	# support.microsoft.com
	'publish_date',		# itworld.com
	'lastupdated',		# cbc.ca
	'hui12',			# xinhuanet.com
	'headingnext',		# economictimes.indiatimes.com
	'text_article_date',	# computerandvideogames.com
	'datetag',			# macrumors.com
	'postmetadata', 	# mydigitallife.info
	'time',     		# play.tm
	'categoryTime',		# blogs.telegraph.co.uk
	'PublishDate',		# greenpeace.org


	# Site using id=
	'pubdate',			# charleston.net (id=)
	'date_time',		# wired.com (id=)
	
	'publishdate', 
	'ds',				# news.bbc.co.uk

	'lastUpdate',	# ESPNsoccernet 
	'moddate',		# modifed date, komotv.com
		
)
# This data should be generated from a database dump
DomainPublisherName = {
	'Guardian.co.uk':	'Guardian',
	'News.bbc.co.uk':	'BBC News',
	'Iht.com':			'International Herald Tribune',
	'Detnews.com':		'The Detroit News',
	'Query.nytimes.com':'New York Times',
	'Msnbc.msn.com':	'MSNBC', # msnbc.com - Publisher can't get it right
	'Youtube.com':		'YouTube.com',

}
storyHeader = (
	'storyheaderlarge', # politico.com
	'news_story_title',	# Bloomberg.com
	'text_article_headline',	# ComputerAndVideoGames.com
)

def printu(s):
	print s.encode('utf-8')

def getClassTextNodes(className, text, flags = None):
	list = []
	for m in re.finditer(r'<(?P<tag>\w+)[^<>]*?class\s*?=\s*?(?:["\'][^"\']*)?\b'+className+r'\b[^<>]*>(?P<contents>.*?(<(?P=tag)\b.+?</(?P=tag)>.*?)*)</(?P=tag)>', text, flags | re.DOTALL):
		list.append(m.group('contents').strip())
	return list

def compare(cmp, s, ignoreChr="[]{}\\|'!,.", ignoreWords=('.com', 'www.', 'the', '.org'), ignoreCase=True):
	if ignoreCase:
		cmp = cmp.lower()
		s = s.lower()

	for word in ignoreWords:
		cmp = cmp.replace(word, '')
		s = s.replace(word, '')
	
	for char in ignoreChr:
		cmp = cmp.replace(char, '')
		s = s.replace(char, '')
	
	return (cmp == s)

def cleanText(s):
	s = re.sub('\s+', ' ', s)
	s = re.sub(r'</?\w+[^<>]*?>', '', s).strip(', -\n\t')

	"""
	If title has more than 6 characters and has 70% of uppercase
	characters, capitalize() it
	"""
	if len(s) <= 6:
		return s
	nb_upper = 0
	nb_letter = 0
	for letter in s:
		if letter.isupper():
			nb_upper += 1
		if letter.isalpha():
			nb_letter += 1
		if letter.isdigit():
			return s
	if float(nb_upper)/(nb_letter or 1) > .70:
		s = s.title()
	return s

def iterLinkRefs(text, type="simple"):
	"""
	Yield RefLink objects from text
	
convert <ref>s in style:
     <ref>[url title (YYYY)].?</ref>
     <ref>[url title]</ref>
     <ref>[url]</ref> (w/o brackets)
     <ref>url</ref> (w/o brackets)
     <ref>[url title].? Retrieved on? YYYY-MM-DD.?</ref>
     <ref>LAST, FIRST. [?url]?</ref>
     <ref>LAST, FIRST. [url title]</ref>
     <ref>FIRST LAST. [?url]?</ref>
     <ref>FIRST LAST. [url title]</ref>
     <ref>[url title] (?YYYY)?.?</ref>
     <ref>LAST, FIRST (YYYY). [url title].?</ref>
     <ref>LAST, FIRST. [url title].? (?YYYY)?.?</ref>
     <ref>LAST, FIRST. [url title]. retrieved on? YYYY-MM-DD.?</ref>
     <ref>LAST, FIRST (YYYY). [url title]. retrieved on? YYYY-MM-DD.?</ref>        !2!
     <ref>LAST, FIRST. [url title]. retrieved on? Month DD, YYYY.?</ref>       !1! !2!
     <ref>LAST, FIRST (YYYY). [url title]. retrieved Month DD, YYYY.?</ref>    !1! !2!
     <ref>LAST, FIRST (YYYY). [url title]. retrieved on Month DD, YYYY.?</ref> !1! !2!
     <ref>LAST, FIRST MIDDLE. [url title].?</ref>
     <ref>LAST, FIRST MIDDLE (YYYY). [url title].?</ref>
     <ref><url></ref>
     <ref>LAST, FIRST. <url></ref>
     <ref>LAST, FIRST. "~~". <url></ref>
     <ref>LAST, FIRST. "~~". [url]</ref>
     <ref>[url title] (YYYY). retrieved on Month DD, YYYY.</ref>
  to Cite web format, respectively
  	"""
	for ref in re.finditer(r'<ref(?P<name>[^>]*)>\s*(?<content>.*?)\s</ref>'):
		c = ref.group('content')
		m = re.search(r'\[(?P<url>(?:http|https|ftp)://[^][<>"\s]+) (?P<title>[^\n])\]')
		pass
	"""
linksInRef = re.compile(
	# bracketed URLs
	ur'<ref(?P<name>[^>]*)>\s*\[*(?P<url>(?:http|https|ftp)://(?:' +
	# unbracketed with()
	ur'[^\[\]\s<>"]+\([^\[\]\s<>"]+[^\[\]\s\.:;\\,<>\?"]+|'+
	# unbracketed without ()
	ur'[^\[\]\s<>"]+[^\[\]\s\)\.:;\\,<>\?"]+|[^\[\]\s<>"]+))[!?,.\s]*(?P<title>(?<= )[^]\n]*?(?=\])|)\]*\s*</ref>', re.S | re.I)

   r"\[(.+?)\s([^\]]+?)\s\(\[{0,2}(\d{4})\]{0,2}\)\]\.?\s",
   r"\[([^\s]+?)\]",
   r"(http:\/\/[^\s]+?)",
   r"\[([^\s]+?)\s([^\]]+?)\][\.\,]?\s(retrieved|accessed|reached)\s(on\s)?\[{0,2}(\d{4}\-\d{1,2}\-\d{1,2})\]{0,2}\.?",
   r"(\w+)\,\s(\w+)\.\s\[?([^\s]+?)\]?\.?",
   r"(\w+)\,\s(\w+)\.\s\[([^\s]+?)\s([^\]]+?)\]\.?",
   r"(\w+)\s(\w+)\.\s\[?([^\s]+?)\]?\.?",
   r"(\w+)\s(\w+)\.\s\[?(http:\/\/.+?)\s(.+?)\]?\.?",
   r"\[(.+?)\s([^\]]+?)\]\.?\s\(?\[{0,2}(\d{4})\]{0,2}\)?\.?",
   r"(\w+)\,\s(\w+)\s\(\[{0,2}(\d{4})\]{0,2}\)\.\s\[([^\s]+?)\s([^\]]+?)\]\.?",
   r"(\w+)\,\s(\w+)\.\s\[([^\s]+?)\s([^\]]+?)\]\.?\s\(?\[{0,2}(\d{4})\]{0,2}\)?\.?",
   r"(\w+)\,\s(\w+)\.\s\[([^\s]+?)\s([^\]]+?)\][\.\,]?\s(retrieved|accessed|reached)\s(on\s)?\[{0,2}(\d{4}\-\d{1,2}\-\d{1,2})\]{0,2}\.?",
   r"(\w+)\,\s(\w+)\s\(\[{0,2}(\d{4})\]{0,2}\)\.\s\[([^\s]+?)\s([^\]]+?)\][\.\,]?\s(retrieved|accessed|reached)\s(on\s)?\[{0,2}(\d{4}\-\d{1,2}\-\d{1,2})\]{0,2}\.?",
   r"(\w+)\,\s(\w+)\.\s\[([^\s]+?)\s([^\]]+?)\][\.\,]?\sretrieved\s(on\s)?\[{0,2}(January|February|March|April|May|June|July|August|September|October|November|December)\s(\d{1,2})\]{0,2}\,?\s\[{0,2}(\d{4})\]{0,2}\.?",
   r"(\w+)\,\s(\w+)\s\((\d{4})\)\.\s\[([^\s]+?)\s([^\]]+?)\][\.\,]?\sretrieved\s\[{0,2}(January|February|March|April|May|June|July|August|September|October|November|December)\s(\d{1,2})\]{0,2}\,?\s\[{0,2}(\d{4})\]{0,2}\.?",
   r"(\w+)\,\s(\w+)\s\((\d{4})\)\.\s\[([^\s]+?)\s([^\]]+?)\][\.\,]?\sretrieved\son\s\[{0,2}(January|February|March|April|May|June|July|August|September|October|November|December)\s(\d{1,2})\]{0,2}\,?\s\[{0,2}(\d{4})\]{0,2}\.?",
   r"(\w+)\,\s(\w+\.?\s\w+)\.\s\[([^\s]+?)\s([^\]]+?)\]",
   r"(\w+)\,\s(\w+\.?\s\w+)\s\(\[{0,2}(\d{4})\]{0,2}\)\.\s\[([^\s]+?)\s([^\]]+?)\]",
   r"<(http:\/\/.+?)>",
   r"(\w+)\,\s(\w+)\.\s<(http:\/\/.+?)>",
   r"(\w+)\,\s(\w+)\.\s"(.+?)"\.?\s<(http:\/\/.+?)>",
   r"(\w+)\,\s(\w+)\.\s"(.+?)"\.?\s\[(http:\/\/.+?)\]",
   r"\[([^\s]+?)\s([^\]]+?)\]\s\(\[{0,2}(\d{4})\]{0,2}\)[\.\,]\sretrieved\s(on\s)?\[{0,2}(January|February|March|April|May|June|July|August|September|October|November|December)\s(\d{1,2})\]{0,2}\,\s\[{0,2}(\d{4})\]{0,2}\.?",

"""
	for match in linksInRef.finditer(new_text):
		yield match

class RefLink:
	def __init__(self, link, title = None, name=''):
		self.page = None
		self.refname = name
		self.link = link
		self.site = wikipedia.getSite()
		self.linkComment = wikipedia.translate(self.site, comment)
		self.url = re.sub(u'#.*', '', self.link)
		self.title = title

		# Interface wizardry
		self.contextLine = None

		# setup default values
		self.lang   = None
		self.publisher = None
		self.date   = None
		self.format = None
		self.byline = None
		self.author = None
		self.first  = None
		self.last   = None
		self.location = None
		self.page   = None
		self.doi	= None

	def setTitle(self, t):
		#convert html entities
		t = wikipedia.html2unicode(t)
		#reduce repeating -
		t = re.sub(r'-+', '-', t)
		#remove formatting, i.e long useless strings
		t = re.sub(r'[\.+\-=]{4,}', ' ', t)
		#remove \n and \r and Unicode spaces from titles
		t = re.sub(r'(?u)\s', ' ', t)
		t = re.sub(r'[\n\r\t]', ' ', t)
		#remove extra whitespaces
		#remove leading and trailing ./;/,/-/_/+/ /
		t = re.sub(r' +', ' ', t.strip('=.;,-+_ '))
		if t:
			self.title = t
		return t

	def fixTitle(self):
		self.title = re.sub(ur'(?iu)[\s[\]|:»\-(]+%s\W*$'%re.escape(self.publisher or ''), r'', self.title)
		self.title = re.sub(ur'(?iu)^\W*%s[\s[\]|:»\-)]+'%re.escape(self.publisher or ''), r'', self.title)

	def setPublisher(self, domain, hints = None):
		#TODO
		# should match X Y-Z with yz.x.com and z.y.x.com
		# should match subdomains "X" in x.y.com
		# partial matches "Education | guardian.co.uk " with Education.guardian.co.uk
		dividers = u'|:>»()'

		if not self.publisher:
			self.publisher=domain.capitalize()
		## HACK
		if self.publisher in DomainPublisherName:
			self.publisher = DomainPublisherName[self.publisher]
		
		parts = re.split(ur'(\s*['+dividers+r']+\s*|\s+-\s*|\s*-\s+|\s+from\s+)', wikipedia.html2unicode(hints or self.title))
		wikipedia.output('Publisher possibles %r'%(parts,))
		partsComparR = re.compile(ur'(?i)\.[a-z]{2,4}\.[a-z]{2}$|\.(net|org|com)|www\.|the|english|article|[\s[\]:;",./\\!`~<\-|()>]')
		for part in parts:
			# compare
			# \.(net|org|com)
			print 'publisher-compare: ', partsComparR.sub('', domain.lower()).encode('utf-8'), partsComparR.sub('', part.lower()).encode('utf-8'), partsComparR.sub('', domain.lower()) == partsComparR.sub('', part.lower()), 
			if partsComparR.sub('', domain.lower()) == partsComparR.sub('', part.lower()):
				self.publisher = cleanText(part.strip())
		self.fixTitle()

	def setDate(self, list):
		dayInMonth = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31) # unused
		monthlist = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"] # lists has .index()
		pMonth = r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December|jan|feb|mar|apr|may|june?|july?|aug|sept?|oct|nov|dec)"
		pDay   = r"(?P<day>0?[1-9]|[12]\d|3[01]) *(st|nd|rd|th)?"
		pDayG  = r"(?P<day>1?[3-9]|2\d|3[01]) *(st|nd|rd|th)?"
		pMon   = r"(?P<mon>0?[1-9]|1[012])"
		pYear  = r"(?P<year>19\d\d|20[0-2]\d)"
		pDow   = r"(?P<wday>mon|tues?|wed|thur|fri|sat|sun|thurs?|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
		# Last Updated: 4:46PM BST 25 Sep 2008
		# MM/DD/YY
		# mmmm DD,? YY
		dateformats = [
			# DD-mmmm-YYYY
			r'(?i)\b'+pDay+'[/\-.]'+pMonth+'[/\-.]'+pYear+r'\b',
			# Friday, 7 Nov. YYYY
			r'(?i)\b'+pDow+'[.,]? +'+pDay+' +'+pMonth+'[.]? +'+pYear+r'\b',
			# DD mmmm YYYY  (Should be more specific)
			r'(?i)\b'+pDay+' +'+pMonth+'[., ]+'+pYear+r'\b',
			# mmmmm DD, YYYY
			r'(?i)\b'+pMonth+'[. ]+'+pDay+'[., ]+'+pYear+r'\b',

			# Numerical format
			# YYYY/MM/DD
			r'(?i)\b(?<!\d)'+pYear+r'[/\-.]'+pDayG+r'[/\-.]'+pMon+r'\b',
			# YYYY/MM/DD
			r'(?i)\b(?<!\d)'+pYear+r'[/\-.]'+pMon+r'[/\-.]'+pDayG+r'\b',
			# MM./DD./YYYY
			r'(?i)\b(?<!\d)'+pMon+r'[/\-.]'+pDayG+r'[/\-.]'+pYear+r'\b',
			# DD/MM/YYYY
			r'(?i)\b(?<!\d)'+pDayG+r'[/\-.]'+pMon+r'[/\-.]'+pYear+r'\b',
			# MM/DD/YY
			
			#  YYYY-MM-DD
			r'(?i)\b(?<!\d)'+pYear+r'-'+pMon+r'-'+pDay+r'\b',
			# YYYYMMDDhhmmss
			r'(?i)\b(?<!\d)'+pYear+pMon+pDay+r'[01]\d[0-5]\d[0-5]\d\b',
		]
		
		goodDates = []
		for field in list[:]:
			for p in dateformats:
				matches= re.finditer(p, field)
				for m in matches:
					year = m.group('year')
					mday = m.group('day')
					try:	mon  = monthlist.index(m.group('month')[:3].lower()) + 1
					except:	mon  = m.group('mon')
	
					datestamp = (int(year), int(mon), int(mday), 0, 0, 0, 0, 0, 0,)
					try:
						if time.mktime(datestamp) < time.time() - 86400*4:
							goodDates.append(datestamp)
							print 'date recongized: %r' % (m.group(),)
						else:
							print 'discarding date, too recent: %r' % m.group()
					except Exception, args:
						print args
		
		# Remove duplicate items
		goodDates = dict.fromkeys(goodDates).keys()

		if len(goodDates) > 1:
			print ' too many dates (%d), rejecting ' % len(goodDates)
			return False
		elif len(goodDates)== 1:
			self.date = (
				# Day Month Year
				time.strftime("%d %B %Y", goodDates[0] ),
				# Month Day Year
				time.strftime("%B %d, %Y", goodDates[0] ),
				# Year-Month-Day
				time.strftime("%Y-%m-%d", goodDates[0] ),
				)[2]
			print 'len(goodDates) = %s '% len(goodDates) 
			return True
		else: # len(goodDates) < 1:
			return False

	def setAuthor(self, list):
	#TODO reconize
	# Posted by David Cochran at 01:35:50 PM EST on 5.21.2007.
	# get "Written by James Bartlett"
		# Sign in / Log in / JS variable like
		authorblacklist = re.compile(ur'Log on|Sign in|Sign up|post[ a ]*comments?|Meld je aan|registreer|\bvar *[0-9a-zA-Z_$]+ *=', re.U | re.I)
		for byline in list:
			print 'Parsing byline', 
			wikipedia.output(byline)
			if len(list)>1:
				if len(list)>1 and re.search(r'(?is)^\s*By\W', byline):
					pass
				else:
					continue
			elif any(s in byline.lower() for s in ('staff', 'reporter', 'inc.', 'ltd', 'news', 'services')):
				wikipedia.output('Reject "%s" as author'% byline)
				continue
			print 'Parsing byline', 
			wikipedia.output(byline)
			# Avoid: SUN STAFF, STAFF REPORTER, DAILY REPORTERa
			# Dr. Mr. Ms. Jr. Sr. III
			# Van Buren
			# J J. SMITH
			# RAULl McZINE
			# Doris X. Hartwig
			# McCallister, Kevin
			# Cal Ripken, Jr.
			# JSR
			# Brendan O'Neill

			byline = re.sub(r'\s+', ' ', re.sub(r'</?\w+[^<>]*>', '', byline))
			byline = cleanText(byline)
			if authorblacklist.search(byline):
				wikipedia.output('Byline matches blacklist')
				continue

			if len(byline) < 60:
				self.byline = byline

			# By: Jack O'Nell and Keven Spade
			firstlast = re.match(r"(?su)^\s*(Written\W+|Posted\W+|Reporter\W+)?(on\W+|[Bb][Yy]\W+)(?P<first>[A-Z][a-z]+( +[A-Z].?)?) +(?P<last>(Mc|O'|)[A-Z][a-z]+)\b.*", byline)
			if firstlast:
				self.last = firstlast.group('last')
				self.first= firstlast.group('first')

			#	author_r = re.search(r'\b[Bb]y ([A-Z. /]+(?:[a-z,]+ +[A-Z. /]+)*), \w', u.unicode)
			#authors = [s.strip() for s in byline.split(',')]
			if byline.count(',') > 1 or ' and ' in byline:
			#	p.append('coauthors = %s' % (', '.join(authors[1:])))
				wikipedia.output('WARNING: All authors may not have been parsed')

	def refTitle(self):
		self.fixTitle()
		tl = ''
		if useTemplates:
			# We try to arrange parameters in the order they are outputted 
			#	 Author, Date, [url (archiveurl/date) title], format, publisher, accessdate
			#  	 [url title] date publisher accessdate
			p = []

			if self.last and self.first:
				p.append('last=%s' % self.last)
				p.append('first=%s'% self.first)
			elif self.byline:
				p.append('author=%s' % cleanText(self.byline))

			p.append("url=%s" % self.link)
#ARX		p.append("title=%s" % cleanText(re.sub('<!-+ *Bot[- ]generated title *-+>', '', self.title)).replace('|', '&#124;') )
			p.append("title=%s" % cleanText(self.title).replace('|', '&#124;') )
			if self.format:
				p.append('format=%s' % self.format)
			if self.lang and self.lang != self.site.language():
				p.append('language={{%s icon}}' % self.lang)
			if self.location:
				p.append('location=%s' % cleanText(self.location))
			if self.doi:
				p.append('doi=%s' % self.doi)
			if self.publisher:
				p.append('publisher=%s' % self.publisher)
			p.append('date=%s' % cleanText(self.date or ''))
			p.append("accessdate=%s" % time.strftime("%Y-%m-%d"))
			

#			if self.byline and not self.format and self.date:
#				s = "<ref%s>{{cite news|%s}}</ref>" % (self.refname, ' |'.join(p))
#			else:
			s = "<ref%s>{{cite web|%s}}</ref>" % (self.refname, ' |'.join(p))
		else:
			self.title = cleanText(self.title)
			if self.lang and self.lang != self.site.language():
				tl = wikipedia.translate(self.site, lang_template) % self.lang
				tl += ' '
			else:
				tl =''
			if (self.last and self.first or self.author) and self.date:
				s = '%s. (%s) [%s %s]. %s' % (
					self.first and self.last and '%s, %s'%(self.last,self.first) or self.byline,
					self.date,
					self.link, 
					self.title,
					self.publisher,
					)
			elif self.date:
				s = '[%s %s]. %s (%s)' % (self.link, self.title, self.publisher, self.date, )
			else:
				s = '[%s %s]. %s' % (self.link, self.title, self.publisher)
			s = '<ref%s>%s%s%s. Retrieved on %s.</ref>' % (self.refname, tl, s, self.format and '(%s) '%self.format or '', time.strftime("%Y-%m-%d"),)

		#TODO enable commonfixes
		if commonfixes:
			s = commonfixes.fix(s)
		self.printFormField(s)
		return s

	def refLink(self):
		if self.lang and self.lang != self.site.language():
			tl = wikipedia.translate(self.site, lang_template) % self.lang
			tl = tl + ' '
		else:
			tl =''
		s = '<ref%s>%s%s</ref>' % (self.refname, tl, self.link)
		self.printFormField(s)
		return s

	
	def refDead(self):
		tag = wikipedia.translate(self.site, deadLinkTag)
		s = '<ref%s>[%s%s]%s</ref>' % (self.refname, self.link, " "+(self.title or ''), tag)
		self.printFormField(s)
		return s

	def printFormField(self, s):
		global refsupdate
		refsupdate+=1
		printu('<div class="refTextBox"><a class="ref-showdoc" target="_blank" onclick="linkIframe(this);return false" href="//en.wikipedia.org/wiki/Category:Citation_templates">List citation templates</a>Reference%s:<textarea class="refBox" rows="4" cols="80" style="width:100%%;" onmouseover="toTextArea(this)" onfocus="toTextArea(this)">%s</textarea></div>' % (self.contextLine and ' on <a href="#from0_%(line)d">line %(line)d</a>' % dict(line=self.contextLine) or '', wikipedia.escape(s)))

	def transform(self):
		self.title = cleanText(self.title or '')
		#avoid closing the link before the end
		self.title = self.title.replace(']', '&#93;')
		#avoid multiple } being interpreted as a template inclusion
		self.title = self.title.replace('}}', '}&#125;')
		#prevent multiple quotes being interpreted as '' or '''
		self.title = self.title.replace('\'\'', '\'&#39;')
		self.title = wikipedia.unicode2html(self.title, self.site.encoding())


class ReferencesRobot:
	def __init__(self, site, generator, acceptall = False, limit = None):
		self.generator = generator
		self.acceptall = acceptall
		self.limit = limit
		self.site = site
		self.stopPage = wikipedia.translate(self.site, stopPage)
		self.stopPageRevId = wikipedia.Page(self.site, 
											self.stopPage).latestRevision()
		self.META_CONTENT = re.compile(r'(?i)<meta[^>]*content\-type[^>]*>')
		self.CHARSET = re.compile(r'(?i)charset\s*=\s*(?P<enc>[^\'";>/]*)')
		self.META_LANG = re.compile(r'(?i)<meta[^>]*content\-language[^>]*>')
		self.LANG = re.compile(ur'(?i)content\s*=\s*(?P<lang>[^\'";>/]*)')
		self.TITLE = re.compile(ur'(?is)<title[^<>]*>(.*?)</title>')
		self.NON_HTML = re.compile(r'(?is)<script[^>]*>.*?</script>|<style[^>]*>.*?</style>|<!--.*?-->|<!\[CDATA\[.*?\]\]>')
		allowed_media_types = ur'application/(?:xhtml\+xml|xml)|text/(?:ht|x)ml'
		self.MIME = re.compile(allowed_media_types)
		
		local = wikipedia.translate(self.site, badtitles)
		if local:
			self.titleBlackList = re.compile(globalbadtitles + '|' + local, re.I | re.S | re.X)
		else:
			self.titleBlackList = re.compile(globalbadtitles, re.I | re.S | re.X)
		self.norefbot = noreferences.NoReferencesBot(None, verbose=False, site=self.site)
 
	def put_page(self, page, new):
		"""
		Prints diffs between orginal and new (text), puts new text for page
		"""
		#wikipedia.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<" 
		#				 % page.title())
		wikipedia.showDiff(page.get(), new)
		wikipedia.setAction(wikipedia.translate(self.site, msg)%globals())
		page.put(new, wikipedia.EditMsg+u' using [[WP:REFLINKS|Reflinks]]')
		#age.put(new, wikipedia.EditMsg+u' using [[tools:~dispenser/view/Reflinks|reflinks]]')

	def httpError(self, err_num, link, pagetitleaslink):
		"""Log HTTP Error"""
		wikipedia.output(u'HTTP error (%s) for %s on %s' 
						  % (err_num, link, pagetitleaslink),
						 toStdout = True)
		f = codecs.open(
				wikipedia.datafilepath(
					'../../webreflinks-httpErrorLog', 
					'reflinks-%s-%s.txt' % (self.site.family.name, 
											self.site.language())),
				'a', 'utf-8')
		f.write(u'%s: %s from %s on %s\n' % (err_num, link, pagetitleaslink, time.ctime()) )
		f.close()

	def getPDFTitle(self, ref, data): 
		# We cannot use pipes in python 2.5 since it
		# is screwed up, 2.6 is fixed
		fd, infile = tempfile.mkstemp()
		urlobj = os.fdopen(fd, 'r+w')
		urlobj.write(data)
		try:
			pdfinfo = subprocess.Popen(["pdfinfo", "/dev/stdin"], stdin=urlobj, stdout=subprocess.PIPE,	stderr=None)
			pdfinfo_out = pdfinfo.communicate()[0]

			for aline in pdfinfo_out.splitlines():
				aline = unicode(aline, 'latin-1')
				if aline.lower().startswith('title'):
					ref.title = aline.split(None)[1:]
					ref.title = ' '.join(ref.title)
					#if ref.title: wikipedia.output(u'Title: ' +ref.title )
				if aline.lower().startswith('author'):
					ref.author = aline.split(None)[1:]
					ref.author = ' '.join(ref.author)
					#if ref.author != '': wikipedia.output(u'Author: ' +ref.author )
			if pdfinfo_out:
				print('<div class="console-link"><a href="javascript:" onclick="with(this.parentNode.nextSibling.style){display=(display?\'\':\'none\')}">Open Console</a></div><pre \nclass="console" style="display:none;">%s</pre>'%pdfinfo_out)#.encode('utf-8'))
		except ValueError:
			wikipedia.output( u'pdfinfo value error.' )
		except OSError:
			wikipedia.output( u'pdfinfo OS error.' )
		except:	# Ignore errors
			wikipedia.output( u'PDF processing error.' )
			raise
		urlobj.close()
		os.unlink(infile)
	
		# 
		ref.publisher=''
		ref.page = ' '
		ref.format = "PDF"

	def run(self):
		"""
		Runs the Bot
		"""
		deadLinks = codecs.open(listof404pages, 'r', 'latin_1').read() 
		socket.setdefaulttimeout(30)
		for page in self.generator:
			try:
				# Load the page's text from the wiki
				new_text = page.get()
				if not page.canBeEdited():
					wikipedia.output(u"You can't edit page %s" 
									  % page.aslink())
					continue
			except wikipedia.NoPage:
				wikipedia.output(u'Page %s not found' % page.aslink())
				continue
			except wikipedia.IsRedirectPage:
				target = wikipedia.Page(self.site, page._redirarg)
				printu('<img src="//bits.wikimedia.org/skins-1.5/common/images/redirectltr.png" alt="#REDIRECT " /><a href="?page=%s" class="redirectText">%s</a>' % (target.title(asUrl=True, allowInterwiki=True), target.title()))
				continue

			if commonfixes:
				new_text = commonfixes.fix(page=page, text=new_text)
				old_text = new_text
	
			count = 0
			for match in linksInRef.finditer(new_text):#wikipedia.removeDisabledParts(new_text)):
				if 'generated title' in match.group() and overrideBotTitles:
					pass
				elif match.group('title') and not overrideSimpleTitles:
					#print '<!-- title found, not editing as overrideSimpleTitles==%s -->' % overrideSimpleTitles
					continue
				elif match.group() not in wikipedia.removeDisabledParts(new_text):
					print '<hr class="refSep" />'
					print '<div class="ref-disabled">Ref found in disabled area</div>'
					print match.groups()
					continue
				else:
					pass
				
				link = match.group(u'url')
				#debugging purpose
				#print link
				if u'www.jstor.org' in link or 'www.imdb.com' in link:
					#TODO: Clean URL blacklist
					wikipedia.output('Skipping %s ' % link)
					continue
				#if link.startswith('https:'):
				#	print('<hr class="refSep" />')
				#	print('<div class="ref-skipped">Skipping %s<br/> See <a href="//bugs.python.org/issue7305">Issue 7305: urllib2.urlopen() segfault using SSL on Solaris - Python tracker</a></div>' % link)
				#	continue
				
				if count > self.limit:
					wikipedia.output('Stopping at %d references' % count)
					break
				else:
					time.sleep(2)
					count += 1
				
				ref = RefLink(link, match.group('title'), match.group('name'))
				# set line number
				iBegin = page.get().find(match.group())
				ref.contextLine  = page.get().count('\n', 0, iBegin) + 1 if iBegin>0 else None
				mylink = re.sub(r'https?://(?:web.archive.org|wayback.archive.org)/web/(\d+)/(http:?//?|)', 'http://', link)
				iPath  = mylink.find('/', 8)
				iHost  = 7 if mylink.startswith('http://') else 0
				if iPath < 0: iPath=len(link)
				printu('<div class="retrieve"><hr /><a href="//dispenser.info.tm/~dispenser/cgi-bin/url_info.py?archivesearch=dead-0&url=%(quoted)s" class="info" onclick="linkIframe(this);return false">WebCite </a><a href="%(url)s" onclick="linkIframe(this);return false" class="external free"><span class="domain">%(domain)s</span><span class="pathquery">%(pathquery)s</span></a></div>' % dict(
					url 	= wikipedia.escape(link), 
					quoted	= urllib2.quote(link.encode('utf-8')),
					domain    = wikipedia.escape(mylink[iHost:iPath]),
					pathquery = wikipedia.escape(mylink[iPath:link.find('#') if '#' in link else None]),
				))
				# Flush
				os.sys.stdout.flush()
				f = None
				try:
					socket.setdefaulttimeout(20)
					# traceback debugging:
					# import urllib2
					# url = ""
					# import urllib2; req=urllib2.Request(url); f=urllib2.urlopen(req); print f.read(200)
					req = urllib2.Request(ref.url, headers={
						'User-Agent':	'Reflinks (+http://dispenser.info.tm/~dispenser/view/Reflinks)',
						'Referer':   	'http://%s%s' % (self.site.hostname(), self.site.nice_get_address(page.urlname())),
                    	'Accept-Encoding':	'gzip',
						})
					f = urllib2.urlopen(req)
					os.sys.stdout.flush()
					#Try to get Content-Type from server
					headers = f.info()
					contentType = headers.getheader('Content-Type')
					#get the content language
					ref.lang = headers.getheader('Content-Language')
					if ref.lang:
						ref.lang=ref.lang[:2].lower()
					# Test if the redirect was valid
					redir = f.geturl()
					if redir != ref.link and domain.findall(redir) == domain.findall(link):
						if soft404.search(redir) and not soft404.search(ref.link):
							wikipedia.output(u'\03{lightyellow}WARNING\03{default} : Redirect 404 : %s ' % redir)
							continue
						if dirIndex.match(redir) and not dirIndex.match(ref.link):
							wikipedia.output(u'\03{lightyellow}WARNING\03{default} : Redirect to root : %s ' % redir)
							continue

					socket.setdefaulttimeout(None)
					try:
						if headers.get('Content-Encoding') in ('gzip', 'x-gzip'):
							try:
								data = gzip.GzipFile(fileobj=StringIO.StringIO(f.read())).read()
							except Exception as e:
								wikipedia.output(u'\03{lightyellow}WARNING\03{default} : Decompression error : %s' % redir)
								continue
						else:
							data = f.read()
					except IOError, args:
						# Example:
						# http://www.commondreams.org/news2000/0619-11.htm
						data = ''
						wikipedia.output('Content Encoding Error (%s)' % (args))
					except MemoryError:
						wikipedia.output('\03{lightred}MemoryError\03{default} : Out of memory : %s' % ref.link)
						continue

					

				except UnicodeError:
					#example : http://www.adminet.com/jo/20010615¦/ECOC0100037D.html in [[fr:Cyanure]]
					wikipedia.output(u'\03{lightred}Bad link\03{default} : %s in %s' % (ref.url, page.aslink()))
					continue
				except urllib2.HTTPError, e:
					self.httpError(e.code, ref.url, page.aslink())
					if e.code == 410: # 410 Gone, indicates that the resource has been purposely removed
						repl = ref.refDead()
						new_text = new_text.replace(match.group(), repl)
					elif e.code == 404 and (u'\t%s\t' % ref.url in deadLinks):
						repl = ref.refDead()
						new_text = new_text.replace(match.group(), repl)
					#	for keywords in ('error page', 'http error 404', 'file not found', 'not be found'):
					elif e.code == 404:
						wikipedia.output("\03{lightred}DO NOT DELETE\03{default}  CiteWeb or the Wayback Machine can be used to relocated dead link, Checklinks is designed to handle this. ")
						repl = ref.refDead()
						new_text = new_text.replace(match.group(), repl)
					continue
				except (urllib2.URLError, 
						socket.error, 
						IOError, 
						httplib.error,
						socket.timeout), e:
				#except (urllib2.URLError, socket.timeout, ftplib.error, httplib.error, socket.error), e:
					wikipedia.output(u'Can\'t get page %s : %s' % (ref.url, e))
					continue
				except ValueError:
					#Known bug of httplib, google for :
					#"httplib raises ValueError reading chunked content"
					wikipedia.output("httplib raises ValueError reading chunked content")
					continue
				finally:
					if f:
						f.close()

				# URL looks ok
				# now process it for the title

				if contentType and not self.MIME.search(contentType):
					if ref.link.lower().endswith('.pdf'):
						# If file has a PDF suffix
						ref.title= match.group('title') or ref.title
						self.getPDFTitle(ref, data)
					if not ref.title:
						wikipedia.output(u'\03{lightyellow}WARNING\03{default} : No title : %s ' % ref.link)
						repl = ref.refLink()
					elif self.titleBlackList.match(ref.title):
						wikipedia.output(u'\03{lightyellow}WARNING\03{default} : Unusable web page title : %s ' % ref.link)
						repl = ref.refLink()
					else:
						ref.transform()
						repl = ref.refTitle()
					new_text = new_text.replace(match.group(), repl)

					continue

				# HTML handler
				# Read the first 1,000,000 bytes (0.95 MB)
				linkedpagetext = data#f.read(1000000)

				meta_content = self.META_CONTENT.search(linkedpagetext)
				enc = []
				if meta_content:
					tag = meta_content.group()
					# Prefer the contentType from the HTTP header :
					if not contentType:
						contentType = tag
					s = self.CHARSET.search(tag)
					if s:
						tmp = s.group('enc').strip("\"' ").lower()
						naked = re.sub('[ _\-]', '', tmp)
						# Convert to python correct encoding names
						if naked == "gb2312":
							enc.append("gbk")
						elif naked == "shiftjis":
							enc.append("shift jis 2004")
							enc.append("cp932")
						elif naked == "xeucjp":
							enc.append("euc-jp")
						else:
							enc.append(tmp)
				if not contentType:
					wikipedia.output(u'No content-type found for %s' % ref.link)
					continue
				elif not self.MIME.search(contentType):
					wikipedia.output(u'\03{lightyellow}WARNING\03{default} : media : %s ' % ref.link)
					repl = ref.refLink()
					new_text = new_text.replace(match.group(), repl)
					continue

				# Ugly hacks to try to survive when both server and page return no encoding.
				# Uses most used encodings for each national suffix
				if u'.ru' in ref.link or u'.su' in ref.link:
					# see http://www.sci.aha.ru/ATL/ra13a.htm : no server encoding, no page encoding
					enc = enc + ['koi8-r', 'windows-1251']
				elif u'.jp' in ref.link:
					enc.append("shift jis 2004")
					enc.append("cp932")
				elif u'.kr' in ref.link:
					enc.append("euc-kr")
					enc.append("cp949")
				elif u'.zh' in ref.link:
					enc.append("gbk")

				u = UnicodeDammit(linkedpagetext, overrideEncodings = enc)

				if not u.unicode:
					#Some page have utf-8 AND windows-1252 characters,
					#Can't easily parse them. (~1 on 1000)
					wikipedia.output('%s : Hybrid encoding...' % ref.link)
					repl = ref.refLink()
					new_text = new_text.replace(match.group(), repl)
					continue
				if enc and u.originalEncoding and u.originalEncoding not in enc:
					# BeautifulSoup thinks that the original encoding of our page was not one
					# of the encodings we specified. Output a warning.
					wikipedia.output(u'\03{lightpurple}ENCODING\03{default} : character encoding mismatch : %s (%s)' % (ref.link, ref.title))
				if u'Ã©' in ref.title:
					wikipedia.output(u'%s : Hybrid encoding...' % ref.link)
					repl = ref.refLink()
					new_text = new_text.replace(match.group(), repl)
					continue

			
				t=''
				# Retrieves the first non empty string inside <title> tags
				for m in self.TITLE.finditer(u.unicode):
					t = match.group('title') or m.group(1) or ''
					if ref.setTitle(t):
						break;

				# Begin console
				print('<div class="console-link"><a href="javascript:" onclick="with(this.parentNode.nextSibling.style){display=(display?\'\':\'none\')}">Show console</a></div><div \nclass="console" style="display:none;">')
				
				ref.setPublisher(domain.search(ref.link).group(2), hints=t)

				print '<dl class="page_analysis" styles="">'
				print '<dt>Classes</dt>'
				print '<dd>'
				print '<span class="highlight">'
				for c in mdClass:
					list = getClassTextNodes(c, u.unicode, re.I|re.U)
					if list and list != []:
						wikipedia.output("\"%s\" yields: %r" % (c, [cleanText(re.sub(r'<(/?\w+)[^<>]*>', r'<\1>', s[:200])) for s in list[:10] ]))
				print '</span>'
				
				for c in bylClass+dateClass+pubClass:
					list = getClassTextNodes(c, u.unicode, re.U)
					if list and list != []:
						wikipedia.output("\"%s\" yields: %r" % (c, [cleanText(re.sub(r'<(/?\w+)[^<>]*>', r'<\1>', s[:200])) for s in list[:10] ]))
				for c in bylClass:
					list = getClassTextNodes(c, u.unicode, re.I|re.U)
					if list and ref.setAuthor(list):
						wikipedia.output('INFORMATION: Setting author as %r from class %r'% (ref.date, c))
						break
				print '</dd>'
				wikipedia.output("DATE:")
				for c in dateClass + bylClass:
					if ref.setDate( getClassTextNodes(c, u.unicode, re.U) ):
						wikipedia.output('Setting date as %r from class %r'% (ref.date, c))
						break
				else:
					#TODO get text from <p>...</p> first
					if ref.setDate( ref.url ):
						wikipedia.output('DATE set from the URL')
					# Try get any date out of the page, this can cause it to pickup comment or irrlevent dates in the text
					elif ref.setDate( (cleanText(u.unicode),) ):
						wikipedia.output('DATE extracted from text, likely is not correct')
					elif ref.setDate((u.unicode,)):
						wikipedia.output('DATE extracted from raw HTML, very likely not correct')
					else:
						wikipedia.output('ERROR: DATE extracted failed.  Please examine the HTML to find hidden structures for dates.  Dates newer than 1 week old are ignored')

				for c in pubClass:
					list = getClassTextNodes(c, u.unicode, re.I|re.U)
					if list and len(list)==1:
						ref.setPublisher(list[0])
						break
				
				if '<meta' in u.unicode:
					# Parse meta tags
					"""  Extract the following fields when avalible----
<meta name="citation_journal_title" content="Science">
<meta name="citation_publisher" content="AAAS">

<meta name="citation_authors" content="Schaeffer, Jonathan; Burch, Neil; Bjornsson, Yngvi; Kishimoto, Akihiro; Muller, Martin; Lake, Robert; Lu, Paul; Sutphen, Steve">
<meta name="citation_title" content="Checkers Is Solved">
<meta name="citation_date" content="09/14/2007">
<meta name="citation_volume" content="317">
<meta name="citation_issue" content="5844">
<meta name="citation_firstpage" content="1518">
<meta name="citation_id" content="317/5844/1518">
<meta name="citation_mjid" content="sci;317/5844/1518">
<meta name="citation_doi" content="10.1126/science.1144079">
<meta name="citation_pdf_url" content="http://www.sciencemag.org/cgi/reprint/317/5844/1518.pdf">
<meta name="citation_pmid" content="17641166">

<meta name="dc.Contributor" content="Schaeffer, Jonathan">
<meta name="dc.Contributor" content="Burch, Neil">
<meta name="dc.Contributor" content="Bjornsson, Yngvi">
<meta name="dc.Contributor" content="Kishimoto, Akihiro">
<meta name="dc.Contributor" content="Muller, Martin">
<meta name="dc.Contributor" content="Lake, Robert">
<meta name="dc.Contributor" content="Lu, Paul">
<meta name="dc.Contributor" content="Sutphen, Steve">
<meta name="dc.Title" content="Checkers Is Solved">
<meta name="dc.Identifier" content="10.1126/science.1144079">
<meta name="dc.Date" content="09/14/2007">

...

LastUpdated
				"""
					print '<dt>&lt;meta&gt; tags</dt>'
					print '<dd>'
					for m in re.finditer(r'(?is)<meta\s+name\s*=\s*[\'"]?(?P<name>\w+)[^<>]+content\s*=\s*(?P<quote>["\']?)(?P<content>[^<"\'>]+)(?P=quote)>', u.unicode):
						# eliminate search engine hints - they are of no use to us
						# 'PUBDATE', # USAToday.com
						# 'author', 
						if not m.group('name').lower() in ('keywords', 'description', 'robots', 'robot', 'bots'):
							wikipedia.output("%s: %r" % (m.group('name'), m.group('content')))
						if m.group('name').lower() in (
						'pubdate',		# nytimes
						'doc_date',		# cbsnews.com
						'LastUpdated',	#calmac.co.uk
						# seems to be last modified stamp
						#'pd',		# chess.about.com
						):
							ref.setDate( [m.group('content'), ] )
						elif m.group('name').lower() in (
						'author', # globalsecurity.org,  # cbsnews.com usually set as "CBSNews"
						'alt_author',	# cbsnews.com (always Joel Roberts?)
						'byl',			# nytimes.com
						):
							ref.byline = m.group('content')
						elif m.group('name').lower() in (
						'citation_doi', # nytimes.com
						):
							ref.doi		= m.group('content')
						elif m.group('name').lower() in (
						'geo', # nytimes.com
						):
							ref.location = m.group('content')
						elif m.group('name').lower() in (
						'pg', # nytimes.com
						):
							ref.page = m.group('content')
	
						else:
							pass
					print '</dd>'

				print '<dt>Nodes</dt>'
				print '<dd>'
				# smh.com.au uses nodes <byline> and <date>
				for c in ('title', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'byline', 'date', 'arttitle'):
					contents = re.findall(r'(?uis)<%s[^</>]*>\s*(.*?)\s*</%s\s*>' % (c, c), u.unicode)
					if contents:
						wikipedia.output("<%s>: %r"%(c, [re.sub(r'\s+', r' ', re.sub(r'</?\w+[^<>]*>', '', s)) for s in contents[:5] ]))
					if c in ('h1', 'h2') and len(contents) == 1:
						contents[0] = re.sub(r'</?\w+[^<>]*>', '', contents[0]).strip()
						if not ref.title:
							ref.title=contents[0]	
						elif contents[0] in ref.title and not hasattr(ref, 'publisher'):
							ref.title=contents[0]
							ref.setPublisher(ref.title.replace(contents[0], '').strip('-\n. :'))
				print '</dd>'
				# Note the third part really can be anyting
				finddoi = re.findall(r'(?u)(?:doi:|=\s*"|dx.doi.org/|hdl.handle.net/)(?P<doi>10\.[0-9]{4}/[\w\-\.]{10,})(?=[<>"\s]|[^\w\.\-])', u.unicode)
				if not ref.doi and len(finddoi)==1:
					print 'adding doi'
					ref.doi = finddoi[0]#.group('doi')
				
				contents = re.search(r'\b[Pp]ermalink\b', u.unicode)
				if contents:
					print '<dt>Analysis</dt><dd>Page has a Permalink</dd>'
				lastMod = headers.getheader('Last-Modified')
				if lastMod:
					print '<dt>Headers</dt><dd>Last Modified header: %r</dd>'%lastMod
				print '</dl>'

				# End console output
				print '</div>'

# Error conditions
				if not ref.title:
					wikipedia.output(u'%s : No title found...' % ref.link)
					repl = ref.refLink()
					new_text = new_text.replace(match.group(), repl)
					continue
#TODO move to ref class
				if self.titleBlackList.match(ref.title):
					wikipedia.output(u'\03{lightred}WARNING\03{default} : Unusable web page title (%s)' % (ref.title))
					repl = ref.refLink()
					new_text = new_text.replace(match.group(), repl)
					continue

				ref.transform()

				repl = ref.refTitle()
				new_text = new_text.replace(match.group(), repl)

			try: # KEEP MAINTENANCE UP TO DATE
				import maintainer
				maintainer.updateBel(page, remove=True)
			except ImportError:
				pass
			if not refsupdate:
				if new_text == page.get():
					wikipedia.output('No changes were necessary in %s' 
									 % page.aslink())
					continue

				if commonfixes and new_text == old_text:
					wikipedia.output('Only common fixes for %s'
									 % page.aslink())
					continue
				
			if self.norefbot.lacksReferences(new_text):
				new_text = self.norefbot.addReferences(new_text)
				# [[User talk:Dispenser/Reflinks#2 requests]]
				if useTemplates:
					new_text=new_text.replace('<references/>', '{{reflist}}')
			self.put_page(page, new_text)

def main():
	global useTemplates
	global overrideBotTitles, overrideSimpleTitles
	useTemplates = False
	genFactory = pagegenerators.GeneratorFactory()
	site = wikipedia.getSite()
	pages = []
	xmlFilename = None
	always = True
	limit = None
	namespaces = []
	generator = None
	title = ""
	for arg in wikipedia.handleArgs():
		if arg.startswith('-page:'):
			page = wikipedia.Page(site, arg[6:])
			title = page.title(allowInterwiki=True)
			if title:
				site = page.site()
				pages.append(page)
		elif arg.startswith('-namespace:'):
			try:
				namespaces.append(int(arg[11:]))
			except ValueError:
				namespaces.append(arg[11:])
		elif arg.startswith('-summary:'):
			wikipedia.setAction(arg[9:])
		elif arg == '-always':
			always = True
		elif arg.startswith('-commonfixes'):
			#cf = arg[13:] in ('', 'yes', 'true', 'y')
			if arg[13:].lower() in ('n', 'no', 'false'):
				# HACK!
				global commonfixes
				commonfixes = None
		elif arg.startswith('-limit:'):
			try:
				limit = int(arg[7:])
			except ValueError:
				wikipedia.output("-limit: only accepts numbers")
		elif arg.startswith('-templates:'):
			useTemplates = bool(arg[11:], true)
		elif arg.startswith('-overwrite:'):
			if 'bot' in arg:
				overrideBotTitles=True
			elif 'all' in arg or 'simple' in arg:
				overrideBotTitles=True
				overrideSimpleTitles=True
			elif 'text' in arg:
				pass
			elif not arg[11:]:
				pass
			else:
				print 'Unkown:', arg
		## DEPRECATED 
		elif arg.startswith('-citeweb'):
			useTemplates= True
		elif arg.startswith('-force'):
			overrideBotTitles=True
		elif arg.startswith('-client'):
			pass
		else:
			generator = genFactory.handleArg(arg) or generator
			print arg

	print '<form action="../cgi-bin/webreflinks.py" style="text-align:center;">'
	print '<input name="page" size="40" value="%s" onchange="fixTitle(this)" />' % wikipedia.escape(title).encode('utf-8')
	print '<input value="Fix bare references" type="submit" />'
	print '<div>'
	print '<input type="hidden" name="citeweb" id="citeweb" %s/><label for="citeweb"><!--Use templates--></label>' % (useTemplates and 'value="checked"' or '')
#	print '<input type="checkbox" name="overwrite" value="bot" id="force" %s/><label for="force">Overwrite bot generated titles</label>' % (overrideBotTitles and 'checked="checked"' or '')
	print '</div>'
	print '</form>'

	if pages and pages != []:
		generator = iter(pages)
	if not generator:
		# syntax error, show help text from the top of this file
		print('<img src="//bits.wikimedia.org/skins-1.5/common/images/redirectltr.png" alt="#REDIRECT " /><span class="redirectText"><a href="/~dispenser/view/Reflinks">tools:~dispenser/view/Reflinks</a></span>')
		wikipedia.stopme()
		os.sys.exit()
	print("""
Introduction by <a href="//en.wikipedia.org/wiki/User:Smartse">SmartSE</a>
<div style="font-size:88%; font-style:italic; padding:0 2em 0.5em;">Reflinks will help you to turn bare urls into templated references, hopefully leaving you more time to write and reducing link rot caused by bare urls. The tool visits each webpage that is in a bare reference and collects the page title and some other information automatically, the tool has to be checked over manually to make sure that the references are filled in correctly by the tool. You may have to remove some extra information from the template and add extra details if the tool is not able to find it for you. Some links may be marked as dead links incorrectly as the site blocks the tool, you may wish to manually check these dead links before adding the dead link tag to the article. The tool also does a few other minor maintenance tasks.</div>
""")
	bot = ReferencesRobot(site, generator, always, limit or 20)
	bot.run()

if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=False, head = """
<style type="text/css">
.retrieve {
	background-color: #37b;
	border-bottom: 1px solid #3c78b5;
	color:white;
	font-weight:bold;
	margin: 3em 0 0;
	padding: 0 0.3em;
	-moz-border-radius-topleft: .5em;
	-moz-border-radius-topright:.5em;
	border-top-left-radius: .5em;
	border-top-right-radius:.5em;
}
.retrieve .domain {
	text-decoration:underline;	
}
.retrieve .info {
	float:right;
	padding: 0.1em 0.5em 0.1em 0.1em;
}
#mw_content .retrieve a:link {
	color:#fff;
}
#mw_content .retrieve a:visited {
	color:#acf;
}
.retrieve hr { display:none; }
.console-link {
	background:#eee;
	font-size:x-small;
	line-height:1em;
	text-align:right;
}
.console {
	background:#000;
	border:1px inset;
	color:#999;
	font-family:monospace;
	max-height:20em;
	overflow:auto;
	padding:0.5em;
}
.ref-showdoc {
	float:right;
	font-size:92%;
}
.refTextBox{
	background:#eee;
}
.ref-toolShelf {
	background:#eee;
	font-size:88%;
	margin: 0 0 3em;
	padding: 0 0.3em;
	-moz-border-radius-bottomleft: .5em;
	-moz-border-radius-bottomright:.5em;
	border-bottom-left-radius: .5em;
	border-bottom-right-radius:.5em;
}

/* -- -- */
.desynced {
	background-color:#FCC;
	border:solid red 2px;
}
.sync-wait {
	cursor:not-allowed;
}
.synced {
}
.refBox {
	cursor:wait;
}

</style>
		<!--link rel="stylesheet" href="/~dispenser/resources/reflinks.css" type="text/css" /-->
		<script src="/~dispenser/resources/reflinks.js" type="text/javascript"></script>
		""")
		main()
	finally:
		wikipedia.endContent()
		wikipedia.stopme()
