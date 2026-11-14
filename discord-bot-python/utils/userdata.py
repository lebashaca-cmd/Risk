"""Finds, exports and erases everything Risk has saved about one Discord user.

Every cog keeps its data in a JsonStore. This walks all of them (the live in-memory copies, plus any data file no
cog has open) and matches a user three ways:
  * a dictionary key that is the user's id (the usual layout: guild -> user -> entry),
  * a list entry that is the user's id,
  * a record in a list whose "who it belongs to" field is the user's id.
Records where the user only appears as a moderator or staff member are left alone, because they belong to
the person the action was taken against. Some stores are kept on purpose, see KEEP."""
import json
import time

from utils.store import DATA_DIR, JsonStore

# Whose record is it? A list item with one of these fields equal to the user's id belongs to that user.
OWNER_FIELDS = (
    "user", "user_id", "uid", "author", "author_id", "member", "member_id", "owner", "owner_id", "opener", "opener_id",
    "creator", "creator_id", "created_by", "userid", "id", "from_id", "giver", "recipient", "target", "target_id",
)
# Kept so the bot can keep protecting everyone else, and so there is proof a request was handled.
KEEP = {"data_requests": "the record of the request itself", "owner_control": "the bot's block list and switches",
        "staff": "staff roles and server bans", "tempbans": None}


def _same(value, uid):
    return (isinstance(value, (str, int)) and not isinstance(value, bool)) and str(value) == uid


def _key_matches(key, uid):
    key = str(key)
    return key == uid or key.endswith(":" + uid) or key.endswith("_" + uid)


def find_hits(node, uid, path=()):
    """Returns a list of (path, kind) where path leads to the matching dict key / list index."""
    hits = []
    if isinstance(node, dict):
        for key, value in node.items():
            if _key_matches(key, uid):
                hits.append(((*path, key), "entry"))
            else:
                hits.extend(find_hits(value, uid, (*path, key)))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            if _same(item, uid):
                hits.append(((*path, index), "value"))
            elif isinstance(item, dict) and any(_same(item.get(field), uid) for field in OWNER_FIELDS):
                hits.append(((*path, index), "record"))
            else:
                hits.extend(find_hits(item, uid, (*path, index)))
    return hits


def _get(node, path):
    for part in path:
        node = node[part]
    return node


def open_stores(bot):
    """{store name: JsonStore}. Prefers the copy a cog already has open, so unsaved changes are included."""
    found = {}
    for cog in bot.cogs.values():
        for value in vars(cog).values():
            if isinstance(value, JsonStore):
                found.setdefault(value.path.stem, value)
    if DATA_DIR.exists():
        for file in sorted(DATA_DIR.glob("*.json")):
            if file.stem not in found:
                found[file.stem] = JsonStore(file.stem)
    return found


def collect(bot, user_id):
    """{store: [{"where": "a > b > c", "kind": ..., "data": ...}]} for every store that mentions the user."""
    uid = str(user_id)
    result, kept = {}, {}
    for name, store in open_stores(bot).items():
        hits = find_hits(store.data, uid)
        if not hits:
            continue
        rows = [{"where": " > ".join(str(p) for p in path), "kind": kind, "data": _get(store.data, path)} for path, kind in hits]
        (kept if name in KEEP else result)[name] = rows
    return result, kept


def export_json(bot, user_id):
    found, kept = collect(bot, user_id)
    payload = {
        "user_id": str(user_id),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Everything Risk has saved that is tied to this Discord user id.",
        "data": found,
        "kept_on_purpose": sorted(kept),
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8"), {name: len(rows) for name, rows in found.items()}


def summary(bot, user_id):
    found, kept = collect(bot, user_id)
    return {name: len(rows) for name, rows in found.items()}, sorted(kept)


def erase(bot, user_id):
    """Removes the user's data and saves each changed store. Returns {store: number of items removed}."""
    uid = str(user_id)
    removed = {}
    for name, store in open_stores(bot).items():
        if name in KEEP:
            continue
        hits = find_hits(store.data, uid)
        if not hits:
            continue
        # Delete from the deepest and highest list index first so earlier paths stay valid.
        for path, _ in sorted(hits, key=lambda h: (len(h[0]), [p if isinstance(p, int) else 0 for p in h[0]]), reverse=True):
            try:
                parent = _get(store.data, path[:-1])
                if isinstance(parent, dict):
                    parent.pop(path[-1], None)
                elif isinstance(parent, list) and 0 <= path[-1] < len(parent):
                    del parent[path[-1]]
                removed[name] = removed.get(name, 0) + 1
            except (KeyError, IndexError, TypeError):
                continue
        store.save()
    return removed
