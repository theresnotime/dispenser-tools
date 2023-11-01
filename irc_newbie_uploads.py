#!/usr/bin/env python
"""
screen -ls | grep ircbot
if [ $? -ne 0 ]; then
screen -dmO ircbot
screen -S ircbot -X stuff $'while true; do ~/pyscripts/irc_newbie_uploads.py `date  -d "1 hour ago" "+%Y%m%d%H0000"`; sleep 300; done\n'
fi
"""
# SQL queries are CC-0 license
import os, socket, time, re, urllib
import oursql, phpserialize
os.sys.path.append('/user-data/acoustid')
try:
	import trackmatch
except ImportError:
	trackmatch = None

stalkwords_R = re.compile(br'(Wikipedia|WP)[-. _\-]*(0|Zero)|T129845|Z591|Z567|Dispenser|HaeB|Keegan|Koerner|Vito|Zhuyifei|PING', re.I)
pirate_names_R = re.compile(br'(([Nn]+[Ee]+[Ww]+[Ss]+|[Nn]+[Ww]+[Ee]+[Ss]+|[Pp]ortal|[Mm]u[sz]ik|[Mm]adezyma|Walter|Mr[.]?_Gamer|MRGAMER|Germano|[Aa]rlindo|[Aa]mbrosio|[Hh]indio|[Ee]dman|Edgar|[Yy]ounes)[_.\-]??(?![^ ]*/))+')
ping_me = {
	#'thib': 'fr.wikipedia.org',
	#'dispenser': 'acoustid.org',
	#'Di\x01\x01spencer\x0F': 'acoustid.org', # fancy
}

botnick = "NewbieAudioVideo"
passwd = open(os.path.expanduser('~/.irc_passwd')).read()

# Settings
server = "irc.freenode.org"
# Syntax * matches all channels, !wikimedia.org 
# ~ will not increament message counter (use for mostly empty channel)
channels = {
"##wikimedia-commons-newbie-av": "*",
}
"""#

# Commons
#"#wikimedia-commons":      "commons.wikimedia.org",
"##wikimedia-commons-newbie-av": "*",
"#wikimedia-commons-admin": "commons.wikimedia.org",  # Multiple confirmations

#  
"#wikinews":                "wikinews.org",
"#wikisource":            "wikisource.org",
"#wikivoyage":            "wikivoyage.org",
"#wiktionary":            "wiktionary.org",
"#wikispecies":    "species.wikimedia.org",
#"#wikimedia":          "meta.wikimedia.org", # Catchall

# Wikiversity
"#wikiversity-en":    "en.wikiversity.org",
"#wikiversity-fr":    "fr.wikiversity.org",
"#wikiversity-pt":    "pt.wikiversity.org",
"#wikiversity":          "wikiversity.org", # Catchall

# Wikipedias
"#wikipedia-el":        "el.wikipedia.org",
"#wikipedia-en-alerts": "en.wikipedia.org",
"#wikipedia-fr-admin":  "fr.wikipedia.org",
"#wikipedia-he":        "he.wikipedia.org",
"#wikipedia-hu":        "hu.wikipedia.org",
#"#wikipedia-ml":        "ml.wikipedia.org", # Empty
# Sept 2017
"#wikipedia-fi":        "fi.wikipedia.org",
#"#wikipedia-ar":        "ar.wikipedia.org",


"#cvn-meta":          "meta.wikimedia.org",
"#cvn-mediawiki":      "www.mediawiki.org",
"#cvn-sw":                 "wikipedia.org", # Catchall
"#countervandalism":                 "org", # Final catchall

####################
# invite-only
#"#wikispecies-admins": "species.wikimedia.org",
#"#wikinews-en-admins":   "en.wikinews.org",
#"#wikipedia-en-admins": "en.wikipedia.org",
# Banned
#"#wikimedia-admin-pt":  "pt.wikipedia.org", # Why???
##
# No bot speaking channel
#"#wikipedia":            "wikipedia.org",
}
##### """ #####

# Default options
last_run = os.sys.argv[1] if len(os.sys.argv) > 1 else time.strftime('%Y%m%d%H0000')
lastrun  = os.sys.argv[1] if len(os.sys.argv) > 1 else time.strftime('%Y%m%d%H0000')
forceUpdate = os.sys.argv[2:3] == ['update']

ping_back = {}
uploaders = {
}


connections = {}
def getConn(wiki, host="s1.web.db.svc.eqiad.wmflabs", reconnect=False):
    if not wiki.endswith('_p'): wiki+='_p'
    if (host,wiki) not in connections or reconnect:
        connections[host,wiki] = oursql.connect(
            db=wiki,
            host=host,
            read_default_file="/home/dispenser/replica.my.cnf",
            charset=None,
            use_unicode=False,
			autoping=True,
        )
    return connections[host,wiki]


def no_ping_name(username):
	# TODO Use channel member list instead of randomly inserting characters
	username = username.decode('utf-8', 'ignore')
	username, n = re.subn(ur'(?<=[a-z])(?=[A-Z])|[ _-]+', ur'.', username)
	if n == 0:
		l = len(username)
		username = username[:l//2] + u'.' + username[l//2:]
	return username.encode('utf-8')


def getNewVideos(last_run):
	return []
	# Query time is usualy 10-20 second
	StartTime = time.time()
	cursor = getConn('commonswiki', reconnect=True).cursor()
	queries = []
	for dbname, (url, family) in wikis.iteritems():
		queries.append(('''
SELECT "$1", "$2" AS host, "$3" AS family, img_name, img_size, img_metadata, 
       img_timestamp, user_name, user_registration, user_editcount, (
	SELECT COUNT(*)
	FROM $1_p.logging_logindex 
	WHERE log_namespace=6 AND log_title=img_name
	AND log_type="delete" AND log_action="delete"
) AS deletes, (
  SELECT GROUP_CONCAT(DISTINCT ug_group SEPARATOR ", ")
  FROM $1_p.user_groups
  WHERE ug_user = img_user
) AS user_groups, 
'''+
' + '.join(("(SELECT IFNULL(user_editcount,0) FROM %s_p.user x WHERE x.user_name=user.user_name)"%dbname for dbname in [
'commonswiki',
#'dewiki',
#'elwiki',
#'enwiki',
#'eswiki',
#'frwiki',
#'nlwiki',
#'ptwiki',
]))
+''' AS global_editcount, TIMESTAMPDIFF(MINUTE, img_timestamp, NOW()) AS MinutesAgo
FROM $1_p.image
JOIN $1_p.user ON user_id = img_user

WHERE 
    img_timestamp > ? -- DATE_FORMAT(NOW() - INTERVAL 3 SECONDS, "%Y%m%d%H%i%s")
/* Let counter-vandalism handle it first */
AND img_timestamp < DATE_FORMAT(NOW() - INTERVAL 3 MINUTE, "%Y%m%d%H%i%s")
/* File size as proxy to exclude short videos */
AND ( ( FALSE 
) OR img_media_type="VIDEO"  AND (
	img_size >      500 * 1024
) OR img_media_type="AUDIO"  AND (
	img_size >      100 * 1024
) OR img_media_type="OFFICE" AND (
	img_size > 8 * 1024 * 1024 /* 15.9% of all PDFs */
) OR img_media_type="BITMAP" AND (
	img_major_mime="image" AND img_minor_mime="jpeg"  AND img_size > 3 * img_width * img_height + 10*1024*1024
 OR img_major_mime="image" AND img_minor_mime="x-xcf" AND img_size > 3 * img_width * img_height + 10*1024*1024
 OR img_major_mime="image" AND img_minor_mime="png"   AND img_size > 1.10 * ( 10*1024*1024 + img_width * img_height * img_bits / 8 * 
    IF(img_metadata LIKE '%s:16:"truecolour-alpha"%', 4, IF(img_bits<8 OR img_metadata LIKE '%s:14:"index-coloured"%' OR img_metadata LIKE '%s:9:"greyscale"%', 1, 3)) 
	) AND (img_metadata NOT LIKE '%"frameCount";i:%' OR img_metadata LIKE '%"frameCount";i:0;%')
)
)

/* Newish users only */
AND (
--  user_editcount < 20 AND user_registration > DATE_FORMAT(NOW() - INTERVAL 90 DAY, "%Y%m%d%H%i%s")
    user_editcount < 20 AND user_registration > "20170101"
 OR user_name IN (
		SELECT REPLACE(page_title, "_", " ") AS abuser_name
		FROM commonswiki_p.categorylinks
		JOIN commonswiki_p.page ON page_id=cl_from
		WHERE page_namespace=2 AND cl_to IN (
			"Users_suspected_of_abusing_Wikipedia_Zero",
			/* 22 Subcategories */
			"Sockpuppets_of_Cebola_Da_Cash_Birdman",
			"Sockpuppets_of_Wikimedia_Angolla",
			"Sockpuppets_of_Nayon061215",
			"Sockpuppets_of_Simo_cvb",
			"Sockpuppets_of_Me_RK_Rony",
			"Sockpuppets_of_Wunnakyaw1",
			"Sockpuppets_of_Principe_Enthony_Stark",
			"Sockpuppets_of_Mnmrlay",
			"Sockpuppets_of_Noureddine_1997",
			"Sockpuppets_of_Mimmatulislam_bd",
			"Sockpuppets_of_EduardoMadureira2017",
			"Sockpuppets_of_Motin3432",
			"Sockpuppets_of_Hamid_hoh",
			"Sockpuppets_of_Nsit_3lih",
			"Sockpuppets_of_Nis777",
			"Sockpuppets_of_Tifo_wac",
			"Sockpuppets_of_Tvkianda",
			"Sockpuppets_of_Zikkkkgff",
			"Sockpuppets_of_Ikram_mejrad",
			"Sockpuppets_of_Zajzkaza_banabza",
			"Sockpuppets_of_Boubik",
			"Sockpuppets_of_Tamara787"
		)
	)
 OR user_name IN (
	SELECT REPLACE(pl_title, "_", " ") AS abuser_name
	FROM commonswiki_p.pagelinks
	WHERE pl_from IN (
		41822829, /* User:Teles/Angola Facebook Case */
		48078086  /* User:NahidSultan/Bangladesh Facebook Case/Accounts */
	)
	)
)

/* Avoid "Excess Flood" the channel */
/*LIMIT 12*/
''').replace('$1', dbname).replace('$2', url).replace('$3', family))
	cursor.execute('/* irc_newbie_upload LIMIT:120 */'+' UNION ALL '.join(queries), (last_run, ) * len(wikis))
	results = cursor.fetchall()
	os.sys.stdout.write("%d uploads > %s [%d sec]\r" % (len(results), last_run, time.time()-StartTime))
	# 
	if results:
		print
	
	return results


def getBlockedUsers(ipb_addresses, dbname='commonswiki'):
	cursor = getConn(dbname).cursor()
	cursor.execute('''
SELECT ipb_address, ipb_reason, ipb_by_text 
FROM ipblocks_ipindex
WHERE ipb_address IN ('''+','.join(('?',)*len(ipb_addresses))+')', tuple(ipb_addresses))
	return cursor.fetchall()

def talkABF(lastrun, dbname='commonswiki'):
	cursor = getConn(dbname).cursor()
	cursor.execute('''
SELECT rev_user_text, rev_timestamp
FROM revision 
JOIN page ON page_id = rev_page
LEFT JOIN user_groups ON ug_user = rev_user AND ug_group="confirmed"
WHERE rev_user IN (
  SELECT DISTINCT afl_user
  FROM abuse_filter_log
  WHERE afl_filter = 180
  AND afl_timestamp > DATE_FORMAT(NOW() - INTERVAL 1 WEEK, "%Y%m%d%H%i%s")
)
AND page_namespace=5 AND page_title="Abuse_filter"
AND rev_timestamp > ?
AND ug_group IS NULL
LIMIT 10;
''', (lastrun, ) )
	return cursor.fetchall()
	

# Store list of all available wikis
with getConn('commonswiki_p').cursor() as curs:
	curs.execute("""
	SELECT DISTINCT dbname, url, family
	FROM meta_p.wiki 
	JOIN INFORMATION_SCHEMA.tables ON table_schema = CONCAT(dbname, "_p")
	WHERE is_closed=0
	""")
	wikis = dict([(a, (b, c)) for (a,b,c) in curs.fetchall()])

def main(forceUpdate):
	#
	global last_run
	global lastrun
	print b"\x1B[1mconnecting to:"+server+b"\x1B[0m"
	irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #defines the socket
	irc.connect((server, 6667))
	irc.setblocking(False)
	irc.send("USER {botnick} {botnick} {botnick} :Feed of newbie uploads (WP0 Abuse, phab:T129845)\n".format(botnick=botnick)) #user authentication
	irc.send("NICK "+ botnick +"\n")
	#irc.send("PRIVMSG NickServ :IDENTIFY "+botnick +" "+passwd+"\r\n")
	time.sleep(15) # ???

	for channel in channels.keys():
		irc.send("JOIN "+ channel +"\n")

	time.sleep(10)

	print 'forceUpdate:', forceUpdate, 'last_run:', last_run
	while True:    #puts it in a loop
		try:
			text=irc.recv(2048)  #receive the text
			for line in text.split('\r\n'):
				command, sep, arguments = line.partition(' ')
				if command == 'PING':                       #check if 'PING' is found
					irc.send('PONG ' + arguments + '\r\n') #returns 'PONG' back to the server (prevents pinging out!)
				elif command == 'ERROR':
					raise
				#elif command == 'QUIT':
				elif 'QUIT ' in line and botnick in line:
					print line
					os.sys.exit(1)
				if botnick in line or command in ("NOTICE",):
					print line.replace(botnick, b'\x1b[44m%s\x1b[0m'%botnick)
				elif stalkwords_R.search(line):
					print stalkwords_R.sub(b'\x1b[30;103m\\g<0>\x1b[0m', line)
		except socket.error as e:
			if e.errno != 11: # no messages
				print "socket.error", repr(e)
		
		# Query takes about 1 minute to run.  Add 50 sec to run on time
		#if (time.time() + 50) // 60 % 30 < 3 or forceUpdate: # Run every half-hour
		if (time.time() + 50) // 60 % 10 < 2 or forceUpdate:
			forceUpdate = False
			old_last_run = last_run
			for dbname, host, family, img_name, img_size, img_metadata, img_timestamp,\
				user_name, user_registration, user_editcount, deletes, user_groups, global_editcount, min_ago in getNewVideos(last_run):
				if img_timestamp > last_run:
					last_run = img_timestamp
				try: # Error details in https://phabricator.wikimedia.org/T155741
					metadata = phpserialize.loads(img_metadata)
					if not isinstance(metadata, dict):
						metadata = {}
				except ValueError as e:
					metadata = {}
					print 'img_metadata decode error:', e
				
				extra = b''
				playtime = float(metadata.get('playtime_seconds', metadata.get('playtime', metadata.get('length', '-60'))))

				# PDF
				if 'Page' in metadata:
					extra = (u'%s pages' % metadata['Page']).encode('utf-8')

				
				# save
				uploaders[user_name] = (host, dbname)
				ping_back[user_name] = []
				
				# AcoustID matcher
				try:
					bestmatch = None
					# Under 10 minutes or 10 MB, try AcoustID matching
					if trackmatch and (10 < playtime < 10 * 60 or img_name.lower().endswith(('.ogg', '.oga', '.ogv', '.webm')) and img_size < 10e6): 
						domain_parts = re.sub(r'[^/]*//([^/]+).*', r'\1', host).split('.')
						bestmatch = trackmatch.match_commons(
							img_name,
							lang=dbname[:-4].replace('_', '-') if family in ('special', 'wikimania') else domain_parts[-3],
							family=family,
						)
					if bestmatch:
						(score, track_id, mb_title) = bestmatch
						extra = (u' :: %d%% "%s" https://acoustid.org/track/%s' % (100.0*score, mb_title, track_id,)).encode('utf-8')
				except Exception as e:
					if '2048' in e.message:	
						extra = b' [File 404]'
					else:
						extra = b'  pyAcoustID: %r: %s' % (type(e), e.message)
					print 
					print repr(type(e)), repr(e)
					print
				line = b'http://tinyurl.com/CentralAuth/%s (%s %s%s) %s%s %s/wiki/File:%s (%s)%s' % (
					user_name.replace(' ', '_'), user_editcount, 'edit' if user_editcount==1 else 'edits',
					#b', %d global' % global_editcount if global_editcount > user_editcount else '',
					b', \x0301,09%s\x0F' % user_groups if user_groups else '',
					'uploaded' if deletes == 0 else 're-uploaded',
					' %d hour ago'%(min_ago//60,) if min_ago >= 120 else ' %d min ago'%min_ago if min_ago >= 10 else '',
					host, img_name,
					','.join([x for x in (
						'%.1f MB'%(img_size/1024.0/1024.0,),
						' %d min' %(playtime / 60.0,) if playtime > 0 else '',
					) if x]),
					extra,
				)
				line = pirate_names_R.sub(b'\x0304\\g<0>\x0F', line)
				for user, needle in ping_me.iteritems():
					if needle in line:
						line += " Yo, %s" % (user,)
				#print line
				#for channel, needle in channels.iteritems():
				print_cnt = 0
				for channel in sorted(channels, key=lambda x: ('!' not in channels.get(x), channels.get(x).count('.'), 255-len(channels.get(x))), reverse=True):
					needle = channels[channel]
					
					if needle == "*" or needle.lstrip('!~') in line and (print_cnt == 0 or '!' in needle):
						if not needle.startswith('~'):
							print_cnt += 1
						try:
							#print b"PRIVMSG \x1b[6;30;42m%-30s\x1b[0m :%s" % (channel, line)
							#irc.send(b"PRIVMSG %s :%s\n" % (channel, line))
							ping_back[user_name].append(channel)
						except IOError:
							print "Problem sending %r: %r\n" % (channel, line)
							raise
				
				time.sleep(3) # try avoid "Excessive flood"
			if last_run > old_last_run:
				print  
		
		# List uploaders blocked
		for host, dbname in set(uploaders.values()):
			for ipb_address, ipb_reason, ipb_by_text in getBlockedUsers(tuple(u for u, (h,dbn) in uploaders.iteritems() if h==host), dbname):
				del uploaders[ipb_address]
				line = b'%s blocks User:%s for: \x02%s\x0F%s' % (
					no_ping_name(ipb_by_text),
					ipb_address.replace(' ', '_'),
					re.sub(br'\[\[([^[\]{|}]+\|)?(.*?)\]\]', b'\x1f\\2\x1f', ipb_reason),
					'' if uploaders else ' LIST CLEARED',
				)
				print '\x1b[6;30;42m%s\x1b[0m' % line
				for channel in ping_back.get(ipb_address, []):
					if channel != '##wikimedia-commons-newbie-av':
						irc.send(b"PRIVMSG %s :%s\n" % (channel, line))
				irc.send(b"PRIVMSG ##wikimedia-commons-newbie-av :%s #%s\n" % (line.replace('User:', 'http://tinyurl.com/CentralAuth/', 1), dbname,))
		
		# Commons users requesting unblocking from affected edit filter
		for rev_user_text, rev_timestamp in talkABF(lastrun):
			line = "http://enwp.org/c:Commons_talk:Abuse_filter#Report_by_%s" % urllib.quote(rev_user_text.replace(' ', '_'), safe=";@$!*(),/:").replace('%', '.')
			irc.send(b"PRIVMSG ##wikimedia-commons-newbie-av :%s\n" % line)
			#irc.send(b"PRIVMSG #wikimedia-commons-admin :%s\n" % line)
			print '\x1b[6;30;46m%s\x1b[0m' % line
			lastrun = max(lastrun, rev_timestamp)
		
		time.sleep(10) # Don't kill the CPU

if __name__ == "__main__":
	except_count = 0 
	while True:
		if except_count >= 20:
			raise Exception("Too many exceptions, time to die")
		try:
			connections = {}
			main(forceUpdate)
		except KeyboardInterrupt:
			raise
		except (oursql.ProgrammingError, oursql.InterfaceError, oursql.OperationalError) as e:
				print 
				print repr(type(e)), repr(e)
				print
				print b'\x1B[1mReconnecting in 5 minutes...\x1B[0m'
				time.sleep(5 * 60)
				continue
		except socket.error as e:
				print 
				print repr(type(e)), repr(e)
				print
				print b'\x1B[1mReconnecting...\x1B[0m'
				continue
		else:
			print "Error"
		finally:
			except_count += 1

