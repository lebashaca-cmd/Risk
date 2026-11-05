---
title: Dashboard frontend structure
date: 2026-11-05
tags: [risk, dashboard, frontend]
---

# Dashboard frontend structure

TypeScript in `website/src/`, compiled with `npx tsc -p .` to `website/web/assets/js/` (committed). No framework: a small `h()` helper in `dom.ts` builds elements, and each view returns `{ node, cleanup }`.

| File | Role |
|---|---|
| `dashboard.ts` | Server list, the editor with tabs, drafts and dirty tracking, save bar, sign-in messages |
| `dash-extra.ts` | Overview, Command rules, Auto-replies, Announcements and VIP tabs |
| `dash-profile.ts` | The bot profile card with live preview |
| `dash-ui.ts` | Form widgets: toggle, text, number, select, channel and role pickers, tag editor, file import, lock and VIP badge |
| `dash-types.ts` | Types for every payload |
| `api.ts` | `dashApi` calls and `ApiFailure` |
| `app.ts` | Routing and the nav |

## How a tab is built

A renderer receives the draft for its section, the server `meta`, a `changed()` callback and a context, and returns elements. The editor keeps a draft per section, compares it with the saved copy to show unsaved changes, and saves one section at a time. Read-only tabs (Overview) hide the save bar. The `status` object keeps "Saved." visible after a save.

## Styling

`site.css`, grey and white. Dashboard classes start with `dash-`; the profile card uses `pf-`. A rule `.dash [hidden]{display:none!important}` makes the `hidden` attribute work for filters.

Related: [Website file map](../website/file-map.md), [Adding a dashboard section](../guides/add-a-dashboard-section.md)
