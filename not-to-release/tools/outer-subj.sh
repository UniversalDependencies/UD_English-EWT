#!/bin/bash
# e.g., cat en_ewt-ud-train.conllu | bash be-ccomp.sh > train.conllu
export PATH="$HOME/.local/bin/:$PATH"
udapy util.Eval node='if node.deprel in ("nsubj","csubj"):
    """
    Mark a subject with :outer
      - before another nsubj or csubj (:outer1)
      - before a pre-head expl (:outer2)
      - before a cop dependent of a VERB/AUX (:outer3)
      - before the first of two cop dependents of a predicate (:outer4)
    Basic deps only for now.
    
    This produces some false positives, e.g. due to participles tagged as VERB
    with a cop dependent. For EWT, which already distinguished most outer subjects
    by treating the copula as head, the approach was to
    (1) run be-ccomp.sh to add :outer to all the edeprels
    (2) run this script to add :outer[1-4] to the basic deprels
    (3) look for lines with one but not the other. A few were annotation errors
    to fix manually in the original data. A few legitimate differences, e.g. with
    relativizer subject "which" (:outer belongs on the edeprel of the antecedent).
    There are several participial predicates that should NOT trigger :outer
    (https://github.com/UniversalDependencies/UD_English-EWT/issues/355).
    (4) rerun be-ccomp.sh on the corrected original file
    (5) do a regex search/replace to copy :outer from the edeprel into the basic dep
    if the basic dep is a subject
    (6) deal manually with tokens whose edeprel has :outer but basic dep is not a subject.
    Some are due to coordination. For others, :outer should be added to the basic dep
    for the "which" relativizer.
    
    Also note that there will be additional tokens which should have an :outer edeprel
    but not basic deprel (due to coordination). This script will not find those,
    but be-ccomp.sh should.
    """
    
    pred = node.parent
    sibs = pred.children
    for s in node.siblings(following_only=True):
    	if s.deprel in ("nsubj","nsubj:pass","nsubj:outer","csubj","csubj:pass","csubj:outer"):
    		node.deprel += ":outer1"
    		break
    	elif s.deprel=="expl" and s.precedes(pred):
    		node.deprel += ":outer2"
    		break
    	elif s.deprel=="cop" and s.precedes(pred) and pred.upos in ("VERB","AUX"):
    		node.deprel += ":outer3"
    		break
    	elif s.deprel=="cop" and any(s2 for s2 in s.siblings(following_only=True) if s2.deprel=="cop"):
    		node.deprel += ":outer4"
    		break
' write.Conllu
