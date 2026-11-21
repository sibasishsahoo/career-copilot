"""Shared set-up for the interview service and API tests: notes, scripted AI replies, an application."""

import json

from app.services.rag import knowledge_service as knowledge
from app.services.rag.embedder import HashingEmbedder
from app.services.rag.vector_store import InMemoryVectorStore

DEPLOY = (
    "Situation: deployments of the billing service took forty minutes.\n\n"
    "Task: reduce deployment time.\n\n"
    "Action: containerized the service and automated rollbacks.\n\n"
    "Result: deployment time fell to twelve minutes."
)
MENTOR = "I mentored two interns, reviewing their code twice a week and teaching testing."
JOB_TEXT = "We need Python and Docker for backend services and deployments."

# Chosen (and measured with the hashing embedder) so that:
#   question 1 finds "Faster deployments", question 2 finds "Mentoring interns", question 3 finds nothing.
Q1 = "Tell me about a time you reduced deployment time for a service."
Q2 = "Describe how you mentored interns and reviewed their code."
Q3 = "How would you use Docker in production?"


def notes_env(with_notes: bool = True):
    """(store, embedder, provider): the provider is what the agent and interview code receive."""
    store, embedder = InMemoryVectorStore(), HashingEmbedder()
    if with_notes:
        knowledge.add_document(store, embedder, "Faster deployments", DEPLOY, 800, 0)
        knowledge.add_document(store, embedder, "Mentoring interns", MENTOR, 800, 0)
    return store, embedder, (lambda: (store, embedder))


def questions_reply(extra_question: str | None = None) -> str:
    questions = [
        {"text": Q1, "category": "behavioral", "why_asked": "Impact on delivery.", "skill": None},
        {"text": Q2, "category": "behavioral", "why_asked": "Leadership.", "skill": None},
        {"text": Q3, "category": "gap", "why_asked": "Probes a missing skill.", "skill": "Docker"},
    ]
    return json.dumps({"questions": questions, "questions_to_ask": ["What does success look like in six months?"]})


def answers_reply() -> str:
    return json.dumps({"answers": [
        {"question_id": 1, "fits": True, "sources_used": [1],
         "outline": "Deployments took forty minutes. I containerized the service and automated rollbacks, cutting it to twelve [1]."},
        {"question_id": 2, "fits": True, "sources_used": [2],
         "outline": "I mentored two interns and reviewed their code twice a week [2]."},
    ]})


def create_application_with_match(db, with_match: bool = True):
    from app.schemas.application import ApplicationCreate, MatchSnapshotCreate  # imported here: needs pydantic
    from app.services import application_service as tracker

    application = tracker.create_application(db, ApplicationCreate(company="Acme Cloud", job_title="Backend Engineer"))
    if with_match:
        tracker.attach_match(db, application.id, MatchSnapshotCreate(
            job_description=JOB_TEXT, score=60,
            matched_skills=[{"skill": "Python", "category": "required"}],
            missing_skills=[{"skill": "Docker", "category": "required"}],
        ))
    return application
