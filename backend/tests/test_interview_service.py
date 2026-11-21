"""generate / get / delete an interview prep pack, against a real (in-memory) database."""

import pytest
from sqlalchemy import func, select

from app.models.interview_prep import InterviewPrep
from app.services import application_service as tracker
from app.services.application_service import ApplicationNotFoundError
from app.services import interview_service as interview
from app.services.interview.errors import NoSavedMatchError
from app.services.interview.pipeline import NOTE_NO_NOTES
from app.services.interview_service import InterviewPrepNotFoundError
from app.services.llm.base import LLMOutputError
from app.services.rag.errors import EmbeddingError
from tests.fakes import ScriptedLLM
from tests.interview_helpers import answers_reply, create_application_with_match, notes_env, questions_reply


def count(db) -> int:
    return db.scalar(select(func.count()).select_from(InterviewPrep))


def generate(db, llm, provider, application_id, count_=3, min_score=None):
    return interview.generate_prep(db, llm, provider, application_id, count_, min_score)


# ======================= generating =======================

def test_a_pack_is_generated_with_cited_outlines_and_flagged_gaps(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env()
    llm = ScriptedLLM([questions_reply(), answers_reply()])

    pack = generate(db, llm, provider, application.id)

    assert (pack.application_id, pack.company, pack.job_title) == (application.id, "Acme Cloud", "Backend Engineer")
    first, second, third = pack.items
    assert first.story_found and "[Faster deployments]" in first.answer_outline and first.sources == ["Faster deployments"]
    assert second.story_found and second.sources == ["Mentoring interns"]
    assert third.story_found is False and third.note == NOTE_NO_NOTES and third.category == "gap"
    assert (pack.coverage.total, pack.coverage.with_story, pack.coverage.without_story) == (3, 2, [3])
    assert pack.questions_to_ask == ["What does success look like in six months?"]
    assert len(llm.prompts) == 2


def test_the_pack_is_saved_on_the_application(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env()
    pack = generate(db, ScriptedLLM([questions_reply(), answers_reply()]), provider, application.id)

    db.expire_all()
    row = db.scalar(select(InterviewPrep))
    assert row.application_id == application.id
    assert set(row.content) == {"items", "questions_to_ask", "coverage"}
    assert row.generated_at.isoformat() == pack.generated_at
    assert interview.get_prep(db, application.id) == pack


def test_the_job_description_and_missing_skills_reach_the_question_prompt(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env()
    llm = ScriptedLLM([questions_reply(), answers_reply()])
    generate(db, llm, provider, application.id)
    assert "We need Python and Docker for backend services" in llm.prompts[0]
    assert "is MISSING: Docker" in llm.prompts[0]
    assert "already has: Python" in llm.prompts[0]


def test_only_questions_with_notes_reach_the_drafting_prompt(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env()
    llm = ScriptedLLM([questions_reply(), answers_reply()])
    generate(db, llm, provider, application.id)
    drafting = llm.prompts[1]
    assert "deployments of the billing service" in drafting and "I mentored two interns" in drafting
    assert '<question id="1"' in drafting and '<question id="2"' in drafting
    assert '<question id="3"' not in drafting


def test_generating_again_replaces_the_pack(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env()
    generate(db, ScriptedLLM([questions_reply(), answers_reply()]), provider, application.id)
    first_time = interview.get_prep(db, application.id).generated_at

    second = generate(db, ScriptedLLM([questions_reply(), answers_reply()]), provider, application.id)
    assert count(db) == 1
    assert second.generated_at >= first_time


def test_without_any_notes_only_one_llm_call_is_made(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env(with_notes=False)
    llm = ScriptedLLM([questions_reply()])  # a second call would raise AssertionError
    pack = generate(db, llm, provider, application.id)
    assert len(llm.prompts) == 1
    assert pack.coverage.with_story == 0 and pack.coverage.without_story == [1, 2, 3]
    assert all(item.note == NOTE_NO_NOTES for item in pack.items)


def test_the_question_count_is_kept_between_3_and_12(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env(with_notes=False)
    llm = ScriptedLLM([questions_reply(), questions_reply()])
    generate(db, llm, provider, application.id, count_=99)
    generate(db, llm, provider, application.id, count_=1)
    assert "exactly 12 questions" in llm.system_prompts[0]
    assert "exactly 3 questions" in llm.system_prompts[1]


# ======================= things that stop it early =======================

def test_an_application_without_a_saved_match_is_refused_before_anything_else(db):
    application = create_application_with_match(db, with_match=False)
    calls = []
    llm = ScriptedLLM([])

    def provider():
        calls.append(1)
        return notes_env()[:2]

    with pytest.raises(NoSavedMatchError, match="saved job match"):
        generate(db, llm, provider, application.id)
    assert calls == [] and llm.prompts == [] and count(db) == 0


def test_an_unknown_application_raises_not_found(db):
    _, _, provider = notes_env()
    with pytest.raises(ApplicationNotFoundError):
        generate(db, ScriptedLLM([]), provider, 999)


def test_an_unavailable_knowledge_base_fails_before_any_llm_call(db):
    application = create_application_with_match(db)
    llm = ScriptedLLM([])

    def broken():
        raise EmbeddingError("The local embedding model failed.")

    with pytest.raises(EmbeddingError):
        generate(db, llm, broken, application.id)
    assert llm.prompts == [] and count(db) == 0


def test_when_the_ai_output_stays_invalid_nothing_is_saved(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env()
    with pytest.raises(LLMOutputError):
        generate(db, ScriptedLLM(["garbage", "more garbage"]), provider, application.id)
    assert count(db) == 0


# ======================= get and delete =======================

def test_getting_a_pack_that_was_never_generated_explains_how(db):
    application = create_application_with_match(db)
    with pytest.raises(InterviewPrepNotFoundError, match="POST /applications/"):
        interview.get_prep(db, application.id)


def test_getting_the_pack_of_an_unknown_application_raises_not_found(db):
    with pytest.raises(ApplicationNotFoundError):
        interview.get_prep(db, 999)


def test_deleting_removes_the_pack(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env()
    generate(db, ScriptedLLM([questions_reply(), answers_reply()]), provider, application.id)
    interview.delete_prep(db, application.id)
    assert count(db) == 0
    with pytest.raises(InterviewPrepNotFoundError):
        interview.get_prep(db, application.id)
    with pytest.raises(InterviewPrepNotFoundError):
        interview.delete_prep(db, application.id)


def test_deleting_the_application_deletes_its_pack(db):
    application = create_application_with_match(db)
    _, _, provider = notes_env()
    generate(db, ScriptedLLM([questions_reply(), answers_reply()]), provider, application.id)
    tracker.delete_application(db, application.id)
    assert count(db) == 0
