---
title: economy_more.py
date: 2026-11-05
tags: [risk, cog]
---

# economy_more.py

Cog file `cogs/economy_more.py` (494 lines).

- File: `discord-bot-python/cogs/economy_more.py` (494 lines)
- Classes: `HighLowView`, `HeistView`, `EconomyMore`
- Data files: `data/lottery.json`
- Environment variables: none
- Background loops: `lottery_loop` (every(minutes=5))
- Event listeners: none

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `dicebet` | `diceroll` | Bets on the number a die will land on. A correct guess pays 5 to 1. Usage: !dicebet 100 4 |  |
| `gift` |  | Gives one of your shop items to another member. Usage: !gift @user padlock 1 |  |
| `heist` |  | Starts a bank heist that others can join for 45 seconds. Usage: !heist |  |
| `highlow` | `hl` | Guesses higher or lower to build a streak, then cash out. Usage: !highlow 200 |  |
| `hunt` |  | Hunts animals with a rifle for coins. Usage: !hunt |  |
| `lottery` | `lotto` | Shows the lottery pot and your tickets. Actions: buy, info, draw. Usage: !lottery |  |
| `lottery_buy` |  | Buys lottery tickets for 100 coins each (up to 50 per person). Usage: !lottery buy 5 |  |
| `lottery_draw` |  | Draws the lottery now (staff only). Usage: !lottery draw | has_permissions |
| `lottery_info` | `pot` | Shows the pot, the next draw and the last winner. Usage: !lottery info |  |
| `networth` | `nw` | Shows wallet, bank and item value added together. Usage: !networth @user |  |
| `scratch` | `scratchcard` | Scratches a card with 3 hidden boxes. Match symbols to win. Usage: !scratch 50 |  |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
