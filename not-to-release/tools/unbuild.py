#!/usr/bin/env python3
"""
Given a .conllu file with parses from multiple documents,
update individual document files under not-to-release/sources/
(e.g. reviews/001325.xml.conllu).

@author: Nathan Schneider (@nschneid)
@since: 2020-03-01

Requires python3.6+
"""
import sys, fileinput

SOURCES_PATH = 'not-to-release/sources'
outF = None

for split in ('train', 'dev', 'test'):
    with open(f'en_ewt-ud-{split}.conllu', encoding='utf-8') as inF:
        for ln in inF:
            if ln.startswith('# newdoc id = '):
                if outF:
                    outF.close()
                fulldocid = ln[len('# newdoc id = '):].strip()
                subcorp, docid = fulldocid.split('-')
                filename = f'{SOURCES_PATH}/{subcorp}/{docid}.xml.conllu'
                #print(filename, file=sys.stderr)
                outF = open(filename, 'w', encoding='utf-8', newline='\n')
            elif ln.startswith('# streusle_sent_id') or ln.startswith('# mwe ='):
                continue    # STREUSLE-specific metadata lines
            outF.write(ln)
        if outF: outF.close()
