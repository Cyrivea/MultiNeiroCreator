"""工具注册器的单元测试（C4）。

合同：agents/tools/ 下每个 @tool 函数自动进 tools_map，并自动生成 OpenAI
function-calling 格式的 tools_schema——名称/描述/参数/执行函数单一事实来源。
"""

from agents.tools import registry


def test_all_tools_discovered():
    assert set(registry.tools_map) == {
        "calculate",
        "get_current_time",
        "search_web",
        "generate_lyrics_block",
        "configure_lyrics_workflow",
        "configure_image_workflow",
        "clear_workflow_draft",
        "read_workflow_state",
        "run_current_workflow",
    }
    assert registry.capability_map == {
        "generate_lyrics_block": "lyrics.generate",
        "configure_lyrics_workflow": "workflow.control",
        "configure_image_workflow": "workflow.control",
        "clear_workflow_draft": "workflow.control",
        "read_workflow_state": "workflow.control",
        "run_current_workflow": "workflow.control",
    }


def test_schema_matches_map():
    schema_names = {item["function"]["name"] for item in registry.tools_schema}
    assert schema_names == set(registry.tools_map)


def test_schema_shape_is_openai_function_calling():
    for item in registry.tools_schema:
        assert item["type"] == "function"
        func = item["function"]
        assert func["name"]
        assert func["description"]  # 描述来自 docstring，空描述=模型不知道何时调用
        assert func["parameters"]["type"] == "object"


def test_search_web_query_param_has_description():
    """parse_docstring=True 应把 Args 段落变成参数描述。"""
    schema = next(
        item for item in registry.tools_schema if item["function"]["name"] == "search_web"
    )
    assert schema["function"]["parameters"]["properties"]["query"].get("description")


def test_tools_are_invocable_with_validated_args():
    """注册对象即执行入口：invoke 走 pydantic args_schema 校验。"""
    result = registry.tools_map["calculate"].invoke({"expression": "2+3"})
    assert "5" in str(result)
