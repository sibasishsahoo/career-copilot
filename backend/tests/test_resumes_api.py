import json

from app.api.deps import get_llm
from app.main import app
from app.services.llm.base import LLMProviderError, LLMRateLimitError
from app.services.resume.prompts import EXAMPLE_RESUME
from tests.fakes import ScriptedLLM
from tests.helpers import make_blank_pdf, make_docx, make_pdf

VALID_REPLY = json.dumps(EXAMPLE_RESUME)
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def use_llm(llm):
    app.dependency_overrides[get_llm] = lambda: llm


def upload(client, filename, content, content_type="application/octet-stream"):
    return client.post("/resumes/parse", files={"file": (filename, content, content_type)})


# ---------- success ----------

def test_parse_docx_resume(client):
    llm = ScriptedLLM([VALID_REPLY])
    use_llm(llm)
    response = upload(client, "resume.docx", make_docx(["Jane Doe", "Python developer"]), DOCX_TYPE)
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "resume.docx"
    assert body["parsed"]["full_name"] == "Jane Doe"
    assert "Python developer" in body["text_preview"]
    assert body["text_truncated"] is False
    assert "Python developer" in llm.prompts[0]  # extracted text really reached the LLM


def test_parse_pdf_resume(client):
    use_llm(ScriptedLLM([VALID_REPLY]))
    response = upload(client, "resume.pdf", make_pdf("Jane Doe Python Developer"), "application/pdf")
    assert response.status_code == 200
    assert response.json()["parsed"]["skills"] == ["Python", "SQL"]


def test_retry_happens_transparently(client):
    llm = ScriptedLLM(["not json at all", VALID_REPLY])
    use_llm(llm)
    response = upload(client, "resume.docx", make_docx(["Jane Doe"]), DOCX_TYPE)
    assert response.status_code == 200
    assert len(llm.prompts) == 2


# ---------- file problems (the LLM must never be called) ----------

def test_unsupported_type_returns_415(client):
    llm = ScriptedLLM([])
    use_llm(llm)
    response = upload(client, "resume.txt", b"plain text", "text/plain")
    assert response.status_code == 415
    assert llm.prompts == []


def test_empty_file_returns_400(client):
    use_llm(ScriptedLLM([]))
    assert upload(client, "resume.pdf", b"", "application/pdf").status_code == 400


def test_fake_pdf_returns_400(client):
    use_llm(ScriptedLLM([]))
    response = upload(client, "resume.pdf", b"\x89PNG" + b"0" * 50, "application/pdf")
    assert response.status_code == 400
    assert "not a PDF" in response.json()["detail"]


def test_scanned_pdf_without_text_returns_422(client):
    llm = ScriptedLLM([])
    use_llm(llm)
    response = upload(client, "scan.pdf", make_blank_pdf(), "application/pdf")
    assert response.status_code == 422
    assert llm.prompts == []


def test_oversized_file_returns_413(client, monkeypatch):
    monkeypatch.setattr("app.api.resumes.MAX_UPLOAD_BYTES", 10)
    use_llm(ScriptedLLM([]))
    response = upload(client, "resume.pdf", make_pdf("Jane Doe Python Developer"), "application/pdf")
    assert response.status_code == 413


def test_missing_file_field_returns_422(client):
    use_llm(ScriptedLLM([]))
    assert client.post("/resumes/parse").status_code == 422


# ---------- LLM problems ----------

def test_invalid_llm_output_after_retries_returns_502(client):
    use_llm(ScriptedLLM(["garbage", "more garbage"]))
    response = upload(client, "resume.docx", make_docx(["Jane Doe"]), DOCX_TYPE)
    assert response.status_code == 502
    assert "valid structured data" in response.json()["detail"]


def test_provider_rate_limit_returns_429(client):
    use_llm(ScriptedLLM([LLMRateLimitError("slow down")]))
    assert upload(client, "resume.docx", make_docx(["Jane Doe"]), DOCX_TYPE).status_code == 429


def test_provider_failure_returns_502(client):
    use_llm(ScriptedLLM([LLMProviderError("upstream down")]))
    assert upload(client, "resume.docx", make_docx(["Jane Doe"]), DOCX_TYPE).status_code == 502
