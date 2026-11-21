import copy

import pytest
from pydantic import ValidationError

from app.schemas.resume import ParsedResume
from app.services.resume.prompts import EXAMPLE_RESUME, SYSTEM_PROMPT


def valid_data() -> dict:
    return copy.deepcopy(EXAMPLE_RESUME)


def error_locations(exc_info) -> list[tuple]:
    return [error["loc"] for error in exc_info.value.errors()]


# ---------- valid ----------

def test_full_valid_resume():
    resume = ParsedResume.model_validate(valid_data())
    assert resume.full_name == "Jane Doe"
    assert resume.experience[0].company == "Acme Corp"
    assert resume.education[0].graduation_year == 2019


def test_minimal_resume_uses_defaults_for_optional_fields():
    resume = ParsedResume.model_validate(
        {"full_name": "Ana", "skills": [], "experience": [], "education": []}
    )
    assert resume.email is None
    assert resume.summary is None


def test_nested_optional_fields_default():
    data = valid_data()
    data["experience"] = [{"company": "Acme", "title": "Dev"}]
    resume = ParsedResume.model_validate(data)
    assert resume.experience[0].start_date is None
    assert resume.experience[0].highlights == []


def test_whitespace_is_stripped():
    data = valid_data()
    data["full_name"] = "  Jane Doe  "
    assert ParsedResume.model_validate(data).full_name == "Jane Doe"


def test_unknown_extra_fields_are_ignored():
    data = valid_data()
    data["favorite_color"] = "blue"
    assert not hasattr(ParsedResume.model_validate(data), "favorite_color")


def test_prompt_example_is_a_valid_resume():
    # Guards against the prompt's example drifting out of sync with the schema.
    ParsedResume.model_validate(EXAMPLE_RESUME)
    assert "Jane Doe" in SYSTEM_PROMPT


# ---------- missing fields ----------

def test_missing_full_name():
    data = valid_data()
    del data["full_name"]
    with pytest.raises(ValidationError) as exc_info:
        ParsedResume.model_validate(data)
    assert ("full_name",) in error_locations(exc_info)


def test_missing_skills_list():
    data = valid_data()
    del data["skills"]
    with pytest.raises(ValidationError) as exc_info:
        ParsedResume.model_validate(data)
    assert ("skills",) in error_locations(exc_info)


def test_missing_nested_company_reports_full_path():
    data = valid_data()
    del data["experience"][0]["company"]
    with pytest.raises(ValidationError) as exc_info:
        ParsedResume.model_validate(data)
    assert ("experience", 0, "company") in error_locations(exc_info)


def test_empty_full_name_is_rejected():
    data = valid_data()
    data["full_name"] = ""
    with pytest.raises(ValidationError):
        ParsedResume.model_validate(data)


# ---------- incorrect data types ----------

def test_skills_as_a_string_is_rejected():
    data = valid_data()
    data["skills"] = "Python, SQL"
    with pytest.raises(ValidationError) as exc_info:
        ParsedResume.model_validate(data)
    assert ("skills",) in error_locations(exc_info)


def test_skills_null_is_rejected():
    data = valid_data()
    data["skills"] = None
    with pytest.raises(ValidationError):
        ParsedResume.model_validate(data)


def test_experience_as_a_dict_instead_of_list_is_rejected():
    data = valid_data()
    data["experience"] = {"company": "Acme", "title": "Dev"}
    with pytest.raises(ValidationError):
        ParsedResume.model_validate(data)


def test_graduation_year_text_is_rejected():
    data = valid_data()
    data["education"][0]["graduation_year"] = "twenty nineteen"
    with pytest.raises(ValidationError) as exc_info:
        ParsedResume.model_validate(data)
    assert ("education", 0, "graduation_year") in error_locations(exc_info)


def test_graduation_year_numeric_string_is_converted():
    data = valid_data()
    data["education"][0]["graduation_year"] = "2019"
    assert ParsedResume.model_validate(data).education[0].graduation_year == 2019


def test_graduation_year_can_be_null():
    data = valid_data()
    data["education"][0]["graduation_year"] = None
    assert ParsedResume.model_validate(data).education[0].graduation_year is None


def test_number_where_text_expected_is_rejected():
    data = valid_data()
    data["email"] = 12345
    with pytest.raises(ValidationError):
        ParsedResume.model_validate(data)
