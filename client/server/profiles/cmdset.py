BASELINE = ("GETTOKEN", "PAIR", "UNPAIR", "GVER", "GVBAT", "TIME",
            "PLS", "PLL", "STS", "STL", "CUID", "WL")

CMD_SPAN = {
    "CCUID":  ("1.2.8", None),
    "CSIUID": ("1.3.0", "1.3.1"),
    "ADDID":  ("1.3.7", "2.0.8"),
    "DELID":  ("1.3.7", "2.0.8"),
    "FRID":   ("1.2.7", "2.0.8"),
    "BFRD":   ("1.3.7", "2.0.8"),
    "TORLE":  ("1.4.9", None),
    "PTEST":  ("1.5.5", None),
    "ASYNC":  ("2.1.1", None),
    "ASYLT":  ("2.1.1", None),
    "GSYN":   ("2.1.1", None),
    "STLTH":  ("2.1.1", None),
    "GSTLTH": ("2.1.1", None),
    "CU3D":   ("2.1.1", None),
}

SUSPECTED_SINCE = {
    "RADAR":  "1.9.5",
    "SPARM":  "2.0.0",
    "GSPARM": "2.0.0",
    "BRGT":   "2.0.0",
    "GBRGT":  "2.0.0",
}

VER_STRING_QUIRK = {"2.0.5": "2.0.4"}

BVER_CHK = 0x00


def vkey(ver):
    try:
        m, n, p = (int(x) for x in ver.split("."))
    except (ValueError, AttributeError):
        return None
    return m * 100 + n * 10 + p


def supports(cmd, ver, strict=False):
    k = vkey(ver)
    if k is None:
        return True
    span = CMD_SPAN.get(cmd)
    if span is None:
        if strict and cmd in SUSPECTED_SINCE:
            return k >= vkey(SUSPECTED_SINCE[cmd])
        return True
    since, until = span
    if k < vkey(since):
        return False
    return until is None or k <= vkey(until)


def reported_version(ver):
    return VER_STRING_QUIRK.get(ver, ver)


def missing(ver):
    return sorted(c for c in CMD_SPAN if not supports(c, ver))


def suspected_missing(ver):
    k = vkey(ver)
    if k is None:
        return []
    return sorted(c for c, since in SUSPECTED_SINCE.items() if k < vkey(since))


def groups_within(versions):
    out = []
    for v in versions:
        k = tuple(missing(v))
        if out and out[-1][1] == k:
            out[-1][0].append(v)
        else:
            out.append(([v], k))
    return [(vs, list(k)) for vs, k in out]
