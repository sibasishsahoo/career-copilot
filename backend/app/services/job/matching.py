"""Deterministic skill matching and scoring - plain Python, no AI, fully unit-testable.

This is the "code for logic" half of the hybrid design: the score is computed by a
formula you can explain and test. The LLM never decides the number.
"""

from dataclasses import dataclass, field

from app.services.job.errors import NoSkillsToCompareError
from app.services.job.skills import appears_in_text, normalize_skill

# Required skills matter more than nice-to-haves. Change these two numbers to re-tune.
REQUIRED_WEIGHT = 0.7
PREFERRED_WEIGHT = 0.3


@dataclass(frozen=True)
class SkillHit:
    skill: str  # the skill as the JOB wrote it
    found_in: str  # "skills_section" or "experience_text"


@dataclass
class GroupResult:
    matched: list[SkillHit] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.matched) + len(self.missing)

    @property
    def ratio(self) -> float:
        return len(self.matched) / self.total if self.total else 0.0


def match_skills(job_skills: list[str], resume_skills: list[str], evidence_text: str) -> GroupResult:
    """Compare one list of job skills against a resume.

    A job skill counts as matched if:
      1. it is in the resume's skills list (after normalization), or
      2. failing that, it is mentioned as a whole word in `evidence_text`
         (the resume's summary, job titles and bullet points).
    """
    resume_skill_set = {normalize_skill(skill) for skill in resume_skills}
    evidence = evidence_text.lower()

    result = GroupResult()
    seen: set[str] = set()
    for skill in job_skills:
        key = normalize_skill(skill)
        if not key or key in seen:  # skip blanks and duplicates ("JS" + "JavaScript")
            continue
        seen.add(key)

        if key in resume_skill_set:
            result.matched.append(SkillHit(skill, "skills_section"))
        elif appears_in_text(key, evidence):
            result.matched.append(SkillHit(skill, "experience_text"))
        else:
            result.missing.append(skill)
    return result


def compute_score(required: GroupResult, preferred: GroupResult) -> int:
    """Score 0-100:  70% weight on required skills, 30% on preferred skills.

    If the job has only one kind of skill, that kind gets 100% of the weight.
    """
    if required.total == 0 and preferred.total == 0:
        raise NoSkillsToCompareError(
            "The job description does not list any skills, so there is nothing to compare."
        )

    if preferred.total == 0:
        ratio = required.ratio
    elif required.total == 0:
        ratio = preferred.ratio
    else:
        ratio = REQUIRED_WEIGHT * required.ratio + PREFERRED_WEIGHT * preferred.ratio

    return round(ratio * 100)
