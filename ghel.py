#! /usr/bin/env python
# -*- coding: utf-8  -*-
"""
GHEL - GeoHack External Links

ghel (pronounced jell) is a library that handle external link used by and generated for the GeoHack program 

TODO:
Documentation goes here

example:

./ghel.py -dbname:enwiki

Which will run a simple test on external links from the enwiki database

Parameters
	-dbname:

	-refUrl:
"""
import urllib
import re

# precompile regular expressions
swap_latlng = re.compile(r'^([0-9_.,]+_[WEO]_)([0-9_.,]+_[NSZ]_)')

# s.find('W_')+1 or [...] or len(s) fails with 1_N_2_E_heading:_W_
latlng_delimiter  = re.compile(r'_[WEOLwe](?=_)|$')
latlong_semicolon = re.compile(r'^([-]?[0-9.,]+);([-]?[0-9.,]+)(?=_[^NESWOZ])')

# TODO research and recommend coordinate systems
# http://astrogeology.usgs.gov/Projects/WGCCRE/constants/iau2000_table2.html
# http://reference.wolfram.com/legacy/applications/astronomer/CoordinateFunctions/JupiterCoordinates.html
# http://en.wikipedia.org/wiki/Prime_Meridian#Other_planetary_bodies
# http://planetarynames.wr.usgs.gov/TargetCoordinates
# http://astropedia.astrogeology.usgs.gov/alfresco/d/d/workspace/SpacesStore/442665d4-2d6c-40d8-8ea5-22d6121bf97f/table2.pdf

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
default_scale = {
	'country'	:  10000000, # 10 mill
	'satellite'	:  10000000, # 10 mill
	'state'		:   3000000, # 3 mill
	'adm1st'	:   1000000, # 1 mill
	'adm2nd'	:    300000, # 300 thousand
	'adm3rd'	:    100000, # 100 thousand
	'city'		:    100000, # 100 thousand
	'mountain'	:    100000, # 100 thousand
	'isle'		:    100000, # 100 thousand
	'river'		:    100000, # 100 thousand
	'waterbody'	:    100000, # 100 thousand
	'forest'	:     50000, # 50 thousand
	'glacier'	:     50000, # 50 thousand
	'event'		:     50000, # 50 thousand
	'airport'	:     30000, # 30 thousand
	'railwaystation': 10000, # 10 thousand
	'edu'		:     10000, # 10 thousand
	'pass'		:     10000, # 10 thousand
	'camera'	:     10000, # 10 thousand
	'landmark'	:     10000, # 10 thousand
}
headings = {
'n':	0.00,
'nbe':	11.25,
'nne':	22.50,
'nebn':	33.75,
'ne':	45.00,
'nebe':	56.25,
'ene':	67.50,
'ebn':	78.75,
'e':	90.00,
'ebs':	101.25,
'ese':	112.50,
'sebe':	123.75,
'se':	135.00,
'sebs':	146.25,
'sse':	157.50,
'sbe':	168.75,
's':	180.00,
'sbw':	191.25,
'ssw':	202.50,
'swbs':	213.75,
'sw':	225.00,
'swbw':	236.25,
'wsw':	247.50,
'wbs':	258.75,
'w':	270.00,
'wbn':	281.25,
'wnw':	292.50,
'nwbw':	303.75,
'nw':	315.00,
'nwbn':	326.25,
'nnw':	337.50,
'nbw':	348.75,
}
heading_corrections = {
# Incorrect boxing
'nnebn': 'nbe',  # 11.25
'nnebe': 'nebn', # 33.75
'enebn': 'nebe', # 56.25
'enebe': 'ebn',  # 78.75
'esebe': 'ebs',  # 101.25
'esebs': 'sebe', # 123.75
'ssebe': 'sebs', # 146.25
'ssebs': 'sbe',  # 168.75
'sswbs': 'sbw',  # 191.25
'sswbw': 'swbs', # 213.75
'wswbs': 'swbw', # 236.25
'wswbw': 'wbs',  # 258.75
'wnwbw': 'wbn',  # 281.25
'wnwbn': 'nwbw', # 303.75
'nnwbw': 'nwbn', # 326.25
'nnwbn': 'nbw',  # 348.75

'nnebne': 'nebn', # 33.75
'enebne': 'nebe', # 56.25
'esebse': 'sebe', # 123.75
'ssebse': 'sebs', # 146.25
'sswbsw': 'swbs', # 213.75
'wswbsw': 'swbw', # 236.25
'wnwbnw': 'nwbw', # 303.75
'nnwbnw': 'nwbn', # 326.25

'nebnne': 'nebn', # 33.75
'nebene': 'nebe', # 56.25
'sebese': 'sebe', # 123.75
'sebsse': 'sebs', # 146.25
'swbssw': 'swbs', # 213.75
'swbwsw': 'swbw', # 236.25
'nwbwnw': 'nwbw', # 303.75
'nwbnnw': 'nwbn', # 326.25

# Forgetting the 'b's
# EN may also mean NE
'nen': 'nebn', # 33.75
'nee': 'nebe', # 56.25
'en':  'ebn',  # 78.75
'es':  'ebs',  # 101.25
'see': 'sebe', # 123.75
'ses': 'sebs', # 146.25
'sws': 'swbs', # 213.75
'sww': 'swbw', # 236.25
'ws':  'wbs',  # 258.75
'wn':  'wbn',  # 281.25
'nww': 'nwbw', # 303.75
'nwn': 'nwbn', # 326.25

# Confusing order?  Likely not what they intended
'nbne': 'nebn', # 33.75
'ebne': 'nebe', # 56.25
'ebse': 'sebe', # 123.75
'sbse': 'sebs', # 146.25
'sbsw': 'swbs', # 213.75
'wbsw': 'swbw', # 236.25
'wbnw': 'nwbw', # 303.75
'nbnw': 'nwbn', # 326.25

# Not abbreviated
# XXX o -> e hack
'nerth':			'n',   # 0.00,
'nerth-nertheast':	'nne', # 22.50,
'nertheast':		'ne',  # 45.00,
'east-nertheast':	'ene', # 67.50,
'east': 			'e',   # 90.00,
'east-seutheast':	'ese', # 112.50,
'seutheast':		'se',  # 135.00,
'seuth-seutheast':	'sse', # 157.50,
'seuth':			's',   # 180.00,
'seuth-seuthwest':	'ssw', # 202.50,
'seuthwest':		'sw',  # 225.00,
'west-seuthwest':	'wsw', # 247.50,
'west': 			'w',   # 270.00,
'west-nerthwest':	'wnw', # 292.50,
'nerthwest':		'nw',  # 315.00,
'nerth-nerthwest':	'nnw', # 337.50,

# dyslexics
'en': 'ne',
'es': 'se',
'ws': 'sw',
'wn': 'nw',
}
type_corrections = {
	# Adminstrative district issues for non-English speaker 
	'admin1st':	'adm1st',
	'admin2nd':	'adm2nd',
	'admin3rd':	'adm3rd',
	'admin':	'adm1st',
	'admin1':	'adm1st',
	'admin2':	'adm2nd',
	'admin3':	'adm3rd',
	'adm':  	'adm1st',
	'adm1': 	'adm1st',
	'adm2': 	'adm2nd',
	'adm3': 	'adm3rd',
	'adm2st':	'adm2nd',
	'adm3st':	'adm3rd',
	'adm1nd':   'adm1st',
	'adm3nd':	'adm3rd',
	'adm1rd':	'adm1st',
	'adm2rd':	'adm2nd',
	# Common typos and mistakes
	'montain':	'mountain', # 198 (frwiki mostly)
	'buildings':'building', # 208 
	#'railway':	'railwaystation', # 226
	'railwaystationstation': 'railwaystation', # 106
	'station':	'railwaystation', # 103
	# TODO research: landscape, town, user, island, 
	'lake': 	'waterbody', # 953
	'water':	'waterbody', #  50
	')':    	'', # 141
}
region_corrections = {
	# China
	'CN-71':'TW',
	'CN-91':'HK',
	'CN-92':'MO',
	# Finland
	'FI-AL':'AX',
	# France
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
	# Netherlands
	'NL-AW':'AW',
	'NL-BQ1':'BQ',
	'NL-BQ2':'BQ',
	'NL-BQ3':'BQ',
	'NL-CW':'CW',
	'NL-SX':'SX',
	# Norway
	'NO-21':'SJ',
	'NO-22':'SJ',
	# United States
	'US-AS':'AS',
	'US-GU':'GU',
	'US-MP':'MP',
	'US-PR':'PR',
	'US-UM':'UM',
	'US-VI':'VI',
	# Exceptional reserved
	# TODO Wild card sub-devisions
	'FX':'FR', # Metropolitan of France
	'UK':'GB',
	'SF':'FI',
	'YU':'CS',
}
# Updated: August 2011
iso3166_1_alpha_2 = [
# Officially assigned
"AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT", "AU", "AW", "AX", "AZ", "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS", "BT", "BV", "BW", "BY", "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN", "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM", "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK", "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM", "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK", "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM", "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW", "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW", "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI", "VN", "VU", "WF", "WS", "YE", "YT", "ZA", "ZM", "ZW", 
# User-assigned
## dewiki ocean code (see [[de:Vorlage:Coordinate#Ozeane]])
'XA', 'XI', 'XN', 'XP', 'XS',
'XO', # Geostationary orbit
## International waters ([[Template:GeoTemplate]])
'XZ',
# Exceptionally reserved
'AC', 'CP', 'DG', 'EA', 'EU', 'FX', 'IC', 'SU', 'TA', 'UK',
# Transitionally reserved (TODO raise warnings)
'AN', 'BU', 'CS', 'NT', 'SF', 'TP', 'YU', 'ZR', 
# Indeterminately reserved
'DY', 'EW', 'FL', 'JA', 'LF', 'PI', 'RA', 'RB', 'RB', 'RC', 'RH', 'RI', 'RL', 'RM', 'RN', 'RP', 'WG', 'WL', 'WV', 'YV',
# User request
'??',
# Commons category hack 
'CAT',
]

# Notes:
# UK is reserved, but is often (incorrectly) used as an alais for GB
# 
#iso3166_2
# FIXME program better?
try:
	# Orginal data source, not up to date
	from iso_3166_2 import subdivision 
except ImportError:
	subdivision = []
# Old code, not easy to generate
subcodes = {
'AU':"NSW,QLD,SA,TAS,VIC,WA,ACT,NT,CC,CX,HM,NF".split(','),
'CA':"AB,BC,MB,NB,NL,NS,ON,PE,QC,SK,NT,NU,YT".split(','),
'CH':"AG,AR,AI,BL,BS,BE,FR,GE,GL,GR,JU,LU,NE,NW,OW,SG,SH,SZ,SO,TG,TI,UR,VS,VD,ZG,ZH".split(','),
'CN':"11,50,31,12,34,35,62,44,52,46,13,23,41,42,43,32,36,22,21,63,61,37,14,51,71,53,33,45,15,64,65,54,91,92".split(','),
'DE':"BW,BY,BE,BB,HB,HH,HE,MV,NI,NW,RP,SL,SN,ST,SH,TH".split(','),
'GB':"ABE,ABD,ANS,ANT,ARD,AGB,ARM,BLA,BLY,BNB,BDG,BNE,BNS,BAS,BDF,BFS,BEX,BIR,BBD,BPL,BGW,BOL,BMH,BRC,BRD,BEN,BGE,BNH,BST,BRY,BKM,BUR,CAY,CLD,CAM,CMD,CRF,CMN,CKF,CSR,CGN,CHS,CLK,CLR,CWY,CKT,CON,COV,CGV,CRY,CMA,DAL,DEN,DER,DBY,DRY,DEV,DNC,DOR,DOW,DUD,DGY,DND,DGN,DUR,EAL,EAY,EDU,ELN,ERW,ERY,ESX,EDH,ELS,ENF,ESS,FAL,FER,FIF,FLN,GAT,GLG,GLS,GRE,GWN,HCK,HAL,HMF,HAM,HRY,HRW,HPL,HAV,HEF,HRT,HLD,HIL,HNS,IVC,AGY,IOW,IOS,ISL,KEC,KEN,KHL,KTT,KIR,KWL,LBH,LAN,LRN,LDS,LCE,LEC,LEW,LMV,LIN,LSB,LIV,LND,LUT,MFT,MAN,MDW,MTY,MRT,MDB,MLN,MIK,MON,MRY,MYL,NTL,NET,NWM,NWP,NYM,NTA,NFK,NAY,NDN,NEL,NLK,NLN,NSM,NTY,NYK,NTH,NBL,NGM,NTT,OLD,OMH,ORK,OXF,PEM,PKN,PTE,PLY,POL,POR,POW,RDG,RDB,RCC,RFW,RCT,RIC,RCH,ROT,RUT,SLF,SAW,SCB,SFT,SHF,ZET,SHR,SLG,SOL,SOM,SAY,SGC,SLK,STY,STH,SOS,SWK,SHN,STS,STG,SKP,STT,STE,STB,SFK,SND,SRY,STN,SWA,SWD,TAM,TFW,THR,TOB,TOF,TWH,TRF,VGL,WKF,WLL,WFT,WND,WRT,WAR,WBK,WDU,WLN,WSX,WSM,WGN,WIL,WNM,WRL,WOK,WLV,WOR,WRX,YOR,ENG,NIR,SCT,WLS,EAW,GBN,UKM".split(','),
'IN':"AP,AR,AS,BR,CT,GA,GJ,HR,HP,JK,JH,KA,KL,MP,MH,MN,ML,MZ,NL,OR,PB,RJ,SK,TN,TR,UL,UP,WB,AN,CH,DN,DD,DL,LD,PY".split(','),
'JP':"23,05,02,38,21,10,34,01,18,40,07,28,08,17,03,37,46,14,39,43,26,24,04,45,20,42,29,15,44,33,47,27,41,11,25,32,22,12,09,36,13,31,16,30,06,35,19".split(','),
'MX':"DIF,AGU,BCN,BCS,CAM,COA,COL,CHP,CHH,DUR,GUA,GRO,HID,JAL,MEX,MIC,MOR,NAY,NLE,OAX,PUE,QUE,ROO,SLP,SIN,SON,TAB,TAM,TLA,VER,YUC,ZAC".split(','),
'RS':"KM,VO,00,01,06,05,03,02,04,14,11,23,09,25,28,29,08,17,20,24,26,22,10,13,27,19,18,07,12,21,15,16".split(','),
'US':"AL,AK,AZ,AR,CA,CO,CT,DE,FL,GA,HI,ID,IL,IN,IA,KS,KY,LA,ME,MD,MA,MI,MN,MS,MO,MT,NE,NV,NH,NJ,NM,NY,NC,ND,OH,OK,OR,PA,RI,SC,SD,TN,TX,UT,VT,VA,WA,WV,WI,WY,DC,AS,GU,MP,PR,UM,VI".split(','),
}

# Docu request
typelessCount = 0
prependCount = 0

# FIXME describle error and warning and how to get ride of them
def void(*s):
	pass
def debug(*s):
	print 'DEBUG:  \t'+ '\t'.join(s)
def info(*s):
	print 'Message:  \t'+ '\t'.join(s)
def warn(*s):
	print 'Warning:\t'+ '\t'.join(s)
def error(*s):
	print 'Error:  \t'+ '\t'.join(s)

class Geolink:
	def __init__(self):
		"""
		"""
		# Define properties
		self.lat = None
		self.lng = None
		self.classification=None
		self.dim = None
		self.elevation=None
		self.globe=None
		self.heading=None
		self.region=None
		self.scale=None
		self.source=None
		self.type=None 
		self.typesize=None
		# TODO add google earth's image overlay over 3d background stuff
		# e.g. pitch, roll, field of view (h & v)

		self.title=None
		self.pagename=''

		# Debug properties...
		self.params = []
		self.raw_coord = ''

	def getelevation(self):
		if not self.elevation:
			# TODO  prep call service to establish elevation
			pass
		return self.elevation
	def getscale(self, default=0):
		"return .scale if exists or compute a approximation base on other properties"
		# TODO fallback: city size 
		# TODO fallback: lat/lng resolution
		if self.scale:
			return self.scale
		elif False:
				try:
					self.scale = float(s[4:]) * 1000000.0
				except ValueError:
					warn('BadFloat', '%-8r\t[[%s]]'%(s,pagename))
		elif self.typesize :
			pass
		else:
			return default_scale.get(self.type, default)

	def simple_parse(self, link, defaultpagename=''):
		"""
		If all validation and notifications were removed this is what would be 
		left.  It actually even more robust as it can handle unbalanced crazy 
		inputs like
		    &params=1;2_3_4_source:sc_city_region:ko_region:me_json
		"""
		params = re.search(r'&params=([\d.+-]+)_?([\d.+-]*)_?([\d.+-]*)_?([NS;])_?([\d.+-]+)_?([\d.+-]*)_?([\d.+-]*)_?([EOW]?)_?([^&=]*)', link)
		lat_d, lat_m, lat_s = (float(s or 0) for s in params.group(1, 2, 3))
		lng_d, lng_m, lng_s = (float(s or 0) for s in params.group(5, 6, 7))
		
		self.lat = abs(lat_d) + lat_m/60.0 + lat_s/3600.0
		self.lng = abs(lng_d) + lng_m/60.0 + lng_s/3600.0
		if self.lat<0 or params.group(4)=='S': self.lat *= -1
		if self.lng<0 or params.group(8)=='W': self.lng *= -1
		
		switches = dict(switch.split(':', 1) for switch in m.group(9).split('_') if ':' in switch)

	
	def parse(self, link, defaultpagename=''):
		# Notes:
				# Note Z is supported by maps.asp
				# Note L used on pt: instead of E
		global typelessCount, prependCount
		pagename = defaultpagename
		params = []
		coord  = []
		# [[tswiki:GeoHack#Short URLs]]
		if '/' in link[31+2:31+12]: # XXX speed hack
			link = re.sub(r'/~geohack/([a-z\-]{2,12})/(.*?)[&?]?((?<=[?&])[a-z]+=.*|)$', r'/~geohack/geohack.php?language=\1&params=\2&\3', link)

		# MediaWiki stores %26 as & which breaking URLs.  We try to correct this
		# by assuming that if & is not followed by a = is encoded incorrectly
		# 
		# ex: http://en.wikipedia.org/w/api.php?action=query&prop=extlinks&titles=7th_%26_Capitol_and_8th_%26_Capitol
		# or SELECT el_to FROM externallinks WHERE el_from=10794325;
		# TODO file bug
		#if '%3C' in link: # XXX make speed hack work
		#	#i = link.index('<')
		#	#warn('Removed HTML', '%-8r\t[[%s]]'%(link[i:i+12], defaultpagename))
		#	link, n = re.subn(r'%3C.*?%3E', '', link)
		#	if n:warn('Removed HTML', '...\t[[%s]]'%(defaultpagename,))
		#link = re.sub(r'&(?=[^&=]*?(&|$))', '%27', link)
		link = reduce(lambda x,y: x+'&'+y if '=' in y else x+'%26'+y, link.split('&'))
	
		for s in link[link.index('?')+1 : link.index('#') if '#' in link else None].split('&'):
			if s.startswith('language='):
				pass
				
			elif s.startswith('pagename='):
				# Optional
				try:
					pagename = urllib.unquote(s[9:]).decode('utf-8')[:255].encode('utf-8')
					# Skip if Template:GeoTemplate
					#if # '{' in pagename:
					if pagename in ('{pagename}', '{title}'):
						return
					# Check if legal MedaWiki title
					if any(c in pagename for c in '<\n>[]{|}'):
						error('Bad pagename', '%-8r\t[[%s]]'%(pagename, defaultpagename))
						continue
					elif len(pagename)>250:
					#	if self.title:
							error('Long pagename', '%-8r\t[[%s]]'%(pagename, defaultpagename))
							continue
					#	else:
					# TODO self.title == unicode string, self.pagename == byte string
					#		warn('Pagename too long', '%-8r\t[[%s]]'%(pagename, defaultpagename))
					#		self.title = pagename[:247].replace('_', ' ').strip()+'...'
					else:
						self.pagename = pagename
				except UnicodeDecodeError:
			  		error("utf-8 decoding failed", "%s\t[[%s]]"%(s, defaultpagename))
				
			elif s.startswith('params='):
				s = urllib.unquote(s[7:]).strip('_')+'_'
				# ASCII characters only
				try:	us = s.decode('utf-8')
				except: us = s.decode('latin-1')
				try:
					s = us.encode('ascii', 'strict')
				except UnicodeEncodeError as exc:
					import unicodedata
					warn('UTF8params', '%-8s\t[[%s]]' % (
						''.join(c for c in us[max(0,exc.start-8):exc.end+15].encode('utf-8') if ord(c) >= 0x20), 
						pagename, 
					))
					# Substitute Unicode characters with their ASCII counterpart
					# NFD
					# NFKD  "（）" (Double width) => ()
					s = unicodedata.normalize('NFKD', us).encode('ascii', 'ignore')
				
				# Check for restricted characters
				# removed { } due it their use in templates
				#if any(c in s for c in '&<=>[]{|}'):
				for c in '&<>[]|':	# unrolled to access c
					if c in s:
						error('Bad char %r'%c, '%-8r\t[[%s]]'% (s,pagename,))
						return
				
				# TODO improve with whitelisting all valid characters
				## Short URL check
				## passes {{fullurl:tools:~geohack/en/...}} test
				## Fails: ' % + ? ~ = 
				##m= re.search(r'[^0-9A-Za-z_.:;@$!*(),/\-   \'%+?~  {|}<=>[\]]', s)
				#m = re.search(r'[^0-9A-Za-z_.:;@$!*(),/\-   \'+?~=  {|}<>[\]]', s)
				#if m and not '_{' in s:
				#	#      Large longitude
				#	debug('Short URL check', '[%s]: %-8r\t[[%s]]'%(m.group(), s, pagename))
				
				# Fix issue with no space before direction (_63W)
				s,n = re.subn(r'(?<=\d)([NSZEWO])_', r'_\1_', s)
				if n:
					debug('forgot spaces',  '%-8r\t[[%s]]'% (s, pagename, ))

				if swap_latlng.match(s):
					warn('lat/lon swapped', '%-8r\t[[%s]]'% (s, pagename, ))
					s = swap_latlng.sub(r'\2\1', s)
				
				# TODO merge with latlng_delimiter
				# [0-9,.+-]+;[0-9,.+-]+(?=_)
				#s = re.sub(r'^([-]?[0-9.,]+);([-]?[0-9.,]+)(?=_[^NESWOZ])', r'\1_N_\2_E', s)
				#if latlong_semicolon.match(s):
				#	debug('semicolon-latlong', '%-8r\t[[%s]]'% (s, pagename, ))
					

				# Split input into coord and params
				i = latlng_delimiter.search(s).end()
				# '_ 
				# ' 	
				# , 	European decimal separator
				# --	Double negative
				cs = s[:i].replace("'_", '_').replace("'", '_').replace(',', '.').replace('--', '').upper()
				## '10,10_N__E' GeoHack doesn't actually parse this
				#cs = re.sub(r'([\d\.\-]+)[,_]+([\d\.\-]+)_([NSZ])_+([EWO])', r'\1_\3_\2_\4', cs)
				coord       = cs.split('_')
				self.params = s[i+1:-1].split('_')
			
			# 
			elif s.startswith('project='):
				# Only valid value is project=osm
				return
				
			# Undocumented, possibly former feature of maps.asp
			elif s.startswith('src='):
				warn('Bad parameter', '%-8r\t[[%s]]'%(s, pagename, ))
				
			#
			elif s.startswith('title='):
				self.title = urllib.unquote(s[6:].replace('+', ' '))
				try:    self.title = unicode(self.title, 'utf-8')
				except UnicodeDecodeError:
						self.title = unicode(self.title, 'latin-1')
			
			# 
			else:
				warn('Bad parameter', '%-8r\t[[%s]]'%(s, pagename, ))
		
		# Quietly skip templates: if {{{...}}} appears in nearly all parts
		if ''.join(coord).count('{{{')+(2 if 'N' in coord or 'S' in coord or 'Z' in coord else 1) >= len(coord):
			return

		try:
			def precision(s):
				i = s.find('.') + 1
				if i == 0:
					return 0
				if len(s) - i > 2:
					if 5 <= int(s[-2]) == int(s[-1]) - 1:
						# .555556
						s=s[:-1]+s[-2]
					s=s.rstrip(s[-2])
				return len(s) - i

			# Make sure we don't come up short on values
			# D M S N/S D M S E/W = 8
			self.raw_coord = '_'.join(coord)
			coord.extend(['']*(8-len(coord)))
			# XXX
			self.digits = 0

			if ';' in coord[0]:
				self.lat = float(coord[0].split(';')[0])
				self.lng = float(coord[0].split(';')[1])
				if len(coord) - coord.count('') > 2:
					warn('Too many parameters','%-8r\t[[%s]]' % (coord, pagename, ))
			elif coord[1] in 'NSZ' and coord[1]:
				# '10,10_N__E' GeoHack doesn't actually parse this
				#if ',' in coord[0] and not coord[2]:
				#	(coord[0], coord[2]) = coord[0].split(',')
				self.lat = float(coord[0] or 0) 
				self.lng = float(coord[2] or 0)
				# XXX 
				self.digits = max(0, len(coord[0])-(coord[0].find('.')+1), len(coord[2])-(coord[2].find('.')+1))
				if 'N' != coord[1]:
					self.lat *= -1
					if self.lat > 0:
						warn('Double negative', '%-8r\t[[%s]]'%(coord,pagename))
				if 'W' in coord:
					self.lng *= -1
					if self.lng > 0:
						warn('Double negative', '%-8r\t[[%s]]'%(coord,pagename))
				

				#
				#digits = max(precision(coord[0]), precision(coord[2]))
				if len(coord) - coord.count('') > 4:
					warn('Too many parameters','%-8r\t[[%s]]' % (coord, pagename, ))
				#elif digits > 12:
				##	lat_DMS = round((self.lat-int(self.lat))*36000, 4)
				##	lng_DMS = round((self.lng-int(self.lng))*36000, 4)
				##	if abs(lat_DMS - round(lat_DMS)) > 0.0001 and abs(lng_DMS - round(lng_DMS)) > 0.0001:
				#		debug('Overly precise %d'%digits, '%-8r\t[[%s]]' % (coord, pagename, ))
					
			elif coord[2] in 'NSZ' and coord[2]:
				# experimental
				# re.sub(r'([-\d]+)_(\d{5,})_+([NESWOZ])', r'\1.\2_\3
				lat_d, lat_m = float(coord[0] or 0), float(coord[1] or 0)
				lng_d, lng_m = float(coord[3] or 0), float(coord[4] or 0)

				self.lat = abs(lat_d) + lat_m/60.0
				self.lng = abs(lng_d) + lng_m/60.0
				# XXX
				self.digits = 2
				if 'N' != coord[2]: self.lat *= -1
				if 'W' in coord:     self.lng *= -1
				if lat_d < 0:
					self.lat *= -1
					if self.lat > 0:
						warn('Double negative', '%-8r\t[[%s]]'%(coord,pagename))
				if lng_d < 0:
					self.lng *= -1
					if self.lng > 0:
						warn('Double negative', '%-8r\t[[%s]]'%(coord,pagename))

				if coord[1:5:3].count('') % 2 == 1:
					warn('Zero assumed','%-8r\t[[%s]]' % (coord, pagename))
				elif not (0.0 <= lat_m <= 60.0 and 0.0 <= lng_m <= 60.0):
					warn('Out of range','%-8r\t[[%s]]' % (coord, pagename))
				elif len(coord) - coord.count('') > 6:
					warn('Too many parameters','%-8r\t[[%s]]' % (coord, pagename, ))
				elif not lat_d.is_integer() and lat_m!=0.0 or not lng_d.is_integer() and lng_m!=0.0:
					debug('decimals', '%-8r\t[[%s]]' % (coord, pagename))
			elif coord[3] in 'NSZ' and coord[3]:
				lat_d, lat_m, lat_s = float(coord[0] or 0), float(coord[1] or 0), float(coord[2] or 0)
				lng_d, lng_m, lng_s = float(coord[4] or 0), float(coord[5] or 0), float(coord[6] or 0)

				self.lat = abs(lat_d) + lat_m/60.0 + lat_s/3600.0
				self.lng = abs(lng_d) + lng_m/60.0 + lng_s/3600.0
				# XXX
				self.digits = 4
				if 'N' != coord[3]: self.lat *= -1
				if 'W' in coord:    self.lng *= -1
				if lat_d < 0:
					self.lat *= -1
					if self.lat > 0:
						warn('Double negative', '%-8r\t[[%s]]'%(coord,pagename))
				if lng_d < 0:
					self.lng *= -1
					if self.lng > 0:
						warn('Double negative', '%-8r\t[[%s]]'%(coord,pagename))

				if coord[1:6:4].count('') == 1 or coord[2:7:4].count('') == 1:
					warn('Zero assumed','%-8r\t[[%s]]' % (coord, pagename))
				elif not (0.0 <= lat_m <= 60.0 and 0.0 <= lat_s <= 60.0 and 0.0 <= lng_m <= 60.0 and 0.0 <= lng_s <= 60.0):
					warn('Out of range','%-8r\t[[%s]]' % (coord, pagename))
				elif len(coord) - coord.count('') > 8:
					warn('Too many parameters','%-8r\t[[%s]]' % (coord, pagename, ))
				elif not lat_d.is_integer() and lat_m!=0.0 or not lng_d.is_integer() and lng_m!=0.0:
					debug('decimals', '%-8r\t[[%s]]' % (coord, pagename))
				elif not lat_m.is_integer() and lat_s!=0.0 or not lng_m.is_integer() and lng_s!=0.0:
					debug('decimals', '%-8r\t[[%s]]' % (coord, pagename))
			elif coord[4] in 'NSZ' and coord[4]:
				# XXX Assume 4th column is the decimal of seconds
				lat_d, lat_m, lat_s = float(coord[0] or 0), float(coord[1] or 0), float('.'.join(coord[2:4]) or 0)
				lng_d, lng_m, lng_s = float(coord[5] or 0), float(coord[6] or 0), float('.'.join(coord[7:9]) or 0)

				self.lat = abs(lat_d) + lat_m/60.0 + lat_s/3600.0
				self.lng = abs(lng_d) + lng_m/60.0 + lng_s/3600.0
				if 'N' != coord[4]: self.lat *= -1
				if 'W' in coord:    self.lng *= -1
				if lat_d < 0:
					self.lat *= -1
					if self.lat > 0:
						warn('Double negative', '%-8r\t[[%s]]'%(coord,pagename))
				if lng_d < 0:
					self.lng *= -1
					if self.lng > 0:
						warn('Double negative', '%-8r\t[[%s]]'%(coord,pagename))

				if coord[1:7:5].count('') == 1 or coord[2:8:5].count('') == 1:
					warn('Zero assumed','%-8r\t[[%s]]' % (coord, pagename))
				elif not (0.0 <= lat_m <= 60.0 and 0.0 <= lat_s <= 60.0 and 0.0 <= lng_m <= 60.0 and 0.0 <= lng_s <= 60.0):
					warn('Out of range','%-8r\t[[%s]]' % (coord, pagename))
				elif len(coord) - coord.count('') > 10:
					warn('Too many parameters','%-8r\t[[%s]]' % (coord, pagename, ))
				else:
					# Not supported by GeoHack
					warn('dec-sec ','%-8r\t[[%s]]' % (coord, pagename))
			elif sum(y.isdigit() for y in ''.join(coord)) < 2:
				# typically templates and examples
				error('NoDigits','%-8r\t[[%s]]' % ('_'.join(coord), pagename, ))
				return
			elif not ('N' in coord or 'S' in coord or 'Z' in coord):
				error('No N/S  ','%r+%-8r\t[[%s]]' % ('_'.join(coord), self.params, pagename, ))
				return
			else:
				error('Unable to parse', '%-8r\t[[%s]]' % (coord, pagename, ) )
				return
			
			# Check for -NaN from {{#expr:}}
			if self.lat != self.lat or self.lng != self.lng: # NaN!=NaN per PEP 754
				error('NotANumber', '%-8r\t[[%s]]' % (coord, pagename, )) 
				return
			
			#if (len(coord) - coord.count(''))% 2 == 1:
			#	warn('UnevenCoord', '%-8r\t[[%s]]'%(coord, pagename,))
			
			# TODO check for lat/long mix ups
			# TODO do something with decimal checking
			# The decimal point may be forgotten sometimes
			# Some precision is lost due to the iterative divisions
			# lat >= 100,   reduce to 9<lat<=90 range
			if not -90.0 <= self.lat <= 90.0:
				warn('Large latitude', '%-8r\t[[%s]]' % ('_'.join(coord), pagename))
				if abs(self.lat) >= 100:
					while not -90.0 <= self.lat <= 90.0: self.lat/=10.0
				
			# long >= 1000, reduce to 18<long<=180 range
			# Note: other planets use [-360, 360]
			if not -360.0 <= self.lng <= 360.0:
				warn('Large longitude', '%-8r\t[[%s]]' % ('_'.join(coord), pagename))
				if abs(self.lng) >= 1000:
					while not -180.0 <= self.lng <= 180.0: self.lng/=10.0
		except ValueError, e:
			# Check to make sure there're at least two numbers, e.g. -29.3_N_0_W
			if sum(y.isdigit() for y in ''.join(coord)) < 2:
				# typically templates and examples
				error('NoDigits','%-8r\t[[%s]]' % ('_'.join(coord), pagename) )
			else:
				error('ValueError','%-8r\t[[%s]]'%('_'.join(coord), pagename) )
			return

		# Prepend is used to fix types which use an '_' instead of ':'
		# example: type_city_(20,000)
		prepend = ''
		used = {}
		for s in self.params:
			# Multiple colons
			colon_count = s.count(':')
			if colon_count == 1:
				pass
			elif colon_count == 0:
				if prepend:
					s, prepend = prepend+':'+s, ''
				if ';' in s:
					warn('Semicolon', '%-8r\t[[%s]]'%(s, pagename))
					s = s.replace(';', ':', 1)
				elif '=' in s:
					warn('Equalsign', '%-8r\t[[%s]]'%(s, pagename))
					s = s.replace('=', ':', 1)
			else:
				# Fix double struck params (type:type:city)
				i = s.find(':')+1
				if s[0:i] == s[0+i:i+i]:
					warn('Double struck', '%-8r\t[[%s]]' % (s, pagename))
					colon_count -= 1
					s = s[i:]
				if colon_count >= 2 and colon_count%2 == 1:
					if prepend:
						s, prepend = prepend+':'+s, ''
					# Fix colon as separator error (type:county:US)
					i = s.find(':', s.find(':')+1)
					if i+1 != len(s): # avoid 'region:CZ:'
						warn('Too many colons', '%-8r\t[[%s]]' % (s, pagename))
						self.params.append(s[i+1:]) # does not work with iters
					s = s[:i]

			# Commons has Capilization and FULLUPPERCASE
			i = s.find(':')
			if i >= 1 and s[:i].isalpha() and not s[:i].islower():
				# Warn on casing about anything GeoHack can't handle
				if s[:i].lower() in ('type','scale','dim','default','region',):
					warn('ParamCase', '%-8r\t[[%s]]' % (s, pagename))
				elif s[:i].lower() in ('heading',):
					# Commons specific, historically case insensitive
					pass
				else:
					pass
				s = s[:i].lower() + s[i:]
			if s[:i] in used and s:#s[:i+1]!='':
				#if not s.startswith('type:'):
				#	# Originally ignored type: since Commons uses a hack to give all coordinates type:landmark
					warn('Duplicate param', '%-8r\t[[%s]]' % (s, pagename))
			else:
				used[s[:i]] = True

			if not s:
				continue
			## Parameters supported in GeoHack
			elif s.startswith('type:'):
				self.type = s[5:]
			elif s.startswith('scale:'):
				try:
					self.scale = float(s[6:])
					if self.scale < 0:
						warn('NegScale','%-8r\t[[%s]]' % (s, pagename))
				except ValueError:
					warn('BadFloat','%-8r\t[[%s]]' % (s, pagename))
			elif s.startswith('default:'):
				# default: specifies the scale if it is not defined
				try:
					if self.scale is None:
						self.scale = s[8:]
				except ValueError:
					warn('BadFloat','%-8r\t[[%s]]' % (s, pagename))
			elif s.startswith('region:'):
				self.region = s[7:]
			elif s.startswith('globe:'):
				self.globe = s[6:]
			elif s.startswith('source:'):
				self.source = s[7:]
				try:
					# User unwittingly include _ when giving the source
					srcpos = len(self.params)
					for i, nextparam in enumerate(self.params):
						if   i <= srcpos or nextparam=='': 
							if nextparam.startswith(s): srcpos = i
							continue
						if ':' in nextparam or nextparam=='': break
						self.source += " " + self.params.pop(i)
				except:
					debug('unable to merge', '%-8r\t[[%s]]' %  (s, pagename))
			elif s.startswith('dim:'):
				# Diameter in meters (NOT equivalent to span)
				# Actually scale is so poorly defined it could be anything, m, km, cm, inch, pixels.
				try:
					# GeoHack supports km and m for dim:
					if s.endswith('km'):
						self.dim = float(s[4:-2]) * 1000.0
					elif s.endswith('m'):
						self.dim = float(s[4:-1])
					elif s.endswith('mi'):
						self.dim = float(s[4:-2]) * 1609.344
						warn('DimUnit ','%-8r\t[[%s]]'%(s,pagename))
					elif s.endswith('ft'):
						self.dim = float(s[4:-2]) * 0.3048
						warn('DimUnit ','%-8r\t[[%s]]'%(s,pagename))
					else:
						self.dim = float(s[4:])
					if not 0 < self.dim < 40000000: # max size ~ Jupiter's spot
						warn('DimRange', '%-8r\t[[%s]]'%(self.dim, pagename))
						self.dim = abs(self.dim) # avoid DB errors
				except ValueError:
					error('DimError','%-8r\t[[%s]]'%(s,pagename))
			## Parameters NOT support in GeoHack
			# Caviotes: Many tool ignore case warnings and
			# 
			# Zoom only supported by nlwiki's maps.asp
			elif s.startswith('zoom:'):
				# SCALE = POWER(2, 12 - ZOOM) * 100000
				try:
					self.scale = 100000 * (2**(12-int(s[5:])))
				except ValueError:
					error('BadInt  ','%-8r\t[[%s]]'%(s,pagename))
			# Commons
			elif s.startswith('heading:'):
				head = s[8:].replace('by', 'b').lower().replace('o', 'e')
				# Degrees
				if s[8:].translate(None, '+-.').isdigit():
					try:
						self.heading = float(s[8:])
					except ValueError:
						error('BadFloat','%-8r\t[[%s]]' % (s, pagename))
					else:
						if not 0.0 <= self.heading <= 360.0:
							warn('Heading range','%-8r\t[[%s]]' % (s, pagename))
						self.heading %= 360.0
				# Valid compase rose
				elif head in headings:
					self.heading = headings[head]
				# Correct heading:SEE to heading:SEbE
				elif head in heading_corrections:
					if head == heading_corrections[head].replace('b', ''):
						warn('Missing b', '%-8r\t[[%s]]' % (s, pagename))
					else:
						warn('Bad heading', '%-8r\t[[%s]]' % (s, pagename))
					self.heading = headings.get(heading_corrections[head])
				# Headings marked unknown or empty
				elif head in ('?', ''):
					pass
				# Heading used as pitch
				elif head in ('up', 'down'):
					pass
				else:
					error('Heading ','%-8r\t[[%s]]' % (s, pagename))
					pass
			elif s.startswith('alt:'):
				try:             	self.elevation = float(s[4:])
				except ValueError:	error('BadFloat','%-8r\t[[%s]]'%(s,pagename))
			elif s.startswith('elevation:'):
				try:             	self.elevation = float(s[10:])
				except ValueError:	error('BadFloat','%-8r\t[[%s]]'%(s,pagename))
			elif s.startswith('height:'):
				pass
			elif s=='class:object':
				self.classification = s[6:]
			#elif s.startswith('class:'):
			#	self.classification = s[6:]
			# Some weird Commons thing
			elif s.startswith('name:'):
				if not self.title:
					self.title = s[5:]
				warn('Invldparam','%-8r\t[[%s]]'%(s,pagename))
				break # Its just garbage from this point
			## Error correction begins
			elif s == '...':
				# People copying template without changing it
				pass
			# Fixes instances where 'type' wasn't printed
			elif s.startswith('city(') or s.lower() in default_scale.keys() + [
				# Not actually support by any software but still used
				'building', 'village', 'commnity', 'municipality', 'town', 'settlement', 
				'buildings', 'subdivision', 'military', 'water',]:
				self.type = s.lower()
				#if self.type != 'city':
				warn('Typeless','%-8r\t[[%s]]' % (s, pagename, ))
				typelessCount += 1
			# Input mistyped
			elif s.lower() in ('scale', 'region', 'globe', 'source', 'type', 'heading', 'alt', 'dim', 'class', 'elevation',):
				prepend = s
				warn('Missing colon', '%-8r\t[[%s]]' % (s, pagename, ))
				#prependCount += 1
			# Assume that left over NESW are heading, very broad assumption
			# this overrules the regionless below
			elif s.lower().replace('o', 'e') in headings:
				self.heading = headings[s.lower().replace('o', 'e')]
				warn('Headingless', '%-8r\t[[%s]]'%(s, pagename, ))
			# Assume that the prefix was typed wrong if we're matching the keys
			elif ':' in s and s[s.find(':')+1:].lower() in headings:
				self.heading = headings[s[s.find(':')+1:].lower()]
				warn('Assumed heading', '%-8r\t[[%s]]'%(s, pagename, ))
			# Assume 2 uppercased letters are country code
			elif s[:2].isupper() and (len(s)==2 or len(s)>2 and s[2]=='-'):
				if self.region:	self.region+='-'+s
				else:			self.region=s
				warn('Regionless', '%-8r\t[[%s]]' % (self.region, pagename, ))
			# Assuming keywords are data sources
			# TODO improve dewiki-GNIS
			elif s.lower() in ('exif', 'google', 'gnis', 'osgb36'):
				self.source=s
				warn('Sourceless',  '%-8r\t[[%s]]' % (self.source, pagename, ))
			# Plain number could be typesize, scale, or something else
			elif s.translate(None, '+-/.').isdigit():
				# All digits, assume scale:X000
				if s.isdigit() and 3 < s.count('0') + 1 <= len(s):
					self.scale=float(s)
					warn('Scaleless','%-8r\t[[%s]]' % (s, pagename))
				# RAW EXIF GPSAltitude
				# TODO GPS altituted should be check against NASA terrain map
				# XXX GPS doesn't work under water
				elif s.count('/') == 1:
					i = s.find('/')
					try:
						self.elevation = float(s[:i])/float(s[i+1:])
						warn('GPS Altitude','%-8r\t[[%s]]' % (s, pagename))
					except ValueError:
						error('BadFloat','%-8r\t[[%s]]'%(s,pagename))
				# Assume EXIF GPS Alt 
				elif s.isdigit() and 1 < len(s) < 4 and self.type=='camera':
					try:
						self.elevation = float(s)
						warn('Assumed alt','%-8r\t[[%s]]' % (s, pagename))
					except ValueError:
						error('BadFloat','%-8r\t[[%s]]'%(s,pagename))
				else:
					error('Number  ','%-8r\t[[%s]]' % (s, pagename))
			# Assume type:TYPE_(num)_
			elif s[0]=='(' and s[-1]==')' and s[1:-1].translate(None, ',.').isdigit():
				self.type = (self.type or "xcity") + s
				# warn(... TODO 
			# Input not supplied or template page
			elif s.startswith('{{{'):
				pass
			# Error in parameter detection
			elif ':' in s:
				# Non determinable entity
				error('Bad prefix', '%-8r\t[[%s]]' % (s, pagename))
				pass
			else:
				# TODO: record in a separate field
				error('Unparsed','%-8r\t[[%s]]' % (s, pagename))
				pass

		# Parse the value in the type parameter
		if self.type:
			i = self.type.find('(')
			if i != -1:
				try:
					#warn on type:city(2306):mx-son
					if i + 2 != len(self.type): # Avoid marking city()
						self.typesize = int(self.type[i+1:].translate(None, ',._)'))
				except ValueError:
					error('BadTypeSize', '%-8r\t[[%s]]' %  (self.type, pagename))
				# Bounds check: Tokyo Metro Pop. 35 mil, Geostationary 50 Mm (unsupported)
				if self.typesize and not 0 <= self.typesize < 70e6:
					error('WrongTypeSize', '%-8r\t[[%s]]' %  (self.type, pagename))
					self.typesize = None
				# Remove typesize from type field
				self.type = self.type[:i]
			if self.type in type_corrections:
				warn('Corrected Type', '%-8r\t[[%s]]' %  (self.type, pagename))
				self.type = type_corrections[self.type]
			else:
				# TODO improve
				# Warn on weird characters, but still allow adm1st
				if self.type[-1:].isdigit() or not self.type.isalnum():
					debug('Nonconform type', '%-8r\t[[%s]]' %  (self.type, pagename))
					self.type = self.type.rstrip('0123456789')

		# 
		if self.globe:
			if self.globe in globes:
				# Speed hack
				pass
			elif self.globe.capitalize() not in globes:
				error('Globe invalid', '%-8r\t[[%s]]'%(self.globe, pagename))
				return		 # Skip insertion, assume it pseudo globe sandbox
			elif self.globe == '':
				warn('Globe blank', '%-8r\t[[%s]]'%(self.globe, pagename))
			elif not self.globe.islower() and self.globe != self.globe.capitalize():
				warn('GlobeCase', '%-8r\t[[%s]]'%(self.globe, pagename))
				self.globe = self.globe.lower()
			else:
				pass
		#
		if self.region:
			for region in self.region.split('/'):
				if region in iso3166_1_alpha_2:
					# XXX optimization - skip valid 2 letter coordinates
					pass	
				elif region[3:4]=='-' or len(region)==3 and region.isalpha():
					# skips alpha-3 code IRQ-BGD
					error('ISO alpha-3', '%-8r\t[[%s]]'%(self.region, pagename))
				elif region.split('-')[0].upper() not in iso3166_1_alpha_2:
					warn('Region invalid', '%-8r\t[[%s]]'%(self.region, pagename))
				elif len(region)==3 and region[2:3]=='-':
					debug('Empty subdiv', '%-8r\t[[%s]]'%(self.region, pagename))
				#TODO clean up
#				elif '-' in region and region.split('-')[0].upper() in subcodes and region.split('-')[1].upper() not in subcodes[region.split('-')[0].upper()]:
#					if region.upper() in iso_3166_2.subdivision:
#						debug('Deprecated subdivision', '%-8r\t[[%s]]'%(self.region, pagename))
#					else:
#						debug('Subdiv invalid', '%-8r\t[[%s]]'%(self.region, pagename))
#				elif '-' in region and region.split('-')[0].upper() not in subcodes:
#					if region.upper() in iso_3166_2.subdivision:
#						pass # We haven't put the code in, but it exists in an older list
#					else:
#						debug('Subdivision invalid or too new', '%-8r\t[[%s]]'%(region, pagename))
				elif not region.isupper():
					warn('RegionCase', '%-8r\t[[%s]]'%(self.region, pagename))
				else:
					pass
			# TODO support '/' notation
			self.region = region_corrections.get(self.region, self.region)
			# Warn if non-earth body are used
			if self.globe not in (None, '', 'Earth', 'earth', 'EARTH', 'Tera', 'tera'):
				# better name? NonEarthRegion? GlobeWithRegion? BadGlobe?
				warn('RegionAndGlobe', '%-8r\t[[%s]]'%(self.globe, pagename))
		if self.dim and self.scale:
			# dewiki requests to keep correct proper scale: and dim: silent
			if self.scale != self.dim * 10:
				warn('Dim override', 'dim:%s_scale:%s\t[[%s]]' % (
					# avoid .0 from %s formatting
					int(self.dim)   if self.dim.is_integer()   else self.dim,
					int(self.scale) if self.scale.is_integer() else self.scale,
					pagename,
				))
		return self

# Stuff for creating links
#TODO Add more 
	def makeLink(self):
		#TODO: make pagename and title optional
		basehref="http://toolserver.org/~geohack/geohack.php?"
		return basehref+('&'.join([
				self.pagename and 'params=%s'%self.pagename or '',
				'params=%s_%s'%(self.makecoord(),self.makeparams()),
				self.title and 'title=%s'%self.title or '',
				])
			)
	def makeTemplate(self, template='Coord', *arg):
		"""
			makeTemplate("display=title")
		"""
		# HACK should be done with .remove('|')
		return "{{%s}}" % '|'.join((template, self.makecoord(sep='|'), self.makeparams(), self.title and 'name='+self.title or '')+arg).replace('||', '|').replace('||', '|')
	def makecoord(self, sep='_'):
		#TODO: implement switch dms/decimal/short/auto
		s = '%s;%s' % (self.lat, self.lng)
		return s
		
	def makeparams(self):
		s = ''

		if self.type:
			s+='_type:%s'%self.type
			if self.typesize:
				s+='(%s)'%self.typesize
		if self.heading:	s+='_heading:%s'%self.heading
		if self.classification:	s+='_class:%s'%self.classification
		if self.scale:
			# should employ language switch for those which use dim:
			s+='_scale:%s'%self.scale
		if self.elevation:	s+='_elevation:%s'%self.elevation
		if self.region:	s+='_region:%s'%self.region
		if self.globe:	s+='_globe:%s'%self.globe
		if self.source:	s+='_source:%s'%self.source
		return s[1:]
def compare(gl1, gl2):
	"""
	Compares two geolinks returns True if they have approximately the same coordinates and scale
	"""
	if (gl1.globe or 'earth') != (gl2.globe or 'earth'):
		return False
def combine(geolink1, geolink2):
	"""
	Combines two geolinks and returns one with all attributes combined
	"""
	gl = geolink()

	gl.scale = geolink1.scale or geolink2.scale

# Not sure where to put this
def precision(n):
	# Rounding factor
	rf = 1e-5
	# D
	if (n+rf) % 1 < 2*rf:
		pass
	# DM
	elif (n+rf) % (1/60.) < 2*rf:
		pass
	# DMS
	elif (n+rf) % (1/3600.) < 2*rf:
		pass
	# DMS + 1/10*s
	elif (n+rf) % (1/36000.) < 2*rf:
		pass
	# Decimal
	else:
		pass

def main():
	dbname = ''
	refUrl = "http://toolserver.org/~geohack/geohack.php"
	
	import sys
	for arg in sys.argv[1:]:
		if arg.startswith('-help'):
			print __doc__
			return
		elif arg.startswith('-dbname:'):
			dbname = arg[8:]
			if not dbname.endswith('_p'):
				dbname += '_p'
		elif arg.startswith('-refUrl:'):
			refUrl = arg[8:]
		else:
			print "Argument not understood", arg

	if dbname:
		import MySQLdb
		conn = MySQLdb.connect(db=dbname, host=dbname.replace('_', '-')+'.rrdb.toolserver.org', read_default_file="~/.my.cnf")
		coord = Geolink()
	
		cursor = conn.cursor()
		cursor.execute('/* ghel SLOW_OK */SELECT el_to FROM externallinks WHERE el_to LIKE %s', (refUrl+"?_%",))
		#print b'\xEF\xBB\xBF', # UTF-8 byte order mark
		print '# level \ttype\tvalue\tpage'
		for el_to, in c.fetchall():
			coord.parse(el_to)

if __name__ == "__main__" :
	main()

