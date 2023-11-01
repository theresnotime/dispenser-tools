#! /usr/bin/python
"""


http://geodata.grid.unep.ch/download/
http://tdr.tug-libraries.on.ca/DRCUG/GIS/esri_worldadmin98.htm
http://opengrads.org/doc/udxt/shape/shape.html#esri_first_level_world_administrative_boundaries_1998



bzip2 /home/para/worldadmin98.sql.bz2 -dc | mysql -h sql-s1-user u_dispenser

XXX 
  SPATIAL KEY `area` (`area`(32))
needs to be change to 
  SPATIAL KEY `area` (`area`)


 -wiki: 	(default: enwiki)

Usage:
./regioncheck.py -wiki:enwiki
"""
import MySQLdb, math, sys
import time; starttime=time.time()
Inf = float('inf')

iso_corrections = {
	'FX':	'FR',
	'RS':	'CS',
	'UK':	'GB',
# Subdivisions in ISO 3166-1 
	# CN
	'CN-91':'HK',
	'CN-92':'PF',
	'CN-71':'TW',
	# FI
	'FI-AL':'AX',
	# FR
	'FR-BL':'BL',
	'FR-GF':'GF',
	'FR-GP':'GP',
	'FR-MF':'MF',
	'FR-MQ':'MQ',
	'FR-NC':'NC',
	'FR-PF':'PF',
	'FR-PM':'PM',
	'FR-RE':'RE',
	'FR-TF':'TF',
	'FR-WF':'WF',
	'FR-YT':'YT',
	# NO	
	'NO-21':'SJ',
	'NO-22':'SJ',
	# US
	'US-AS':'AS',
	'US-GU':'GU',
	'US-MP':'MP',
	'US-PR':'PR',
	'US-UM':'UM',
	'US-VI':'VI',

}
# FIXME build addition list from the list above
iso_additions = {
	'FR':	'TR',
}
iso_ignore = (
# dewiki oceans
'XA','XP','XS','XI',
)
# Since the database it build for FLIP we need to convert
# certain ISO codes to FLIP
iso2fips = {
	'AE':	'TC', # United Arab Emirates, code since changed
	'GG':	'GK',
	'ME':	'MW',
	'AE':	'TC',
	'RS':	'SR', # Serbia, iso change
	'TL':	'TT', # Does not exist
}

def output(*s):
	print '\t'.join(s)
	if logfile:
		f = open(logfile, 'a')
		f.write('\t'.join(s)+'\n')
		f.close()

def main():
	global logfile
	logfile = ""
	wiki = None
	rf = 10e-6 # Rounding factor
	for arg in sys.argv[1:]:
		if arg.startswith('-wiki:'):
			wiki = arg[6:]
		elif arg.startswith('-log:'):
			pass
		elif arg == "-help" or arg == "--help" or arg == "-h":
			print __doc__
	
	# Check inputs
	if not wiki:
		print __doc__
		sys.exit(0)

	# Setup worldadmin connection
	sql_db = MySQLdb.connect(db='u_dispenser_p', host='sql', read_default_file="/home/dispenser/.my.cnf")
	wa98 = sql_db.cursor()
	
	logfile = "%s/regioncheck-%s.log" % ("/home/dispenser/public_html/logs", wiki,)
	
	# Setup 
	db = MySQLdb.connect(db='u_dispenser_p', host=wiki.replace('_', '-')+'-p.db.toolserver.org', read_default_file="/home/dispenser/.my.cnf")
	c = db.cursor()
	c.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
	c.execute("""
SELECT gc_from, gc_name, gc_primary, gc_region, gc_type, gc_lat, gc_lon, gc_location
FROM coord_"""+wiki+"""
WHERE gc_region IS NOT NULL AND gc_region != ""
ORDER BY gc_region
""")

	# Try the following
	output('# Name'.ljust(47), 'region:', 'type:   ', 'Nearest state', 'Nearest landmass', 'Notes')
	for (page_id, name, primary, region, type, lat, lon, point) in c.fetchall():
		pagelink = primary and (name) and "[[%s]]"%name or "[[?curid=%s|%s]]"%(page_id, name)
		pagelink = pagelink.ljust(47, ' ')
		foundwithin = []
		
		# Produce a list of region to check
		checkregions = []
		for s in region.split('/'):
			if s == '':
				continue
			# Three digit iso codes
			if s[3:4] == '-' or s.isalpha() and len(s) == 3:
				continue
			# strip to alpha 1
			if s[2:3] == '-':
				s = s[0:2].upper()
			# Check blacklist
			if s in iso_ignore:
				continue
			# FIPS convertion
			#if s.startswith('RS'):
			#	print region
			#	print iso_corrections.get(region, region).split('-')[0]
			#	print iso2fips.get(region, "----")
			# Apply iso region corrections
			checkregions.append(iso_corrections.get(s, s))
		
		land_distsq = Inf
		land_iso = ''
		land_state = ''
		iso_distsq = Inf
		iso_iso = ''
		iso_state = ''
		#
		inside = False
		# 
		for region in checkregions:
			# Notes
			# We use two routines, one measures distances based on location the other measure based on region code
			#
			#
			# optismation: Check if we are already inside
			wa98.execute("SELECT country_iso, country_fips, state, AsText(area) as area FROM worldadmin98 WHERE MBRWithin(PointFromText('Point(%s %s)'),area) AND (country_iso = %s OR country_fips = %s)", (lat,lon, region, iso2fips.get(region, '--')) )
			for result in wa98.fetchall():
				if region == result[0] or iso2fips.get(region, '-') == result[1]:
					if myWithin(result[3], "POINT(%s %s)"%(lat,lon)):
						foundwithin.append( (result[0], result[2]) )
						inside = True
						break
			if inside:
				break
			
			# Not inside any of the regions
			wa98.execute("SELECT country_iso, state, AsText(area) as area FROM worldadmin98 WHERE country_iso = %s OR country_fips = %s", (region, iso2fips.get(region, '--')))
			for (country_iso, state, poly) in wa98.fetchall():
				if myWithin(poly, "POINT(%s %s)"%(lat,lon)): d = 0
				else: d = distanceSq(poly, "POINT(%s %s)"%(lat,lon))
				if d < land_distsq:
					land_distsq = d
					land_iso = country_iso
					land_state = state
				elif d==0 and land_distsq == 0:
					print "inside two polys"
				#	break
			
			#TODO some logic here to skip if we're close enough
			# Check for the nearest friendly
			wa98.execute("SELECT country_iso, state, AsText(area) as area FROM worldadmin98 WHERE MBRIntersects(GeomFromText(%s),area)",
				('Polygon((%s %s, %s %s, %s %s, %s %s, %s %s))'%(lat+5,lon+5,  lat+5,lon-5,  lat-5,lon-5,  lat-5,lon+5,  lat+5,lon+5,),
				)
			)
			for (country_iso, state, poly) in wa98.fetchall():
				if myWithin(poly, "POINT(%s %s)"%(lat,lon)): d = 0
				else: d = distanceSq(poly, "POINT(%s %s)"%(lat,lon))
				if d < iso_distsq:
					iso_distsq = d
					iso_iso = country_iso
					iso_state = state
				elif d==0 and iso_distsq == 0:
					print "inside two polys"
				#	break
	
		# OK - All checks out
		if inside:
			pass
		# No valid regions were given
		elif checkregions == []:
			pass
		elif land_distsq < 0.018:
			# Ignore distances less than 15 km, 30 km lower resolution
			pass
		# Country ISO does not match any in database
		elif land_distsq == Inf:
			output(pagelink, region, type or '-', 'Country code %r not in database.' % checkregions, '', '')
		#elif land_distsq > 0.070 or land_distsq > 0.018 and not ((lat+rf)%0.001 < 2*rf and (lon+rf)%0.001 < 2*rf):# (20 / 111.317)**2 :
		#	# Ignore distances less than 15 km, 30 km lower resolution
		#	if foundwithin != []:
		#		output(pagelink, region, type or '-', "%d km outside of %s (%s); found within %s"%(111.317*math.sqrt(land_distsq), land_state, land_iso, ' and '.join(["%s (%s)"%(b,a) for (a,b) in foundwithin])), '%r %r %r ' % (iso_distsq, iso_iso, iso_state, ))
		#	else:
		#		output(pagelink, region, type or '-', "%d km outside of %s (%s)"%(111.317*math.sqrt(land_distsq), land_state, land_iso), '%r %r %r' % (iso_distsq, iso_iso, iso_state,))
		else:
			if land_distsq == iso_distsq and land_state==iso_state and land_iso==iso_iso:
				da = 'OFFSET'
			elif iso_distsq == Inf:
				da = 'ISOLATED'
			elif land_distsq > 0.8 and iso_distsq == 0:
				da = 'ERROR'
			else:
				da = 'NA'# Not Assiged
			output(pagelink, 
			region, 
			(type or '-').ljust(8), 
			"%5d km outside of %s (%s)"%(111.317*math.sqrt(land_distsq), land_state, land_iso,),
			iso_distsq != Inf and "%5d km outside of %s (%s)"%(111.317*math.sqrt(iso_distsq), iso_state, iso_iso,) or 'INF',
			da
			)

	# Close connections
	wa98.close()
	c.close()



def distanceSq(polygon, point, distance = Inf):
	# Find mininum distance to the polygon
	# POLYGON((    ))
	points = [(float(x), float(y)) for x,y in (s.split(' ') for s in polygon[9:-2].split(','))]
	p = point[6:-1].split(' ')
	lat, lon = float(p[0]), float(p[1])
	for i, (px, py) in enumerate(points):
		m = (py - points[i-1][1]) / (px - points[i-1][0] or 1e-10)
		if px + m*py > lat + m*lon > points[i-1][0] + m*points[i-1][1] or points[i-1][0] + m*points[i-1][1] > lat + m*lon > px + m*py:
			# http://www.worsleyschool.net/science/files/linepoint/method5.html
			d = (m*lat - lon + (py-m*px))**2 / (m**2 + 1)
		else:
			d = (px - lat)**2 + (py - lon)**2
		if d < distance:
			distance = d
	return distance
	

"""
Purpose: Inside/outside polygon test of a point by calculating the number of time an horizontal ray emanating from a point to the rigth intersects the lines
segments making up the polygon (even=no, odd=yes)
Author: Paul Bourke, python adaptation: Dispenser

MySQL only does MBR
http://bugs.mysql.com/bug.php?id=24659

http://local.wasp.uwa.edu.au/~pbourke/geometry/insidepoly/
"""
def myWithin(myPolygon,point):
	counter = 0;
	#// get the x and y coordinate of the point
	p = point[6:-1].split(' ')
	px, py = float(p[0]), float(p[1])
	#// make an array of points of the polygon
	polygon = [(float(x), float(y)) for x,y in (s.split(' ') for s in myPolygon[9:-2].split(','))]
	#// number of points in the polygon
	n = len(polygon)
	poly1 = polygon[0]
	for i in range(1, n):
		poly2 = polygon[i % n]
		poly1x, poly1y = poly1
		poly2x, poly2y = poly2
		if poly1y != poly2y and min(poly1y,poly2y) < py <= max(poly1y,poly2y):
			if px <= max(poly1x,poly2x):
				if poly1x == poly2x or px <= (py-poly1y)*(poly2x-poly1x)/(poly2y-poly1y)+poly1x:
					counter+=1
		poly1 = poly2;
	# even = outside = False, odd = inside = True
	return (counter % 2 == 1)

if __name__ == "__main__":
	try:
		main()
	finally:
		output("Completed in %#4.2f minutes with python using %s seconds of CPU" %((time.time()-starttime)/60, time.clock()))
