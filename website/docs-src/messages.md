# Message templates

Several features send a message you write yourself: welcome and leave messages, level-up messages, auto-replies, custom commands and the VIP welcome DM. You can drop **variables** into any of them, and Risk fills in the real values when the message is sent.

## The basics

A variable is a word in curly braces, like `{server}`. If you write

```
Welcome to {server}, {name}! We now have {server.members} members.
```

Risk sends something like `Welcome to Risk HQ, Sam! We now have 1,204 members.`

Rules that always apply:

- Variables are not case sensitive, so `{Server}` and `{server}` are the same.
- A variable Risk doesn't know is left exactly as you typed it, so you will spot typos.
- Names and text from members are made safe, so a member called `@everyone` can never ping anyone.
- You can use as many variables as you like in one message.

See the full list on the [variables](variables) page, or type `!variables` in Discord.

## Sending as an embed

Put `{embed}` at the very start and the very end of a message to send it as an embed instead of plain text:

```
{embed}Welcome {user} to {server}!{embed}
```

In an embed the member appears in bold with their picture, and the real mention is sent above the embed so they still get the notification. Embeds use your VIP accent colour when the server has one.

## Which variables work where

| Place | Notes |
|---|---|
| Welcome message | Write `New_user` where the member goes. All other variables work |
| Leave message | Write `New_user` for the name. Leave messages never ping |
| Level-up message | `{user}`, `{name}`, `{level}`, `{nextlevel}`, `{xp}` and `{messages}` plus all the others |
| Auto-replies | `{user}` is the member's name, and all the others work |
| VIP custom commands | `{user}` is a mention, and all the others work |
| VIP welcome DM | `{user}` is the member's name |

## Ideas

- A welcome with a counter: `{embed}{party} Welcome {user}! You are the {ordinal} member of {server}.{embed}`
- A level-up with progress: `{star} {user} reached level {level} with {xp} XP. Next stop: level {nextlevel}.`
- A random auto-reply: `{choose:Yes|No|Maybe|Ask again later}`
- A dice command: `You rolled a {random:1-20}!`
- A server card reply: `{server} has {server.humans} people and {server.bots} bots. Created {server.created}.`

## Try before you publish

`!testvars <your message>` shows the result using you as the member. It works in any channel, so test as often as you like. `!levelmessage` also shows a preview as soon as you save a new level-up message.
