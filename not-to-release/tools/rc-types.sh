#!/bin/bash
# e.g., cat en_ewt-ud-train.conllu | bash rc-types.sh > train.conllu
export PATH="$HOME/.local/bin/:$PATH"
udapy util.Eval node='if node.deprel in ("acl:relcl","advcl:relcl"):
    """
    Indicate relative clause subtype. Adds in the MISC column a Cxn (construction) label of the form

        rc-TYPE-DEPRELPATH
    
    TYPE is one of: free, red [reduced], wh, that, cleft.{red,wh,that} (for it-clefts)

    DEPRELPATH is an underscore-separated list of one or more deprels
    indicating the understood role of the relativized element within the relative clause.
    These are derived from the enhanced dependencies graph (but omit lexicalization like ":from").
    The path is bottom-up, ending when the relative clause predicate is reached.
    If the predicate itself is directly relativized, then the path consists of "pred".

    Examples:
        - rc-wh-nsubj for "the boy who lived"
        - rc-red-obj for "all you need (is love)"
        - rc-free-nsubj for "what happens in Vegas (stays in Vegas)"
        - rc-that-obj_xcomp for "somebody that I used to know"
        - rc-cleft.red_obl for "who is it he asked for?"
        - rc-free-pred for "(doing) what they can"
        - rc-red-pred for "a panel I will be on"
    
    TODO: add P stranding/fronting info

    Many reduced RCs lack an enhanced deprel for the relativized element,
    so "missingedep" serves as a placeholder.

    Most frequent in training data:

    581 rc-red-missingedep
    438 rc-wh-nsubj
    308 rc-that-nsubj
    113 rc-that-obj
     93 rc-wh-obl
     77 rc-free-obj
     50 rc-wh-nsubj:pass
     50 rc-that-nsubj:pass
     35 rc-wh-csubj
     27 rc-red-obj
    """
    basic_pred = node
    rctype = ""
    head = basic_pred.parent    
    assert head.precedes(basic_pred)
    wh = None   # relativizer if present

    if node.deprel=="advcl:relcl" and any(ch.deprel=="expl" and ch.lemma=="it" for ch in head.children):
        rctype = "cleft."
    elif head.feats["PronType"]=="Rel":
        rctype = "free"
    # sibs = pred.children
    # node.siblings(following_only=True)
    if rctype != "free":
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

    if basic_pred.misc["Promoted"]=="Yes":
        edeprels.append("pred") # note that this does not capture all cases of predicate anaphora: if it is embedded in a deeper layer ("which I think it does") it will have a regular deprel (ccomp)
    else:
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

    basic_pred.misc["Cxn"] += "rc-" + rctype + "-" + edeprelsS
' write.Conllu
