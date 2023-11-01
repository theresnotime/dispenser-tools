#/bin/bash
# Download pages with pp_prop="disambiguation" and gzip
# Interactive ./make_dabs_gz.sh
# Cron: $HOME/scripts/make_dabs_gz.sh > /dev/null

tmpdir=`mktemp --directory /tmp/dispenser.XXX`
gzfile="$tmpdir/dabs_$(date +%Y%m%d).tar.gz"
store=$HOME/public_html/
cd $tmpdir

#if [ -n "$SGE_ACCOUNT" ]; then
if [ -z "$PS1" ]; then
    if [[ "$(date --date=tomorrow +\%d)" != "01" ]]; then
        # not the end of the month
        exit
    fi
fi

if [ -w $store ]; then
	: # no-op
else
	echo "Not writable: $store"
	exit
fi

# Create dab_urls.txt
python -c 'import os, oursql, urllib;
cursor=oursql.connect(db="enwiki_p",host="s1.labsdb",read_default_file=os.path.expanduser("~/.my.cnf")).cursor()
cursor.execute("""/* make_dabs_gz SLOW_OK */
SELECT page_title
FROM page
-- JOIN page_props ON pp_page=page_id AND pp_propname="disambiguation"
JOIN categorylinks ON cl_from=page_id AND cl_to="All_article_disambiguation_pages"
WHERE page_namespace=0
""")
with open("dab_urls.txt", "w") as f:
	for page_title, in cursor.fetchall():
		f.write("https://en.wikipedia.org/w/api.php?action=parse&format=json&redirects&page=%s%s"%(urllib.quote(page_title),chr(10),))
'

mkdir -p $tmpdir/mosdab; cd $tmpdir/mosdab
# 0.2 s/pg * 250,000 pg / 3600 h/s = 14 h
#wget -w 0.2  -i $tmpdir/dab_urls.txt --no-verbose --continue --user-agent="User:Dispenser/MOS:DAB_stats" --directory-prefix=$tmpdir/mosdab
wget  -w 0.2  -i $tmpdir/dab_urls.txt --no-verbose --continue --user-agent="User:Dispenser/MOS:DAB_stats" 2>&1 | grep -v " -> "
# Total wall clock time: 19h 52m 10s

# Rename from URL encoded to something shorter
python -c 'import os, urllib;
for filename in os.listdir("."):
	if "&page=" not in filename: continue
	os.rename(filename, urllib.unquote(filename[filename.index("&page=")+6:]).replace("/","|")+".json")
'

export GZIP=-9 # Use better compression
tar czf $gzfile .

if [ -s $gzfile ]; then
	mv $gzfile $store
	if [[ $? -ne 0 ]]; then exit; fi
	rm -rf $tmpdir
	echo $(date)
	echo "Ready.  Download at https://tools.wmflabs.org/dispenser/$(basename $gzfile)"
#    mail -s "$0 [$SECONDS sec]" "$USER" <<< "Ready.  Download at https://tools.wmflabs.org/dispenser/$(basename $gzfile)"
fi

