# Current decisions and inputs

The initial corpus, voice fingerprint, target JDs, creator watchlist, market
templates, and self-performance report are already seeded. The next decisions
are operational; do not add personal material unless you choose to do so.

## 1. Improve x-factor coverage

The last batch produced 225 posts with no non-null x-factors. The calculation
requires at least ten recent self-excluded posts from the same author. Choose a
higher `maxPosts` value for the watchlist and rerun the batch market pipeline if
author-level baselines are needed.

## 2. Handle pre-graph profile drafts

Two existing queue drafts were not produced through router → ground → write →
gate → human approval → commit. Choose one action before relying on them:

- delete them;
- quarantine them outside `drafts/queue/`; or
- recreate them through the graph after the profile-rewrite coverage gate passes.

## 3. Decide memory scope before adding a memory layer

Define which user-authored facts may persist across runs, where they are stored,
and whether any content may leave the local machine for embeddings or retrieval.
The existing `private/` corpus remains the source of truth; a memory layer must
not invent facts, bypass the claim allowlist, or write account/person records.

## 4. Maintain the corpus safely

When you have a new verified story, metric, or voice sample, add it yourself to
the ignored `private/` corpus, rebuild the relevant index/fingerprint, and
rerun the verification suite. Do not place credentials or personal corpus files
in git.

## 5. Security follow-up

Rotate any credential that was ever exposed in a traceback, terminal scrollback,
or tracked file. Removing a value from the working tree cannot revoke an
already-exposed key.
