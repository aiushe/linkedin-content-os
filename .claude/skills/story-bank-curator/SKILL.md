---
name: story-bank-curator
description: Turn newly discussed career material into reviewable, truthful story-bank entries.
---

# Story-bank curator

At session end, scan the conversation/draft for events not already in `corpus/stories/`.
For each candidate, extract tension → turn → result → lesson and ask for metric, proof, date,
role context, and pillar. Create a file from `corpus/stories/_TEMPLATE.md`; mark all unknown
metrics `verified: false`.

Never delete or merge existing stories without a human decision. Run `pipeline/index_corpus.py`
after accepted additions and list what still needs verification.
