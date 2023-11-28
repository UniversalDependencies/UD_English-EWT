#!/bin/bash
# e.g., cat en_ewt-ud-train.conllu | bash rc-types.sh > train.conllu
# (takes about 2 min to run on train)
# to produce counts:
#  egrep -o 'Cxn=[^|]+' train.conllu | sort | uniq -c | sort -rn | head -n10
export PATH="$HOME/.local/bin/:$PATH"
udapy util.Eval node='if node.deprel in ("acl:relcl","advcl:relcl"):
    """
    Indicate relative clause subtype. Adds in the MISC column a Cxn (construction) label of the form

        rc-TYPE-DEPRELPATH(-FRONTSTRAND)
    
    TYPE is one of: free, red [reduced], wh, that, cleft.{red,wh,that} (for it-clefts)

    DEPRELPATH is an underscore-separated list of one or more deprels
    indicating the understood role of the relativized element within the relative clause.
    These are derived from the enhanced dependencies graph (but omit lexicalization like ":from").
    The path is bottom-up, ending when the relative clause predicate is reached.
    If the predicate itself is directly relativized, then the path consists of "pred".

    The last part, FRONTSTRAND, is present if:
    - the relative phrase is a fronted PP (-pfront), and/or
    - the relative clause has triggered stranding of a preposition (-pstrand) or
      an auxiliary/copula/infinitive "to" (-auxstrand).
    (-auxstrand is NOT added if the stranded item appears to have been triggered by a comparative
    construction, i.e. it is marked by "as", "like", or "than": e.g. "people who share the same tastes as I do")

    Examples:
        - rc-wh-nsubj for "the boy who lived"
        - rc-red-obj for "all you need (is love)"
        - rc-free-nsubj for "what happens in Vegas (stays in Vegas)"
        - rc-that-obj_xcomp for "somebody that I used to know"
        - rc-cleft.red_obl-pstrand for "who is it he asked for?"
        - rc-free-pred-auxstrand for "(doing) what they can"
        - rc-red-pred-pstrand for "a panel I will be on"
        - rc-wh-nmod_obl-pfront-pstrand for "the cookies (some of which I sat on)"
        - rc-wh-ccomp-auxstrand for "If the baby is feathered yet - which I’m sure he is mostly"
    
    Many reduced RCs lack an enhanced deprel for the relativized element,
    so "missingedep" serves as a placeholder.

    Note: Some errors arise in cases of nested RCs or multiple RCs sharing the same head.

    TODO: consider refining -auxstrand rules to avoid matching cases like
        obtain the very best possible education they can
        is there someone else that will
    (should ellipsis nodes be added?)

    TODO: "at the exact same positions they were" (missing P?)

    Most frequent in training data:

    488 Cxn=rc-red-missingedep
    431 Cxn=rc-wh-nsubj
    305 Cxn=rc-that-nsubj
    112 Cxn=rc-that-obj
     76 Cxn=rc-free-obj
     61 Cxn=rc-red-missingedep-pstrand
     55 Cxn=rc-wh-obl
     50 Cxn=rc-wh-nsubj:pass
     47 Cxn=rc-that-nsubj:pass
     35 Cxn=rc-wh-csubj
    """
    import sys

    basic_pred = node
    rctype = ""
    head = basic_pred.parent    
    assert head.precedes(basic_pred)
    wh = None   # relativizer if present (same as basic_pred for predicate relative) (not including head of free relative)

    if node.deprel=="advcl:relcl" and any(ch.deprel=="expl" and ch.lemma=="it" for ch in head.children):
        rctype = "cleft."
    elif head.feats["PronType"]=="Rel": # TODO: "whatever coverage this story receives"
        rctype = "free"
    
    if rctype!="free":
        isFreeRCHead = False    # free relative may be embedded as predicate of wh-relative ("which is what is needed")
        if basic_pred.feats["PronType"]=="Rel":
            for ch in basic_pred.children(following_only=True):
                if ch.deprel==("advcl:relcl" if basic_pred.upos=="ADV" else "acl:relcl"):
                    isFreeRCHead = True
                    break

        if basic_pred.feats["PronType"]=="Rel" and not isFreeRCHead:
            # relativized predicate
            wh = basic_pred
            if wh.lemma=="that":    # "one of the nicest pubs that i have been into"
                rctype += "that"
            else:
                assert wh.lemma=="which" or wh.lemma=="whom",wh # TODO: figure out "among whom have been" case        
                rctype += "wh"
        else:
            cc = basic_pred.children[:]
            for i,c in enumerate(cc):
                if c in cc[:i]:
                    continue    # prevent infinite recursion
                if c.deprel in ("acl:relcl", "advcl:relcl"):    # embedded RC
                    continue
                if len(c.deps)==1 and c.deps[0]["deprel"] == "ref":
                    #assert c.deps[0]["parent"] == head,(basic_pred,head,c.deps) # false for a dependent WH word (which, whose)
                    if c.feats.get("PronType") == "Rel":
                        wh = c
                    else:
                        wh = next(ch for ch in c.children if ch.deprel not in ("case","mark"))  # e.g. "whose" as nmod:poss
                        assert wh.feats.get("PronType")=="Rel",(wh,head)
                        assert wh.lemma in ("whose", "which"),wh
                    
                    if wh.lemma == "that" and wh.xpos == "WDT":
                        rctype += "that"
                    else:
                        assert wh.lemma.startswith("wh") or wh.lemma=="how",(c.lemma,c.xpos)
                        rctype += "wh"
                    break
                cc.extend(c.children)   # recurse down the tree in case the relativizer is not a direct dependent of the predicate

    if not rctype or rctype=="cleft.":
        rctype += "red"
    
    edeprels = []
    edep = None

    #if basic_pred.misc["Promoted"]=="Yes":
    if basic_pred is wh or basic_pred.upos in ("AUX","ADP"):    # ...which it is; what it is; the room the cage is in
        # other causes of ellipsis are NOT in this category: "is there someone else that will?"
        # note that this does not capture all cases of predicate anaphora: if it is embedded in a deeper layer ("which I think it does") it will have a regular deprel (ccomp)
        if rctype=="free":
            #assert sum(1 for e in head.deps if not e["deprel"].startswith("conj"))==(0 if head.deprel=="conj" else 1),head
            for e in head.deps:
                if e["parent"].ord > head.ord and e["parent"] is not head.parent:
                    # free RC head (WH word) should not have an edep into the RC if it is a predicate relative
                    # (if there is an edep parent after the head it should be after the last word of this RC. It may be in a subsequent RC with the same head)
                    assert e["parent"].ord > basic_pred.descendants(following_only=True, add_self=True)[-1].ord,head
            edeprels.append("pred")
        else:
            for e in head.deps:
                if e["parent"] is basic_pred:
                    break   # there is a reentrancy into the RC, so this is not a predicate relative
                    # e.g. "is there someone else that will/AUX?" E:nsubj(will, someone)
            else:
                edeprels.append("pred")
    
    if not edeprels:
        for edep in head.deps:  # there may be multiple edeps. we take the first one that may be in the RC
            if edep["parent"]==head.parent:
                continue    # basic tree head is in the matrix clause, not RC
            if wh is not None and wh.deprel != "nmod" and edep["deprel"] != "obl:of":  # nmod, obl exceptions for fronted partitive ("400 of whom", "much of which")
                if edep["parent"].ord > wh.ord:
                    break
            elif edep["parent"].ord > head.ord:
                break
        else:
            if rctype == "red":
                edeprels.append("missingedep")
            else:
                assert False,(rctype,head,edep,wh,basic_pred)
            edep = None

    while edep and edep["parent"] is not head:
        r = edep["deprel"]
        if r.endswith((":about", ":after", ":as", ":at", ":besides", ":for", ":from", ":in", ":inside", ":into",
                       ":like", ":of", ":off_of", ":on", ":through", ":to", ":with", ":without")):   # note: this removes both prepositional and infinitival :to
            r = r[:r.rindex(":")]
        edeprels.append(r)
        assert edep["parent"].deps,(rctype,edeprels,edep["parent"])
        edep = edep["parent"].deps[0]

    edeprelsS = "_".join(edeprels)
    assert edeprelsS in {"missingedep", "pred", "nsubj", "nsubj:outer", "nsubj:pass", "csubj", "csubj:outer",
                         "iobj", "obj", "advmod", "obl", "obl:agent", "obl:npmod", "obl:tmod", "xcomp", "ccomp",
                         "nsubj_ccomp", "nsubj:pass_ccomp", "csubj_ccomp",
                         "obj_advcl", "obj_ccomp", "obj_xcomp", "obl_nsubj", "obl_xcomp", "obl_obl",
                         "xcomp_xcomp", "advmod_xcomp",
                         "nmod:poss_nsubj", "nmod:poss_nsubj:outer", "nmod:poss_nsubj:pass",
                         "nmod:poss_obj", "nmod:poss_obl",
                         "nmod_nsubj", "nmod_nsubj:pass", "nmod_obj", "nmod_xcomp",
                         "obj_acl_obj", "obj_xcomp_ccomp", "obl_advcl_obj", "obj_xcomp_xcomp"},(head, edeprelsS, rctype)
    if edeprelsS.startswith("xcomp"):   # advmod is usually free, but "now when..." is not
        assert (rctype == "free" or head.lemma=="wipe"),head  # exception for "wiped off the map, which..." example
    elif edeprelsS == "ccomp":
        assert rctype in ("wh","that"),(rctype,head)
    
    strandfront = ""
    if wh is not None:
        if rctype!="free" and any(p for p in wh.children(preceding_only=True) if p.deprel=="case"):
            strandfront = "-pfront"
        elif any(p for p in wh.children(following_only=True) if p.deprel=="case"):
            strandfront = "-pstrand"
    eltsInRC = list(filter(lambda n: n.deprel!="punct", basic_pred.children(add_self=True)))
    # not following_only=True ("which I’m certain it does n’t": sure -> which -> does)
    # if basic_pred.upos=="AUX":
    #     print(basic_pred,eltsInRC, file=sys.stderr)
    for lastChInRC in eltsInRC[::-1]:
        if lastChInRC.deprel in ("punct", "advmod", "advcl"):
            # adverbial things and puncts can occur after a stranded element, but should not contain RC-induced stranding
            # (a possible exception would be complement advcls: "what I was thinking about trying to do")
            continue
        elif lastChInRC is basic_pred:
            lastInRC = lastChInRC
        else:
            lastInRC = list(filter(lambda n: n.deprel not in ("punct", "advmod", "advcl"), lastChInRC.descendants(add_self=True)))
            # not following_only=True ("which I’m certain it does n’t": sure -> which -> does)
            if not lastInRC:
                continue
            lastInRC = lastInRC[-1]
            # if lastInRC.deprel in ("cop","aux","aux:pass","mark") and lastInRC.parent.ord > basic_pred.ord:
            #     break

        # if basic_pred.upos=="AUX":
        #     print(lastChInRC, lastInRC, file=sys.stderr)
        if lastInRC.parent.ord < lastInRC.ord:  # if preposition or aux attaches to the right it is not stranded
            if lastInRC.upos=="ADP" and lastInRC.deprel!="compound:prt":        
                assert lastInRC.deprel in ("acl:relcl", "advcl:relcl", "obl", "nmod", "case"),lastInRC
                assert strandfront in ("", "-pstrand"),(strandfront,lastInRC)
                strandfront = "-pstrand"
                assert (lastInRC.misc["Promoted"]=="Yes") ^ (lastInRC.deprel=="case"),lastInRC
                break
            elif lastInRC.upos=="AUX" or (lastInRC.upos=="PART" and lastInRC.lemma=="to"):
                assert strandfront in ("", "-pstrand") or wh.lemma=="whom",(strandfront,lastInRC)   # TODO: "among whom"
                ee = set(map(lambda e: e["deprel"], lastInRC.deps))
                if not any(e.endswith((":as",":like",":than")) for e in ee) and not (lastInRC.deprel=="conj" and lastInRC.parent.upos==lastInRC.upos):
                    strandfront += "-auxstrand"
                    assert (lastInRC.misc["Promoted"]=="Yes") ^ (lastInRC.parent is wh and lastInRC.deprel in ("cop","aux","aux:pass")),(lastInRC,edeprels)
                break

    basic_pred.misc["Cxn"] += "rc-" + rctype + "-" + edeprelsS + strandfront
' write.Conllu
