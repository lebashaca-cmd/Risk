import io
import os
import re

import aiohttp
import discord
from discord.ext import commands

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
SYSTEM_PROMPT = (
    "You are a helpful assistant inside a Discord server. Keep answers clear and reasonably short.\n"
    "Formatting rules:\n"
    "- Always put code inside a fenced code block with the language name, like ```lua or ```python. "
    "Never write code outside a code block.\n"
    "- If the user asks for a file (for example a .txt, .json or .lua file), put the full contents of "
    "the file in ONE fenced code block with the right language tag (use ```txt for plain text), "
    "and add at most one short sentence before it.\n"
    "- Do not wrap normal prose in code blocks."
)

EXTENSIONS = {
    "lua": "lua", "luau": "lua", "python": "py", "py": "py", "javascript": "js", "js": "js",
    "typescript": "ts", "ts": "ts", "json": "json", "html": "html", "css": "css", "c": "c",
    "cpp": "cpp", "c++": "cpp", "csharp": "cs", "cs": "cs", "c#": "cs", "java": "java",
    "rust": "rs", "rs": "rs", "go": "go", "bash": "sh", "sh": "sh", "shell": "sh", "zsh": "sh",
    "yaml": "yml", "yml": "yml", "xml": "xml", "sql": "sql", "markdown": "md", "md": "md",
    "batch": "bat", "bat": "bat", "powershell": "ps1", "ps1": "ps1", "php": "php", "ruby": "rb",
    "rb": "rb", "kotlin": "kt", "swift": "swift", "csv": "csv", "ini": "ini", "toml": "toml",
    "txt": "txt", "text": "txt", "plaintext": "txt", "": "txt",
}

FILE_NAME = re.compile(
    r"\b([\w\-]+\.(?:txt|py|lua|luau|js|ts|json|html|css|md|csv|c|cpp|cs|java|rs|go|sh|yml|yaml|xml|sql|bat|ps1|php|rb|kt|swift|ini|toml))\b",
    re.IGNORECASE,
)
FILE_WORD = re.compile(r"\b(file|attachment|attach|download)\b", re.IGNORECASE)
CODE_BLOCK = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)

MESSAGE_LIMIT = 2000
INLINE_CODE_LIMIT = 1800


def chunk_text(text, limit=MESSAGE_LIMIT):
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text.strip():
        chunks.append(text)
    return chunks


def build_messages(answer, wants_file=False, filename=None):
    if answer.count("```") % 2 == 1:
        answer += "\n```"

    pieces = []
    last = 0
    for match in CODE_BLOCK.finditer(answer):
        before = answer[last:match.start()].strip()
        if before:
            pieces.append(("text", before))
        lang = match.group(1).strip().lower()
        pieces.append(("code", lang, match.group(2).rstrip("\n")))
        last = match.end()
    after = answer[last:].strip()
    if after:
        pieces.append(("text", after))

    code_count = sum(1 for p in pieces if p[0] == "code")
    messages = []
    buffer = ""
    file_index = 0

    def flush():
        nonlocal buffer
        if buffer.strip():
            messages.append({"content": buffer.strip(), "file": None})
        buffer = ""

    def add(text):
        nonlocal buffer
        if buffer and len(buffer) + len(text) + 2 > MESSAGE_LIMIT:
            flush()
        buffer = f"{buffer}\n\n{text}" if buffer else text

    for piece in pieces:
        if piece[0] == "text":
            for chunk in chunk_text(piece[1]):
                add(chunk)
            continue

        _, lang, code = piece
        extension = EXTENSIONS.get(lang, lang if re.fullmatch(r"[a-z0-9]{1,5}", lang) else "txt")
        as_file = wants_file or len(code) > INLINE_CODE_LIMIT

        if as_file:
            flush()
            file_index += 1
            if filename and code_count == 1:
                name = filename
            else:
                name = f"code_{file_index}.{extension}" if code_count > 1 else f"code.{extension}"
            messages.append({"content": f"📄 `{name}`", "file": (name, code)})
        else:
            add(f"```{lang}\n{code}\n```")

    flush()
    return messages


class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        key = os.getenv("GROQ_API_KEY") or os.getenv("AI_API_KEY")
        self.api_key = None if not key or key.startswith("your_") else key
        self.model = os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    @commands.command(name="ask")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ask(self, ctx, *, question: str):
        """Ask the AI a question. Code comes in code blocks, files get attached. Usage: ,ask your question"""
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
            "max_tokens": 2048,
            "temperature": 0.5,
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

        name_match = FILE_NAME.search(question)
        filename = name_match.group(1) if name_match else None
        wants_file = bool(name_match or FILE_WORD.search(question))

        no_pings = discord.AllowedMentions.none()
        for message in build_messages(answer, wants_file=wants_file, filename=filename):
            file = None
            if message["file"]:
                name, text = message["file"]
                file = discord.File(io.BytesIO(text.encode("utf-8")), filename=name)
            await ctx.send(message["content"], file=file, allowed_mentions=no_pings)

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Slow down, try again in {error.retry_after:.0f}s.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `,ask <your question>`")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(AIChat(bot))
