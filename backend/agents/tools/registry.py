"""工具注册器（C4）：新增工具 = 在 agents/tools/ 下新建一个模块，其余全自动。

旧世界加一个工具要同步改 4 处（工具文件、neyria 的 import、tools_map、tools_schema），
漏一处就是"模型看得见但执行不了"或反过来。现在：

- 自动发现本包下所有模块里的 langchain BaseTool 实例（@tool 装饰的函数）；
- tools_map：名字 → 工具对象（执行入口，参数由工具自身的 pydantic args_schema 校验）；
- tools_schema：由工具对象一键转换成 OpenAI function-calling 格式（喂给模型）。

名称、描述、参数 schema、执行函数由同一个对象提供，单一事实来源。
"""

import importlib
import pkgutil

from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool


def _discover_tools() -> tuple[dict[str, BaseTool], dict[str, str]]:
    import agents.tools as tools_pkg

    registry: dict[str, BaseTool] = {}
    capability_registry: dict[str, str] = {}
    for mod_info in pkgutil.iter_modules(tools_pkg.__path__):
        if mod_info.name.startswith("_") or mod_info.name == "registry":
            continue
        module = importlib.import_module(f"agents.tools.{mod_info.name}")
        for obj in vars(module).values():
            if not isinstance(obj, BaseTool):
                continue
            existing = registry.get(obj.name)
            if existing is not None and existing is not obj:
                # 启动即失败：重名工具是配置错误，跑起来再暴露只会更难查
                raise RuntimeError(f"工具重名冲突: {obj.name}（{mod_info.name} 与既有注册冲突）")
            registry[obj.name] = obj
            capability_id = getattr(module, "CAPABILITY_ID", None)
            if capability_id:
                capability_registry[obj.name] = capability_id
    return registry, capability_registry


tools_map, capability_map = _discover_tools()
tools_schema: list[dict] = [convert_to_openai_tool(t) for t in tools_map.values()]
