#!/bin/bash
mkdir -p orig
for f in *.conllu; do
    cp $f orig/$f;
done

# The check_paired_punct_upos=1 parameter prevents touching anything else than PUNCT,
# so it prevents creating e.g.
#   │ ╰─┾ Constellation NOUN appos
#   │   ┡─╼ Power X flat
#   │   │ ╭─╼ ( X flat
#   │   ┡─┶ GISB X flat
#   │   ┡─┮ draft X flat
#   │   │ ╰─╼ ) X flat
#   │   ╰─╼ .doc X flat

udapy \
  read.Conllu files='!*.conllu !not-to-release/sources/*/*.conllu' \
  ud.FixPunct check_paired_punct_upos=1 \
  write.Conllu overwrite=1

for f in *.conllu; do
    udapy -HM \
      read.Conllu files=$f zone=fixed read.Conllu files=orig/$f zone=orig \
      util.MarkDiff gold_zone=orig \
    > diff-${f%.conllu}.html
done
