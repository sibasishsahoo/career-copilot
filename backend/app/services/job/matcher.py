"""Adapter: turns Pydantic models into plain lists, runs the pure matching code, and
wraps the result back into Pydantic models. No scoring logic lives here - see matching.py."""

from app.schemas.job import JobAnalysis, SkillComparison, SkillGroupResult, SkillMatch
from app.schemas.resume import ParsedResume
from app.services.job.matching import GroupResult, compute_score, match_skills


def build_evidence_text(resume: ParsedResume) -> str:
    """The free text in which a skill may be mentioned even if it is not in the skills list."""
    parts = [resume.summary or ""]
    for experience in resume.experience:
        parts.append(experience.title)
        parts.extend(experience.highlights)
    return "\n".join(parts)


def _to_schema(group: GroupResult) -> SkillGroupResult:
    return SkillGroupResult(
        matched=[SkillMatch(skill=hit.skill, found_in=hit.found_in) for hit in group.matched],
        missing=list(group.missing),
    )


def compare_resume_to_job(resume: ParsedResume, job: JobAnalysis) -> SkillComparison:
    evidence = build_evidence_text(resume)
    required = match_skills(job.required_skills, resume.skills, evidence)
    preferred = match_skills(job.preferred_skills, resume.skills, evidence)
    score = compute_score(required, preferred)  # raises NoSkillsToCompareError if job has no skills
    return SkillComparison(score=score, required=_to_schema(required), preferred=_to_schema(preferred))
