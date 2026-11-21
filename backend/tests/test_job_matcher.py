import pytest

from app.schemas.job import JobAnalysis
from app.schemas.resume import ParsedResume
from app.services.job.errors import NoSkillsToCompareError
from app.services.job.matcher import build_evidence_text, compare_resume_to_job


def make_resume(skills=None, summary=None, title="Software Engineer", highlights=None) -> ParsedResume:
    return ParsedResume(
        full_name="Jane Doe",
        summary=summary,
        skills=skills or [],
        experience=[
            {"company": "Acme", "title": title, "highlights": highlights or []},
        ],
        education=[],
    )


def make_job(required=None, preferred=None) -> JobAnalysis:
    return JobAnalysis(
        job_title="Backend Engineer",
        required_skills=required or [],
        preferred_skills=preferred or [],
        responsibilities=[],
    )


def test_matched_missing_and_score():
    resume = make_resume(skills=["Python", "SQL"])
    job = make_job(required=["Python", "SQL", "REST APIs"], preferred=["Docker", "AWS"])
    result = compare_resume_to_job(resume, job)
    assert [m.skill for m in result.required.matched] == ["Python", "SQL"]
    assert result.required.missing == ["REST APIs"]
    assert result.preferred.matched == []
    assert result.preferred.missing == ["Docker", "AWS"]
    assert result.score == 47  # 0.7 * (2/3) + 0.3 * 0 = 46.7


def test_perfect_match():
    resume = make_resume(skills=["Python", "Docker"])
    job = make_job(required=["Python"], preferred=["Docker"])
    result = compare_resume_to_job(resume, job)
    assert result.score == 100
    assert result.required.missing == []
    assert result.preferred.missing == []


def test_skill_found_in_a_highlight_is_labelled_experience_text():
    resume = make_resume(skills=["Python"], highlights=["Deployed services with Docker"])
    result = compare_resume_to_job(resume, make_job(required=["Python", "Docker"]))
    by_skill = {m.skill: m.found_in for m in result.required.matched}
    assert by_skill == {"Python": "skills_section", "Docker": "experience_text"}


def test_skill_found_in_the_summary_counts():
    resume = make_resume(summary="Engineer with deep AWS experience")
    result = compare_resume_to_job(resume, make_job(required=["AWS"]))
    assert result.required.matched[0].found_in == "experience_text"


def test_skill_found_in_job_title_counts():
    resume = make_resume(title="Senior Kubernetes Engineer")
    result = compare_resume_to_job(resume, make_job(required=["Kubernetes"]))
    assert len(result.required.matched) == 1


def test_aliases_match_between_resume_and_job():
    resume = make_resume(skills=["ReactJS", "Amazon Web Services"])
    result = compare_resume_to_job(resume, make_job(required=["React", "AWS"]))
    assert result.required.missing == []
    assert result.score == 100


def test_substring_in_experience_text_does_not_count():
    resume = make_resume(highlights=["Tuned MySQL queries"])
    result = compare_resume_to_job(resume, make_job(required=["SQL"]))
    assert result.required.missing == ["SQL"]


def test_resume_with_no_skills_scores_zero():
    result = compare_resume_to_job(make_resume(), make_job(required=["Python"]))
    assert result.score == 0


def test_job_with_no_skills_raises():
    with pytest.raises(NoSkillsToCompareError):
        compare_resume_to_job(make_resume(skills=["Python"]), make_job())


def test_only_preferred_skills_still_scores():
    resume = make_resume(skills=["Docker"])
    result = compare_resume_to_job(resume, make_job(preferred=["Docker", "AWS"]))
    assert result.score == 50


def test_evidence_text_contains_summary_titles_and_highlights():
    resume = make_resume(summary="SUMMARY", title="TITLE", highlights=["BULLET ONE", "BULLET TWO"])
    evidence = build_evidence_text(resume)
    for expected in ["SUMMARY", "TITLE", "BULLET ONE", "BULLET TWO"]:
        assert expected in evidence


def test_evidence_text_handles_missing_summary():
    assert "None" not in build_evidence_text(make_resume(summary=None))
