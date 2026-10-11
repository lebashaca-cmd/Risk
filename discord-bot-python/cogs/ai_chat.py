import os

import aiohttp
import discord
from discord.ext import commands

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
SYSTEM_PROMPT = (
    "You are a helpful assistant inside a Discord server. "
    "Keep answers clear and reasonably short."
)


class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        key = os.getenv("GROQ_API_KEY") or os.getenv("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")
        self.api_key = None if not key or key.startswith("your_") else key
        self.model = os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    @commands.command(name="ask")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ask(self, ctx, *, question: str):
        """Ask the AI a question. Usage: ,ask What is the meaning of life?"""
        if not self.api_key:
            await ctx.send("The AI key isn't set. Add `GROQ_API_KEY` to the bot's `.env`.")
            return

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            "max_tokens": 1024,
            "temperature": 0.7,
        }

        async with ctx.typing():
            try:
                timeout = aiohttp.ClientTimeout(total=45)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(GROQ_URL, headers=headers, json=payload) as response:
                        body = await response.json(content_type=None)
                        status = response.status
            except aiohttp.ClientError:
                await ctx.send("I couldn't reach the AI service.")
                return
            except TimeoutError:
                await ctx.send("The AI took too long to answer.")
                return

        if status == 401:
            await ctx.send("The AI key was rejected. Check `GROQ_API_KEY`.")
            return
        if status == 429:
            await ctx.send("The AI is rate limited right now. Try again in a bit.")
            return
        if status != 200:
            detail = ""
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                detail = body["error"].get("message", "")
            await ctx.send(f"The AI returned an error ({status}). {detail}"[:500])
            return

        try:
            answer = body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            await ctx.send("The AI sent back something I couldn't read.")
            return

        if not answer:
            await ctx.send("The AI didn't have an answer for that.")
            return

        no_pings = discord.AllowedMentions.none()
        for i in range(0, len(answer), 2000):
            await ctx.send(answer[i:i + 2000], allowed_mentions=no_pings)

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Slow down, try again in {error.retry_after:.0f}s.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `,ask <your question>`")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(AIChat(bot))
