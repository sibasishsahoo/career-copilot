import json

import pytest

from app.services.agent.tools import (
    MAX_OBSERVATION_CHARS,
    Tool,
    ToolArgumentError,
    ToolError,
    ToolParam,
    ToolRegistry,
    execute_tool,
    signature,
    validate_arguments,
)

QUERY = ToolParam("query", "string", "what to look for", max_length=20)
K = ToolParam("k", "integer", "how many", required=False, default=3, minimum=1, maximum=5)
STATUS = ToolParam("status", "string", "a status", required=False, enum=("wishlist", "applied", "offer"))
FLAG = ToolParam("flag", "boolean", "a switch", required=False)
PARAMS = (QUERY, K, STATUS, FLAG)


def problems(raw) -> str:
    with pytest.raises(ToolArgumentError) as excinfo:
        validate_arguments(PARAMS, raw)
    return str(excinfo.value)


# ======================= validate_arguments =======================

def test_valid_arguments_are_returned_with_defaults_filled_in():
    assert validate_arguments(PARAMS, {"query": "deploy"}) == {"query": "deploy", "k": 3}


def test_optional_parameters_without_a_default_are_left_out():
    clean = validate_arguments(PARAMS, {"query": "x"})
    assert "status" not in clean and "flag" not in clean


def test_strings_are_trimmed():
    assert validate_arguments(PARAMS, {"query": "  deploy  "})["query"] == "deploy"


def test_a_missing_required_argument_is_reported():
    assert "missing required argument 'query'" in problems({})


def test_null_counts_as_missing():
    assert "missing required argument 'query'" in problems({"query": None})
    assert validate_arguments(PARAMS, {"query": "x", "k": None})["k"] == 3  # optional null -> default


def test_unknown_arguments_are_rejected_and_the_allowed_ones_listed():
    message = problems({"query": "x", "limit": 5})
    assert "unknown argument 'limit'" in message
    assert "allowed: flag, k, query, status" in message


def test_every_problem_is_reported_at_once():
    message = problems({"k": 99, "color": "red"})
    assert "missing required argument 'query'" in message
    assert "'k' must be at most 5" in message
    assert "unknown argument 'color'" in message


def test_arguments_must_be_a_json_object():
    for not_an_object in ["query", ["query"], 5, None]:
        assert "must be a JSON object" in problems(not_an_object)


def test_a_string_parameter_rejects_other_types_and_empty_text():
    assert "'query' must be a string" in problems({"query": 42})
    assert "'query' must not be empty" in problems({"query": "   "})


def test_string_length_is_limited():
    assert "'query' must be at most 20 characters" in problems({"query": "x" * 21})
    assert validate_arguments(PARAMS, {"query": "x" * 20})["query"] == "x" * 20


def test_enum_values_are_matched_ignoring_case_and_returned_in_canonical_form():
    assert validate_arguments(PARAMS, {"query": "x", "status": "Applied"})["status"] == "applied"
    assert validate_arguments(PARAMS, {"query": "x", "status": " OFFER "})["status"] == "offer"


def test_an_unknown_enum_value_lists_the_choices():
    assert "'status' must be one of: wishlist, applied, offer" in problems({"query": "x", "status": "ghosted"})


def test_integers_accept_numeric_strings_and_whole_floats():
    assert validate_arguments(PARAMS, {"query": "x", "k": "4"})["k"] == 4
    assert validate_arguments(PARAMS, {"query": "x", "k": 4.0})["k"] == 4
    assert validate_arguments(PARAMS, {"query": "x", "k": " 2 "})["k"] == 2


def test_integers_reject_everything_else():
    for bad in [2.5, "two", True, [], "3.5"]:
        assert "'k' must be an integer" in problems({"query": "x", "k": bad})


def test_integer_range_is_enforced():
    assert "'k' must be at least 1" in problems({"query": "x", "k": 0})
    assert "'k' must be at most 5" in problems({"query": "x", "k": 6})
    assert validate_arguments(PARAMS, {"query": "x", "k": 5})["k"] == 5


def test_booleans_accept_true_false_and_their_string_forms():
    assert validate_arguments(PARAMS, {"query": "x", "flag": True})["flag"] is True
    assert validate_arguments(PARAMS, {"query": "x", "flag": "False"})["flag"] is False
    assert "'flag' must be true or false" in problems({"query": "x", "flag": "yes"})
    assert "'flag' must be true or false" in problems({"query": "x", "flag": 1})


# ======================= signature, registry =======================

def make_tool(name="echo", params=(QUERY,), run=lambda args: {"echo": args}) -> Tool:
    return Tool(name=name, description="Echoes its input.", params=params, run=run)


def test_signature_marks_optional_parameters():
    assert signature(make_tool("search", (QUERY, K))) == "search(query: string, k?: integer)"
    assert signature(make_tool("nothing", ())) == "nothing()"


def test_registry_looks_tools_up_by_name():
    registry = ToolRegistry([make_tool("a"), make_tool("b")])
    assert registry.get("a").name == "a"
    assert registry.get("zzz") is None
    assert registry.names == ["a", "b"]


def test_registry_rejects_duplicate_names():
    with pytest.raises(ValueError, match="unique"):
        ToolRegistry([make_tool("a"), make_tool("a")])


def test_describe_lists_every_tool_with_its_parameters():
    text = ToolRegistry([make_tool("search", (QUERY, K, STATUS))]).describe()
    assert "- search(query: string, k?: integer, status?: string)" in text
    assert "Echoes its input." in text
    assert "* query (string, required): what to look for" in text
    assert "default 3" in text and "range 1 to 5" in text
    assert "one of: wishlist, applied, offer" in text


# ======================= execute_tool =======================

def test_a_successful_call_returns_compact_json():
    registry = ToolRegistry([make_tool()])
    outcome = execute_tool(registry, "echo", {"query": " hi "})
    assert outcome.ok is True
    assert outcome.observation == '{"echo":{"query":"hi"}}'


def test_the_tool_receives_validated_arguments_not_raw_ones():
    seen = {}

    def run(args):
        seen.update(args)
        return {}

    execute_tool(ToolRegistry([make_tool("t", (QUERY, K), run)]), "t", {"query": "x", "k": "4"})
    assert seen == {"query": "x", "k": 4}


def test_non_ascii_text_is_kept_readable():
    registry = ToolRegistry([make_tool(run=lambda args: {"text": "café – résumé"})])
    assert "café – résumé" in execute_tool(registry, "echo", {"query": "x"}).observation


def test_an_unknown_tool_lists_the_available_ones():
    outcome = execute_tool(ToolRegistry([make_tool("a"), make_tool("b")]), "delete_everything", {})
    assert outcome.ok is False
    assert "no tool named 'delete_everything'" in outcome.observation
    assert "Available tools: a, b" in outcome.observation


def test_invalid_arguments_become_an_observation_with_the_usage():
    outcome = execute_tool(ToolRegistry([make_tool("search", (QUERY, K))]), "search", {"k": 99})
    assert outcome.ok is False
    assert "invalid arguments for search" in outcome.observation
    assert "missing required argument 'query'" in outcome.observation
    assert "Usage: search(query: string, k?: integer)" in outcome.observation


def test_the_tool_function_is_not_called_when_arguments_are_invalid():
    calls = []
    registry = ToolRegistry([make_tool(run=lambda args: calls.append(args))])
    execute_tool(registry, "echo", {})
    assert calls == []


def test_a_tool_error_message_is_shown_to_the_model():
    def run(args):
        raise ToolError("Application 9 was not found.")

    outcome = execute_tool(ToolRegistry([make_tool(run=run)]), "echo", {"query": "x"})
    assert outcome == type(outcome)("Error: Application 9 was not found.", False)


def test_an_unexpected_crash_is_hidden_from_the_model_but_does_not_stop_the_agent():
    def run(args):
        raise RuntimeError("secret path /etc/passwd and API key abc123")

    outcome = execute_tool(ToolRegistry([make_tool(run=run)]), "echo", {"query": "x"})
    assert outcome.ok is False
    assert "failed unexpectedly" in outcome.observation
    assert "abc123" not in outcome.observation and "/etc/passwd" not in outcome.observation


def test_a_very_long_result_is_cut():
    registry = ToolRegistry([make_tool(run=lambda args: {"text": "x" * 10_000})])
    observation = execute_tool(registry, "echo", {"query": "x"}).observation
    assert len(observation) < MAX_OBSERVATION_CHARS + 100
    assert observation.endswith("[truncated: the result was too long]")


def test_results_that_are_not_plain_json_types_are_still_handled():
    from datetime import datetime, timezone

    moment = datetime(2026, 10, 1, tzinfo=timezone.utc)
    registry = ToolRegistry([make_tool(run=lambda args: {"when": moment})])
    outcome = execute_tool(registry, "echo", {"query": "x"})
    assert outcome.ok is True and "2026-10-01" in outcome.observation
    assert json.loads(outcome.observation)["when"].startswith("2026-10-01")
