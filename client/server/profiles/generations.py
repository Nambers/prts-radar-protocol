from . import cmdset
from .base import BaseFirmware

_COMMON = {
    "PLS":    "42504c534f4b09d352",
    "STS":    "425354534f4b09df52",
    "PLL":    "42504c4c4f4b09cd52",
    "STL":    "4253544c4f4b09d852",
    "FRID":   "42465249444f4b0a0b52",
    "TIME":   "425254494d454f4b0b6852",
    "UNPAIR": "42554e5041495245440ca652",
}
_CCUID = {"CCUID": "4243435549444f4b0b4752"}
_CSIUID = {"CSIUID": "424353495549444f4b0c8d52"}
_IDMGMT = {
    "ADDID": "4241444449444f4b0b3552",
    "DELID": "4244454c49444f4b0b4152",
}
_TORLE = {"TORLE": "42544f524c454f4b0b2152"}

_VBAT_1B = {"GVBAT": "425642415408017752"}
_VBAT_2B = {"GVBAT": "42564241540801007752"}
_VBAT_3B = {"GVBAT": "4256424154080100007752"}
_VBAT_FIX = {"GVBAT": "42564241540b0100000052"}


class Gen1(BaseFirmware):
    label = "gen1"
    note = "1.2.7（基线 8 条命令）"
    measured = True
    versions = ("1.2.7",)
    default_version = "1.2.7"
    TEMPLATES = dict(_COMMON, **_VBAT_1B)


class Gen2(Gen1):
    label = "gen2"
    note = "1.2.8–1.2.9（+CCUID）"
    versions = ("1.2.8", "1.2.9")
    default_version = "1.2.9"
    TEMPLATES = dict(Gen1.TEMPLATES, **_CCUID)


class Gen3(Gen2):
    label = "gen3"
    note = "1.3.0–1.3.1（+CSIUID，昙花一现）"
    versions = ("1.3.0", "1.3.1")
    default_version = "1.3.1"
    TEMPLATES = dict(Gen2.TEMPLATES, **_CSIUID)


class Gen4(Gen3):
    label = "gen4"
    note = "1.3.7–1.4.8（-CSIUID +ADDID +DELID）"
    versions = ("1.3.7", "1.3.8", "1.4.4", "1.4.5", "1.4.8")
    default_version = "1.4.8"
    TEMPLATES = {k: v for k, v in dict(Gen3.TEMPLATES, **_IDMGMT).items()
                 if k != "CSIUID"}


class Gen5(Gen4):
    label = "gen5"
    note = "1.4.9–1.6.5（+TORLE，GVBAT params 2B）"
    versions = ("1.4.9", "1.5.0", "1.5.5", "1.5.6", "1.5.8", "1.6.0", "1.6.3", "1.6.5")
    default_version = "1.6.5"
    TEMPLATES = dict(Gen4.TEMPLATES, **_TORLE, **_VBAT_2B)


class Gen6(Gen5):
    label = "gen6"
    note = "1.7.0–1.9.8（GVBAT params 3B，LEN 仍错）— **部分实物验证**"

    MEASURED_CMDS = ("GETTOKEN", "GVER", "GVBAT", "TIME", "PAIR")
    versions = ("1.7.0", "1.7.3", "1.7.6", "1.8.5", "1.9.5", "1.9.8")
    default_version = "1.9.8"
    TEMPLATES = dict(Gen5.TEMPLATES, **_VBAT_3B)


class Gen7(Gen6):
    label = "gen7"
    note = "2.0.0–2.0.8（GVBAT LEN 修正 + 改成运行时拼帧）— **部分实物验证**"

    MEASURED_CMDS = ("GVER", "GVBAT", "GBRGT", "PTEST", "TORLE", "RADAR")
    versions = ("2.0.0", "2.0.1", "2.0.3", "2.0.4", "2.0.5", "2.0.6", "2.0.8")
    default_version = "2.0.8"
    TEMPLATES = dict(Gen6.TEMPLATES, **_VBAT_FIX)


class Gen8(Gen7):
    label = "gen8"
    note = ("2.1.1（跟随/同步子系统：删 ADDID/DELID/FRID/BFRD，"
            "增 ASYNC/ASYLT/GSYN/STLTH/GSTLTH/CU3D）— 真机 GVER/GVBAT 实测")

    MEASURED_CMDS = ("GVER", "GVBAT", "GSYN", "GSTLTH")
    versions = ("2.1.1",)
    default_version = "2.1.1"

    TEMPLATES = {k: v for k, v in Gen7.TEMPLATES.items()
                 if k not in ("FRID", "ADDID", "DELID")}


GENERATIONS = (Gen1, Gen2, Gen3, Gen4, Gen5, Gen6, Gen7, Gen8)

for _g in GENERATIONS:
    _g.modeled_version = _g.default_version

_PINNED = {}


def _pin(gen, ver):
    key = (gen.__name__, ver)
    if key not in _PINNED:
        _PINNED[key] = type(
            f"{gen.__name__}_{ver.replace('.', '')}", (gen,),
            {
                "__doc__": f"固件 {ver}（模板同 {gen.label}，命令集/BVER 按本版）。",
                "label": ver,
                "note": f"{ver}（模板 {gen.label}，命令集与 BVER 按本版）",
                "versions": (ver,),
                "modeled_version": ver,
                "default_version": cmdset.reported_version(ver),
            })
    return _PINNED[key]


def for_version(ver):
    for g in GENERATIONS:
        if ver in g.versions:
            return _pin(g, ver)
    return None
