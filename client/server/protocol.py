import pathlib
import sys

SOF = 0x41
EOF = 0x51
RESP_EOF = 0x52

try:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import profiles as _profiles
    from profiles import cmdset as _cmdset
except Exception:
    _profiles = _cmdset = None

PROFILES_OK = _profiles is not None

BASE = "-0000-1000-8000-00805f9b34fb"
SVC_UUID = "0000fef0" + BASE
NOTIFY_UUID = "0000fef1" + BASE
WRITE_UUID = "0000fef2" + BASE

MTU_TOKEN = 56
MTU_CUID_PAGE = 123


def checksum(body: bytes) -> int:
    return (SOF + sum(body)) & 0xFF


def build_frame(cmd, params: bytes = b"", chk_override=None) -> bytes:
    if isinstance(cmd, str):
        cmd = cmd.encode("ascii")
    body = cmd + bytes([len(cmd) + len(params) + 4]) + params
    chk = checksum(body) if chk_override is None else (chk_override & 0xFF)
    return bytes([SOF]) + body + bytes([chk, EOF])


def build_resp(cmd, params: bytes = b"", chk=None, ln=None) -> bytes:
    if isinstance(cmd, str):
        cmd = cmd.encode("ascii")
    n = (len(cmd) + len(params) + 3) if ln is None else (ln & 0xFF)
    body = cmd + bytes([n]) + params
    c = (sum(body) & 0xFF) if chk is None else (chk & 0xFF)
    return body + bytes([c, RESP_EOF])


def hexs(b: bytes) -> str:
    return " ".join(f"{x:02x}" for x in b)


def printable(b: bytes) -> str:
    return "".join(chr(x) if 32 <= x < 127 else "." for x in b)


def _u8(name, label, help_, options=None, default=0):
    return {"kind": "u8", "name": name, "label": label, "help": help_,
            "options": options, "default": default}


CMDS = [
    {"name": "GVER", "group": "read", "effect": "read", "since": "1.2.7",
     "title": "取固件版本", "params": [], "len_fw": 0x08, "chk_fw": 0x7D,
     "reply": {"name": "BVER", "len": 12, "tpl": "425645520c322e302e380052",
               "note": "CHK 恒为 00"},
     "rollback": None,
     "note": "固件 2.0.5 报 2.0.4。其他命令是否可用取决于版本，先发这条。"},

    {"name": "GVBAT", "group": "read", "effect": "read", "since": "1.2.7",
     "title": "取电量", "params": [], "len_fw": 0x09, "chk_fw": 0xBE,
     "reply": {"name": "BVBAT", "len": 11, "tpl": "42564241540b0100000052",
               "note": "参数：电量 / 提醒音 / 雷达"},
     "rollback": None,
     "note": "电量 0 充电中，1 满 … 6 低；提醒音 = TORLE 的当前值；雷达 = 是否在感应（0/1）。",
     "notes_fw": [
         {"from": "1.2.7", "to": "1.9.8",
          "text": "LEN 恒为 08（不等于整帧长）；参数 < 1.4.9 只有 1 B，1.4.9 – 1.6.5 为 2 B；CHK 照抄模板。"},
         {"from": "2.0.0", "to": None,
          "text": "LEN = 整帧长；CHK 由设备现算，不等于模板里的 00。"},
     ]},

    {"name": "GSPARM", "group": "read", "effect": "read", "since": "2.0.0",
     "title": "读定向雷达参数", "params": [], "len_fw": 0x0A, "chk_fw": 0x15,
     "reply": {"name": "BGPARM", "len": 14, "tpl": None, "note": "5 B 参数"},
     "rollback": None,
     "note": None},

    {"name": "GETTOKEN", "group": "read", "effect": "read", "since": "1.2.7",
     "title": "取 token", "params": [], "len_fw": 0x0C, "chk_fw": 0xAE,
     "reply": {"name": "BTOKEN", "len": 53, "tpl": None, "note": "44 B token"},
     "rollback": None,
     "mtu_min": MTU_TOKEN,
     "note": "需要 MTU ≥ 56，否则 token 读不全。"},

    {"name": "GBRGT", "group": "read", "effect": "read", "since": "2.0.0",
     "title": "读亮度", "params": [], "len_fw": 0x09, "chk_fw": None,
     "reply": {"name": "BGBRGT", "len": 10, "tpl": None, "note": "1 B 亮度"},
     "rollback": None,
     "notes_fw": [
         {"from": "2.0.0", "to": None,
          "text": "亮度 1e / 3c / 5a（30 / 60 / 90）对应等级 0 / 1 / 2。"},
     ],
     "note": None},

    {"name": "TIME?", "group": "read", "effect": "read", "since": "1.2.7",
     "title": "读设备时间", "params": [], "raw": "4154494d4551",
     "len_fw": None, "chk_fw": None,
     "reply": {"name": "(无命令名)", "len": 8, "tpl": None, "note": "42 <时间 6 B> 52"},
     "rollback": None,
     "note": "请求是固定字节，没有 LEN 和 CHK；应答没有命令名。"},

    {"name": "PTEST", "group": "read", "effect": "read", "since": "1.2.7",
     "title": "产测", "params": [], "raw": "41505445535451",
     "len_fw": None, "chk_fw": None,
     "reply": {"name": "BPTESTR", "len": 7, "tpl": "42505445535452", "note": None},
     "rollback": None,
     "note": "请求是固定字节，没有 LEN 和 CHK。"},

    {"name": "CUID", "group": "read", "effect": "read", "since": "1.2.7",
     "title": "读感应记录", "params": [], "len_fw": 0x08, "chk_fw": 0x6E,
     "reply": {"name": "BRCUID", "len": 10, "tpl": None,
               "note": "随后每 100 ms 推一页，共 20 页 × 120 B，以 52 52 结束"},
     "rollback": None,
     "mtu_min": MTU_CUID_PAGE,
     "paged": True,
     "note": "每条记录 12 B：对方身份 6 B + 时间 5 B（UTC）+ 近场 1 B，最多 200 条。"
             "每页只有 20 B 说明 MTU 不够，不是表空。"},

    {"name": "PLL", "group": "control", "effect": "write", "since": "1.2.7",
     "title": "开灯", "params": [], "len_fw": 0x07, "chk_fw": None,
     "reply": {"name": "BPLLOK", "len": 9, "tpl": "42504c4c4f4b09cd52", "note": None},
     "rollback": "STL 关灯", "note": None},

    {"name": "STL", "group": "control", "effect": "write", "since": "1.2.7",
     "title": "关灯", "params": [], "len_fw": 0x07, "chk_fw": None,
     "reply": {"name": "BSTLOK", "len": 9, "tpl": "4253544c4f4b09d852", "note": None},
     "rollback": "PLL 开灯", "note": None},

    {"name": "PLS", "group": "control", "effect": "write", "since": "1.2.7",
     "title": "放音", "params": [], "len_fw": 0x07, "chk_fw": None,
     "reply": {"name": "BPLSOK", "len": 9, "tpl": "42504c534f4b09d352", "note": None},
     "rollback": "STS 停音", "note": None},

    {"name": "STS", "group": "control", "effect": "write", "since": "1.2.7",
     "title": "停音", "params": [], "len_fw": 0x07, "chk_fw": None,
     "reply": {"name": "BSTSOK", "len": 9, "tpl": "425354534f4b09df52", "note": None},
     "rollback": "PLS 放音", "note": None},

    {"name": "BRGT", "group": "control", "effect": "write", "since": "2.0.0",
     "title": "设亮度", "len_fw": 0x09, "chk_fw": None,
     "params": [_u8("level", "亮度",
                    "1e / 3c / 5a → 等级 0 / 1 / 2；00 / 01 / 02 → 等级 2 / 1 / 0（反向）；其他值未定义。",
                    [{"v": 30, "t": "30 (0x1E) → 等级 0"},
                     {"v": 60, "t": "60 (0x3C) → 等级 1"},
                     {"v": 90, "t": "90 (0x5A) → 等级 2"},
                     {"v": 0, "t": "0 → 等级 2（反向）"},
                     {"v": 1, "t": "1 → 等级 1（反向）"},
                     {"v": 2, "t": "2 → 等级 0（反向）"}], 30)],
     "reply": {"name": "BBRGTOK", "len": 10, "tpl": None, "note": None},
     "rollback": "重发 BRGT 写回原值（先用 GBRGT 读）",
     "persists": "NVRAM，断电保持",
     "note": None},

    {"name": "RADAR", "group": "control", "effect": "write", "since": "1.9.5",
     "title": "切系统模式", "len_fw": 0x0A, "chk_fw": None,
     "params": [_u8("mode", "模式",
                    "00 常态，01 雷达。切换后广播里的模式字节变成 00 / 02。",
                    [{"v": 0, "t": "0 常态"},
                     {"v": 1, "t": "1 雷达"}])],
     "reply": {"name": "BRADAR", "len": 8, "tpl": None, "note": "没有 LEN 字段"},
     "rollback": "重发 RADAR 换回原模式（当前模式见广播里的模式字节）",
     "note": "进入雷达模式后设备开始记录感应。断电后是否保持未验证。"},

    {"name": "TORLE", "group": "control", "effect": "write", "since": "1.2.7",
     "title": "感应提醒音开关", "len_fw": 0x0A, "chk_fw": None,
     "params": [_u8("value", "提醒音",
                    "00 感应时只闪灯，其他值（01–ff）灯 + 声。",
                    [{"v": 0, "t": "0 只闪灯"},
                     {"v": 1, "t": "1 灯 + 声"}], 0)],
     "reply": {"name": "BTORLEOK", "len": 11, "tpl": "42544f524c454f4b0b2152", "note": None},
     "rollback": "重发 TORLE 写回原值（当前值见 GVBAT 的第 2 个参数）",
     "persists": "NVRAM，断电保持",
     "note": None},

    {"name": "SPARM", "group": "control", "effect": "write", "since": "2.0.0",
     "title": "设定向雷达口令", "len_fw": 0x0D, "chk_fw": None,
     "params": [{"kind": "digits4", "name": "code", "label": "口令",
                 "help": "4 个 ASCII 数字（30–39），即 0000–9999", "default": "0000"}],
     "reply": {"name": "BSPARM", "len": 8, "tpl": None, "note": "没有 LEN 字段"},
     "rollback": "重发 SPARM 写回原口令（先用 GSPARM 读）",
     "note": "设了口令后只感应口令相同的设备。"},

    {"name": "TIME", "group": "control", "effect": "write", "since": "1.2.7",
     "title": "同步时间", "len_fw": 0x0E, "chk_fw": None,
     "params": [{"kind": "time6", "name": "t", "label": "时间",
                 "help": "UTC，6 字节二进制（不是 BCD）：年后两位 0–99、月 1–12、日 1–31、"
                         "时 0–23、分 0–59、秒 0–59", "default": None}],
     "reply": {"name": "BRTIMEOK", "len": 11, "tpl": "425254494d454f4b0b6852",
               "note": "应答名是 BRTIMEOK"},
     "rollback": "重发 TIME 覆盖",
     "note": "感应记录的时间戳取自这个时钟。"},

    {"name": "ADDID", "group": "whitelist", "effect": "write", "since": "1.3.7",
     "title": "加白名单", "len_fw": 0x0F, "chk_fw": None,
     "params": [{"kind": "id6", "name": "id", "label": "身份",
                 "help": "任意 6 B（对方广播厂商数据的前 6 字节）", "default": ""}],
     "reply": {"name": "BADDIDOK", "len": 11, "tpl": "4241444449444f4b0b3552",
               "note": "表满时回字符串 UID FULL（不是帧）"},
     "rollback": "DELID 同一身份",
     "persists": "NVRAM（白名单，最多 200 条）",
     "note": "白名单里的身份不会被记入感应记录。"},

    {"name": "DELID", "group": "whitelist", "effect": "write", "since": "1.3.7",
     "title": "删白名单", "len_fw": 0x0F, "chk_fw": None,
     "params": [{"kind": "id6", "name": "id", "label": "身份", "help": "任意 6 B",
                 "default": ""}],
     "reply": {"name": "BDELIDOK", "len": 11, "tpl": "4244454c49444f4b0b4152",
               "note": None},
     "rollback": "ADDID 同一身份",
     "persists": "NVRAM（白名单）",
     "note": None},

    {"name": "FRID", "group": "whitelist", "effect": "destructive", "since": "1.3.7",
     "title": "重置白名单", "len_fw": None, "chk_fw": None,
     "params": [{"kind": "raw", "name": "raw", "label": "参数（未定型）",
                 "help": "已知 41 46 52 49 44 ?? 01 5f <计数> …，其余未还原",
                 "default": ""}],
     "reply": {"name": "BFRIDOK", "len": 10, "tpl": "42465249444f4b0a0b52",
               "note": "无应答"},
     "rollback": None,
     "blocked": "会清空整个白名单，无应答、不可撤销；帧尾部未还原。控制台不发送。",
     "persists": "NVRAM（整个白名单）",
     "note": "清空白名单。"},

    {"name": "PAIR", "group": "bind", "effect": "destructive", "since": "1.2.7",
     "title": "绑定", "len_fw": 0x10, "chk_fw": None,
     "params": [{"kind": "const", "name": "hdr", "label": "固定头", "value": "005f",
                 "help": "固定头"},
                {"kind": "id6", "name": "id", "label": "身份",
                 "help": "任意 6 B，之后出现在广播里", "default": ""}],
     "reply": {"name": "BINFO", "len": 43, "tpl": None,
               "note": "身份 6 B、型号 11 B、名称 11 B、版本 5 B；LEN 不含 CHK 和帧尾"},
     "rollback": "UNPAIR 可解绑，但清掉的感应记录回不来",
     "persists": "NVRAM：身份、已绑定标志；感应记录被清空",
     "note": "会清空全部感应记录，先用 CUID 读走。之后广播名加 DE 前缀，厂商数据换成这个身份。"},

    {"name": "UNPAIR", "group": "bind", "effect": "destructive", "since": "1.2.7",
     "title": "解绑", "params": [], "len_fw": 0x0A, "chk_fw": 0x1A,
     "reply": {"name": "BUNPAIRED", "len": 12, "tpl": "42554e5041495245440ca652", "note": None},
     "rollback": "重新 PAIR，需要原来的身份",
     "persists": "NVRAM",
     "note": "回到未绑定的广播。"},

    {"name": "CCUID", "group": "bind", "effect": "destructive", "since": "1.2.7",
     "title": "清空感应记录", "params": [], "len_fw": 0x09, "chk_fw": 0xB2,
     "reply": {"name": "BCCUIDOK", "len": 11, "tpl": "4243435549444f4b0b4752",
               "note": None},
     "rollback": None,
     "persists": "NVRAM（全部感应记录）",
     "note": "清空全部感应记录，不可撤销。"},

    {"name": "WL", "group": "dead", "effect": "read", "since": "1.3.7",
     "title": "WL（空实现）", "params": [], "len_fw": None, "chk_fw": None,
     "reply": None, "rollback": None,
     "no_reply": "无应答（空实现）",
     "blocked": "空实现，请求帧长未还原。",
     "note": "设备收到后什么都不做。"},

    {"name": "BFRD", "group": "dead", "effect": "read", "since": "1.3.7",
     "title": "BFRD（空实现）", "params": [], "len_fw": 0x08, "chk_fw": 0x67,
     "reply": None, "rollback": None,
     "no_reply": "无应答（空实现）",
     "note": "设备收到后什么都不做。"},

    {"name": "GSYN", "group": "read", "effect": "read", "since": "2.1.1",
     "title": "读跟随状态", "params": [], "len_fw": 0x08, "chk_fw": 0x8A,
     "reply": {"name": "BGSYN", "len": 10, "tpl": None, "note": "2 B：开关、组"},
     "note": "开关和组分别由 ASYNC / ASYLT 设置。"},

    {"name": "GSTLTH", "group": "read", "effect": "read", "since": "2.1.1",
     "title": "读 stealth 状态", "params": [], "len_fw": 0x0A, "chk_fw": 0x21,
     "reply": {"name": "BGSTLTH", "len": 11, "tpl": None, "note": "1 B：aa 开，00 关"},
     "note": "由 STLTH 设置。"},

    {"name": "CU3D", "group": "read", "effect": "read", "since": "2.1.1",
     "title": "读感应记录（大容量）", "params": [], "len_fw": 0x08, "chk_fw": 0x58,
     "paged": True,
     "reply": {"name": "(分页推送)", "len": None, "tpl": None,
               "note": "最多 300 条 × 30 B，分页推送"},
     "note": "应答格式未测。"},

    {"name": "ASYNC", "group": "control", "effect": "write", "since": "2.1.1",
     "title": "跟随开关", "len_fw": 0x0A, "chk_fw": None,
     "params": [_u8("on", "开关",
                    "00 关，01 开（分时扫描并跟随匹配的设备）。",
                    [{"v": 0, "t": "0 关"}, {"v": 1, "t": "1 开"}], 0)],
     "reply": {"name": "BASYNC", "len": None, "tpl": None, "note": "未实测"},
     "rollback": "重发 ASYNC 换回（当前值见 GSYN）",
     "note": "应答和副作用未实测。"},

    {"name": "ASYLT", "group": "control", "effect": "write", "since": "2.1.1",
     "title": "设跟随组", "len_fw": 0x0A, "chk_fw": None,
     "params": [_u8("group", "组",
                    "01 / 02 / 03（03 = 常开）。",
                    [{"v": 1, "t": "1"}, {"v": 2, "t": "2"}, {"v": 3, "t": "3（常开）"}], 1)],
     "reply": {"name": "BASYLT", "len": None, "tpl": None, "note": "未实测"},
     "rollback": "重发 ASYLT 换回（当前值见 GSYN）",
     "note": "应答和副作用未实测。"},

    {"name": "STLTH", "group": "control", "effect": "write", "since": "2.1.1",
     "title": "stealth 开关", "len_fw": 0x0A, "chk_fw": None,
     "params": [_u8("on", "开关",
                    "00 关，aa 开。",
                    [{"v": 0x00, "t": "0x00 关"}, {"v": 0xAA, "t": "0xAA 开"}], 0)],
     "reply": {"name": "BSTLTH", "len": None, "tpl": None, "note": "未实测"},
     "rollback": "重发 STLTH 换回（当前值见 GSTLTH）",
     "persists": "NVRAM，断电保持",
     "note": "应答未实测。"},
]

BY_NAME = {c["name"]: c for c in CMDS}

REAL_NAME = {"TIME?": "TIME"}


def _real(name: str) -> str:
    return REAL_NAME.get(name, name)


_FALLBACK_TPL = {c["name"]: (c.get("reply") or {}).get("tpl")
                 for c in CMDS if (c.get("reply") or {}).get("tpl")}


def fw_view(version: str | None) -> dict:
    if not PROFILES_OK:
        return {"version": version, "source": "内置 2.0.x 假定（profiles/ 未装载）",
                "exact": False, "templates": dict(_FALLBACK_TPL),
                "missing": [], "suspect": [], "since": {}, "reported": None}

    prof = _profiles.for_version(version) if version else None
    if prof is None:
        return {"version": version,
                "source": (f"未知版本 {version} —— 按 2.0.x 假定" if version
                           else "未读取固件版本 —— 按 2.0.x 假定（先发 GVER）"),
                "exact": False, "templates": dict(_FALLBACK_TPL),
                "missing": [], "suspect": [], "since": _since_map(), "reported": None}

    tpl = dict(prof.TEMPLATES)
    reported = _cmdset.reported_version(version)
    tpl["GVER"] = build_resp(b"BVER", reported.encode(), chk=_cmdset.BVER_CHK).hex()

    return {
        "version": version, "source": f"profiles/ 档案 {prof.label}（真固件常量表）",
        "exact": True, "templates": tpl,
        "missing": list(_cmdset.missing(version)),
        "suspect": list(_cmdset.suspected_missing(version)),
        "since": _since_map(), "reported": reported,
    }


def _ver_in(ver: str | None, lo: str, hi: str | None) -> bool:
    if not PROFILES_OK:
        return hi is None
    key = _cmdset.vkey(ver) if ver else _cmdset.vkey("2.0.8")
    if key < _cmdset.vkey(lo):
        return False
    return hi is None or key <= _cmdset.vkey(hi)


def _since_map() -> dict:
    if not PROFILES_OK:
        return {}
    out = {}
    for cmd, (first, last) in _cmdset.CMD_SPAN.items():
        out[cmd] = {"since": first, "until": last, "evidence": "hard"}
    for cmd, first in _cmdset.SUSPECTED_SINCE.items():
        out.setdefault(cmd, {"since": first, "until": None, "evidence": "soft"})
    for cmd in _cmdset.BASELINE:
        out.setdefault(cmd, {"since": "1.2.7", "until": None, "evidence": "hard"})
    return out

GROUPS = [
    {"key": "read", "label": "读取", "sub": "不改变设备状态"},
    {"key": "control", "label": "控制", "sub": "有明确回滚手段"},
    {"key": "whitelist", "label": "白名单", "sub": "NVRAM id 8"},
    {"key": "bind", "label": "绑定", "sub": "不可逆"},
    {"key": "dead", "label": "空实现", "sub": "命中即忽略"},
]


def catalog_json(fw: str | None = None):
    view = fw_view(fw)
    since = view["since"]
    out = []
    for c in CMDS:
        e = dict(c)
        real = _real(c["name"])

        tpl = view["templates"].get(real)
        if c["name"] == "TIME?":
            tpl = None
        e["reply"] = dict(c["reply"] or {}, tpl=tpl) if c.get("reply") else None

        e.pop("notes_fw", None)
        cur, other = None, []
        for n in c.get("notes_fw") or []:
            if _ver_in(fw, n["from"], n["to"]):
                cur = n["text"]
            else:
                other.append({"range": f"{n['from']}–{n['to'] or '最新'}", "text": n["text"]})
        e["note_fw"] = cur
        e["notes_other"] = other

        sv = since.get(real)
        if sv:
            e["since"] = sv["since"]
            e["since_evidence"] = sv["evidence"]
        else:
            e["since_evidence"] = "soft" if PROFILES_OK else "unknown"
        e["absent"] = real in view["missing"]
        e["suspect_absent"] = real in view["suspect"]

        if c.get("raw"):
            frame = bytes.fromhex(c["raw"])
            e["preview"] = frame.hex()
            e["chk_calc"] = None
        elif not c["params"]:
            frame = build_frame(c["name"])
            e["preview"] = frame.hex()
            e["chk_calc"] = frame[-2]
        else:
            e["preview"] = None
            e["chk_calc"] = None
        out.append(e)
    known = []
    if PROFILES_OK:
        known = sorted({v for g in _profiles.GENERATIONS
                        for v in getattr(g, "versions", ())}, key=_cmdset.vkey)
    return {"groups": GROUPS, "commands": out,
            "fw": {"version": view["version"], "source": view["source"],
                   "exact": view["exact"], "reported": view["reported"],
                   "missing": view["missing"], "profilesOk": PROFILES_OK,
                   "known": known},
            "mtu": {"token": MTU_TOKEN, "cuid_page": MTU_CUID_PAGE}}


def _ascii_name(data: bytes) -> str:
    i = 0
    while i < len(data) and 0x41 <= data[i] <= 0x5A:
        i += 1
    name = data[:i].decode("ascii", "replace")
    return name if len(name) >= 4 else ""


def _check(r, metric, observed, refs):
    refs = [x for x in refs if x["value"] is not None]
    r["checks"].append({
        "metric": metric, "observed": observed, "refs": refs,
        "within": any(x["value"] == observed for x in refs),
    })


def parse_reply(data: bytes, mtu: int | None = None, paging: bool = False,
                for_cmd: str | None = None, fw: str | None = None) -> dict:
    spec = BY_NAME.get(for_cmd) if for_cmd else None
    reply_spec = (spec or {}).get("reply") or {}
    fw_eff = fw
    if len(data) >= 11 and data[:4] == b"BVER":
        v = data[5:10].rstrip(b"\x00").decode("ascii", "replace").strip()
        if v:
            fw_eff = v

    view = fw_view(fw_eff)
    tpl_hex = None
    if for_cmd and for_cmd != "TIME?":
        tpl_hex = view["templates"].get(_real(for_cmd))
    tpl = bytes.fromhex(tpl_hex) if tpl_hex else None

    r = {
        "hex": data.hex(), "ascii": printable(data), "size": len(data),
        "name": None, "len_field": None, "len_actual": len(data),
        "chk_field": None,
        "checks": [], "fields": [], "flags": [], "template": None,
    }

    if not data:
        return r

    if data == b"RR":
        r["name"] = "(CUID 结束标记)"
        r["fields"].append({"k": "52 52", "v": "分页推送结束 —— 20 页已推完"})
        return r
    if len(data) == 120 or (paging and len(data) % 12 == 0 and len(data) >= 12):
        r["name"] = "(CUID 分页)"
        r["fields"] = _decode_cuid_page(data)
        if len(data) != 120:
            r["flags"].append({"level": "warn",
                               "text": f"分块只有 {len(data)} B —— 正常应为 120 B。"
                                       f"MTU {mtu or '?'}，需要 ≥ {MTU_CUID_PAGE}。"
                                       "这不是「表里没数据」，是帧按 MTU 被截断了。"})
        return r

    if for_cmd == "TIME?" or (len(data) == 8 and data[0] == 0x42 and data[-1] == RESP_EOF
                              and not _ascii_name(data)):
        r["name"] = "(读时间应答·无命令名)"
        if len(data) >= 8:
            yy, mo, dd, hh, mm, ss = data[1:7]
            r["fields"].append({"k": "设备 RTC",
                                "v": f"20{yy:02d}-{mo:02d}-{dd:02d} "
                                     f"{hh:02d}:{mm:02d}:{ss:02d} UTC", "mono": True})
        r["flags"].append({"level": "info",
                           "text": "该应答既无命令名也无 LEN/CHK（固件如此），无从校验"})
        return r

    if data[-1] != RESP_EOF:
        r["flags"].append({"level": "warn",
                           "text": f"帧尾不是 0x52 'R'，实际 0x{data[-1]:02x}"})

    name = _ascii_name(data)
    r["name"] = name or "(未识别)"

    if name == "BINFO":
        _decode_binfo(data, r)
    elif name == "BTOKEN":
        _decode_btoken(data, r, mtu)
    elif name in ("BSPARM", "BRADAR"):
        r["chk_field"] = data[-2]
        r["flags"].append({"level": "info", "text": "该应答没有 LEN 字段（固件如此）"})
        _check(r, "CHK", data[-2],
               [{"label": "公式 sum&0xFF", "value": sum(data[:-2]) & 0xFF}])
    elif name and len(data) >= len(name) + 3:
        r["len_field"] = data[len(name)]
        r["chk_field"] = data[-2]
        params = data[len(name) + 1:-2]
        _decode_params(name, params, r)
        _check(r, "LEN", r["len_field"], [
            {"label": "整帧总长", "value": r["len_actual"]},
            {"label": "固件模板", "value": tpl[len(name)] if tpl and len(tpl) > len(name) else None},
        ])
        _check(r, "CHK", r["chk_field"], [
            {"label": "公式 sum&0xFF", "value": sum(data[:-2]) & 0xFF},
            {"label": "固件模板", "value": tpl[-2] if tpl else None},
        ])

    if tpl is not None:
        r["template"] = {"hex": tpl.hex(), "match": data == tpl,
                         "name": reply_spec["name"], "exact": view["exact"],
                         "source": view["source"]}
        if not view["exact"]:
            r["flags"].append({
                "level": "info",
                "text": f"{view['source']} —— 模板比对只作参考，「不一致」不作数。"})
        elif not r["template"]["match"] and len(data) == len(tpl):
            diff = [i for i in range(len(tpl)) if tpl[i] != data[i]]
            runtime = (r.get("name") == "BVBAT" and _ver_in(view.get("version"), "2.0.0", None)
                       and set(diff) <= {6, 7, 8, 9})
            r["flags"].append({
                "level": "info" if runtime else "warn",
                "text": ("2.0.x 的 BVBAT 是运行时拼帧，参数位/CHK 与常量表不同属正常"
                         f"（差异在 {', '.join(f'0x{i:02x}' for i in diff)}）"
                         if runtime else
                         "与固件模板常量表不一致，差异在偏移 "
                         + ", ".join(f"0x{i:02x}" for i in diff[:8]))})
    return r


def _decode_params(name: str, params: bytes, r: dict):
    if not params:
        return
    if name == "BVER":
        r["fields"].append({"k": "固件版本",
                            "v": params.rstrip(b"\x00").decode("ascii", "replace")})
    elif name == "BVBAT":
        r["fields"].append({"k": "参数原始字节", "v": hexs(params), "mono": True})
        if len(params) >= 1:
            r["fields"].append({"k": "电量",
                                "v": f"{params[0]}（0=充电中 1=满 … 6=低电）"})
        if len(params) >= 2:
            r["fields"].append({"k": "提醒音（TORLE）", "v": f"{params[1]}"})
        if len(params) >= 3:
            r["fields"].append({"k": "雷达", "v": f"{params[2]}（1 = 在感应）"})
    elif name == "BGBRGT":
        lv = {0x1E: 0, 0x3C: 1, 0x5A: 2}.get(params[0])
        r["fields"].append({
            "k": "亮度",
            "v": (f"{params[0]} → 等级 {lv}（BRGT 的参数值，30/60/90 ↔ 0/1/2）"
                  if lv is not None else
                  f"{params[0]} —— ⚠ 不是 30/60/90 中的任何一个，超出已知映射")})
    elif name == "BGPARM":
        r["fields"].append({"k": "定向雷达参数", "v": hexs(params), "mono": True})
    elif name == "BRCUID":
        r["fields"].append({"k": "参数", "v": hexs(params), "mono": True})
        r["fields"].append({"k": "接下来", "v": "100 ms 周期推 20 页 × 120 B，末尾 52 52"})
    else:
        r["fields"].append({"k": "参数", "v": hexs(params), "mono": True})


def _decode_btoken(data: bytes, r: dict, mtu):
    r["len_field"] = data[6] if len(data) > 6 else None
    r["chk_field"] = data[-2]
    tok = data[7:-2]
    r["fields"].append({"k": "token", "v": tok.hex(), "mono": True, "wrap": True})
    r["fields"].append({"k": "长度", "v": f"{len(tok)} B（应为 44 B）"})
    if len(tok) >= 16:
        h = tok[:16].hex()
        r["fields"].append({"k": "genDeviceId",
                            "v": f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}",
                            "mono": True})
        r["fields"].append({"k": "未使用", "v": f"后 {len(tok) - 16} B —— "
                                                "genDeviceId 上界硬编码 0x10，App 完全没用"})
    else:
        r["flags"].append({"level": "error",
                           "text": f"token 只有 {len(tok)} B —— 被 MTU 截断。"
                                   f"MTU {mtu or '?'}，需要 ≥ {MTU_TOKEN}"})
    _check(r, "LEN", r["len_field"], [{"label": "整帧总长", "value": r["len_actual"]}])
    _check(r, "CHK", r["chk_field"],
           [{"label": "公式 sum&0xFF", "value": sum(data[:-2]) & 0xFF}])


def _decode_binfo(data: bytes, r: dict):
    r["len_field"] = data[5] if len(data) > 5 else None
    r["chk_field"] = data[-2]
    if len(data) >= 43:
        r["fields"] += [
            {"k": "身份", "v": hexs(data[8:14]), "mono": True},
            {"k": "型号", "v": data[14:25].decode("ascii", "replace").strip()},
            {"k": "名称", "v": data[25:36].decode("ascii", "replace").strip()},
            {"k": "版本", "v": data[36:41].decode("ascii", "replace").strip()},
        ]
    _check(r, "LEN", r["len_field"], [
        {"label": "整帧长 − 2（BINFO 特例）", "value": r["len_actual"] - 2},
    ])
    _check(r, "CHK", r["chk_field"],
           [{"label": "公式 sum&0xFF", "value": sum(data[:-2]) & 0xFF}])


def _decode_cuid_page(data: bytes):
    out = []
    for i in range(0, len(data) - 11, 12):
        rec = data[i:i + 12]
        if not any(rec):
            continue
        yy, mo, dd, hh, mm = rec[6:11]
        near = rec[11]
        out.append({
            "k": hexs(rec[0:6]),
            "v": f"20{yy:02d}-{mo:02d}-{dd:02d} {hh:02d}:{mm:02d} UTC · "
                 f"{'碰一碰' if near == 1 else '路过'}",
            "mono": True,
        })
    if not out:
        out.append({"k": "—", "v": "本页全零（表未满，正常）"})
    return out
