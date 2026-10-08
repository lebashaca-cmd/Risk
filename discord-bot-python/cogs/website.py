import discord
from discord.ext import commands
from bs4 import BeautifulSoup
import os

class Website(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bio_path = r"C:\Users\ttayl\Downloads\Risk-Bio\index.html"

    @commands.command(name="bio")
    async def bio(self, ctx):
        """Displays information from your Risk Bio website. Usage: !bio"""
        if not os.path.exists(self.bio_path):
            await ctx.send("Could not find the bio file. Please check the path.")
            return

        try:
            with open(self.bio_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'html.parser')
            username = soup.find('h1', class_='username').text if soup.find('h1', class_='username') else "Unknown"
            bio_text = soup.find('p', class_='bio-description').text.strip() if soup.find('p', class_='bio-description') else "No bio available."

            langs = soup.find_all('div', class_='lang-box')
            lang_list = list(set([lang.text for lang in langs]))
            lang_string = ", ".join(lang_list)

            links = soup.find_all('a', class_='link-item')
            link_details = []
            for link in links:
                link_details.append(f"[{link.text}]({link['href']})")
            link_string = "\n".join(link_details)

            embed = discord.Embed(
                title=f"👤 {username}'s Profile",
                description=bio_text,
                color=discord.Color.dark_grey()
            )

            avatar_img = soup.find('img', id='user-avatar')
            if avatar_img:
                embed.set_thumbnail(url=avatar_img['src'])

            embed.add_field(name="💻 Languages", value=lang_string, inline=False)
            embed.add_field(name="🔗 Links", value=link_string, inline=False)
            embed.set_footer(text="Data pulled from Risk-Bio website")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"An error occurred while reading your bio: {e}")

async def setup(bot):
    await bot.add_cog(Website(bot))
