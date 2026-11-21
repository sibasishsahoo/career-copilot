"""Tools: what the agent is allowed to do.

A tool is a name, a description the model can read, a list of parameters, and a Python function.
This file is the safety layer between the model and your code. The model only ever produces TEXT
(a tool name and some arguments). Before anything runs we check that:
  * the tool exists (only tools in the registry can be called),
  * the arguments have exactly the right names and types,
  * and whatever goes wrong, the loop survives: errors become text the model can read and react to.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MAX_OBSERVATION_CHARS = 4000  # a tool result longer than this is cut, to keep prompts small


class ToolError(Exception):
    """A failure the tool expects can happen (e.g. 'Application 9 was not found').
    The message is shown to the model, so write it for the model to read."""


class ToolArgumentError(Exception):
    """The model passed arguments that do not fit the tool's parameters."""


@dataclass(frozen=True)
class ToolParam:
    name: str
    type: str  # "string", "integer" or "boolean"
    description: str
    required: bool = True
    default: Any = None  # filled in when an optional argument is missing
    enum: tuple[str, ...] | None = None  # for strings: the only allowed values
    minimum: int | None = None
    maximum: int | None = None
    max_length: int | None = None


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    params: tuple[ToolParam, ...]
    run: Callable[[dict[str, Any]], Any]  # receives VALIDATED arguments, returns JSON-friendly data


@dataclass(frozen=True)
class ToolOutcome:
    observation: str
    ok: bool


# --------------------------------------------------------------------------------------------
# Argument validation
# --------------------------------------------------------------------------------------------

def _coerce(param: ToolParam, value: Any) -> Any:
    """Check one value against its parameter and return the cleaned value (or raise ValueError)."""
    if param.type == "string":
        if not isinstance(value, str):
            raise ValueError("must be a string")
        text = value.strip()
        if param.enum is not None:
            matches = [option for option in param.enum if option.lower() == text.lower()]
            if not matches:
                raise ValueError(f"must be one of: {', '.join(param.enum)}")
            return matches[0]
        if param.required and not text:
            raise ValueError("must not be empty")
        if param.max_length is not None and len(text) > param.max_length:
            raise ValueError(f"must be at most {param.max_length} characters")
        return text

    if param.type == "integer":
        number: int
        if isinstance(value, bool):
            raise ValueError("must be an integer")
        if isinstance(value, int):
            number = value
        elif isinstance(value, float) and value.is_integer():
            number = int(value)
        elif isinstance(value, str) and value.strip().lstrip("-").isdigit():
            number = int(value.strip())  # models often write numbers as strings
        else:
            raise ValueError("must be an integer")
        if param.minimum is not None and number < param.minimum:
            raise ValueError(f"must be at least {param.minimum}")
        if param.maximum is not None and number > param.maximum:
            raise ValueError(f"must be at most {param.maximum}")
        return number

    if param.type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return value.strip().lower() == "true"
        raise ValueError("must be true or false")

    raise ValueError(f"unsupported parameter type {param.type!r}")  # a bug in the tool definition


def validate_arguments(params: tuple[ToolParam, ...], raw: Any) -> dict[str, Any]:
    """Return clean arguments (with defaults filled in) or raise ToolArgumentError listing EVERY problem."""
    if not isinstance(raw, dict):
        raise ToolArgumentError("arguments must be a JSON object, like {\"name\": value}")

    known = {param.name for param in params}
    problems = [
        f"unknown argument '{name}' (allowed: {', '.join(sorted(known)) or 'none'})"
        for name in raw
        if name not in known
    ]

    clean: dict[str, Any] = {}
    for param in params:
        value = raw.get(param.name)
        if value is None:  # missing, or explicitly null
            if param.required:
                problems.append(f"missing required argument '{param.name}'")
            elif param.default is not None:
                clean[param.name] = param.default
            continue
        try:
            clean[param.name] = _coerce(param, value)
        except ValueError as exc:
            problems.append(f"'{param.name}' {exc}")

    if problems:
        raise ToolArgumentError("; ".join(problems))
    return clean


# --------------------------------------------------------------------------------------------
# The registry: the complete list of things the agent may do
# --------------------------------------------------------------------------------------------

def signature(tool: Tool) -> str:
    """'search_knowledge(query: string, k?: integer)' - '?' marks an optional parameter."""
    parts = [f"{param.name}{'' if param.required else '?'}: {param.type}" for param in tool.params]
    return f"{tool.name}({', '.join(parts)})"


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        names = [tool.name for tool in tools]
        if len(set(names)) != len(names):
            raise ValueError("Tool names must be unique.")
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def describe(self) -> str:
        """The text that tells the model which tools exist and how to call them."""
        blocks = []
        for tool in self._tools.values():
            lines = [f"- {signature(tool)}", f"    {tool.description}"]
            for param in tool.params:
                details = [param.type, "required" if param.required else "optional"]
                if param.enum:
                    details.append("one of: " + ", ".join(param.enum))
                if param.minimum is not None or param.maximum is not None:
                    details.append(f"range {param.minimum if param.minimum is not None else '-'} to "
                                   f"{param.maximum if param.maximum is not None else '-'}")
                if param.default is not None:
                    details.append(f"default {param.default}")
                lines.append(f"    * {param.name} ({', '.join(details)}): {param.description}")
            blocks.append("\n".join(lines))
        return "\n".join(blocks)


def _to_text(result: Any) -> str:
    text = json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text) > MAX_OBSERVATION_CHARS:
        text = text[:MAX_OBSERVATION_CHARS] + "... [truncated: the result was too long]"
    return text


def execute_tool(registry: ToolRegistry, name: str, arguments: Any) -> ToolOutcome:
    """Run one tool call safely. NEVER raises: every failure becomes an Observation for the model."""
    tool = registry.get(name)
    if tool is None:
        available = ", ".join(registry.names)
        return ToolOutcome(f"Error: there is no tool named '{name}'. Available tools: {available}.", False)

    try:
        clean = validate_arguments(tool.params, arguments)
    except ToolArgumentError as exc:
        return ToolOutcome(f"Error: invalid arguments for {tool.name}: {exc}. Usage: {signature(tool)}", False)

    try:
        return ToolOutcome(_to_text(tool.run(clean)), True)
    except ToolError as exc:
        return ToolOutcome(f"Error: {exc}", False)
    except Exception:
        # A bug or an infrastructure problem. Log the details for the developer, but show the
        # model only a generic message (internal error text could leak paths or secrets).
        logger.exception("Tool %s crashed", tool.name)
        return ToolOutcome(f"Error: the tool {tool.name} failed unexpectedly. Try another approach.", False)
