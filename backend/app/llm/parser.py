import json
import re

from json_repair import repair_json
from pydantic import BaseModel


class InvalidJSONResponse(ValueError):
    """The provider response cannot be converted into a JSON object."""


def _first_json_object(content: str) -> str:
    """Extract the first balanced JSON object, ignoring prose and code fences."""
    start = content.find("{")
    if start < 0:
        raise ValueError("LLM response does not contain a JSON object")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(content)):
        character = content[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1]
    raise ValueError("LLM response contains an incomplete JSON object")


def parse_json(content: str) -> dict:
    if not content or not content.strip():
        raise InvalidJSONResponse("LLM response is empty")
    clean = re.sub(
        r"^\s*```(?:json)?\s*|\s*```\s*$", "", content.strip(), flags=re.I
    ).strip()
    try:
        value = json.loads(clean)
    except json.JSONDecodeError:
        try:
            value = json.loads(_first_json_object(clean))
        except (json.JSONDecodeError, ValueError):
            value = repair_json(clean, return_objects=True)
    if not isinstance(value, dict):
        raise InvalidJSONResponse("LLM response is not a valid JSON object")
    return value


def parse_model(content: str, model: type[BaseModel]) -> BaseModel:
    return model.model_validate(parse_json(content))
