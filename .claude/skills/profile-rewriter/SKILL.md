---
name: profile-rewriter
description: Rewrite a LinkedIn profile for a focused target role, using only retrieved verified evidence.
---

# Profile rewriter

Read `corpus/profile/current.md`, `corpus/identity/{positioning,icp,pillars,truth-table,voice}.md`,
the latest keyword brief, and the reference files in this skill. If no focused keyword brief or
positioning exists, stop and ask for those inputs rather than guessing a career target.

## Evidence gate

- Every number/result must come from the truth table or a retrieved story metric marked
  `verified: true`.
- Use `[bracketed gaps]` where proof is absent. Never replace a missing outcome with invented
  precision.
- Draft three headline/about variants, then explain the tradeoff in one line each.

## Deliverable

Write a reviewable proposal to `drafts/queue/YYYY-MM-DD-profile-v1.md`; never overwrite the
current profile. Include headline, banner line, About, experience rewrites, skill strategy,
Featured suggestion, custom-URL check, and a list of facts the user must verify. After the user
ships it, snapshot the exact live text in `corpus/profile/versions/`.
