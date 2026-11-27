"""Music from voice channels, through a Lavalink server with the Pomice library.

`!play <song or link>` joins your voice channel and plays it. YouTube, YouTube Music, SoundCloud, Spotify and Apple Music
links all work (Spotify needs SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET on the bot). Risk keeps the queue itself, so
loop, shuffle, remove and skip work the same for every source.

The bot owner needs a Lavalink server and these settings in the environment (.env):
    LAVALINK_HOST, LAVALINK_PORT (default 2333), LAVALINK_PASSWORD, LAVALINK_SECURE=true if it uses https/wss.
Without them the commands explain that music isn't set up instead of failing.
"""
import asyncio
import os
import random
import re
import time

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error

try:
    import pomice
    HAVE_POMICE = True
except ImportError:  # the bot still starts without it
    pomice = None
    HAVE_POMICE = False

MAX_QUEUE = 100
MAX_PLAYLIST = 50
IDLE_LEAVE = 180  # seconds with nothing playing before Risk leaves
LOOPS = ("off", "track", "queue")
URL = re.compile(r"https?://\S+")


def clock(ms):
    seconds = int(ms // 1000)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class GuildMusic:
    """What Risk remembers about music in one server."""

    def __init__(self):
        self.queue = []  # tracks waiting, in order
        self.current = None
        self.loop = "off"
        self.channel_id = None  # where "now playing" messages go
        self.idle_task = None
        self.volume = 60


class Music(commands.Cog, name="Music"):
    """Play music in a voice channel: play, queue, skip, loop, volume and more."""

    def __init__(self, bot):
        self.bot = bot
        self.guilds = {}
        self.node_task = None
        self.node = None
        self.problem = None  # why music isn't available, shown to people

    # ------------------------------------------------------------------ setup
    async def cog_load(self):
        self.node_task = asyncio.create_task(self.connect_node())

    def cog_unload(self):
        if self.node_task:
            self.node_task.cancel()
        for state in self.guilds.values():
            if state.idle_task:
                state.idle_task.cancel()

    async def connect_node(self):
        if not HAVE_POMICE:
            self.problem = "Music needs the `pomice` package. The bot owner can install it with `pip install pomice`."
            return
        host, password = os.getenv("LAVALINK_HOST", "").strip(), os.getenv("LAVALINK_PASSWORD", "")
        if not host or not password:
            self.problem = "Music isn't set up on this bot yet. The owner needs a Lavalink server and the `LAVALINK_HOST` and `LAVALINK_PASSWORD` settings."
            return
        await self.bot.wait_until_ready()
        delay = 5
        while True:
            try:
                self.node = await pomice.NodePool.create_node(
                    bot=self.bot, host=host, port=int(os.getenv("LAVALINK_PORT", "2333") or 2333), password=password, identifier="risk-main",
                    secure=os.getenv("LAVALINK_SECURE", "").lower() in ("1", "true", "yes"),
                    spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID") or None, spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET") or None,
                )
                self.problem = None
                print("[music] connected to Lavalink")
                return
            except pomice.NodeCreationError:
                self.problem = None  # already created by an earlier attempt
                return
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.problem = "I can't reach the music server right now. Try again in a minute."
                print(f"[music] Lavalink connection failed ({type(error).__name__}), retrying in {delay}s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 120)

    async def cog_command_error(self, ctx, error):
        original = getattr(error, "original", error)
        if HAVE_POMICE and isinstance(original, (pomice.NodeRestException, pomice.NodeConnectionFailure, pomice.NoNodesAvailable)):
            # the Lavalink node restarted or dropped us: say so instead of dumping a traceback
            print(f"[music] Lavalink node error: {type(original).__name__}: {original}")
            await ctx.send("I lost my connection to the music server. Try that again in a moment - if it keeps happening, the Lavalink server needs a restart.", allowed_mentions=NO_MENTIONS)
            return
        if not await explain_error(ctx, error):
            raise error

    # ------------------------------------------------------------------ helpers
    def state(self, guild_id):
        return self.guilds.setdefault(guild_id, GuildMusic())

    def ready(self):
        if self.problem:
            raise ModError(self.problem)
        if self.node is None:
            raise ModError("Music is still starting up. Try again in a few seconds.")

    def player_of(self, ctx):
        player = ctx.guild.voice_client
        return player if HAVE_POMICE and isinstance(player, pomice.Player) else None

    def need_player(self, ctx):
        """The running player, after checking the person is in the same voice channel."""
        self.ready()
        player = self.player_of(ctx)
        if player is None:
            raise ModError("I'm not playing anything. Start with `" + ctx.clean_prefix + "play <song>`.")
        if ctx.author.voice is None or ctx.author.voice.channel != player.channel:
            raise ModError(f"Join {player.channel.mention} to control the music.")
        return player

    async def join(self, ctx):
        voice = ctx.author.voice
        if voice is None or voice.channel is None:
            raise ModError("Join a voice channel first.")
        mine = voice.channel.permissions_for(ctx.guild.me)
        if not (mine.connect and mine.speak):
            raise ModError(f"I need Connect and Speak in {voice.channel.mention}.")
        player = self.player_of(ctx)
        if player is not None:
            if player.channel != voice.channel:
                raise ModError(f"I'm already playing in {player.channel.mention}. Join that channel to add songs.")
            return player
        if ctx.guild.voice_client is not None:  # some other voice client is stuck
            await ctx.guild.voice_client.disconnect(force=True)
        player = await voice.channel.connect(cls=pomice.Player, self_deaf=True)
        try:
            await player.set_volume(self.state(ctx.guild.id).volume)
        except (pomice.NodeRestException, pomice.NodeConnectionFailure) as error:
            # the node restarted and forgot the voice session, so this player is dead: build a fresh one
            print(f"[music] stale voice session ({type(error).__name__}), rejoining")
            try:
                await player.destroy()
            except Exception:
                pass
            if ctx.guild.voice_client is not None:
                await ctx.guild.voice_client.disconnect(force=True)
            player = await voice.channel.connect(cls=pomice.Player, self_deaf=True)
            await player.set_volume(self.state(ctx.guild.id).volume)
        return player

    def cancel_idle(self, state):
        if state.idle_task:
            state.idle_task.cancel()
            state.idle_task = None

    def schedule_idle(self, guild, player):
        state = self.state(guild.id)
        self.cancel_idle(state)

        async def leave_later():
            try:
                await asyncio.sleep(IDLE_LEAVE)
                if not player.is_playing and not state.queue:
                    await self.stop_all(guild, player)
            except asyncio.CancelledError:
                pass

        state.idle_task = asyncio.create_task(leave_later())

    async def stop_all(self, guild, player):
        state = self.state(guild.id)
        self.cancel_idle(state)
        state.queue.clear()
        state.current = None
        state.loop = "off"
        try:
            await player.destroy()
        except Exception:
            try:
                await guild.voice_client.disconnect(force=True)
            except Exception:
                pass

    def now_embed(self, track, state, title="Now playing"):
        embed = discord.Embed(title=title, description=f"[{track.title[:200]}]({track.uri})" if track.uri else track.title[:200], color=discord.Color.blurple())
        embed.add_field(name="By", value=(track.author or "Unknown")[:100])
        embed.add_field(name="Length", value="Live" if track.is_stream else clock(track.length))
        requester = getattr(track, "requester", None)
        if requester:
            embed.add_field(name="Requested by", value=requester.display_name)
        if state.loop != "off":
            embed.set_footer(text=f"Loop: {state.loop}")
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        return embed

    async def start_next(self, player, announce=True):
        """Plays the next waiting track, or goes quiet and waits to leave."""
        guild = player.guild
        state = self.state(guild.id)
        if not state.queue:
            state.current = None
            self.schedule_idle(guild, player)
            return
        track = state.queue.pop(0)
        state.current = track
        self.cancel_idle(state)
        try:
            await player.play(track)
        except Exception as error:
            print(f"[music] couldn't play a track: {type(error).__name__}")
            state.current = None
            await self.notify(state, f"I couldn't play **{track.title[:80]}**, skipping it.")
            return await self.start_next(player)
        if announce:
            channel = self.bot.get_channel(state.channel_id or 0)
            if channel is not None:
                try:
                    await channel.send(embed=self.now_embed(track, state), allowed_mentions=NO_MENTIONS)
                except discord.HTTPException:
                    pass

    async def notify(self, state, text):
        channel = self.bot.get_channel(state.channel_id or 0)
        if channel is not None:
            try:
                await channel.send(text, allowed_mentions=NO_MENTIONS)
            except discord.HTTPException:
                pass

    # ------------------------------------------------------------------ events from Lavalink
    @commands.Cog.listener()
    async def on_pomice_track_end(self, player, track, reason):
        state = self.state(player.guild.id)
        if str(reason).lower() in ("replaced", "stopped", "cleanup"):
            return  # we stopped it on purpose and already moved on
        if track is not None and state.loop == "track":
            state.queue.insert(0, track)
        elif track is not None and state.loop == "queue":
            state.queue.append(track)
        await self.start_next(player)

    @commands.Cog.listener()
    async def on_pomice_track_stuck(self, player, track, threshold):
        await self.start_next(player)

    @commands.Cog.listener()
    async def on_pomice_track_exception(self, player, track, error):
        state = self.state(player.guild.id)
        await self.notify(state, f"Something went wrong playing **{getattr(track, 'title', 'that track')[:80]}**, skipping it.")
        await self.start_next(player)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Leave when everyone else has left the channel."""
        player = member.guild.voice_client
        if not (HAVE_POMICE and isinstance(player, pomice.Player)) or before.channel is None or before.channel != player.channel:
            return
        if member.id == self.bot.user.id:
            if after.channel is None:  # kicked or disconnected: forget the queue
                state = self.state(member.guild.id)
                self.cancel_idle(state)
                state.queue.clear()
                state.current = None
            return
        if not any(not m.bot for m in player.channel.members):
            await asyncio.sleep(60)
            if player.is_connected and not any(not m.bot for m in player.channel.members):
                await self.stop_all(member.guild, player)

    # ------------------------------------------------------------------ commands
    @commands.command(name="play", aliases=["p"])
    @commands.guild_only()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def play(self, ctx, *, query: str):
        """Plays a song or adds it to the queue. Takes a name or a YouTube, SoundCloud or Spotify link. Usage: !play never gonna give you up | !play https://youtu.be/..."""
        self.ready()
        state = self.state(ctx.guild.id)
        if len(state.queue) >= MAX_QUEUE:
            raise ModError(f"The queue is full ({MAX_QUEUE} songs).")
        player = await self.join(ctx)
        state.channel_id = ctx.channel.id
        query = query.strip().strip("<>")
        async with ctx.typing():
            try:
                result = await player.get_tracks(query, ctx=ctx)
            except pomice.InvalidSpotifyClientAuthorization:
                raise ModError("Spotify links aren't set up on this bot. Try a YouTube or SoundCloud link, or the song's name.")
            except pomice.TrackLoadError:
                raise ModError("I couldn't load that. It may be private, age-restricted or blocked in the music server's region.")
            except pomice.NoNodesAvailable:
                raise ModError("The music server is down right now. Try again in a minute.")
            except Exception as error:
                print(f"[music] search failed ({type(error).__name__}: {error})")
                raise ModError("The search failed. Try different words or a direct link.")
        if not result:
            if not player.is_playing and not state.queue:
                await self.stop_all(ctx.guild, player)
            raise ModError("I found nothing for that. Try different words or a direct link.")
        for track in (result.tracks if isinstance(result, pomice.Playlist) else result[:1]):
            track.requester = ctx.author
        if isinstance(result, pomice.Playlist):
            tracks = list(result.tracks)[:min(MAX_PLAYLIST, MAX_QUEUE - len(state.queue))]
            if not tracks:
                raise ModError("The queue is full.")
            state.queue.extend(tracks)
            summary = f"Added **{len(tracks)}** songs from **{result.name[:80]}**."
        else:
            track = result[0]
            state.queue.append(track)
            summary = None
        if not player.is_playing and state.current is None:
            await self.start_next(player, announce=False)
            first = state.current
            if first is not None:
                await ctx.reply(summary or None, embed=self.now_embed(first, state), mention_author=False, allowed_mentions=NO_MENTIONS)
            return
        if summary is None:
            track = state.queue[-1]
            embed = self.now_embed(track, state, title=f"Added to the queue (#{len(state.queue)})")
            await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)
        else:
            await ctx.reply(summary, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="join", aliases=["summon"])
    @commands.guild_only()
    async def join_command(self, ctx):
        """Makes Risk join your voice channel. Usage: !join"""
        self.ready()
        player = await self.join(ctx)
        self.state(ctx.guild.id).channel_id = ctx.channel.id
        self.schedule_idle(ctx.guild, player) if not player.is_playing else None
        await ctx.reply(f"Joined {player.channel.mention}. Play something with `{ctx.clean_prefix}play <song>`.", mention_author=False)

    @commands.command(name="pause")
    @commands.guild_only()
    async def pause(self, ctx):
        """Pauses the music. Usage: !pause"""
        player = self.need_player(ctx)
        if not player.is_playing:
            raise ModError("Nothing is playing.")
        if player.is_paused:
            raise ModError("It's already paused.")
        await player.set_pause(True)
        await ctx.reply(f"Paused. Use `{ctx.clean_prefix}resume` to continue.", mention_author=False)

    @commands.command(name="resume", aliases=["unpause"])
    @commands.guild_only()
    async def resume(self, ctx):
        """Resumes paused music. Usage: !resume"""
        player = self.need_player(ctx)
        if not player.is_paused:
            raise ModError("The music isn't paused.")
        await player.set_pause(False)
        await ctx.reply("Resumed.", mention_author=False)

    @commands.command(name="skip", aliases=["s", "next"])
    @commands.guild_only()
    async def skip(self, ctx):
        """Skips the current song. Usage: !skip"""
        player = self.need_player(ctx)
        state = self.state(ctx.guild.id)
        if state.current is None:
            raise ModError("Nothing is playing.")
        skipped = state.current
        if state.loop == "track":
            state.loop = "off"  # skipping a looped song means moving on
        if state.loop == "queue":
            state.queue.append(skipped)
        await ctx.reply(f"Skipped **{skipped.title[:100]}**.", mention_author=False, allowed_mentions=NO_MENTIONS)
        await self.start_next(player)

    @commands.command(name="stop", aliases=["leave", "disconnect", "dc"])
    @commands.guild_only()
    async def stop(self, ctx):
        """Stops the music, clears the queue and leaves the voice channel. Usage: !stop"""
        player = self.need_player(ctx)
        await self.stop_all(ctx.guild, player)
        await ctx.reply("Stopped and left the voice channel.", mention_author=False)

    @commands.command(name="queue", aliases=["q"])
    @commands.guild_only()
    async def queue(self, ctx, page: int = 1):
        """Shows what is playing and what is coming up. Usage: !queue | !queue 2"""
        self.ready()
        state = self.state(ctx.guild.id)
        if state.current is None and not state.queue:
            raise ModError("The queue is empty. Add a song with `" + ctx.clean_prefix + "play <song>`.")
        per = 10
        pages = max(1, -(-len(state.queue) // per))
        page = max(1, min(page, pages))
        lines = [f"**Now:** {state.current.title[:80]} ({clock(state.current.length)})" if state.current else "Nothing playing right now."]
        for i, track in enumerate(state.queue[(page - 1) * per:page * per], (page - 1) * per + 1):
            lines.append(f"`{i}.` {track.title[:70]} ({'live' if track.is_stream else clock(track.length)})")
        total = sum(t.length for t in state.queue if not t.is_stream)
        embed = discord.Embed(title="Queue", description="\n".join(lines), color=discord.Color.blurple())
        embed.set_footer(text=f"Page {page}/{pages} • {len(state.queue)} waiting • {clock(total)} of music • Loop: {state.loop}")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="nowplaying", aliases=["np", "current"])
    @commands.guild_only()
    async def nowplaying(self, ctx):
        """Shows the song that is playing, with a progress bar. Usage: !nowplaying"""
        self.ready()
        player = self.player_of(ctx)
        state = self.state(ctx.guild.id)
        if player is None or state.current is None:
            raise ModError("Nothing is playing.")
        embed = self.now_embed(state.current, state)
        if not state.current.is_stream and state.current.length:
            filled = min(20, int(20 * player.position / state.current.length))
            embed.add_field(name="Progress", value=f"`{'▬' * filled}\U0001F518{'▬' * (20 - filled)}` {clock(player.position)} / {clock(state.current.length)}", inline=False)
        if player.is_paused:
            embed.title = "Paused"
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="volume", aliases=["vol"])
    @commands.guild_only()
    async def volume(self, ctx, level: int = None):
        """Shows or sets the volume from 1 to 150. Usage: !volume | !volume 80"""
        state = self.state(ctx.guild.id)
        if level is None:
            await ctx.reply(f"The volume is **{state.volume}%**.", mention_author=False)
            return
        player = self.need_player(ctx)
        if not 1 <= level <= 150:
            raise ModError("Pick a volume from 1 to 150.")
        state.volume = level
        await player.set_volume(level)
        await ctx.reply(f"Volume set to **{level}%**." + (" Above 100 can sound distorted." if level > 100 else ""), mention_author=False)

    @commands.command(name="loop", aliases=["repeat"])
    @commands.guild_only()
    async def loop(self, ctx, mode: str = None):
        """Repeats the current song or the whole queue. Usage: !loop track | !loop queue | !loop off (no mode cycles through them)"""
        self.need_player(ctx)
        state = self.state(ctx.guild.id)
        if mode is None:
            mode = LOOPS[(LOOPS.index(state.loop) + 1) % 3]
        mode = {"song": "track", "one": "track", "current": "track", "all": "queue", "none": "off", "disable": "off"}.get(mode.lower(), mode.lower())
        if mode not in LOOPS:
            raise ModError("Use `track`, `queue` or `off`.")
        state.loop = mode
        await ctx.reply({"off": "Loop is off.", "track": "Looping the current song.", "queue": "Looping the whole queue."}[mode], mention_author=False)

    @commands.command(name="shufflequeue", aliases=["qshuffle", "shuffleq"])
    @commands.guild_only()
    async def shufflequeue(self, ctx):
        """Shuffles the songs waiting in the queue. Usage: !shufflequeue"""
        self.need_player(ctx)
        state = self.state(ctx.guild.id)
        if len(state.queue) < 2:
            raise ModError("There aren't enough songs in the queue to shuffle.")
        random.shuffle(state.queue)
        await ctx.reply(f"Shuffled {len(state.queue)} songs.", mention_author=False)

    @commands.command(name="remove", aliases=["qremove"])
    @commands.guild_only()
    async def remove(self, ctx, number: int):
        """Removes a song from the queue by its number in `!queue`. Usage: !remove 3"""
        self.need_player(ctx)
        state = self.state(ctx.guild.id)
        if not 1 <= number <= len(state.queue):
            raise ModError(f"Pick a number from 1 to {len(state.queue)}." if state.queue else "The queue is empty.")
        track = state.queue.pop(number - 1)
        await ctx.reply(f"Removed **{track.title[:100]}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="queueclear", aliases=["qclear", "clearqueue"])
    @commands.guild_only()
    async def queueclear(self, ctx):
        """Clears the queue but keeps the current song playing. Usage: !queueclear"""
        self.need_player(ctx)
        state = self.state(ctx.guild.id)
        count = len(state.queue)
        state.queue.clear()
        await ctx.reply(f"Cleared {count} song{'s' if count != 1 else ''} from the queue.", mention_author=False)

    @commands.command(name="seek")
    @commands.guild_only()
    async def seek(self, ctx, position: str):
        """Jumps to a time in the current song. Usage: !seek 1:30 | !seek 90"""
        player = self.need_player(ctx)
        state = self.state(ctx.guild.id)
        if state.current is None or state.current.is_stream or not state.current.is_seekable:
            raise ModError("I can't seek in this one.")
        parts = position.split(":")
        if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
            raise ModError("Give a time like `90` (seconds) or `1:30`.")
        seconds = 0
        for part in parts:
            seconds = seconds * 60 + int(part)
        if seconds * 1000 >= state.current.length:
            raise ModError(f"That's past the end ({clock(state.current.length)}).")
        await player.seek(seconds * 1000)
        await ctx.reply(f"Jumped to {clock(seconds * 1000)}.", mention_author=False)


async def setup(bot):
    await bot.add_cog(Music(bot))
