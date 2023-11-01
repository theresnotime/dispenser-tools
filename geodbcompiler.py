#! /usr/bin/env python
# -*- coding: utf-8  -*-
"""
geodbcompiler is the wedge between the databases and the parsing library ghel 
(GeoHack External links).

Parameters
	-wiki:		x
	-offset:	x
	-limit:		(0 = non-limiting)
	-refUrl:	x
	-dbname:	x
	-help

Examples:
nice ~/pyscripts/geodbcompiler.py -rebuild -wiki:jawiki > ~/public_html/logs/coord-jawiki.log


import geodbcompiler
tuple(geodbcompiler.process_db_row_with_ghel(((1,"http://toolserver.org/~geohack/geohack.php?pagename=File:Scheiblingkirchen-T._-_Pfarrhof_Thernberg.jpg&params=47.66143_N_16.17678_E_type:camera_AT-3&language=en"),), "commonswiki"))

/* Using MBR for local search
 * TODO Improve example
 */
SELECT *
FROM coord_enwiki
WHERE Contains(Envelope(LineString(Point(X(Point(0,0))-.1,Y(Point(0,0))-.1),
	POINT(X(Point(0,0))+.1,Y(Point(0,0))+.1))), gc_location);


----
Scratchpad


TODO make into a tool:
/* Number of coordinates on a page */
SELECT page_namespace, page_title, COUNT(*)
FROM `coord_enwiki`
LEFT JOIN enwiki_p.page ON gc_from = page_id
GROUP BY gc_from
ORDER BY COUNT(*) DESC

/* Pages with duplicate coordinates */
SELECT GROUP_CONCAT(gc_from), GROUP_CONCAT(page_title), gc_globe
FROM u2815__p.coord_enwiki
JOIN page ON page_id=gc_from AND page_namespace=0
GROUP BY gc_from, gc_location
HAVING COUNT(*) >= 2;


/*  */
SELECT gc_from, CONCAT(MIN(gc_count), '-', MAX(gc_count)) AS r_count,  CONCAT(MIN(gc_sum), '-', MAX(gc_sum)) AS r_sum, COUNT(*)
FROM (
SELECT gc_from, COUNT(*) gc_count, SUM(gc_primary) as gc_sum
FROM u2815__p.coord_enwiki
GROUP BY gc_from
HAVING gc_sum = gc_count
) as r
GROUP BY FLOOR(LOG(gc_count)),  FLOOR(LOG(gc_sum));


/*  */
SELECT GROUP_CONCAT(gc_from), GROUP_CONCAT(page_title), gc_globe
FROM u2815__p.coord_enwiki
JOIN page ON page_id=gc_from AND page_namespace=0
GROUP BY gc_from, gc_location
HAVING COUNT(*) >= 2;


SELECT GROUP_CONCAT(gc_from), GROUP_CONCAT(gc_name), GROUP_CONCAT(gc_globe)
FROM u2815__p.coord_commonswiki
GROUP BY gc_from, gc_name, gc_location
HAVING COUNT(*) >= 2;

SELECT GROUP_CONCAT(gc_from), GROUP_CONCAT(gc_name), GROUP_CONCAT(gc_globe)
FROM u2815__p.coord_enwiki
GROUP BY gc_location
HAVING COUNT(*) >= 2;

/* Old databases */
SELECT TABLE_NAME, IFNULL(UPDATE_TIME, CREATE_TIME) AS updated
FROM information_schema.tables 
WHERE TABLE_SCHEMA='u2815__p' AND TABLE_NAME LIKE "coord%"
HAVING updated < NOW() - INTERVAL 8 DAY;

-- 2> /dev/null; echo '
/* Find unreferencable dead tables */
SELECT a.update_time, a.table_schema, a.table_name
FROM information_schema.tables AS a
LEFT JOIN information_schema.tables AS b
ON b.table_schema=CONCAT(TRIM(LEADING "coord_" FROM a.table_name),"_p")
WHERE b.table_schema IS NULL
AND a.table_schema="u2815__p"
AND a.table_name LIKE "coord%"
;-- ' | mysql -h sql-s8-user


/* Check accuracy of MBR worldadmin98 database */
SELECT *, points, ROUND(points/(SUM(points)+1)*100,1) AS Accuracy 
FROM (
SELECT id, subid, country_iso AS "iso", gc_region, country, state,
  COUNT(DISTINCT gc_from) AS points, gc_from
FROM  u_dispenser.worldadmin98
JOIN u2815__p.coord_enwiki ON MBRWithin(gc_location, area)
AND LENGTH(gc_region)>2
GROUP BY id, subid, gc_region
ORDER BY id, subid, COUNT(*) DESC
) AS xx
GROUP BY id, subid
HAVING LEFT(gc_region,2)!=iso AND Accuracy > 60.0
ORDER BY Accuracy DESC;


"""
import os, sys, struct, cgitb
sys.path.append('/home/dispenser/pyscripts/oursql/')
import oursql
import ghel
import time; starttime=time.time()

# grep legacy_stable ~/public_html/logs/coord* -h
# Languages still using http://stable.toolserver.org/geohack/
# If you are one of these languages please update
legacy_stable = ['afwiki', 'alswiki', 'bgwiki', 'bpywiki', 
'gawiki', 'hewiki', 'hiwiki',  'hrwiki', 'lbwiki', 
'pamwiki', 'tawiki', 'thwiki', 'vecwiki', 'viwiki', 'vowiki', 'warwiki',
]


connection={}
def getConn(dbname, host=None, reconnect=False, *args, **kwargs):
	if not dbname.endswith('_p'):dbname+='_p'
	if (host,dbname) not in connection or reconnect:
		connection[host,dbname] = oursql.connect(
			db=dbname, 
			host=host or dbname[:-2]+'.analytics.db.svc.eqiad.wmflabs',
			read_default_file=os.path.expanduser('~/.my.cnf'),
			charset=None, 
			local_infile=True,
			use_unicode=False,
			*args,
			**kwargs
		)
	return connection[host,dbname]

def delConn(dbname, host=None):
	if not dbname.endswith('_p'):dbname+='_p'
	try: connection[host,dbname].close()
	except:pass
	del connection[host,dbname]

mysql_byte_escape = dict((chr(i), chr(i)) for i in range(256))
mysql_byte_escape.update({
	b'\0':  b'\\0',
	b'\b':  b'\\b',
	b'\n':  b'\\n',
	b'\r':  b'\\r',
	b'\t':  b'\\t',
	b'\x16':b'\\Z',
	b'\\':  b'\\\\',
})
def MySQL_format(s, encoding='utf-8'):
	if s is None:
		return b'\\N'
	elif isinstance(s, float):
		# repr() does not round unlike str()
		return repr(s)# if s==s else b'\\N' # NaN => NULL
	elif isinstance(s, bool):
		return b'1' if s else b'0'
	elif isinstance(s, (int, long)):
		return bytes(s)
	elif isinstance(s, bytes):
		return b''.join(map(mysql_byte_escape.__getitem__, s))
	elif isinstance(s, unicode):
		return b''.join(map(mysql_byte_escape.__getitem__, s.encode(encoding)))
	else:
		raise TypeError("%s not supported" % (type(s),))

def existingGlobesOnly(dbname, host=None):
	avail_globes = set(['Earth'])
	cursor = getConn(dbname, host=host).cursor()
	cursor.execute("""
SELECT DISTINCT SUBSTRING(page_title FROM 13)
FROM page 
WHERE page_namespace=10 AND page_title LIKE "GeoTemplate/%"
""")
	avail_globes |= set(globe.capitalize() for (globe,) in cursor if globe.isalpha())
	if dbname!='enwiki':
		conn   = getConn('enwiki')
		cursor = conn.cursor()
		cursor.execute("""
SELECT DISTINCT SUBSTRING(page_title FROM 13)
FROM page 
WHERE page_namespace=10 AND page_title LIKE "GeoTemplate/%"
""")
		avail_globes |= set(globe.capitalize() for (globe,) in cursor if globe.isalpha())
		# Conserve DB connections
		conn.close()
	ghel.globes = tuple(avail_globes & set(ghel.globes))

def getRegion(cursor, lat, lon):
	# TODO handle polygons edges better
	def myWithin(polygon, tx, ty):
		# Based off of http://local.wasp.uwa.edu.au/~pbourke/geometry/insidepoly/
		inside = False
		# TODO switch to WKB
		# POLYGON((1 2,2 3,3 4))
		begin_x, begin_y = polygon[0]
		for i in xrange(1, len(polygon)):
			end_x, end_y = polygon[i]
			if begin_y < ty <= end_y or end_y <= ty < begin_y:
				if tx < (end_x-begin_x)*(ty-end_y)/(end_y-begin_y)+end_x:
					inside = not inside
			begin_x, begin_y = end_x, end_y
		return inside
	def distanceSq(polygon, lat, lon, distsq = float('inf')):
		# Find mininum distance to the polygon
		for i in xrange(1, len(polygon)):
			cur  = polygon[i]
			prev = polygon[i-1]
			try:
				m = (cur[1] - prev[1]) / (cur[0] - prev[0] or 1e-6)
				if cur[0] == prev[0]:
					d = (cur[1] - lon)**2
				elif cur[0] + m*cur[1] > lat + m*lon > prev[0] + m*prev[1] or prev[0] + m*prev[1] > lat + m*lon > cur[0] + m*cur[1]:
					# http://www.worsleyschool.net/science/files/linepoint/method5.html
					d = (m*lat - lon + (cur[1]-m*cur[0]))**2 / (m**2 + 1)
				else:
					d = (cur[0] - lat)**2 + (cur[1] - lon)**2
				if d < distsq:
					distsq= d
			except OverflowError:
				continue
		# wrong therom for spherical distances
		return distsq
	
	# Database loaded with the worldadmin98 dataset
	wa98 = getConn('u2815__p', host='tools.labsdb').cursor()
	wa98.execute("""
SELECT country_iso, state, AsBinary(area)
FROM worldadmin98 
WHERE MBRWithin(POINT(?, ?), area)
""", (lat,lon,))
	#print lat, lon
	area_iso = None
	area_distsq = float('inf')
	for country_iso, state, area_wkb in wa98.fetchall():
		# Begining and end points are the same
		if area_wkb[0:5]!="\x01\x03\x00\x00\x00":
			# little-endian and Polygon WKB type
			raise
		polygon = tuple(struct.unpack('>dd', area_wkb[i:i+16]) for i in xrange(13, len(area_wkb), 16))
		#polygon = tuple((float(x), float(y)) for x,y in (s.split() for s in area_wkt[9:-2].split(',')))
		if myWithin(polygon, lat, lon):
			return country_iso
		else:
			distsq = distanceSq(polygon, lat, lon)
			# 0.018 is about 2 km
			#print country_iso, state, distsq**0.5
			if distsq < area_distsq and distsq < 0.018:
				area_iso    = country_iso
				area_distsq = distsq
	return area_iso

def detectDbCorruption(cursor, wiki):
	# Experimental code for detecting TS and API inconsistencies
	import urllib, urllib2, json
	params = urllib.urlencode({
		'action': 'query',
		'meta':   'siteinfo',
		'siprop': 'statistics',
		'format': 'json',
	})
	try:
		f = urllib2.urlopen('http://%s/w/api.php'%'en.wikipedia.org', params, 30)
		api_json = json.loads(f.read())
		wmf_edit_count    = api_json['query']['statistics']['edits']
		wmf_article_count = api_json['query']['statistics']['articles']
		wmf_page_count    = api_json['query']['statistics']['pages']
		wmf_image_count   = api_json['query']['statistics']['images']
		cursor.execute("SELECT ss_total_edits, ss_good_articles, ss_total_pages, ss_images, (SELECT UNIX_TIMESTAMP() - UNIX_TIMESTAMP(MAX(rev_timestamp)) FROM revision) AS replag FROM site_stats")
		ts_edits_count, ts_article_count, ts_page_count, ts_image_count, replag = cursor.fetchall()[0]
		# If negative, than we have more than offical recorded
		print wmf_edit_count, ts_edits_count, replag
		print wmf_article_count, ts_article_count, replag
		print wmf_page_count, ts_page_count, replag
		print wmf_image_count, ts_image_count, replag
	#except:
	finally:
		pass


def createTable(cursor, ghel_table):
	cursor.execute("CREATE DATABASE IF NOT EXISTS u2815__p")
	cursor.execute("DROP TABLE IF EXISTS "+ghel_table)
	cursor.execute("""CREATE TABLE %s (
	/* reference to page_id */
	gc_from   INT(8) unsigned NOT NULL,
	
	/* coord3d, direction, major dimension */
	gc_lat    DOUBLE(11,8) NOT NULL,
	gc_lon    DOUBLE(11,8) NOT NULL,
	gc_alt    FLOAT DEFAULT NULL,
	gc_head   FLOAT DEFAULT NULL,
	gc_dim    FLOAT unsigned DEFAULT NULL,

	gc_type   VARBINARY(32) DEFAULT NULL,
	gc_size   FLOAT DEFAULT NULL,
	gc_region VARBINARY(127) DEFAULT NULL,
	gc_globe  enum('',%s) NOT NULL DEFAULT '',

	gc_primary TINYINT(1) NOT NULL DEFAULT '0',
	gc_namespace INT NOT NULL,
	gc_name   VARBINARY(255) NOT NULL DEFAULT '',
	gc_location POINT NOT NULL,

	/* setup indexes */
  KEY gc_from (gc_from),
  SPATIAL KEY location (gc_location)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;
""" % (ghel_table, ','.join("'%s'"%globe for globe in ghel.globes), ))

suppressed_warnings = {}
def supress_warn(*s):
	if s[0] in suppressed_warnings:
		suppressed_warnings[s[0]] += 1
	else:
		print 'Warning:\t'+ '\t'.join(s)

def supress_error(*s):
	if s[0] in suppressed_warnings:
		suppressed_warnings[s[0]] -= 1
	else:
		print 'Error:  \t'+ '\t'.join(s)

#extra_stats = {'old_url':0, 'new_url':0}
def process_db_row_with_ghel(cursor, wiki):
	# Suppress trivial warnings that clog error report
	# TODO automate updating
	global suppressed_warnings
	if wiki == 'commonswiki': # Updated Sept 2013
		ghel.warn = supress_warn
		ghel.error = supress_error
		suppressed_warnings = {
			'CameraOverride':0,	# 69113
			'Duplicate param':0,# 69657
			'Assumed alt':  0,	# 11556
			'AvoidedTemplate':0,# 11091
			'Number  ':     0,  #  6675
			'RegionCase':   0,	#  3109 
			'Regionless':   0,	#  2269
			'GPS Altitude': 0,	#  1540
			'Region invalid':0,	#  1361
			# Unparsed      	#   795
			'UTF8params':   0, 	#   669
			# Headingless		#   564
			'Sourceless':   0,	#   555
			'Dim override': 0,	#   545
			'ParamCase':    0,	#   202
			'Too many colons':0,#   195 

		}
	elif wiki == 'cswiki': # Added Aug 2012
		ghel.warn = supress_warn
		suppressed_warnings = {
			'Too many colons':0,#  2155
			'Regionless': 0,    #  1944
			'Typeless':   0,    #   964
			'RegionCase': 0,    #   436
		}
	elif wiki == 'eswiki': # Added Aug 2012
		ghel.warn = supress_warn
		ghel.error = supress_error
		suppressed_warnings = {
			'Typeless': 0,      #  3227
			'Out of range': 0,	#   670
			'NoDigits': 0,  	#   500
			'Bad prefix': 0,	#   442
			'Missing colon': 0,	#   436
			'Too many colons':0,#   434
			'Regionless': 0,	#   419
		}
	elif wiki == 'fawiki': # Added Aug 2012
		ghel.warn = supress_warn
		suppressed_warnings = {
			#'UTF8params':  0,   # 1637
			'Nonconform type': 0,# 1361
			'Typeless':     0,   #  533
		}
	elif wiki == 'ukwiki': # Updated Aug 2012
		ghel.warn = supress_warn
		suppressed_warnings = {
			'Equalsign': 0, 	# 60006
		}
	elif wiki == 'zhwiki': # Added Aug 2012
		ghel.warn = supress_warn
		suppressed_warnings = {
			'UTF8params': 0,    #  2451
			'Empty subdiv': 0,  #  2447
			'ParamCase': 0,     #   355
		}
	elif wiki == 'newwiki': # Added June 2013
		ghel.warn = supress_warn
		ghel.error = supress_error
		suppressed_warnings = {
			# Nepal Wikipedia using non-ASCII inputs
			'UTF8params': 0,    #
			'NoDigits': 0,      #
		}
	elif wiki == 'ptwiki': # Added Sept 2013
		ghel.warn = supress_warn
		ghel.error = supress_error
		suppressed_warnings = {
			# Nepal Wikipedia using non-ASCII inputs
			'Number': 0,    	# 839
			#'Too many parameters': 0,	# 811
			'Typeless': 0,  	# 368
			'ValueError': 0,	# 321
		}
	else:
		suppressed_warnings = {}

	coord = ghel.Geolink()
	laststop = time.time()
	# Avoid MySQL client ran out of memory on Commons
	# And reduce latency
	def batchfetch(cursor, size=2000000):
		for i in xrange(100):
			subset = cursor.fetchmany(size)
			if not subset:
				break
			for row in subset:
				yield row
			sys.stdout.write("%s-%s rows : %s minutes" % (i*size, (i+1)*size, (time.time()-starttime)/60.0,))
			sys.stderr.write("%s-%s rows : %s minutes" % (i*size, (i+1)*size, (time.time()-starttime)/60.0,))
			sys.stdout.flush() # See where we're stalling

	for el_from, el_to, el_from_namespace in cursor.fetchall():#batchfetch(cursor):
		#if el_to.startswith("http://stable.toolserver.org"):
		#	ghel.warn("old_url", "stable.toolserver.org will be ignored soon", '[[?curid=%s]]'%el_from)
		#	extra_stats['old_url'] += 1
		#else:
		#	extra_stats['new_url'] += 1

		#coord = ghel.Geolink()
		# Avoid garbage collecting by reusing the previous object
		coord.__init__() # reset values
		if not coord.parse(el_to, defaultpagename="?curid=%s"%el_from):
			continue
		if coord.globe=="Earth":
			coord.globe=""

		if coord.region and len(coord.region) > 60:
			ghel.warn('DB Warn','Truncating region', '[[%s]]'%coord.pagename)
			coord.region = coord.region[:60]
		#if coord.globe and coord.globe.capitalize() not in ('', 'Mercury', 'Venus', 'Earth', 'Moon', 'Mars', 'Phobos', 'Deimos', 'Ceres', 'Ganymede', 'Callisto', 'Io', 'Europa', 'Mimas', 'Enceladus', 'Tethys', 'Dione', 'Rhea', 'Titan', 'Hyperion', 'Iapetus', 'Phoebe', 'Miranda', 'Ariel', 'Umbriel', 'Titania', 'Oberon', 'Triton', 'Pluto'):
		#	ghel.debug('Globe not in DB', '%s might not be in DB monitoring - dispenser\t[[%s]]' % (coord.globe, coord.pagename))
		# Insert data into database
		# 
		name = coord.pagename.replace('_', ' ')
		if coord.title:
			# See reverse diff: http://ja.wikipedia.org/?diff=33400046&oldid=34466697
			if len(coord.title.encode('utf-8')) <= 250:
				name = coord.title[0:255].encode('utf-8')
			else:
				ghel.error('long title', '%-8r\t[[%s]]'%(coord.title, coord.pagename))

		if wiki == 'commonswiki' and coord.pagename.startswith('File:'):
			if coord.classification == "object":
				if coord.type == "camera":
					ghel.warn('Conflict', '%-8r\t[[%s]]'%(coord.type, coord.pagename))
				else:
					pass
			elif coord.classification is None:
				if coord.type == "camera":
					pass
				elif '_type:camera' in el_to:
					ghel.warn('CameraOverride', '%-8r\t[[%s]]'%(coord.type, coord.pagename))
					coord.type="camera"
				elif coord.source in ('NARA', ):
					# NARA lists nearby cities
					pass
				#elif coord.type:
				#	pass
				#	ghel.warn('Invalid type', '%-8r\t[[%s]]'%(coord.type, coord.pagename))
				else:
					# error msg?  Not cam or obj ? Template not used? Use template? Template skipped?
					ghel.warn('AvoidedTemplate', '%-8r\t[[%s]]'%(coord.source or coord.type, coord.pagename))
					pass
			else:
				ghel.warn('unhandled class:', '%-8r\t[[%s]]'%(coord.classification, coord.pagename))

		if coord.type:
			if len(coord.type) > 24:
				ghel.error('type too long', '%-8r\t[[%s]]'%(coord.type, coord.pagename))
			if not coord.type.isalnum():
				ghel.warn('type bad char', '%-8r\t[[%s]]'%(coord.type, coord.pagename))
			coord.type = coord.type[:24].lower()
		if coord.globe == "":
			if not -180.0 <= coord.lng <= 180.0:
				ghel.debug('wrap around', '%-8r\t[[%s]]'%(coord.lng, coord.pagename))

#		if time.time()-laststop >= 0.100:
#			print "Processing took %f seconds for %s" % (time.time()-laststop, el_to)
#		laststop = time.time()

		# Limit POINT to 6 decimals and modulo to [-90,+90] and (-180,+180] 
		# because of MySQL's incomplete spatial implementation
		# Decimals accuracy: 8 ~= .1 cm, 7 ~= 1.1 cm, 6 ~= 11 cm (US Census), 5 ~= 111 cm (1.1 m)
		yield (
			el_from,
			coord.lat,
			coord.lng,
			coord.elevation,
			coord.heading,
			coord.dim or None,
			coord.type,
			coord.typesize,
			coord.region,
			coord.globe or '',
			coord.title==None or coord.title.encode('utf-8')==coord.pagename,
			el_from_namespace,
			name,
			'POINT(%.6f %.6f)'% (coord.lat if 90.0<=coord.lat<=90.0 else 90.0-abs((coord.lat+90.0)%360.0-180.0), 180.0-(180.0-coord.lng)%360.0),
			coord.digits,
			coord.raw_coord,
		)
		#del coord

def buildTable(wiki, refUrl=None, host=None, write=True):
	offset = 0
	limit  = 0#-1
	# FIXME tools.labsdb / Main wiki cross JOIN
	limit  = 5.5e6 # 'MySQL client ran out of memory' for commonswiki
	write_host = 'tools.labsdb'
	if limit < 0:
		offset = raw_input('offset [%d]: '%offset)       or offset
		limit  = int(raw_input('limit [5000]: ') or 5000)
		write  = raw_input('Simulation (don\'t write to the database) [Y]').lower() in ('n', 'no', 'write')
		if write:print "Truncating table..."
	
	def el_index_convert(url):
		#dBegin = len('https://') if url.startswith('https:') else len('http://')
		dBegin = url.index(':') + 3
		dEnd = url.index('/', dBegin)
		return url[:dBegin]+'.'.join(reversed(url[dBegin:dEnd].split('.')))+'.'+url[dEnd:]
	
	# Main db connection
	conn   = getConn(wiki, host=host, compress=True)
	cursor = conn.cursor()
	# Setup ghel to only recognize created
	existingGlobesOnly(wiki, host=host)
	#ghel_table = 'u_dispenser_p.coord_%s'%wiki
	ghel_table = 'u2815__p.coord_%s'%wiki
	coord_urls = [
		"http://toolserver.org/~geohack/geohack.php?%",
		# {{fullurl:tools:~geohack/LANG/PARAMS}}
		"https://toolserver.org/\\%7Egeohack/__/_%",
		# Unoffical build on WMF Labs
		"http://tools.wmflabs.org/geohack/geohack.php?%",
		"https://tools.wmflabs.org/geohack/geohack.php?%",
	]
	if wiki in legacy_stable:
		coord_urls.append("http://stable.toolserver.org/geohack/geohack.php?%")
	# Even older URLs
	if False:
		#coord_urls.append("http://www.kvaleberg.no/cgi-bin/coordinates.pl?coor=%")
		#coord_urls.append("http://kvaleberg.com/wiki/index.php/Special:Mapsources/")
		coord_urls.append("http://kvaleberg.com/extensions/mapsources/index.php?%") # 2005
		coord_urls.append("http://tools.wikimedia.de/~magnus/geo/geohack.php?%")	# 2006
		coord_urls.append("http://www.nsesoftware.nl/wiki/maps.asp?%")

	if refUrl:
		coord_urls.append(refUrl+"_%")
	cursor.execute("SELECT @@hostname, @@version, @@max_user_connections, UNIX_TIMESTAMP()-UNIX_TIMESTAMP(MAX(rc_timestamp)) FROM recentchanges;")
	(server_name, server_version, max_user_connections, replication_lag) = cursor.fetchall()[0]
	# At 3+ million coordinates Commons takes nearly 2 hours to rebuild
	# It may not be possible divide the query due to lacking indexes [untested]
	# 
	# Commons is currently using an unoffical build of GeoHack
	if wiki == 'commonswiki' and False:
		cursor.execute("""/* geodbcompiler.buildTable SLOW_OK LIMIT:7200 */
SELECT el_from, el_to
FROM externallinks
WHERE el_to LIKE "http://toolserver.org/~geohack/geohack.php?%";
""")
	else:
		# XXX TODO FIXME profile if this JOIN is too expensive
		cursor.execute("""/* geodbcompiler.buildTable SLOW_OK LIMIT:7200 */
SELECT el_from, el_index, page_namespace
FROM externallinks
JOIN page ON page_id=el_from
-- JOIN toolserver.namespace ON ns_id=page_namespace AND dbname=(SELECT DATABASE())
WHERE %s %s"""%(
	" OR ".join(("el_index LIKE ?",)*len(coord_urls)),
	"LIMIT %d,%d"%(offset,limit) if limit else '',
),	tuple(el_index_convert(url) for url in coord_urls))
	querytime = time.time()
	
	#print b'\xEF\xBB\xBF', # UTF-8 byte order mark
	print('# level \ttype    \tvalue   \tpagename')
	parambatch = process_db_row_with_ghel(cursor, wiki)
	# Local file system option, saves 30 sec
	#import tempfile
	#tmpf=tempfile.NamedTemporaryFile('wb', delete=False)
	#filename = tmpf.name
	##chmod +r filename
	filename='/tmp/ghel/%s.tmp'%ghel_table
	filename = "/user-data/geo/tmp/%s.tmp"%ghel_table
	#mkdir -p
	path = os.path.dirname(filename)
	if not os.path.exists(path):
		os.makedirs(path, mode=0o700)
	with open(filename, 'wb') as f:
		f.truncate(0)
		for params in parambatch:
			f.write(b'\t'.join(MySQL_format(s) for s in params))
			f.write(b'\n')
	#if extra_stats['old_url']>0:
	#	print extra_stats
	#	if extra_stats['old_url']*3 > extra_stats['new_url']:
	#		print 'legacy_stable.append(%r)'%wiki

	# Separate main report and statistics
	sys.stdout.flush()
	print #empty

	# Disconnect from read server and connect to write server
	# This also avoids connection reset issues from waiting too long
	delConn(wiki, host=host)
	#conn   = getConn(wiki, host=write_host, compress=True)
	conn   = getConn('u2815__p', host=write_host, compress=True)
	cursor = conn.cursor()

	transformtime = time.time()
	if write:
		createTable(cursor, "u2815__p.loadfile_ghel")
		cursor.execute("ALTER TABLE u2815__p.loadfile_ghel DISABLE KEYS")
		cursor.execute("LOAD DATA LOCAL INFILE '"+filename+"' INTO TABLE u2815__p.loadfile_ghel FIELDS TERMINATED BY '\\t' LINES TERMINATED BY '\\n' (gc_from,gc_lat,gc_lon,gc_alt,gc_head,gc_dim,gc_type,gc_size,gc_region,gc_globe,gc_primary,gc_namespace,gc_name,@point,@digits,@params) SET gc_location = GeomFromText(@point)")

		cursor.execute("SHOW WARNINGS")
		if cursor.rowcount not in (-1, 0):
			# Weird huh?  Oursql typically returns -1 for SELECTs
			for row in cursor:
				print 'Oursql Warning:', row
		# Duplicate removal
		cursor.execute("DROP TABLE IF EXISTS u2815__p.sort_ghel, u2815__p.ghel_sync")
		cursor.execute("CREATE TABLE u2815__p.sort_ghel LIKE u2815__p.loadfile_ghel")
		cursor.execute("ALTER TABLE u2815__p.sort_ghel DISABLE KEYS, ADD UNIQUE uniq_loc (gc_from, gc_name, gc_globe, gc_location)")
		cursor.execute("""/* geodbcompiler SLOW_OK */
INSERT INTO u2815__p.sort_ghel
SELECT * 
FROM u2815__p.loadfile_ghel AS orig
/* On duplicate keys, replace value unless NULL */
ON DUPLICATE KEY UPDATE
gc_alt    = IFNULL(VALUES(gc_alt),  sort_ghel.gc_alt),
gc_head   = IFNULL(VALUES(gc_head), sort_ghel.gc_head),
gc_dim    = IFNULL(VALUES(gc_dim),  sort_ghel.gc_dim),
gc_type   = IFNULL(VALUES(gc_type), sort_ghel.gc_type),
gc_size   = IFNULL(VALUES(gc_size), sort_ghel.gc_size),
gc_region = IFNULL(VALUES(gc_region), sort_ghel.gc_region)
/* gc_primary = LEAST(VALUES(gc_primary), sort_ghel.gc_primary) */
""")
		cursor.execute("SHOW STATUS LIKE 'Handler_update'")
		dupkeys = cursor.fetchall()[0][1] # XXX fragile
		# Remove primary flags when multiple primary coordinates are present
		# TODO lower COUNT(*) threshold, add more comments
		cursor.execute("""/* geodbcompiler SLOW_OK */
CREATE TEMPORARY TABLE u2815__p.prime_ghel (
  prime_id INT NOT NULL PRIMARY KEY
) ENGINE=MyISAM AS
SELECT gc_from AS prime_id
FROM u2815__p.sort_ghel 
GROUP BY gc_from 
HAVING COUNT(*) > 4 AND SUM(gc_primary) = COUNT(*)
""")
		x_b = cursor.rowcount
		cursor.execute("""/* geodbcompiler SLOW_OK */
UPDATE u2815__p.sort_ghel, u2815__p.prime_ghel
SET gc_primary=DEFAULT
-- No sure about adding this, may break alot of things but is correct
-- SET gc_name=DEFAULT
WHERE gc_from=prime_id
""")
		x_a = cursor.rowcount
		
		# FIXME tools.labsdb / Main wiki cross JOIN 
		# 
		# Main, File, Template, and Category
		# http://commons.wikimedia.org/w/index.php?diff=71273650
		cursor.execute("""/* geodbcompiler SLOW_OK */
CREATE TEMPORARY TABLE u2815__p.clustered_ghel (
  mp_location POINT NOT NULL PRIMARY KEY
) ENGINE=MyISAM AS 
SELECT gc_location AS mp_location
FROM u2815__p.sort_ghel
-- JOIN page ON page_id=gc_from
WHERE gc_primary=1 AND gc_namespace IN (0, 6, 10, 14)
GROUP BY gc_location
HAVING COUNT(*) >= 8
""")
		clusters = cursor.rowcount
		cursor.execute("""/* geodbcompiler SLOW_OK */
UPDATE u2815__p.sort_ghel
JOIN u2815__p.clustered_ghel ON gc_location = mp_location
SET gc_primary=DEFAULT
WHERE gc_primary=1
""")
		cluster_coords = cursor.rowcount

		
		# Scale DMS/D 
		# 
		# 
		# ALTER TABLE u2815__p.sort_ghel DROP COLUMN gc_location_res


		# TODO add scale by input resolution
		# TODO setup a cache flushing system
		#  cursor.execute("TRUNCATE TABLE u2815__p.region_cache")
		cursor.execute("""/* geodbcompiler SLOW_OK */
CREATE TABLE IF NOT EXISTS u2815__p.region_cache (
	grc_geom   POINT     NOT NULL PRIMARY KEY,
	grc_region BINARY(2) NULL
) ENGINE=MyISAM;
""")
		# 2500 keeps under 10 min (21 ms lookups)
		cursor.execute("""/* geodbcompiler SLOW_OK */
SELECT DISTINCT gc_location, X(gc_location), Y(gc_location)
FROM u2815__p.sort_ghel
LEFT JOIN u2815__p.region_cache ON grc_geom=gc_location
WHERE gc_region IS NULL AND grc_geom IS NULL
GROUP BY gc_location
-- LIMIT 2500
LIMIT 3000000
""")
		cursor.executemany("INSERT u2815__p.region_cache (grc_geom, grc_region) VALUES (?, ?)", 
		((geom, getRegion(cursor, lat, lng),) for geom, lat, lng in cursor.fetchall()))
		region_lookups = cursor.rowcount
		
		# SELECT COUNT(*) FROM u2815__p.region_cache WHERE grc_geom IS NOT NULL;
		# ALTER TABLE u2815__p.region_cache ORDER BY grc_geom
		# DELETE FROM u2815__p.region_cache WHERE grc_region IS NULL;
		cursor.execute("""/* geodbcompiler SLOW_OK */
UPDATE u2815__p.sort_ghel
JOIN u2815__p.region_cache ON grc_geom=gc_location
SET gc_region=grc_region
WHERE gc_region IS NULL AND grc_region IS NOT NULL;
""")
		region_augment = cursor.rowcount
#		# FIXME tools.labsdb / Main wiki cross JOIN 
#		cursor.execute("""/* geodbcompiler SLOW_OK */
#SELECT COUNT(*)
#FROM u2815__p.sort_ghel
#JOIN page ON page_id=gc_from
#-- LEFT JOIN redirect ON rd_from=gc_from
#-- WHERE rd_from IS NOT NULL
#-- AND rd_fragment;
#WHERE page_namespace=0 AND page_is_redirect=1;
#""")
#		redirect_coordinates = cursor.fetchall()[0][0]
		
		#
		cursor.execute("ALTER TABLE u2815__p.sort_ghel DROP INDEX uniq_loc, ENABLE KEYS")
		cursor.execute("CREATE TABLE IF NOT EXISTS "+ghel_table+" LIKE u2815__p.sort_ghel")
		cursor.execute("RENAME TABLE "+ghel_table+" TO u2815__p.deleteme, u2815__p.sort_ghel TO "+ghel_table)
		cursor.execute("DROP TABLE u2815__p.deleteme, u2815__p.loadfile_ghel")

		# Fill in cardinality and other statistics for MyISAM tables
		cursor.execute("ANALYZE TABLE "+ghel_table)
		
		## Remove temp file upon successful completion
		#import os;os.remove(filename)
		#import os;os.chmod(filename, 00664)
		# Let others use the raw data
		#store = "/mnt/user-store/dispenser"
		store = "/user-data/geo"
		import shutil; shutil.move(filename, "%s/coord_%s_p.tab" % (store, wiki) )
	else:
		print 'Ran with simulate flag on'
		dupkeys = ''

	conn.commit()  # keep changes
	

	print "Performance: Extract %#3.2f, Transform %#3.2f, Load %#3.2f min" % ((querytime-starttime)/60.0, (transformtime-querytime)/60.0, (time.time()-transformtime)/60.0,)
	# Coordinates in articles
	# add gc_globe=''?
	#cursor.execute("SELECT COUNT(*), COUNT(DISTINCT gc_from) FROM "+ghel_table+" JOIN page ON page_id=gc_from WHERE page_namespace=0 -- SLOW_OK")
	cursor.execute("SELECT COUNT(*), COUNT(DISTINCT gc_from) FROM "+ghel_table+" WHERE gc_namespace=0")
	print '%d coordinates in %s articles' % cursor.fetchall()[0]
	# Coordinates in all namespaces
	cursor.execute("SELECT COUNT(*), COUNT(DISTINCT gc_from) FROM "+ghel_table)
	print '%d coordinates across %s pages' % cursor.fetchall()[0]
	if dupkeys:
		print "%s duplicates merged" % dupkeys
	if True:
		print '%s regions added (%d not cached)'%(region_augment, region_lookups)
		print '%d primary flags removed in %d clusters' % (cluster_coords, clusters)
		# We need to express this better
		print '%d primary flags removed from %d pages' % (x_a, x_b)
#		#
#		print '%d coordinate on redirect pages' % (redirect_coordinates,)
	if ghel.typelessCount:
		print '%d coordinates don\'t use "type:"' % ghel.typelessCount
	if ghel.prependCount:
		print '%d coordinates use "type_"' % ghel.prependCount
	for key, value in sorted(suppressed_warnings.iteritems()):
		if value:
			print "%5s %s %s suppressed"%(abs(value), key, "warnings" if value>0 else "errors",)
	if wiki in legacy_stable:
		print "Legacy stable.toolserver.org URLs enabled.  Please change templates to point to http://toolserver.org/~geohack/ instead"
	if refUrl:
		print "Base URL: %s" % refUrl
	print "Extract server: MySQL %s on %s"%(server_version, server_name,)
	cursor.execute("SELECT COUNT(*) AS rows, gc_type FROM "+ghel_table+" GROUP BY gc_type ORDER BY gc_type ASC")
	print 'rows\ttype'
	for t in cursor:
		print '% 6s\t%s'%t
	# Close SQL cursors
	cursor.close()
	conn.close()

# ~/pyscripts/geodbcompiler.py -wiki:commonswiki -sync
def syncTable(wiki, refUrl, since, host=None):
	# date +"%Y%m%d%H0000" -d "1 hour ago"
	conn = getConn(wiki, host=host)
	cursor = conn.cursor()
	ghel_table = 'u2815__p.coord_%s'%wiki

	cursor.execute('DROP TABLE IF EXISTS u2815__p.ghel_sync')
	#cursor.execute('CREATE TABLE u2815__p.ghel_sync LIKE '+ghel_table)
	#cursor.execute('INSERT INTO u2815__p.ghel_sync SELECT * FROM '+ghel_table)
	#ghel_table = 'u2815__p.ghel_sync'

	cursor.execute('SET @since = ?', (since.ljust(14, '0'),))
	cursor.execute('SET @since = (SELECT DATE_FORMAT(NOW() - INTERVAL 25 HOUR, "%Y%m%d%H%i%S"));')
	cursor.execute('SET @cutoff= (SELECT DATE_FORMAT(NOW() - INTERVAL 1 SECOND,"%Y%m%d%H%i%S"));')
	# TODO Template/transclusion support
	'''
	CREATE TEMPROARY TABLE u2815__p.updates
	INSERT INTO u2815__p.update
	SELECT STRAIGHT_JOIN IFNULL(rc_cur_id, tl_from)
	FROM recentchanges
	LEFT JOIN templatelinks ON tl_namespace=rc_namespace AND tl_title=rc_title
	WHERE rc_timestamp >= @since;
	# Plus some stuff to filter it down
	'''
	# TODO check on performance using el_index
	cursor.execute('''/* geodbcompiler.syncTable SLOW_OK LIMIT:900 */
SELECT SQL_NO_CACHE DISTINCT
  el_from,
  el_to
FROM externallinks
JOIN recentchanges ON rc_cur_id=el_from
WHERE rc_timestamp BETWEEN @since AND @cutoff
AND el_to LIKE ?
''', (refUrl+"_%", ))

	print '# level \ttype    \tvalue   \tpagename'
	cursor.execute("DROP TABLE IF EXISTS u2815__p.sort_ghel")
	cursor.execute("CREATE TABLE u2815__p.sort_ghel LIKE "+ghel_table)
	cursor.execute("ALTER TABLE u2815__p.sort_ghel DISABLE KEYS, ADD UNIQUE uniq_loc (gc_from, gc_name, gc_globe, gc_location)")
	cursor.executemany('''INSERT INTO u2815__p.sort_ghel
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GeomFromText(?))
/* On duplicate keys, replace value unless NULL */
ON DUPLICATE KEY UPDATE
gc_alt    = IFNULL(VALUES(gc_alt),  sort_ghel.gc_alt),
gc_head   = IFNULL(VALUES(gc_head), sort_ghel.gc_head),
gc_dim    = IFNULL(VALUES(gc_dim),  sort_ghel.gc_dim),
gc_type   = IFNULL(VALUES(gc_type), sort_ghel.gc_type),
gc_size   = IFNULL(VALUES(gc_size), sort_ghel.gc_size),
gc_region = IFNULL(VALUES(gc_region), sort_ghel.gc_region)
/* gc_primary = LEAST(VALUES(gc_primary), sort_ghel.gc_primary) */
''', (parts[:-1] for parts in process_db_row_with_ghel(cursor, wiki)))
	rows_added = cursor.rowcount
	cursor.execute('''
/* geodbcompiler.syncTable */
DELETE QUICK %s
FROM %s
JOIN recentchanges ON rc_cur_id=gc_from
WHERE rc_timestamp BETWEEN @since AND @cutoff;
''' % (ghel_table,ghel_table) )
	rows_removed = cursor.rowcount
	cursor.execute('''
	# Merge into large table
	INSERT INTO '''+ghel_table+'''
	SELECT *
	FROM u2815__p.sort_ghel
	''')
	rows_net = rows_added - rows_removed

	## http://dev.mysql.com/doc/refman/5.1/en/server-status-variables.html
	#cursor.execute("SHOW STATUS WHERE Variable_name IN ('Handler_delete', 'Handler_write','Com_insert','Com_stmt_execute','Com_stmt_fetch');")
	#cursor.execute("SHOW STATUS")
	#print '\n'.join('\t'.join(repr(y) for y in x) for x in cursor.fetchall())
	conn.commit()

	# Show statistics
	# 
	# Compare to https://commons.wikimedia.org/wiki/Special:MostLinkedTemplates
	cursor.execute("SELECT COUNT(*) FROM "+ghel_table)
	(coord_count,), = cursor.fetchall()
	print 'coord_count: ', coord_count
	#print "Update %d coordinate (%s total) across %d pages" % (coords, coord_count, pages)
	print 'Incremental update: Added/removed/net: %(rows_added)d/%(rows_removed)d/%(rows_net)+d' % locals()
	('''
SELECT COUNT(*) -- new.gc_from, new.gc_name
FROM u2815__p.ghel_sync AS new
LEFT JOIN u2815__p.coord_commonswiki  AS old ON old.gc_from=new.gc_from
WHERE old.gc_from IS NULL;
	''')
	#(new_count,), = cursor.fetchall()
	#print 'new_count: ', new_count
	conn.close()

def main():
	refUrl=""
	host = None
	dbname = 'u2815__p'
	wiki = ''
	since = ''
	write = True
	
	# get args from command line
	for arg in sys.argv[1:]:
		if arg.startswith('-wiki:'):
			wiki = arg[6:]
		elif arg.startswith('-offset:'):
			offset = int(arg[8:])
		elif arg.startswith('-limit:'):
			limit = int(arg[7:])
		elif arg.startswith('-refUrl:'):
			refUrl = arg[8:]
		elif arg.startswith('-dbname:'):
			dbname = arg[8:]
		elif arg.startswith('-host:'):
			host = arg[6:]
		elif arg.startswith('-since:'):
			since = arg[7:]
		elif arg.startswith('-help') or arg == '-h' or arg == '--help':
			print __doc__
			return
		elif arg.startswith('-simulate'):
			write = False
		elif arg.startswith('-raise'):
			print 'Turning warning into exceptions'
		elif arg.startswith(('-create', '-rebuild', '-sync')):
			# options used later
			pass
		else:
			print "Argument not understood", arg

	# Prompt for values?
	if not wiki:
		print "Use -help to see all command line options"
		wiki   = raw_input('Wiki name [%s]: '%wiki) or wiki
		print "SQL server: %s" % wiki.replace('_', '-') + '-p.userdb.toolserver.org'
		#dbname     = raw_input('Coordinate database [%s]: ' % dbname)  or dbname
		write  = raw_input('Simulation (don\'t write to the database) [Y]').lower() in ('n', 'no', 'write')
		if write:print "Truncating table..."
	else:
		# turn warnings into exceptions
		cgitb.enable(logdir='/home/dispenser/public_html/cgi-bin/tracebacks/', format="html")
		import warnings; warnings.simplefilter("error")

	
	# select the part to run
	for arg in sys.argv[1:]:
		#if arg.startswith('-create'):
		#	createTable(dbname, wiki)
		if arg.startswith('-rebuild'):
			buildTable(wiki, refUrl, host=host, write=write)
		elif arg.startswith('-sync'):
			#HACK
			#refUrl="http://toolserver.org/~geohack/geohack.php?"
			refUrl="http://tools.wmflabs.org/geohack/geohack.php?"
			syncTable(wiki, refUrl, since, host=host)

if __name__ == "__main__" :
	try:
		main()
	finally:
		print "Completed in %#3.2f min" %((time.time()-starttime)/60.0,)

