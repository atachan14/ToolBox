from tools import TOOLS

def load_tools():

    tool_map = {t.TOOL_NAME: t for t in TOOLS}

    return dict(
        sorted(tool_map.items(), key=lambda x: x[1].TOOL_ORDER)
    )