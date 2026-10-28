import pytest

from agent_core import TOOL_SCHEMAS, calculate, execute_tool, get_current_time


def test_calculator_basic_arithmetic():
    assert calculate("(1250 * 3) + 99") == 3849
    assert calculate("sqrt(81) + pi") == pytest.approx(12.141592653589793)


def test_calculator_rejects_code_execution():
    with pytest.raises(ValueError):
        calculate("__import__('os').system('echo unsafe')")


def test_calculator_rejects_huge_exponent():
    with pytest.raises(ValueError):
        calculate("2 ** 1000")


def test_only_registered_tools_are_executable():
    assert execute_tool("made_up_tool", {})["error"].startswith("Tool not allowed")
    assert {item["function"]["name"] for item in TOOL_SCHEMAS} == {
        "web_search", "github_search", "calculator", "get_current_time"
    }


def test_time_is_makassar_timezone():
    result = get_current_time()
    assert result.endswith("+08:00")
