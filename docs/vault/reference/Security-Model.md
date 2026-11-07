---
title: Security model
date: 2026-11-05
tags: [risk, reference, security]
---

# Security model

- **Who can change settings**: Administrator, Manage Server or owner, checked by the bot on every request from the live guild, not from the website's session.
- **Shared key**: `X-Dashboard-Key` between site and bot, at least 16 characters, compared in constant time. Without a key the bot refuses all dashboard calls.
- **Sessions**: random ids in memory, cookie `risk_session` (HttpOnly, SameSite, Secure when on HTTPS). Lost on restart.
- **OAuth**: random `state` in a cookie, checked on return. The access token is revoked right after use. Only `identify` and `guilds` scopes.
- **CSRF**: writes need `X-Requested-With: risk` and a same-origin Origin header.
- **CSP**: no inline script, no eval, connections only to the site itself.
- **Input**: every field validated; ids must exist in the server; images checked by signature and size.
- **Mentions**: auto-replies, announcements and templates use restricted allowed mentions so a setting cannot ping everyone.
- **Secrets**: only in environment variables on the two hosts, never in the repo or the zip.
- **Privacy**: the privacy policy on the site lists what is stored, including dashboard sessions and VIP status.

Related: [Dashboard validation rules](../dashboard/validation-rules.md), [Sign-in flow](../dashboard/sign-in-flow.md)
