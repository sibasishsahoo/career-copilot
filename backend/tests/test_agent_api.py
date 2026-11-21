"""POST /agent/ask end to end: HTTP -> agent loop -> tools -> real (in-memory) database and notes.

The LLM is a scripted fake that plays the model: each reply is the JSON object a real model would
send for one turn. So these tests need no API key, and the agent's behaviour is fully repeatable."""

import json

import pytest

from app.api.deps import get_knowledge_provider, get_llm
from app.config import Settings, get_settings
from app.main import app
from app.services.llm.base import LLMConfigError, LLMProviderError, LLMRateLimitError
from app.services.rag import knowledge_service as knowledge
from app.services.rag.embedder import HashingEmbedder
from app.services.rag.errors import EmbeddingError
from app.services.rag.vector_store import InMemoryVectorStore
from tests.fakes import ScriptedLLM

DEPLOY = (
    "Situation: deployments of the billing service took forty minutes.\n\n"
    "Task: reduce deployment time.\n\n"
    "Action: containerized the service and automated rollbacks.\n\n"
    "Result: deployment time fell to twelve minutes."
)


def tool_reply(tool, thought="Checking.", **arguments):
    return json.dumps({"thought": thought, "action": "tool", "tool": tool, "arguments": arguments})


def final_reply(answer, thought="Done."):
    return json.dumps({"thought": thought, "action": "final", "answer": answer})


@pytest.fixture
def store():
    return InMemoryVectorStore()


@pytest.fixture
def agent(client, store):
    """The shared test client, with the notes wired to an in-memory store and the hashing embedder."""
    embedder = HashingEmbedder()
    app.dependency_overrides[get_knowledge_provider] = lambda: (lambda: (store, embedder))
    return client


def use_llm(llm):
    app.dependency_overrides[get_llm] = lambda: llm


def ask(client, question="What is going on with my applications?"):
    return client.post("/agent/ask", json={"question": question})


def create_application(client, company, title="Backend Engineer", status="wishlist"):
    response = client.post("/applications", json={"company": company, "job_title": title, "status": status})
    assert response.status_code == 201, response.text
    return response.json()


# ======================= the happy paths =======================

def test_the_agent_looks_up_the_tracker_then_answers(agent):
    create_application(agent, "Acme Corp", status="interviewing")
    create_application(agent, "Globex")
    llm = ScriptedLLM([
        tool_reply("list_applications", "I need the list of applications."),
        final_reply("Acme Corp (Backend Engineer) is furthest along: it is at the interviewing stage."),
    ])
    use_llm(llm)

    response = ask(agent, "Which application is furthest along?")
    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "Which application is furthest along?"
    assert body["answer"].startswith("Acme Corp")
    assert body["stopped_reason"] == "final"

    (step,) = body["steps"]
    assert (step["number"], step["tool"], step["ok"]) == (1, "list_applications", True)
    assert step["thought"] == "I need the list of applications."
    assert step["arguments"] == {}
    assert "Acme Corp" in step["observation"] and "Globex" in step["observation"]

    assert len(llm.prompts) == 2
    assert "Which application is furthest along?" in llm.prompts[0]
    assert "Acme Corp" in llm.prompts[1]  # the tool result was shown to the model on the next turn


def test_the_agent_can_chain_two_tools(agent):
    application = create_application(agent, "Acme Corp")
    llm = ScriptedLLM([
        tool_reply("list_applications", status="wishlist"),
        tool_reply("get_application", id=application["id"]),
        final_reply("Acme Corp was created as a wishlist item and has had no changes since."),
    ])
    use_llm(llm)
    body = ask(agent).json()
    assert [s["tool"] for s in body["steps"]] == ["list_applications", "get_application"]
    assert body["steps"][0]["arguments"] == {"status": "wishlist"}
    assert '"status_history"' in body["steps"][1]["observation"]  # the full details of that one application
    assert "status_history" in llm.prompts[2]


def test_the_agent_can_search_the_career_notes(agent, store):
    knowledge.add_document(store, HashingEmbedder(), "Faster deployments", DEPLOY, 800, 0)
    llm = ScriptedLLM([
        tool_reply("search_knowledge", query="reduce deployment time billing service"),
        final_reply('From my note "Faster deployments": I cut deployment time to twelve minutes.'),
    ])
    use_llm(llm)
    body = ask(agent, "How did I speed up deployments?").json()
    assert body["steps"][0]["tool"] == "search_knowledge"
    assert "Faster deployments" in body["steps"][0]["observation"]
    assert "twelve minutes" in body["steps"][0]["observation"]
    assert "twelve minutes" in body["answer"]


def test_the_agent_can_answer_without_any_tool(agent):
    use_llm(ScriptedLLM([final_reply("Hello! Ask me about your applications or notes.")]))
    body = ask(agent, "Hi").json()
    assert body["steps"] == [] and body["stopped_reason"] == "final"


def test_the_system_prompt_lists_the_three_tools_and_the_read_only_rule(agent):
    llm = ScriptedLLM([final_reply("ok")])
    use_llm(llm)
    ask(agent)
    system = llm.system_prompts[0]
    for name in ("search_knowledge", "list_applications", "get_application"):
        assert name in system
    assert "can only READ" in system


# ======================= mistakes the model can make =======================

def test_an_unknown_tool_becomes_an_error_and_the_agent_recovers(agent):
    create_application(agent, "Acme Corp")
    use_llm(ScriptedLLM([
        tool_reply("delete_application", id=1),
        tool_reply("list_applications"),
        final_reply("I can only read: you have one application, at Acme Corp."),
    ]))
    body = ask(agent, "Delete my Acme application").json()
    assert body["steps"][0]["ok"] is False
    assert "no tool named 'delete_application'" in body["steps"][0]["observation"]
    assert body["steps"][1]["ok"] is True


def test_the_agent_cannot_change_data_even_if_the_model_tries(agent):
    application = create_application(agent, "Acme Corp")
    use_llm(ScriptedLLM([
        tool_reply("update_application", id=application["id"], status="rejected"),
        final_reply("I cannot change anything."),
    ]))
    ask(agent, "Mark Acme as rejected")
    assert agent.get(f"/applications/{application['id']}").json()["status"] == "wishlist"
    assert len(agent.get("/applications").json()) == 1


def test_invalid_arguments_become_an_error_with_usage_help(agent):
    use_llm(ScriptedLLM([
        tool_reply("list_applications", status="ghosted", limit=99),
        final_reply("Sorry, I could not list them."),
    ]))
    step = ask(agent).json()["steps"][0]
    assert step["ok"] is False
    assert "invalid arguments for list_applications" in step["observation"]
    assert "'status' must be one of" in step["observation"] and "'limit' must be at most 25" in step["observation"]
    assert "Usage: list_applications(" in step["observation"]


def test_an_unknown_application_id_is_reported_to_the_model(agent):
    use_llm(ScriptedLLM([tool_reply("get_application", id=999), final_reply("There is no application 999.")]))
    step = ask(agent).json()["steps"][0]
    assert step["ok"] is False
    assert step["observation"] == "Error: Application 999 was not found."


def test_repeating_the_same_call_is_blocked(agent):
    create_application(agent, "Acme Corp")
    use_llm(ScriptedLLM([
        tool_reply("list_applications"),
        tool_reply("list_applications"),
        final_reply("You have one application."),
    ]))
    steps = ask(agent).json()["steps"]
    assert steps[0]["ok"] is True
    assert steps[1]["ok"] is False and "already made this exact call" in steps[1]["observation"]


def test_an_unavailable_knowledge_base_does_not_break_the_agent(agent):
    def broken():
        raise EmbeddingError("The local embedding model failed.")

    app.dependency_overrides[get_knowledge_provider] = lambda: broken
    use_llm(ScriptedLLM([
        tool_reply("search_knowledge", query="leadership"),
        final_reply("I could not search your notes right now."),
    ]))
    response = ask(agent)
    assert response.status_code == 200
    step = response.json()["steps"][0]
    assert step["ok"] is False
    assert step["observation"] == "Error: the knowledge base is unavailable: The local embedding model failed."


def test_a_crashing_tool_is_hidden_from_the_model_and_the_user(agent):
    def crash():
        raise RuntimeError("secret internal detail: /home/me/.env")

    app.dependency_overrides[get_knowledge_provider] = lambda: crash
    use_llm(ScriptedLLM([tool_reply("search_knowledge", query="x"), final_reply("Sorry.")]))
    response = ask(agent)
    assert response.status_code == 200
    assert "failed unexpectedly" in response.json()["steps"][0]["observation"]
    assert "secret internal detail" not in response.text


# ======================= limits =======================

def test_the_step_limit_comes_from_the_settings(agent):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, agent_max_steps=2, gemini_api_key="k"
    )
    llm = ScriptedLLM([
        tool_reply("list_applications", limit=1),
        tool_reply("list_applications", limit=2),
        final_reply("never reached"),
    ])
    use_llm(llm)
    body = ask(agent).json()
    assert body["stopped_reason"] == "max_steps"
    assert len(body["steps"]) == 2
    assert "couldn't finish" in body["answer"] and "2 steps" in body["answer"]
    assert len(llm.prompts) == 2  # the third scripted reply was never requested


def test_the_last_step_tells_the_model_to_wrap_up(agent):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, agent_max_steps=2, gemini_api_key="k"
    )
    llm = ScriptedLLM([tool_reply("list_applications"), final_reply("Wrapped up.")])
    use_llm(llm)
    body = ask(agent).json()
    assert "LAST step" not in llm.prompts[0] and "LAST step" in llm.prompts[1]
    assert body["stopped_reason"] == "final" and body["answer"] == "Wrapped up."


# ======================= errors from the LLM and validation =======================

def test_malformed_model_output_is_retried_transparently(agent):
    llm = ScriptedLLM(["I think I should look things up!", final_reply("All good.")])
    use_llm(llm)
    assert ask(agent).status_code == 200
    assert len(llm.prompts) == 2 and "No JSON object" in llm.prompts[1]


def test_model_output_that_stays_invalid_returns_502(agent):
    use_llm(ScriptedLLM(["garbage", "more garbage"]))
    response = ask(agent)
    assert response.status_code == 502
    assert "valid structured data" in response.json()["detail"]


def test_a_rate_limit_returns_429(agent):
    use_llm(ScriptedLLM([LLMRateLimitError("slow down")]))
    assert ask(agent).status_code == 429


def test_a_provider_failure_returns_502(agent):
    use_llm(ScriptedLLM([LLMProviderError("upstream down")]))
    assert ask(agent).status_code == 502


def test_a_missing_api_key_returns_503(agent):
    def no_key():
        raise LLMConfigError("GEMINI_API_KEY is not set")

    app.dependency_overrides[get_llm] = no_key
    assert ask(agent).status_code == 503


def test_the_question_is_validated(agent):
    use_llm(ScriptedLLM([]))
    assert agent.post("/agent/ask", json={"question": ""}).status_code == 422
    assert agent.post("/agent/ask", json={"question": "   "}).status_code == 422
    assert agent.post("/agent/ask", json={"question": "x" * 501}).status_code == 422
    assert agent.post("/agent/ask", json={}).status_code == 422
    assert agent.post("/agent/ask", json={"question": "ok", "max_steps": 99}).status_code == 422
