#!/usr/bin/env python
# -*- coding: utf-8  -*-
"""
A simple demo program that grown beyond, see locateCoordv1.py for the simpler version

This should really be scale back infavor of a better backend implementation
"""
import wikipedia
import toolsql, cgi
import cgitb; cgitb.enable(logdir='tracebacks')

# XXX copied from ghel.py
globes = (
# Only object larger than XX are included.
#	Moons are indented, only important/well studied are listed
"Sun",
# Terrestrials
"Mercury",
"Venus",
"Earth",
	"Moon",
"Mars",
	"Phobos", "Deimos",
# Asteroid belt
"Ceres",
# Jovian Planets (Gas Giants)
"Jupiter",
	"Ganymede", "Callisto", "Io", "Europa", "Amalthea", "Thebe", "Adrastea", "Metis",# and 55 more
"Saturn",
	"Mimas", "Enceladus", "Tethys", "Dione", "Rhea", "Titan", "Hyperion", "Iapetus", "Phoebe", "Janus", "Epimetheus", # and 50 more
	# TODO needs review
	"Pan",
	"Atlas",
	"Pandora",
	"Prometheus",
	"Janus",
	"Telesto",
	"Calypso",
	"Helene",
"Uranus",
	"Miranda", "Ariel", "Umbriel", "Titania", "Oberon", "Puck", # and 21 more
	# TODO needs review
	"Cordelia",
	"Ophelia",
	"Bianca",
	"Cressida",
	"Desdemona",
	"Juliet",
	"Portia",
	"Rosalind",
	"Belinda",
	"Puck",
"Neptune",
	"Triton", "Nereid", "Proteus", # and 10 more
	# TODO needs review
	"Naiad",
	"Thalassa",
	"Despina",
	"Galatea",
	"Larissa",
# Kuiper belt
"Pluto",
	"Charon",
"Haumea",
"Makemake", 
"Eris"
)


def main():
	form = cgi.FieldStorage()
	site = wikipedia.getSite()
	# Support older URL where dbname was the table name
	if form.getfirst('dbname', '').startswith('coord_'):
		try:site = wikipedia.Site(form.getfirst('dbname')[6:], 'wikipedia')
		except:pass
	ghel_table= "u2815__p.coord_%s" % site.dbName()
	globe   = form.getfirst('globe', '')
	# 
	try:
		def get_form_float(name, defaultValue):
			try:return float(form.getfirst(name, defaultValue))
			except ValueError:return defaultValue
		lat1	= get_form_float('lat1', 0.0)
		lat2	= get_form_float('lat2', 0.0)
		lon1	= get_form_float('lon1', 0.0)
		lon2	= get_form_float('lon2', 0.0)
		limit	= 500
		offset  = int(get_form_float('offset', 0))
		if not any((lat1, lat2, lon1, lon2)):
			# based on http://toolserver.org/~kolossos/wp-world/umkreis-source.php
			# by http://de.wikipedia.org/wiki/Benutzer:Kolossos
			import math
			range_deg = (get_form_float('range_km', 0) or 0.0001)/111.3
			#
			lat  = get_form_float('lat', 0.0)
			lat1 = lat - range_deg/2.0
			lat2 = lat + range_deg/2.0
			#
			lon  = (get_form_float('lon', 0.0)+180) % 360 - 180
			lon1 = lon - range_deg/2.0/math.cos(lat/57.27)
			lon2 = lon + range_deg/2.0/math.cos(lat/57.27)
		# Swap if relations are reversed
		if lat1 > lat2:
			lat1, lat2 = lat2, lat1
		if lon1 > lon2:
			lon1, lon2 = lon2, lon1
	except (TypeError, ValueError) as errmsg:
		wikipedia.output("Input error: \03{lightred}%s\03{default}"%(errmsg,))
		return
	wikipedia.logtime('Finished reading inputs')
	
	with toolsql.getConn(host='tools.labsdb') as cursor:
		cursor.execute("""/* locateCoord LIMIT:30 */
SELECT DATE_FORMAT(IFNULL(UPDATE_TIME, CREATE_TIME), '%d %M %Y at %H:%i UTC')
FROM information_schema.tables
WHERE TABLE_SCHEMA=? AND TABLE_NAME=?
""", ghel_table.partition('.')[::2])
		updated = cursor.fetchall()
		if updated: updated=updated[0][0]
		
		wikipedia.logtime('Lookup tables Last-Modified')

		print """<form action="locateCoord.py"><fieldset>
<legend>Locate articles in geographic region</legend>
<div style="background:#333; float:right; position: relative; width: 180px; height: 90px;">
<div style="position: absolute;">%s</div>
<div id="selection_window" style="position: absolute; top: %dpx; left: %dpx; border:1px solid red; background:rgba(255,32,32,0.3); width:%dpx; height:%dpx;"><!-- --></div>
</div>
<div>Site: %s<br/>
Globe: <select name='globe'>
<option value="">(all)</option>
%s
</select><br/>
<input name='lat1' value="%f" size="10" /> to <input name='lat2' value="%f" size="10" /> latitude<br/>
<input name='lon1' value="%f" size="10" /> to <input name='lon2' value="%f" size="10" /> longitude<br/>
<input type="submit" />

<div style="font-size:88%%;">
Last updated on %s | <a href="//toolserver.org/~dispenser/dumps/">database dumps</a> | <a href="//wiki.toolserver.org/view/Ghel">documentation</a>
</fieldset>
</form>""" % (
	'<img alt="" src="//upload.wikimedia.org/wikipedia/commons/thumb/4/46/World_map_with_nations.svg/180px-World_map_with_nations.svg.png" height="90" width="180"/>' if globe in ('', 'Earth') else '',
	( 90.0-lat2)//2, 
	(180.0+lon1)//2,
	( lon2-lon1)//2,
	( lat2-lat1)//2,
	'<input type="text" name="site" value="%s"/>'%wikipedia.escape(site.dbName()), 
	'\n'.join(
		'<option%s>%s</option>'%(
			' selected="selected"' if globe==s else '',
			wikipedia.escape(s),
		) for s in globes
	),# if globe in globes else '<input name="dbname" value="%s"/>'%wikipedia.escape(globe), 
	lat1, lat2,
	lon1, lon2, 
	updated,
)
	
		where_conditions = []
		where_data       = []
		def addWhere(condition, params=()):
			where_conditions.append(condition)
			for param in params:
				where_data.append(param)
		
		addWhere("MBRWithIn(gc_location, Envelope(LineString(Point(?, ?), Point(?, ?))))", (lat1,lon1,lat2,lon2))
		if globe:
			addWhere("gc_globe = ?", ('' if globe=='Earth' else globe,))
		if form.getfirst('region'):
			addWhere("gc_region LIKE ?", ("/%s%%"%form.getfirst('region'),))
			addWhere("gc_region LIKE ?", ("%s%%" %form.getfirst('region'),))
		if form.getfirst('type') != None:
			addWhere("gc_type REGEXP ?", (form.getfirst('type'),))
		if form.getfirst('namespace'):
			addWhere("page_namespace != ?" if form.getfirst('invert') else "page_namespace = ?", (form.getfirst('namespace'),))
		if form.getfirst('title'):
			addWhere("page_title REGEXP ?", (form.getfirst('title'),))
		if form.getfirst('name'):
			addWhere("gc_name REGEXP ?", (form.getfirst('name'),))
		
		wikipedia.logtime('Setup query')

		try:
			cursor.execute("""/* locateCoord LIMIT:120 NM */
SELECT
  gc_from,
  gc_lat,
  gc_lon,
  gc_head,
  gc_dim,
  gc_type,
  gc_size,
  gc_region,
  gc_globe,
  gc_primary,
  gc_name,
  gc_namespace
--  CONCAT(ns_name, IF(ns_name="", '', ':'), page_title) AS title
FROM """+ghel_table+"""
-- JOIN page ON page_id=gc_from
-- JOIN u2815__p.namespacename ON ns_id=page_namespace AND ns_is_favorite=1 AND dbname=(SELECT DATABASE())
WHERE """+' AND '.join(where_conditions)+"""
LIMIT ? OFFSET ?;
			""", tuple(where_data)+(limit+1, offset, ))
		except toolsql.Error as (errno, strerror, extra):
			if errno == 1146:
				wikipedia.output(strerror)
				return
			else:
				raise
		
		wikipedia.logtime('Ran query')
		
		print '<table class="wikitable lightrow sortable" style="width:100%">'
		print '<tr>'
		for heading in 'Lat|Lon|Dim|Type|Size|Region|Globe|Name'.split('|'):
			print '<th>%s</th>'%heading
		print '</tr>'
		print '<!--RESULTS-->'
		for gc_from, gc_lat, gc_lon, gc_heading, gc_dim, gc_type, gc_typesize, gc_region, gc_globe, gc_primary, gc_name, gc_namespace in cursor.fetchmany(500):
			print (u'<tr%s><td>%#.7g</td><td>%#.7g</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><a href="//%s/w/index.php?curid=%d">%s</a></td></tr>' % (
			#print '<tr%s><td>%#.7g</td><td>%#.7g</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><a href="//%s/wiki/%s">%s</a></td></tr>' % (
				'' if gc_primary else ' class="nonprimary"' if (':' in gc_name) == (gc_namespace!=0) else ' class="nonprimary nameistitle"',
				#'' if gc_primary else ' class="nonprimary"' if gc_name.replace(' ', '_')==fullpagename else ' class="nonprimary nameistitle"',
				gc_lat,
				gc_lon,
				gc_dim or '',
				gc_type or '',
				gc_typesize or '',
				gc_region or '',
				gc_globe or '',
				site.hostname(),
				gc_from,
				#wikipedia.urllib.quote(fullpagename),
				gc_name.replace('_', ' ') or '<i>[empty string]</i>',
			)).encode('utf-8')
		print '<!--/RESULTS-->'
		print '</table>'

	try:
		if cursor.fetchone():
			print '<p><a href="%s">Next 500</a></p>' % '?dbname=%s&amp;lat1=%s&amp;lat2=%s&amp;lon1=%s&amp;lon2=%s&amp;offset=%s' % (site.dbName(), lat1, lat2, lon1, lon2, offset+500)
	except toolsql.ProgrammingError as (errno, errmsg, extra):
		# No more results
		if errno != None: raise

if __name__ == "__main__" and wikipedia.handleUrlAndHeader(allowBots=True):
	try:
		wikipedia.startContent(form=False, head="""<style type="text/css">
.nonprimary {
	background-color:#e7e7e7;
	color:#666;
	line-height:95%;
}
.nameistitle a {
	font-style: italic;
}
html.theme-dark .nonprimary {
	background-color:#444;
	color:#999;

}
</style>""")
		main()
	except toolsql.Error as (errno, strerror, extra):
		if errno in (1040, 1226, 1317, 2006, 2013):
			print '<p class="errormsg">Database operational error (%d), retry in a few minutes.</p><blockquote>%s</blockquote>'%(errno, wikipedia.escape(strerror),)
			print '<script type="text/javascript">setTimeout("window.location.reload()", (Math.random()*3+0.2)*60*1000);</script>'
		else:
			raise
	finally:
		wikipedia.endContent()
		wikipedia.stopme()

