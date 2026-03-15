import importlib
import pkgutil
import tools


def load_tools():

    tool_map = {}

    for module in pkgutil.iter_modules(tools.__path__):

        try:
            mod = importlib.import_module(f"tools.{module.name}.tool")
        except ModuleNotFoundError:
            continue

        tool = mod.Tab
        tool_map[tool.TOOL_NAME] = tool

    return dict(
        sorted(tool_map.items(), key=lambda x: x[1].TOOL_ORDER)
    )