"""The interview-prep workflow with prepared answers in place of the AI: exact, fast, no network."""

import pytest

from app.services.interview.errors import InterviewGenerationError
from app.services.interview.models import DraftedAnswer, JobContext, Question, QuestionPlan
from app.services.interview.pipeline import (
    NOTE_NO_ANSWER,
    NOTE_NO_NOTES,
    NOTE_NOT_A_FIT,
    NOTE_UNGROUNDED,
    build_prep,
    clean_questions,
    clean_questions_to_ask,
    replace_citations,
    retrieval_query,
    used_sources,
)
from app.services.rag.models import SearchHit
from tests.store_contract import make_chunk

JOB = JobContext(7, "Acme", "Backend Engineer", "We need Python and Docker.", 60, ["Python"], ["Docker"])


def question(text, category="behavioral", skill=None, why="To learn more."):
    return Question(0, text, category, why, skill)


def hit(chunk_id, title="Faster deployments", text="I cut deploys from 40 to 12 minutes.", score=0.8):
    return SearchHit(make_chunk(doc_id=chunk_id, title=title, text=text), score)


class Harness:
    """Records what the pipeline asks of each injected step, and answers from a script."""

    def __init__(self, questions, hits_by_text=None, answers=None, to_ask=("Ask me about the team.",)):
        self.questions = questions
        self.hits_by_text = hits_by_text or {}
        self.answers = answers
        self.to_ask = list(to_ask)
        self.generate_calls = []
        self.queries = []
        self.draft_inputs = []

    def generate(self, job, count):
        self.generate_calls.append((job, count))
        return QuestionPlan(self.questions, self.to_ask)

    def search(self, query):
        self.queries.append(query)
        for fragment, hits in self.hits_by_text.items():
            if fragment in query:
                return hits
        return []

    def draft(self, drafting):
        self.draft_inputs.append(drafting)
        if callable(self.answers):
            return self.answers(drafting)
        return list(self.answers or [])

    def run(self, count=8, k=3):
        return build_prep(JOB, self.generate, self.search, self.draft, count, k)


def fits(number, outline, sources):
    return DraftedAnswer(number, True, outline, sources)


# ======================= the happy path =======================

def test_a_question_with_a_matching_note_gets_a_cited_outline():
    h = Harness(
        [question("Tell me about improving deployments.")],
        {"deployments": [hit("a:0")]},
        [fits(1, "I cut deploy time from 40 to 12 minutes [1].", [1])],
    )
    pack = h.run()
    item = pack.items[0]
    assert item.story_found is True and item.note is None
    assert item.answer_outline == "I cut deploy time from 40 to 12 minutes [Faster deployments]."
    assert item.sources == ["Faster deployments"]
    assert (pack.coverage.total, pack.coverage.with_story, pack.coverage.without_story) == (1, 1, [])


def test_the_question_details_are_carried_into_the_item():
    h = Harness([question("Describe a hard bug.", "technical", "Python", "Probes debugging.")],
                {"bug": [hit("a:0")]}, [fits(1, "I fixed it [1].", [1])])
    item = h.run().items[0]
    assert (item.number, item.question, item.category, item.why_asked, item.skill) == (
        1, "Describe a hard bug.", "technical", "Probes debugging.", "Python")


def test_the_generator_receives_the_job_and_the_requested_count():
    h = Harness([question("Q one is long enough?")])
    h.run(count=6)
    assert h.generate_calls == [(JOB, 6)]


def test_questions_to_ask_are_passed_through_cleaned():
    h = Harness([question("Q one is long enough?")], to_ask=["  Ask A  ", "ask a", "", "Ask B"])
    assert h.run().questions_to_ask == ["Ask A", "Ask B"]


# ======================= retrieval =======================

def test_each_question_is_searched_with_its_text_and_skill():
    h = Harness([question("How do you deploy?", skill="Docker"), question("Tell me about teamwork.")])
    h.run()
    assert h.queries == ["How do you deploy? Docker", "Tell me about teamwork."]


def test_retrieval_query_adds_the_skill_only_when_there_is_one():
    assert retrieval_query(Question(1, "Q text here", "gap", "w", "Docker")) == "Q text here Docker"
    assert retrieval_query(Question(1, "Q text here", "gap", "w", None)) == "Q text here"


def test_only_the_first_k_hits_per_question_are_used():
    hits = [hit(f"n{i}:0", title=f"Note {i}") for i in range(5)]
    h = Harness([question("Tell me about deployments.")], {"deployments": hits}, [])
    h.run(k=3)
    assert [s.title for s in h.draft_inputs[0].sources] == ["Note 0", "Note 1", "Note 2"]


def test_a_passage_found_by_several_questions_is_numbered_once():
    shared = hit("shared:0", title="Shared note")
    h = Harness(
        [question("First about deployments?"), question("Second about deployments again?")],
        {"deployments": [shared, hit("only:0", title="Other")]},
        [],
    )
    h.run()
    drafting = h.draft_inputs[0]
    assert [(s.number, s.title) for s in drafting.sources] == [(1, "Shared note"), (2, "Other")]
    assert [q.source_numbers for q in drafting.questions] == [[1, 2], [1, 2]]


def test_the_full_text_of_the_notes_goes_to_the_drafter():
    h = Harness([question("Tell me about deployments.")], {"deployments": [hit("a:0", text="FULL NOTE TEXT")]}, [])
    h.run()
    assert h.draft_inputs[0].sources[0].text == "FULL NOTE TEXT"


# ======================= questions with no story =======================

def test_a_question_without_matching_notes_is_flagged_and_not_sent_to_the_drafter():
    h = Harness(
        [question("Tell me about deployments."), question("Tell me about gardening.")],
        {"deployments": [hit("a:0")]},
        [fits(1, "Done it [1].", [1])],
    )
    pack = h.run()
    assert [q.question.number for q in h.draft_inputs[0].questions] == [1]  # question 2 never asked
    assert pack.items[1].story_found is False and pack.items[1].note == NOTE_NO_NOTES
    assert pack.items[1].answer_outline is None and pack.items[1].sources == []
    assert pack.coverage.without_story == [2]


def test_when_no_note_matches_anything_the_drafter_is_never_called():
    h = Harness([question("Tell me about gardening."), question("Tell me about sailing.")])
    pack = h.run()
    assert h.draft_inputs == []
    assert pack.coverage.with_story == 0 and pack.coverage.without_story == [1, 2]


def test_a_note_that_does_not_really_fit_is_not_presented_as_a_story():
    h = Harness([question("Tell me about deployments.")], {"deployments": [hit("a:0")]},
                [DraftedAnswer(1, False, "", [])])
    item = h.run().items[0]
    assert item.story_found is False and item.note == NOTE_NOT_A_FIT


def test_a_question_the_ai_skipped_is_flagged():
    h = Harness([question("Tell me about deployments."), question("Tell me about teamwork.")],
                {"deployments": [hit("a:0")], "teamwork": [hit("b:0", title="Team")]},
                [fits(1, "Yes [1].", [1])])
    pack = h.run()
    assert pack.items[0].story_found is True
    assert pack.items[1].story_found is False and pack.items[1].note == NOTE_NO_ANSWER


# ======================= checking the AI's citations =======================

def test_an_answer_that_cites_nothing_valid_is_discarded():
    for outline, declared in [("I did great things.", []), ("Cites a stranger [9].", [9]), ("", [1])]:
        h = Harness([question("Tell me about deployments.")], {"deployments": [hit("a:0")]},
                    [fits(1, outline, declared)])
        item = h.run().items[0]
        assert item.story_found is False and item.note == NOTE_UNGROUNDED, outline


def test_a_citation_written_only_in_the_text_counts():
    h = Harness([question("Tell me about deployments.")], {"deployments": [hit("a:0")]},
                [fits(1, "Cut the time [1].", [])])
    assert h.run().items[0].story_found is True


def test_a_source_only_listed_but_not_written_in_the_text_counts():
    h = Harness([question("Tell me about deployments.")], {"deployments": [hit("a:0")]},
                [fits(1, "Cut the time.", [1])])
    item = h.run().items[0]
    assert item.story_found is True and item.sources == ["Faster deployments"]


def test_invalid_citations_are_removed_from_the_text_and_the_source_list():
    h = Harness([question("Tell me about deployments.")], {"deployments": [hit("a:0")]},
                [fits(1, "Cut the time [1] and did more [7].", [1, 7])])
    item = h.run().items[0]
    assert item.answer_outline == "Cut the time [Faster deployments] and did more."
    assert item.sources == ["Faster deployments"]


def test_a_question_cannot_cite_a_note_that_was_only_found_for_another_question():
    h = Harness(
        [question("Tell me about deployments."), question("Tell me about teamwork.")],
        {"deployments": [hit("a:0", title="Deploys")], "teamwork": [hit("b:0", title="Team")]},
        [fits(1, "Deploy story [1].", [1]), fits(2, "Stole the other note [1].", [1])],
    )
    pack = h.run()
    assert pack.items[0].story_found is True
    assert pack.items[1].story_found is False and pack.items[1].note == NOTE_UNGROUNDED


def test_sources_are_listed_by_title_without_repeats():
    h = Harness([question("Tell me about deployments.")],
                {"deployments": [hit("a:0", title="Same note"), hit("a:1", title="Same note"), hit("b:0", title="Other")]},
                [fits(1, "Facts [1][2][3].", [1, 2, 3])])
    assert h.run().items[0].sources == ["Same note", "Other"]


def test_unknown_question_ids_are_ignored_and_the_first_answer_per_question_wins():
    h = Harness([question("Tell me about deployments.")], {"deployments": [hit("a:0")]},
                [fits(99, "Phantom [1].", [1]), fits(1, "First answer [1].", [1]), fits(1, "Second answer [1].", [1])])
    pack = h.run()
    assert len(pack.items) == 1
    assert pack.items[0].answer_outline == "First answer [Faster deployments]."


# ======================= cleaning the AI's questions =======================

def test_questions_are_deduplicated_renumbered_and_capped():
    h = Harness([question("Alpha question here?"), question("  alpha   QUESTION here? "), question(""),
                 question("Beta question here?"), question("Gamma question here?")])
    pack = h.run(count=2)
    assert [(i.number, i.question) for i in pack.items] == [(1, "Alpha question here?"), (2, "Beta question here?")]


def test_an_unknown_category_becomes_role():
    h = Harness([question("A question to ask?", category="trick")])
    assert h.run().items[0].category == "role"


def test_no_usable_questions_is_an_error():
    with pytest.raises(InterviewGenerationError, match="usable interview questions"):
        Harness([question("   "), question("")]).run()


def test_errors_from_the_llm_steps_are_not_swallowed():
    def boom(drafting):
        raise RuntimeError("model down")

    h = Harness([question("Tell me about deployments.")], {"deployments": [hit("a:0")]}, boom)
    with pytest.raises(RuntimeError, match="model down"):
        h.run()


# ======================= helpers =======================

def test_used_sources_combines_declared_and_written_citations_within_the_allowed_set():
    assert used_sources("Facts [2] and [5].", [1, 9], [1, 2, 3]) == [1, 2]
    assert used_sources("No citations.", [], [1, 2]) == []
    assert used_sources("", [3, 3], [3]) == [3]


def test_replace_citations_swaps_numbers_for_titles_and_removes_invalid_ones():
    titles = {1: "Alpha", 2: "Beta"}
    assert replace_citations("A [1] and B [2][1].", titles, [1, 2]) == "A [Alpha] and B [Beta][Alpha]."
    assert replace_citations("Only [1] here, not [2] there.", titles, [1]) == "Only [Alpha] here, not there."
    assert replace_citations("Ends with a stranger [9] .", titles, [1]) == "Ends with a stranger."
    assert replace_citations("Line one [1].\nLine two.", titles, [1]) == "Line one [Alpha].\nLine two."


def test_clean_helpers_directly():
    cleaned = clean_questions([Question(5, " Hello   there friend ", " GAP ", " why  now ", "  ")], 3)
    assert cleaned == [Question(1, "Hello there friend", "gap", "why now", None)]
    assert clean_questions_to_ask(["a"] * 3 + [f"item {n}" for n in range(10)]) == ["a", "item 0", "item 1", "item 2", "item 3", "item 4"]
