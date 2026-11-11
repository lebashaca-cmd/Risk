# Utility, fun and lookups

## Info

`!ping` checks the response time, `!uptime` shows how long Risk has been online, `!botinfo` shows its stats, `!invite` gives the link to add it, `!prefix` shows or changes the server prefix, `!dashboard` gives the dashboard link and `!tos` and `!privacy` show the policies.

## Server and user info

`!serverinfo`, `!userinfo`, `!roleinfo`, `!channelinfo`, `!avatar`, `!banner`, `!servericon`, `!serverbanner`, `!membercount`, `!roles`, `!emojis`, `!emojiinfo`, `!inrole @Role`, `!whohas`, `!admins`, `!bots`, `!boosters`, `!newest`, `!oldest`, `!joined` and `!permissions`.

## Everyday tools

| Goal | Command |
|---|---|
| Reminders | `!remindme 1h take out the trash`, `!reminders` |
| Personal to-do list | `!todo add buy milk`, `!todo list`, `!todo done 1` |
| Away message | `!afk lunch` |
| Polls | `!poll Pizza \| Tacos` (a question, or options split by a bar) |
| Embeds | `!embed #news Title \| The text` (Manage Messages) |
| Countdown | `!countdown` to a UTC date and time, `!daysuntil` |
| Timestamps | `!timestamp`, `!epoch`, `!snowflake` |
| Math and converters | `!calc 2*(3+4)`, `!convert`, `!base64`, `!binary`, `!hash`, `!uuid`, `!password`, `!qr text`, `!color`, `!palette` |
| Text tools | `!uppercase`, `!lowercase`, `!titlecase`, `!slugify`, `!urlencode`, `!wordcount`, `!leetspeak`, `!morse`, `!caesar`, `!rot13`, `!roman` |
| Emoji | `!enlarge`, `!addemoji`, `!removeemoji` |
| Variables | `!variables` lists them and `!testvars` previews a message |

## Lookups

`!weather Chicago`, `!define serendipity`, `!wiki`, `!crypto`, `!pypi` and `!age` use public sources and need no setup.

Four commands look up profiles on other sites: `!github`, `!spotify`, `!youtube` and `!tiktok`. They need the bot's host to have a lookup service key. If they say a key isn't set, the person running the bot has to add it.

## Ask the AI

`!ask your question` sends a question to an AI model and replies with the answer. Code comes in code blocks and long answers can come as a file. There is a short cooldown per person, and the command says so if the AI service is busy or its key isn't set.

## Fun

There are more than 70 fun commands: games like `!tictactoe`, `!connect4`, `!hangman`, `!trivia`, `!rps`, `!mathrace`, `!typing`, `!guess`, `!reactiontest`, `!russianroulette` and `!duel`; jokes and facts like `!joke`, `!dadjoke`, `!fact`, `!catfact`, `!riddle` and `!fortune`; reactions like `!hug`, `!pat`, `!slap`, `!wave` and `!highfive`; and silly tools like `!8ball`, `!ship`, `!rate`, `!roast`, `!compliment`, `!emojify`, `!mock`, `!uwu` and `!wheel`. Browse them all in the [Fun commands](commands-fun).

## Good to know

- Every command here is open to everyone unless the reference says otherwise.
- Staff can switch any command off or restrict it with [command rules](command-rules).

## AI helpers

These use the same free Groq key as `!ask` (`GROQ_API_KEY` on the bot host). The text you give a command, or the recent messages for `!catchup`, is sent to the AI service to write the answer, so don't use them for anything private.

| Command | What it does |
| --- | --- |
| `!summarize <text>` (`!tldr`) | Short bullet summary of the text, or of the message you reply to |
| `!catchup 40` | Summarizes the last messages in the channel (10 to 80), so you can catch up |
| `!translate spanish <text>` | Translates into a language. Quote two-word languages: `"brazilian portuguese"` |
| `!explain <topic>` (`!eli5`) | Explains something simply with an analogy |
| `!rewrite formal <text>` | Rewrites text in a style such as formal, casual or shorter |
| `!grammar <text>` | Fixes spelling and grammar and lists what changed |
| `!ideas <topic>` | Eight ideas for anything |
| `!story <prompt>` | A short all-ages story |
| `!proscons <topic>` | Pros, cons and a verdict |
| `!suggestreply <message>` | Three ways to reply: friendly, direct and funny |
| `!aiquiz <topic>` | A five question quiz with the answers hidden in spoilers |
| `!explaincode <code>` | What a piece of code does, and any obvious bug |

Each person can use these once every 8 to 20 seconds. Where a command takes text, you can reply to a message instead of typing it.
