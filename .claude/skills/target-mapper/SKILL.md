---
name: target-mapper
description: Produce a guided, manual people-map for an applied-to target role.
---

# Target mapper

Read the JD and extract team, role, location, and likely reporting chain. Give the user the
manual LinkedIn sequence: company page → People → location → `product management` (or target
function); if results are thin, remove location and use the team keyword. Ask the user to paste
the likely people back.

Create `corpus/targets/companies/<company>.md` from the template with separate probable hiring
managers and peers. Only use public/manual research. Do not automate people searches, connection
requests, DMs, or follow-ups.
