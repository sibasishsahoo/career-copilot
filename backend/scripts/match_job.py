"""Run resume + job matching with the REAL LLM provider.

Run from the backend/ folder:
    python -m scripts.match_job path/to/resume.pdf samples/sample_job_description.txt

Uses about 3 LLM calls (parse resume, analyze job, write suggestions), so on the Gemini
free tier wait a minute between runs. Use a fake or anonymized resume on the free tier.
"""

import sys
from pathlib import Path

from app.config import get_settings
from app.services.job.analyzer import analyze_job
from app.services.job.errors import JobError
from app.services.job.matcher import compare_resume_to_job
from app.services.job.suggestions import generate_suggestions
from app.services.llm.base import LLMError
from app.services.llm.factory import get_llm_client
from app.services.resume.cleaner import clean_text
from app.services.resume.errors import ResumeError
from app.services.resume.extractor import MAX_UPLOAD_BYTES, extract_text, read_limited
from app.services.resume.parser import parse_resume_text


def print_group(title: str, group) -> None:
    print(f"\n{title}")
    for hit in group.matched:
        print(f"  [x] {hit.skill}  (found in {hit.found_in.replace('_', ' ')})")
    for skill in group.missing:
        print(f"  [ ] {skill}")
    if not group.matched and not group.missing:
        print("  (none listed)")


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.match_job path/to/resume.pdf|docx path/to/job.txt")
        return 1
    resume_path, job_path = Path(sys.argv[1]), Path(sys.argv[2])

    try:
        llm = get_llm_client(get_settings())

        with resume_path.open("rb") as handle:
            content = read_limited(handle, MAX_UPLOAD_BYTES)
        resume_text = clean_text(extract_text(resume_path.name, content))
        print("1/3 Parsing resume...")
        resume = parse_resume_text(llm, resume_text)

        job_text = job_path.read_text(encoding="utf-8")
        print("2/3 Analyzing job description...")
        job = analyze_job(llm, job_text)

        comparison = compare_resume_to_job(resume, job)  # pure code, no LLM
        print("3/3 Writing suggestions...")
        suggestions = generate_suggestions(llm, resume, job, comparison)
    except (ResumeError, JobError, LLMError, OSError) as exc:
        print(f"FAILED: {exc}")
        return 1

    print(f"\n=== {job.job_title} ({job.company or 'company not stated'}) ===")
    print(f"Match score: {comparison.score}/100  (computed by code, not by the LLM)")
    print_group("Required skills", comparison.required)
    print_group("Preferred skills", comparison.preferred)
    print("\nSuggestions (written by the LLM):")
    for number, text in enumerate(suggestions, start=1):
        print(f"  {number}. {text}")
    if not suggestions:
        print("  Nothing is missing - no suggestions needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
