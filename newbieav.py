#!/usr/bin/env python
# -*- coding: utf-8  -*-
import wikipedia; from wikipedia import logtime
import re, json, os, time
import binascii, phpserialize
import toolsql
import cgitb; cgitb.enable(logdir='tracebacks')

logos = {
	'commons.wikimedia.org': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Commons-logo.svg/12px-Commons-logo.svg.png',
	'.wikipedia.org':        'https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-logo-v2.svg/17px-Wikipedia-logo-v2.svg.png',
	'.wikinews.org':         'https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Wikinews-logo.svg/30px-Wikinews-logo.svg.png',
	'wikisource.org':        'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Wikisource-logo.svg/15px-Wikisource-logo.svg.png',
	'.wiktionary.org':       'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Wiktionary_small.svg/16px-Wiktionary_small.svg.png',
}


def printu(s, data=None):
	print (s%data if data else s).encode('utf-8')

def main():
	try: days = float(wikipedia.SysArgs.get('days', '1'))
	except ValueError: days = 0.5
	site = wikipedia.getSite()
	# These queries are normally fast, but indexes need to be hot
	conn = toolsql.getConn('commonswiki_p', cluster='web', charset='utf8')
	cursor = conn.cursor()
	
	cursor.execute('SELECT family, dbname FROM meta_p.wiki WHERE is_closed=0 ORDER BY family')
	print '<form><label>Use database: <select name="dbname">'
	print '<option value="">(All wikis)</option>'
	grpfamily = ''
	for family, dbname in cursor:
		if grpfamily != family:
			if grpfamily: print '</optgroup>'
			grpfamily = family
			print '<optgroup label="%s">'% family
		print '<option%s>%s</option>'%(' selected="selected"' if dbname==site.dbName() and dbname!='enwiki' else '', dbname)
	print '</optgroup>'
	print '</select></label>'
	print '<label>Check last <select name="days">'
	for i in (0.5, 1, 2, 3, 7, 14, 30):
		print '<option%s%s>%s</option>' % (' selected="selected"' if i == days else '', ' value=""' if i==1 else '', i)
	print '</select> days</label>'
	print '<!-- days = %s -->' % days
	print '<input type="submit" value="Show" />'
	print '</form>'
	print '</div>'
	os.sys.stdout.flush()
	
	StartTime = time.time()
	cursor.execute("""
SELECT DISTINCT dbname, url 
FROM meta_p.wiki 
JOIN INFORMATION_SCHEMA.tables ON table_schema = CONCAT(dbname, "_p")
WHERE is_closed=0
"""+('' if site.dbName()=='enwiki' else 'AND dbname="%s"'%site.dbName()))
	wikis = dict(cursor.fetchall())

	queries = []
	for dbname, url in wikis.iteritems():
		# Find broken databases
		#print dbname; os.sys.stdout.flush(); cursor.execute(b'SELECT EXISTS (SELECT 1 FROM $1_p.logging_logindex);'.replace('$1', dbname)); cursor.fetchall()
		queries.append(('''
SELECT "$1", "$2" AS host, rc_id, rc_patrolled, img_name, img_size, img_media_type, HEX(img_metadata), 
       img_timestamp, user_name, user_registration, user_editcount, (
	SELECT COUNT(*)
	FROM $1_p.logging_logindex 
	WHERE log_namespace=6 AND log_title=img_name
	AND log_type="delete" AND log_action="delete"
) AS deletes, (
  SELECT GROUP_CONCAT(DISTINCT ug_group SEPARATOR ", ")
  FROM $1_p.user_groups
  WHERE ug_user = img_user
) AS user_groups, (SELECT tl_title
	FROM $1_p.templatelinks
	WHERE tl_from=rc_cur_id
	AND tl_namespace=10 AND tl_title IN ("Delete", "Copyvio", "No_permission_since", "Dw_no_source_since")
	LIMIT 1
	) AS tpl_delete, TIMESTAMPDIFF(HOUR, img_timestamp, NOW()) AS HoursAgo 
FROM $1_p.recentchanges
JOIN $1_p.image         ON img_name = rc_title 
JOIN $1_p.user          ON user_id = rc_user AND user_name = rc_user_text

/* rc_name_type_patrolled_timestamp = rc_namespace, rc_type, rc_patrolled, rc_timestamp */
WHERE rc_namespace = 6 /* File: */
/* Only uploads */
AND rc_type=3
AND rc_log_type  = "upload"
/* Only unpatrolled files */
AND rc_patrolled IN (0)
AND rc_timestamp > DATE_FORMAT(NOW() - INTERVAL ? HOUR, "%Y%m%d%H%i%s")

/* Speed Hack: Exclude .png, .jpeg, .jpg, .gif, .svg */
AND rc_title NOT REGEXP "[.][PpJjGgSs][NnPpIiVv][Ee]?[GgFf]$"

AND img_timestamp  > DATE_FORMAT(NOW() - INTERVAL ? HOUR, "%Y%m%d%H%i%s")
/* Only Audio and Video from new users */
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
OR img_media_type="MULTIMEDIA" 
)

/* Newish users only */
AND (
    user_editcount < 25 AND user_registration > "20170101"
/* OR user_name IN (
		SELECT DISTINCT REPLACE(page_title, "_", " ") AS abuser_name
		FROM commonswiki_p.categorylinks
		JOIN commonswiki_p.page ON page_id=cl_from
		WHERE page_namespace=2 AND cl_to IN (
			"Users_suspected_of_abusing_Wikipedia_Zero",
			-- 22 Subcategories --
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
	UNION DISTINCT
		SELECT DISTINCT REPLACE(pl_title, "_", " ") AS abuser_name
		FROM commonswiki_p.pagelinks
		WHERE pl_from IN (
			41822829, -- User:Teles/Angola Facebook Case --
			48078086  -- User:NahidSultan/Bangladesh Facebook Case/Accounts --
		)
	)/*-*/
)

''').replace('$1', dbname).replace('$2', url))
# Test disabling query cache (.replace()) for a bug report (remove after Feb 2018)
	cursor.execute(' UNION ALL '.join(queries).replace('SELECT ', 'SELECT SQL_NO_CACHE', 1).encode('ascii') + ' ORDER BY img_timestamp DESC', (days*24,days*24)*len(wikis), decode_errors='replace', max_time=180)

	results = cursor.fetchall()
	print '<div dir="ltr">'
	#printu(cursor.htmltable())
	#print '<hr />'
	#print "%d audio/video uploads > %s, %.2g sec :: %s" % (len(results), lastRun, time.time()-StartTime, site.dbName())
	#print '<hr />'
	printu('<table class="sortable" style="margin:1em auto;">')
	printu('''<tr>
<th class="">User</th>
<th class="">Time</th>
<th class="unsortable"></th>
<th class="">File name</th>
<th class="unsortable">Size</th>
<th class="unsortable">Patrol</th>
<th class="unsortable">Nom</th>
<th class="unsortable">Delete</th>
</tr>''')
	#for rc_id, rc_patrolled, img_name, img_size, img_metadata, img_timestamp, user_name, user_registration, user_editcount, deletes, min_ago in results:
	for dbname, host, rc_id, rc_patrolled, img_name, img_size, img_media_type, img_metadata, img_timestamp, user_name, user_registration, user_editcount, deletes, user_groups, tpl_delete, hour_ago in results:
			try:
				metadata = phpserialize.loads(binascii.a2b_hex(img_metadata))
				if not isinstance(metadata, dict):
					metadata = {}
			except ValueError as e:
				metadata = {}
				#print 'img_metadata decode error:', e

			extra = ''
			playtime = float(metadata.get('playtime_seconds', metadata.get('playtime', metadata.get('length', '-60'))))
			logo_html = '<code>%(dbname)s</code>'%locals()
			for d, logo_url in logos.iteritems():
				if d in host:
					logo_html =  '<img src="%s" height="16" alt="%s" title="%s">' % (logo_url, dbname, dbname)
			printu('<tr dir="ltr">')
			printu(u'''\
<td><a href="%s/wiki/User:%s">User:%s</a>&#8206; (<a href="https://meta.wikimedia.org/wiki/Special:CentralAuth/%s">%s&nbsp;%s</a>%s)</td>
<td>%s%s </td>
<td>%s</td>
<td><a class="link-%s" href="%s/wiki/File:%s">%s</a></td>
<td>%s%s%s</td>\
''', (
				host, user_name, user_name, user_name, user_editcount, 'edit' if user_editcount==1 else 'edits',
				', <span style="background-color:lime;color:black;">%s</span>' % user_groups if user_groups else '',
				'',#'uploaded' if deletes == 0 else 're-uploaded',
				' %d hour ago'%hour_ago if hour_ago >= 0 else '',
				logo_html,
				img_media_type.lower().replace('office', 'document'), host, img_name, img_name.replace('_', ' '), 
				'%.1f&nbsp;MB' % (img_size/1024.0/1024.0,),
				', %3.1f&nbsp;min' % (playtime / 60.0,) if playtime > 0 else '',
				extra,
			))
			if tpl_delete:
				printu('<td colspan="2" class="tpl_delete">{{%s}}'%tpl_delete)
			else:
				printu('<td>')
			if not rc_patrolled:
				if not tpl_delete:
					printu('<a class="mw-ui-button" href="%s/w/index.php?title=File:%s&amp;action=markpatrolled&amp;rcid=%s&amp;uselang=en">Mark as patrolled</a>', (host, img_name, rc_id, ))
					printu('</td><td>')
					printu('<a class="mw-ui-button" href="%s/w/index.php?title=File:%s&amp;action=edit&amp;uselang=en&amp;preview=yes&amp;section=0&amp;summary={{copyvio}}">Nominate</a>', (host, img_name,))
				printu('</td><td>')
				printu('<a class="mw-ui-button" style="background-color:#fe4e34" href="%s/w/index.php?title=File:%s&amp;action=delete&amp;uselang=en">Delete</a>', (host, img_name,))
			printu('</td>')
			printu('</tr>')

	printu('</table>')



if __name__ == "__main__" and wikipedia.handleUrlAndHeader():
	try:
		wikipedia.startContent(form=False, head='''<style type="text/css">
.tpl_delete { color:red; text-decoration:underline; text-align:center; } 
</style>''')
		main()
	except toolsql.OperationalError as (errno, strerror, extra):
		if errno in (1041, 1226, 2013): # Too many connection / Max connections / Lost connection
			print '<p class="errormsg">Database operational error (%d), retry in a few minutes.</p><blockquote>%s</blockquote>'%(errno, wikipedia.escape(strerror),)
			print '<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>'
		else:
			raise
	finally:
		wikipedia.endContent()
		wikipedia.stopme()

