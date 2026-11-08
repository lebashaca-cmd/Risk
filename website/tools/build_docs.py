"""Builds the documentation site into web/docs/ from three sources:

  - docs-src/*.md          the written guides
  - data/bot.json          every command (run tools/export_bot_data.py first)
  - utils/variables.py     every {variable}, read straight from the bot so the list can't drift

    python tools/build_docs.py [/path/to/discord-bot-python]

The output is plain static HTML with no inline scripts or styles, so it works under the site's strict CSP.
All pages sit in one flat folder and link to each other with relative links, so the same files work at
docs.example.com/ and at example.com/docs/.
"""
import html
import importlib.util
import json
import re
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs-src"
OUT = ROOT / "web" / "docs"
DEFAULT_BOT = ROOT.parent / "discord-bot-python"

# Sidebar: (group, [(slug, title)]). Pages with a markdown file use docs-src/<slug>.md; the rest are generated.
NAV = [
    ("Start here", [("index", "Overview"), ("getting-started", "Getting started"), ("dashboard", "The dashboard")]),
    ("Features", [
        ("moderation", "Moderation and auto-mod"), ("levels", "Levels and XP"), ("economy", "Economy and games"),
        ("tickets", "Tickets"), ("logs", "Server logs"), ("community", "Community tools"),
        ("welcome", "Welcome and leave"), ("streams", "Stream alerts"), ("utility", "Utility, fun and lookups"),
    ]),
    ("Customising", [("messages", "Message templates"), ("variables", "Variables"), ("command-rules", "Command rules")]),
    ("VIP", [("vip", "VIP plans"), ("vip-commands", "VIP commands")]),
    ("Reference", [("commands", "All commands"), ("permissions", "Permissions"), ("faq", "Troubleshooting")]),
]
CATEGORY_ORDER = ["Info", "Moderation", "Utility", "Fun", "Economy", "Levels", "Community", "Tickets", "Server logs", "Welcome", "Sticky", "Lookups", "AI", "VIP"]
CATEGORY_BLURB = {
    "Info": "Status, help and links.", "Moderation": "Keep the server safe: bans, timeouts, locks, auto-mod and bulk tools.",
    "Utility": "Handy tools: lookups, converters, reminders, server and user info.", "Fun": "Games, jokes and reactions.",
    "Economy": "Coins, jobs, shops and gambling.", "Levels": "XP, ranks, leaderboards and level rewards.",
    "Community": "Giveaways, starboard, birthdays, counting, reaction roles, tags and more.",
    "Tickets": "A support desk with panels, claims, notes and transcripts.", "Server logs": "Record what happens in your server.",
    "Welcome": "Greet people who join and say goodbye to those who leave.", "Sticky": "Keep a message at the bottom of a channel.",
    "Lookups": "Look up profiles and media on other sites.", "AI": "Ask Risk a question.",
    "VIP": "Extras for servers with VIP.",
}
PREFIX = "!"


# ---------------------------------------------------------------- small markdown
def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"


def safe_url(url):
    url = url.strip()
    if re.match(r"^(https://|/|#|[a-z0-9][a-z0-9_.#/-]*$)", url, re.I):
        return url
    return "#"


def link_tag(url, label):
    url = safe_url(url)
    # A root-relative link points at the main site. docs.js turns it into the right address on the docs host.
    main = ' data-main' if url.startswith("/") else ""
    return f'<a href="{html.escape(url, quote=True)}"{main}>{label}</a>'


def inline(text):
    spans = []

    def keep(match):
        spans.append("<code>" + html.escape(match.group(1)) + "</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep, text)
    text = html.escape(text, quote=True)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: link_tag(html.unescape(m.group(2)), m.group(1)), text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def render_markdown(source, directives):
    """Returns (html, headings, title, summary). Directives like {{variables}} expand to generated HTML."""
    lines = source.splitlines()
    out, headings = [], []
    title, summary = None, None
    i = 0
    paragraph, items, kind = [], [], None

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph = []

    def flush_list():
        nonlocal items, kind
        if items:
            out.append(f"<{kind}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{kind}>")
            items, kind = [], None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph(); flush_list()
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            out.append('<pre><code>' + html.escape("\n".join(block)) + "</code></pre>")
        elif m := re.fullmatch(r"\{\{(\w+)(?::([^}]*))?\}\}", stripped):
            flush_paragraph(); flush_list()
            fn = directives.get(m.group(1))
            out.append(fn(m.group(2)) if fn else f"<p>Missing block: {html.escape(m.group(1))}</p>")
        elif m := re.match(r"^(#{1,3})\s+(.*)$", stripped):
            flush_paragraph(); flush_list()
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and title is None:
                title = text
            else:
                anchor = slugify(text)
                if level >= 2:
                    headings.append((level, text, anchor))
                out.append(f'<h{level} id="{anchor}">{inline(text)}<a class="anchor" href="#{anchor}" aria-label="Link to this section">#</a></h{level}>')
        elif stripped.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\|?[\s:|-]+\|?", lines[i + 1].strip()):
            flush_paragraph(); flush_list()
            def cells(row):
                parts = re.split(r"(?<!\\)\|", row.strip().strip("|"))
                return [c.strip().replace("\\|", "|") for c in parts]
            head = cells(stripped)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            i -= 1
            table = "<div class=\"table-wrap\"><table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            table += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in rows) + "</tbody></table></div>"
            out.append(table)
        elif re.match(r"^[-*]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            flush_paragraph()
            want = "ol" if re.match(r"^\d+\.", stripped) else "ul"
            if kind not in (None, want):
                flush_list()
            kind = want
            items.append(re.sub(r"^([-*]|\d+\.)\s+", "", stripped))
        elif stripped.startswith(">"):
            flush_paragraph(); flush_list()
            out.append('<p class="note">' + inline(stripped.lstrip("> ").strip()) + "</p>")
        elif not stripped:
            flush_paragraph(); flush_list()
        else:
            flush_list()
            paragraph.append(stripped)
            if summary is None and title is not None and not out:
                pass
        i += 1
    flush_paragraph(); flush_list()
    body = "\n".join(out)
    # The summary is the first plain paragraph.
    first = re.search(r"<p>(.*?)</p>", body, re.S)
    if first:
        summary = re.sub(r"<[^>]+>", "", first.group(1))
        summary = html.unescape(summary)[:200]
    return body, headings, title, summary


# ---------------------------------------------------------------- generated blocks
def load_variables(bot_dir):
    spec = importlib.util.spec_from_file_location("risk_variables", Path(bot_dir) / "utils" / "variables.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.catalog()


def load_vip(bot_dir):
    """The plan layout, read from vip.py as text so nothing from the bot has to be installed."""
    source = (Path(bot_dir) / "cogs" / "vip.py").read_text()
    tiers = re.search(r"TIERS = \{(.*?)\n\}", source, re.S).group(1)
    plans = OrderedDict()
    for key, name, groups in re.findall(r'"(\w+)": \("([^"]+)", \{([^}]*)\}\)', tiers):
        plans[key] = (name, re.findall(r'"(\w+)"', groups))
    block = re.search(r"GROUP_COMMANDS = \{(.*?)\n\}", source, re.S).group(1)
    groups = OrderedDict()
    for key, names in re.findall(r'"(\w+)": \[(.*?)\]', block, re.S):
        groups[key] = re.findall(r'"(\w+)"', names)
    return plans, groups


def cmd_html(command, show_category=False):
    name = command["name"]
    usage = f"{PREFIX}{name}"
    examples = [e for e in command.get("examples", []) if e is not None]
    args = examples[0] if examples else ""
    anchor = "cmd-" + slugify(name)
    bits = [f'<div class="cmd" id="{anchor}" data-search="{html.escape((name + " " + command.get("description", "")).lower(), quote=True)}">']
    bits.append(f'<h3><code>{html.escape(usage)}</code><a class="anchor" href="#{anchor}" aria-label="Link to this command">#</a></h3>')
    meta = []
    if command.get("permission"):
        meta.append(f'<span class="tag">Needs {html.escape(command["permission"])}</span>')
    else:
        meta.append('<span class="tag tag-quiet">Anyone can use it</span>')
    if command.get("kind") and command["kind"] != "prefix":
        meta.append(f'<span class="tag tag-quiet">{html.escape(command["kind"])}</span>')
    if show_category:
        meta.append(f'<a class="tag tag-quiet" href="commands-{slugify(command["category"])}">{html.escape(command["category"])}</a>')
    bits.append('<p class="meta">' + " ".join(meta) + "</p>")
    bits.append("<p>" + inline(command.get("description") or "No description yet.") + "</p>")
    if args:
        bits.append("<p class=\"usage\">Try it: <code>" + html.escape(f"{usage} {args}".strip()) + "</code></p>")
    bits.append("</div>")
    return "".join(bits)


def build_variables_block(catalog):
    by_group = OrderedDict()
    for item in catalog:
        by_group.setdefault(item["group"], []).append(item)
    out = []
    for group, items in by_group.items():
        anchor = slugify(group)
        out.append(f'<h3 id="var-{anchor}">{html.escape(group)}<a class="anchor" href="#var-{anchor}" aria-label="Link to this group">#</a></h3>')
        out.append('<div class="table-wrap"><table><thead><tr><th>Variable</th><th>What it does</th><th>Looks like</th></tr></thead><tbody>')
        for item in items:
            example = item["example"]
            out.append(f"<tr><td><code>{html.escape(item['token'])}</code></td><td>{inline(item['description'])}</td><td>{html.escape(example) if example else '(a new line)'}</td></tr>")
        out.append("</tbody></table></div>")
    return "\n".join(out)


def main(bot_dir):
    data = json.loads((ROOT / "data" / "bot.json").read_text())
    commands = data["commands"]
    catalog = load_variables(bot_dir)
    plans, vip_groups = load_vip(bot_dir)
    by_category = defaultdict(list)
    for c in commands:
        by_category[c["category"]].append(c)
    categories = [c for c in CATEGORY_ORDER if c in by_category] + sorted(set(by_category) - set(CATEGORY_ORDER))
    for cat in categories:
        by_category[cat].sort(key=lambda c: c["name"])
    lookup = {c["name"]: c for c in commands}

    def d_commands(arg):
        return "\n".join(cmd_html(c) for c in by_category.get(arg, []))

    def d_variables(arg):
        return build_variables_block(catalog)

    def d_vipplans(arg):
        rows = []
        names = {"basic": "Basic", "lifetime": "Lifetime commands", "white": "White", "supreme": "Supreme"}
        head = "".join(f"<th>{html.escape(n)}</th>" for n, _ in plans.values())
        for group, label in (("basic", "Basic commands"), ("white", "White commands"), ("supreme", "Supreme commands"), ("lifetime", "Lifetime-only commands")):
            cells = "".join("<td>" + ("Yes" if group in g else "No") + "</td>" for _n, g in plans.values())
            rows.append(f"<tr><td>{label}</td>{cells}</tr>")
        return f'<div class="table-wrap"><table><thead><tr><th>Included</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'

    def d_vipcommands(arg):
        titles = {"basic": "Basic", "white": "VIP White", "supreme": "VIP Supreme", "lifetime": "Lifetime"}
        notes = {
            "basic": "Every VIP plan includes these.", "white": "VIP White, VIP Supreme and Lifetime.",
            "supreme": "VIP Supreme and Lifetime.", "lifetime": "Only Lifetime servers.",
        }
        out = []
        for group in ("basic", "white", "supreme", "lifetime"):
            out.append(f'<h2 id="vip-{group}">{titles[group]} commands<a class="anchor" href="#vip-{group}" aria-label="Link to this group">#</a></h2><p>{notes[group]}</p>')
            for name in vip_groups.get(group, []):
                if name in lookup:
                    out.append(cmd_html(lookup[name]))
        return "\n".join(out)

    def d_permissions(arg):
        grouped = defaultdict(list)
        for c in commands:
            if c.get("permission"):
                grouped[c["permission"]].append(c["name"])
        out = []
        for perm in sorted(grouped, key=lambda p: (-len(grouped[p]), p)):
            names = " ".join(f"<code>{html.escape(PREFIX + n)}</code>" for n in sorted(set(grouped[perm])))
            out.append(f'<h3 id="perm-{slugify(perm)}">{html.escape(perm)}<a class="anchor" href="#perm-{slugify(perm)}" aria-label="Link to this permission">#</a></h3><p class="chips">{names}</p>')
        return "\n".join(out)

    def d_categories(arg):
        cards = []
        for cat in categories:
            cards.append(f'<a class="card" href="commands-{slugify(cat)}"><strong>{html.escape(cat)}</strong><span>{len(by_category[cat])} commands</span><em>{html.escape(CATEGORY_BLURB.get(cat, ""))}</em></a>')
        return '<div class="cards">' + "".join(cards) + "</div>"

    def d_stats(arg):
        return f'<p class="stats"><strong>{len(commands)}</strong> commands in <strong>{len(categories)}</strong> categories, <strong>{len(catalog)}</strong> message variables.</p>'

    directives = {
        "commands": d_commands, "variables": d_variables, "vipplans": d_vipplans, "vipcommands": d_vipcommands,
        "count": lambda arg: str(len(catalog)), "permissions": d_permissions, "categories": d_categories, "stats": d_stats,
    }

    pages = OrderedDict()  # slug -> dict(title, body, headings, summary, group)
    for group, entries in NAV:
        for slug, title in entries:
            pages[slug] = {"title": title, "group": group}

    # Written pages
    for slug, page in pages.items():
        path = SRC / f"{slug}.md"
        if path.exists():
            body, headings, title, summary = render_markdown(path.read_text().replace("{{count}}", str(len(catalog))), directives)
            page.update(body=body, headings=headings, summary=summary or "")
            page["title"] = title or page["title"]
    # Generated pages
    for slug in ("commands", "permissions"):
        if "body" not in pages[slug]:
            raise SystemExit(f"docs-src/{slug}.md is missing")

    # One page per command category
    for cat in categories:
        slug = "commands-" + slugify(cat)
        body = f'<p>{html.escape(CATEGORY_BLURB.get(cat, ""))} Anyone can use a command unless it says it needs a permission. If your server changed the prefix, use that instead of <code>{PREFIX}</code>.</p>'
        body += '<p><label class="filter">Filter these commands <input type="search" data-filter placeholder="Type a command or a word" autocomplete="off"></label></p>'
        body += '<div data-filter-list>' + "\n".join(cmd_html(c) for c in by_category[cat]) + '</div><p class="empty" data-filter-empty hidden>No command matches that.</p>'
        pages[slug] = {"title": f"{cat} commands", "group": "Command reference", "body": body, "headings": [], "summary": CATEGORY_BLURB.get(cat, "")}

    order = list(pages)
    nav_groups = OrderedDict()
    for group, entries in NAV:
        nav_groups[group] = list(entries)
    nav_groups["Command reference"] = [("commands-" + slugify(cat), cat) for cat in categories]

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.html"):
        old.unlink()

    def sidebar(current):
        parts = []
        for group, entries in nav_groups.items():
            parts.append(f'<div class="nav-group"><p class="nav-title">{html.escape(group)}</p><ul>')
            for slug, title in entries:
                label = pages[slug]["title"] if slug in pages and not slug.startswith("commands-") else title
                mark = ' aria-current="page"' if slug == current else ""
                parts.append(f'<li><a href="{"./" if slug == "index" else slug}"{mark}>{html.escape(label)}</a></li>')
            parts.append("</ul></div>")
        return "".join(parts)

    flat = [slug for slug in order if not slug.startswith("commands-")] + [s for s in order if s.startswith("commands-")]
    search = []
    for slug in flat:
        page = pages[slug]
        title = page["title"]
        plain = re.sub(r"<[^>]+>", " ", page["body"])
        search.append({"t": title, "u": "./" if slug == "index" else slug, "g": page["group"], "x": html.unescape(re.sub(r"\s+", " ", plain))[:400]})
        for level, text, anchor in page["headings"]:
            if level == 2:
                search.append({"t": text, "u": f"{'./' if slug == 'index' else slug}#{anchor}", "g": title, "x": ""})
    for c in commands:
        search.append({"t": PREFIX + c["name"], "u": f"commands-{slugify(c['category'])}#cmd-{slugify(c['name'])}", "g": c["category"] + " command", "x": c.get("description", "")})
    for item in catalog:
        search.append({"t": item["token"], "u": "variables#var-" + slugify(item["group"]), "g": "Variable", "x": item["description"]})

    main_pages = [s for s in flat if not s.startswith("commands-")]
    cat_pages = [s for s in flat if s.startswith("commands-")]
    for slug in flat:
        page = pages[slug]
        seq = cat_pages if slug.startswith("commands-") else main_pages
        index = seq.index(slug)
        prev_slug = seq[index - 1] if index > 0 else ("commands" if slug.startswith("commands-") else None)
        next_slug = seq[index + 1] if index + 1 < len(seq) else None
        toc = ""
        if page["headings"]:
            toc = '<nav class="toc" aria-label="On this page"><p class="nav-title">On this page</p><ul>' + "".join(
                f'<li class="l{lvl}"><a href="#{a}">{html.escape(t)}</a></li>' for lvl, t, a in page["headings"]
            ) + "</ul></nav>"
        pager = '<nav class="pager" aria-label="Previous and next page">'
        pager += f'<a href="{"./" if prev_slug == "index" else prev_slug}"><span>Previous</span>{html.escape(pages[prev_slug]["title"])}</a>' if prev_slug else "<span></span>"
        pager += f'<a class="next" href="{next_slug}"><span>Next</span>{html.escape(pages[next_slug]["title"])}</a>' if next_slug else ""
        pager += "</nav>"
        desc = html.escape(page.get("summary") or "Documentation for the Risk Discord bot.", quote=True)
        doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page['title'])} · Risk docs</title>
<meta name="description" content="{desc}">
<link rel="icon" href="/favicon.png">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="docs.css">
<script src="docs.js" defer></script>
</head>
<body>
<a class="skip" href="#content">Skip to the page</a>
<header class="top">
  <a class="brand" href="./">Risk <span>docs</span></a>
  <div class="search" role="search">
    <label class="sr" for="q">Search the docs</label>
    <input id="q" type="search" placeholder="Search commands, guides and variables" autocomplete="off" data-search-input>
    <ul class="results" data-search-results hidden></ul>
  </div>
  <button class="menu-toggle" type="button" data-menu aria-expanded="false" aria-controls="side">Menu</button>
  <a class="back" href="/" data-home>Back to Risk</a>
</header>
<div class="shell">
  <aside class="side" id="side" data-side>{sidebar(slug)}</aside>
  <main id="content" tabindex="-1">
    <article>
      <h1>{html.escape(page['title'])}</h1>
      {page['body']}
    </article>
    {pager}
  </main>
  {toc}
</div>
<footer class="foot">Risk documentation. Spotted something wrong or missing? Tell us in the support server.</footer>
</body>
</html>
"""
        (OUT / f"{slug}.html").write_text(doc)

    (OUT / "search.json").write_text(json.dumps(search, separators=(",", ":")))
    print(f"Wrote {len(flat)} pages and {len(search)} search entries to {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BOT)
