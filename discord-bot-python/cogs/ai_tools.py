"""More AI commands that use the same free Groq key as `!ask` (GROQ_API_KEY): summaries, catching up on a channel,
translation, plain-language explanations, rewriting, grammar fixes, ideas, stories, pros and cons, reply
suggestions, quizzes and code explanations. Text you give a command (or the recent messages for `!catchup`)
is sent to the AI provider to produce the answer."""
import os

import aiohttp
import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
MAX_INPUT = 3000
BASE = "You are a helpful assistant inside a Discord server. Be clear and concise. Plain text only unless code is needed; put code in fenced blocks. Never include @mentions."


class AIError(ModError):
    pass


def split_message(text, limit=1900):
    pieces = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        pieces.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text.strip():
        pieces.append(text)
    return pieces


class AITools(commands.Cog, name="AITools"):
    """AI helpers: summarize, translate, explain, rewrite and more."""

    def __init__(self, bot):
        self.bot = bot
        key = os.getenv("GROQ_API_KEY") or os.getenv("AI_API_KEY")
        self.api_key = None if not key or key.startswith("your_") else key
        self.model = os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    async def complete(self, system, user, max_tokens=900, temperature=0.5):
        """Asks the AI and returns its answer, or raises AIError with something safe to show."""
        if not self.api_key:
            raise AIError("The AI key isn't set. Add `GROQ_API_KEY` to the bot's `.env`.")
        payload = {"model": self.model, "messages": [{"role": "system", "content": f"{BASE}\n{system}"}, {"role": "user", "content": user[:MAX_INPUT]}], "max_tokens": max_tokens, "temperature": temperature}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
                async with session.post(GROQ_URL, headers=headers, json=payload) as response:
                    status = response.status
                    body = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError):
            raise AIError("I couldn't reach the AI service. Try again in a moment.")
        if status == 401:
            raise AIError("The AI key was rejected. Check `GROQ_API_KEY`.")
        if status == 429:
            raise AIError("The AI is rate limited right now. Try again in a bit.")
        if status != 200:
            raise AIError(f"The AI returned an error ({status}).")
        try:
            answer = body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            raise AIError("The AI sent back something I couldn't read.")
        if not answer:
            raise AIError("The AI didn't have an answer for that.")
        return answer

    async def respond(self, ctx, system, user, title=None, **kw):
        async with ctx.typing():
            answer = await self.complete(system, user, **kw)
        pieces = split_message(answer)
        for index, piece in enumerate(pieces):
            if index == 0 and title:
                piece = f"**{title}**\n{piece}"
            if index == 0:
                await ctx.reply(piece, mention_author=False, allowed_mentions=NO_MENTIONS)
            else:
                await ctx.send(piece, allowed_mentions=NO_MENTIONS)

    async def source_text(self, ctx, text):
        """The text given, or the message being replied to."""
        if text and text.strip():
            return text.strip()
        ref = ctx.message.reference
        if ref and ref.resolved and isinstance(ref.resolved, discord.Message) and ref.resolved.content:
            return ref.resolved.content.strip()
        raise ModError(f"Give me some text, or reply to a message. Usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`")

    @commands.command(name="summarize", aliases=["tldr", "summary"])
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def summarize(self, ctx, *, text: str = None):
        """Summarizes some text, or the message you reply to. Usage: !summarize <text>"""
        source = await self.source_text(ctx, text)
        await self.respond(ctx, "Summarize the text in at most 5 short bullet points, then one sentence with the main takeaway.", source, "Summary")

    @commands.command(name="catchup", aliases=["recap"])
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def catchup(self, ctx, count: int = 40):
        """Summarizes the last messages in this channel so you can catch up. Usage: !catchup 40 (up to 80)"""
        count = max(10, min(count, 80))
        lines = []
        async for message in ctx.channel.history(limit=count, before=ctx.message):
            if message.author.bot or not message.content:
                continue
            lines.append(f"{message.author.display_name}: {message.clean_content[:300]}")
        if len(lines) < 3:
            raise ModError("There isn't enough recent conversation to summarize.")
        lines.reverse()
        await self.respond(ctx, "Summarize this chat for someone who missed it. Say who talked about what, any decisions or open questions, in at most 6 short bullet points.", "\n".join(lines), "Catch up", max_tokens=700)

    @commands.command(name="translate", aliases=["tr"])
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def translate(self, ctx, language: str, *, text: str = None):
        """Translates text into a language. Usage: !translate spanish good morning, or !translate "brazilian portuguese" thanks"""
        if len(language) > 40:
            raise ModError("Give the language first, like `spanish`.")
        source = await self.source_text(ctx, text)
        await self.respond(ctx, f"Translate the user's text into {language}. Reply with the translation only, then on a new line the detected source language in parentheses.", source, f"Translation ({language})", temperature=0.2)

    @commands.command(name="explain", aliases=["eli5"])
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def explain(self, ctx, *, topic: str):
        """Explains something in plain language. Usage: !explain how does wifi work"""
        await self.respond(ctx, "Explain the topic simply, as if to a curious 12 year old. Use one short analogy and keep it under 150 words.", topic, "Explained simply")

    @commands.command(name="rewrite", aliases=["rephrase"])
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def rewrite(self, ctx, style: str, *, text: str = None):
        """Rewrites text in a style. Usage: !rewrite formal hey can u send the file, or !rewrite "more friendly" <text>"""
        if len(style) > 40:
            raise ModError("Give the style first, like `formal`, `casual` or `shorter`.")
        source = await self.source_text(ctx, text)
        await self.respond(ctx, f"Rewrite the text in this style: {style}. Keep the meaning. Reply with the rewritten text only.", source, f"Rewritten ({style})", temperature=0.6)

    @commands.command(name="grammar", aliases=["fixgrammar", "proofread"])
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def grammar(self, ctx, *, text: str = None):
        """Fixes spelling and grammar. Usage: !grammar i dont no what to rite"""
        source = await self.source_text(ctx, text)
        await self.respond(ctx, "Fix spelling, grammar and punctuation without changing the meaning or tone. Reply with the corrected text, then a line starting 'Changes:' with a very short list of what you fixed.", source, "Corrected", temperature=0.1)

    @commands.command(name="ideas", aliases=["brainstorm"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def ideas(self, ctx, *, topic: str):
        """Brainstorms ideas for something. Usage: !ideas events for a gaming server"""
        await self.respond(ctx, "Give 8 specific, varied ideas as a numbered list. One short line each, no preamble.", topic, "Ideas", temperature=0.9)

    @commands.command(name="story", aliases=["tale"])
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def story(self, ctx, *, prompt: str):
        """Writes a short story from a prompt. Usage: !story a robot who learns to bake"""
        await self.respond(ctx, "Write a short story of about 200 words with a beginning, a twist and an ending. Keep it friendly and suitable for all ages.", prompt, "Story", max_tokens=700, temperature=0.9)

    @commands.command(name="proscons", aliases=["pc"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def proscons(self, ctx, *, topic: str):
        """Lists pros and cons. Usage: !proscons getting a dog"""
        await self.respond(ctx, "List 4 pros and 4 cons as two short bullet lists headed 'Pros' and 'Cons', then a one-line balanced verdict.", topic, "Pros and cons")

    @commands.command(name="suggestreply", aliases=["replyidea"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def suggestreply(self, ctx, *, text: str = None):
        """Suggests three ways to reply to a message. Usage: !suggestreply <message>, or reply to one"""
        source = await self.source_text(ctx, text)
        await self.respond(ctx, "Suggest three different replies to this message: one friendly, one short and direct, one funny. Label each.", source, "Reply ideas", temperature=0.8)

    @commands.command(name="aiquiz", aliases=["quizme"])
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def aiquiz(self, ctx, *, topic: str):
        """Makes a 5 question quiz on a topic with the answers hidden. Usage: !aiquiz the solar system"""
        await self.respond(ctx, "Write 5 multiple choice questions (A to D) about the topic. After the questions write 'Answers:' and put the answers inside Discord spoiler tags like ||1-B, 2-D, 3-A, 4-C, 5-A||.", topic, "Quiz", max_tokens=800)

    @commands.command(name="explaincode", aliases=["codeexplain"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def explaincode(self, ctx, *, code: str = None):
        """Explains what some code does. Usage: !explaincode <code>, or reply to a message with code"""
        source = await self.source_text(ctx, code)
        await self.respond(ctx, "Explain what this code does in plain language: a one-line overview, then the main steps in short bullets. Point out any obvious bug.", source, "Code explained", temperature=0.2)


async def setup(bot):
    await bot.add_cog(AITools(bot))
