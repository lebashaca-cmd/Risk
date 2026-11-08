# Getting started

This page takes you from nothing to a working server in a few minutes. You need the Manage Server permission on the server you want to add Risk to.

## 1. Add Risk to your server

1. Use the **Add to server** button on the main site.
2. Pick your server and keep every permission ticked. Risk asks only for what its features need, and a missing permission is the most common reason a command fails.
3. Open your server's role list and drag Risk's role **above** any roles it should manage (level rewards, autorole, verify). Discord only lets a bot manage roles that sit below its own.

## 2. Try a command

Type `!ping` in any channel. Risk answers with its response time. If nothing happens, check that Risk can see and send in that channel, then read [Troubleshooting](faq).

Type `!commands` to see the categories, or `!help <command>` for details on one command.

## 3. Open the dashboard

Type `!dashboard` and open the link, then sign in with Discord. You will see every server where you have Manage Server and Risk is present. Pick one to change its settings. The [dashboard guide](dashboard) explains each section.

## 4. Set up the basics

A good first ten minutes:

1. **Welcome message.** `!welcome #welcome {embed} Welcome New_user to {server}! {embed}` greets new members. See [Welcome and leave](welcome).
2. **Log channel.** `!logchannel` and the log commands record joins, leaves, edits, deletes and moderation. See [Server logs](logs).
3. **Auto-mod.** Turn on `!antilink on`, `!antispam on` and `!maxmentions 5` if you want automatic filtering. See [Moderation](moderation).
4. **Level rewards.** `!levelreward 10 @Regular` gives a role at level 10. See [Levels](levels).
5. **Autorole.** `!autorole set @Member` gives new members a role as they join.

## 5. Change the prefix (optional)

`!prefix $` adds `$` as an extra prefix for your server. The defaults `!`, `?` and `,` keep working, so nobody gets locked out. In the dashboard it is under General.

## Next steps

- Browse [all commands](commands).
- Make messages your own with [message templates](messages) and [variables](variables).
- Run a support desk with [tickets](tickets).
- Look at [VIP](vip) if you want custom commands, scheduled announcements and more.
