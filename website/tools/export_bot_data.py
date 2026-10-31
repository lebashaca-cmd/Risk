"""Reads the bot's source files and writes data/bot.json for the website.

Nothing is imported or run: the cogs are parsed with `ast`, so this works
without discord.py installed and without any tokens.

    python tools/export_bot_data.py /path/to/bot
"""
import argparse
import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CATEGORY_BY_FILE = {
    "main": "Info",
    "commands_list": "Info",
    "uptime": "Info",
    "bot_time": "Info",
    "website": "Info",
    "tos": "Info",
    "utility": "Utility",
    "utility_tools": "Utility",
    "moderation": "Moderation",
    "moderation_tools": "Moderation",
    "give_role": "Moderation",
    "fun": "Fun",
    "economy": "Economy",
    "tickets": "Tickets",
    "serverlogs": "Server logs",
    "welcome": "Welcome",
    "ai_chat": "AI",
    "nerve": "Lookups",
}
CATEGORY_ORDER = ["Info", "Utility", "Moderation", "Fun", "Economy", "Tickets", "Server logs", "Welcome", "AI", "Lookups"]
DEFAULT_HIDDEN = {"dusklogs", "duskreset"}


def keyword(call, name):
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return None


def permission_label(call):
    names = [kw.arg for kw in call.keywords if kw.arg and isinstance(kw.value, ast.Constant) and kw.value.value is True]
    if not names:
        return None
    nice = {"administrator": "Administrator", "manage_guild": "Manage Server"}
    return ", ".join(nice.get(n) or n.replace("_", " ").title() for n in names)


def split_doc(doc, name):
    if not doc:
        return "", []
    doc = doc.strip()
    before, _, rest = doc.partition("Usage:")
    usage_line, _, after = rest.partition("\n")
    description = " ".join((before + " " + after).split())
    examples = []
    for part in re.split(r"\s+or\s+", usage_line.strip()):
        part = part.strip()
        if not part:
            continue
        part = re.sub(r"^[!?,/]" + re.escape(name) + r"\b\s*", "", part)
        examples.append(part)
    return description, examples


def collect(path, category):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []

    def handle(func, groups):
        perm = None
        kind = None
        name = None
        description = None
        group = None
        for dec in func.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                continue
            attr = dec.func.attr
            owner = dec.func.value
            if attr == "has_permissions":
                perm = permission_label(dec)
            elif attr == "command" and isinstance(owner, ast.Name):
                if owner.id in ("commands", "bot"):
                    kind, name = "prefix", keyword(dec, "name") or func.name
                elif owner.id == "app_commands":
                    kind, name, description = "slash", keyword(dec, "name") or func.name, keyword(dec, "description")
                elif owner.id in groups:
                    kind, name, description = "slash", keyword(dec, "name") or func.name, keyword(dec, "description")
                    group = groups[owner.id]
        if not kind:
            return
        doc_desc, examples = split_doc(ast.get_docstring(func), name)
        if kind == "slash":
            full = f"{group['name']} {name}" if group else name
            perm = perm or (group or {}).get("permission")
            found.append({"name": full, "kind": "slash", "category": category,
                          "description": description or doc_desc, "examples": [], "permission": perm})
        else:
            found.append({"name": name, "kind": "prefix", "category": category,
                          "description": doc_desc, "examples": examples, "permission": perm})

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            groups = {}
            for item in node.body:
                if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
                    func = item.value.func
                    if isinstance(func, ast.Attribute) and func.attr == "Group" and isinstance(item.targets[0], ast.Name):
                        perm = None
                        for kw in item.value.keywords:
                            if kw.arg == "default_permissions" and isinstance(kw.value, ast.Call):
                                perm = permission_label(kw.value)
                        groups[item.targets[0].id] = {"name": keyword(item.value, "name") or item.targets[0].id, "permission": perm}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    handle(item, groups)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            handle(node, {})
    return found


def read_prefixes(main_path):
    try:
        tree = ast.parse(main_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "command_prefix":
                    try:
                        value = ast.literal_eval(kw.value)
                    except ValueError:
                        return []
                    return [value] if isinstance(value, str) else [str(v) for v in value]
    return []


def read_tos(path):
    if not path.exists():
        return {"sections": [], "updated": None}
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    sections = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SECTIONS" for t in node.targets):
            for title, text in ast.literal_eval(node.value):
                sections.append({"title": title, "text": text})
    match = re.search(r"Last updated:\s*([^\"']+)", source)
    return {"sections": sections, "updated": match.group(1).strip() if match else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bot_dir", help="folder that contains main.py and cogs/")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "bot.json"))
    parser.add_argument("--hide", default=",".join(sorted(DEFAULT_HIDDEN)),
                        help="comma separated command names to leave off the public site")
    args = parser.parse_args()

    root = Path(args.bot_dir)
    hidden = {h.strip() for h in args.hide.split(",") if h.strip()}
    commands = []
    files = [root / "main.py"] + sorted((root / "cogs").glob("*.py"))
    for path in files:
        if not path.exists():
            continue
        category = CATEGORY_BY_FILE.get(path.stem.lower(), path.stem.replace("_", " ").title())
        commands.extend(collect(path, category))

    commands = [c for c in commands if c["name"].split()[0] not in hidden]
    seen = set()
    unique = []
    for c in commands:
        key = (c["kind"], c["name"])
        if key not in seen:
            seen.add(key)
            unique.append(c)

    def order(c):
        cat = CATEGORY_ORDER.index(c["category"]) if c["category"] in CATEGORY_ORDER else len(CATEGORY_ORDER)
        return (cat, c["name"])

    unique.sort(key=order)

    prefixes = read_prefixes(root / "main.py") or ["!"]
    data = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prefixes": prefixes,
        "commands": unique,
        "tos": read_tos(root / "cogs" / "tos.py"),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}: {len(unique)} commands, {len(data['tos']['sections'])} terms sections, prefixes {prefixes}")


if __name__ == "__main__":
    sys.exit(main())
