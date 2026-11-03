from __future__ import annotations

import asyncio
import contextlib
import json
import pathlib
import time

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import protocol as P
from link import BaseLink, LinkError, RealLink, RejectError

WEB_DIST = pathlib.Path(__file__).resolve().parents[1] / "web" / "dist"


@asynccontextmanager
async def lifespan(_app):
    yield
    with contextlib.suppress(Exception):
        await hub.link.disconnect()


app = FastAPI(title="设备控制台", lifespan=lifespan)


class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.link: BaseLink = RealLink(self.broadcast)
        self.history: list[dict] = []
        self.lock = asyncio.Lock()

    async def broadcast(self, event: dict):
        if event.get("type") in ("tx", "rx", "log", "error"):
            self.history.append(event)
            del self.history[:-400]
        dead = []
        for ws in self.clients:
            try:
                await ws.send_text(json.dumps(event, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

hub = Hub()


@app.get("/api/catalog")
async def catalog(fw: str | None = None):
    return JSONResponse(P.catalog_json(fw or getattr(hub.link, "fw", None)))


def encode_params(spec: dict, values: dict) -> bytes:
    out = b""
    for p in spec.get("params") or []:
        kind, name = p["kind"], p["name"]
        v = values.get(name, p.get("default"))
        if kind == "const":
            out += bytes.fromhex(p["value"])
        elif kind == "u8":
            out += bytes([int(v) & 0xFF])
        elif kind == "id6":
            h = str(v or "").replace(" ", "").replace(":", "")
            if len(h) != 12:
                raise RejectError(f"{p['label']} 需要 6 字节（12 个十六进制字符），收到 {len(h)//2} 字节")
            out += bytes.fromhex(h)
        elif kind == "digits4":
            s = str(v or "")
            if len(s) != 4 or not s.isdigit():
                raise RejectError(f"{p['label']} 需要 4 个数字字符")
            out += s.encode("ascii")
        elif kind == "time6":
            if isinstance(v, list) and len(v) == 6:
                out += bytes(int(x) & 0xFF for x in v)
            else:
                t = time.gmtime()
                out += bytes([t.tm_year % 100, t.tm_mon, t.tm_mday,
                              t.tm_hour, t.tm_min, t.tm_sec])
        elif kind == "raw":
            h = str(v or "").replace(" ", "")
            out += bytes.fromhex(h) if h else b""
        else:
            raise RejectError(f"未知参数类型 {kind}")
    return out


def build_for(spec: dict, values: dict) -> bytes:
    if spec.get("raw"):
        return bytes.fromhex(spec["raw"])
    cmd = spec["name"].encode("ascii")
    params = encode_params(spec, values)
    chk = spec.get("chk_fw") if not params else None
    return P.build_frame(cmd, params, chk_override=chk)


async def handle(msg: dict):
    op = msg.get("op")
    link = hub.link

    if op == "hello":
        await hub.broadcast({"type": "state", **link.snapshot()})
        return
    if op == "scan":
        devices = await link.scan(float(msg.get("seconds", 6)))
        await hub.broadcast({"type": "scan", "devices": devices, "at": time.time()})
        return
    if op == "connect":
        await link.begin_connect(msg["address"])
        return
    if op == "disconnect":
        if await link.cancel_connect():
            return
        await link.disconnect()
        return
    if op == "setFw":
        await link.set_fw(msg.get("fw"))
        return
    if op == "sendRaw":
        h = str(msg.get("hex", "")).replace(" ", "").replace(":", "")
        try:
            frame = bytes.fromhex(h)
        except ValueError as e:
            raise RejectError(f"十六进制解析失败：{e}") from e
        if not frame:
            raise RejectError("空帧")
        if len(frame) > 64:
            raise RejectError(f"{len(frame)} 字节 —— 请求帧最长 16 B（PAIR），拒绝发送")
        label = str(msg.get("label") or "RAW")
        await link.send(frame, label, paged=bool(msg.get("paged")))
        return
    if op == "send":
        spec = P.BY_NAME.get(msg["cmd"])
        if spec is None:
            raise RejectError(f"未知命令 {msg['cmd']}")
        if spec.get("blocked"):
            raise RejectError(f"{spec['name']} 已被拦下：{spec['blocked']}")
        frame = build_for(spec, msg.get("values") or {})
        await link.send(frame, spec["name"], paged=bool(spec.get("paged")))
        return
    raise LinkError(f"未知操作 {op}")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    hub.clients.add(ws)
    await ws.send_text(json.dumps({"type": "state", **hub.link.snapshot()},
                                  ensure_ascii=False))
    for ev in hub.history[-120:]:
        await ws.send_text(json.dumps({**ev, "replay": True}, ensure_ascii=False))
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            async with hub.lock:
                try:
                    await handle(msg)
                except LinkError as e:
                    await hub.broadcast({
                        "type": "error", "at": time.time(), "text": str(e),
                        "kind": "reject" if isinstance(e, RejectError) else "link"})
                except Exception as e:
                    await hub.broadcast({"type": "error", "at": time.time(),
                                         "text": f"{type(e).__name__}: {e}"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)


if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(WEB_DIST / "index.html")
else:
    @app.get("/")
    async def index_missing():
        return JSONResponse(
            {"error": "前端还没构建",
             "fix": "cd client/web && npm install && npm run build，"
                    "或开发时 npm run dev（5173 端口，已配好到 8787 的代理）"},
            status_code=503)
