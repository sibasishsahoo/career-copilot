from app.services.agent.knowledge_tools import build_search_knowledge_tool
from app.services.agent.tools import ToolRegistry, execute_tool
from app.services.rag import knowledge_service as knowledge
from app.services.rag.embedder import Embedder, HashingEmbedder
from app.services.rag.errors import EmbeddingError
from app.services.rag.vector_store import InMemoryVectorStore

DEPLOY = (
    "Situation: deployments of the billing service took forty minutes.\n\n"
    "Task: reduce deployment time.\n\n"
    "Action: containerized the service and automated rollbacks.\n\n"
    "Result: deployment time fell to twelve minutes."
)
MENTOR = "I mentored two interns, reviewing their code twice a week and teaching testing."


def make_registry(min_score=None, notes=((("Faster deploys", DEPLOY)), ("Mentoring", MENTOR))):
    store, embedder = InMemoryVectorStore(), HashingEmbedder()
    for title, text in notes:
        knowledge.add_document(store, embedder, title, text, 800, 0)
    tool = build_search_knowledge_tool(lambda: (store, embedder), min_score)
    return ToolRegistry([tool])


def search(registry, **arguments):
    import json

    outcome = execute_tool(registry, "search_knowledge", arguments)
    return outcome, (json.loads(outcome.observation) if outcome.ok else None)


def test_it_returns_matching_notes_with_titles_and_scores():
    outcome, data = search(make_registry(), query="reduce deployment time for the billing service")
    assert outcome.ok
    assert data["count"] == 1  # the mentoring note shares no words, so it is below the cut-off
    match = data["matches"][0]
    assert match["note"] == "Faster deploys"
    assert 0.3 < match["score"] <= 1.0
    assert "deployments of the billing service" in match["text"]


def test_a_query_that_matches_nothing_says_so():
    _, data = search(make_registry(), query="pizza toppings volcano")
    assert data == {"count": 0, "matches": [], "message": "No notes matched this query."}


def test_an_empty_knowledge_base_just_returns_no_matches():
    _, data = search(make_registry(notes=()), query="anything")
    assert data["count"] == 0


def test_k_limits_the_number_of_passages():
    registry = make_registry(notes=(("A", DEPLOY), ("B", DEPLOY), ("C", DEPLOY)))
    _, data = search(registry, query="deployment time billing", k=2)
    assert data["count"] == 2


def test_k_defaults_to_three():
    registry = make_registry(notes=tuple((f"N{n}", DEPLOY) for n in range(6)))
    _, data = search(registry, query="deployment time billing")
    assert data["count"] == 3


def test_a_configured_min_score_overrides_the_embedders_default():
    strict = make_registry(min_score=0.99)
    _, data = search(strict, query="reduce deployment time for the billing service")
    assert data["count"] == 0


def test_invalid_arguments_are_reported_as_errors_not_raised():
    registry = make_registry()
    for arguments in [{}, {"query": ""}, {"query": "x" * 501}, {"query": "ok", "k": 0}, {"query": "ok", "k": 9}]:
        outcome, _ = search(registry, **arguments)
        assert outcome.ok is False and outcome.observation.startswith("Error: invalid arguments")


def test_an_unavailable_knowledge_base_becomes_an_error_observation():
    def broken_provider():
        raise EmbeddingError("The local embedding model failed.")

    registry = ToolRegistry([build_search_knowledge_tool(broken_provider, None)])
    outcome, _ = search(registry, query="anything")
    assert outcome.ok is False
    assert outcome.observation == "Error: the knowledge base is unavailable: The local embedding model failed."


def test_a_failing_embedder_during_search_is_also_handled():
    class Broken(Embedder):
        name = "broken"

        def embed(self, texts):
            raise EmbeddingError("model crashed")

    registry = ToolRegistry([build_search_knowledge_tool(lambda: (InMemoryVectorStore(), Broken()), None)])
    outcome, _ = search(registry, query="anything")
    assert outcome.ok is False and "model crashed" in outcome.observation


def test_the_provider_is_only_called_when_the_tool_is_used():
    calls = []

    def provider():
        calls.append(1)
        return InMemoryVectorStore(), HashingEmbedder()

    build_search_knowledge_tool(provider, None)
    assert calls == []  # building the tool does not open the database or load the model
