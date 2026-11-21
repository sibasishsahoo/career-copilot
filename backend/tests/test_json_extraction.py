import pytest

from app.services.llm.json_utils import JSONExtractionError, extract_json_object


def test_plain_json():
    assert extract_json_object('{"name": "Ana", "age": 30}') == {"name": "Ana", "age": 30}


def test_json_in_code_fence_with_language_tag():
    reply = 'Here you go:\n```json\n{"name": "Ana"}\n```\nAnything else?'
    assert extract_json_object(reply) == {"name": "Ana"}


def test_json_in_plain_code_fence():
    assert extract_json_object('```\n{"a": 1}\n```') == {"a": 1}


def test_chatter_before_and_after_without_fence():
    reply = 'Sure! {"a": 1} Hope that helps.'
    assert extract_json_object(reply) == {"a": 1}


def test_nested_objects_and_lists():
    reply = '{"outer": {"inner": [1, 2, {"x": "}"}]}}'
    assert extract_json_object(reply) == {"outer": {"inner": [1, 2, {"x": "}"}]}}


def test_surrounding_whitespace_is_ignored():
    assert extract_json_object('\n\n  {"a": 1}  \n') == {"a": 1}


def test_no_json_at_all():
    with pytest.raises(JSONExtractionError, match="No JSON object"):
        extract_json_object("Sorry, I cannot help with that.")


def test_empty_reply():
    with pytest.raises(JSONExtractionError):
        extract_json_object("")


def test_json_array_is_not_an_object():
    with pytest.raises(JSONExtractionError):
        extract_json_object("[1, 2, 3]")


def test_trailing_comma_is_malformed():
    with pytest.raises(JSONExtractionError, match="malformed JSON"):
        extract_json_object('{"a": 1,}')


def test_single_quotes_are_malformed():
    with pytest.raises(JSONExtractionError, match="malformed JSON"):
        extract_json_object("{'a': 1}")


def test_truncated_json_is_malformed():
    with pytest.raises(JSONExtractionError, match="malformed JSON"):
        extract_json_object('{"name": "Ana", "skills": ["Python", "SQ')


def test_error_message_includes_position():
    with pytest.raises(JSONExtractionError, match="line 1, column"):
        extract_json_object('{"a": }')
