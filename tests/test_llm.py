import httpx

from data.llm import explain

TEMPLATE = "Start **Puka Nacua** over **Tyler Lockett** (+3.4 pts)."
OLLAMA_URL = "http://localhost:11434/api/generate"


def test_no_provider_configured_returns_template_untouched(respx_mock, monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    result = explain(TEMPLATE)

    assert result == TEMPLATE
    assert len(respx_mock.calls) == 0


def test_ollama_response_is_used(respx_mock, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    respx_mock.post(OLLAMA_URL).respond(json={"response": "Swap in Puka, he's rolling."})

    result = explain(TEMPLATE)

    assert result == "Swap in Puka, he's rolling."


def test_ollama_timeout_falls_back_to_template(respx_mock, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    respx_mock.post(OLLAMA_URL).mock(side_effect=httpx.TimeoutException("timed out"))

    assert explain(TEMPLATE) == TEMPLATE


def test_ollama_server_error_falls_back_to_template(respx_mock, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    respx_mock.post(OLLAMA_URL).respond(status_code=500)

    assert explain(TEMPLATE) == TEMPLATE


def test_ollama_malformed_json_falls_back_to_template(respx_mock, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    respx_mock.post(OLLAMA_URL).respond(text="not json")

    assert explain(TEMPLATE) == TEMPLATE


def test_ollama_missing_response_key_falls_back_to_template(respx_mock, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    respx_mock.post(OLLAMA_URL).respond(json={"done": True})

    assert explain(TEMPLATE) == TEMPLATE
