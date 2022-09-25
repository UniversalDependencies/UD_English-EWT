#!/bin/bash
# e.g., cat en_ewt-ud-train.conllu | bash be-ccomp.sh > train.conllu
export PATH="$HOME/.local/bin/:$PATH"
udapy util.Eval node='if node.deprel=="ccomp" and node.parent.lemma=="be":
	cop = node.parent
	if not any(n for n in cop.children if n.deprel in ["expl", "compound:prt"]):
		head = cop.parent
		
		def edep_with_head(n, h, rprefix):
			ee = [d for d in n.deps if d["parent"] is h]
			if len(ee)!=1:
				# could be a relativizer, so edeprel is "ref"
				return None
			d, = ee
			assert d["deprel"].startswith(rprefix),(rprefix,d)	# enhancement may contain :suffix
			return d
	
		# move other dependents of copula (modifiers/subjects) under node
		esubjs = []
		for mod in cop.children:
			if mod is not node:
				# REL(cop,mod) -> REL(node,mod) and enhanced equivalent
				mod.parent = node
				d = edep_with_head(mod, cop, mod.deprel)
				if d is None:
					d, = mod.deps
					assert d["deprel"]=="ref"
					# resolve ref
					ref = d["parent"]
					d = edep_with_head(ref, cop, mod.deprel)
				else:
					ref = mod
				d["parent"] = node
				if "subj" in d["deprel"]:
					esubjs.append((d["deprel"], ref))
					d["deprel"] += ":outer"
		rel = cop.deprel
	
		# rel(head,cop), ccomp(cop,node) -> rel(head,node), cop(node,cop)
		cop.deprel = "cop"
		node.parent = head
		cop.parent = node
		node.deprel = rel
		d = edep_with_head(cop, head, rel)
		d["parent"] = node	# modify the edep in place
		erel = d["deprel"]	# enhanced, e.g. conj:and
		d["deprel"] = "cop"
		d = edep_with_head(node, cop, "ccomp")
		d["parent"] = head
		d["deprel"] = erel
		
		cop.upos = "AUX"	# was "VERB"
		
		eccomps = [node]
		
		# look for edeprels on other tokens, e.g. due to coordination, that also need updating
		for n in node.root.descendants:
			for d in n.deps:
				if d["parent"] is cop:
					if d["deprel"]=="ccomp":
						d["parent"] = head
						d["deprel"] = erel
						eccomps.append(n)
					else:
						d["parent"] = node
						if "subj" in d["deprel"]:
							esubjs.append((d["deprel"], n))
							d["deprel"] += ":outer"
		
		# propagate subjects across possibly coordinated clausal predicates (prior ccomps)
		for eccomp in eccomps:
			for (esubjrel,esubj) in esubjs:
				d = edep_with_head(esubj, eccomp, esubjrel)
				if d is None:
					esubj.deps.append({"parent": eccomp, "deprel": esubjrel+":outer"})
' write.Conllu
