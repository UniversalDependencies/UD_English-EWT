#!/usr/bin/env python3
"""
Regenerate en_ewt-ud-{train,dev,test}.conllu from source files in the
not-to-release/sources directory.

Requires python3.6+
"""
FLIST_BASE_PATH = 'not-to-release/file-lists/files'
for split in ('train', 'dev', 'test'):
    flist = FLIST_BASE_PATH + '.' + split
    with open(flist, encoding='utf-8') as inF:
        fpaths = inF.readlines()
    with open(f'en_ewt-ud-{split}.conllu', 'w', encoding='utf-8') as outF:
        for fpath in fpaths:
            fpath = fpath.strip()
            with open('not-to-release/sources/' + fpath, encoding='utf-8') as inF:
                data = inF.read()
            outF.write(data)
