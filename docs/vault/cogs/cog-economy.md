---
title: economy.py
date: 2026-11-05
tags: [risk, cog]
---

# economy.py

Cog file `cogs/economy.py` (213 lines).

- File: `discord-bot-python/cogs/economy.py` (213 lines)
- Classes: `Economy`
- Data files: `data/economy.json`
- Environment variables: none
- Background loops: none
- Event listeners: none

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `addmoney` |  | Adds or removes coins from someone's wallet. Usage: !addmoney @user 1000 | Administrator |
| `balance` | `bal` | Shows a wallet and bank balance. Usage: !balance @user |  |
| `bet` | `gamble` | Bets on a coin flip. Win to double it. Usage: !bet 100 heads |  |
| `daily` |  | Claims your daily coins. Keep a streak for a bonus. Usage: !daily |  |
| `deposit` | `dep` | Moves coins from your wallet to your bank. Usage: !deposit 500 |  |
| `give` | `pay` | Gives some of your wallet coins to someone. Usage: !give @user 100 |  |
| `slots` |  | Spins the slot machine. Usage: !slots 100 |  |
| `withdraw` | `with` | Moves coins from your bank to your wallet. Usage: !withdraw 500 |  |
| `work` |  | Works a shift for coins once an hour. Usage: !work |  |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
