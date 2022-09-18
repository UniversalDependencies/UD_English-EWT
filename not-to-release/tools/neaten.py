"""
neatEN: Validator for English UD corpora

Implements English-specific rules not covered by the general
UD validator (https://github.com/UniversalDependencies/tools/)

Parts are adapted from the GUM validator,
https://raw.githubusercontent.com/amir-zeldes/gum/master/_build/utils/validate.py

@author: Nathan Schneider
@since: 2022-09-10
"""

from collections import defaultdict
import glob
import re
import sys
import conllu

def isRegularNode(line):
    idS = str(line['id'])
    return not ('-' in idS or '.' in idS)

def validate_src(infiles):
    tok_count = 0
    lemma_dict = defaultdict(lambda : defaultdict(int))  # collects tok+pos -> lemmas -> count  for consistency checks
    lemma_docs = defaultdict(set)

    for inFP in infiles:
        with open(inFP) as inF:
            doc = None
            for tree in conllu.parse_incr(inF):
                if 'newdoc id'in tree.metadata:
                    doc = tree.metadata['newdoc id']
                tree.metadata['docname'] = doc
                tree.metadata['filename'] = inFP.rsplit('/',1)[1]

                sentid = tree.metadata['sent_id']
                prev_line = None
                for line in tree:
                    """ `dict(line)` e.g.:
                    {'id': 1, 'form': 'What', 'lemma': 'what', 'upos': 'PRON',
                    'xpos': 'WP', 'feats': {'PronType': 'Int'}, 'head': 0,
                    'deprel': 'root', 'deps': [('root', 0)], 'misc': None}
                    `line` is of type dict_items
                    """
                    if not isRegularNode(line):    # avoid e.g. ellipsis node
                        continue
                    tok_count += 1
                    form, xpos, lemma = line['form'], line['xpos'], line['lemma']
                    # for lemma error-checking purposes, uses the corrected form of the token if there is one
                    tok = (line.get('misc') or {}).get('CorrectForm') or form   # in GUM, some explicit CorrectForm=_ which parses as None

                    # goeswith
                    if line['deprel']=='goeswith' and prev_line['deprel']!="goeswith":
                        # undo previous count as it has a partial form string
                        lemma_dict[prev_key][prev_line["lemma"]] -= 1
                        if prev_line['xpos'] in ["AFX", "GW"]:
                            # copy substantive XPOS to the preceding token
                            prev_line['xpos'] = line['xpos']

                        prev_line['form'] += line['form']
                        ptok = (prev_line.get('misc') or {}).get('CorrectForm') or prev_line['form']    # in GUM, some explicit CorrectForm=_ which parses as None
                        lemma_dict[ptok,prev_line['xpos']][prev_line["lemma"]] += 1
                        lemma_docs[ptok,prev_line['xpos'],prev_line["lemma"]].add(sentid)
                    else:
                        lemma_dict[(tok,xpos)][lemma] += 1
                        lemma_docs[(tok,xpos,lemma)].add(sentid)

                    prev_line = line
                    prev_key = (tok,xpos)

                validate_annos(tree)

    validate_lemmas(lemma_dict,lemma_docs)
    sys.stdout.write("\r" + " "*70)

def validate_lemmas(lemma_dict, lemma_docs):
    exceptions = [("Democratic","JJ","Democratic"),("Water","NNP","Waters"),("Sun","NNP","Sunday"),("a","IN","of"),
                  ("a","IN","as"),("car","NN","card"),("lay","VB","lay"),("that","IN","than"),
                  ("da","NNP","Danish"),("Jan","NNP","Jan"),("Jan","NNP","January"),
                  ("'s","VBZ","have"),("’s","VBZ","have"),("`s","VBZ","have"),("'d","VBD","do"),("'d","VBD","have")]
    suspicious_types = 0
    for tok, xpos in sorted(lemma_dict):
        if sum(lemma_dict[(tok,xpos)].values()) > 1:
            for i, lem in enumerate(filter(lambda y: y!='_', sorted(lemma_dict[(tok,xpos)],key=lambda x:lemma_dict[(tok,xpos)][x],reverse=True))):
                docs = ", ".join(list(lemma_docs[(tok,xpos,lem)]))
                if i == 0:
                    majority = lem
                else:
                    if lemma_dict[tok,xpos][lem]>0 and (tok,xpos,lem) not in exceptions:  # known exceptions
                        suspicious_types += 1
                        print("! rare lemma " + lem + " for " + tok + "/" + xpos + " in " + docs +
                                     " (majority: " + majority + ")\n")
    if suspicious_types > 0:
        sys.stderr.write("! "+str(suspicious_types) + " suspicious lemma types detected\n")


def validate_annos(tree):
        docname = tree.metadata['sent_id']

        # Dictionaries to hold token annotations from conllu data
        funcs = {}
        postags = {}
        tokens = {}
        parent_ids = {}
        lemmas = {}
        sent_positions = defaultdict(lambda: "_")
        parents = {}
        children = defaultdict(list)
        child_funcs = defaultdict(list)
        tok_num = 0

        line_num = 0
        sent_start = 0
        for r, line in enumerate(tree):
            line_num += 1
            head = line['head']
            #if "." in line['id']:  # Ignore ellipsis tokens
            if not isRegularNode(line):
                continue

            tok_num += 1
            tok = (line.get('misc') or {}).get('CorrectForm') or line['form']   # in GUM, some explicit CorrectForm=_ which parses as None
            funcs[tok_num] = line['deprel']
            if head!=0:  # Root token
                if head == "_" or head == '' or head is None:
                    print("Invalid head '_' at line " + str(r) + " in " + docname)
                    sys.exit()
                parent_ids[tok_num] = head
                children[head].append(tok)
                child_funcs[head].append(line['deprel'])
            else:
                parent_ids[tok_num] = 0
            tokens[tok_num] = tok

        for i in range(1, len(tokens) + 1, 1):
            if parent_ids[i] == 0:
                parents[i] = "ROOT"
            else:
                parents[i] = tokens[parent_ids[i]]

        tok_num = 0
        new_sent = True
        for line in tree:
            if not isRegularNode(line):
                continue
            tok_num += 1
            postags[tok_num], lemmas[tok_num] = line['xpos'], line['lemma']
            #sent_types[tok_num] = s_type
            if new_sent:
                sent_positions[tok_num] = "first"
                new_sent = False
        sent_positions[tok_num] = "last"

        tok_num = 0

        # PTB with HYPH, ADD, NFP
        tagset = ["CC","CD","DT","EX","FW","IN","IN/that","JJ","JJR","JJS","LS","MD","NN","NNS","NNP","NNPS","PDT","POS",
                  "PRP","PRP$","RB","RBR","RBS","RP","SENT","SYM","TO","UH","VB","VBD","VBG","VBN","VBP","VBZ",
                  "WDT","WP","WP$","WRB", ".", "``", "''", "-LRB-", "-RRB-", "-LSB-", "-RSB-", "-LCB-", "-RCB-",
                   ",", ":", "$", "HYPH", "ADD", "AFX", "NFP", "GW"]
        non_lemmas = ["them","me","him","n't"]
        non_lemma_combos = [("PP","her"),("MD","wo"),("PP","us"),("DT","an")]
        lemma_pos_combos = {"which":"WDT"}
        non_cap_lemmas = ["There","How","Why","Where","When"]

        prev_tok = ""
        prev_pos = ""
        for i, line in enumerate(tree):
            if not isRegularNode(line):
                continue

            tok_num += 1
            tok = (line.get('misc') or {}).get('CorrectForm') or line['form']   # in GUM, some explicit CorrectForm=_ which parses as None
            assert tok is not None,(docname, tree.metadata['filename'], tok_num, line)
            xpos, lemma = line['xpos'], line['lemma']
            pos = xpos
            upos = line['upos']
            func = line['deprel']
            if pos not in tagset:
                print("WARN: invalid POS tag " + pos + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
            if lemma.lower() in non_lemmas:
                print("WARN: invalid lemma " + lemma + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
            elif lemma in non_cap_lemmas:
                print("WARN: invalid lemma " + lemma + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
            elif (pos,lemma.lower()) in non_lemma_combos:
                print("WARN: invalid lemma " + lemma + " for POS "+pos+" in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
            elif lemma in lemma_pos_combos:
                if pos != lemma_pos_combos[lemma]:
                    print("WARN: invalid pos " + pos + " for lemma "+lemma+" in " + docname + " @ line " + str(i) + " (token: " + tok + ")")

            parent_string = parents[tok_num]
            parent_id = parent_ids[tok_num]
            parent_lemma = lemmas[parent_ids[tok_num]] if parent_ids[tok_num] != 0 else ""
            parent_func = funcs[parent_ids[tok_num]] if parent_ids[tok_num] != 0 else ""
            parent_pos = postags[parent_ids[tok_num]] if parent_ids[tok_num] != 0 else ""
            filename = tree.metadata['filename']
            assert parent_pos is not None,(tok_num,parent_ids[tok_num],postags,filename)
            S_TYPE_PLACEHOLDER = None
            assert parent_string is not None,(tok_num,docname,filename)
            flag_dep_warnings(tok_num, tok, pos, upos, lemma, func, parent_string, parent_lemma, parent_id,
                              children[tok_num], child_funcs[tok_num], S_TYPE_PLACEHOLDER, docname,
                              prev_tok, prev_pos, sent_positions[tok_num], parent_func, parent_pos, filename)
            prev_pos = pos
            prev_tok = tok



def flag_dep_warnings(id, tok, pos, upos, lemma, func, parent, parent_lemma, parent_id, children, child_funcs, s_type,
                      docname, prev_tok, prev_pos, sent_position, parent_func, parent_pos, filename):
    # Shorthand for printing errors
    inname = " in " + docname + " @ token " + str(id) + " (" + parent + " -> " + tok + ") " + filename

    if func == "amod" and pos in ["VBD"]:
        print("WARN: finite past verb labeled amod " + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func in ['fixed','goeswith','flat', 'conj'] and id < parent_id:
        print("WARN: back-pointing func " + func + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func in ['cc:preconj','cc','nmod:poss'] and id > parent_id:
        if tok not in ["mia"]:
            print("WARN: forward-pointing func " + func + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func == "auxpass" and lemma != "be" and lemma != "get":
        print("WARN: auxpass must be 'be' or 'get'" + inname)

    if lemma == "'s" and pos != "POS":
        print("WARN: possessive 's must be tagged POS" + inname)

    if func not in ["case","reparandum","goeswith"] and pos == "POS":
        print("WARN: tag POS must have function case" + inname)

    if pos in ["VBG","VBN","VBD"] and lemma == tok:
        # check cases where VVN form is same as tok ('know' and 'notice' etc. are recorded typos, l- is a disfluency)
        if tok not in ["shed","put","read","become","come","overcome","cut","pre-cut","hit","split","cast","set","hurt","run","overrun","outrun","broadcast","knit",
                       "undercut","spread","shut","upset","burst","bit","bid","outbid","let","l-","g-","know","notice","reach","raise","beat","forecast"]:
            print("WARN: tag "+pos+" should have lemma distinct from word form" + inname)

    if pos == "NNPS" and tok == lemma and tok.endswith("s") and func != "goeswith":
        if tok not in ["Netherlands","Analytics","Olympics","Commons","Paralympics","Vans",
                       "Andes","Forties","Philippines"]:
            print("WARN: tag "+pos+" should have lemma distinct from word form" + inname)

    if pos == "NNS" and tok.lower() == lemma.lower() and lemma.endswith("s") and func != "goeswith":
        if lemma not in ["surroundings","energetics","politics","jeans","clothes","electronics","means","feces",
                         "biceps","triceps","news","species","economics","arrears","glasses","thanks","series"]:
            if re.match(r"[0-9]+'?s",lemma) is None:  # 1920s, 80s
                print("WARN: tag "+pos+" should have lemma distinct from word form" + inname)

    if pos == "IN" and func=="compound:prt":
        print("WARN: function " + func + " should have pos RP, not IN" + inname)

    if pos == "CC" and func not in ["cc","cc:preconj","conj","reparandum","root","dep"] and not (parent_lemma=="whether" and func=="fixed"):
        if not ("languages" in inname and tok == "and"):  # metalinguistic discussion in whow_languages
            print("WARN: pos " + pos + " should normally have function cc or cc:preconj, not " + func + inname)

    if pos == "RP" and func not in ["compound:prt","root","conj","ccomp"] or pos != "RP" and func=="compound:prt":
        print("WARN: pos " + pos + " should not normally have function " + func + inname)

    if pos != "CC" and func in ["cc","cc:preconj"]:
        if lemma not in ["/","rather","as","et","+","let","only","-"]:
            print("WARN: function " + func + " should normally have pos CC, not " + pos + inname)

    if pos == "VBG" and "very" in children:
        print("WARN: pos " + pos + " should not normally have child 'very'" + inname)

    if pos == "UH" and func=="advmod":
        print("WARN: pos " + pos + " should not normally have function 'advmod'" + inname)

    if pos =="IN" and func=="discourse":
        print("WARN: pos " + pos + " should not normally have function 'discourse'" + inname)

    if pos == "VBG" and "case" in child_funcs:
        print("WARN: pos " + pos + " should not normally have child function 'case'" + inname)

    if pos.startswith("V") and any([f.startswith("nmod") for f in child_funcs]):
        print("WARN: pos " + pos + " should not normally have child function 'nmod.*'" + inname)

    if pos in ["JJR","JJS","RBR","RBS"] and lemma == tok:
        if lemma not in ["least","further","less","more"] and not lemma.endswith("most"):
            print("WARN: comparative or superlative "+tok+" with tag "+pos+" should have positive lemma not " + lemma + inname)

    if re.search(r"never|not|no|n't|n’t|’t|'t|nt|ne|pas|nit", tok, re.IGNORECASE) is None and func == "neg":
        print(str(id) + docname)
        print("WARN: mistagged negative" + inname)

    if pos == "VBG" and func == "compound":
        # Check phrasal compound exceptions where gerund clause is a compound modifier:
        # "'we're *losing* $X - fix it' levels of pressure
        if tok not in ["losing"]:
            print("WARN: gerund compound modifier should be tagged as NN not VBG" + inname)

    if pos == "VBG" and func in ["obj","nsubj","iobj","nmod","obl"]:
        if not tok == "following" and func=="obj":  # Exception nominalized "the following"
            print("WARN: gerund should not have noun argument structure function " + func + inname)

    if pos.startswith("NN") and func=="amod":
        print("WARN: tag "+ pos + " should not be " + func + inname)

    be_funcs = ["cop", "aux", "root", "csubj", "auxpass", "rcmod", "ccomp", "advcl", "conj","xcomp","parataxis","vmod","pcomp"]
    if lemma == "be" and func not in be_funcs:
        if not parent_lemma == "that" and func == "fixed":  # Exception for 'that is' as mwe
            print("WARN: invalid dependency of lemma 'be' > " + func + inname)

    if parent_lemma in ["tell","show","give","pay","teach","owe","text","write"] and \
            tok in ["him","her","me","us","you"] and func=="obj":
        print("WARN: person object of ditransitive expected to be iobj, not obj" + inname)

    if func == "aux" and lemma.lower() != "be" and lemma.lower() != "have" and lemma.lower() !="do" and pos!="MD" and pos!="TO":
        print("WARN: aux must be modal, 'be,' 'have,' or 'do'" + inname)

    if func == "xcomp" and pos in ["VBP","VBZ","VBD"]:
        if parent_lemma not in ["=","seem"]:
            print("WARN: xcomp verb should be infinitive, not tag " + pos + inname)

    if parent_pos is None:
        assert False,(id,docname)

    if func == "xcomp" and pos in ["VB"] and parent_pos.startswith("N"):
        print("WARN: infinitive child of a noun should be acl not xcomp" + inname)

    if func =="xcomp" and parent_lemma == "be":
        print("WARN: verb lemma 'be' should not have xcomp child" + inname)

    IN_not_like_lemma = ["vs", "vs.", "v", "ca", "that", "then", "a", "fro", "too", "til", "wether", "b/c"]  # incl. known typos
    if pos == "IN" and tok.lower() not in IN_not_like_lemma and lemma != tok.lower() and func != "goeswith" and "goeswith" not in child_funcs:
        print("WARN: pos IN should have lemma identical to lower cased token" + inname)
    if pos == "DT" and lemma == "an":
        print("WARN: lemma of 'an' should be 'a'" + inname)

    if re.search(r"“|”|n’t|n`t|[’`](s|ve|d|ll|m|re|t)", lemma, re.IGNORECASE) is not None:
        print(str(id) + docname)
        print("WARN: non-ASCII character in lemma" + inname)

    if pos == "POS" and lemma != "'s" and func != "goeswith":
        print(str(id) + docname)
        print("WARN: tag POS must have lemma " +'"'+ "'s" + '"' + inname)

    if func == "goeswith" and lemma != "_":
        print("WARN: deprel goeswith must have lemma '_'" + inname)

    if func == "obj" and "case" in child_funcs and not (pos == "NNP" and any([x in children for x in ["'s","’s"]])):
        print("WARN: obj should not have child case" + inname + str(children))

    if func == "ccomp" and "mark" in child_funcs and not any([x in children for x in ["that","That","whether","if","Whether","If","wether","a"]]):
        if not ((lemma == "lie" and "once" in children) or  (lemma=="find" and ("see" in children or "associate" in children))):  # Exceptions
            print("WARN: ccomp should not have child mark" + inname)

    if func == "acl:relcl" and pos in ["VB"] and "to" in children and "cop" not in child_funcs and "aux" not in child_funcs:
        print("WARN: infinitive with tag " + pos + " should be acl not acl:relcl" + inname)

    if pos in ["VBG"] and "det" in child_funcs:
        # Exceptions for phrasal compound in GUM_reddit_card and nominalization in GUM_academic_exposure
        if tok != "prioritizing" and tok != "following":
            print(str(id) + docname)
            print("WARN: tag "+pos+" should not have a determinder 'det'" + inname)

    if parent_lemma == "let" and func=="ccomp":
        print("WARN: verb 'let' should take xcomp clausal object, not ccomp" + inname)

    if pos == "MD" and lemma not in ["can","must","will","shall","would","could","may","might","ought","should"] and func != "goeswith":
        print("WARN: lemma '"+lemma+"' is not a known modal verb for tag MD" + inname)

    if lemma == "like" and pos == "UH" and func not in ["discourse","conj","reparandum"]:
        print("WARN: lemma '"+lemma+"' with tag UH should have deprel discourse, not "+ func + inname)

    if func in ["iobj","obj"] and parent_lemma in ["become","remain","stay"]:
        print("WARN: verb '"+parent_lemma+"' should take xcomp not "+func+" argument" + inname)

    if func in ["nmod:tmod","nmod:npmod","obl:tmod","obl:npmod"] and "case" in child_funcs:
        print("WARN: function " + func +  " should not have 'case' dependents" + inname)

    if func in ["aux:pass","nsubj:pass"] and parent_pos not in ["VBN"]:
        if not (("stardust" in docname and parent_lemma == "would") or parent_lemma == "Rated"):
            print("WARN: function " + func + " should not be the child of pos " + parent_pos + inname)

    if func == "obl:agent" and (parent_pos not in ["VBN"] or "by" not in children):
        print("WARN: function " + func +  " must by child of V.N with a 'by' dependent" + parent_pos + inname)

    if child_funcs.count("obl:agent") > 1:
        print("WARN: a token may have at most one obl:agent dependent" + inname)

    if "obl:agent" in child_funcs and ("nsubj" in child_funcs or "csubj" in child_funcs) and not "nsubj:pass" in child_funcs:
        print("WARN: a token cannot have both a *subj relation and obl:agent" + inname)

    if pos in ["VBD","VBD","VBP"] and "aux" in child_funcs:
        print(str(id) + docname)
        print("WARN: tag "+pos+" should not have auxiliaries 'aux'" + inname)

    if lemma == "not" and func not in ["advmod","root","parataxis","reparandum","advcl","conj","orphan","fixed"]:
        print("WARN: deprel "+func+" should not be used with lemma '"+lemma+"'" + inname)

    if func == "xcomp" and parent_lemma in ["see","hear","notice"]:  # find
        print("WARN: deprel "+func+" should not be used with perception verb lemma '"+parent_lemma+"' (should this be nsubj+ccomp?)" + inname)

    if "obj" in child_funcs and "ccomp" in child_funcs:
        print("WARN: token has both obj and ccomp children" + inname)

    if func == "acl" and (pos.endswith("G") or pos.endswith("N")) and parent_id == id + 1:  # premodifier V.G/N should be amod not acl
        print("WARN: back-pointing " + func + " for adjacent premodifier (should be amod?) in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func.endswith("tmod") and pos.startswith("RB"):
        print("WARN: adverbs should not be tmod" + inname)

    """
    Existential construction

    X.xpos=EX <=> X.deprel=expl & X.lemma=there
    X.xpos=EX => X.upos=PRON
    """
    if func!="reparandum":
        _ex_tag = (pos=="EX")
        _expl_there = (func=="expl" and lemma=="there")
        if _ex_tag != _expl_there or (_ex_tag and upos!="PRON"):
            print("WARN: 'there' with " + pos + " and " + upos + inname)
        if lemma=="there" and not _ex_tag and 'nsubj' in func:
            print("WARN: subject 'there' not tagged as EX/expl" + inname)

    """
    (Pre)determiner 'what'

    X[lemma=what,xpos=WDT] <=> X[lemma=what,deprel=det|det:predet]
    """
    _what_wdt = (lemma=="what" and pos=="WDT")
    _what_det = (lemma=="what" and func in ["det", "det:predet"])
    if _what_wdt!=_what_det:
        print("WARN: what/WDT should correspond with det or det:predet" + inname)

    """
    Numerics

    X[lemma contains digits and nonalphabetics] => X.upos=NUM

    (Note that pluralized years like "1960s" or "'60s" are NOUN/NNS)

    pattern { X[]; X.lemma=re"\([0-9]\|[^A-Za-z0-9]\)+" }
    without { X.lemma=re"[0-9]+" }
    without { X.lemma=re"[^A-Za-z0-9]+" }
    """
    if upos not in ["NUM","X"] and re.match(r'^[\d\W_]*\d[\d\W_]*$',lemma) and pos!="NNS" and lemma!="<3":  # and not re.match(r'^\d+$',lemma):
        print("WARN: numeric lemma '" + lemma + "' is not NUM" + inname)

    #if func == "advmod" and lemma in ["where","when"] and parent_func == "acl:relcl":
    #    print("WARN: lemma "+lemma+" should not be func '"+func+"' when it is the child of a '" + parent_func + "'" + inname)

    if (sent_position == "first" and pos == "''") or (sent_position == "last" and pos=="``"):
        print("WARN: incorrect quotation mark tag " + pos + " at "+sent_position+" position in sentence" + inname)

    mwe_pairs = {("accord", "to"), ("all","but"), ("as","for"), ("as","if"), ("as", "well"), ("as", "as"), ("as","in"), ("all","of"), ("as","oppose"),("as","to"),
                 ("at","least"),("because","of"),("due","to"),("had","better"),("'d","better"),
                 ("how","come"),("in","between"), ("per", "se"), ("in","case"),("in","of"), ("in","order"), ("in","that"),
                 ("instead","of"), ("kind","of"),("less","than"),("let","alone"),
                 ("more","than"),("not","to"),("not","mention"),("of","course"),("prior","to"),("rather","than"),("so","as"),
                 ("so", "to"),("sort", "of"),("so", "that"),("such","as"),("that","is"), ("up","to"),
                 ("depend","on"),("out","of"),("off","of"),("long","than"),("on","board"),("as","of"),("depend","upon"),
                 ("that","be"),("just","about"),("vice","versa"),("as","such"),("next","to"),("close","to"),("one","another"),
                 ("de","facto"),("each","other"), ("as","many")}

    # Ad hoc listing of triple mwe parts - All in all, in order for, whether or not
    mwe_pairs.update({("all","in"),("all","all"),("in","for"),("whether","or"),("whether","not")})

    if func == "fixed":
        if (parent_lemma.lower(), lemma.lower()) not in mwe_pairs:
            print("WARN: unlisted fixed expression" + inname)

    #if pos != "CD" and "quantmod" in child_funcs:
    #    print("WARN: quantmod must be cardinal number" + inname)

    if tok == "sort" or tok == "kind":
        if "det" in child_funcs and "fixed" in child_funcs:
            print("WARN: mistagged fixed expression" + inname)

    if tok == "rather" and "fixed" in child_funcs and func not in ["cc","mark"]:
        print("WARN: 'rather than' fixed expression must be cc or mark" + inname)

    if s_type == "imp" or s_type == "frag" or s_type == "ger" or s_type == "inf":
        if func == "root" and "nsubj" in child_funcs:
            # Exception for frag structures like "Whatever it is that ...", which is actually frag
            # and "don't you VERB", which is an imperative with a subject
            if not ("acl:relcl" in child_funcs and "cop" in child_funcs and s_type=="frag") and \
                    not (("do" in children or "Do" in children) and ("n't" in children or "not" in children)):
                print("WARN: " + s_type + " root may not have nsubj" + inname)

    temp_wh = ["when", "how", "where", "why", "whenever", "while", "who", "whom", "which", "whoever", "whatever",
               "what", "whomever", "however"]

    #if s_type == "wh" and func == "root":
    #    tok_count = 0                            #This is meant to keep it from printing an error for every token.
    #    if tok.lower() not in temp_wh:
    #        for wh in children:
    #            if re.search(r"when|how|where|why|whenever|while|who.*|which|what.*", wh, re.IGNORECASE) is None:
    #                tok_count += 1
    #        if tok_count == len(children):
    #            print("WARN: wh root must have wh child" + inname)

    if s_type == "q" and func == "root":
        for wh in children:
            if wh in temp_wh:
                if not any([c.lower()=="do" or c.lower()=="did" for c in children]):
                    if not (tok == "Remember" and wh == "when") and not (tok=="know" and wh=="what") and \
                            not (tok =="Know" and wh=="when"):  # Listed exceptions in GUM_reddit_bobby, GUM_conversation_christmas, GUM_vlog_covid
                        print("WARN: q root may not have wh child " + wh + inname)

    suspicious_pos_tok = [("*","DT","only","RB"),
                          ("*","JJ","one","CD")]

    for w1, pos1, w2, pos2 in suspicious_pos_tok:
        if w1 == prev_tok or w1 == "*":
            if pos1 == prev_pos or pos1 == "*":
                if w2 == tok or w2 == "*":
                    if pos2 == pos or pos2 == "*":
                        print("WARN: suspicious n-gram " + prev_tok + "/" + prev_pos+" " + tok + "/" + pos + inname)

if __name__=='__main__':
    validate_src(sys.argv[1:] or glob.glob('../../en_ewt-ud-*.conllu'))
