#!/usr/bin/env python
# -*- coding: utf-8  -*-
# TODO: Decide how to handle HTTP redirects and wiki redirects
import urllib, requests, oursql, gzip, re
import time; StartTime = time.time()

mysql_byte_escape = dict((chr(i), chr(i)) for i in range(256))
mysql_byte_escape.update({
    # Bytes escape
    b'\0':   b'\\0',
    b'\b':   b'\\b',
    b'\n':   b'\\n',
    b'\r':   b'\\r',
    b'\t':   b'\\t',
    b'\x16': b'\\Z',
    b'\\':   b'\\\\',
})
def MySQL_format(s, encoding='utf-8',
        ## HACK: hand-optimized bytecode; turn globals into locals
        bytes=bytes,
        dict=dict,
        float=float,
        int=int,
        isinstance=isinstance,
        list=list,
        long=long,
        str=str,
        tuple=tuple,
        unicode=unicode,
    ):
    if s is None:
        return b'\\N'
    elif isinstance(s, bytes):
        return b''.join(map(mysql_byte_escape.__getitem__, s))
    elif isinstance(s, unicode):
        return b''.join(map(mysql_byte_escape.__getitem__, s.encode(encoding)))
    elif isinstance(s, bool):
        return b'1' if s else b'0'
    elif isinstance(s, (int, long)):
        return bytes(s)
    elif isinstance(s, float):
        # repr() does not round unlike str()
        return repr(s)
    else:
        raise TypeError

js_escaped = dict((chr(i), chr(i) if i > 31 else b'\\x%02x'%i) for i in range(256))
js_escaped.update({
	# IE < 9 doesn't support \v
	b'\b':  b'\\b',
	b'\t':  b'\\t',
	b'\n':  b'\\n',
	b'\f':  b'\\f',
	b'\r':  b'\\r',
	b'"':	b'\\"', # \" may confuse the HTML parser
	b'/':	b'\\/', # May break regular expressions
	b'\\':  b'\\\\',
})

def jsescape(s, encoding='utf-8',
        ## HACK: hand-optimized bytecode; turn globals into locals
        bytes=bytes,
        dict=dict,
        float=float,
        int=int,
        isinstance=isinstance,
        list=list,
        long=long,
        str=str,
        tuple=tuple,
        unicode=unicode,
    ):
	if s is None:
		return b'null'
	elif isinstance(s, bool):
		return b'true' if s else b'false'
	elif isinstance(s, (int, long, float)):
		return bytes(s)
	elif isinstance(s, bytes):
		return b'"'+b''.join(map(js_escaped.__getitem__, s))+b'"'
	elif isinstance(s, unicode):
		# XXX Incorrect, just avoid Unicode control characters
		return b'"'+b''.join(map(js_escaped.__getitem__, s.encode('utf-8')))+b'"'
	elif isinstance(s, list):
		return b'['+b','.join(jsescape(item, encoding) for item in s)+b']'
	elif isinstance(s, dict):
		return b'{'+b','.join("%s:%s"%(jsescape(key, encoding), jsescape(value, encoding)) for key, value in s.iteritems())+b'}'
		# TODO implement float with NaN, Infinity
		#
	elif True:
		return bytes(s)
	else:
		raise TypeError("Not implemented for %s"%type(s))

timings = []
def logtime(event_name):
	global timings
	timings.append((event_name, time.time(),))
	print "%7.1f\t%s"% (time.time()-StartTime, event_name)

def timereport():
	last = StartTime
	lout = []
	for event_name, sec in timings:
		lout.append('%7.3f %7.3f    %s'%(sec-StartTime, sec-last, event_name, ))
		last = sec
	return '\n'.join(lout)

connections = {}
def getConn(dbname, host=None, reconnect=False):
    if not dbname.endswith('_p'): dbname+='_p'
    if (host,dbname) not in connections or reconnect:
        connections[host,dbname] = oursql.connect(
            db=dbname,
            host=host or dbname.replace('_', '-')+'.rrdb',
            read_default_file="/home/dispenser/.my.cnf",
            charset=None,
            use_unicode=False,
            raise_on_warnings=False,
			local_infile=True
        )
    return connections[host,dbname]

cursor = getConn('enwiki').cursor()
logtime('Got MySQL cursor')
if True:
	# Get namespaces
	req=requests.post("http://en.wikipedia.org/w/api.php", data={
		"action":"query",
		"meta":"siteinfo",
		"siprop":"namespaces|namespacealiases",
		"format":"json",
		"utf8":"yes",
	})
	ns_inverse = {}
	
	response_json = req.json()
	for ns_props in response_json["query"]["namespaces"].itervalues():
		ns_id = ns_props['id']
		ns_name = ns_props['*']
		# XXX string matching hack
		ns_inverse[ns_name.capitalize()] = ns_id
	
	logtime("Imported namespaces")
	# ['query']['namespacealiases'] is auto http redirected to the canonical name
	# investigation is still needed 

# interwiki links filter

existingpages={}
def init_pageIds():
	# FIXME make work for new and red linked pages
	# Load and Hash all article titles
	def splitline(f, int=int):
		next(f) # Skip header
		for line in f:
			pgid, pgns, pgt = line[:-1].split('\t')
			if pgns == 0:
				yield int(pid), (int(pns), pt)
	# mysql -e "SELECT page_id, page_namespace, page_title FROM page" > page_id-enwiki.tsv
	with open("page_id-enwiki.tsv") as f:
		global existingpages
		existingpages=dict((y,x) for (x,y) in splitline(f))
	logtime("Imported page_ids")
	# SQL version
	#cursor.execute("SELECT page_namespace, page_title, page_id FROM page WHERE page_namespace=0")
	#existingpages=dict((((page_namespace, page_title), page_id) for page_namespace, page_title, page_id in cursor))
	# TODO Use negative values for non-existing pages
	#global nextUnusedId
	#with open() as f:
	#	
	#nextUnusedId=min(0,min(existingpages.itervalues()))

def transform(filename):
	if existingpages == {}:
		init_pageIds()
	with open(filename+'.out', 'wb') as f:
		f.truncate(0)
		logtime("Open output file %s.out"%filename)
		#for line in open(filename, 'r+b'):
		for line in gzip.open(filename+'.gz', "rb"):
			items = line[:-1].split(b' ')
			if len(timings) < 5 : logtime("Decompressed?")
			if len(items) != 4:
				print "Warning malformed line"
				print line
				continue
			vc_wiki, vc_title, vc_count, vc_traffic = items
			# Normalize wiki name
			vc_wiki = vc_wiki.lower()
			
			# Only process interested wikis (English & English Mobile Wikipedia)
			if vc_wiki not in (b'en', b'en.mw'):
				continue
			
			# Skip invalid titles
			if re.search(r'[[\]{|}<\n\r\t>]', vc_title):
				continue

			
			# Normalize title
			# %28 -> (, %20 -> _ 
			try:
				vc_title = urllib.unquote(vc_title)
				vc_title = vc_title.replace(' ', '_').strip('_')
				if True:
					# Decode unicode characters
					try:    vc_title = vc_title.decode('utf-8')
					except: vc_title = vc_title.decode('latin-1')
					vc_title = vc_title[0:1].upper() + vc_title[1:]
					vc_title = vc_title.encode('utf-8')
				# 
				vc_ns_index = vc_title.find(':')
				if vc_ns_index >= 0:
					# XXX .capitalize() crud matching hack
					vc_ns = ns_inverse.get(vc_title[0:vc_ns_index].capitalize(), 0)
					if vc_ns:
						vc_title = vc_title[vc_ns_index:]
				else:
					vc_ns = 0
			except Exception, e:
				print repr(vc_title)
				print e
				continue
				
			# Prune non-existing pages
			#if existingpages:
			#	if vc_title not in existingpages:
			#		continue
			vc_id = existingpages.get((vc_ns, vc_title), 0)
			if vc_id == 0: continue # skip non-existant page
				
			f.write(b'\t'.join((MySQL_format(s) for s in (
				filename[11:].replace('-', ''),
				vc_wiki,
				vc_wiki.endswith('.mw'),
				vc_id,
				vc_ns,
				vc_title,
				vc_count,
				vc_traffic,
			))) )
			f.write(b'\n')
		logtime("Closed output file %s" % f.name)

def load(filename):
		cursor.execute("""
LOAD DATA LOCAL INFILE '"""+filename+"""'
  INTO TABLE u_dispenser_p.viewcounter
/* Here it the same as the default.  See manual more formats like CSV */
  FIELDS TERMINATED BY '\\t' 
  LINES TERMINATED BY '\\n' 
  (@timestamp, pc_wiki, pc_mobile, pc_page, pc_namespace, pc_title, pc_views, pc_traffic)
  SET pc_timestamp = TIMESTAMP(@timestamp),
      pc_date      = DATE(TIMESTAMP(@timestamp)),
	  pc_samples   = 1
""")
		logtime('Load %s rows from %s into table' % (cursor.rowcount, filename, ))

def json_export(filename):
	cursor.execute("""
SELECT pc_page, pc_mobile, pc_date, pc_namespace, pc_title, pc_views, pc_traffic, hourly
FROM u_dispenser_p.dailycount
/*LIMIT 200000*/
""")
	""" Bigquery Schema
[
      {"name":"pc_page",      "mode":"required", "type":"INTEGER"},
      {"name":"pc_mobile",    "mode":"required", "type":"BOOLEAN"},
      {"name":"pc_date",      "mode":"required", "type":"TIMESTAMP"},
      {"name":"pc_namespace", "mode":"required", "type":"INTEGER"},
      {"name":"pc_title",     "mode":"required", "type":"STRING"},
      {"name":"pc_views",     "mode":"required", "type":"INTEGER"},
      {"name":"pc_traffic",   "mode":"required", "type":"INTEGER"},
      {"name":"pc_samples",   "mode":"required", "type":"INTEGER"},
      {"name":"pc_hourly",    "mode":"repeated", "type":"RECORD",
       "fields": [
          {"name":"hour",  "mode":"required", "type":"STRING"},
          {"name":"views", "mode":"required", "type":"INTEGER"}
        ]}
]
	"""
	logtime("Queried data out")
	with open(filename, 'wb') as f:
		for pc_page, pc_mobile, pc_date, pc_namespace, pc_title, pc_views, pc_traffic, hourly in cursor:
		#TODO fix timestamp
			f.write('{"pc_page":%s, "pc_mobile":%s, "pc_date":%s, "pc_namespace":%s, "pc_title":%s, "pc_views":%s, "pc_traffic":%s, "pc_samples":%s, "pc_hourly":[%s]}\n' % (
				tuple(jsescape(s) for s in (pc_page, pc_mobile==1, "2014-09-24 00:00", pc_namespace, pc_title, pc_views, pc_traffic,))+
				(', '.join('{"hour":"%s", "views":%s}'%(s[11:13], s[20:s.rfind(',')]) for s in hourly.split('|')),)
			))
		logtime("Wrote JSON %s" % f.name)

# Load
def createTable():
	cursor.execute("DROP TABLE IF EXISTS u_dispenser_p.viewcounter")
	cursor.execute("""
CREATE TABLE u_dispenser_p.viewcounter (
	pc_wiki     BINARY(8)        NOT NULL,
	pc_mobile   BOOL             NOT NULL,
	pc_timestamp TIMESTAMP       NOT NULL DEFAULT 0,
	pc_date     DATE             NOT NULL,
	pc_page     INT(10) UNSIGNED NOT NULL, 
	pc_namespace INT             NOT NULL,
	pc_title    VARBINARY(255)   NOT NULL,
	pc_views    INT    UNSIGNED  NOT NULL,
	pc_traffic  BIGINT UNSIGNED  NOT NULL,
	pc_samples  INT    UNSIGNED  NOT NULL
) ENGINE = MyISAM;
""")
	logtime('Created table')
def sumcounts():
	logtime("Start db stuff")
	#cursor.execute("SET group_concat_max_len = 4096") # 40 * 24 = 960
	cursor.execute("DROP TABLE IF EXISTS u_dispenser_p.dailycount, u_dispenser_p.tmp_uniq")
	cursor.execute("CREATE TABLE u_dispenser_p.tmp_uniq LIKE u_dispenser_p.viewcounter")
	cursor.execute("CREATE UNIQUE INDEX page_timestamp ON u_dispenser_p.tmp_uniq (pc_page, pc_mobile, pc_timestamp)")
	logtime("Added index")
	cursor.execute("""
INSERT INTO u_dispenser_p.tmp_uniq
SELECT * 
FROM u_dispenser_p.viewcounter AS orig
ON DUPLICATE KEY UPDATE
pc_views   = VALUES(pc_views)   + tmp_uniq.pc_views,
pc_traffic = VALUES(pc_traffic) + tmp_uniq.pc_traffic,
pc_samples = VALUES(pc_samples) + tmp_uniq.pc_samples
""")
	logtime("Merged duplicate entries")
	cursor.execute("ALTER TABLE u_dispenser_p.tmp_uniq DROP INDEX page_timestamp, ADD INDEX page_date (pc_page, pc_mobile, pc_date)")
	logtime("Switched indexes")
	cursor.execute("""
CREATE TABLE u_dispenser_p.dailycount ENGINE=MyISAM AS
SELECT pc_page, pc_mobile, pc_date, pc_namespace, pc_title,
  CAST(SUM(pc_views) AS UNSIGNED INT) AS pc_views,
  CAST(SUM(pc_traffic) AS UNSIGNED) AS pc_traffic, 
  CAST(SUM(pc_samples) AS UNSIGNED INT) AS pc_samples,
  GROUP_CONCAT(CONCAT(pc_timestamp, "=", pc_views, ",", pc_traffic) SEPARATOR "|") AS hourly
FROM u_dispenser_p.tmp_uniq FORCE INDEX (page_date)
GROUP BY pc_page, pc_mobile, pc_date;
""")
	logtime("Ran date reduction query")

if __name__ == "__main__":
	a = "pagecounts-20140924-140000"
	date= "20140924"
	#print 'wget "http://dumps.wikimedia.org/other/pagecounts-raw/2014/2014-09/%s.gz"' % a
	#print 'md5sum %s.gz' % a
	#createTable()
	for i in range(00, 24):
		#transform("pagecounts-20140924-%02d0000"%i)
		#load(     "pagecounts-20140924-%02d0000.out"%i)
		pass
	sumcounts()
	json_export("20140924.json")
	# TODO shell out to call gzip
	logtime("Finished")

	print timereport()
