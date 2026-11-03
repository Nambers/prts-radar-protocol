
class BaseFirmware:
    label = "generic"
    note = "纯反编译推断，不含任何版本特有怪癖"
    measured = False
    versions = ()

    MEASURED_CMDS = ()

    modeled_version = None

    default_version = "1.0.0"

    TEMPLATES = {}
