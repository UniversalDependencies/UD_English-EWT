#coding=utf-8
"""
neatEN: Validator for English UD corpora

Implements English-specific rules not covered by the general
UD validator (https://github.com/UniversalDependencies/tools/)

Parts are adapted from the GUM validator,
https://raw.githubusercontent.com/amir-zeldes/gum/master/_build/utils/validate.py

To get an overview of the distribution of error types:

$ python neaten.py | sort | cut -c1-30 | uniq -c

@author: Nathan Schneider
@since: 2022-09-10
"""

from typing import Dict, List
from collections import defaultdict, Counter
import glob
import re
import sys
import traceback
import conllu

NNS_warnings = Counter()

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
                if 'newdoc id' in tree.metadata:
                    doc = tree.metadata['newdoc id']
                tree.metadata['docname'] = doc
                tree.metadata['filename'] = ('/'+inFP).rsplit('/',1)[1] # prefix slash so it runs on GUM

                sentid = tree.metadata['sent_id']
                prev_line = prev_key = None
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
                    if line['deprel']=='goeswith' and prev_line:
                        # copy substantive UPOS, feats from the preceding token
                        line['upos'] = prev_line['upos']
                        line['feats'] = dict(prev_line['feats'])
                        if 'Typo' in line['feats']:
                            del line['feats']['Typo']

                    if line['deprel']=='goeswith' and prev_line and prev_line['deprel']!="goeswith":
                        # undo previous count as it has a partial form string
                        lemma_dict[prev_key][prev_line["lemma"]] -= 1

                        prev_line['merged'] = True # Typo fixed via goeswith deprel.
                        prev_line['form'] += line['form']
                        ptok = (prev_line.get('misc') or {}).get('CorrectForm') or prev_line['form']    # in GUM, some explicit CorrectForm=_ which parses as None
                        lemma_dict[ptok,prev_line['xpos']][prev_line["lemma"]] += 1
                        lemma_docs[ptok,prev_line['xpos'],prev_line["lemma"]].add(sentid)
                    else:
                        assert prev_line or line['deprel']!='goeswith'
                        lemma_dict[(tok,xpos)][lemma] += 1
                        lemma_docs[(tok,xpos,lemma)].add(sentid)

                    prev_line = line
                    prev_key = (tok,xpos)

                line2 = None
                for line1 in tree[::-1]: # go backwards to propagate from last token of goeswith expression
                    if not isRegularNode(line1):    # avoid e.g. ellipsis node
                        continue
                    if line2 and line2['deprel']=='goeswith' and line1['xpos'] in ["AFX", "GW"]:
                            # copy substantive XPOS to the preceding token
                            line1['xpos'] = line2['xpos']
                    line2 = line1

                validate_annos(tree)

    validate_lemmas(lemma_dict,lemma_docs)
    if NNS_warnings:
        sys.stderr.write("!suspicious NNS lemmas: "+' '.join(k for k,v in NNS_warnings.most_common()) + '\n')
    sys.stdout.write("\r" + " "*70)

def validate_lemmas(lemma_dict, lemma_docs):
    exceptions = [("Democratic","JJ","Democratic"),("Water","NNP","Waters"),("Sun","NNP","Sunday"),("a","IN","of"),
                  ("a","IN","as"),("car","NN","card"),("lay","VB","lay"),("that","IN","than"),
                  ("da","NNP","Danish"),("Jan","NNP","Jan"),("Jan","NNP","January"),
                  ("'s","VBZ","have"),("’s","VBZ","have"),("`s","VBZ","have"),("'d","VBD","do"),("'d","VBD","have")]
    suspicious_types = 0
    majority = None
    for tok, xpos in sorted(lemma_dict):
        if sum(lemma_dict[(tok,xpos)].values()) > 1:
            for i, lem in enumerate(filter(lambda y: y!='_', sorted(lemma_dict[(tok,xpos)],key=lambda x:lemma_dict[(tok,xpos)][x],reverse=True))):
                docs = ", ".join(sorted(lemma_docs[(tok,xpos,lem)]))
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
        upostags = {}
        feats: Dict[int,Dict[str,str]] = {}
        tokens = {}
        parent_ids: Dict[int,int] = {}
        lemmas = {}
        sent_positions = defaultdict(lambda: "_")
        parents: Dict[int,str] = {}
        children: Dict[int,List[str]] = defaultdict(list)
        child_funcs: Dict[int,List[str]] = defaultdict(list)
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
            feats[tok_num] = line['feats']

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
            postags[tok_num], upostags[tok_num], lemmas[tok_num] = line['xpos'], line['upos'], line['lemma']
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
        # Map UPOS tags to known associated PTB tags. This helps identify mismatched UPOS+POS pairs.
        tagset_combos = {
            "ADJ":["JJ","JJR","JJS","NN","NNP","FW","AFX"],
            "ADP":["RP","IN","NNP","CC"],
            "ADV":["RB","RBR","RBS","WRB","CC","NN","NNP","FW","AFX"],
            "AUX":["MD","VB","VBD","VBG","VBN","VBP","VBZ"],
            "CCONJ":["CC"],
            "DET":["DT","PDT","WDT","NNP"],
            "INTJ":["UH","JJ","NN","FW"],
            "NOUN":["NN","NNS"],
            "NUM":["CD","LS","NNP"],
            "PART":["POS","RB","TO"],
            "PRON":["PRP","PRP$","WP","WP$","DT","WDT","EX","NN"],
            "PROPN":["ADD","NNP","NNPS"],
            "PUNCT":[".",",",":","``","''","-LCB-","-RCB-","-LRB-","-RRB-","-LSB-","-RSB-","NFP","HYPH","SYM"],
            "SCONJ":["IN"],
            "SYM":["$",",","SYM","NFP","NN","NNS","IN","HYPH"],
            "VERB":["VB","VBD","VBG","VBN","VBP","VBZ","NNP"],
            "X":["ADD","GW","FW","AFX","NN","NNP","VB","RB","JJ","WP","LS","IN","PRP","WRB","MD","-LRB-","-RRB-"]
        }

        non_lemmas = ["them","me","him","n't"]
        non_lemma_combos = [("PP","her"),("MD","wo"),("PP","us"),("DT","an")]
        lemma_pos_combos = {"which":"WDT"}
        non_cap_lemmas = ["There","How","Why","Where","When"]

        passive_verbs = set()

        prev_tok = ""
        prev_pos = ""
        prev_upos = ""
        prev_func = ""
        prev_parent_lemma = ""
        prev_feats = {}
        prev_misc = {}
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
            featlist = line['feats'] or {}
            misclist = line['misc'] or {}
            edeps = line['deps']
            merged = 'merged' in line and line['merged']
            form = check_and_fix_form_typos(tok_num, line['form'], featlist, misclist, merged, docname)

            if featlist and featlist.get("Voice")=="Pass":
                passive_verbs.add(tok_num)

            if upos not in tagset_combos.keys():
                print("WARN: invalid UPOS tag " + upos + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
            if pos not in tagset:
                print("WARN: invalid POS tag " + pos + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
            if upos in tagset_combos and pos not in tagset_combos[upos]:
                if pos=="CD" and upos=="PRON":
                    if featlist.get("PronType")!="Rcp":
                        print("WARN: CD/PRON combination requires PronType=Rcp ('one another') in " + docname)
                elif pos=="FW" and upos=="NOUN" and lemma=="etc.":
                    pass    # this is an exception to the usual mapping of FW
                else:
                    print("WARN: invalid POS tag " + pos + " for UPOS " + upos + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")

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
            parent_upos = upostags[parent_ids[tok_num]] if parent_ids[tok_num] != 0 else ""
            parent_feats = feats[parent_ids[tok_num]] if parent_ids[tok_num] != 0 else {}
            filename = tree.metadata['filename']
            assert parent_pos is not None,(tok_num,parent_ids[tok_num],postags,filename)
            S_TYPE_PLACEHOLDER = None
            assert parent_string is not None,(tok_num,docname,filename)
            is_parent_copular = any(funcs[x]=="cop" for x in parent_ids if parent_ids[x]==parent_id)    # if tok or any siblings attach as cop
            flag_dep_warnings(tok_num, tok, pos, upos, lemma, func, edeps,
                              parent_string, parent_lemma, parent_id, is_parent_copular,
                              children[tok_num], child_funcs[tok_num], S_TYPE_PLACEHOLDER, docname,
                              prev_tok, prev_pos, prev_upos, prev_func, prev_parent_lemma, sent_positions[tok_num],
                              parent_func, parent_pos, parent_upos, filename)
            flag_feats_warnings(tok_num, tok, pos, upos, lemma, featlist, misclist, docname)

            if func!='goeswith':
                if (prev_tok.lower(),lemma) in {("one","another"),("each","other")}:    # note that "each" is DET, not PRON
                    # check for PronType=Rcp
                    flag_pronoun_warnings(tok_num, form, prev_pos, upos, lemma, prev_feats, prev_misc, prev_tok, docname)
                elif upos == "PRON" or (upos == "DET" and misclist.get("ExtPos")!="PRON") or upos == "ADV" and lemma in ADV_ENTRIES:  # ExtPos exception for "each other"
                    if lemma == "however" and "advcl:relcl" not in child_funcs[tok_num] and not (
                            func == "advmod" and parent_upos in ("ADJ", "ADV") and not is_parent_copular
                        ):  # don't assign PronType to discourse connective use of "however"
                        if pos == "WRB":
                            print(f"WARN: should however/{pos} be tagged RB? in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
                    elif lemma == "however" and pos == "RB":
                        print(f"WARN: should however/{pos} be tagged WRB? in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
                    else:
                        # Pass FORM to detect abbreviations, etc.
                        _misclist = dict(misclist)
                        if lemma in ("all","that") and _misclist.get("ExtPos")=="ADV":  # "all of" (quantity), "that is"
                            del _misclist["ExtPos"] # prevent complaint about ExtPos=ADV
                        flag_pronoun_warnings(tok_num, form, pos, upos, lemma, featlist, _misclist, prev_tok, docname)
                elif lemma in PRON_LEMMAS:
                    if not ((lemma=="one" and upos in ("NOUN","NUM"))
                            or (lemma=="I" and upos=="NUM") # Roman numeral
                            or (lemma=="he" and upos=="INTJ") # laughter
                            or upos=="DET"):
                        print("WARN: invalid pronoun UPOS tag " + upos + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
                        # This warns about a few that are arguably correct, e.g. "oh my/INTJ", "I/PROPN - 24"
                elif upos == "NUM":
                    if "NumForm" not in featlist or "NumType" not in featlist:
                        print("WARN: NUM should have NumForm and NumType in " + docname + " @ line " + str(i) + " (token: " + tok + ")")

            extpos_funcs: dict[str,str] = {
                "ADP": "case",
                "SCONJ": "mark",
                "ADV": "advmod",
                "CCONJ": "cc",
                "PRON": "obj iobj obl nmod nmod:poss"
            }

            mwe_pairs: dict[tuple[str,str],str] = {("accord", "to"): 'ADP', ("all","but"): 'ADV',
                ("as","for"): 'ADP SCONJ', ("as","if"): 'SCONJ',
                ("as","well"): 'ADV CCONJ', ("as","as"): 'CCONJ', ("as","in"): 'ADP SCONJ',
                ("all","of"): 'ADV', ("as","oppose"): 'ADP SCONJ', ("as","to"): 'ADP SCONJ',
                ("at","least"): 'ADV', ("because","of"): 'ADP', ("due","to"): 'ADP SCONJ',
                #("had","better"): 'AUX', ("'d","better"): 'AUX',
                ("how","come"): 'ADV', ("in","between"): 'ADP ADV', ("per", "se"): 'ADV',
                ("in","case"): 'ADP SCONJ ADV', ("in","of"): 'ADP', ("in","order"): 'SCONJ', ("in","that"): 'SCONJ',
                ("instead","of"): 'ADP SCONJ', ("kind","of"): 'ADV', ("less","than"): 'ADV', ("let","alone"): 'CCONJ',
                ("more","than"): 'ADV', ("not","to"): 'CCONJ', ("not","mention"): 'CCONJ',
                ("of","course"): 'ADV', ("prior","to"): 'ADP SCONJ', ("rather","than"): 'CCONJ ADP SCONJ',
                ("so","as"): 'SCONJ', ("so", "to"): 'SCONJ', ("sort", "of"): 'ADV', ("so", "that"): 'SCONJ',
                ("such","as"): 'ADP SCONJ', ("that","be"): 'ADV', ("up","to"): 'ADV',
                #("depend","on"): 'ADP SCONJ', 
                #("out","of"): 'ADP', ("off","of"): 'ADP', 
                #("long","than"), 
                ("on","board"): 'ADP',
                ("as","of"): 'ADP',
                # ("depend","upon"),
                #("just","about"),("vice","versa"),("as","such"),("next","to"),("close","to"),
                ("one","another"): 'PRON',
                #("de","facto"),
                ("each","other"): 'PRON', ("as","many"): 'ADV'}    # TODO: only tested for EWT

            # Ad hoc listing of triple mwe parts - All in all, in order for, whether or not
            mwe_pairs.update({("all","in"): 'ADV', ("all","all"): 'ADV', ("in","for"): 'SCONJ',
                                ("whether","or"): 'SCONJ', ("whether","not"): 'SCONJ'})

            if func == "fixed":
                if (parent_lemma.lower(), lemma.lower()) not in mwe_pairs:
                    print("WARN: unlisted fixed expression" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
            elif "fixed" in child_funcs[tok_num]:
                fixedChild = children[tok_num][child_funcs[tok_num].index("fixed")]
                fixedChild = {"a": "of", "is": "be", "opposed": "oppose", "t": "to"}.get(fixedChild, fixedChild)
                expectedExtPos = mwe_pairs.get((lemma.lower(), fixedChild.lower()))
                if not expectedExtPos:
                    print(f"WARN: fixed expression missing entry: {(lemma.lower(), fixedChild.lower())}" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
                elif "ExtPos" not in misclist:
                    print("WARN: fixed head missing ExtPos" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
                elif (extpos := misclist["ExtPos"]) not in expectedExtPos:
                    print(f"WARN: fixed head ExtPos={extpos} but one of {expectedExtPos} expected" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
                elif func!='conj' and func not in extpos_funcs[extpos]:
                    if extpos=="SCONJ" and func=='ccomp' and misclist["Promoted"]=="Yes":
                        pass
                    else:
                        print(f"WARN: fixed head ExtPos={extpos} in unexpected function {func}" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")

            if func.endswith(':relcl'):
                # Check PronType=Rel for free relative headed by the WDT/WP/WRB
                # (won't catch cases where the relativizer is a dependent in a larger relative phrase)
                if upos=="PRON" or (upos=="ADV" and (xpos=="WRB" or (xpos=="GW" and "PronType" in featlist))):
                    if featlist["PronType"]=="Int":
                        print("WARN: Looks like a WH word as internal root of relative clause, should be PronType=Rel?" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
                if parent_upos=="PRON" or (parent_upos=="ADV" and (parent_pos=="WRB" or (parent_pos=="GW" and "PronType" in parent_feats))):
                    if parent_feats["PronType"]=="Int":
                        print("WARN: Looks like a WH word-headed free relative, should be PronType=Rel" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")

            if func!='goeswith' and featlist.get("PronType")=="Rel" and edeps is not None:
                if len(edeps)!=1 or edeps[0][0]!="ref":
                    if "acl:relcl" not in child_funcs[tok_num] and "advcl:relcl" not in child_funcs[tok_num]: # not free relative
                        if tok_num>1 and docname!="weblog-blogspot.com_tacitusproject_20040712123425_ENG_20040712_123425-0032":   # sentence fragment may begin with "Which"
                            print("WARN: PronType=Rel should have `ref` as its sole enhanced dependency" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")
                elif not {"acl:relcl","advcl:relcl"} & set(child_funcs[edeps[0][1]]):
                    # the ref antecedent doesn't head the RC
                    print("WARN: `ref` antecedent lacks :relcl dependent" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")

            if upos!="PROPN" and "flat" in child_funcs[tok_num] and "Foreign" not in featlist:
                # non-PROPN-headed flat structure
                if "FlatType" not in misclist:
                    print("WARN: non-PROPN non-Foreign flat expression lacks FlatType" + " in " + docname + " @ line " + str(i) + " (token: " + tok + ")")

            """
            Extraposition Construction

            - Check for anomalous csubj: post-head, head is not a root ADJ or VERB, head has no expl dependent
            (and a couple of exceptions: "a real pleasure" etc.)
            (https://github.com/UniversalDependencies/UD_English-EWT/issues/524)
            """
            if not (func in ('root','parataxis') and upos in ('ADJ','VERB')):
                if 'csubj' in child_funcs[tok_num] and 'expl' not in child_funcs[tok_num]:
                    for j in parent_ids:
                        if parent_ids[j]==tok_num and j>tok_num and funcs[j]=='csubj':
                            if not (func=='root' and tok in ('pleasure','joy','move')):
                                print("WARN: suspicious post-head `csubj` in " + docname + " @ line " + str(i) + " (token: " + tok + ")")


            if ':pass' in func:
                passive_verbs.add(parent_id)

            prev_pos = pos
            prev_upos = upos
            prev_tok = tok
            prev_func = func
            prev_parent_lemma = parent_lemma
            prev_feats = featlist
            prev_misc = misclist

        """
        Passive Construction

        A main verb is necessarily passive if any of its dependents are *:pass.
        In such cases,
            - the main verb should have the feature Voice=Pass
            - the xpos should be VBN
            - all subjects and (only) the last aux should probably be :pass varieties
            - there should probably not be a cop

        Additionally,
            - if there is an obl:agent (by-phrase), it must be a "by"-PP attaching to a passive verb
              (with Voice=Pass)
            - if a VBN has no *:pass, obl:agent, aux, or cop dependents, it should be Voice=Pass
        
        Discussion: https://github.com/UniversalDependencies/UD_English-EWT/issues/290
        """
        for v in passive_verbs:
            if feats[v].get("Voice") != "Pass":
                print("WARN: Passive verb with lemma '" + lemmas[v] + "' should have Voice=Pass in " + docname)
            if postags[v] not in ["VBN", "MD"]:
                print("WARN: Passive verb with lemma '" + lemmas[v] + "' should be VBN in " + docname)
            dependents = {j: funcs[j] for j,i in parent_ids.items() if i==v}
            aux_dependents = sorted([(j,f) for j,f in dependents.items() if f.startswith('aux')])
            if aux_dependents and (not all(f=='aux' for j,f in aux_dependents[:-1]) or aux_dependents[-1][1]!='aux:pass'):
                if docname!="answers-20111106035951AADq0Qg_ans-0012":    # sentence has missing 'be' aux:pass
                    print("WARN: Passive verb with lemma '" + lemmas[v] + "' has suspicious aux(:pass) dependents (only the last should be aux:pass) in " + docname)
            subj_dependents = {f for f in dependents.values() if 'subj' in f}
            if not subj_dependents < {'nsubj:pass','csubj:pass','nsubj:outer','csubj:outer'}:
                print("WARN: Passive verb with lemma '" + lemmas[v] + "' has subject dependents " + repr(sorted(subj_dependents)).replace('[','{').replace(']','}') + " in " + docname)
            if 'cop' in dependents.values():
                if 'aux:pass' in dependents.values() and any(':outer' in d for d in dependents.values()):
                    pass
                else:
                    print("WARN: Passive verb with lemma '" + lemmas[v] + "' has cop dependent in " + docname)
        for i,f in funcs.items():
            if f=='obl:agent':
                if (feats[parent_ids[i]] or {}).get("Voice") != "Pass":
                    print("WARN: Voice=Pass missing from verb that heads obl:agent (lemmas: " + lemmas[i] + " <- " + lemmas[parent_ids[i]] + ") in " + docname)
                if not any(k==i and lemmas[j]=='by' and funcs[j]=='case' for j,k in parent_ids.items()):
                    print("WARN: obl:agent without 'by' (lemmas: " + lemmas[i] + " <- " + lemmas[parent_ids[i]] + ") in " + docname)
        # If a VBN has no *:pass, obl:agent, or aux dependents, it should be Voice=Pass
        for v,p in postags.items():
            if p=='VBN':
                isVoicePass = (feats[v] or {}).get("Voice") == "Pass"
                if funcs[v] in ['aux', 'aux:pass', 'cop']:
                    if isVoicePass:
                        print("WARN: Voice=Pass prohibited on verbs functioning as auxiliaries in " + docname)
                elif lemmas[v]=='suppose' and not isVoicePass:  # (be) supposed (to)
                    print("WARN: 'supposed (to)' missing Voice=Pass? " + docname)
                else:
                    dependents = {j: funcs[j] for j,i in parent_ids.items() if i==v}
                    pass_marking_dependents = {f for f in dependents.values() if ':pass' in f or f=='obl:agent'}
                    other_dependents = {f for f in dependents.values() if f=='aux'}
                    
                    if not isVoicePass and not pass_marking_dependents and not other_dependents:
                        if (funcs[v]=='conj' and postags[parent_ids[v]]=='VBN'):    # "have" can scope over coordination
                            pass
                        elif lemmas[v]=='get':  # "I (have) got to leave"
                            pass
                        elif docname in ["reviews-122564-0003", "answers-20111108104724AAuBUR7_ans-0001"]:
                            pass    # hardcode two exceptions interpreted as perfect
                        else:
                            print("WARN: Voice=Pass missing from VBN verb with no aux dependent in " + docname)
                    elif isVoicePass and not pass_marking_dependents and other_dependents:
                        print("WARN: VBN with aux but no aux:pass dependent incompatible with Voice=Pass in " + docname)

NNS_PTAN_LEMMAS = ["aesthetics", "arrears", "auspices", "barracks", "billiards", "clothes", "confines", "contents",
                   "dynamics", "earnings", "eatables", "economics", "electronics", "energetics", "environs", "ergonomics",
                   "eyeglasses", "feces", "finances", "fives", "furnishings", "genetics", "genitals", "geopolitics", "glasses",
                   "goods", "grounds", "hackles", "headquarters", "jeans", "manners", "means", "memoirs", "news",
                   "orthodontics", "panties", "pants", "politics", "proceedings", "regards", "remains", "respects",
                   "savings", "scissors", "specifics", "statistics", "sunglasses", "supplies", "surroundings",
                   "tenterhooks", "thanks", "troops", "trousers", "wares", "whereabouts",
                   "twenties", "thirties", "forties", "fifties", "sixties", "seventies", "eighties", "nineties", "mid-nineties"]

# some of these can also be singular (NN), in which case not Ptan: politics, economics
# "respects" only Ptan in "pay one's respects" (cf. "thanks")
# "glasses" is Ptan in meaning of eyeglasses
# not Ptan: biceps, triceps

NNPS_PTAN_LEMMAS = ["Netherlands", "Analytics", "Olympics", "Commons", "Paralympics", "Vans", "Andes", "Philippines",
                    "Maldives"]

SING_AND_PLUR_S_LEMMAS = ["series", "species"]

def flag_dep_warnings(id, tok, pos, upos, lemma, func, edeps, parent, parent_lemma, parent_id, is_parent_copular,
                      children: List[str], child_funcs: List[str], s_type,
                      docname, prev_tok, prev_pos, prev_upos, prev_func, prev_parent_lemma, sent_position,
                      parent_func, parent_pos, parent_upos, filename):
    # Shorthand for printing errors
    inname = " in " + docname + " @ token " + str(id) + " (" + parent + " -> " + tok + ") " + filename

    if func == "amod" and pos in ["VBD"]:
        print("WARN: finite past verb labeled amod " + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func in ["amod", "det"] and parent_lemma == "one" and parent_pos == "CD":
        print("WARN: 'one' with " + func + " dependent should be NN/NOUN not CD/NUM in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func in ["det", "det:predet"] and lemma in ["this", "that"] and not (pos == "DT" and upos == "DET"):
        print("WARN: '" + tok + "' attaching as " + func + " should be DT/DET not " + pos + "/" + upos + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")
    elif func not in ["det", "det:predet"] and lemma in ["that", "which"] and pos == "WDT" and upos != "PRON":
        print("WARN: '" + tok + "' attaching as " + func + " should be WDT/PRON not " + pos + "/" + upos + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")
    elif func not in ["det", "det:predet"] and lemma in ["this", "that"] and pos not in ["IN", "RB", "WDT"] and not (pos == "DT" and upos == "PRON"):
        print("WARN: '" + tok + "' attaching as " + func + " should be DT/PRON not " + pos + "/" + upos + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func == "amod" and parent_upos not in ["NOUN", "PRON", "PROPN", "NUM", "SYM", "ADJ"] and parent_pos != "ADD":    # see issue #438
        if parent_upos == "ADV" and parent_lemma in ["somewhere","anywhere","someplace","somehow","sometime"]:
            pass    # postpositive amod e.g. "somewhere rural"
        elif parent_upos == "DET" and parent_lemma in ["all","both"]:
            pass    # postpositive amod e.g. "all due tomorrow"
        elif parent_upos == "VERB" and parent_pos in ["VBN","VBG"] and parent_lemma in ["bear","train","range","look"]:
            pass    # compounds - for now special-case things like "French-born" and "wide-ranging"
        else:
            print("WARN: " + parent_upos + " shouldn't have amod dependent in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func.split(':')[0] == "acl" and parent_upos not in ["NOUN", "PRON", "PROPN", "NUM", "SYM"]:  # see issue #439 for plain acl
        if func == "acl" and parent_lemma in ["much", "more", "enough"]:
            pass    # e.g. "much to do"
        elif func == "acl:relcl" and parent_upos == "ADJ":
            pass    # coerced to nominal, e.g. "the least we can do"
        elif func == "acl:relcl" and parent_upos == "DET" and (parent_lemma in ["all", "some", "any"]) or parent.lower()=="those":
            pass    # e.g. "those who like cheese"
        elif docname == "newsgroup-groups.google.com_alt.animals_0084bdc731bfc8d8_ENG_20040905_212000-0001":
            pass    # special case: "What We've Lost/VERB", published/acl by Little Brown
        elif docname == "reviews-093655-0007":
            pass    # special case: "the last/ADJ to get/acl my food"
        else:
            print("WARN: " + parent_upos + " shouldn't have " + func + " dependent in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func == "appos" and parent_upos not in ["NOUN", "PRON", "PROPN", "NUM", "SYM", "ADJ", "DET"] and parent_pos != "ADD":    # see issue #437 for VERB heads
        if parent_func == "root":
            pass    # Exception: key-value appos
        elif parent_upos == "ADV" and parent_lemma == "here":
            pass    # "here (California)"
        else:
            print("WARN: " + parent_upos + " shouldn't have appos dependent in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func in ['fixed','goeswith','flat', 'conj'] and id < parent_id:
        print("WARN: back-pointing func " + func + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func == "flat" and parent_upos == "PROPN" and upos == "NOUN":
        print("WARN: PROPN-[flat]->NOUN - should be compound? " + func + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func in ['cc:preconj','cc','nmod:poss'] and id > parent_id:
        if tok not in ["mia"]:
            print("WARN: forward-pointing func " + func + " in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func == "aux:pass" and lemma != "be" and lemma != "get":
        print("WARN: aux:pass must be 'be' or 'get'" + inname)

    if lemma == "get" and upos == "AUX" and func != "aux:pass":
        print("WARN: get/AUX should be aux:pass" + inname)

    if lemma == "'s" and pos != "POS":
        print("WARN: possessive 's must be tagged POS" + inname)

    if func not in ["case","reparandum","goeswith"] and pos == "POS":
        print("WARN: tag POS must have function case" + inname)

    if pos in ["VBG","VBN","VBD"] and lemma.lower() == tok.lower():
        t = tok.lower()
        if pos == "VBN" and t in ["become","come","overcome","run","outrun","overrun"]:
            pass
        elif pos in ["VBN", "VBD"] and t in ["put","shut","cut","pre-cut","undercut",
                                            "cost","cast","broadcast","forecast",
                                            "let","set","upset","shed","spread",
                                            "hurt","burst","bust",
                                            "beat","read","re-read",
                                            "bit","fit","hit","knit","slit","split","bid","outbid",
                                            "l-","g-"]:  # disfluencies
                                            #,"know","notice","reach","raise",]:
            pass
        else:
            print("WARN: tag "+pos+" should have lemma distinct from word form" + inname)

    if pos == "NNPS" and tok == lemma and tok.endswith("s") and func != "goeswith":
        if tok not in ["Netherlands","Analytics","Olympics","Commons","Paralympics","Vans",
                       "Andes","Forties","Philippines"]:
            print("WARN: tag "+pos+" should have lemma distinct from word form" + inname)

    if pos == "NNS" and tok.lower() == lemma.lower() and lemma.endswith("s") and func != "goeswith":
        if lemma not in NNS_PTAN_LEMMAS + NNPS_PTAN_LEMMAS + SING_AND_PLUR_S_LEMMAS:
            if re.search(r"[0-9]+'?s$",lemma) is None:  # 1920s, 80s
                print("WARN: tag "+pos+" should have lemma distinct from word form" + inname)
                NNS_warnings[lemma] += 1

    if pos == "IN" and func=="compound:prt":
        print("WARN: function " + func + " should have pos RP, not IN" + inname)

    if pos == "CC" and func not in ["cc","cc:preconj","conj","reparandum","root","dep"] and not (parent_lemma=="whether" and func=="fixed"):
        if not ("languages" in inname and tok == "and"):  # metalinguistic discussion in whow_languages
            print("WARN: pos " + pos + " should normally have function cc or cc:preconj, not " + func + inname)

    if pos == "RP" and func not in ["compound:prt","conj"] or pos != "RP" and func=="compound:prt":
        print("WARN: pos " + pos + " should not normally have function " + func + inname)

    if pos != "CC" and func in ["cc","cc:preconj"]:
        if func == "cc:preconj" or lemma not in ["/","rather","as","et","+","let","-"]:
            print("WARN: function " + func + " should normally have pos CC, not " + pos + inname)

    if func == "cc:preconj" and lemma not in ["both", "either", "neither"]:
        print("WARN: cc:preconj should be restricted to both/either/neither, not " + pos + inname)

    if pos == "VBG" and "very" in children:
        print("WARN: pos " + pos + " should not normally have child 'very'" + inname)

    if pos == "UH" and func=="advmod":
        print("WARN: pos " + pos + " should not normally have function 'advmod'" + inname)

    if func == "mark" and lemma in ["when", "how", "where", "why", "whenever", "wherever", "however"]:
        print("WARN: WH adverbs should attach as advmod, not mark" + inname)

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

    if pos == "VBZ" and lemma == "be" and func in ["aux", "aux:pass"] and parent_lemma == "get" and parent_pos == "VBN":
        print("WARN: \"'s got\" clitic lemma should be \"have\" not \"be\"? " + inname)

    if upos=="VERB" and func.split(':')[0] in ["obj","nsubj","iobj","nmod","obl","expl"]:
        if not (pos == "VBG" and tok == "following") and not (pos == "VBN" and tok == "attached"):  # Exception: nominalized "the following/attached"
            print("WARN: verb should not have nominal argument structure function " + func + inname)

    if pos.startswith("NN") and not pos.startswith("NNP") and func=="amod":
        print("WARN: tag "+ pos + " should not be " + func + inname)

    be_funcs = ["root", "cop", "aux", "aux:pass", "csubj", "ccomp", "xcomp",    # TODO: if Promoted=Yes is implemented, some of these funcs should check for it
                "acl", "acl:relcl", "advcl", "advcl:relcl", "conj", "parataxis", "reparandum"]
    if lemma == "be" and func not in be_funcs:
        if parent_lemma == "that" and func == "fixed":  # Exception for 'that is' as mwe
            pass
        elif parent_lemma == "all" and func == "compound":  # Exception for 'be all, end all'
            pass
        elif func == "appos" and parent_func == "root": # Exception for key-value pair appos
            pass
        else:
            print("WARN: invalid dependency of lemma 'be' > " + func + inname)

    if parent_lemma in ["tell","show","give","pay","charge","bill","teach","owe","text","write"] and \
            tok in ["him","her","me","us","you"] and func=="obj":
        print("WARN: person object of ditransitive expected to be iobj, not obj" + inname)
    
    # verbs checked for obj to be converted to iobj:
    # cause|pardon|tell|ask|show|teach|email|cc|bcc|believe|trust|ask|allow|permit|pay|explain|convince|persuade|urge|advise|inform|notify|warn|command|instruct|remind|promise|assure|reassure|guarantee
    if "obj" in child_funcs and {"ccomp", "xcomp"} & set(child_funcs) and lemma in ["tell", "ask", "show",
        "allow", "permit", "cause", "pardon",
        "pay",
        "thank", # thank God that...
        "believe", "trust",
        "explain",  # explain me that... (not quite grammatical)
        "convince", "persuade", "teach",
        "urge", "advise", "inform", "notify", "warn", "command", "instruct", "remind", 
        "email", "cc", "bcc",
        "promise", "assure", "reassure", "guarantee"]:
        # Note that the test for iobj is that the verb licenses iobj+obj or iobj+ccomp. 
        # So e.g. "encourage" is ruled out, while "allow" and "permit" are included because of "allow you an exception" etc.
        # Idiom exceptions: have+idea(obj) that..., give a damn(obj) that..., make up + mind(obj) that...
        # TODO: see them as they are?
        if lemma in ["believe","show"]:
            print("WARN: verb expects iobj, not obj, with ccomp/xcomp (" + lemma + " -- OK if raising-to-object)" + inname)
        else:
            print("WARN: verb expects iobj, not obj, with ccomp/xcomp (" + lemma + ")" + inname)

    if func == "aux" and lemma.lower() != "be" and lemma.lower() != "have" and lemma.lower() !="do" and pos!="MD" and pos!="TO":
        print("WARN: aux must be modal, 'be,' 'have,' or 'do'" + inname)

    if func == "xcomp" and pos in ["VBP","VBZ","VBD"]:
        if parent_lemma not in ["=","seem"]:
            print("WARN: xcomp verb should be non-finite, not tag " + pos + inname)

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
        if "nsubj:outer" in child_funcs:
            pass    # he said the reason was because...
        # to-infinitivals can be ccomp in certain circumstances
        elif "advmod" in child_funcs and {"how","where"} & set(map(str.lower, children)) and "to" in children:
            pass    # "know how to..." or "tell s.o. how to..."
        elif {"obj","obl"} & set(child_funcs) and {"what","who"} & set(map(str.lower, children)) and "to" in children:
            pass    # what to do, who to talk to
        elif parent_upos=="ADJ" and "to" in children:   # complement of adjective
            pass
        elif parent_lemma in {"love","leave","make","feel","find","mean","need","say"} and "to" in children:
            # some verbs license to-infinitival ccomps (sometimes due to it-extraposition)
            pass    # I would love to join; I leave it to you [to figure it out]; makes it impossible [to single out]; felt it necessary [to...]
        elif "newsgroup-groups.google.com_magicworld_04c89d43ff4fd6ea_ENG_20050104_152000-0021 @ token 8":
            pass    # it-extraposition: have it in you to...
        elif "answers-20111108103354AAQzdFB_ans-0004 @ token 26" in inname:
            pass    # sentence is missing a word
        #elif not ((lemma == "lie" and "once" in children) or (lemma=="find" and ("see" in children or "associate" in children))):  # Exceptions
        else:
            print("WARN: ccomp should not have child mark" + inname)
            # TODO: should all be fixed for EWT except "answers-20111108092321AAK0Eqp_ans-0025 @ token 6" (awaiting guideline on tough-constructions)

    if func == "acl:relcl" and pos in ["VB"] and "to" in children and "cop" not in child_funcs and "aux" not in child_funcs:
        print("WARN: infinitive with tag " + pos + " should be acl not acl:relcl" + inname)

    if func == "acl:relcl" and parent_upos == "ADV":
        print("WARN: dependent of adverb should be advcl:relcl not acl:relcl" + inname)

    # ADV in nominal function of clause is probably a bug
    if upos == "ADV" and func.startswith(('nsubj','obj','iobj')):
        print("WARN: ADV with core nominal function "+ func + inname)
    elif upos=="ADV" and func.startswith('obl') and not (set(child_funcs) & {'case','det'}):
        print("WARN: ADV with function "+ func +" and no case or det dependent" + inname)

    if upos == "ADV" and func.split(':')[0]=='amod':
        print("WARN: ADV should not be amod" + inname)

    if (upos == "ADV" or pos.startswith("RB")) and lemma == "at":
        print("WARN: at/ADV/RB is forbidden" + inname)

    if ("acl:relcl" in child_funcs or "advcl:relcl" in child_funcs) and edeps is not None:  # relativized element
        # should (in most cases) have an enhanced dependency out of the relative clause
        if len(edeps)<=1 or not any(rel.startswith(('nsubj','csubj','obj','obl','nmod','advmod','ccomp','xcomp')) and isinstance(h,int) and h>id for (rel,h) in edeps):
            print("WARN: relativized word should have enhanced dependency within the relative clause" + inname)

    if pos in ["VBG"] and "det" in child_funcs:
        # Exceptions for phrasal compound in GUM_reddit_card and nominalization in GUM_academic_exposure
        if tok != "prioritizing" and tok != "following":
            print(str(id) + docname)
            print("WARN: tag "+pos+" should not have a determinder 'det'" + inname)

    if parent_lemma in ["let", "help"] and func=="ccomp":
        print(f"WARN: verb '{parent_lemma}' should take xcomp clausal object, not ccomp" + inname)

    if pos == "MD" and lemma not in ["can","must","will","shall","would","could","may","might","ought","should","need","dare"] and func != "goeswith":
        print("WARN: lemma '"+lemma+"' is not a known modal verb for tag MD" + inname)

    if lemma == "like" and pos == "UH" and func not in ["discourse","conj","reparandum"]:
        print("WARN: lemma '"+lemma+"' with tag UH should have deprel discourse, not "+ func + inname)

    if func in ["iobj","obj"] and parent_lemma in ["become","remain","stay"]:
        print("WARN: verb '"+parent_lemma+"' should take xcomp not "+func+" argument" + inname)

    if ":tmod" in func or ":npmod" in func:
        # https://github.com/UniversalDependencies/docs/issues/1028
        print("WARN: function " + func +  " is deprecated, use :unmarked instead" + inname)

    if func in ["nmod:unmarked","obl:unmarked"] and "case" in child_funcs:
        print("WARN: function " + func +  " should not have 'case' dependents" + inname)

    if func in ["aux:pass","nsubj:pass"] and parent_pos not in ["VBN"]:
        if not (("stardust" in docname and parent_lemma == "would") or parent_lemma == "Rated"):
            print("WARN: function " + func + " should not be the child of pos " + parent_pos + inname)

    if func == "obl:agent" and (parent_pos not in ["VBN"] or "by" not in map(str.lower, children)):
        print("WARN: function " + func +  " must be child of VBN with a 'by' dependent" + parent_pos + inname)

    if child_funcs.count("obl:agent") > 1:
        print("WARN: a token may have at most one obl:agent dependent" + inname)

    if "obl:agent" in child_funcs and ("nsubj" in child_funcs or "csubj" in child_funcs) and not "nsubj:pass" in child_funcs:
        print("WARN: a token cannot have both a *subj relation and obl:agent" + inname)

    if pos in ["VBD","VBD","VBP"] and "aux" in child_funcs and "nsubj:outer" not in child_funcs:
        print(str(id) + docname)
        print("WARN: tag "+pos+" should not have auxiliaries 'aux'" + inname)

    if lemma == "not" and func not in ["advmod","root","ccomp","amod","parataxis","reparandum","advcl","conj","orphan","fixed"]:
        print("WARN: deprel "+func+" should not be used with lemma '"+lemma+"'" + inname)

    if func == "xcomp" and parent_lemma in ["see","hear","notice"]:  # find
        print("WARN: deprel "+func+" should not be used with perception verb lemma '"+parent_lemma+"' (should this be nsubj+ccomp?)" + inname)

    if lemma == "have" and "ccomp" in child_funcs and ("obj" not in child_funcs or not set(children) & {"idea","clue"}) and "expl" not in child_funcs:
        # exceptional idioms: 'have no idea/clue', 'rumor has it'
        print("WARN: 'have' token has suspicious ccomp dependent (should it be xcomp?)" + inname)

    if "obj" in child_funcs and "ccomp" in child_funcs:
        print("WARN: token has both obj and ccomp children" + inname)

    if child_funcs.count("ccomp") + child_funcs.count("xcomp") > 1 and "expl" not in child_funcs:
        print("WARN: token has multiple (c|x)comp dependents (usually an error if not extraposition)" + inname)

    if func == "acl" and (pos.endswith("G") or pos.endswith("N")) and parent_id == id + 1:  # premodifier V.G/N should be amod not acl
        print("WARN: back-pointing " + func + " for adjacent premodifier (should be amod?) in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func == "advcl" and upos=="VERB" and (pos.endswith("G") or pos.endswith("N")) and parent_upos in ["NUM","SYM","NOUN","PRON","PROPN","DET"] and not is_parent_copular and parent_func!="root":
        print("WARN: non-predicate non-root nominal should not have advcl dependent (should be acl?) in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    if func.endswith("unmarked") and pos.startswith("RB"):
        print("WARN: adverbs should not be unmarked" + inname)

    if func == "case" and lemma in ["back", "down", "over", "out", "up"] and parent_lemma in ["here","there"] and id+1==parent_id:
        # adjacency check because "out of there" is OK
        print("WARN: '"+lemma+" "+parent_lemma+"' should probably be advmod not case" + inname)

    if func == "case" and upos == "SCONJ" and "fixed" not in child_funcs:
        print("WARN: SCONJ/case combination is invalid in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")
    
    # indefinites of time and place
    if lemma in ["anytime", "anyplace", "anywhere", "sometime", "someplace", "somewhere", "nowhere"]:
        if (pos != "RB" or upos != "ADV"):
            # https://github.com/UniversalDependencies/UD_English-EWT/issues/132
            print(f"WARN: indefinite time or place pro-form tagging {upos}/{pos} is invalid, should be ADV/RB in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")
        if func.startswith("obl:"):
            print(f"WARN: indefinite time or place pro-form tagging {upos}/{pos} is invalid, should be ADV/RB in " + docname + " @ token " + str(id) + " (" + tok + " <- " + parent + ")")

    """
    Existential construction

    X.xpos=EX <=> X.deprel=expl & X.lemma=there
    X.xpos=EX => X.upos=PRON
    X.parent.lemma=be => X.parent.upos=VERB
    """
    if func!="reparandum":
        _ex_tag = (pos=="EX")
        _expl_there = (func=="expl" and lemma=="there")
        if _ex_tag != _expl_there or (_ex_tag and upos!="PRON"):
            print("WARN: 'there' with " + pos + " and " + upos + inname)
        if lemma=="there" and not _ex_tag and 'nsubj' in func:
            print("WARN: subject 'there' not tagged as EX/expl" + inname)
        if _ex_tag and parent_lemma=="be" and parent_upos!="VERB":
            print(f"WARN: existential BE should be VERB, is {parent_upos}" + inname)
        # TODO: check "there seems to be/VERB" etc.

    """
    (Pre)determiner 'what'

    X[lemma=what,xpos=WDT] <=> X[lemma=what,deprel=det|det:predet]
    """
    if lemma=="what" and ((pos=="WDT") != (func in ["det", "det:predet"])):
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
                          ("no","RB","matter","RB")]

    for w1, pos1, w2, pos2 in suspicious_pos_tok:
        if w1 == prev_tok.lower() or w1 == "*":
            if pos1 == prev_pos or pos1 == "*":
                if w2 == lemma or w2 == "*":
                    if pos2 == pos or pos2 == "*":
                        print("WARN: suspicious n-gram " + prev_tok + "/" + prev_pos+" " + tok + "/" + pos + inname)

    def check_bigram_fixed(w1, w2, parent_lemma, w2func, pos1, upos1, pos2, upos2, inname, outerdeprel=None):
        """Verify a 2-word fixed expression has the correct structure and tags"""

        try:
            assert w2func=="fixed"
            assert w1==parent_lemma
            match (w1,w2):
                case ("one", "another"):
                    assert (pos1, pos2)==("CD", "DT") and (upos1, upos2)==("PRON", "DET")
                case ("each", "other"):
                    assert (pos1, pos2)==("DT", "JJ") and (upos1, upos2)==("DET", "ADJ")
                case ("kind", "of"):
                    assert (pos1, pos2)==("NN", "IN") and (upos1, upos2)==("NOUN", "ADP")
                case ("sort", "of"):
                    assert (pos1, pos2)==("NN", "IN") and (upos1, upos2)==("NOUN", "ADP")
                case ("at", "least"):
                    assert (pos1, pos2)==("IN", "JJS") and (upos1, upos2)==("ADP", "ADJ")
                case _:
                    assert False,(w1,w2)
        except AssertionError:
            print("WARN: structure of '{w1} {w2}' should be fixed({w1}/{pos1}/{upos2}, {w2}/{pos2}/{upos2})" + inname)

        try:
            if (w1,w2) in {("kind", "of"), ("sort", "of"), ("at", "least")}:
                assert outerdeprel=="advmod"
        except AssertionError:
            print("WARN: fixed expr '{w1} {w2}' should attach as advmod not {outerdeprel}" + inname)


    # UPOS bigrams
    if prev_tok.lower()=="no" and lemma=="one" and upos!="PRON":
        print("WARN: UPOS should be one/PRON in 'no one': " + upos + inname)
    elif prev_tok.lower()=="one" and lemma=="another":
        check_bigram_fixed("one", "another", parent_lemma, func, prev_pos, prev_upos, pos, upos, inname)
    elif prev_tok.lower()=="each" and lemma=="other":
        check_bigram_fixed("each", "other", parent_lemma, func, prev_pos, prev_upos, pos, upos, inname)
    elif prev_tok.lower() in ("kind", "sort") and lemma=="of" and func=="fixed":    # hedge usage
        check_bigram_fixed(prev_tok.lower(), "of", parent_lemma, func, prev_pos, prev_upos, pos, upos, inname, prev_func)
    elif prev_tok.lower()=="at" and lemma=="least" and func=="fixed":    # non-quantity usage
        check_bigram_fixed("at", "least", parent_lemma, func, prev_pos, prev_upos, pos, upos, inname, prev_func)
    elif prev_tok.lower()=="a" and lemma=="couple":
        try:
            assert prev_func=="det"
            assert prev_parent_lemma=="couple"
            assert func not in ('nummod', 'compound', 'fixed')
            if func=="nmod":
                assert "case" in child_funcs
        except AssertionError:
            print("WARN: structure of 'a couple NOUN' should be det(couple, a), nmod:unmarked(NOUN, couple)" + inname)
    elif prev_tok.lower()=="and" and lemma=="/":
        try:
            assert prev_pos=="CC"
            assert prev_upos=="CCONJ"
            assert func=="cc"
            assert parent_lemma=="or"
            assert pos=="SYM"
            assert upos=="SYM"
            assert ("cc", parent_id) in edeps,(parent_id,edeps)
        except AssertionError as ex:
            print("WARN: structure of 'and/or' should be conj(and/CC/CCONJ, cc(or/CC/CCONJ, '/'/SYM/SYM)) and E:cc(or, '/')" + inname)
            traceback.print_tb(ex.__traceback__, limit=1, file=sys.stdout)
    elif prev_tok.lower()=="/" and lemma=="or":
        try:
            assert prev_pos=="SYM"
            assert prev_upos=="SYM"
            assert func=="conj"
            assert parent_lemma=="and"
            assert pos=="CC"
            assert upos=="CCONJ"
            assert ("conj:slash", parent_id) in edeps,(parent_id,edeps)
            assert any(rel=="cc" for (rel,h) in edeps),(parent_id,edeps)
        except AssertionError as ex:
            print("WARN: structure of 'and/or' should be conj(and/CC/CCONJ, cc(or/CC/CCONJ, '/'/SYM/SYM)) and E:conj(and, or) and E:cc(*, or)" + inname)
            traceback.print_tb(ex.__traceback__, limit=1, file=sys.stdout)

def flag_feats_warnings(id, tok, pos, upos, lemma, feats, misc, docname):
    """
    Check compatibility of tags and features.

    @author: Reece H. Dunn (@rhdunn)
    """

    degree = feats["Degree"] if "Degree" in feats else None
    number = feats["Number"] if "Number" in feats else None
    numType = feats["NumType"] if "NumType" in feats else None
    person = feats["Person"] if "Person" in feats else None
    poss = feats["Poss"] if "Poss" in feats else None
    pronType = feats["PronType"] if "PronType" in feats else None
    tense = feats["Tense"] if "Tense" in feats else None
    verbForm = feats["VerbForm"] if "VerbForm" in feats else None

    # ADJ => (JJ <=> [Degree=Pos])
    if upos == "ADJ" and ((pos == "JJ") != (degree == "Pos")):
        # ADJ+NNP occurs in proper noun phrases per PTB guidelines
        if pos != "NNP" and pos != "AFX":   # TODO: map all AFX to X instead (#152)? if so remove the 2nd condition
            print("WARN: ADJ+JJ should correspond with Degree=Pos in " + docname + " @ token " + str(id))

    # (ADJ+JJR | ADV+RBR) <=> [Degree=Cmp]
    if (upos == "ADJ" and pos == "JJR" or upos == "ADV" and pos == "RBR") != (degree == "Cmp"):
        # ADJ+NNP occurs in proper noun phrases per PTB guidelines
        if pos != "NNP":
            print("WARN: ADJ+JJR or ADV+RBR should correspond with Degree=Cmp in " + docname + " @ token " + str(id))

    # (ADJ+JJS | ADV+RBS) <=> [Degree=Sup]
    if (upos == "ADJ" and pos == "JJS" or upos == "ADV" and pos == "RBS") != (degree == "Sup"):
        # ADJ+NNP occurs in proper noun phrases per PTB guidelines
        if pos != "NNP":
            print("WARN: ADJ+JJS or ADV+RBS should correspond with Degree=Sup in " + docname + " @ token " + str(id))

    if degree and upos not in ("ADJ", "ADV"):
        print("WARN: Degree should only apply to ADJ or ADV in " + docname + " @ token " + str(id))

    if upos == "ADJ" and not degree:
        print("WARN: ADJ should have Degree in " + docname + " @ token " + str(id))

    if number and upos not in ("NOUN", "PRON", "PROPN", "SYM", "AUX", "DET", "VERB"):
        print("WARN: Number should not apply to " + upos + " in " + docname + " @ token " + str(id))

    # NUM+CD => NUM[NumType=Card]
    if upos == "NUM" and pos == "CD" and not (numType in ["Card","Frac"]):
        # NumType=Frac applied to decimals modeled after GUM (discussed at https://github.com/UniversalDependencies/UD_English-PUD/issues/22)
        print("WARN: NUM+CD should correspond with NumType=Card or NumType=Frac in " + docname + " @ token " + str(id))

    if pos == "LS" and upos != "NUM" and re.search(r'\w', lemma):
        print("WARN: alphanumeric LS should be NUM in " + docname + " @ token " + str(id))

    # NOUN+NN <=> NOUN[Number=Sing]
    if upos == "NOUN" and ((pos == "NN") != (number == "Sing")):
        # NOUN+GW can also have an optional Number=Sing feature
        if pos != "GW":
            print("WARN: NOUN+NN should correspond with Number=Sing in " + docname + " @ token " + str(id))

    # etc. <=> NOUN+FW <=> Number=Plur; otherwise NOUN+NNS <=> NOUN[Number=Plur]
    if lemma == "etc.":
        if pos != "FW" or upos != "NOUN" or number != "Plur" or not feats.get("Abbr") == "Yes":
            print("WARN: 'etc.' should correspond with NOUN+FW, Abbr=Yes|Number=Plur in " + docname + " @ token " + str(id))
    elif upos == "NOUN" and ((pos == "NNS") + (lemma in NNS_PTAN_LEMMAS or re.search(r"[0-9]+'?s$",lemma) is not None) + (number == "Ptan")) == 2:
        print("WARN: pluralia tantum should have NNS, Number=Ptan: " + lemma + " in " + docname + " @ token " + str(id))
    elif upos == "NOUN" and ((pos == "NNS") != (number == "Plur")) and lemma not in NNS_PTAN_LEMMAS and re.search(r"[0-9]+'?s$",lemma) is None:
        print("WARN: NOUN+NNS should correspond with Number=Plur in " + docname + " @ token " + str(id))

    if (upos == "PART" and lemma == "not" or upos == "INTJ" and lemma == "no") != (feats.get("Polarity")=="Neg"):
        print("WARN: not/PART and no/INTJ should correspond with Polarity=Neg in " + docname + " @ token " + str(id))

    if (upos == "INTJ" and lemma == "yes") != (feats.get("Polarity")=="Pos"):
        print("WARN: yes/INTJ should correspond with Polarity=Pos in " + docname + " @ token " + str(id))

    # PRON+WP$ <=> PRON[Poss=Yes,PronType=Int,Rel]
    if upos == "PRON" and ((pos == "WP$") != (poss == "Yes" and pronType in ["Int","Rel"])):
        print("WARN: PRON+WP$ should correspond with Poss=Yes|PronType=Int,Rel in " + docname + " @ token " + str(id))

    # [PronType=Int,Rel] => WDT|WP|WRB
    # (upos=="X" for goeswith)
    if upos!="X" and pos not in ["WDT","WP","WRB"] and (poss is None and pronType in ["Int","Rel"]):
        print("WARN: PronType=Int,Rel and not poss implies WP|WDT|WRB in " + docname + " @ token " + str(id))
    # WDT|WP|WRB => [PronType=Dem,Int,Rel]
    # (upos=="X" for goeswith)
    elif upos!="X" and (pos in ["WDT","WP","WRB"]) and not (poss is None and pronType in ["Dem","Int","Rel"]):
        print("WARN: WP|WDT|WRB implies not poss and PronType=Dem,Int,Rel in " + docname + " @ token " + str(id))

    # PROPN+NNP <=> PROPN[Number=Sing]
    if upos == "PROPN" and ((pos == "NNP") != (number == "Sing")):
        print("WARN: PROPN+NNP should correspond with Number=Sing in " + docname + " @ token " + str(id))

    # PROPN+NNPS <=> PROPN[Number=Plur]
    if upos == "PROPN" and ((pos == "NNPS") != (number == "Plur")) and lemma not in NNPS_PTAN_LEMMAS:
        print("WARN: PROPN+NNPS should correspond with Number=Plur in " + docname + " @ token " + str(id))

    # VB feats (subjunctive, imperative, or infinitive)
    if pos == "VB" and "VerbForm" not in feats:
        print("WARN: VB should have VerbForm in " + docname + " @ token " + str(id))
    elif pos == "VB" and verbForm == "Fin" and feats["Mood"] == "Sub":
        if not all(f in feats for f in ["Number","Person","Tense"]) or tense != "Pres":
            print("WARN: VB/Mood=Sub should have Number, Person, and Tense=Pres in " + docname + " @ token " + str(id))
    elif pos == "VB" and any(f in feats for f in ["Number","Person","Tense"]):
        print("WARN: non-subjunctive VB should not have Number, Person, or Tense in " + docname + " @ token " + str(id))
    elif pos == "VB" and verbForm == "Inf":
        if "Mood" in feats:
            print("WARN: VB/VerbForm=Inf should not have Mood in " + docname + " @ token " + str(id))
    elif pos == "VB" and not (verbForm == "Fin" and feats["Mood"] == "Imp"):
        print("WARN: non-inf VB should correspond with Mood=Imp, VerbForm=Fin in " + docname + " @ token " + str(id))
    elif pos == "VB" and any(f in feats for f in ["Voice"]):
        print("WARN: VB should not have Voice in " + docname + " @ token " + str(id))

    # VBD => Tense=Past, VerbForm=Fin, Mood=Ind, ...
    if pos == "VBD" and verbForm != "Fin":
        print("WARN: VBD should correspond with VerbForm=Fin in " + docname + " @ token " + str(id))
    if pos == "VBD" and not all(f in feats for f in ["Number","Person","Tense","Mood"]):
        print("WARN: VBD should have Number, Person, Tense, and Mood in " + docname + " @ token " + str(id))
    elif pos == "VBD" and (tense != "Past" or feats["Mood"] != "Ind"):
        if not (lemma=="be" and tense=="Past" and feats["Mood"]=="Sub"):
            print("WARN: VBD should correspond with Tense=Past and Mood=Ind (or Mood=Sub for 'were') in " + docname + " @ token " + str(id))
    if pos == "VBD" and any(f in feats for f in ["Voice"]):
        print("WARN: VBD should not have Voice in " + docname + " @ token " + str(id))

    # {VBP,VBZ} => Tense=Pres, VerbForm=Fin, Mood=Ind, ...
    # VBZ => Person=3, Number=Sing
    if pos in ("VBP","VBZ") and verbForm != "Fin":
        print("WARN: " + pos + " should correspond with VerbForm=Fin in " + docname + " @ token " + str(id))
    if pos in ("VBP","VBZ") and not all(f in feats for f in ["Number","Person","Tense","Mood"]):
        print("WARN: " + pos + " should have Number, Person, Tense, and Mood in " + docname + " @ token " + str(id))
    elif pos in ("VBP","VBZ") and (tense != "Pres" or feats["Mood"] != "Ind"):
        print("WARN: " + pos + " should correspond with Mood=Ind, Tense=Pres in " + docname + " @ token " + str(id))
    elif pos == "VBZ" and (number != "Sing" or person != "3"):
        print("WARN: VBZ should have Number=Sing, Person=3 in " + docname + " @ token " + str(id))
    if pos in ("VBP","VBZ") and any(f in feats for f in ["Voice"]):
        print("WARN: " + pos + " should not have Voice in " + docname + " @ token " + str(id))


    # VBG => VerbForm=Ger,Part
    if pos == "VBG" and verbForm == "Part":
        # VBG => Tense=Pres | VerbForm=Part
        if pos == "VBG" and not (tense == "Pres"):
            print("WARN: VBG should correspond with Tense=Pres in " + docname + " @ token " + str(id))
    elif pos == "VBG" and not (verbForm == "Ger"):
        # AUX+VBG | VERB+VBG => VerbForm=Ger
        if upos in ["AUX","VERB"]:
            print("WARN: " + upos + "+VBG should correspond with VerbForm=Ger,Part in " + docname + " @ token " + str(id))
        # ADJ+VBG => Degree=Poss
        elif upos == "ADJ" and not (degree == "Pos"):
            print("WARN: ADJ+VBG should correspond with Degree=Pos in " + docname + " @ token " + str(id))

    # VBN => Tense=Past | VerbForm=Part
    if pos == "VBN" and not (verbForm == "Part"):
        print("WARN: VBN should correspond with VerbForm=Part in " + docname + " @ token " + str(id))
    if pos == "VBN" and not (tense == "Past"):
        print("WARN: VBN should correspond with Tense=Past in " + docname + " @ token " + str(id))

    # VBZ => Number=Sing | Person=3 | Tense=Pres | VerbForm=Fin
    if pos == "VBZ" and not (number == "Sing"):
        print("WARN: VBZ should correspond with Number=Sing in " + docname + " @ token " + str(id))
    if pos == "VBZ" and not (person == "3"):
        print("WARN: VBZ should correspond with Person=3 in " + docname + " @ token " + str(id))
    if pos == "VBZ" and not (tense == "Pres"):
        print("WARN: VBZ should correspond with Tense=Pres in " + docname + " @ token " + str(id))
    if pos == "VBZ" and not (verbForm == "Fin"):
        print("WARN: VBZ should correspond with VerbForm=Fin in " + docname + " @ token " + str(id))

    # VBP => Number=Sing | Person!=3 | Tense=Pres | VerbForm=Fin
    if pos == "VBP":
        if not (number == "Sing" or number == "Plur"):
            print("WARN: VBP should correspond with Number=Sing|Plur in " + docname + " @ token " + str(id))
        elif number == "Sing" and not (person == "1" or person == "2") and not misc.get("CorrectNumber")=="Sing":
            print("WARN: singular VBP should correspond with Person=1|2 in " + docname + " @ token " + str(id))
        elif person not in {"1", "2", "3"}:
            print("WARN: plural VBP should correspond with Person=1|2|3 in " + docname + " @ token " + str(id))
    if pos == "VBP" and not (tense == "Pres"):
        print("WARN: VBP should correspond with Tense=Pres in " + docname + " @ token " + str(id))
    if pos == "VBP" and not (verbForm == "Fin"):
        print("WARN: VBP should correspond with VerbForm=Fin in " + docname + " @ token " + str(id))

    if lemma == "be":
        t = tok.lower()
        if t == "be":
            if upos=="NOUN" and docname=="newsgroup-groups.google.com_INTPunderground_b2c62e87877e4a22_ENG_20050906_165900-0025":
                pass    # "the be all end all"
            elif pos!="VB" or not (verbForm=="Inf" or (verbForm=="Fin" and tense=="Pres" and feats["Mood"]=="Sub") or (verbForm=="Fin" and feats["Mood"]=="Imp")):
                print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
        elif t == "am" or t == "'m" or t == "’m":
            if pos!="VBP" or verbForm!="Fin" or tense!="Pres" or feats["Mood"]!="Ind" or person!="1" or number!="Sing":
                print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
        elif t == "are":    # can be 1st person in negation: "aren't I"
            if pos!="VBP" or verbForm!="Fin" or tense!="Pres" or feats["Mood"]!="Ind" or not ((number=="Plur" and person in {"1","2","3"}) or (number=="Sing" and person in {"1","2"})):
                print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
        elif t == "is" or t == "'s" or t == "’s":
            if (pos!="VBZ" and "CorrectNumber" not in misc) or verbForm!="Fin" or tense!="Pres" or feats["Mood"]!="Ind" or person!="3" or misc.get("CorrectNumber",number)!="Sing":
                print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
        elif t == "art":    # thou art
            if pos!="VBP" or verbForm!="Fin" or tense!="Pres" or feats["Mood"]!="Ind" or not (number=="Sing" and person=="2") or feats["Style"]!="Arch":
                print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
        elif t == "ai": # ain't = am/are/is + not (mainly)
            if pos not in {"VBP","VBZ"} or verbForm!="Fin" or tense!="Pres" or feats["Mood"]!="Ind" or feats["Style"]!="Vrnc":
                print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
        elif t == "was":
            if pos!="VBD" or verbForm!="Fin" or tense!="Past" or feats["Mood"]!="Ind" or number!="Sing":
                print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
        elif t == "were":
            if pos!="VBD" or verbForm!="Fin" or tense!="Past" or not ((feats["Mood"]=="Ind" and (number=="Plur" or person=="2")) or (feats["Mood"]=="Sub" and number=="Sing")):
                print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
        elif t == "'re" or t == "’re":  # indicative were or are
            if pos!="VBD" and pos!="VBP":
                print("WARN: unexpected XPOS for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
            elif pos=="VBD":
                if verbForm!="Fin" or tense!="Past" or not (feats["Mood"]=="Ind" and (number=="Plur" or person=="2")):
                    print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
            elif pos=="VBP":
                if verbForm!="Fin" or tense!="Pres" or feats["Mood"]!="Ind" or not ((number=="Plur" and person in {"1","2","3"}) or (number=="Sing" and person in {"1","2"})):
                    print("WARN: unexpected morphology for 'be' verb: '" + t + "' in " + docname + " @ token " + str(id))
        elif t == "been":
            if pos != "VBN":
                print("WARN: 'been' should be VBN in " + docname + " @ token " + str(id))
        elif t == "being":
            if pos != "VBG":
                print("WARN: 'being' should be VBG in " + docname + " @ token " + str(id))
        else:
            print("WARN: unknown 'be' form: " + t + " in " + docname + " @ token " + str(id))

# See https://universaldependencies.org/en/pos/PRON.html
PRONOUNS: dict[tuple[str,str],dict] = {
  # personal, nominative -- PronType=Prs|Case=Nom
  ("i","PRP"):{"Case":"Nom","Number":"Sing","Person":"1","PronType":"Prs","LEMMA":"I"},
  ("we","PRP"):{"Case":"Nom","Number":"Plur","Person":"1","PronType":"Prs","LEMMA":"we"},
  ("thou","PRP"):{"Case":"Nom","Number":"Sing","Person":"2","PronType":"Prs","LEMMA":"thou","Style":"Arch","ModernForm":"you"}, # early modern english
  ("ye","PRP"):{"Case":"Nom","Number":"Plur","Person":"2","PronType":"Prs","LEMMA":"ye","Style":"Arch","ModernForm":"you"}, # early modern english
  ("you","PRP"):{"Case":["Acc","Nom"],"Person":"2","PronType":"Prs","LEMMA":"you"},
  ("he","PRP"):{"Case":"Nom","Gender":"Masc","Number":"Sing","Person":"3","PronType":"Prs","LEMMA":"he"},
  ("she","PRP"):{"Case":"Nom","Gender":"Fem","Number":"Sing","Person":"3","PronType":"Prs","LEMMA":"she"},
  ("it","PRP"):{"Case":["Acc","Nom"],"Gender":"Neut","Number":"Sing","Person":"3","PronType":"Prs","LEMMA":"it"},
  ("they","PRP"):{"Case":"Nom","Number":"Plur","Person":"3","PronType":"Prs","LEMMA":"they"},
  # personal, accusative -- PronType=Prs|Case=Acc
  ("me","PRP"):{"Case":"Acc","Number":"Sing","Person":"1","PronType":"Prs","LEMMA":"I"},
  ("us","PRP"):{"Case":"Acc","Number":"Plur","Person":"1","PronType":"Prs","LEMMA":"we"},
  ("thee","PRP"):{"Case":"Acc","Number":"Sing","Person":"2","PronType":"Prs","LEMMA":"thou","Style":"Arch","ModernForm":"you"}, # early modern english
  ("him","PRP"):{"Case":"Acc","Gender":"Masc","Number":"Sing","Person":"3","PronType":"Prs","LEMMA":"he"},
  ("her","PRP"):{"Case":"Acc","Gender":"Fem","Number":"Sing","Person":"3","PronType":"Prs","LEMMA":"she"},
  ("them","PRP"):{"Case":"Acc","Number":"Plur","Person":"3","PronType":"Prs","LEMMA":"they"},
  # personal, dependent possessive -- PronType=Prs|Case=Gen|Poss=Yes
  ("my","PRP$"):{"Case":"Gen","Number":"Sing","Person":"1","Poss":"Yes","PronType":"Prs","LEMMA":"my"},
  ("our","PRP$"):{"Case":"Gen","Number":"Plur","Person":"1","Poss":"Yes","PronType":"Prs","LEMMA":"our"},
  ("thy","PRP$"):{"Case":"Gen","Number":"Sing","Person":"2","Poss":"Yes","PronType":"Prs","LEMMA":"thy","Style":"Arch","ModernForm":"your"}, # early modern english
  ("your","PRP$"):{"Case":"Gen","Person":"2","Poss":"Yes","PronType":"Prs","LEMMA":"your"},
  ("his","PRP$"):{"Case":"Gen","Gender":"Masc","Number":"Sing","Person":"3","Poss":"Yes","PronType":"Prs","LEMMA":"his"},
  ("her","PRP$"):{"Case":"Gen","Gender":"Fem","Number":"Sing","Person":"3","Poss":"Yes","PronType":"Prs","LEMMA":"her"},
  ("its","PRP$"):{"Case":"Gen","Gender":"Neut","Number":"Sing","Person":"3","Poss":"Yes","PronType":"Prs","LEMMA":"its"},
  ("their","PRP$"):{"Case":"Gen","Gender":["Neut",None],"Number":["Plur","Sing"],"Person":"3","Poss":"Yes","PronType":"Prs","LEMMA":"their"},
  # personal, independent possessive -- PronType=Prs|Poss=Yes
  ("mine","PRP"):{"Number":"Sing","Person":"1","Poss":"Yes","PronType":"Prs","LEMMA":"my"},
  ("ours","PRP"):{"Number":"Plur","Person":"1","Poss":"Yes","PronType":"Prs","LEMMA":"our"},
  ("thine","PRP"):{"Number":"Sing","Person":"2","Poss":"Yes","PronType":"Prs","LEMMA":"thy","Style":"Arch","ModernForm":"yours"}, # early modern english
  ("yours","PRP"):{"Person":"2","Poss":"Yes","PronType":"Prs","LEMMA":"your"},
  ("his","PRP"):{"Gender":"Masc","Number":"Sing","Person":"3","Poss":"Yes","PronType":"Prs","LEMMA":"his"},
  ("hers","PRP"):{"Gender":"Fem","Number":"Sing","Person":"3","Poss":"Yes","PronType":"Prs","LEMMA":"her"},
  ("its","PRP"):{"Gender":"Neut","Number":"Sing","Person":"3","Poss":"Yes","PronType":"Prs","LEMMA":"its"},
  ("theirs","PRP"):{"Number":"Plur","Person":"3","Poss":"Yes","PronType":"Prs","LEMMA":"their"},
  # personal, reflexive -- PronType=Prs|Case=Acc|Reflex=Yes
  ("myself","PRP"):{"Case":"Acc","Number":"Sing","Person":"1","PronType":["Emp","Prs"],"Reflex":"Yes","LEMMA":"myself"},
  ("ourselves","PRP"):{"Case":"Acc","Number":"Plur","Person":"1","PronType":["Emp","Prs"],"Reflex":"Yes","LEMMA":"ourselves"},
  ("thyself","PRP"):{"Case":"Acc","Number":"Sing","Person":"2","Poss":"Yes","PronType":["Emp","Prs"],"LEMMA":"thyself","Style":"Arch","ModernForm":"yourself"}, # early modern english
  ("yourself","PRP"):{"Case":"Acc","Number":"Sing","Person":"2","PronType":["Emp","Prs"],"Reflex":"Yes","LEMMA":"yourself"},
  ("yourselves","PRP"):{"Case":"Acc","Number":"Plur","Person":"2","PronType":["Emp","Prs"],"Reflex":"Yes","LEMMA":"yourselves"},
  ("himself","PRP"):{"Case":"Acc","Gender":"Masc","Number":"Sing","Person":"3","PronType":["Emp","Prs"],"Reflex":"Yes","LEMMA":"himself"},
  ("herself","PRP"):{"Case":"Acc","Gender":"Fem","Number":"Sing","Person":"3","PronType":["Emp","Prs"],"Reflex":"Yes","LEMMA":"herself"},
  ("itself","PRP"):{"Case":"Acc","Gender":"Neut","Number":"Sing","Person":"3","PronType":["Emp","Prs"],"Reflex":"Yes","LEMMA":"itself"},
  ("themselves","PRP"):{"Case":"Acc","Number":"Plur","Person":"3","PronType":["Emp","Prs"],"Reflex":"Yes","LEMMA":"themselves"},
  # abbreviations
  ("u","PRP"):{"Abbr":"Yes","Case":["Acc","Nom"],"Person":"2","PronType":"Prs","LEMMA":"you","CorrectForm":"you"},
  ("ur","PRP$"):{"Abbr":"Yes","Case":"Gen","Person":"2","Poss":"Yes","PronType":"Prs","LEMMA":"your","CorrectForm":"your"},
  # colloquial, vernacular, slang
  ("ya","PRP"):{"Case":["Acc","Nom"],"Person":"2","PronType":"Prs","LEMMA":"you","Style":"Coll"},
  ("'em","PRP"):{"Case":"Acc","Number":"Plur","Person":"3","PronType":"Prs","LEMMA":"they","Style":"Coll"},
  ("yo","PRP$"):{"Case":"Gen","Person":"2","Poss":"Yes","PronType":"Prs","LEMMA":"your","Style":"Slng"},
  ("y'all","PRP"):{"Case":"Acc","Number":"Plur","Person":"2","PronType":"Prs","LEMMA":"y'all","Style":"Vrnc"},
  # other
  ("one","PRP"):{"Number":"Sing","Person":"3","PronType":"Prs","LEMMA":"one"},    # one/PRP is the generic individual use
  ("'s","PRP"):{"Case":"Acc","Number":"Plur","Person":"1","PronType":"Prs","LEMMA":"we"},
}

# add indefinite PRONs
# 1-word simple indefinite:
PRONOUNS[("none", "NN")] = {"LEMMA":"none", "PronType":"Neg"}
PRONOUNS[("naught", "NN")] = {"LEMMA":"naught", "PronType":"Neg"}
# 2-word compound indefinite: 'one' following 'no'
PRONOUNS[("no one", "NN")] = {"Number":"Sing", "LEMMA":"one", "PronType":"Neg"}
# 1-word compound indefinites
for b in ("body","one","thing"):
    for a,t in {("any","Ind"),("some","Ind"),("every","Tot"),("no","Neg")}:
        l = a+b
        if l=="noone":
            l = "no-one"
        PRONOUNS[(l, "NN")] = {"Number":"Sing", "LEMMA": l, "PronType": t}

PRON_LEMMAS = {v["LEMMA"] for k,v in PRONOUNS.items()} # pronouns only, no DETs

# 2-word reciprocals (fixed; store XPOS/feats of first word but lemma of second word)
PRONOUNS[("each other", "DT")] = {"LEMMA":"other", "PronType":"Rcp", "ExtPos":"PRON"}   # ExtPos since the technical head is DET
PRONOUNS[("one another", "CD")] = {"LEMMA":"another", "PronType":"Rcp", "ExtPos":"PRON"}
# (we don't want to store "each" as a PRON lemma)

DETS = {
  # articles
  ("a", "DT"):{"Definite":"Ind","PronType":"Art","LEMMA":"a"},
  ("an", "DT"):{"Definite":"Ind","PronType":"Art","LEMMA":"a"},
  ("the", "DT"):{"Definite":"Def","PronType":"Art","LEMMA":"the"},
  # demonstratives. Note: tagged PRON if not acting as det, but script will check either way
  ("this", "DT"):{"Number":"Sing","PronType":"Dem","LEMMA":"this"},
  ("that", "DT"):{"Number":"Sing","PronType":"Dem","LEMMA":"that"},
  ("these", "DT"):{"Number":"Plur","PronType":"Dem","LEMMA":"this"},
  ("those", "DT"):{"Number":"Plur","PronType":"Dem","LEMMA":"that"},
  ("yonder", "DT"):{"PronType":"Dem","LEMMA":"yonder"},
  # total
  ("all", "DT"):{"PronType":"Tot","LEMMA":"all"},
  ("all", "PDT"):{"PronType":"Tot","LEMMA":"all"},
  ("both", "DT"):{"PronType":"Tot","LEMMA":"both"},
  ("both", "PDT"):{"PronType":"Tot","LEMMA":"both"},
  ("each", "DT"):{"PronType":["Tot","Rcp"],"LEMMA":"each"},
  ("every", "DT"):{"PronType":"Tot","LEMMA":"every"},
  # indefinite
  ("half", "PDT"):{"NumForm":"Word","NumType":"Frac","PronType":"Ind","LEMMA":"half"},
  ("no", "DT"):{"PronType":"Neg","LEMMA":"no"},
  ("neither", "DT"):{"PronType":"Neg","LEMMA":"neither"},
  ("nary", "PDT"):{"PronType":"Neg","LEMMA":"nary"},
  ("any", "DT"):{"PronType":"Ind","LEMMA":"any"},
  ("some", "DT"):{"PronType":"Ind","LEMMA":"some"},
  ("another", "DT"):{"PronType":"Ind","LEMMA":"another"},
  ("either", "DT"):{"PronType":"Ind","LEMMA":"either"},
  ("such", "PDT"):{"PronType":"Ind","LEMMA":"such"},
  ("quite", "PDT"):{"PronType":"Ind","LEMMA":"quite"},
  ("many", "PDT"):{"PronType":"Ind","LEMMA":"many"},
  # WH (interrogative or relative)
  ("that", "WDT"):{"PronType":"Rel","LEMMA":"that"},    # actually PRON
  ("which", "WDT"):{"PronType":["Int","Rel"],"LEMMA":"which"},  # DET or PRON
  ("what", "WDT"):{"PronType":["Int","Rel"],"LEMMA":"what"},
  ("whatever", "WDT"):{"PronType":["Int","Rel"],"LEMMA":"whatever"}
}

ADVS = {
    # WH
    ("how", "WRB"):{"PronType":["Int","Rel"],"LEMMA":"how","ExtPos":["ADV",None]},  # ExtPos=ADV for 'how come'
    ("why", "WRB"):{"PronType":["Int","Rel"],"LEMMA":"why"},
    ("when", "WRB"):{"PronType":["Dem","Int","Rel"],"LEMMA":"when"},
    ("when", "IN"):{"PronType":["Dem"],"LEMMA":"when"},
    ("where", "WRB"):{"PronType":["Dem","Int","Rel"],"LEMMA":"where"},
    ("whither", "WRB"):{"PronType":["Dem","Int","Rel"],"LEMMA":"whither"},
    ("however", "WRB"):{"PronType":["Int","Rel"],"LEMMA":"however"},    # WRB for non-discourse-connective uses
    ("whenever", "WRB"):{"PronType":["Int","Rel"],"LEMMA":"whenever"},
    ("wherever", "WRB"):{"PronType":["Int","Rel"],"LEMMA":"wherever"},
    ("wherein", "WRB"):{"PronType":"Rel","LEMMA":"wherein"},
    # non-WH
    ("here", "RB"):{"PronType":"Dem","LEMMA":"here"},
    ("now", "RB"):{"PronType":"Dem","LEMMA":"now"},
    ("then", "RB"):{"PronType":"Dem","LEMMA":"then"},
    ("there", "RB"):{"PronType":"Dem","LEMMA":"there"},
    ("neither", "RB"):{"PronType":"Neg","LEMMA":"neither"},
    ("never", "RB"):{"PronType":"Neg","LEMMA":"never"},
    ("NEEEEEEEEEVERRRR", "RB"):{"PronType":"Neg","LEMMA":"never","Style":"Expr","CorrectForm":"never"},
    ("nowhere", "RB"):{"PronType":"Neg","LEMMA":"nowhere"},
    ("always", "RB"):{"PronType":"Tot","LEMMA":"always"},
    ("everywhere", "RB"):{"PronType":"Tot","LEMMA":"everywhere"},
    ("anyplace", "RB"):{"PronType":"Ind","LEMMA":"anyplace"},
    ("anytime", "RB"):{"PronType":"Ind","LEMMA":"anytime"},
    ("anywhere", "RB"):{"PronType":"Ind","LEMMA":"anywhere"},
    ("someplace", "RB"):{"PronType":"Ind","LEMMA":"someplace"},
    ("sometime", "RB"):{"PronType":"Ind","LEMMA":"sometime"},
    ("sometimes", "RB"):{"PronType":"Ind","LEMMA":"sometimes"},
    ("somewhere", "RB"):{"PronType":"Ind","LEMMA":"somewhere"},
    ("ever", "RB"):{"PronType":"Ind","LEMMA":"ever"},
    ("either", "RB"):{"PronType":"Ind","LEMMA":"either"}
}
ADV_ENTRIES = {f for (f,p),v in ADVS.items()}


# See https://universaldependencies.org/en/pos/PRON.html
def flag_pronoun_warnings(id, form, pos, upos, lemma, feats, misc, prev_tok, docname):
    form = form.replace("’", "'") # Normalize apostrophe characters.

    # Shorthand for printing errors
    tokname = "FORM '" + form + "'"
    inname = " in " + docname + " @ token " + str(id)

    # Look up the correct features/lemma for the pronoun from the PRONOUNS lexicon
    if upos=='PRON' or form.lower() in ('these','those'):
        data_key = (form.lower(), pos)
    elif form in ADV_ENTRIES:
        data_key = (form, pos)
    else:
        data_key = (lemma, pos)
    
    if (prev_tok.lower(),form.lower()) in {("no","one"), ("one","another"), ("each","other")}:  # special case for bigrams
        data_key = (prev_tok.lower() + " " + form.lower(), pos)

    data = PRONOUNS.get(data_key, DETS.get(data_key, ADVS.get(data_key)))

    if data == None:
        if pos in ["PRP","PRP$"]:
            print("WARN: FORM '" + form + "' with XPOS=" + pos + " does not have a corresponding feature mapping " + inname)
        return

    if not lemma == data["LEMMA"]:
        print("WARN: FORM '" + form + "' should correspond with LEMMA=" + data["LEMMA"] + inname)

    # Check whether the correct features for the lexical item (data) match
    # the observed features on the token (feats)
    if upos != "PRON" and feats.get("Abbr")=="Yes":
        pass    # OK to abbreviate determiners, and to have a CorrectForm on these
    else:
        check_has_feature("Abbr", feats, data, tokname, inname)
        # CorrectForm for Typo=Yes has already been handled.
        if not ("Typo" in feats and feats["Typo"] == "Yes"):
            check_has_feature("CorrectForm", misc, data, tokname, inname)
    check_has_feature("Case", feats, data, tokname, inname)
    check_has_feature("Definite", feats, data, tokname, inname)
    check_has_feature("Gender", feats, data, tokname, inname)
    check_has_feature("Number", feats, data, tokname, inname)
    check_has_feature("Person", feats, data, tokname, inname)
    check_has_feature("Poss", feats, data, tokname, inname)
    check_has_feature("PronType", feats, data, tokname, inname)
    check_has_feature("Style", feats, data, tokname, inname)
    check_has_feature("ExtPos", misc, data, tokname, inname)
    # ensure pronominal uses of 'one' do NOT have these features
    check_has_feature("NumForm", feats, data, tokname, inname)
    check_has_feature("NumType", feats, data, tokname, inname)

    check_has_feature("ModernForm", misc, data, tokname, inname)
    


# See http://universaldependencies.org/u/overview/typos.html
# NOTE: This does not change the form for Abbr=Yes and Style=Expr. This allows
#       pronoun checks and other similar checks to ensure the Abbr/Style is set.
def check_and_fix_form_typos(id, form, feats, misc, merged, docname):
    if "Typo" in feats and feats["Typo"] == "Yes":
        if "CorrectForm" in misc:
            # Misspelled Word ... use the corrected form
            return misc["CorrectForm"] or form # in GUM, some explicit CorrectForm=_ which parses as None
        elif merged:
            # Wrongly Split Word ... use the already combined form from the two words in the goeswith logic
            return form
        else:
            inname = " in " + docname + " @ token " + str(id)
            print("WARN: FORM '" + form + "' with Typo=Yes should have feature CorrectForm or a following goeswith dependency" + inname)
    return form


def check_has_feature(name, feats, data, tokname, inname):
    if not name in data:
        if name in feats:
            print("WARN: " + tokname + " should not have feature " + name + inname)
        return

    if isinstance(data[name], str):
        if not (name in feats and feats[name] == data[name]):
            feature = name + "=" + data[name]
            print("WARN: " + tokname + " should correspond with " + feature + inname)
    else:
        if not name in feats and None in data[name]:
            pass # optional feature
        elif not (name in feats and feats[name] in data[name]):
            feature = name + "=" + ','.join([value for value in data[name] if value != None])
            print("WARN: " + tokname + " should correspond with " + feature + inname)


if __name__=='__main__':
    validate_src(sys.argv[1:] or glob.glob('../../en_ewt-ud-*.conllu'))
