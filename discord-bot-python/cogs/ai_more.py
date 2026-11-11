"""A bigger batch of AI commands: creative writing, word tools, study helpers, planning and code helpers. They use the
same Groq key as `!ask` and the AITools helpers. Text you give a command is sent to the AI provider to write the answer."""
from discord.ext import commands

from utils.helpers import ModError, explain_error


class AIMore(commands.Cog, name="AIMore"):
    """More AI helpers: poems, rhymes, study plans, recipes, regex, SQL and more."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    async def run(self, ctx, text, system, title, temperature, max_tokens):
        ai = self.bot.get_cog("AITools")
        if ai is None:
            raise ModError("The AI tools aren't loaded on this bot.")
        source = await ai.source_text(ctx, text)
        await ai.respond(ctx, system, source, title, temperature=temperature, max_tokens=max_tokens)

    @commands.command(name="haiku")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def haiku(self, ctx, *, text: str = None):
        """Writes a haiku about a topic. Usage: !haiku autumn rain"""
        await self.run(ctx, text, 'Write a haiku (5-7-5) about the topic. Output only the haiku.', 'Haiku', 0.9, 300)

    @commands.command(name="poem")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def poem(self, ctx, *, text: str = None):
        """Writes a short poem about a topic. Usage: !poem friendship"""
        await self.run(ctx, text, 'Write an original short poem (8 to 12 lines) about the topic. Output only the poem.', 'Poem', 0.9, 500)

    @commands.command(name="rap", aliases=['bars'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def rap(self, ctx, *, text: str = None):
        """Writes a short original rap verse about a topic. Usage: !rap pizza night"""
        await self.run(ctx, text, 'Write an original, playful 8-line rap verse about the topic. Keep it clean and fun. Do not quote any existing song.', 'Rap', 0.9, 500)

    @commands.command(name="limerick")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def limerick(self, ctx, *, text: str = None):
        """Writes a limerick about a topic. Usage: !limerick a cat who loved Mondays"""
        await self.run(ctx, text, 'Write a clean, funny limerick (AABBA) about the topic. Output only the limerick.', 'Limerick', 0.9, 300)

    @commands.command(name="rhyme", aliases=['rhymes'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def rhyme(self, ctx, *, text: str = None):
        """Lists words that rhyme with a word. Usage: !rhyme orange"""
        await self.run(ctx, text, 'List 15 words that rhyme with the given word (include near rhymes and mark them). Output a compact comma separated list.', 'Rhymes', 0.3, 300)

    @commands.command(name="synonyms", aliases=['syn'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def synonyms(self, ctx, *, text: str = None):
        """Lists synonyms and antonyms of a word. Usage: !synonyms happy"""
        await self.run(ctx, text, 'Give 8 synonyms and 4 antonyms for the word, each with a tiny nuance note in brackets only when it matters.', 'Synonyms', 0.3, 400)

    @commands.command(name="etymology", aliases=['origin'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def etymology(self, ctx, *, text: str = None):
        """Explains where a word comes from. Usage: !etymology salary"""
        await self.run(ctx, text, 'Explain the origin and history of the word in 3 to 4 sentences. If you are not sure, say so.', 'Etymology', 0.3, 400)

    @commands.command(name="analogy")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def analogy(self, ctx, *, text: str = None):
        """Explains something with an analogy. Usage: !analogy how the internet works"""
        await self.run(ctx, text, 'Explain the topic using one clear everyday analogy, then say where the analogy breaks down. Keep it under 120 words.', 'Analogy', 0.6, 400)

    @commands.command(name="titles", aliases=['headlines'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def titles(self, ctx, *, text: str = None):
        """Suggests titles or headlines for a topic. Usage: !titles a video about budget travel"""
        await self.run(ctx, text, 'Give 10 catchy title ideas for the topic, numbered, in different styles.', 'Title ideas', 0.9, 500)

    @commands.command(name="hashtags")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def hashtags(self, ctx, *, text: str = None):
        """Suggests hashtags for a post. Usage: !hashtags sunset at the beach"""
        await self.run(ctx, text, 'Suggest 12 relevant hashtags for the text, on one line, most relevant first.', 'Hashtags', 0.6, 250)

    @commands.command(name="caption")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def caption(self, ctx, *, text: str = None):
        """Writes caption ideas for a photo or post. Usage: !caption my dog at the park"""
        await self.run(ctx, text, 'Write 5 short, different caption ideas (funny, sweet, punny, minimal, bold) for the described photo or post.', 'Captions', 0.9, 400)

    @commands.command(name="slogan", aliases=['tagline'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def slogan(self, ctx, *, text: str = None):
        """Makes slogans for an idea or brand. Usage: !slogan a bakery called Rise"""
        await self.run(ctx, text, 'Write 8 short, memorable slogans for the idea. Numbered.', 'Slogans', 0.9, 400)

    @commands.command(name="namebrand", aliases=['brandnames'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def namebrand(self, ctx, *, text: str = None):
        """Suggests names for a project, brand or server. Usage: !namebrand a cozy gaming server"""
        await self.run(ctx, text, 'Suggest 12 creative, easy to say names for what is described, with at most 5 words of explanation each. Numbered.', 'Name ideas', 1.0, 500)

    @commands.command(name="outline")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def outline(self, ctx, *, text: str = None):
        """Makes an outline for an essay, talk or video. Usage: !outline why sleep matters"""
        await self.run(ctx, text, 'Create a clear outline with headings and 2 to 3 bullets each for the topic. Keep it compact.', 'Outline', 0.5, 800)

    @commands.command(name="studyplan")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def studyplan(self, ctx, *, text: str = None):
        """Builds a short study plan for a subject. Usage: !studyplan 7 days to learn basic Spanish"""
        await self.run(ctx, text, 'Create a realistic day by day study plan for the request. Keep each day to one or two lines and end with one tip.', 'Study plan', 0.5, 900)

    @commands.command(name="flashcards", aliases=['cards'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def flashcards(self, ctx, *, text: str = None):
        """Makes flashcards for a topic. Usage: !flashcards photosynthesis"""
        await self.run(ctx, text, 'Make 8 flashcards for the topic in the form `Q: ... / A: ...`, one per line pair, accurate and concise.', 'Flashcards', 0.4, 800)

    @commands.command(name="mnemonic")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def mnemonic(self, ctx, *, text: str = None):
        """Makes a memory trick for something you need to remember. Usage: !mnemonic the order of the planets"""
        await self.run(ctx, text, 'Create a memorable mnemonic or memory trick for the request and explain how to use it in one line.', 'Mnemonic', 0.8, 300)

    @commands.command(name="recipe", aliases=['cook'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def recipe(self, ctx, *, text: str = None):
        """Suggests a quick recipe from a dish or ingredients. Usage: !recipe chicken, rice, spinach"""
        await self.run(ctx, text, 'Give a simple recipe for the request: a name, ingredients with amounts, and short numbered steps. Mention any allergens or safe cooking temperatures when relevant.', 'Recipe', 0.6, 900)

    @commands.command(name="debatecase", aliases=['bothsides'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def debatecase(self, ctx, *, text: str = None):
        """Argues both sides of a question. Usage: !debatecase should schools start later"""
        await self.run(ctx, text, 'Give the strongest case for each side in 3 bullets each, then one neutral sentence on what the disagreement really turns on. Be even handed.', 'Both sides', 0.5, 700)

    @commands.command(name="fallacy", aliases=['fallacies'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def fallacy(self, ctx, *, text: str = None):
        """Spots logical fallacies in an argument. Usage: !fallacy Everyone I know likes it so it must be good"""
        await self.run(ctx, text, 'Identify any logical fallacies in the text, name each, quote the part, and explain in one sentence. If there are none, say so.', 'Fallacy check', 0.3, 500)

    @commands.command(name="commitmsg", aliases=['commit'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def commitmsg(self, ctx, *, text: str = None):
        """Writes a git commit message for your changes. Usage: !commitmsg fixed login bug where empty passwords passed"""
        await self.run(ctx, text, 'Write a conventional commit message (type(scope): subject under 72 chars, blank line, short body) for the described change.', 'Commit message', 0.3, 250)

    @commands.command(name="regex")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def regex(self, ctx, *, text: str = None):
        """Writes a regular expression from a description. Usage: !regex match a US phone number"""
        await self.run(ctx, text, 'Write a regular expression for the request. Give the pattern in a code block, a one-line explanation, and 3 example matches and 2 non-matches. Say which flavour (PCRE/JavaScript/Python) it works in.', 'Regex', 0.2, 500)

    @commands.command(name="sql")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def sql(self, ctx, *, text: str = None):
        """Writes an SQL query from a description. Usage: !sql top 5 customers by total orders"""
        await self.run(ctx, text, 'Write the SQL for the request (standard SQL, mention assumptions about table and column names) in a code block with a short explanation.', 'SQL', 0.2, 600)

    @commands.command(name="shellhelp", aliases=['cmdhelp'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def shellhelp(self, ctx, *, text: str = None):
        """Suggests a terminal command for a task. Usage: !shellhelp find files bigger than 100MB"""
        await self.run(ctx, text, 'Give the shell command(s) for the task (Linux/macOS bash, mention a Windows PowerShell equivalent if it differs) in a code block and explain each flag briefly. Warn if the command deletes or changes data.', 'Command help', 0.2, 500)

    @commands.command(name="codereview", aliases=['review'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def codereview(self, ctx, *, text: str = None):
        """Reviews a piece of code and suggests improvements. Usage: !codereview <paste code>"""
        await self.run(ctx, text, 'Review the code: list bugs first, then readability and safety issues, then one improved snippet. Be concise.', 'Code review', 0.3, 900)

    @commands.command(name="shorten", aliases=['condense'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def shorten(self, ctx, *, text: str = None):
        """Makes text shorter without losing the point. Usage: !shorten <text>"""
        await self.run(ctx, text, 'Rewrite the text to be about half as long while keeping every key point. Output only the shortened text.', 'Shorter', 0.3, 600)

    @commands.command(name="expand", aliases=['elaborate'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def expand(self, ctx, *, text: str = None):
        """Expands a short note into fuller text. Usage: !expand meeting moved to friday"""
        await self.run(ctx, text, 'Expand the text into a clear, friendly paragraph without inventing facts. Output only the paragraph.', 'Expanded', 0.6, 600)

    @commands.command(name="dialogue", aliases=['script'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def dialogue(self, ctx, *, text: str = None):
        """Writes a short dialogue for a scene. Usage: !dialogue two robots arguing about pizza"""
        await self.run(ctx, text, 'Write a short, funny dialogue (10 to 14 lines) for the scene, as `Name: line`. Keep it clean.', 'Dialogue', 0.9, 700)

    @commands.command(name="whatif")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def whatif(self, ctx, *, text: str = None):
        """Explores a what-if scenario for fun. Usage: !whatif the moon disappeared"""
        await self.run(ctx, text, 'Explore the scenario in a fun but scientifically sensible way: 4 short bullets of consequences and one surprising detail.', 'What if', 0.8, 600)

    @commands.command(name="dndhook", aliases=['adventure'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def dndhook(self, ctx, *, text: str = None):
        """Creates a tabletop adventure hook. Usage: !dndhook haunted lighthouse"""
        await self.run(ctx, text, 'Create a tabletop RPG adventure hook for the theme: a setting line, the problem, a villain, two twists, and a reward. Keep it under 180 words.', 'Adventure hook', 1.0, 600)

    @commands.command(name="characterbio", aliases=['charbio'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def characterbio(self, ctx, *, text: str = None):
        """Writes a character backstory from an idea. Usage: !characterbio a retired space pirate who bakes"""
        await self.run(ctx, text, 'Write a vivid character bio (name, look, personality, secret, goal) in about 120 words.', 'Character', 1.0, 600)

    @commands.command(name="dream", aliases=['dreamread'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def dream(self, ctx, *, text: str = None):
        """Gives a playful reading of a dream (just for fun). Usage: !dream I was flying over my school"""
        await self.run(ctx, text, 'Give a playful, imaginative interpretation of the dream in 4 to 5 sentences. Say clearly that it is just for fun and not psychology advice.', 'Dream reading', 0.9, 400)

    @commands.command(name="lifehack")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def lifehack(self, ctx, *, text: str = None):
        """Suggests practical tips for an area of life. Usage: !lifehack staying focused while studying"""
        await self.run(ctx, text, 'Give 6 practical, safe, specific tips for the request. Short bullets.', 'Tips', 0.7, 500)

    @commands.command(name="tonecheck", aliases=['tone'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def tonecheck(self, ctx, *, text: str = None):
        """Tells you how a message might come across. Usage: !tonecheck Fine. Whatever you want."""
        await self.run(ctx, text, 'Describe the tone of the message (e.g. friendly, passive aggressive, urgent), how the reader may feel, and give one friendlier rewrite.', 'Tone check', 0.4, 400)

    @commands.command(name="keywords", aliases=['keyphrases'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def keywords(self, ctx, *, text: str = None):
        """Pulls the key words and topics out of text. Usage: !keywords <text>"""
        await self.run(ctx, text, 'Extract the 8 most important keywords or key phrases from the text, then name its main topic in one line.', 'Keywords', 0.2, 300)

    @commands.command(name="emaildraft", aliases=['emailwrite'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def emaildraft(self, ctx, *, text: str = None):
        """Drafts an email from a short description. Usage: !emaildraft ask my teacher for a deadline extension, polite"""
        await self.run(ctx, text, 'Draft a clear, polite email with a subject line for the request. Keep it brief and use [Name] style placeholders for unknown details.', 'Email draft', 0.6, 600)


async def setup(bot):
    await bot.add_cog(AIMore(bot))
