from __future__ import annotations

import asyncio
import contextlib
import os
import time

import protocol as P


class LinkError(Exception):
    pass


class RejectError(LinkError):
    pass


class BaseLink:
    kind = "base"

    def __init__(self, emit):
        self.emit = emit
        self.address: str | None = None
        self.name: str | None = None
        self.mtu: int | None = None
        self.mtu_floor = 0
        self.fw: str | None = None
        self.phase = "idle"
        self.phase_since = time.time()
        self.chrc_count = 0
        self.paging_until = 0.0
        self._connect_task: asyncio.Task | None = None
        self.last_tx_at: float | None = None
        self.last_tx_cmd: str | None = None

    async def _phase(self, phase: str, **extra):
        if phase != self.phase:
            self.phase_since = time.time()
        self.phase = phase
        await self.emit({"type": "state", **self.snapshot(), **extra})

    async def begin_connect(self, address: str):
        if self._connect_task and not self._connect_task.done():
            raise LinkError("已经在连接中 —— 先按「取消连接」")

        async def run():
            try:
                await self.connect(address)
            except LinkError as e:
                await self.emit({"type": "error", "at": time.time(), "text": str(e)})
            except Exception as e:
                await self.emit({"type": "error", "at": time.time(),
                                 "text": f"{type(e).__name__}: {e}"})

        self._connect_task = asyncio.get_running_loop().create_task(run())

    async def cancel_connect(self) -> bool:
        t, self._connect_task = self._connect_task, None
        if not (t and not t.done()):
            return False
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
        with contextlib.suppress(Exception):
            await self.disconnect()
        await self._log("info", "连接已取消")
        return True

    async def _log(self, level: str, text: str):
        await self.emit({"type": "log", "level": level, "text": text,
                         "at": time.time()})

    @property
    def mtu_effective(self) -> int | None:
        vals = [v for v in (self.mtu, self.mtu_floor or None) if v]
        return max(vals) if vals else None

    def snapshot(self) -> dict:
        return {
            "kind": self.kind, "phase": self.phase, "address": self.address,
            "name": self.name, "mtu": self.mtu, "mtuFloor": self.mtu_floor or None,
            "mtuEffective": self.mtu_effective,
            "chrcCount": self.chrc_count, "adapter": getattr(self, "adapter", None),
            "fw": self.fw,
            "phaseSince": self.phase_since,
            "phaseLimit": getattr(self, "_gatt_wait", None),
            "knownCount": len(getattr(self, "_devices", {})),
        }

    async def set_fw(self, fw: str | None):
        fw = (fw or "").strip() or None
        if fw == self.fw:
            return
        self.fw = fw
        await self.emit({"type": "state", **self.snapshot()})

    async def _on_notify(self, data: bytes):
        now = time.time()
        rtt = None
        if self.last_tx_at is not None:
            rtt = round((now - self.last_tx_at) * 1000)
        floor = len(data) + 3
        grew = floor > self.mtu_floor
        if grew:
            self.mtu_floor = floor
        parsed = P.parse_reply(bytes(data), mtu=self.mtu_effective,
                               paging=now < self.paging_until,
                               for_cmd=self.last_tx_cmd, fw=self.fw)
        await self.emit({"type": "rx", "at": now, "rtt": rtt,
                         "forCmd": self.last_tx_cmd, **parsed})

        fw_new = None
        if parsed.get("name") == "BVER":
            for f in parsed.get("fields") or []:
                if f["k"] == "固件版本":
                    fw_new = f["v"].strip()
        if fw_new and fw_new != self.fw:
            self.fw = fw_new
            await self._log("ok", f"GVER 读到固件 {fw_new} —— 目录与模板已自动切到该版"
                                  "（链路栏里仍可手改解释版本）")
        if grew or fw_new:
            await self.emit({"type": "state", **self.snapshot()})

    async def _note_tx(self, cmd_name: str, frame: bytes, paged: bool):
        self.last_tx_at = time.time()
        self.last_tx_cmd = cmd_name
        if paged:
            self.paging_until = self.last_tx_at + 3.0
        await self.emit({"type": "tx", "at": self.last_tx_at, "cmd": cmd_name,
                         "hex": frame.hex(), "size": len(frame)})


NAME_PREFIXES = ("PRTS", "DE")


def _is_family(name: str) -> bool:
    n = (name or "").strip().upper()
    return n.startswith(NAME_PREFIXES)


_HCI_DIR = "/sys/class/bluetooth"


def _adapters() -> list[str]:
    try:
        return sorted(n for n in os.listdir(_HCI_DIR)
                      if n.startswith("hci") and ":" not in n)
    except OSError:
        return []


def _pick_adapter() -> str | None:
    want = os.environ.get("PRTS_HCI", "").strip()
    if want:
        return want.rsplit("/", 1)[-1]
    return "hci1" if "hci1" in _adapters() else None


class RealLink(BaseLink):
    kind = "real"

    def __init__(self, emit):
        super().__init__(emit)
        self.adapter = _pick_adapter()
        self._client = None
        self._closing = False
        self._devices: dict = {}
        self._gatt_wait = float(os.environ.get("PRTS_GATT_WAIT", "70"))
        self._bond = os.environ.get("PRTS_BOND", "").strip().lower() \
            not in ("", "0", "false", "no", "off")

    async def scan(self, seconds: float = 6.0) -> list[dict]:
        from bleak import BleakScanner
        await self._phase("scanning")
        kw = {"adapter": self.adapter} if self.adapter else {}
        try:
            found = await BleakScanner.discover(timeout=seconds, return_adv=True, **kw)
        except Exception as e:
            await self._phase("idle")
            raise LinkError(f"扫描失败：{e}") from e
        out = []
        self._devices = {addr.upper(): dev for addr, (dev, _a) in found.items()}
        for addr, (dev, adv) in found.items():
            mfg = adv.manufacturer_data or {}
            name = dev.name or adv.local_name or ""
            out.append({
                "address": addr,
                "name": name,
                "rssi": adv.rssi,
                "services": list(adv.service_uuids or []),
                "mfg": {str(k): v.hex() for k, v in mfg.items()},
                "likely": bool(adv.service_uuids
                               and P.SVC_UUID in [u.lower() for u in adv.service_uuids]),
                "family": _is_family(name),
            })
        out.sort(key=lambda d: (-int(d["family"]), -int(d["likely"]), -(d["rssi"] or -999)))
        await self._phase("idle")
        return out

    async def connect(self, address: str):
        from bleak import BleakClient
        if self._client is not None:
            raise LinkError("已有连接，先断开")
        self.address = address.upper()
        self.mtu_floor = 0
        self.fw = None
        await self._phase("connecting")
        have = _adapters()
        via = (self.adapter if self.adapter else "BlueZ 默认")
        if self.adapter and self.adapter not in have:
            via += f" ⚠ 不存在！本机只有 {', '.join(have) or '(无)'}"
        elif not self.adapter:
            via += f"（本机有 {', '.join(have) or '(无)'}）"
        await self._log("info", f"连接 {self.address} via {via}（GATT 发现最多等 "
                                f"{self._gatt_wait:.0f} s —— 连接间隔 1000 ms，急不得）")

        def on_disconnect(_c):
            asyncio.get_running_loop().create_task(self._handle_drop())

        kw = {"adapter": self.adapter} if self.adapter else {}
        target = self._devices.get(self.address)
        if target is None:
            await self._log("warn",
                            "没有该地址的扫描缓存，只能按地址连 —— bleak 会先花最多 "
                            f"{self._gatt_wait:.0f} s 等一条广播。设备若被手机 App 或"
                            "上一次会话占着就不会广播，这一步会一直等到超时。\n"
                            "建议：先「扫描设备」，从列表里点进来。")
        client = BleakClient(target or self.address,
                             disconnected_callback=on_disconnect,
                             timeout=self._gatt_wait, **kw)

        async def heartbeat():
            t0 = time.time()
            while True:
                await asyncio.sleep(10)
                el = time.time() - t0
                await self._log("info",
                                f"仍在建链 + GATT 发现：已等 {el:.0f} s / 上限 "
                                f"{self._gatt_wait:.0f} s。该设备连接间隔 1000 ms，"
                                "30–60 s 属正常，不是卡死。要放弃按「取消连接」。")

        hb = asyncio.get_running_loop().create_task(heartbeat())
        try:
            await client.connect()
        except asyncio.CancelledError:
            self._client = None
            raise
        except Exception as e:
            self._client = None
            await self._phase("idle")
            raise LinkError(
                f"连接失败：{type(e).__name__}: {e}\n"
                "常见原因：\n"
                "  · 设备只接受一条连接 —— 手机 App 要先退出；\n"
                "  · 本机适配器正在发信标（先停掉 beacon）；\n"
                "  · 「找不到设备」= 等广播超时，多半是设备已被别人连着。") from e
        finally:
            hb.cancel()

        self._client = client
        await self._phase("discovering")
        chrcs = {}
        for svc in client.services:
            for ch in svc.characteristics:
                chrcs[ch.uuid.lower()] = ch
        self.chrc_count = len(chrcs)

        if P.NOTIFY_UUID not in chrcs or P.WRITE_UUID not in chrcs:
            await self._fail_and_close(
                f"未找到 fef1/fef2。实际发现的特征值：{sorted(chrcs) or '(空)'}\n"
                "多半是设备侧状态问题：按一下按键让它回到正常广播态，或断电重启后再试。\n"
                "本工具不会去清 BlueZ 缓存 —— 那会连累你其它蓝牙设备。"
                f"要清请自行执行：bluetoothctl remove {self.address}")

        # 别用 bleak 的 _acquire_mtu()（会抢占 fef1，随后 StartNotify 失败）或 mtu_size（没测时恒为 23）
        self.mtu = await self._read_att_mtu(client, chrcs[P.NOTIFY_UUID])
        if self.mtu is None:
            await self._log("warn",
                            "没从 BlueZ 属性读到 ATT MTU（可能 BlueZ < 5.62）—— 面板显示"
                            "「未测」，**不会**拿默认 23 顶替。收到帧后会从帧长反推下界。")

        n, w = chrcs[P.NOTIFY_UUID], chrcs[P.WRITE_UUID]
        await self._log("info",
                        f"fef1 handle=0x{n.handle:04x} props={','.join(n.properties)} · "
                        f"fef2 handle=0x{w.handle:04x} props={','.join(w.properties)} · "
                        f"ATT MTU {self.mtu if self.mtu else '未测'}")
        if "notify" not in n.properties and "indicate" not in n.properties:
            await self._fail_and_close(
                f"fef1 的属性里没有 notify（实际 {n.properties}）。\n"
                "真机 fef1 的 props 应为 0x10 notify。读到别的，多半是 BlueZ 缓存的是"
                "旧一代固件的 GATT 库。")

        async def cb(_ch, data: bytearray):
            await self._on_notify(bytes(data))

        for attempt in (1, 2):
            try:
                await client.start_notify(P.NOTIFY_UUID, cb)
                break
            except Exception as e:
                if attempt == 1:
                    await self._log("warn", f"订阅 fef1 失败（第 1 次）：{e} —— 等 1.5 s 重试")
                    await asyncio.sleep(1.5)
                    continue
                await self._fail_and_close(
                    f"订阅 fef1 notify 失败：{type(e).__name__}: {e}\n"
                    f"（写 CCCD 0x2902 被设备的 ATT 服务端拒了，句柄 0x{n.handle:04x}）\n"
                    "按可能性排序，逐条排除：\n"
                    "  1. 另一个订阅者还在 —— 手机 App、别的 BLE 脚本、"
                    "或本控制台上一次没断干净的会话。先全部退掉。\n"
                    "  2. BlueZ 缓存的 GATT 库是旧的（设备刷过 OTA 后句柄变了）："
                    f"bluetoothctl remove {self.address} 再重连。"
                    "⚠ 这会清掉该设备的配对缓存，但不动你其它蓝牙设备。\n"
                    "  3. 设备不在正常广播态 —— 按一下按键，或断电重启。\n"
                    "  4. 设备要求先加密才让写 CCCD —— 用 bluetoothctl pair 配对后再试。\n"
                    "链路已断开，设备不会被晾在已连接态。", cause=e)

        await self._phase("linked")
        await self._log("ok", f"已订阅 fef1 notify · 特征值 {self.chrc_count} 个 · "
                              f"MTU {self.mtu}")

        if self._bond:
            try:
                await self._client.pair()
                await self._log("ok",
                                "已发起绑定 —— BlueZ 将缓存本设备 GATT 库，下次连接"
                                "应跳过冷发现（与手机 App 同机制）。\n"
                                f"撤销：bluetoothctl remove {self.address}")
            except Exception as e:
                await self._log("warn",
                                "绑定失败（不影响本次会话，只是下次仍是 42 s 冷发现）："
                                f"{type(e).__name__}: {e}\n"
                                "部分适配器要先起配对 agent（bluetoothctl 里 agent on）。")

        if self.mtu and self.mtu < P.MTU_CUID_PAGE:
            await self._log("warn",
                            f"MTU {self.mtu} < {P.MTU_CUID_PAGE}：CUID 分页会被截到 "
                            f"{self.mtu - 3} B，看起来像「表里没数据」。"
                            f"BTOKEN 也需要 ≥ {P.MTU_TOKEN}。")

    @staticmethod
    async def _read_att_mtu(client, notify_chrc) -> int | None:
        from dbus_fast.message import Message
        from dbus_fast.constants import MessageType
        from bleak.backends.bluezdbus import defs
        try:
            bus = getattr(getattr(client, "_backend", None), "_bus", None)
            path = notify_chrc.obj[0]
            if bus is None or not isinstance(path, str):
                return None
            reply = await bus.call(Message(
                destination=defs.BLUEZ_SERVICE,
                path=path,
                interface=defs.PROPERTIES_INTERFACE,
                member="Get",
                signature="ss",
                body=[defs.GATT_CHARACTERISTIC_INTERFACE, "MTU"],
            ))
            if reply is None or reply.message_type != MessageType.METHOD_RETURN:
                return None
            val = reply.body[0].value if reply.body else None
            mtu = int(val) if val else None
            return mtu if mtu and mtu > 0 else None
        except Exception:
            return None

    async def _fail_and_close(self, msg: str, cause: Exception | None = None):
        with contextlib.suppress(Exception):
            await self.disconnect()
        raise LinkError(msg) from cause

    async def send(self, frame: bytes, cmd_name: str, paged: bool = False):
        if self._client is None:
            raise LinkError("未连接")
        await self._note_tx(cmd_name, frame, paged)
        try:
            await self._client.write_gatt_char(P.WRITE_UUID, frame, response=True)
        except Exception as e:
            raise LinkError(f"写入 fef2 失败：{e}") from e

    async def _handle_drop(self):
        if self._closing or self._client is None:
            return
        self._client = None
        self.mtu = None
        self.mtu_floor = 0
        self.chrc_count = 0
        await self._log("error", "链路已断开（对端主动断开或超时）")
        await self._phase("idle")

    async def disconnect(self):
        c, self._client = self._client, None
        if c is None:
            self._closing = False
            await self._phase("idle")
            return
        self._closing = True
        await self._phase("disconnecting")
        try:
            await c.stop_notify(P.NOTIFY_UUID)
        except Exception:
            pass
        try:
            await c.disconnect()
        except Exception as e:
            await self._log("warn", f"断开时出错（可忽略）：{e}")
        self.mtu = None
        self.mtu_floor = 0
        self.chrc_count = 0
        self._closing = False
        await self._log("info", "已断开 —— 设备可以重新广播了")
        await self._phase("idle")
