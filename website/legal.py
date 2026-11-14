"""Server-rendered legal pages (privacy, terms, accessibility, data deletion) and the data-deletion request store.

These pages are plain HTML so they load without JavaScript, can be read by crawlers and screen readers
straight away, and never depend on the single-page app having started."""
import html
import json
import re
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

LEGAL_UPDATED = "November 14, 2026"
SNOWFLAKE = re.compile(r"\d{15,21}")
MAX_STORED = 500
FORM_LIMIT = (5, 3600)


def esc(value):
    return html.escape(str(value), quote=True)


def slug(title, index):
    text = re.sub(r"^\d+\.\s*", "", title).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or f"section-{index + 1}"


def document(title, payload, intro=""):
    sections = payload.get("sections") or []
    if not sections:
        return f'<div class="view container page"><h1>{esc(title)}</h1><p class="empty">This page isn\'t published yet.</p></div>'
    items = [(slug(s["title"], i), s) for i, s in enumerate(sections)]
    toc = "".join(f'<li><a href="#{i}">{esc(s["title"])}</a></li>' for i, s in items)
    body = "".join(f'<h2 id="{i}">{esc(s["title"])}</h2><p>{esc(s["text"])}</p>' for i, s in items)
    updated = f'<p class="muted">Last updated {esc(payload.get("updated") or LEGAL_UPDATED)}</p>'
    return (
        f'<div class="view container page"><h1>{esc(title)}</h1>{intro}'
        f'<div class="terms-layout"><nav class="toc" aria-label="On this page"><ol>{toc}</ol></nav>'
        f'<div class="prose">{updated}{body}</div></div></div>'
    )


def contact_block(settings):
    parts = []
    if settings.support_url.startswith("https://"):
        parts.append(f'the <a href="{esc(settings.support_url)}" rel="noopener noreferrer" target="_blank">support server</a>')
    if settings.contact_email:
        parts.append(f'<a href="mailto:{esc(settings.contact_email)}">{esc(settings.contact_email)}</a>')
    return " or ".join(parts) if parts else "the support server linked from the Risk bot's help command"


def accessibility(settings):
    contact = contact_block(settings)
    return f"""<div class="view container page"><h1>Accessibility statement</h1>
<p class="lede">Risk's website should work for everyone, including people who use a keyboard, a screen reader, zoom or reduced motion.</p>
<div class="prose">
<p class="muted">Last updated {esc(LEGAL_UPDATED)}</p>
<h2 id="our-aim">Our aim</h2>
<p>We aim to meet the Web Content Accessibility Guidelines (WCAG) 2.2 level AA on the public pages, the documentation and the dashboard.</p>
<h2 id="what-we-do">What we've built in</h2>
<ul>
<li>A "Skip to main content" link is the first thing you reach when you press Tab on every page.</li>
<li>Every page has landmarks: a header, a main navigation, a main area, a footer and, in the documentation, a search region.</li>
<li>Everything can be used with a keyboard, and the focused item always has a visible outline.</li>
<li>Text and controls keep a strong contrast against the dark background, and text can be zoomed to 200% without losing content.</li>
<li>Animations stop when your device asks for reduced motion.</li>
<li>Pictures that carry meaning have text alternatives. Purely decorative pictures are hidden from screen readers.</li>
<li>Status messages, such as the toast that confirms a saved setting, are announced by screen readers.</li>
</ul>
<h2 id="known-gaps">Known gaps</h2>
<p>We test with the keyboard, browser accessibility inspectors and automated checks, but we have not yet had an independent audit. Some dashboard screens with many settings are long and can be tiring to move through. Content that comes from Discord, such as server names and icons, is shown as members wrote it, so it may lack text alternatives.</p>
<h2 id="contact">Tell us about a problem</h2>
<p>If something on this site is hard to use, tell us through {contact}. Say which page and what you were trying to do, and which device or assistive technology you use. We aim to reply within 7 days and to fix real barriers as soon as we can.</p>
</div></div>"""


def deletion_form(settings, error="", values=None):
    values = values or {}
    contact = contact_block(settings)
    err = f'<p class="form-error" role="alert">{esc(error)}</p>' if error else ""
    kind = values.get("kind", "delete")
    if settings.turnstile_secret:
        turnstile = (
            f'<div class="field"><div class="cf-turnstile" data-sitekey="{esc(settings.turnstile_site_key)}" data-action="data_deletion" data-theme="dark"></div>'
            '<noscript><p class="form-error">Turn on JavaScript to complete the security check.</p></noscript></div>'
        )
    else:
        turnstile = '<p class="form-error" role="status">Requests are paused until the site\'s security check is switched on. Use the support server for now, or try again later.</p>'
    return f"""<div class="view container page"><h1>Delete my data</h1>
<p class="lede">Ask Risk to delete what it has saved about you, or to send you a copy.</p>
<div class="prose">
<p class="muted">Last updated {esc(LEGAL_UPDATED)}</p>
<h2 id="what-we-delete">What we delete</h2>
<p>Everything Risk saved that is tied to your Discord user ID: coins, items, XP and levels, warnings, reminders, to-do lists, AFK notes, tickets you opened, reputation and similar saved data. The <a href="/privacy">privacy policy</a> lists all of it.</p>
<h2 id="what-we-cant">What we can't delete</h2>
<p>Messages and transcripts that Risk posted in a Discord server (for example a ticket transcript in a staff channel) now live in that server and are controlled by its admins. Discord itself keeps its own data about you. Server-wide settings belong to the server owner, so a request about a whole server has to come from its owner.</p>
<h2 id="how-it-works">How it works</h2>
<ol>
<li>Fill in the form below. You only need your Discord user ID. In Discord, turn on Developer Mode, then right-click your name and choose Copy User ID.</li>
<li>Pass the quick security check from Cloudflare, then send the form. You get a reference number straight away. Keep it.</li>
<li>Your request goes to the Risk owner in Discord. Anyone could type your ID into a form, so we may message you on Discord to check it's really you. We never ask for your password or token.</li>
<li>For a copy, the bot sends it to your Discord DMs. For deletion, we delete everything Risk saved about you and tell you when it's done. Both happen within 30 days.</li>
</ol>
<p>Prefer to do it yourself? In any server with Risk, type <code>!mydata</code> to get a copy in a private message, or <code>!forgetme</code> to delete your data after confirming. No form needed.</p>
<p>Can't use either? Contact us through {contact} and include your Discord user ID.</p>
<h2 id="request-form">Make a request</h2>
{err}
<form class="form" method="post" action="/data-deletion">
<div class="field"><label for="kind">What do you need?</label>
<select id="kind" name="kind"><option value="delete"{" selected" if kind == "delete" else ""}>Delete my data</option><option value="export"{" selected" if kind == "export" else ""}>Send me a copy of my data</option><option value="both"{" selected" if kind == "both" else ""}>Send me a copy, then delete it</option></select></div>
<div class="field"><label for="user_id">Your Discord user ID</label>
<input id="user_id" name="user_id" type="text" inputmode="numeric" pattern="[0-9]{{15,21}}" minlength="15" maxlength="21" required aria-describedby="user_id_help" autocomplete="off" value="{esc(values.get("user_id", ""))}">
<p class="fine" id="user_id_help">Numbers only, 17 to 19 digits long.</p></div>
<div class="field"><label for="server_id">Server ID (optional)</label>
<input id="server_id" name="server_id" type="text" inputmode="numeric" pattern="[0-9]{{15,21}}" maxlength="21" autocomplete="off" aria-describedby="server_help" value="{esc(values.get("server_id", ""))}">
<p class="fine" id="server_help">Only if your request is about one server.</p></div>
<div class="field"><label for="reach">How can we reach you? (optional)</label>
<input id="reach" name="reach" type="text" maxlength="120" autocomplete="off" aria-describedby="reach_help" value="{esc(values.get("reach", ""))}">
<p class="fine" id="reach_help">A Discord username or an email address. If you leave this blank we'll try to message you on Discord.</p></div>
<div class="field"><label for="details">Anything else? (optional)</label>
<textarea id="details" name="details" rows="4" maxlength="500">{esc(values.get("details", ""))}</textarea></div>
<div class="hp" aria-hidden="true"><label for="website">Leave this empty</label><input id="website" name="website" type="text" tabindex="-1" autocomplete="off"></div>
{turnstile}
<button class="btn btn-primary" type="submit"{" disabled" if not settings.turnstile_secret else ""}>Send request</button>
</form>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
</div></div>"""


def confirmation(reference, settings):
    return f"""<div class="view container page"><h1>Request received</h1>
<p class="lede">Your reference number is <strong class="ref">{esc(reference)}</strong>.</p>
<div class="prose">
<p>We've logged your request and will act on it within 30 days. We may message you on Discord to confirm it's really you before anything is deleted or sent. Keep this reference number, and quote it if you contact {contact_block(settings)}.</p>
<p><a class="btn btn-quiet" href="/">Back to the home page</a></p>
</div></div>"""


class DeletionStore:
    """Saves requests to a JSON file and keeps a per-address rate limit. Render's free disk is wiped on every
    deploy, so the real copy goes to DELETION_WEBHOOK_URL (a Discord channel webhook) when it is set."""

    def __init__(self, path):
        self.path = Path(path)
        self.hits = defaultdict(deque)

    def limited(self, ip):
        limit, window = FORM_LIMIT
        now = time.monotonic()
        recent = self.hits[ip]
        while recent and now - recent[0] > window:
            recent.popleft()
        if len(recent) >= limit:
            return True
        recent.append(now)
        if len(self.hits) > 2000:
            for key in [k for k, v in self.hits.items() if not v or now - v[-1] > window]:
                self.hits.pop(key, None)
        return False

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def add(self, entry):
        items = self.load()[-(MAX_STORED - 1):]
        items.append(entry)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(items, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            return False
        return True


def parse_request(form):
    """Returns (entry, error). entry has the cleaned fields; error is a message for the visitor."""
    if (form.get("website") or "").strip():
        return None, "silent"
    user_id = (form.get("user_id") or "").strip()
    server_id = (form.get("server_id") or "").strip()
    kind = (form.get("kind") or "delete").strip()
    if not SNOWFLAKE.fullmatch(user_id):
        return None, "Enter your Discord user ID: 15 to 21 digits, numbers only."
    if server_id and not SNOWFLAKE.fullmatch(server_id):
        return None, "The server ID should be 15 to 21 digits, or left empty."
    if kind not in ("delete", "export", "both"):
        kind = "delete"
    clean = lambda key, size: re.sub(r"\s+", " ", (form.get(key) or "")).strip()[:size]
    reference = "DEL-" + secrets.token_hex(4).upper()
    return {
        "reference": reference,
        "received": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": kind,
        "user_id": user_id,
        "server_id": server_id or None,
        "reach": clean("reach", 120) or None,
        "details": clean("details", 500) or None,
        "status": "received",
    }, None
