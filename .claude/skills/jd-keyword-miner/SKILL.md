---
name: jd-keyword-miner
description: Mine one focused job family into a truthful keyword brief; stop if the role set is scattered.
---

# JD keyword miner

Read at least five files in `corpus/targets/jds/`. Extract meaningful phrases, normalize close
variants, and count coverage by distinct JD rather than raw repetition.

## Hard focus gate

1. Group JDs into two or three role clusters using role title, required outcomes, and recurring
   skills.
2. Let significant terms exclude generic words such as `team`, `work`, and `experience`.
3. Calculate `coverage = terms appearing in >=4 of 5 JDs / distinct significant terms`.
4. If coverage is below `0.75`, stop. Name the clusters, show the conflicting terms, ask the
   user to choose one cluster, and do **not** write a profile or a final brief.

## Output

Save `corpus/targets/briefs/YYYY-MM-DD-role-keywords.md` with:

- input JDs and role family;
- coverage result and focus decision;
- keyword categories: role/domain, product, methods, outcomes, tools, leadership/stage;
- frequencies and exact JD phrasing worth preserving;
- skills to list, outcomes hiring managers actually need, and honest gaps;
- a short positioning recommendation grounded only in the JDs and the corpus.

Never inflate an unverified skill into experience. A gap is useful information, not a drafting
problem to hide.
