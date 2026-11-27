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
from utils.store import JsonStore

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
BASS_PRESETS = {"off": 0, "low": 25, "medium": 50, "high": 75, "extreme": 100}
BASS_SHAPE = (1.0, 0.8, 0.55, 0.25, 0.1)  # how much of the boost each of the lowest five equalizer bands gets
BANDS = ("25", "40", "63", "100", "160", "250", "400", "630", "1k", "1.6k", "2.5k", "4k", "6.3k", "10k", "16k")  # Hz, Lavalink's 15 bands
EQ_MIN, EQ_MAX = -0.25, 1.0  # Lavalink's gain limits (-0.25 is silent, 0 is unchanged)
FLAT = [0.0] * 15
PRESETS = {
    "flat": FLAT,
    "bass boost": [0.3, 0.28, 0.24, 0.18, 0.1, 0.04, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "treble boost": [0, 0, 0, 0, 0, 0, 0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.28, 0.3],
    "vocal": [-0.15, -0.12, -0.1, -0.05, 0, 0.05, 0.1, 0.15, 0.18, 0.18, 0.15, 0.08, 0, -0.05, -0.1],
    "rock": [0.2, 0.18, 0.12, 0.05, -0.05, -0.1, -0.05, 0.05, 0.12, 0.16, 0.18, 0.2, 0.2, 0.18, 0.15],
    "pop": [-0.05, 0.05, 0.12, 0.15, 0.15, 0.1, 0, -0.05, -0.05, 0, 0.08, 0.1, 0.12, 0.12, 0.1],
    "electronic": [0.25, 0.22, 0.12, 0, -0.08, -0.1, 0, 0.06, 0.1, 0.12, 0.1, 0.12, 0.18, 0.22, 0.2],
    "classical": [0, 0, 0, 0, 0, 0, 0, 0, -0.02, -0.05, -0.08, -0.1, -0.12, -0.15, -0.18],
    "loudness": [0.25, 0.2, 0.14, 0.05, 0, -0.04, -0.04, 0, 0, 0.04, 0.1, 0.16, 0.2, 0.22, 0.2],
}
DEFAULTS = {"volume": 60, "bass": 0, "announce": True, "dj": None, "eq": FLAT, "speed": 1.0, "pitch": 1.0, "rotation": False, "karaoke": False}


def clean_eq(values):
    """15 gains clamped to Lavalink's range, or None if the list isn't usable."""
    if not isinstance(values, (list, tuple)) or len(values) != 15:
        return None
    out = []
    for v in values:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
            return None
        out.append(round(min(EQ_MAX, max(EQ_MIN, float(v))), 3))
    return out


def final_levels(eq, bass):
    """The EQ curve plus the bass boost, as (band, gain) pairs."""
    return [(i, round(min(EQ_MAX, max(EQ_MIN, g + (BASS_SHAPE[i] * bass / 100 if i < len(BASS_SHAPE) else 0))), 3)) for i, g in enumerate(eq)]
URL = re.compile(r"https?://\S+")


def clock(ms):
    seconds = int(ms // 1000)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class GuildMusic:
    """What Risk remembers about music in one server."""

    def __init__(self, volume=60, bass=0, saved=None):
        saved = saved or DEFAULTS
        self.bass = bass  # 0 to 100 percent
        self.eq = list(saved.get("eq") or FLAT)
        self.speed = saved.get("speed", 1.0)
        self.pitch = saved.get("pitch", 1.0)
        self.rotation = bool(saved.get("rotation"))
        self.karaoke = bool(saved.get("karaoke"))
        self.queue = []  # tracks waiting, in order
        self.current = None
        self.loop = "off"
        self.channel_id = None  # where "now playing" messages go
        self.idle_task = None
        self.volume = volume


class Music(commands.Cog, name="Music"):
    """Play music in a voice channel: play, queue, skip, loop, volume and more."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("music")
        self.store.data.setdefault("settings", {})
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
    def settings_for(self, guild_id):
        """This server's saved music settings (set in the dashboard), with defaults filled in."""
        return {**DEFAULTS, **self.store.data["settings"].get(str(guild_id), {})}

    def state(self, guild_id):
        if guild_id not in self.guilds:
            saved = self.settings_for(guild_id)
            self.guilds[guild_id] = GuildMusic(saved["volume"], saved["bass"], saved)
        return self.guilds[guild_id]

    def check_dj(self, ctx):
        """If the server picked a DJ role, only people with it (or Manage Server) control the music."""
        dj = self.settings_for(ctx.guild.id)["dj"]
        if not dj or ctx.author.guild_permissions.manage_guild:
            return
        if not any(r.id == dj for r in ctx.author.roles):
            role = ctx.guild.get_role(dj)
            raise ModError(f"You need the {role.name if role else 'DJ'} role to control the music. Anyone can still add songs with `{ctx.clean_prefix}play`.")

    def load_saved(self, state, saved):
        state.volume, state.bass = saved["volume"], saved["bass"]
        state.eq = list(clean_eq(saved["eq"]) or FLAT)
        state.speed, state.pitch = saved["speed"], saved["pitch"]
        state.rotation, state.karaoke = bool(saved["rotation"]), bool(saved["karaoke"])

    async def apply_filters(self, player, state):
        """Sends the equalizer (with bass), speed/pitch, 8D and karaoke to Lavalink. Anything at its default is removed."""
        for tag in ("eq", "timescale", "rotation", "karaoke"):
            if player.filters.has_filter(filter_tag=tag):
                await player.remove_filter(tag)
        levels = final_levels(state.eq, state.bass)
        if any(g for _, g in levels):
            await player.add_filter(pomice.Equalizer(tag="eq", levels=levels))
        if state.speed != 1.0 or state.pitch != 1.0:
            await player.add_filter(pomice.Timescale(tag="timescale", speed=state.speed, pitch=state.pitch))
        if state.rotation:
            await player.add_filter(pomice.Rotation(tag="rotation", rotation_hertz=0.2))
        if state.karaoke:
            await player.add_filter(pomice.Karaoke(tag="karaoke"))

    async def apply_to_guild(self, guild):
        """Pushes the saved settings to a song that's already playing (used by the dashboard)."""
        player = guild.voice_client
        if not (HAVE_POMICE and isinstance(player, pomice.Player)) or guild.id not in self.guilds:
            return
        state = self.guilds[guild.id]
        self.load_saved(state, self.settings_for(guild.id))
        try:
            await player.set_volume(state.volume)
            await self.apply_filters(player, state)
        except Exception as error:
            print(f"[music] couldn't apply dashboard settings ({type(error).__name__})")

    async def refilter(self, ctx, label):
        player = self.need_player(ctx)
        try:
            await self.apply_filters(player, self.state(ctx.guild.id))
        except (pomice.FilterInvalidArgument, pomice.FilterTagInvalid, pomice.FilterTagAlreadyInUse):
            raise ModError("I couldn't change the sound just now. Try again.")
        await ctx.reply(label, mention_author=False)

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
        self.check_dj(ctx)
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
        saved = self.settings_for(ctx.guild.id)
        self.load_saved(self.state(ctx.guild.id), saved)
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
        try:
            await self.apply_filters(player, self.state(ctx.guild.id))
        except Exception as error:
            print(f"[music] couldn't apply the default sound settings ({type(error).__name__})")
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
        if announce and self.settings_for(guild.id)["announce"]:
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

    @commands.command(name="bass", aliases=["bassboost"])
    @commands.guild_only()
    async def bass(self, ctx, level: str = None):
        """Changes the bass boost. Use off, low, medium, high, extreme or a number from 0 to 100. Usage: !bass high | !bass 40 | !bass off (no level shows the current one)"""
        self.ready()
        state = self.state(ctx.guild.id)
        if level is None:
            label = next((n for n, v in BASS_PRESETS.items() if v == state.bass), None)
            await ctx.reply(f"Bass boost is **{state.bass}%**" + (f" ({label})" if label else "") + f". Change it with `{ctx.clean_prefix}bass <off|low|medium|high|extreme|0-100>`.", mention_author=False)
            return
        player = self.need_player(ctx)
        word = level.lower().rstrip("%")
        if word in BASS_PRESETS:
            percent = BASS_PRESETS[word]
        elif word.isdigit() and 0 <= int(word) <= 100:
            percent = int(word)
        else:
            raise ModError("Use `off`, `low`, `medium`, `high`, `extreme` or a number from 0 to 100.")
        state = self.state(ctx.guild.id)
        previous, state.bass = state.bass, percent
        try:
            await self.apply_filters(player, state)
        except (pomice.FilterInvalidArgument, pomice.FilterTagInvalid, pomice.FilterTagAlreadyInUse):
            state.bass = previous
            raise ModError("I couldn't change the bass just now. Try again.")
        await ctx.reply("Bass boost is off." if percent == 0 else f"Bass boost set to **{percent}%**." + (" That's a lot, so it can sound distorted on loud songs." if percent >= 90 else ""), mention_author=False)

    @commands.command(name="equalizer", aliases=["eqset", "fx"])
    @commands.guild_only()
    async def equalizer(self, ctx, *, preset: str = None):
        """Applies an equalizer preset. Presets: flat, bass boost, treble boost, vocal, rock, pop, electronic, classical, loudness. Usage: !equalizer rock | !equalizer reset (the dashboard has sliders for every band)"""
        self.ready()
        state = self.state(ctx.guild.id)
        if preset is None:
            await ctx.reply("Presets: " + ", ".join(f"`{n}`" for n in PRESETS) + f". Use `{ctx.clean_prefix}equalizer <preset>`. The website dashboard has a slider for every band.", mention_author=False)
            return
        name = preset.lower().strip()
        name = "flat" if name in ("reset", "off") else name
        if name not in PRESETS:
            raise ModError("I don't know that preset. Try " + ", ".join(f"`{n}`" for n in PRESETS) + ".")
        player = self.need_player(ctx)
        previous, state.eq = state.eq, list(PRESETS[name])
        try:
            await self.apply_filters(player, state)
        except (pomice.FilterInvalidArgument, pomice.FilterTagInvalid, pomice.FilterTagAlreadyInUse):
            state.eq = previous
            raise ModError("I couldn't change the equalizer just now. Try again.")
        await ctx.reply(f"Equalizer set to **{name}**.", mention_author=False)

    @commands.command(name="speed")
    @commands.guild_only()
    async def speed(self, ctx, amount: float):
        """Changes playback speed from 0.5 to 2 (1 is normal). Usage: !speed 1.25"""
        if not 0.5 <= amount <= 2:
            raise ModError("Speed has to be between 0.5 and 2.")
        state = self.state(ctx.guild.id)
        self.need_player(ctx)
        state.speed = round(amount, 2)
        await self.refilter(ctx, f"Speed set to **{state.speed}x**.")

    @commands.command(name="pitch")
    @commands.guild_only()
    async def pitch(self, ctx, amount: float):
        """Changes pitch from 0.5 to 2 (1 is normal). Usage: !pitch 1.2"""
        if not 0.5 <= amount <= 2:
            raise ModError("Pitch has to be between 0.5 and 2.")
        state = self.state(ctx.guild.id)
        self.need_player(ctx)
        state.pitch = round(amount, 2)
        await self.refilter(ctx, f"Pitch set to **{state.pitch}x**.")

    @commands.command(name="nightcore")
    @commands.guild_only()
    async def nightcore(self, ctx):
        """Toggles nightcore (faster and higher). Usage: !nightcore"""
        state = self.state(ctx.guild.id)
        self.need_player(ctx)
        on = not (state.speed == 1.2 and state.pitch == 1.2)
        state.speed = state.pitch = 1.2 if on else 1.0
        await self.refilter(ctx, "Nightcore is **on**." if on else "Nightcore is **off**.")

    @commands.command(name="8d", aliases=["rotate"])
    @commands.guild_only()
    async def eight_d(self, ctx):
        """Toggles 8D audio, where the sound circles your head. Use headphones. Usage: !8d"""
        state = self.state(ctx.guild.id)
        self.need_player(ctx)
        state.rotation = not state.rotation
        await self.refilter(ctx, "8D audio is **on**. It sounds best in headphones." if state.rotation else "8D audio is **off**.")

    @commands.command(name="karaoke")
    @commands.guild_only()
    async def karaoke(self, ctx):
        """Toggles karaoke mode, which tries to remove the singer's voice. Usage: !karaoke"""
        state = self.state(ctx.guild.id)
        self.need_player(ctx)
        state.karaoke = not state.karaoke
        await self.refilter(ctx, "Karaoke is **on**." if state.karaoke else "Karaoke is **off**.")

    @commands.command(name="resetfx", aliases=["resetfilters"])
    @commands.guild_only()
    async def resetfx(self, ctx):
        """Clears the equalizer, bass, speed, pitch, 8D and karaoke. Usage: !resetfx"""
        state = self.state(ctx.guild.id)
        self.need_player(ctx)
        state.eq, state.bass, state.speed, state.pitch, state.rotation, state.karaoke = list(FLAT), 0, 1.0, 1.0, False, False
        await self.refilter(ctx, "All sound effects are cleared.")

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
