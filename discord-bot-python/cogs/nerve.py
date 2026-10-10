import os
import re
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands

API_BASE = "https://api.nerve.wtf"


def norm(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def find(data, *names):
    wanted = {norm(n) for n in names}
    stack = [data]
    while stack:
        current = stack.pop(0)
        if isinstance(current, dict):
            for key, value in current.items():
                if norm(key) in wanted and value not in (None, "", [], {}):
                    return value
            stack.extend(v for v in current.values() if isinstance(v, dict))
    return None


def top(data, *names):
    if not isinstance(data, dict):
        return None
    wanted = {norm(n) for n in names}
    for key, value in data.items():
        if norm(key) in wanted and value not in (None, "", [], {}):
            return value
    return None


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return f"{int(value):,}"
    return str(value)


SPOTIFY_URL = re.compile(
    r"(?:open\.spotify\.com/(?:intl-[a-z]+/)?|spotify:)(track|album|artist|playlist)[/:]([A-Za-z0-9]+)"
)


def items_of(data, key):
    value = find(data, key) if isinstance(data, dict) else data
    if isinstance(value, dict):
        value = value.get("items") or find(value, "items")
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def names_of(value):
    if isinstance(value, dict):
        value = value.get("name")
    if isinstance(value, list):
        out = []
        for v in value:
            out.append(v.get("name") if isinstance(v, dict) else str(v))
        return ", ".join(n for n in out if n)
    return str(value) if value else None


def image_of(data):
    images = find(data, "images")
    if isinstance(images, list) and images:
        first = images[0]
        url = first.get("url") if isinstance(first, dict) else first
        if isinstance(url, str) and url.startswith("http"):
            return url
    value = find(data, "image", "imageUrl", "cover", "coverArt", "albumArt", "artwork", "thumbnail")
    if isinstance(value, dict):
        value = value.get("url")
    return value if isinstance(value, str) and value.startswith("http") else None


def link_of(data, kind):
    ext = top(data, "externalUrls")
    if isinstance(ext, dict) and isinstance(ext.get("spotify"), str):
        return ext["spotify"]
    value = top(data, "spotifyUrl", "url", "link")
    if isinstance(value, str) and value.startswith("http"):
        return value
    ident = top(data, "id")
    return f"https://open.spotify.com/{kind}/{ident}" if ident else None


def duration_of(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    seconds = int(value / 1000) if value >= 10000 else int(value)
    return f"{seconds // 60}:{seconds % 60:02d}"


def count_of(value):
    if isinstance(value, dict):
        value = value.get("total")
    return number(value)


YT_VIDEO = re.compile(r"(?:youtube\.com/(?:watch\?(?:[^ ]*&)?v=|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")
YT_PLAYLIST = re.compile(r"youtube\.com/playlist\?(?:[^ ]*&)?list=([A-Za-z0-9_-]+)")
YT_CHANNEL = re.compile(r"youtube\.com/(@[A-Za-z0-9._-]+|channel/UC[A-Za-z0-9_-]{22})")
YT_CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")


def thumb_of(data):
    value = find(data, "thumbnail", "thumbnails", "thumbnailUrl")
    if isinstance(value, str) and value.startswith("http"):
        return value
    if isinstance(value, list):
        value = [v for v in value if isinstance(v, (dict, str))]
        if not value:
            return None
        last = value[-1]
        value = last.get("url") if isinstance(last, dict) else last
        return value if isinstance(value, str) and value.startswith("http") else None
    if isinstance(value, dict):
        if isinstance(value.get("url"), str):
            return value["url"]
        for key in ("maxres", "standard", "high", "medium", "default"):
            sub = value.get(key)
            if isinstance(sub, dict) and isinstance(sub.get("url"), str):
                return sub["url"]
    return None


def video_link(item):
    value = top(item, "url", "link", "videoUrl")
    if isinstance(value, str) and value.startswith("http"):
        return value
    ident = top(item, "videoId") or top(item, "id")
    if isinstance(ident, dict):
        ident = ident.get("videoId")
    return f"https://www.youtube.com/watch?v={ident}" if isinstance(ident, str) else None


def yt_duration(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str) and value.startswith("PT"):
        m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
        if not m:
            return value
        h, mi, sec = (int(x or 0) for x in m.groups())
        return f"{h}:{mi:02d}:{sec:02d}" if h else f"{mi}:{sec:02d}"
    if isinstance(value, (int, float)):
        total = int(value)
        h, rem = divmod(total, 3600)
        mi, sec = divmod(rem, 60)
        return f"{h}:{mi:02d}:{sec:02d}" if h else f"{mi}:{sec:02d}"
    return str(value)


def result_items(data):
    for key in ("results", "items", "videos", "data"):
        found = items_of(data, key)
        if found:
            return found
    return []


class Nerve(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("NERVE_API_KEY")

    async def call(self, path, **params):
        if not self.api_key:
            return None, "The Nerve API key isn't set. Add `NERVE_API_KEY` to the bot's `.env`."

        headers = {"x-api-key": self.api_key}
        timeout = aiohttp.ClientTimeout(total=20)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{API_BASE}{path}", params=params, headers=headers) as resp:
                    try:
                        body = await resp.json(content_type=None)
                    except Exception:
                        body = {}

                    if resp.status in (401, 403):
                        return None, "The API rejected the key. Check `NERVE_API_KEY`."
                    if resp.status == 404:
                        return None, "Nothing found for that."
                    if resp.status == 422:
                        return None, "That input isn't valid."
                    if resp.status == 429:
                        return None, "The API rate limit was hit. Try again in a bit."
                    if resp.status >= 400:
                        message = body.get("error") if isinstance(body, dict) else None
                        return None, message or f"The API returned an error ({resp.status})."

                    if isinstance(body, dict) and body.get("success") is False:
                        return None, body.get("error") or "The API couldn't complete that request."
                    return (body.get("data") if isinstance(body, dict) else body), None
        except aiohttp.ClientError:
            return None, "I couldn't reach the API."
        except TimeoutError:
            return None, "The API took too long to answer."

    @commands.command(name="tiktok")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def tiktok(self, ctx, username: str):
        """Shows a TikTok profile. Usage: ,tiktok username"""
        username = username.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_.]{1,24}", username):
            await ctx.send("That doesn't look like a valid TikTok username.")
            return

        async with ctx.typing():
            data, error = await self.call("/v1/tiktok/profile", username=username)

        if error:
            await ctx.send(error)
            return
        if not isinstance(data, dict) or not data:
            await ctx.send("The API didn't return any profile data.")
            return

        nickname = find(data, "nickname", "displayName", "name")
        handle = find(data, "uniqueId", "username") or username
        bio = find(data, "signature", "bio", "biography", "description")
        avatar = find(data, "avatarLarger", "avatarUrl", "avatar", "avatarMedium", "profilePicture")
        verified = find(data, "verified", "isVerified")

        title = f"{nickname} (@{handle})" if nickname else f"@{handle}"
        if verified is True:
            title += " ✅"

        embed = discord.Embed(
            title=title,
            url=f"https://www.tiktok.com/@{handle}",
            description=str(bio)[:2000] if bio else None,
            color=discord.Color.from_str("#fe2c55"),
        )
        if isinstance(avatar, str) and avatar.startswith("http"):
            embed.set_thumbnail(url=avatar)

        stats = [
            ("Followers", find(data, "followerCount", "followers", "fans")),
            ("Following", find(data, "followingCount", "following")),
            ("Likes", find(data, "heartCount", "likes", "hearts", "totalLikes")),
            ("Videos", find(data, "videoCount", "videos", "posts")),
        ]
        added = 0
        for name, value in stats:
            shown = number(value)
            if shown is not None:
                embed.add_field(name=name, value=shown, inline=True)
                added += 1

        engagement = find(data, "engagementRate")
        if engagement is not None:
            shown = f"{engagement:.2f}%" if isinstance(engagement, (int, float)) and not isinstance(engagement, bool) else str(engagement)
            embed.add_field(name="Engagement", value=shown, inline=True)
            added += 1

        if added == 0:
            lines = [f"**{k}**: {str(v)[:100]}" for k, v in list(data.items())[:10] if not isinstance(v, (dict, list))]
            if lines:
                embed.add_field(name="Data", value="\n".join(lines)[:1000], inline=False)

        embed.set_footer(text="Data from Nerve API")
        await ctx.send(embed=embed)

    @commands.command(name="github")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def github(self, ctx, target: str):
        """Shows a GitHub profile or repo. Usage: ,github username  or  ,github owner/repo"""
        target = target.lstrip("@").strip("/")

        if "/" in target:
            parts = target.split("/")
            if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9._-]{1,100}", p) for p in parts):
                await ctx.send("Use `,github owner/repo`, like `,github torvalds/linux`.")
                return
            async with ctx.typing():
                data, error = await self.call("/v1/github/repository", owner=parts[0], repo=parts[1])
            if error:
                await ctx.send(error)
                return
            await ctx.send(embed=self.repo_embed(data, parts[0], parts[1]))
            return

        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", target):
            await ctx.send("That doesn't look like a valid GitHub username.")
            return

        async with ctx.typing():
            data, error = await self.call("/v1/github/user", username=target)
        if error:
            await ctx.send(error)
            return
        if not isinstance(data, dict) or not data:
            await ctx.send("The API didn't return any profile data.")
            return

        login = find(data, "login", "username") or target
        name = find(data, "name", "displayName")
        bio = find(data, "bio", "description")
        avatar = find(data, "avatarUrl", "avatar_url", "avatar")
        url = top(data, "htmlUrl", "html_url", "url", "profileUrl")
        if not (isinstance(url, str) and url.startswith("http")):
            url = f"https://github.com/{login}"

        embed = discord.Embed(
            title=f"{name} ({login})" if name and name != login else str(login),
            url=url,
            description=str(bio)[:2000] if bio else None,
            color=discord.Color.from_str("#2b3137"),
        )
        if isinstance(avatar, str) and avatar.startswith("http"):
            embed.set_thumbnail(url=avatar)

        fields = [
            ("Followers", number(find(data, "followers", "followerCount"))),
            ("Following", number(find(data, "following", "followingCount"))),
            ("Public Repos", number(find(data, "publicRepos", "public_repos", "repos", "repositories"))),
            ("Location", find(data, "location")),
            ("Company", find(data, "company")),
            ("Website", find(data, "blog", "website")),
            ("Joined", self.date(find(data, "createdAt", "created_at"))),
        ]
        added = 0
        for label, value in fields:
            if value not in (None, ""):
                embed.add_field(name=label, value=str(value)[:200], inline=True)
                added += 1

        if added == 0:
            lines = [f"**{k}**: {str(v)[:100]}" for k, v in list(data.items())[:10] if not isinstance(v, (dict, list))]
            if lines:
                embed.add_field(name="Data", value="\n".join(lines)[:1000], inline=False)

        embed.set_footer(text="Data from Nerve API")
        await ctx.send(embed=embed)

    @staticmethod
    def date(value):
        if not isinstance(value, str):
            return None
        try:
            stamp = int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
            return f"<t:{stamp}:D>"
        except ValueError:
            return value

    def repo_embed(self, data, owner, repo):
        if not isinstance(data, dict):
            data = {}
        full = find(data, "fullName", "full_name") or f"{owner}/{repo}"
        description = find(data, "description")
        language = find(data, "language")
        license_ = find(data, "license")
        if isinstance(license_, dict):
            license_ = license_.get("name") or license_.get("spdx_id") or license_.get("spdxId")
        topics = find(data, "topics")
        url = top(data, "htmlUrl", "html_url", "url")
        if not (isinstance(url, str) and url.startswith("http")):
            url = f"https://github.com/{owner}/{repo}"

        embed = discord.Embed(
            title=str(full),
            url=url,
            description=str(description)[:2000] if description else None,
            color=discord.Color.from_str("#2b3137"),
        )
        fields = [
            ("Stars", number(find(data, "stargazersCount", "stars", "stargazers"))),
            ("Forks", number(find(data, "forksCount", "forks"))),
            ("Open Issues", number(find(data, "openIssuesCount", "openIssues"))),
            ("Language", language),
            ("License", license_),
            ("Topics", ", ".join(map(str, topics[:10])) if isinstance(topics, list) and topics else None),
        ]
        for label, value in fields:
            if value not in (None, ""):
                embed.add_field(name=label, value=str(value)[:300], inline=True)
        embed.set_footer(text="Data from Nerve API")
        return embed

    @commands.command(name="spotify")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def spotify(self, ctx, *, query: str):
        """Searches Spotify or shows a link. Usage: ,spotify song name  or  ,spotify <spotify link>"""
        query = query.strip().strip("<>")
        match = SPOTIFY_URL.search(query)

        async with ctx.typing():
            if match:
                kind = match.group(1)
                data, error = await self.call(f"/v1/spotify/{kind}", url=query)
            else:
                kind = "search"
                data, error = await self.call("/v1/spotify/search", query=query[:200], type="track", limit=5)

        if error:
            await ctx.send(error)
            return
        if not data:
            await ctx.send("The API didn't return anything for that.")
            return

        if kind == "search":
            tracks = items_of(data, "tracks")
            if not tracks:
                await ctx.send("No results found.")
                return
            lines = []
            for i, track in enumerate(tracks[:5], 1):
                name = find(track, "name") or "Unknown"
                artist = names_of(find(track, "artists", "artist"))
                url = link_of(track, "track")
                title = f"[{name}]({url})" if url else str(name)
                lines.append(f"**{i}.** {title}" + (f" — {artist}" if artist else ""))
            embed = discord.Embed(
                title=f"Spotify results for \"{query[:100]}\"",
                description="\n".join(lines)[:4000],
                color=discord.Color.from_str("#1db954"),
            )
            art = image_of(tracks[0])
            if art:
                embed.set_thumbnail(url=art)
            embed.set_footer(text="Send a Spotify link with ,spotify for full details")
            await ctx.send(embed=embed)
            return

        await ctx.send(embed=self.spotify_embed(data, kind))

    def spotify_embed(self, data, kind):
        if not isinstance(data, dict):
            data = {}
        name = find(data, "name", "title") or "Unknown"
        embed = discord.Embed(
            title=str(name)[:250],
            url=link_of(data, kind),
            description=None,
            color=discord.Color.from_str("#1db954"),
        )
        art = image_of(data)
        if art:
            embed.set_thumbnail(url=art)

        fields = []
        if kind == "track":
            fields = [
                ("Artist", names_of(find(data, "artists", "artist"))),
                ("Album", names_of(find(data, "album"))),
                ("Duration", duration_of(find(data, "durationMs", "duration_ms", "duration"))),
                ("Popularity", number(find(data, "popularity"))),
                ("Released", find(data, "releaseDate", "release_date")),
                ("ISRC", find(data, "isrc")),
            ]
        elif kind == "album":
            fields = [
                ("Artist", names_of(find(data, "artists", "artist"))),
                ("Released", find(data, "releaseDate", "release_date")),
                ("Label", find(data, "label")),
                ("Tracks", number(find(data, "totalTracks", "total_tracks"))),
                ("Popularity", number(find(data, "popularity"))),
            ]
            tracks = items_of(data, "tracks")
            if tracks:
                lines = [f"{i}. {find(t, 'name') or 'Unknown'}" for i, t in enumerate(tracks[:10], 1)]
                if len(tracks) > 10:
                    lines.append(f"...and {len(tracks) - 10} more")
                fields.append(("Tracklist", "\n".join(lines)))
        elif kind == "artist":
            genres = find(data, "genres")
            fields = [
                ("Followers", count_of(find(data, "followers"))),
                ("Popularity", number(find(data, "popularity"))),
                ("Genres", ", ".join(map(str, genres[:6])) if isinstance(genres, list) and genres else None),
            ]
        elif kind == "playlist":
            embed.description = (str(find(data, "description")) or None) if find(data, "description") else None
            fields = [
                ("Owner", names_of(find(data, "owner")) or find(data, "ownerName")),
                ("Followers", count_of(find(data, "followers"))),
                ("Tracks", count_of(find(data, "tracks"))),
            ]

        shown = 0
        for label, value in fields:
            if value not in (None, ""):
                embed.add_field(name=label, value=str(value)[:1000], inline=label != "Tracklist")
                shown += 1
        if shown == 0:
            lines = [f"**{k}**: {str(v)[:100]}" for k, v in list(data.items())[:10] if not isinstance(v, (dict, list))]
            if lines:
                embed.add_field(name="Data", value="\n".join(lines)[:1000], inline=False)

        embed.set_footer(text="Data from Nerve API")
        return embed

    @commands.command(name="youtube")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def youtube(self, ctx, *, query: str):
        """Shows a YouTube video, channel or playlist, or searches. Usage: ,youtube @channel  or  ,youtube <link>  or  ,youtube search words"""
        query = query.strip().strip("<>")

        video = YT_VIDEO.search(query)
        playlist = YT_PLAYLIST.search(query)
        channel = YT_CHANNEL.search(query)

        async with ctx.typing():
            if video:
                kind = "video"
                data, error = await self.call("/v1/youtube/video", url=query)
            elif playlist:
                kind = "playlist"
                data, error = await self.call("/v1/youtube/playlist", playlist_id=playlist.group(1))
            elif channel or (query.startswith("@") and " " not in query) or YT_CHANNEL_ID.fullmatch(query):
                kind = "channel"
                handle = channel.group(1).replace("channel/", "") if channel else query
                data, error = await self.call("/v1/youtube/channel", handle=handle)
            else:
                kind = "search"
                data, error = await self.call("/v1/youtube/search", query=query[:200], type="video", max_results=5)

        if error:
            await ctx.send(error)
            return
        if not data:
            await ctx.send("The API didn't return anything for that.")
            return

        if kind == "search":
            results = result_items(data)
            if not results:
                await ctx.send("No results found.")
                return
            lines = []
            for i, item in enumerate(results[:5], 1):
                title = find(item, "title", "name") or "Untitled"
                url = video_link(item)
                chan = names_of(find(item, "channelTitle", "channel", "author", "channelName"))
                label = f"[{str(title)[:90]}]({url})" if url else str(title)[:90]
                lines.append(f"**{i}.** {label}" + (f" — {chan}" if chan else ""))
            embed = discord.Embed(
                title=f"YouTube results for \"{query[:100]}\"",
                description="\n".join(lines)[:4000],
                color=discord.Color.from_str("#ff0000"),
            )
            thumb = thumb_of(results[0])
            if thumb:
                embed.set_thumbnail(url=thumb)
            embed.set_footer(text="Send a link with ,youtube for full details")
            await ctx.send(embed=embed)
            return

        await ctx.send(embed=self.youtube_embed(data, kind, query))

    def youtube_embed(self, data, kind, query):
        if not isinstance(data, dict):
            data = {}
        title = find(data, "title", "name") or "Unknown"
        description = find(data, "description")
        embed = discord.Embed(title=str(title)[:250], color=discord.Color.from_str("#ff0000"))
        if description:
            embed.description = str(description)[:400]

        if kind == "channel":
            handle = find(data, "handle", "customUrl")
            if isinstance(handle, str) and handle:
                embed.url = f"https://www.youtube.com/{handle if handle.startswith('@') else '@' + handle}"
            elif query.startswith("@"):
                embed.url = f"https://www.youtube.com/{query}"
            avatar = thumb_of(data) or image_of(data)
            if avatar:
                embed.set_thumbnail(url=avatar)
            banner = find(data, "banner", "bannerUrl")
            if isinstance(banner, dict):
                banner = banner.get("url")
            if isinstance(banner, str) and banner.startswith("http"):
                embed.set_image(url=banner)
            fields = [
                ("Subscribers", number(find(data, "subscriberCount", "subscribers"))),
                ("Views", number(find(data, "viewCount", "totalViews", "views"))),
                ("Videos", number(find(data, "videoCount", "videos"))),
                ("Country", find(data, "country")),
                ("Joined", self.date(find(data, "publishedAt", "createdAt", "joinedDate"))),
            ]
        elif kind == "video":
            embed.url = video_link(data)
            thumb = thumb_of(data)
            if thumb:
                embed.set_image(url=thumb)
            tags = find(data, "tags")
            fields = [
                ("Channel", names_of(find(data, "channelTitle", "channel", "author", "channelName"))),
                ("Views", number(find(data, "viewCount", "views"))),
                ("Likes", number(find(data, "likeCount", "likes"))),
                ("Comments", number(find(data, "commentCount", "comments"))),
                ("Duration", yt_duration(find(data, "duration", "durationSeconds"))),
                ("Published", self.date(find(data, "publishedAt", "uploadDate", "published"))),
                ("Tags", ", ".join(map(str, tags[:8])) if isinstance(tags, list) and tags else None),
            ]
        else:
            thumb = thumb_of(data)
            if thumb:
                embed.set_thumbnail(url=thumb)
            videos = [v for v in result_items(data)]
            fields = [
                ("Channel", names_of(find(data, "channelTitle", "channel", "author", "owner"))),
                ("Videos", number(find(data, "itemCount", "videoCount", "totalVideos")) or (str(len(videos)) if videos else None)),
            ]
            if videos:
                lines = []
                for i, item in enumerate(videos[:10], 1):
                    name = str(find(item, "title", "name") or "Untitled")[:80]
                    url = video_link(item)
                    lines.append(f"{i}. [{name}]({url})" if url else f"{i}. {name}")
                if len(videos) > 10:
                    lines.append(f"...and {len(videos) - 10} more")
                fields.append(("Videos in playlist", "\n".join(lines)))

        shown = 0
        for label, value in fields:
            if value not in (None, ""):
                embed.add_field(name=label, value=str(value)[:1000], inline=label != "Videos in playlist")
                shown += 1
        if shown == 0:
            lines = [f"**{k}**: {str(v)[:100]}" for k, v in list(data.items())[:10] if not isinstance(v, (dict, list))]
            if lines:
                embed.add_field(name="Data", value="\n".join(lines)[:1000], inline=False)

        embed.set_footer(text="Data from Nerve API")
        return embed

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Slow down, try again in {error.retry_after:.0f}s.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Usage: `,{ctx.command.name} <{error.param.name}>`")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Nerve(bot))
