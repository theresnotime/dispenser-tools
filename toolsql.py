#!/usr/bin/env python
# -*- coding: utf-8  -*-
#
#
"""



Workaround for img_metadata and cl_sortkey
curs.execute("SELECT HEX(img_metadata) FROM image LIMIT 1")
for img_metadata_hex, in curs:
	img_metadata = binascii.a2b_hex(img_metadata_hex)
	img_metadata_dict = phpserialize.loads(img_metadata)


Python Database API Specification v2.0
https://www.python.org/dev/peps/pep-0249/

import toolsql
curs = toolsql.getConn('enwiki').cursor()
curs.execute("select 1, 1.00, 'bigger', X'1b' , Point(0, 0)")
for desc in curs.description: print desc



"""
import tempfile, time, os
import oursql
import inspect
from oursql import errnos
from oursql import Error, InterfaceError, DatabaseError, OperationalError, ProgrammingError
#print '\n'.join(['%5s: %s'%(b,a) for a,b in sorted(oursql.errnos.iteritems(), key=lambda (a,b): b)])


#UseQueryKiller = True

# Fun errors to catch
# Something went wrong with the database
# 1040 "Too many connections":
# 1053 "Server shutdown in progress": Connected too long?
# 1226 "User %r has exceeded the %r resource": Too many user connections
# 1267 "Illegal mix of collation": s3 is still running MySQL 4
# 1290 "--read-only option"
# 1317 "Query execution was interrupted" (query-killer)
# 2006 "MySQL server has gone away":
# 2013 "Lost connection to MySQL server during query":
# 2014 "Commands out of sync; you can't run this command now":
# 2027 "Malformed packet"

# LOAD DATA escaper
# TODO look through  /usr/lib/python2.7/json/encoder.py for improvements
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
	## HACK: optimized bytecode: turn globals into locals
	bytes=bytes, unicode=unicode,
	float=float, int=int, long=long, bool=bool,
	isinstance=isinstance, repr=repr):
	" "
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

def like_escape(s, escape=u'\\'):
	" "
	return s.replace(escape, escape+escape).replace(u'_', escape+u'_').replace(u'%', escape+u'%')

# FIXME oursql doesn't set err.message use err.args[1] for now
class QueryTimedOut(oursql.OperationalError):
	"""QueryTimedOut"""
	pass
	#def __init__(self, message, errno, extra):
	#	# Call the base class constructor with the parameters it needs
	#	return super(oursql.OperationalError, self).__init__(message=message, errno=errno, extra=extra)


class UnicodeCursor(oursql.Cursor):
	" MySQLdb like cursor which client side buffers rows "
	@classmethod
	def __init__(self, cursor_class, group_concat_max_len=1000000, *args, **kwargs):
		self.resultset = []
		self.rowcount = -1
		self.group_concat_max_len = group_concat_max_len
		self.elapsedtime = -1
	
	def execute(self, query, params=(), plain_query=False, decode_errors='strict', max_time=None):
		# FIXME! img_metadata contains binary data, decode like: phpserialize.loads(img_metadata)
		self.rowcount = -1
		self.elapsedtime = -1
		execute_start = time.time()
		try:
			if isinstance(query, bytes):   query = query.decode('utf-8')
			if max_time == 0: raise ValueError("max_time cannot be zero")
			if self.group_concat_max_len != None:
				super(UnicodeCursor, self).execute("SET SESSION group_concat_max_len = %d;" % self.group_concat_max_len)
				self.group_concat_max_len = None # only first run
			#if not UseQueryKiller:
			#	# https://wikitech.wikimedia.org/wiki/Help:Toolforge/Database#Query_Limits
			#	# https://mariadb.com/kb/en/library/aborting-statements/
			#	super(UnicodeCursor, self).execute("SET max_statement_time = %d;" % max_time)
			
			# https://stackoverflow.com/questions/900392/getting-the-caller-function-name-inside-another-function-in-python
			stack = inspect.stack()
			#try:
			#	with open('test.stack.log', 'w') as f:
			#		f.write(repr(stack))
			#except Exception, e: pass
			query_head = u"/**%s.%s() LIMIT:%s**/" % (os.path.basename(os.sys.argv[0][:-3]), stack[1][3], max_time,)
			# XXX Turn off while cluster=labsdb still exists
			## XXX Experimentally turn this on
			#if max_time > 0 and query.startswith('SELECT '): 
			#	query_head += u'SET STATEMENT max_statement_time=%s FOR ' % (max_time,)
			params = tuple(s.encode('utf-8') if isinstance(s, unicode) else s for s in params)
			super(UnicodeCursor, self).execute((query_head + query).encode('utf-8'), params, plain_query)
			self.rowcount = super(UnicodeCursor, self).rowcount
			if self.rowcount==0 or not super(UnicodeCursor, self)._statements:
				# No results or ??
				return
			# Buffer results client side to avoid lag
			self.resultset = super(UnicodeCursor, self).fetchall()
			if self.rowcount == -1:
				self.rowcount = len(self.resultset)
			# MySQL's default max packet length is 1 KB, truncating the rest
			# Truncation may occur during a UTF-8 sequence, so we unsafely ignore it
			# Since GROUP_CONCAT truncates strings, we have unicode errors
			# TODO use phpserialize.loads() on img_metadata
			self.resultset = [tuple(s.decode('utf-8', errors=decode_errors) if isinstance(s, bytes) else s for s in row) for row in self.resultset]
#		except UnicodeDecodeError:
#			print '<!--', (query_head + query).replace('%', '%%').replace('?', '"%s"') % params, '-->'
#			raise
		# https://mariadb.com/kb/en/library/mariadb-error-codes/
		except oursql.DatabaseError as e:
			#if e.errno == errnos['ER_QUERY_INTERRUPTED'] and time.time() - execute_start > max_time:
			# Queries can be killed at any stage of execution from being prepared to sorting results
			# 1317 query was killed
			# InternalError(1028, 'Sort aborted
			# ProgrammingError: (1034, 'Create index by sort failed'
			if time.time() - execute_start >= max_time > 0:
				raise QueryTimedOut(*e)
				#exception = QueryTimedOut(*e)
				#exception.cursor = self
				#raise exception
			elif e.errno in ( # Wrong error class in oursql
				#dict((v,k) for (k,v) in oursql.errnos.items()).get(1226)
				errnos['ER_USER_LIMIT_REACHED'],
				errnos['ER_QUERY_INTERRUPTED'],
				errnos['ER_NEED_REPREPARE'],
			):
				raise oursql.OperationalError(*e)
			else:
				raise
		except oursql.UnknownError as e:
			if e.errno == 1969: # ER_STATEMENT_TIMEOUT
				raise QueryTimedOut(*e)
			else:
				raise
		finally:
			self.elapsedtime = time.time() - execute_start

	def fetchall(self):
		return self.resultset

	def fetchmany(self, size=None):
		if size == None: 
			size = self.arraysize
		if not self.resultset:
			return []
		results = self.resultset[0:size]
		del self.resultset[0:size]
		return results

	def fetchone(self):
		if self.resultset:
			return self.resultset.pop(0)
		else:
			return None
	
	def loaddata(self, query, parambatch, encoding='utf-8'):
		"""
		def myiter():
			yield ns, title
		cursor.loaddata('''
			LOAD DATA LOCAL INFILE '%(tmpfile)s'
			INTO TABLE u2815__p.watchlistraw
			(wr_namespace, wr_title)
		''', myiter)
		"""
		with tempfile.NamedTemporaryFile(prefix='loaddata') as temp:
			# Extra safety while tempfile._RandomNameSequence.chracters does not contain ' and "
			if '"' in temp.name or "'" in temp.name:
				raise Exception("tempfile used \' or \" in the filename")

			for row in parambatch:
				temp.write(b'\t'.join(MySQL_format(item, encoding) for item in row)+b'\n')
			temp.flush()
			super(UnicodeCursor, self).execute(query % {
				'tmpfile':temp.name,
			}) 
		self.rowcount = super(UnicodeCursor, self).rowcount

	def create_table(self, name, description):
		" Experimental, Does not support MySQL's unsigned  "
		# PEP 249
		columns = []
		type_codes = {
			1: 'TINYINT',
			#'SMALLINT',
			#'MEDIUMINT',
			3: 'INT',
			4: 'FLOAT',
			5: 'DOUBLE',
			8: 'BIGINT',
			246: 'DECIMAL',
			252: 'BLOB',
			253: 'VARBINARY', 
			254: 'ENUM',
		}
		for (name, type_code, display_size, internal_size, precision, scale, null_ok) in table_description:
			columns.append("`%s` %s(%s) %s" % (
				name,
				type_codes[type_code],
				internal_size,
				'NULL' if null_ok else 'NOT NULL',
			))
		self.execute(b"CREATE TABLE `%s` (\n%s\n)" % (name, b',\n'.join(columns)))

	def load(self, fp, table):
		" Experimental "
		super(UnicodeCursor, self).execute('''
			LOAD DATA LOCAL INFILE "__file__"
			INTO TABLE `__table__`
		'''.replace('__file__', fp.__name__).replace('__table__', table))
		self.rowcount = super(UnicodeCursor, self).rowcount

	def dump(self, fp):
		" Experimental "
		for row in cursor:
			fp.write(b'\t'.join(MySQL_format(item, encoding) for item in row)+b'\n')
		else:
			fp.flush()

	def replag(self):
		" Returns replication lag as number of seconds "
		curs = super(UnicodeCursor, self)
		try:
			curs.execute("/*replag() LIMIT:5*/SELECT UNIX_TIMESTAMP() - UNIX_TIMESTAMP(MAX(rc_timestamp)) FROM recentchanges")
			return curs.fetchall()[0][0]
		except oursql.DatabaseError as e:
			if e.errno != errnos['ER_QUERY_INTERRUPTED']:
				raise
		return None

	def htmltable(self, caption=None, className=u"wikitable sortable", style=None):
		" Method for quickly prototyping tools "
		import cgi
		html = u'<table class="%s"'%cgi.escape(className, quote=True)
		html += ' style="%s">'%style if style else '>'
		if caption:
			html += u'<caption>%s</caption>' % cgi.escape(unicode(caption))
		html += u'<tr>'
		for col in self.description:
			html += u'\n<th>%s</th>'%col[0]
		html += u'\n</tr>'
		for row in self.fetchall():
			html += u'<tr>'
			html += u'\n'.join(u'<td>%s</td>'%cgi.escape(unicode(field)) for field in row)
			html += u'</tr>'
		html += u'</table>'
		return html


connections = {} # cache connections
# TODO rename to connect or conn or something
def getConn(dbname='', host=None, read_default_file=None, local_infile=True, 
	        charset='utf8mb4', use_unicode=False, default_cursor=UnicodeCursor, 
			cluster='web', reconnect=False,
			*args, **kwargs):
	"""
	conn = getConn('enwiki_p')
	curs = conn.cursor()
	or: 
	with getConn('enwiki') as curs:
	"""
	# TODO getConn('tools') should connect to the user's default database
	if dbname and not dbname.endswith('_p'): dbname+='_p'
	if local_infile: kwargs['compress'] = True
	if (host,dbname) not in connections or reconnect:
		connections[host,dbname] = oursql.connect(
			db=dbname,
			host=host or '%s.%s.db.svc.eqiad.wmflabs' % (dbname[:-2], 'web' if cluster=='web' else 'analytics', ),
			read_default_file=read_default_file or os.path.expanduser('~/.my.cnf'),
			local_infile=local_infile,
			charset=charset,
			use_unicode=use_unicode, # We're extended execute to do this
			default_cursor=default_cursor,
			*args,
			**kwargs
		)
	return connections[host,dbname]

