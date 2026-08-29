# Current decisions and inputs

The initial corpus, voice fingerprint, target JDs, creator watchlist, market
templates, and self-performance report are already seeded. The next decisions
are operational; do not add personal material unless you choose to do so.

## 1. Improve x-factor coverage

After repairing timestamp normalization, the existing 225-post batch produces
82 non-null x-factors. The calculation requires at least ten recent
self-excluded posts from the same author. Keep the current `maxPosts` setting;
increase it only if a future pull needs deeper author-level history.

## 2. Handle pre-graph profile drafts

Two existing queue drafts were not produced through router → ground → write →
gate → human approval → commit. Choose one action before relying on them:

- delete them;
- quarantine them outside `drafts/queue/`; or
- recreate them through the graph after the profile-rewrite coverage gate passes.

## 3. Add approved personal memory

Mem0 Platform is wired as optional profile context. It stores only individual
facts or writing preferences typed and approved in the app; it never ingests the
private corpus, drafts, or raw requests. A stable opaque `MEM0_USER_ID` is
configured locally; add the first approved fact in the **Personal memory** panel.
Memory is not evidence and cannot widen the claim allowlist.

If LangSmith tracing remains enabled, profile-memory text is withheld from model
prompts until you explicitly set `MEM0_ALLOW_LANGSMITH_TRACING=true`. That second
approval is required because the retrieved memory would otherwise appear in
dashboard prompt traces.

## 4. Maintain the corpus safely

When you have a new verified story, metric, or voice sample, add it yourself to
the ignored `private/` corpus, rebuild the relevant index/fingerprint, and
rerun the verification suite. Do not place credentials or personal corpus files
in git.

## 5. Security follow-up

Rotate any credential that was ever exposed in a traceback, terminal scrollback,
or tracked file. Removing a value from the working tree cannot revoke an
already-exposed key.
