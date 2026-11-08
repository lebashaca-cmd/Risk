# Variables

Variables are placeholders you type inside a message. Risk swaps each one for the real value when the message is sent. They work in welcome and leave messages, level-up messages, auto-replies, custom commands and more. The [message templates](messages) page explains where each one works.

There are {{count}} variables. Type `!variables` in Discord for the same list, `!variables Server` for one group, and `!testvars <message>` to see a message with the values filled in.

## How to use them

- Wrap the name in curly braces: `{server}`.
- They are not case sensitive.
- An unknown variable is left as typed.
- Variables with a colon take a value after it: `{random:1-100}` and `{choose:red|green|blue}`.
- Times marked "shown in each reader's own time zone" use Discord's time display, so everyone sees their own local time.

{{variables}}
