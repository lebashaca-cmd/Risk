# Stream alerts

Risk announces when someone in your server, or a streamer you follow, goes live. The alert is an embed titled "<name> is live" with a link to the stream. When the stream ends, Risk posts a "stopped streaming" embed with how long it lasted.

## Turn it on

`!streamalerts #streams @StreamPing` picks the channel. The role at the end is optional. Turn alerts off with `!streamalerts off`. `!streamrole @Streams` sets or clears the ping role later.

Run `!streamtest` to post a sample alert and check that the channel and role are right.

## Where alerts come from

| Source | What you do | Notes |
|---|---|---|
| Discord Go Live (screen share in a voice channel) | Nothing | The alert links to the voice channel |
| Discord "Streaming" status | The bot's host must enable the presence setting | If the status links to Twitch, the alert shows the live preview |
| Twitch channels | `!twitchadd shroud @StreamPing` | Checked about every minute. Shows the live preview |
| TikTok accounts | `!tiktokadd @name @StreamPing` | Unofficial, so it can stop working if TikTok changes. Checked about every 90 seconds, 25 accounts per server |

A role you give to `!twitchadd` or `!tiktokadd` is used for that streamer instead of the server-wide role.

Remove a streamer with `!twitchremove` or `!tiktokremove`, and list them with `!twitchlist` and `!tiktoklist`.

## Checking things

- `!twitchtest <channel>` checks one Twitch channel right now and shows what the alert would look like.
- `!tiktoktest @name` checks one TikTok account right now and says what Risk sees. Run it while the person is live.
- `!streaming` shows who is streaming now, `!streamstats @user` one member's total, and `!streamers` ranks members by time streamed.

## Good to know

- TikTok has no public live API, so Risk reads the same page data the TikTok website uses. If that is blocked or changes shape, Risk keeps the previous state instead of guessing, so you may miss alerts rather than get false ones.
- The Twitch and Discord status sources need setup on the bot's side. If `!twitchtest` says it isn't configured, the person running the bot has to add Twitch keys.
