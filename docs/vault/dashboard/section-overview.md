---
title: Dashboard: Overview
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: Overview

Read only landing tab.

## What it holds

`stats` (members, people, bots, text and voice channels, roles, emojis, boost tier and boosts, created, owner), `checklist` (8 steps: welcome, log channel, an auto-mod rule, level rewards, auto role, ticket log channel, an auto-reply, a command rule, each with the tab it opens), `usage` (switched-off commands, rules, auto-replies, announcements, log types on), `activity` (the last 10 saves).

## Where it is stored and how it is applied

Nothing to save. It is rebuilt on every load from the other sections, so it never goes stale.

## Rules and edge cases

Cannot be written: a PUT to `overview` answers 404.

API: `GET /api/dash/guild/<id>` returns this section under `settings.overview`. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
