# Current decisions and inputs

The initial corpus, voice fingerprint, target JDs, creator watchlist, market
templates, and self-performance report are already seeded. The next decisions
are operational; do not add personal material unless you choose to do so.

## 1. Improve x-factor coverage

After repairing timestamp normalization, the existing 225-post batch produces
82 non-null x-factors. The calculation requires at least ten recent
self-excluded posts from the same author. Keep the current `maxPosts` setting;
increase it only if a future pull needs deeper author-level history.

## 2. Configure the confidential-terms gate

Before queueing a real draft, copy the tracked
`corpus/identity/confidential-terms.md` format into the ignored
`private/confidential-terms.md` and add the terms you want surfaced for review. The
check reports an indeterminate advisory result until that explicit configuration
exists; this agent will not create or fill the private list.

The two pre-graph profile drafts were quarantined in `drafts/ungated/`; regenerate
them through the full graph before moving any replacement into `drafts/queue/`.

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

When you have a new verified story, metric, voice sample, or an own-post pull, add it yourself to
the ignored `private/` corpus, rebuild the relevant index/fingerprint, and
rerun the verification suite. Do not place credentials or personal corpus files
in git. For own-post performance, pass your own public handle explicitly to
`pipeline/normalize.py --my-handle`; the system never guesses it.

## 5. Security follow-up

Rotate any credential that was ever exposed in a traceback, terminal scrollback,
or tracked file. Removing a value from the working tree cannot revoke an
already-exposed key.
