import discord
from discord.ext import commands
import aiohttp
import os

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv('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')
        self.api_url = "https://api.groq.com/openai/v1"

    @commands.command(name="ask")
    async def ask(self, ctx, *, question: str):
        """Ask the AI a question. Usage: !ask What is the meaning of life?"""
        if not self.api_key:
            await ctx.send("AI API Key not configured. Please contact the bot owner.")
            return

        async with ctx.typing():
            try:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                data = {
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": question}]
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(self.api_url, headers=headers, json=data) as response:
                        if response.status == 200:
                            res_json = await response.json()
                            answer = res_json['content'][0]['text']
                            if len(answer) > 2000:
                                for i in range(0, len(answer), 2000):
                                    await ctx.send(answer[i:i+2000])
                            else:
                                await ctx.send(answer)
                        else:
                            error_text = await response.text()
                            await ctx.send(f"AI Error: {response.status} - {error_text}")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred: {e}")

async def setup(bot):
    await bot.add_cog(AIChat(bot))
