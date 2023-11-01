#!/bin/bash


WIKI=enwiki
LOGDIR="$HOME/public_html/logs"
#TMPDIR="/tmp/missing_entries"; mkdir -p "$TMPDIR"
TMPDIR=$(mktemp -dt "$(basename $0).XXX")
tbl_articles="$TMPDIR/tbl_articles.tab"
tbl_hatnotes="$TMPDIR/tbl_hatnotes.tab"
tbl_bios="$TMPDIR/tbl_bios.tab"
tbl_dabs="$TMPDIR/tbl_dabs.tab"
tbl_sias="$TMPDIR/tbl_sias.tab"
StartTime=$(sql --cluster=analytics ${WIKI}_p 'SELECT NOW() AS ""')

if [ "1" -eq "1" ] ; then

# Start dump table slices
if [ ! -s "$tbl_sias" ] ; then 

echo "$(date) Start article list"
sql --cluster=analytics ${WIKI}_p > "$tbl_articles" <<< '
SELECT
  page_id    AS aa_page,
  page_title AS aa_title,
  page_len   AS aa_len,
  pp_value IS NOT NULL AS aa_is_dab
FROM page
LEFT JOIN page_props    ON pp_page=page_id AND pp_propname="disambiguation"
WHERE page_namespace = 0
AND page_is_redirect = 0
/* Remove TV Seasons as they are effective the same item split (e.g. Casualty_(series_4), 1000_Ways_to_Die_(season_3,_2010)  */
AND page_title NOT REGEXP "_[(](?:[^0-9(),]+,?_|)(?:seasons?|series)_[0-9]+(?:,_[0-9]{4}|)[)]$"
/* Lists split for performance reasons */
AND page_title NOT LIKE "List\_of\_%"
/* Remove "annualized" events */
AND page_id NOT IN (
  SELECT STRAIGHT_JOIN cl_from
  FROM category
  JOIN categorylinks ON cl_to=cat_title AND cl_type="page"
  WHERE cat_title LIKE "%_in_professional_wrestling"
     OR cat_title LIKE "Professional_wrestling_in_%"
	 OR cat_title LIKE "%_television_seasons"
	 OR cat_title LIKE "%_(TV_series)_seasons"
	 OR cat_title LIKE "%_episode_lists"
);
SHOW WARNINGS;
'; if [ $? -ne 0 ] ; then exit $?; fi

echo "$(date) Start Hatnote list"
sql --cluster=analytics ${WIKI}_p > "$tbl_hatnotes" <<< '
SELECT DISTINCT tl_from FROM templatelinks where tl_namespace=828 AND tl_title="Hatnote" ORDER BY tl_from;
SHOW WARNINGS;
'; if [ $? -ne 0 ] ; then exit $?; fi

echo "$(date) Start biography list"
sql --cluster=analytics ${WIKI}_p > "$tbl_bios" <<< '
SELECT DISTINCT page_id
FROM page
JOIN categorylinks ON cl_from=page_id
JOIN category ON cat_title=cl_to
WHERE cat_title IN (
 "Living_people",
 "Missing_people",        
 "Possibly_living_people",
 "Year_of_death_missing", 
 "Year_of_birth_missing", 
 "Year_of_death_unknown", 
 "Year_of_birth_unknown", 
 "Year_of_birth_uncertain",
 "Year_of_death_uncertain"
)
OR cat_title REGEXP "^[0-9]{4}_(births|deaths)$"
ORDER BY page_id;
SHOW WARNINGS;
'; if [ $? -ne 0 ] ; then exit $?; fi

echo "$(date) Start Dab list"
sql --cluster=analytics ${WIKI}_p > "$tbl_dabs" <<< '
SELECT DISTINCT 
  dabs.page_id AS dab_page,
  COALESCE(rd.page_id, pl.page_id) AS target_page
FROM page_props 
JOIN page AS dabs    ON dabs.page_id=pp_page AND page_namespace=0
JOIN pagelinks       ON pl_from=dabs.page_id AND pl_namespace=0
JOIN page AS pl      ON pl.page_namespace=0  AND pl.page_title=pl_title
LEFT JOIN redirect   ON rd_from=pl.page_id   AND rd_namespace=0 
LEFT JOIN page AS rd ON rd.page_namespace=0  AND rd.page_title=rd_title
WHERE pp_propname="disambiguation"
ORDER BY target_page, dab_page;
SHOW WARNINGS;
'; if [ $? -ne 0 ] ; then exit $?; fi

echo "$(date) Start SIA list"
sql --cluster=analytics ${WIKI}_p > "$tbl_sias" <<< '
SELECT DISTINCT
  SIAs.page_id AS sia_id,
  COALESCE(rd.page_id, pl.page_id) AS target_page
FROM categorylinks 
JOIN page AS SIAs    ON SIAs.page_id=cl_from AND SIAs.page_namespace=0
JOIN pagelinks       ON pl_from=SIAs.page_id AND pl_namespace=0
JOIN page AS pl      ON pl.page_namespace=0  AND pl.page_title=pl_title
LEFT JOIN redirect   ON rd_from=pl.page_id   AND rd_namespace=0
LEFT JOIN page AS rd ON rd.page_namespace=0  AND rd.page_title=rd_title
WHERE cl_to IN ("All_set_index_articles")
ORDER BY target_page, sia_id;
SHOW WARNINGS;
'; if [ $? -ne 0 ] ; then exit $?; fi




# End dump table slices
fi



echo "$(date) Load and prepare main table"
trickle -s -u 500 mysql --local-infile --compress -h tools.labsdb u2815__p <<< '
SET default_storage_engine = INNODB;

CREATE TEMPORARY TABLE dabs2page (
  dab_page    INT unsigned NOT NULL,
  target_page INT unsigned NOT NULL,
  PRIMARY KEY(target_page, dab_page)
);
LOAD DATA LOCAL INFILE "'"$tbl_dabs"'" INTO TABLE dabs2page IGNORE 1 LINES; 
SHOW WARNINGS;

CREATE TEMPORARY TABLE sia2page (
  sia_id      INT unsigned NOT NULL,
  target_page INT unsigned NOT NULL,
  PRIMARY KEY(target_page, sia_id)
);
LOAD DATA LOCAL INFILE "'"$tbl_sias"'" INTO TABLE sia2page IGNORE 1 LINES; 
SHOW WARNINGS;

CREATE TEMPORARY TABLE biographies (
  bio_from INT unsigned NOT NULL PRIMARY KEY
);
LOAD DATA LOCAL INFILE "'"$tbl_bios"'" INTO TABLE biographies IGNORE 1 LINES; 
SHOW WARNINGS;
CREATE TEMPORARY TABLE hatnotes (
  tl_from INT unsigned NOT NULL PRIMARY KEY
);
LOAD DATA LOCAL INFILE "'"$tbl_hatnotes"'" INTO TABLE hatnotes IGNORE 1 LINES; 
SHOW WARNINGS;


DROP TABLE IF EXISTS all_articles;
CREATE TABLE all_articles (
  aa_page          INT unsigned NOT NULL PRIMARY KEY,
  aa_title         VARCHAR(255) CHARACTER SET utf8mb4 COLLATE "utf8mb4_bin"        NOT NULL,
  title_normalized VARCHAR(256) CHARACTER SET utf8mb4 COLLATE "utf8mb4_unicode_ci" NOT NULL,
  aa_len           INT unsigned NOT NULL,
  aa_is_dab        BOOL         NOT NULL,
  aa_is_bio        BOOL         NOT NULL,
  aa_has_hatnote   BOOL         NOT NULL,
  linkedFromDab    BOOL         NOT NULL,
  linkedFromSI     BOOL         NOT NULL
); 
LOAD DATA LOCAL INFILE "'"$tbl_articles"'"
INTO TABLE all_articles
IGNORE 1 LINES
(aa_page, aa_title, aa_len, aa_is_dab)
SET title_normalized=UPPER(TRIM("_" FROM REGEXP_REPLACE(REGEXP_REPLACE(
  CAST(aa_title AS CHAR CHARACTER SET utf8mb4) COLLATE "utf8mb4_unicode_ci",
  /* A (B) and A, B and A: B becomes A             */
  "^([^(]+)[(][^)]*([)]($|,[^(),]*$|.{0,5}[(][^)]*))+$|^([^,])[,].*|^([^:])[:].*", "\\1\\4\\5"),
  /* Normalize without articles (including middle) */
  "^(THE|A|AN)_(?=[^(])|_(THE|A|AN)(?=_[^(])", "")
)),
aa_has_hatnote = EXISTS (
  SELECT 1
  FROM hatnotes
  WHERE tl_from=aa_page
), linkedFromDab = EXISTS (
  /* Flag pages linked from DaB + SI */
  -- TODO research if dab_page/sia_page is narrow
  SELECT 1
  FROM dabs2page
  WHERE target_page=aa_page
), linkedFromSI = EXISTS (
  SELECT 1
  FROM sia2page
  WHERE target_page=aa_page
), aa_is_bio = EXISTS (
  SELECT 1
  FROM biographies
  WHERE bio_from=aa_page
);
SHOW WARNINGS;

UPDATE all_articles
SET title_normalized=REGEXP_REPLACE(REGEXP_REPLACE(title_normalized, 
-- Remove Honorifics and Ordinals
"^(SIR|DAME|LORD|LADY|MUHAMMAD)_|(_JR.?|_SR.?|,_.*|_(X?L|I?X{1,3}|I?V|I{1,3})+)$", ""),
-- Remove middle name
"^([^_.]{4,50}|[A-Z][.]?)_([^_.]{4,50}|[A-Z][.]?)_([^_.]+)$", "\\1_\\3")
WHERE aa_is_bio=1 AND title_normalized LIKE "%\_%\_%";


/*

SELECT aa_title, title_normalized, 
REGEXP_REPLACE(REGEXP_REPLACE(title_normalized, 
-- Remove Honorifics and Ordinals
"^(SIR|DAME|LORD|LADY)_|(,_.*|_JR.?|_SR.?|_(X?L|I?X{1,3}|I?V|I{1,3})+)$", ""),
-- Remove middle name
"^([^_.]{4,50}|[A-Z][.]?)_([^_.]{4,50}|[A-Z][.]?)_([^_.]+)$", CONCAT(0x1B,"[32;40m", "\\1_\\3", 0x1B,"[m")
) AS new FROM all_articles WHERE aa_is_bio=1 AND title_normalized LIKE "%\_%\_%" limit 100 offset 500;

/*-*/

'; if [ $? -ne 0 ] ; then exit $?; fi

echo "$(date) Removing duplicates"
mysql -h tools.labsdb u2815__p <<< '

/* Optimization: Remove entries without collisions (8 min)
 * Use second table to workaround MySQL bug #10327
 */
CREATE TEMPORARY TABLE no_dups (
  aa_page INT unsigned NOT NULL PRIMARY KEY
)
SELECT aa_page
FROM all_articles
GROUP BY title_normalized
HAVING COUNT(*) = 1
ORDER BY aa_page;
SHOW WARNINGS;

DELETE QUICK all_articles
FROM all_articles
JOIN no_dups ON no_dups.aa_page=all_articles.aa_page;
SHOW WARNINGS;
'; if [ $? -ne 0 ] ; then exit $?; fi

echo "$(date) Optimize table"
mysql -h tools.labsdb u2815__p <<< '
-- OPTIMIZE TABLE all_articles;
-- Is mapped for InnoDB tables to ALTER TABLE ... FORCE
ALTER TABLE all_articles ORDER BY aa_page;
'; if [ $? -ne 0 ] ; then exit $?; fi

fi
echo "$(date) Execute main query"
mysql -h tools.labsdb u2815__p <<< '
SET SESSION group_concat_max_len = 65535;

-- SELECT * FROM (
/* Pretty display results (2 minutes) */
-- _utf8mb4 does not work with emojis
SELECT IFNULL(Disambig, "") AS Disambig, CONCAT(MissingCnt, IF(BioCnt, _utf8" 👤", "")) AS "# Missing", Missing AS "Missing links" FROM (

SELECT
  -- COUNT(*) AS Cnt,
  SUM(aa_is_dab) AS DabCnt,
  SUM(aa_is_dab=0 AND linkedFromDab=0 AND linkedFromSI=0) AS MissingCnt,
  SUM(aa_is_bio=1 AND linkedFromDab=0 AND linkedFromSI=0) AS BioCnt,
  SUM(aa_has_hatnote=1) AS HatCnt,
  TRIM(   GROUP_CONCAT(IF(aa_is_dab=1,         CONCAT("[[", REPLACE(aa_title,"_"," "), "]]"), NULL) ORDER BY 1 SEPARATOR ", ")) AS Disambig,
  TRIM(   GROUP_CONCAT(IF(aa_is_dab=0 AND      linkedFromDab=0 AND linkedFromSI=0,  aa_title, NULL) ORDER BY 1 SEPARATOR "  ")) AS Missing,
  -- TRIM(GROUP_CONCAT(IF(aa_is_dab=0 AND NOT (linkedFromDab=0 AND linkedFromSI=0), aa_title, NULL) ORDER BY 1 SEPARATOR "  ")) AS Included,
  -- XXX Remove diacritics suggestions since Dabfix does not find them
  COUNT(DISTINCT MD5(title_normalized)) AS kinds
FROM all_articles AS aa
GROUP BY title_normalized
HAVING MissingCnt BETWEEN 1 AND 10
   AND DabCnt = 1
   AND kinds  = 1
/* Other fun HAVING clauses:*/
 -- Find disambiguation pages to create
 OR DabCnt = 0 
 AND (
      HatCnt = 0 AND MissingCnt BETWEEN 4 AND 10
--   OR HatCnt > 0 AND MissingCnt BETWEEN 5 AND 10
 )
 AND BioCnt >= COUNT(*) * 2 / 3
 AND SUM(UPPER(aa_title) = title_normalized) >= 1
-- AND title_normalized NOT REGEXP "^1|^2"
-- ORDER BY NULL LIMIT 50;
/*-*/
) AS primary_query
/* Sort by last letter, such (1994 film) is with (film), (Wadena,_Iowa), etc. */
ORDER BY Disambig IS NULL, REVERSE(UPPER(REGEXP_REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(
 CAST(Missing AS CHAR CHARACTER SET utf8mb4), "_(", -1), ")", 1),
 "(^|[,.]?_)[c._]*[0-9–-]*$", "")));
SHOW WARNINGS;

SELECT CONCAT("Generated by '"$(basename $0)"' in ", TIMESTAMPDIFF(MINUTE, "'"$StartTime"'", NOW()), DATE_FORMAT(NOW(), " minutes on %d %b %Y at %H:%i"), "; ", @@hostname) AS "";
-- ' > $LOGDIR/missing_entries-${WIKI}.tmp

#if [ $? -eq 0 ] ; then echo "mv -f $LOGDIR/missing_entries-${WIKI}.tmp $LOGDIR/missing_entries-${WIKI}.log" ; fi
 if [ $? -eq 0 ] ; then mv -f "$LOGDIR/missing_entries-${WIKI}.tmp" "$LOGDIR/missing_entries-${WIKI}.log" ; fi


# Delete if using tmp files
if [[ "$TMPDIR" = *"$(basename $0)"* ]]; then
#	echo "rm -rf $TMPDIR"
	rm -rf "$TMPDIR"
fi

echo "$(date) Ran $0 for $(($SECONDS/60)) minutes"
