"""Talks to game servers with nothing but the standard library and aiohttp.

Minecraft Java (status ping and the optional Query protocol), Minecraft Bedrock, Steam/Source servers (CS2, Rust, ARK,
Garry's Mod, Valheim and others that answer A2S), RCON, Terraria's TShock REST API and the Pterodactyl panel API.

Every connection first checks that the host is a public address, so nobody can point the bot at its own network.
Set GAMES_ALLOW_PRIVATE=1 only for local testing.
"""
import asyncio
import ipaddress
import json
import os
import random
import re
import socket
import struct
import time

import aiohttp

TIMEOUT = 6
MC_COLOURS = re.compile("§.")


class GameError(Exception):
    """A problem worth showing to the person who ran the command."""


# ---------------------------------------------------------------------------------------------- safety
def parse_address(text, default_port):
    """'play.example.com:25565' -> ('play.example.com', 25565)."""
    text = text.strip().replace("https://", "").replace("http://", "").strip("/")
    host, port = text, default_port
    if text.count(":") == 1:
        host, raw = text.split(":")
        if not raw.isdigit() or not 1 <= int(raw) <= 65535:
            raise GameError("The port must be a number between 1 and 65535.")
        port = int(raw)
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host or ""):
        raise GameError("That isn't a valid server address. Use something like `play.example.com:25565`.")
    return host.lower(), port


async def ensure_public(host):
    """Raises GameError unless every address the host resolves to is a public one."""
    if os.getenv("GAMES_ALLOW_PRIVATE") == "1":
        return
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        raise GameError(f"I couldn't find `{host}`. Check the address.")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise GameError("That address points at a private network, so I won't connect to it. Use the server's public address.")


# ---------------------------------------------------------------------------------------------- minecraft java
def _varint(n):
    out = b""
    while True:
        byte = n & 0x7F
        n >>= 7
        out += bytes([byte | (0x80 if n else 0)])
        if not n:
            return out


async def _read_varint(reader):
    value = shift = 0
    while True:
        byte = (await reader.readexactly(1))[0]
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value
        shift += 7
        if shift > 35:
            raise GameError("The server sent something that isn't a Minecraft reply.")


def _flatten_motd(node):
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_flatten_motd(n) for n in node)
    if isinstance(node, dict):
        return str(node.get("text", "")) + _flatten_motd(node.get("extra", []))
    return ""


def clean_motd(text):
    return re.sub(r"\n\s*", "\n", MC_COLOURS.sub("", text)).strip()


async def mc_java_status(host, port=25565):
    await ensure_public(host)
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), TIMEOUT)
    except (OSError, asyncio.TimeoutError):
        raise GameError("The server didn't answer. It may be offline, or the address or port may be wrong.")
    try:
        name = host.encode()
        handshake = _varint(0) + _varint(767) + _varint(len(name)) + name + struct.pack(">H", port) + _varint(1)
        writer.write(_varint(len(handshake)) + handshake + b"\x01\x00")
        await writer.drain()
        started = time.monotonic()
        length = await asyncio.wait_for(_read_varint(reader), TIMEOUT)
        if not 1 < length < 2_000_000:
            raise GameError("The server sent something that isn't a Minecraft reply.")
        body = await asyncio.wait_for(reader.readexactly(length), TIMEOUT)
        latency = round((time.monotonic() - started) * 1000)
    except (asyncio.IncompleteReadError, asyncio.TimeoutError, OSError):
        raise GameError("The server answered, but not like a Minecraft server.")
    finally:
        writer.close()
    pos = 0
    while body[pos] & 0x80:  # skip the packet id
        pos += 1
    pos += 1
    size = shift = 0
    while True:  # string length
        byte = body[pos]
        pos += 1
        size |= (byte & 0x7F) << shift
        if not byte & 0x80:
            break
        shift += 7
    try:
        data = json.loads(body[pos:pos + size].decode("utf-8", "replace"))
    except ValueError:
        raise GameError("The server sent a status I couldn't read.")
    players = data.get("players", {})
    return {
        "online": True, "game": "minecraft", "latency": latency,
        "version": str(data.get("version", {}).get("name", "?")), "motd": clean_motd(_flatten_motd(data.get("description", ""))),
        "count": int(players.get("online", 0)), "max": int(players.get("max", 0)),
        "players": [str(p.get("name", "?")) for p in players.get("sample", []) if isinstance(p, dict) and p.get("name") and not str(p.get("name")).startswith("§")],
        "complete": False, "map": None,
    }


# ---------------------------------------------------------------------------------------------- udp helper
class _Udp(asyncio.DatagramProtocol):
    def __init__(self):
        self.queue = asyncio.Queue()

    def datagram_received(self, data, addr):
        self.queue.put_nowait(data)


async def _udp_open(host, port):
    await ensure_public(host)
    loop = asyncio.get_running_loop()
    try:
        transport, proto = await loop.create_datagram_endpoint(_Udp, remote_addr=(host, port))
    except OSError:
        raise GameError(f"I couldn't reach `{host}`.")
    return transport, proto


async def _udp_ask(transport, proto, packet):
    transport.sendto(packet)
    try:
        return await asyncio.wait_for(proto.queue.get(), TIMEOUT)
    except asyncio.TimeoutError:
        raise GameError("The server didn't answer. It may be offline, or that port isn't open for queries.")


# ---------------------------------------------------------------------------------------------- minecraft query (full player list)
async def mc_query(host, port):
    """The Query protocol (needs enable-query=true on the server). Gives the complete player list and the world name."""
    transport, proto = await _udp_open(host, port)
    try:
        session = random.randint(1, 0x0FFFFFFF) & 0x0F0F0F0F
        reply = await _udp_ask(transport, proto, b"\xfe\xfd\x09" + struct.pack(">i", session))
        try:
            token = int(reply[5:].split(b"\x00")[0])
        except ValueError:
            raise GameError("That isn't a Minecraft Query port.")
        reply = await _udp_ask(transport, proto, b"\xfe\xfd\x00" + struct.pack(">ii", session, token) + b"\x00\x00\x00\x00")
    finally:
        transport.close()
    body = reply[16:]
    head, _, tail = body.partition(b"\x00\x01player_\x00\x00")
    parts = head.split(b"\x00")
    info = {parts[i].decode("utf-8", "replace"): parts[i + 1].decode("utf-8", "replace") for i in range(0, len(parts) - 1, 2)}
    names = [n.decode("utf-8", "replace") for n in tail.split(b"\x00") if n]
    return {"players": names, "map": info.get("map"), "count": int(info.get("numplayers", len(names)) or 0), "max": int(info.get("maxplayers", 0) or 0), "version": info.get("version"), "plugins": info.get("plugins", "")}


# ---------------------------------------------------------------------------------------------- minecraft bedrock
async def mc_bedrock_status(host, port=19132):
    transport, proto = await _udp_open(host, port)
    magic = bytes.fromhex("00ffff00fefefefefdfdfdfd12345678")
    started = time.monotonic()
    try:
        reply = await _udp_ask(transport, proto, b"\x01" + struct.pack(">q", int(time.time() * 1000)) + magic + struct.pack(">q", random.getrandbits(62)))
    finally:
        transport.close()
    latency = round((time.monotonic() - started) * 1000)
    if not reply or reply[0] != 0x1C or len(reply) < 35:
        raise GameError("That doesn't look like a Bedrock server.")
    text = reply[35:].decode("utf-8", "replace").split(";")
    def field(i, default=""):
        return text[i] if len(text) > i else default
    return {"online": True, "game": "bedrock", "latency": latency, "version": field(3), "motd": clean_motd(field(1)), "count": int(field(4, "0") or 0), "max": int(field(5, "0") or 0),
            "players": [], "complete": False, "map": field(7) or None}


# ---------------------------------------------------------------------------------------------- steam / source (a2s)
HEADER = b"\xff\xff\xff\xff"


def _cstr(data, pos):
    end = data.index(b"\x00", pos)
    return data[pos:end].decode("utf-8", "replace"), end + 1


async def a2s_status(host, port):
    transport, proto = await _udp_open(host, port)
    request = HEADER + b"TSource Engine Query\x00"
    try:
        started = time.monotonic()
        reply = await _udp_ask(transport, proto, request)
        if reply[4:5] == b"\x41":
            reply = await _udp_ask(transport, proto, request + reply[5:9])
        latency = round((time.monotonic() - started) * 1000)
        if reply[4:5] != b"\x49":
            raise GameError("That server didn't answer like a Steam game server.")
        pos = 6
        name, pos = _cstr(reply, pos)
        world, pos = _cstr(reply, pos)
        _, pos = _cstr(reply, pos)
        game, pos = _cstr(reply, pos)
        pos += 2
        count, maximum, bots = reply[pos], reply[pos + 1], reply[pos + 2]
        names = []
        try:
            answer = await _udp_ask(transport, proto, HEADER + b"\x55" + b"\xff\xff\xff\xff")
            if answer[4:5] == b"\x41":
                answer = await _udp_ask(transport, proto, HEADER + b"\x55" + answer[5:9])
            if answer[4:5] == b"\x44":
                total, at = answer[5], 6
                for _ in range(total):
                    at += 1
                    player, at = _cstr(answer, at)
                    at += 8
                    if player:
                        names.append(player)
        except (GameError, ValueError, IndexError):
            pass
    except (ValueError, IndexError):
        raise GameError("That server sent a reply I couldn't read.")
    finally:
        transport.close()
    return {"online": True, "game": "source", "latency": latency, "version": game, "motd": name, "count": max(0, count - bots), "max": maximum, "players": names, "complete": len(names) >= count - bots, "map": world}


# ---------------------------------------------------------------------------------------------- rcon
class Rcon:
    """Source RCON, which Minecraft servers (enable-rcon=true) and many other games also speak."""

    def __init__(self, host, port, password):
        self.host, self.port, self.password = host, port, password
        self.reader = self.writer = None

    async def __aenter__(self):
        await ensure_public(self.host)
        try:
            self.reader, self.writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), TIMEOUT)
        except (OSError, asyncio.TimeoutError):
            raise GameError("I couldn't connect to RCON. Check the RCON port, and that RCON is turned on and not blocked by a firewall.")
        kind, ident, _ = await self._send(3, self.password)
        if ident == -1:
            raise GameError("RCON refused the password.")
        return self

    async def __aexit__(self, *exc):
        if self.writer:
            self.writer.close()

    async def _send(self, kind, body):
        payload = struct.pack("<ii", 1, kind) + body.encode("utf-8") + b"\x00\x00"
        self.writer.write(struct.pack("<i", len(payload)) + payload)
        await self.writer.drain()
        try:
            while True:
                size = struct.unpack("<i", await asyncio.wait_for(self.reader.readexactly(4), TIMEOUT))[0]
                if not 10 <= size <= 5000:
                    raise GameError("RCON sent something unexpected.")
                data = await asyncio.wait_for(self.reader.readexactly(size), TIMEOUT)
                ident, reply = struct.unpack("<ii", data[:8])
                if kind == 3 and reply != 2 and ident != -1:
                    continue  # some servers send an empty response packet before the auth reply
                return reply, ident, data[8:-2].decode("utf-8", "replace")
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, OSError):
            raise GameError("RCON stopped answering.")

    async def run(self, command):
        return MC_COLOURS.sub("", (await self._send(2, command))[2]).strip()


# ---------------------------------------------------------------------------------------------- terraria (tshock rest)
async def tshock(host, port, token, path, **params):
    await ensure_public(host)
    params["token"] = token
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
            async with session.get(f"http://{host}:{port}{path}", params=params, allow_redirects=False) as response:
                data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        raise GameError("I couldn't reach the Terraria server's REST API. Check the address, the REST port and that TShock's REST API is turned on.")
    if str(data.get("status")) != "200":
        raise GameError(f"TShock said: {str(data.get('error') or data.get('response') or data.get('status'))[:200]}")
    return data


async def terraria_status(host, port, token):
    started = time.monotonic()
    data = await tshock(host, port, token, "/v2/server/status", players="true", rules="false")
    players = [str(p.get("nickname") or p.get("username") or "?") for p in data.get("players", []) if isinstance(p, dict)]
    return {"online": True, "game": "terraria", "latency": round((time.monotonic() - started) * 1000), "version": str(data.get("serverversion", "")), "motd": str(data.get("name", "")),
            "count": int(data.get("playercount", len(players)) or 0), "max": int(data.get("maxplayers", 0) or 0), "players": players, "complete": True, "map": str(data.get("world", "")) or None}


# ---------------------------------------------------------------------------------------------- pterodactyl panel
async def panel(url, key, server_id, method, path, body=None):
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0]
    await ensure_public(host)
    if not re.fullmatch(r"[A-Za-z0-9-]{1,40}", server_id):
        raise GameError("That panel server id isn't valid.")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.request(method, f"{url.rstrip('/')}/api/client/servers/{server_id}{path}", json=body, allow_redirects=False,
                                       headers={"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"}) as response:
                if response.status in (401, 403):
                    raise GameError("The panel refused the API key.")
                if response.status >= 400:
                    raise GameError(f"The panel answered with an error ({response.status}).")
                return await response.text()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        raise GameError("I couldn't reach the panel.")


# ---------------------------------------------------------------------------------------------- one call for the cog
async def check(cfg):
    """Asks a saved server how it is doing. Returns the status dict, or {"online": False, "error": ...}."""
    game, host, port = cfg["game"], cfg["host"], cfg["port"]
    try:
        if game == "minecraft":
            status = await mc_java_status(host, port)
            if cfg.get("query_port"):
                try:
                    query = await mc_query(host, cfg["query_port"])
                    status.update(players=query["players"], complete=True, map=query["map"] or status["map"])
                except GameError:
                    pass
            return status
        if game == "bedrock":
            return await mc_bedrock_status(host, port)
        if game == "source":
            return await a2s_status(host, port)
        if game == "terraria":
            return await terraria_status(host, port, cfg.get("token", ""))
    except GameError as error:
        return {"online": False, "game": game, "error": str(error), "players": [], "count": 0, "max": 0}
    return {"online": False, "game": game, "error": "Unknown game.", "players": [], "count": 0, "max": 0}
