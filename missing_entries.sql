-- 2> /dev/null; sql --cluster=labsdb enwiki_p > $HOME/public_html/logs/missing_entries-enwiki.tmp <<< '
/* Missing Entries
 * http://dispenser.info.tm/~dispenser/logs/missing_entries-enwiki.log
 * [[Foo (song)]] is missing from [[Foo (disambiguation)]]
 * 
 * Caveats: 
 * [[Čelovce]] [[Celovce]]
 *
 *
 * Author:   Dispenser
 * License:  ?
 * Run time: 30-50 minutes <SLOW_OK>
 * Created:  September 25, 2017
 * Updated:  December 1, 2017
 */
/* FIXME:
* [[–30–]] - This probably should be a disambiguation page
* [[¿Quién?]], [[¿Quién? (telenovela)]] - No existing disambiguation page (no cross linking rules written yet)
* [[The 12" Collection]] [[12" Collection]]
* [[Danaë (disambiguation)]],  [[Danae (Artemisia Gentileschi)]]
* Warn for DAB collisions: [[Borisov government]] (Created Jan 2014), [[Borisov Government]] (Created Nov 2014)
*/
SET SESSION group_concat_max_len = 65535;
SET default_storage_engine = INNODB;
SET @StartTime=(SELECT NOW());


/* List of all articles with title normalized - 12 min */
/* XXX
  British_Columbia_(Superintendent_of_Motor_Vehicles)_v_British_Columbia_(Council_of_Human_Rights) 
  Srinagar_(Lok_Sabha_constituency)_by-election,_2017
Philadelphia_Athletics_(1871–76)_all-time_roster
Philadelphia_Athletics_(American_Association)_all-time_roster
Dunfermline_(Milesmark)_Greyhound_Stadium
Roberval_(Air_Saguenay)_Water_Aerodrome

  Mission:_Impossible_(season_4)
  Holland_(hamlet),_New_York
*/
CREATE TEMPORARY TABLE s52690__p.all_articles
SELECT
  page_id     AS aa_page,
  page_title  AS aa_title,
  page_latest AS aa_rev_id,
  UPPER(TRIM("_" FROM REGEXP_REPLACE(REGEXP_REPLACE(
    CAST(page_title AS CHAR CHARACTER SET utf8mb4) COLLATE "utf8mb4_unicode_ci",
    "^([^(]+)[(][^)]*([)]($|,[^(),]*$|.{0,5}[(][^)]*))+$|^([^,])[,].*|^([^:])[:].*", "\\1\\4\\5"),
    "(^|_)(THE|A|AN)(_|$)", "")
  )) AS title_normalized,
  pp_value IS NOT NULL AS isDab,
  -1 AS linkedFromDab,
  -1 AS linkedFromSI
FROM page
LEFT JOIN page_props ON pp_page=page_id AND pp_propname="disambiguation"
WHERE page_namespace = 0
AND page_is_redirect = 0
/* Remove TV Seasons as they are effective the same item split */
AND page_title NOT REGEXP "_[(]seasons?_[0-9]+[)]$"
;

/* XXX Very hacky, Remove annualized Professional Wrestling events */
DELETE s52690__p.all_articles
FROM s52690__p.all_articles
WHERE aa_page IN (
  SELECT STRAIGHT_JOIN cl_from
  FROM category
  JOIN categorylinks ON cl_to=cat_title AND cl_type="page"
  WHERE cat_title LIKE "%_in_professional_wrestling"
);




/* Remove everything without collisions - 8 min */
CREATE TEMPORARY TABLE s52690__p.no_dups LIKE s52690__p.all_articles;
ALTER TABLE s52690__p.no_dups DISABLE KEYS, ADD UNIQUE ids (aa_page);

INSERT INTO s52690__p.no_dups
SELECT *
FROM s52690__p.all_articles
GROUP BY title_normalized
HAVING COUNT(*) = 1;

DELETE s52690__p.all_articles
FROM s52690__p.all_articles
JOIN s52690__p.no_dups ON no_dups.aa_page=all_articles.aa_page;

DROP TABLE s52690__p.no_dups;


/* Forward propagate links (w/redirects) from DaB + SI pages - 10 min */
CREATE TEMPORARY TABLE s52690__p.dabs
SELECT page_id AS dab_id, page_title AS dab_title
FROM page
JOIN page_props ON pp_page=page_id AND pp_propname="disambiguation"
WHERE page_namespace=0
ORDER BY page_id;
ALTER TABLE s52690__p.dabs ADD PRIMARY KEY(dab_id);

CREATE TEMPORARY TABLE s52690__p.dabs2page
SELECT DISTINCT dab_id, IFNULL(rd.page_id, pl.page_id) AS target_id
FROM s52690__p.dabs
JOIN pagelinks       ON pl_from=dab_id AND pl_namespace=0
JOIN page AS pl      ON pl.page_namespace=0 AND pl.page_title=pl_title
LEFT JOIN redirect   ON rd_from=pl.page_id  AND rd_namespace=0 
LEFT JOIN page AS rd ON rd.page_namespace=0 AND rd.page_title=rd_title
ORDER BY target_id, dab_id;
ALTER TABLE s52690__p.dabs2page ADD PRIMARY KEY(target_id,dab_id);

CREATE TEMPORARY TABLE s52690__p.si
SELECT page_id AS si_id, page_title AS si_title
FROM page
JOIN categorylinks ON cl_from=page_id AND cl_to="All_set_index_articles"
WHERE page_namespace=0
ORDER BY page_id;
ALTER TABLE s52690__p.si ADD PRIMARY KEY(si_id);



CREATE TEMPORARY TABLE s52690__p.si2page
SELECT DISTINCT si_id, IFNULL(rd.page_id, pl.page_id) AS target_id
FROM s52690__p.si
JOIN pagelinks       ON pl_from=si_id       AND pl_namespace=0
JOIN page AS pl      ON pl.page_namespace=0 AND pl.page_title=pl_title
LEFT JOIN redirect   ON rd_from=pl.page_id  AND rd_namespace=0
LEFT JOIN page AS rd ON rd.page_namespace=0 AND rd.page_title=rd_title
ORDER BY target_id, si_id;
ALTER TABLE s52690__p.si2page ADD PRIMARY KEY(target_id,si_id);

/* Flag pages linked from DaB + SI */
UPDATE s52690__p.all_articles
SET linkedFromDab = EXISTS (
  SELECT 1
  FROM s52690__p.dabs2page
  WHERE target_id=aa_page
), linkedFromSI = EXISTS (
  SELECT 1
  FROM s52690__p.si2page
  WHERE target_id=aa_page
);

DROP TABLE s52690__p.dabs, s52690__p.dabs2page, s52690__p.si, s52690__p.si2page;


/* Print results
 * 
 * 
 */
SELECT Disambig, NumDabLink AS "# Missing", Missing AS "Missing links" FROM (

SELECT
  title_normalized,
  -- COUNT(*) AS CNT,
  -- LEFT(GROUP_CONCAT(aa_title SEPARATOR "|"), 70) AS titles_cut,
  SUM(isDab) AS DabPages,
  -- TRIM(GROUP_CONCAT(IF(isDab=1, CONCAT("[[", REPLACE(aa_title, "_", " "), "]]"), "") SEPARATOR " ")) AS Disambig,
  TRIM(GROUP_CONCAT(IF(isDab=1, CONCAT("[[", aa_title, "]]"), "") SEPARATOR " ")) AS Disambig,
  SUM(isDab=0 AND linkedFromDab=0 AND linkedFromSI=0) AS NumDabLink,
  TRIM(GROUP_CONCAT(IF(isDab=0 AND linkedFromDab=0 AND linkedFromSI=0, aa_title, "") SEPARATOR " ")) AS Missing,
  -- LEFT(TRIM(GROUP_CONCAT(IF(isDab=0 AND linkedFromDab>0, aa_title, "") SEPARATOR " ")), 60) AS Ok,
  -- SUM(page.page_latest != aa_rev_id) AS isOutDated, /* */
  /* XXX HACK - Dabfix cannot find diacritics alternates, remove from suggestions */
  COUNT(DISTINCT MD5(title_normalized)) AS kinds
FROM s52690__p.all_articles AS aa
/* LEFT JOIN page ON page.page_id=aa_page */
GROUP BY title_normalized
HAVING DabPages = 1 AND NumDabLink BETWEEN 1 AND 10 AND kinds=1 /*NOT isOutDated AND*/ AND COUNT(*) >= 2

) AS r
-- ORDER BY max(length(aa_title)) DESC limit 10

/* Sort by last letter, So (1994 film) is with (film), (Wadena,_Iowa), etc.*/
ORDER BY REVERSE(UPPER(REGEXP_REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(
 CAST(Missing AS CHAR CHARACTER SET utf8mb4), "_(", -1), ")", 1),
 "(^|[,.]?_)[c._]*[0-9–-]*$", "")));

SHOW WARNINGS;

SELECT CONCAT(DATE_FORMAT(NOW(), "Generated on %d %b %Y in "), TIMESTAMPDIFF(MINUTE, @StartTime, NOW()), " minutes") AS "";
-- '; if [ $? -eq 0 ] ; then mv -f $HOME/public_html/logs/missing_entries-enwiki.tmp $HOME/public_html/logs/missing_entries-enwiki.log ; fi

