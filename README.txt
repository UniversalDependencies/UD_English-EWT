Universal Dependencies - English Dependency Treebank
Universal Dependencies English Web Treebank v1.0 -- 2015-01-19
https://github.com/UniversalDependencies/UD_English

A Gold Standard Universal Dependencies Corpus for English,
built over the source material of the English Web Treebank
LDC2012T13 (https://catalog.ldc.upenn.edu/LDC2012T13).


LICENSE/COPYRIGHT

Universal Dependencies English Web Treebank (c) 2013, 2014, 2015 by 
The Board of Trustees of The Leland Stanford Junior University.
All Rights Reserved.

The annotations and database rights of the Universal Dependencies 
English Web Treebank are licensed under a 
Creative Commons Attribution-ShareAlike 4.0 International License.

You should have received a copy of the license along with this
work. If not, see <http://creativecommons.org/licenses/by-sa/4.0/>. 

The underlying texts come from various sources collected for the 
LDC English Web Treebank. Some parts are in the public domain.
Portions may be © 2012 Google Inc., © 2011 Yahoo! Inc., 
© 2012 Trustees of the University of Pennsylvania and/or 
© other original authors.


STRUCTURE

This directory contains a corpus of sentences annotated using Universal Dependencies annotation.
The corpus comprises 254,830 words and 16,622 sentences, taken from various web media including
weblogs, newsgroups, emails, reviews, and Yahoo! answers; see the LDC2012T13 documentation for 
more details on the source of the sentences.  The trees were automatically converted into Stanford
Dependencies and then hand-corrected to Universal Dependencies.  All the dependency annotations
have been single-annotated, and a limited portion of them have been double-annotated with
interannotator agreement at approximately 96%.  

This file is compatible with the CoNLL-U format defined for Universal Dependencies. See:
http://universaldependencies.github.io/docs/format.html . However, at present the files do not
include lemmas or morphological features for words. These may be added in a later release.  

The dependency taxonomy can be found on the Universal Dependencies web site:

    http://universaldependencies.github.io/docs/
    http://universaldependencies.github.io/docs/#language-en


DEVIATIONS FROM UD

Version 1.1 of the English UD treebank conforms to the UD guidelines in
almost all respects, but there are a couple of remaining deviations:
 * The UD dependency 'name' is not used. Everything that would be a 'name is tagged 'compound'
 * Words that the Penn Treebank tag set would tag as 'DT', such as 'this' and 'that' are always
   given the UD tag 'DET' rather than distinguishing whether they are used promonimally or as
   a modifier


FIXES

To help improve the corpus, please alert us to any errors you find in it;
contact Christopher Manning at manning@stanford.edu.


CONTRIBUTORS

Annotation of the Universal Dependencies English Web Treebank was carried out by
(in order of size of contribution):

Natália Silveira
Timothy Dozat
Miriam Connor
Marie-Catherine de Marneffe
Samuel Bowman
Hanzhi Zhu
Daniel Galbraith
Christopher Manning
John Bauer

The construction of the Universal Dependencies English Web Treebank was partially funded
by a gift from Google, Inc., which we gratefully acknowledge.


CITATIONS

You are encouraged to cite this paper if you use the Universal Dependencies English Web Treebank:

@inproceedings{silveira14gold,
  year = {2014},
  author = {Natalia Silveira and Timothy Dozat and Marie-Catherine de Marneffe and Samuel Bowman
    and Miriam Connor and John Bauer and Christopher D. Manning},
  title = {A Gold Standard Dependency Corpus for {E}nglish},
  booktitle = {Proceedings of the Ninth International Conference on Language
    Resources and Evaluation (LREC-2014)}
}



Documentation status: complete
Data source: manual
Data available since: UD v1.0
License: CC BY-SA 4.0
