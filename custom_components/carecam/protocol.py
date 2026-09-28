"""Local (no-cloud) client for CareCam / Huiyun / YGTek (ZJ-TRAS) cameras.

Protocol reverse-engineered and confirmed live:
- TCP 16668. 8-byte header: 23 24 | METHOD_hi METHOD_lo | body length (big-endian)
  | EncType (0x30 plaintext / 0x31 AES) | 00.
- Login (METHOD 3114) is sent plaintext and carries UserToken = the device OwnerToken.
  The camera validates it locally; no cloud is used. The 3115 reply returns a session
  AES key/iv used for every later message. AES-128-CBC, PKCS#7, key = iv = first 16
  bytes of the login EncKey (we use the first 16 bytes of the OwnerToken to bootstrap).
"""

from __future__ import annotations

import asyncio
import json
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PORT = 16668

# METHOD codes (from libbusiness.so; the 0x34xx JSON family, confirmed live)
M_LOGIN = "3114"
M_PTZ = "3428"
M_LENS = "3450"
# Directions for PTZ BODY "PTZControl" (strings); "0" stops.
# Step is the distance: the app sends 360 (keep turning until stopped) and speed 7.
MOVE_STEP, MOVE_SPEED = "360", "7"
PTZ_UP, PTZ_DOWN, PTZ_LEFT, PTZ_RIGHT, PTZ_STOP = "1", "2", "3", "4", "0"


class CareCamError(Exception):
    """Talking to the camera failed."""


def _pad(data: bytes) -> bytes:
    n = 16 - (len(data) % 16) or 16
    return data + bytes([n]) * n


def _unpad(data: bytes) -> bytes:
    return data[:-data[-1]] if data and 1 <= data[-1] <= 16 else data


class CareCamClient:
    """One short-lived session: connect, login, send a few commands, close."""

    def __init__(self, host: str, owner_token: str) -> None:
        self._host = host
        self._token = owner_token
        self._boot = owner_token[:16].encode()  # bootstrap AES key/iv
        self._key = self._boot
        self._iv = self._boot
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def __aenter__(self) -> "CareCamClient":
        await self._connect()
        await self._login()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _connect(self) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, PORT), timeout=6
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise CareCamError(f"connect failed: {err}") from err

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
            self._writer = None

    def _frame(self, method: str, body: dict, plaintext: bool) -> bytes:
        payload = json.dumps({"METHOD": method, "SEQID": "1", "BODY": body}).encode()
        if plaintext:
            enc_type = 0x30
        else:
            payload = Cipher(
                algorithms.AES(self._key), modes.CBC(self._iv)
            ).encryptor().update(_pad(payload))
            enc_type = 0x31
        header = (
            b"\x23\x24"
            + bytes([int(method[:2], 16), int(method[2:], 16)])
            + struct.pack(">H", len(payload))
            + bytes([enc_type, 0])
        )
        return header + payload

    async def _read_msg(self) -> tuple[str, dict]:
        """Read one message; return (METHOD from the header, JSON body or {})."""
        assert self._reader is not None
        try:
            header = await asyncio.wait_for(self._reader.readexactly(8), timeout=6)
            length = struct.unpack(">H", header[4:6])[0]
            body = await asyncio.wait_for(
                self._reader.readexactly(length), timeout=6
            )
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, OSError) as err:
            raise CareCamError(f"no reply: {err}") from err
        method = f"{header[2]:02X}{header[3]:02X}"
        if not body:
            return method, {}  # e.g. the 15 s heartbeat, METHOD 0000
        if header[6] == 0x31:
            for key, iv in ((self._key, self._iv), (self._boot, self._boot)):
                try:
                    plain = _unpad(
                        Cipher(algorithms.AES(key), modes.CBC(iv))
                        .decryptor()
                        .update(body)
                    )
                    if plain[:1] in (b"{", b"["):
                        body = plain
                        break
                except ValueError:
                    continue
        try:
            return method, json.loads(body.decode(errors="replace"))
        except ValueError as err:
            raise CareCamError("bad reply") from err

    async def _send(self, method: str, body: dict, plaintext: bool = False) -> dict:
        assert self._writer is not None
        self._writer.write(self._frame(method, body, plaintext))
        await self._writer.drain()
        # Skip heartbeats and anything else until the reply (request METHOD + 1)
        expected = f"{int(method, 16) + 1:04X}"
        for _ in range(20):
            got, reply = await self._read_msg()
            if got == expected:
                break
        else:
            raise CareCamError(f"no {expected} reply")
        if reply.get("CODE") not in (None, "0"):
            raise CareCamError(f"{method} rejected: CODE {reply.get('CODE')}")
        return reply

    async def _login(self) -> None:
        reply = await self._send(
            M_LOGIN,
            {
                "UserToken": self._token,
                "OsType": "1",
                "SDKVersion": "50663936",
                "EncType": "49",
                "EncKey": self._boot.decode(),
                "EncLoad": self._boot.decode(),
            },
            plaintext=True,
        )
        info = reply.get("BODY", {})
        if info.get("EncKey") and info.get("EncLoad"):
            self._key = info["EncKey"].encode()[:16]
            self._iv = info["EncLoad"].encode()[:16]

    # ---- public commands ---------------------------------------------------

    async def ptz(self, direction: str, seconds: float = 0.6) -> None:
        """Nudge: move in a direction, then stop."""
        await self._send(
            M_PTZ,
            {"PTZType": "0", "PTZControl": direction, "Step": MOVE_STEP, "Speed": MOVE_SPEED},
        )
        await asyncio.sleep(seconds)
        await self._send(
            M_PTZ,
            {"PTZType": "0", "PTZControl": PTZ_STOP, "Step": "8", "Speed": "8"},
        )

    async def set_lens(self, lens_id: int) -> None:
        await self._send(M_LENS, {"LenID": str(lens_id)})


async def async_check(host: str, owner_token: str) -> None:
    """Validate host + token by logging in once. Raise CareCamError otherwise."""
    async with CareCamClient(host, owner_token):
        pass


class CareCamSession:
    """One shared, reused connection per camera; commands run one at a time.

    Overlapping short-lived logins made the camera answer the wrong session
    ("bad reply"), so every command goes through this single queue instead.
    """

    AUTO_STOP = 30.0  # seconds: stop a held move if the release never arrives

    def __init__(self, host: str, owner_token: str) -> None:
        self._host = host
        self._token = owner_token
        self._client: CareCamClient | None = None
        self._lock = asyncio.Lock()
        self._auto_stop: asyncio.TimerHandle | None = None
        self.speed = "4"  # PTZ speed 1..8; set by the PTZ speed number entity
        self.step = "8"  # distance per tap-nudge (Step 360 = a full turn)

    async def _run(self, action) -> None:
        # The camera drops about 1 in 5 logins at random, and any other login
        # (e.g. the phone app) breaks our session, so reconnect and retry.
        async with self._lock:
            for attempt in range(1, 4):
                try:
                    if self._client is None:
                        client = CareCamClient(self._host, self._token)
                        await client._connect()
                        await client._login()
                        self._client = client
                    await action(self._client)
                    return
                except CareCamError:
                    await self._drop()
                    if attempt == 3:
                        raise
                    await asyncio.sleep(0.3)

    async def _drop(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _cancel_auto_stop(self) -> None:
        if self._auto_stop is not None:
            self._auto_stop.cancel()
            self._auto_stop = None

    async def move(self, direction: str) -> None:
        """Start moving and keep going until stop() (or the safety auto-stop)."""
        self._cancel_auto_stop()
        speed = self.speed
        await self._run(
            lambda c: c._send(
                M_PTZ,
                {"PTZType": "0", "PTZControl": direction, "Step": MOVE_STEP, "Speed": speed},
            )
        )
        loop = asyncio.get_running_loop()
        self._auto_stop = loop.call_later(
            self.AUTO_STOP, lambda: loop.create_task(self.stop())
        )

    async def stop(self) -> None:
        self._cancel_auto_stop()
        await self._run(
            lambda c: c._send(
                M_PTZ,
                {"PTZType": "0", "PTZControl": PTZ_STOP, "Step": "8", "Speed": "8"},
            )
        )

    async def nudge(self, direction: str, seconds: float = 0) -> None:
        """One small step. Step (not time) sets the distance, so a single move
        command of a small Step self-completes — no continuous move + stop."""
        self._cancel_auto_stop()
        step, speed = self.step, self.speed
        await self._run(
            lambda c: c._send(
                M_PTZ,
                {"PTZType": "0", "PTZControl": direction, "Step": step, "Speed": speed},
            )
        )

    async def set_lens(self, lens_id: int) -> None:
        await self._run(lambda c: c.set_lens(lens_id))

    async def play_sound(self, name: str) -> None:
        # Fire-and-forget: the camera's reply id isn't 34A4+1, so waiting/retrying
        # would replay the sound several times. Send once, don't wait.
        async def act(c: CareCamClient) -> None:
            c._writer.write(
                c._frame("34a4", {"CtrlType": "1", "Name": name}, False)
            )
            await c._writer.drain()

        await self._run(act)

    async def play_audio(self, name: str, mulaw: bytes) -> None:
        """Upload a G.711 mu-law clip (8kHz mono) and play it on the speaker."""
        mulaw = mulaw + b"\xff" * 1600  # ~200ms trailing silence so the tail isn't clipped
        size = len(mulaw)

        async def upload(c: CareCamClient) -> None:
            # open the sound-file upload channel (frame 21 1A, reply 21 1B)
            await c._send("211A", {"ChannelID": 0, "SoundName": name, "FileSize": size})
            ctr = 0
            for off in range(0, size, 1024):
                chunk = mulaw[off : off + 1024]
                pkt = (
                    b"\x23\x24\x50\x12"
                    + struct.pack(">H", len(chunk) + 4)
                    + b"\x00\x00"
                    + struct.pack(">H", 0)  # channel id
                    + struct.pack(">H", ctr)  # block counter
                    + chunk
                )
                c._writer.write(pkt)
                ctr += 1
            await c._writer.drain()

        await self._run(upload)
        await self.play_sound(name)

    async def sound_list(self) -> list[str]:
        body = await self.send("34a0", {"SoundType": 0})
        return [
            s["Name"]
            for s in body.get("SoundList", [])
            if isinstance(s, dict) and s.get("Name")
        ]

    async def send(self, method: str, body: dict | None = None) -> dict:
        """Send any command; return the reply BODY. Used by config entities."""
        result: dict = {}

        async def act(c: CareCamClient) -> None:
            reply = await c._send(method, body or {})
            result["body"] = reply.get("BODY", {})

        await self._run(act)
        return result.get("body", {})

    async def close(self) -> None:
        self._cancel_auto_stop()
        async with self._lock:
            await self._drop()
