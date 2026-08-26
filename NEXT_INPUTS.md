# What I need from you next

The reusable system is built. Do these in order; none require sharing credentials in chat.

## 1. Pick the target (required before profile work)

- Target role and niche: **domain, product type, superpower, company stage**.
- Whether you are actively job searching or building presence while employed.
- Realistic posting days and weekly time budget.
- A virality threshold appropriate to your niche (the default is 750 likes).

## 2. Seed the truth corpus (required before any factual drafting)

- Paste your complete live profile into `corpus/profile/current.md`.
- Add your current/long-form résumé.
- Add five target JDs for the *same* role family to `corpus/targets/jds/`.
- Fill `corpus/identity/truth-table.md` with every claim/metric, supporting proof, and date.
- Book a 90-minute story-bank interview. We will turn your answers into 15–25 files from
  `corpus/stories/_TEMPLATE.md`; imperfect or unverified metrics are fine when marked as such.

## 3. Capture your voice (required before relying on draft automation)

- Add at least ~5,000 words of real writing to `corpus/identity/voice/samples/` (10,000 is
  ideal): thoughtful emails, docs, post-mortems, Slack/Discord, or voice-note transcripts.
- Mark 3–5 pieces you love in `corpus/identity/voice/exemplars/`.
- Add rejected AI writing in `corpus/identity/voice/negative/`, with a one-line note on why it
  fails your voice.
- Then run `uv run python pipeline/voice.py fingerprint`.

## 4. Add market intelligence only when ready (optional at first)

- Create `.env` from `.env.example`; keep `APIFY_API_TOKEN` and `VOYAGE_API_KEY` there, never
  in git or chat.
- Use Apify MCP to inspect a public-post actor’s schema, price, and proxy/session behavior;
  choose an actor only after review. Do not provide your LinkedIn session cookie.
- Add a 20–40 person public creator watchlist based on your pillars. Start with one creator,
  save the actor result into `intel/raw/`, normalize it, then compute x-factors.
- Add Voyage only once the story bank/intel has grown enough that metadata filtering is no
  longer convenient.

## First reply to send me

Send the four-axis target role plus whether you are job hunting now. I’ll then start the
one-question-at-a-time story-bank interview and help seed the corpus.
