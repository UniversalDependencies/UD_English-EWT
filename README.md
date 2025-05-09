Universal Dependencies - English Dependency Treebank
Universal Dependencies English Web Treebank v2.15 -- 2024-11-15
https://github.com/UniversalDependencies/UD_English-EWT


# Summary

A Gold Standard Universal Dependencies Corpus for English,
built over the source material of the English Web Treebank
LDC2012T13 (https://catalog.ldc.upenn.edu/LDC2012T13).


# Introduction

The corpus comprises 254,820 words and 16,622 sentences, taken from five genres
of web media: weblogs, newsgroups, emails, reviews, and Yahoo! answers. See the
LDC2012T13 documentation for more details on the sources of the sentences. The
trees were automatically converted into Stanford Dependencies and then
hand-corrected to Universal Dependencies. All the basic dependency annotations have
been single-annotated, a limited portion of them have been double-annotated,
and subsequent correction has been done to improve consistency. Other aspects
of the treebank, such as Universal POS, features and enhanced dependencies, has
mainly been done automatically, with very limited hand-correction.


# License/Copyright

Universal Dependencies English Web Treebank annotations © 2013-2021
by The Board of Trustees of The Leland Stanford Junior University.
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


# Structure

This directory contains a corpus of sentences annotated using Universal
Dependencies annotation. The corpus comprises 254,818 words and 16,622
sentences (see [stats](stats.xml)), taken from various web media including
weblogs, newsgroups, emails, reviews, and Yahoo! answers;
see the LDC2012T13 documentation for more details on the source of the sentences.
The trees were automatically converted into Stanford Dependencies and then
hand-corrected to Universal Dependencies. All the dependency annotations have been
single-annotated, and a limited portion of them have been double-annotated with
interannotator agreement at approximately 96%. The sentence IDs include the genre
and the original LDC2012T13 filename.

This corpus is compatible with the CoNLL-U format defined for Universal
Dependencies. See:

   https://universaldependencies.org/format.html

The dependency taxonomy can be found on the Universal Dependencies web site:

   http://www.universaldependencies.org

For the conversion to v2, we performed an automatic conversion with extensive
spot-checking, and manual adjudication of ambiguous cases.

Most enhanced dependencies were automatically obtained by running an adapted version
of the converter by Schuster and Manning (2016). These dependencies have **not** been
manually checked. Enhanced dependencies for *reduced* relative clauses were added in
v2.14.

# Known Issues

The issue tracker at <https://github.com/UniversalDependencies/UD_English-EWT/issues>
documents many yet-to-be-resolved analysis challenges. Significant among these:

 - Many free relatives are incorrectly analyzed as interrogative.

# Changelog

**2025-05-15 v2.16**

Highlights:

  - **Implement new [`nmod:desc`](https://universaldependencies.org/en/dep/nmod-desc.html) subtype for prefixes/suffixes/embellishments in names ([#561](https://github.com/UniversalDependencies/UD_English-EWT/issues/561), [#559](https://github.com/UniversalDependencies/UD_English-EWT/issues/559), [#59](https://github.com/UniversalDependencies/UD_English-EWT/issues/59))**
  - **Implement new [guidelines for dates](https://universaldependencies.org/en/dep/nmod-unmarked.html#dates)** ([#575](https://github.com/UniversalDependencies/UD_English-EWT/issues/575))
  - **Implement new [guidelines for numbered entities](https://universaldependencies.org/en/dep/nmod-desc.html#numbered-entities) like "Chapter 1"** ([#558](https://github.com/UniversalDependencies/UD_English-EWT/issues/558))
  - New policy for "you guys" and similar ([#436](https://github.com/UniversalDependencies/UD_English-EWT/issues/436))
  - Reanalyze some constructions to comply with newly enforced requirements on `det` dependents ("at least", [#553](https://github.com/UniversalDependencies/UD_English-EWT/issues/553); predeterminer "such", [docs#1114](https://github.com/UniversalDependencies/docs/issues/1114))
  - Consistent treatment for "else" ([#556](https://github.com/UniversalDependencies/UD_English-EWT/issues/556)), "rather than" ([#562](https://github.com/UniversalDependencies/UD_English-EWT/issues/562))
  - Clean up postnominal `advmod`s ([#557](https://github.com/UniversalDependencies/UD_English-EWT/issues/557))
  - Clean up tokenization of "#" and "@" in web text ([#577](https://github.com/UniversalDependencies/UD_English-EWT/issues/577))
  - Clean up various phone numbers, addresses, and filenames
  - Clean up lemmas where the word is in all-caps for stylistic reasons ([#560](https://github.com/UniversalDependencies/UD_English-EWT/issues/560))

**2024-11-15 v2.15**

Highlights:

  - **Merge subtypes `nmod:{npmod,tmod}` as `nmod:unmarked` and `obl:{npmod,tmod}` as `obl:unmarked`** ([docs#1028](https://github.com/UniversalDependencies/docs/issues/1028))
     * `:unmarked` indicates a modifier that is structured as an NP without case marking
     * Retain temporal semantics with new custom MISC feature `TemporalNPAdjunct=Yes`
  - Many foreign names that were `compound` corrected to `flat` ([#81](https://github.com/UniversalDependencies/UD_English-EWT/issues/81))
  - Fix a number of cases of spurious nonprojectivity ([#545](https://github.com/UniversalDependencies/UD_English-EWT/issues/545), [#548](https://github.com/UniversalDependencies/UD_English-EWT/issues/548))
  - **Construction annotations in the [UCxn](https://github.com/LeonieWeissweiler/UCxn) framework** added to MISC ([#551](https://github.com/UniversalDependencies/UD_English-EWT/pull/551))
     * This release adds rule-based annotations of Interrogatives, Conditionals, Existentials, and NPN (noun-preposition-noun) constructions on the head of the respective phrase, plus construction elements.
     * The UCxn v1 notation and categories are documented [here](https://github.com/LeonieWeissweiler/UCxn/blob/main/docs/UCxn-v1.pdf).
     * Special thanks: [@LeonieWeissweiler](https://github.com/LeonieWeissweiler), [@WesScivetti](https://github.com/WesScivetti/), [@s-herrera](https://github.com/s-herrera)
  - Features
     * **Implement `ExtPos` for all fixed expressions** ([docs#1037](https://github.com/UniversalDependencies/docs/issues/1037))
     * **Implement `Polarity=Neg` for not/PART, neither/CCONJ, nor/CCONJ, no/INTJ and `Polarity=Pos` for yes/INTJ** ([#526](https://github.com/UniversalDependencies/UD_English-EWT/issues/526), [docs#1056](https://github.com/UniversalDependencies/docs/issues/1056))
     * **Implement `PronType` for none/PRON and ADVs "now", "never", "somewhere", "whenever", and similar**
     * `NumForm` and `NumType` for decades expressed as pluralized years ([#527](https://github.com/UniversalDependencies/UD_English-EWT/issues/527))
     * Correct overuses of `VerbForm=Inf` ([#284](https://github.com/UniversalDependencies/UD_English-EWT/issues/284))
     * Improve feature consistency for `ADJ`s
     * Add custom MISC features `FlatType=Filename` and `FlatType=Phone` (and assign these `ExtPos=PROPN`)

**2024-05-15 v2.14**

Highlights:

  - **Relative clauses**
     * ~700 enhanced edges added for reduced relative clauses ([#392](https://github.com/UniversalDependencies/UD_English-EWT/issues/392)) (thanks [@xiulinyang](https://github.com/xiulinyang)!)
     * relative clause types added in `Cxn` attribute of MISC ([#474](https://github.com/UniversalDependencies/UD_English-EWT/issues/474))
        - e.g. `Cxn=rc-wh-nsubj:pass` (passive subject WH), `Cxn=rc-red-obj` (reduced object), `Cxn=rc-red-obl-pstrand` (reduced oblique with preposition stranding),
          `Cxn=rc-free-obj_xcomp` (free relative, object nested under xcomp)
        - produced by [not-to-release/tools/rc-types.sh](not-to-release/tools/rc-types.sh) - see the code for documentation
        - cf. the [UCxn project](https://github.com/LeonieWeissweiler/UCxn/) (a larger effort which proposed construction annotation in UD,
          though this use of it for relative clauses is EWT-specific at present)
  - Attach list item enumerators (`LS`) as `discourse` ([#518](https://github.com/UniversalDependencies/UD_English-EWT/issues/518))
  - Verb tags/features
     * clean up errors
     * `VBG`: new rules to distinguish `VerbForm=Ger` vs. `Tense=Pres|VerbForm=Part` ([#305](https://github.com/UniversalDependencies/UD_English-EWT/issues/305))
     * implement subjunctive "were" ([#511](https://github.com/UniversalDependencies/UD_English-EWT/issues/511))
  - Noun features: implement `Number=Ptan` for pluralia tantum ([docs#999](https://github.com/UniversalDependencies/docs/issues/999))
  - Improved treatment of internet addresses ([#440](https://github.com/UniversalDependencies/UD_English-EWT/issues/440), [#487](https://github.com/UniversalDependencies/UD_English-EWT/issues/487))
  - Multiword expressions
     * `goeswith` for spaced email addresses
     * `flat` for spaced telephone numbers

**2023-11-15 v2.13**

Highlights:

  - Structural
     - **Adopt subtype `obl:agent` for passive *by*-phrases**, and apply the feature `Voice=Pass` more widely [to distinguish passive uses from active perfect uses of the past participle form](https://universaldependencies.org/en/feat/Voice.html) ([#290](https://github.com/UniversalDependencies/UD_English-EWT/issues/290))
     - **Remove use of `flat:foreign`** in line with most other English treebanks ([#459](https://github.com/UniversalDependencies/UD_English-EWT/issues/459))
     - Implement new guidelines on sufficiency/excess constructions ([#423](https://github.com/UniversalDependencies/UD_English-EWT/issues/423))
     - Use Udapi to standardize `punct` attachments (thanks to [@martin-popel](https://github.com/martinpopel))
  - Features
     - Flesh out features on [DETs](https://universaldependencies.org/en/pos/DET.html) ([#416](https://github.com/UniversalDependencies/UD_English-EWT/issues/416))
     - Make features on numbers more uniform and consistent with other treebanks (flagged by [@rhdunn](https://github.com/rhdunn): [#451](https://github.com/UniversalDependencies/UD_English-EWT/issues/451), [#458](https://github.com/UniversalDependencies/UD_English-EWT/issues/458), [#464](https://github.com/UniversalDependencies/UD_English-EWT/issues/464), [#465](https://github.com/UniversalDependencies/UD_English-EWT/issues/465))
     - Ensure verb features are complete and consistent with tags
  - Use AUX (not VERB) for "have" and "do" when stranded due to ellipsis ([#403](https://github.com/UniversalDependencies/UD_English-EWT/issues/403))
  - Mark verbal contractions missing apostrophes as typos (flagged by [@rhdunn](https://github.com/rhdunn): [#443](https://github.com/UniversalDependencies/UD_English-EWT/issues/443))
  - Extensive cleanup of/based on UPOS

**2023-05-15 v2.12**

Highlights:

  - Implement new policy on [sole `iobj`](https://universaldependencies.org/changes.html#sole-iobj) ([#55](https://github.com/UniversalDependencies/UD_English-EWT/issues/55))
  - Cleanup of free relatives (part of [#278](https://github.com/UniversalDependencies/UD_English-EWT/issues/278))
  - Make use of `xcomp` more consistent
  - For "etc.", change `Number=Sing` to `Number=Plur`

**2022-11-15 v2.11**

Highlights:

  - Implement `:outer` per [multiple subjects](https://universaldependencies.org/changes.html#multiple-subjects) policy ([#310](https://github.com/UniversalDependencies/UD_English-EWT/issues/310))
  - Implement `advcl:relcl` ([#346](https://github.com/UniversalDependencies/UD_English-EWT/issues/346))
  - Implement revised guidelines for English pronouns (lemmas, features) ([issue](https://github.com/UniversalDependencies/docs/issues/517))
  - Revise WH-adverbs to attach in a subordinate clause as `advmod` not `mark` ([#88](https://github.com/UniversalDependencies/UD_English-EWT/issues/88))
  - Improved lemmas/features for numeric values/entities
  - Tag "etc." as `NOUN` ([#353](https://github.com/UniversalDependencies/UD_English-EWT/issues/353))
  - Add neaten.py, which implements English-specific validation rules

**2022-05-15 v2.10**

Highlights:

  - Fixed all validation errors
  - Implement new [`goeswith` policy](https://universaldependencies.org/changes.html#typos-and-goeswith) ([#314](https://github.com/UniversalDependencies/UD_English-EWT/pull/314))
  - Use `parataxis` for "X so Y" and similar ([#313](https://github.com/UniversalDependencies/UD_English-EWT/pull/313))

**2021-11-15 v2.9**
  - Fixed all validation errors
  - Many other improvements to annotation of assorted words and constructions

**2021-05-15 v2.8**
  - Fixed many wrong lemmata, POS tags, and relations
  - Reanalyzed many dependencies to conform to UD validation
  - Retagged words in names to limit PROPN to true nouns
  - Fixed certain metadata issues
  - Fixed some typos, added CorrectForms
  - Added missing multiword tokens for clitics/contractions
  - Added Style=Expr feature for expressive spellings
  - Fixed many incorrectly non-projective graphs, reanalyzing as projective
  - Reannotated list items as NUM not X

**2020-11-15 v2.7**
  - Added multiword tokens where appropriate for contracted verb forms
  - Fixed some wrong lemmata and POS tags

**2020-05-15 v2.6**
  - Added paragraph boundaries
  - Fixed some wrong lemmata and POS tags
  - Fixed directionality of some `goeswith` dependencies

**2019-11-15 v2.5**
  - Fixed miscellaneous syntactic issues
  - Fixed CoNLL-U syntax error

**2019-05-15 v2.4**
  - Fixed some wrong lemmata and POS tags
  - Fixed miscellaneous syntactic issues
  - Fixed some punctuation attachments
  - Fixed malformed enhanced graphs

**2018-11-15 v2.3**
  - Fixed several lemmata

**2018-04-15 v2.2**
  - Repository renamed from UD_English to UD_English-EWT
  - Automatically added enhanced dependencies (These have not been manually checked!)
  - Fixed some wrong lemmata and POS tags
  - Fixed miscellaneous syntactic issues

**2017-11-15 v2.1**

 - Fixed some wrong lemmata, POS tags
 - Fixed miscellaneous syntactic issues
 - Added basic dependencies into the `DEPS` column according to the CONLL-U v2
    format

**2017-02-15 v2.0**

 - Updated treebank to conform to v2 guidelines
 - Fixed some wrong lemmata
 - Fixed miscellaneous syntactic issues
 - Added empty nodes for gapped constructions in enhanced representation

**2016-11-15 v1.4**

 - Changed POS tag of fused det-noun pronouns (e.g., *"somebody"*, *"nothing"*)
    to `PRON`
 - Added original, untokenized sentences to CoNLL-U files
 - Fixed some POS errors, features and wrong lemmata
 - Fixed miscellaneous syntactic issues in a few sentences

**2016-05-15 v1.3**

 - Improved mapping of `WDT` to UPOS
 - Corrected lemma of *"n't"* to *"not"*
 - Fixed some errors between `advcl`, `ccomp` and `parataxis`
 - Fixed inconsistent analyses of sentences repeated between dev and train sets
 - Fixed miscellaneous syntactic issues in a few sentences

**2015-11-15 v1.2**

 - Bugfix: removed *_NFP* suffix from some lemmas
 - Fixed date annotations to adopt UD standard
 - Remove escaping of *(* and *)* from word tokens (XPOSTAGs are still `-LRB-`
    and `-RRB-`)
 - Improved precision of `xcomp` relation
 - Improved recall of `name` relation
 - Corrected lemmas for reduced auxiliaries
 - Corrected UPOS tags of pronominal uses of *this/that/these/those* (from `DET`
    to `PRON`)
 - Corrected UPOS tags of subordinating conjunctions (from `ADP` to `SCONJ`)
 - Corrected UPOS tags of some main verbs (from `AUX` to `VERB`)


# Contributing

To help improve the corpus, please alert us to any errors you find in it.
The best way to do this is to file a github issue at:

   https://github.com/UniversalDependencies/UD_English-EWT/issues

We also welcome pull requests. If you want to make edits, please modify the
trees in the individual files in the `not-to-release/sources` directory instead
of making direct changes to `en_ewt-ud-{dev,test,train}.conllu`.


# Acknowledgments

Annotation of the Universal Dependencies English Web Treebank was carried out by
(in order of size of contribution):

 - Natalia Silveira
 - Timothy Dozat
 - Sebastian Schuster
 - Miriam Connor
 - Marie-Catherine de Marneffe
 - Nathan Schneider
 - Ethan Chi
 - Samuel Bowman
 - Christopher Manning
 - Hanzhi Zhu
 - Daniel Galbraith
 - John Bauer

Creation of the CoNLL-U files, including calculating UPOS, feature, and lemma
information was primarily done by

 - Sebastian Schuster
 - Natalia Silveira

The construction of the Universal Dependencies English Web Treebank was
partially funded by a gift from Google, Inc., which we gratefully acknowledge.


# Citations

You are encouraged to cite this paper if you use the Universal Dependencies
English Web Treebank:

    @inproceedings{silveira14gold,
      year = {2014},
      author = {Natalia Silveira and Timothy Dozat and Marie-Catherine de
		  Marneffe and Samuel Bowman and Miriam Connor and John Bauer and
		  Christopher D. Manning},
      title = {A Gold Standard Dependency Corpus for {E}nglish},
      booktitle = {Proceedings of the Ninth International Conference on Language
        Resources and Evaluation (LREC-2014)}
    }


# Metadata

```
=== Machine-readable metadata (DO NOT REMOVE!) ================================
Data available since: UD v1.0
License: CC BY-SA 4.0
Includes text: yes
Genre: blog social reviews email web
Lemmas: automatic with corrections
UPOS: converted with corrections
XPOS: manual native
Features: converted with corrections
Relations: manual native
Contributors: Silveira, Natalia; Dozat, Timothy; Manning, Christopher; Schuster, Sebastian; Chi, Ethan; Bauer, John; Connor, Miriam; de Marneffe, Marie-Catherine; Schneider, Nathan; Bowman, Sam; Zhu, Hanzhi; Galbraith, Daniel; Bauer, John
Contributing: here source
Contact: syntacticdependencies@lists.stanford.edu
===============================================================================
```
