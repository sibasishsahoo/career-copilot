"""The interview-prep WORKFLOW: fixed steps, run by plain code.

    1. questions  = generate_questions(job)          <- LLM call #1 (injected)
    2. for each question: search the user's notes    <- code, no LLM
    3. drafts     = draft_answers(questions+notes)   <- LLM call #2 (injected), only if some notes were found
    4. check every draft against the notes it may use, and flag questions that have no real story

Why a workflow and not an agent? The steps never change, so code can guarantee the order, the cost
(2 LLM calls) and the shape of the result. The two LLM steps are passed in as functions, so this file
knows nothing about prompts, JSON or providers - and can be tested exactly with prepared answers.
"""

import re
from collections.abc import Callable

from app.services.interview.errors import InterviewGenerationError
from app.services.interview.models import (
    Coverage,
    DraftedAnswer,
    DraftingInput,
    JobContext,
    PrepItem,
    PrepPack,
    Question,
    QuestionPlan,
    QuestionSources,
    Source,
)
from app.services.rag.models import SearchHit

PER_QUESTION_K = 3  # notes retrieved per question
MAX_QUESTIONS_TO_ASK = 6
CATEGORIES = ("behavioral", "technical", "role", "gap")

NOTE_NO_NOTES = "No note in your knowledge base matched this question. Consider writing one."
NOTE_NOT_A_FIT = "Your closest notes do not describe an experience that answers this question."
NOTE_NO_ANSWER = "The AI did not return an answer for this question."
NOTE_UNGROUNDED = "The AI's answer did not cite a valid note, so it was discarded."

QuestionGenerator = Callable[[JobContext, int], QuestionPlan]
Searcher = Callable[[str], list[SearchHit]]
AnswerDrafter = Callable[[DraftingInput], list[DraftedAnswer]]

_CITATION = re.compile(r"\[(\d+)\]")


# ---------------------------------------------------------------------------------------------
# Small, separately testable helpers
# ---------------------------------------------------------------------------------------------

def retrieval_query(question: Question) -> str:
    """What we search the notes for: the question, plus the skill it probes (if any)."""
    return f"{question.text} {question.skill}" if question.skill else question.text


def clean_questions(questions: list[Question], limit: int) -> list[Question]:
    """Drop blanks and duplicates, fix unknown categories, cap the count, and number from 1."""
    seen: set[str] = set()
    cleaned: list[Question] = []
    for question in questions:
        text = " ".join(question.text.split())
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        category = question.category.strip().lower()
        cleaned.append(
            Question(
                number=len(cleaned) + 1,
                text=text,
                category=category if category in CATEGORIES else "role",
                why_asked=" ".join(question.why_asked.split()),
                skill=(question.skill or "").strip() or None,
            )
        )
        if len(cleaned) == limit:
            break
    return cleaned


def clean_questions_to_ask(items: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in items:
        text = " ".join(item.split())
        if text and text.lower() not in seen:
            seen.add(text.lower())
            cleaned.append(text)
    return cleaned[:MAX_QUESTIONS_TO_ASK]


def used_sources(outline: str, declared: list[int], available: list[int]) -> list[int]:
    """The source numbers an answer REALLY used: listed by the model or cited as [n] in the text,
    and only if that source was one of the notes this question was allowed to use."""
    cited = {int(number) for number in _CITATION.findall(outline)}
    return sorted((set(declared) | cited) & set(available))


def replace_citations(outline: str, titles: dict[int, str], available: list[int]) -> str:
    """Make citations readable: "[3]" becomes "[Faster deployments]"; invalid ones are removed."""

    def swap(match: re.Match) -> str:
        number = int(match.group(1))
        return f"[{titles[number]}]" if number in available and number in titles else ""

    text = _CITATION.sub(swap, outline)
    text = re.sub(r"[ \t]{2,}", " ", text)  # tidy the gaps left by removed citations
    text = re.sub(r" ([.,;:!?])", r"\1", text)
    return text.strip()


def _unique(titles: list[str]) -> list[str]:
    return list(dict.fromkeys(titles))


# ---------------------------------------------------------------------------------------------
# The workflow
# ---------------------------------------------------------------------------------------------

def _make_item(
    question: Question,
    available: list[int],
    drafted: DraftedAnswer | None,
    titles: dict[int, str],
) -> PrepItem:
    def without_story(note: str) -> PrepItem:
        return PrepItem(question.number, question.text, question.category, question.why_asked,
                        question.skill, False, None, [], note)

    if not available:
        return without_story(NOTE_NO_NOTES)
    if drafted is None:
        return without_story(NOTE_NO_ANSWER)
    if not drafted.fits:
        return without_story(NOTE_NOT_A_FIT)

    used = used_sources(drafted.outline, drafted.sources_used, available)
    if not used or not drafted.outline.strip():
        return without_story(NOTE_UNGROUNDED)  # claimed a story but could not back it with a note

    return PrepItem(
        number=question.number,
        question=question.text,
        category=question.category,
        why_asked=question.why_asked,
        skill=question.skill,
        story_found=True,
        answer_outline=replace_citations(drafted.outline, titles, available),
        sources=_unique([titles[number] for number in used]),
        note=None,
    )


def build_prep(
    job: JobContext,
    generate_questions: QuestionGenerator,
    search: Searcher,
    draft_answers: AnswerDrafter,
    question_count: int,
    per_question_k: int = PER_QUESTION_K,
) -> PrepPack:
    # 1. Questions (LLM)
    plan = generate_questions(job, question_count)
    questions = clean_questions(plan.questions, question_count)
    if not questions:
        raise InterviewGenerationError("The AI did not return any usable interview questions.")

    # 2. Retrieval (code). Each distinct note passage gets ONE number, shared by every question that finds it.
    sources: list[Source] = []
    number_of: dict[str, int] = {}
    available_for: dict[int, list[int]] = {}
    for question in questions:
        numbers: list[int] = []
        for hit in search(retrieval_query(question))[:per_question_k]:
            if hit.chunk.id not in number_of:
                number_of[hit.chunk.id] = len(sources) + 1
                sources.append(Source(len(sources) + 1, hit.chunk.title, hit.chunk.text))
            number = number_of[hit.chunk.id]
            if number not in numbers:
                numbers.append(number)
        available_for[question.number] = numbers

    # 3. Drafting (LLM) - only for questions that found at least one note; skipped entirely if none did.
    answerable = [QuestionSources(q, available_for[q.number]) for q in questions if available_for[q.number]]
    drafts: dict[int, DraftedAnswer] = {}
    if answerable:
        for draft in draft_answers(DraftingInput(job, answerable, sources)):
            drafts.setdefault(draft.question_number, draft)  # the first answer per question wins

    # 4. Checks (code)
    titles = {source.number: source.title for source in sources}
    items = [_make_item(q, available_for[q.number], drafts.get(q.number), titles) for q in questions]
    missing = [item.number for item in items if not item.story_found]
    coverage = Coverage(total=len(items), with_story=len(items) - len(missing), without_story=missing)
    return PrepPack(items, clean_questions_to_ask(plan.questions_to_ask), coverage)
