import pytest

from app.services.job.errors import NoSkillsToCompareError
from app.services.job.matching import GroupResult, SkillHit, compute_score, match_skills


def names(hits):
    return [hit.skill for hit in hits]


# ---------- match_skills ----------

def test_exact_match_in_skills_section():
    result = match_skills(["Python", "SQL"], ["python", "sql"], "")
    assert names(result.matched) == ["Python", "SQL"]
    assert all(hit.found_in == "skills_section" for hit in result.matched)
    assert result.missing == []


def test_match_ignores_case_and_aliases():
    result = match_skills(["JavaScript", "Kubernetes"], ["JS", "K8s"], "")
    assert names(result.matched) == ["JavaScript", "Kubernetes"]
    assert result.missing == []


def test_missing_skills_are_reported_as_the_job_wrote_them():
    result = match_skills(["Python", "Docker"], ["Python"], "")
    assert names(result.matched) == ["Python"]
    assert result.missing == ["Docker"]


def test_skill_found_in_experience_text_is_labelled_as_such():
    result = match_skills(["Docker"], ["Python"], "Deployed APIs using Docker and Compose")
    assert result.matched == [SkillHit("Docker", "experience_text")]
    assert result.missing == []


def test_skills_section_takes_priority_over_experience_text():
    result = match_skills(["Docker"], ["Docker"], "also used docker daily")
    assert result.matched == [SkillHit("Docker", "skills_section")]


def test_substring_in_text_does_not_count():
    result = match_skills(["SQL"], [], "Administered a MySQL server")
    assert result.matched == []
    assert result.missing == ["SQL"]


def test_duplicate_job_skills_are_counted_once():
    result = match_skills(["JS", "JavaScript", "javascript"], ["JavaScript"], "")
    assert len(result.matched) == 1
    assert result.total == 1


def test_blank_job_skills_are_ignored():
    result = match_skills(["", "  ", "Python"], ["Python"], "")
    assert names(result.matched) == ["Python"]
    assert result.total == 1


def test_empty_job_skill_list():
    result = match_skills([], ["Python"], "text")
    assert result.total == 0
    assert result.ratio == 0.0


def test_empty_resume_matches_nothing():
    result = match_skills(["Python", "SQL"], [], "")
    assert result.matched == []
    assert result.missing == ["Python", "SQL"]


# ---------- compute_score ----------

def group(matched: int, missing: int) -> GroupResult:
    return GroupResult(
        matched=[SkillHit(f"m{i}", "skills_section") for i in range(matched)],
        missing=[f"x{i}" for i in range(missing)],
    )


def test_perfect_match_scores_100():
    assert compute_score(group(4, 0), group(2, 0)) == 100


def test_no_match_scores_0():
    assert compute_score(group(0, 4), group(0, 2)) == 0


def test_weights_are_70_30():
    # all required (1.0 * 0.7) + half of preferred (0.5 * 0.3) = 0.85
    assert compute_score(group(4, 0), group(1, 1)) == 85


def test_required_skills_outweigh_preferred_skills():
    only_required_missing = compute_score(group(0, 2), group(2, 0))  # 0.0*0.7 + 1.0*0.3
    only_preferred_missing = compute_score(group(2, 0), group(0, 2))  # 1.0*0.7 + 0.0*0.3
    assert only_required_missing == 30
    assert only_preferred_missing == 70
    assert only_preferred_missing > only_required_missing


def test_half_of_required_and_all_preferred():
    assert compute_score(group(1, 1), group(3, 0)) == 65  # 0.5*0.7 + 1.0*0.3


def test_only_required_skills_in_job_uses_full_weight():
    assert compute_score(group(3, 1), group(0, 0)) == 75


def test_only_preferred_skills_in_job_uses_full_weight():
    assert compute_score(group(0, 0), group(1, 3)) == 25


def test_score_is_a_whole_number():
    assert isinstance(compute_score(group(1, 2), group(0, 0)), int)
    assert compute_score(group(1, 2), group(0, 0)) == 33


def test_job_without_any_skills_raises():
    with pytest.raises(NoSkillsToCompareError, match="does not list any skills"):
        compute_score(group(0, 0), group(0, 0))
