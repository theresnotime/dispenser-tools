import os
def datafilepath(*filename):
	path = os.path.normpath(os.path.join('../resources/', *filename))
	dirs = os.path.dirname(path)
	if not os.path.exists(dirs): os.makedirs(dirs)
	return path

## Settings need by some programs
# table2wiki.py
splitLongParagraphs = False
deIndentTables = True
table2wikiAskOnlyWarnings = True
table2wikiSkipWarnings = True
# fixes.py
base_dir = ''
