import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from cogs import translator


def make_cog():
    cog = object.__new__(translator.TranslationCog)
    cog.lang_code_map = {}
    return cog


def test_flag_reaction_fetches_and_translates_uncached_message():
    cog = make_cog()
    cog.FLAG_EMOJI_PATTERN = translator.re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")
    cog.multi_lang_countries = {}
    cog.emoji_to_lang = {"🇫🇷": "fr"}
    user = SimpleNamespace(bot=False)
    message = SimpleNamespace(author=SimpleNamespace(bot=False))
    channel = SimpleNamespace(fetch_message=AsyncMock(return_value=message))
    cog.bot = SimpleNamespace(
        user=SimpleNamespace(id=1),
        get_user=Mock(return_value=user),
        get_channel=Mock(return_value=channel),
    )
    cog.translate_message = AsyncMock()
    payload = SimpleNamespace(
        emoji="🇫🇷",
        user_id=2,
        member=user,
        channel_id=3,
        message_id=4,
    )

    asyncio.run(cog.on_raw_reaction_add(payload))

    channel.fetch_message.assert_awaited_once_with(4)
    cog.translate_message.assert_awaited_once_with(message, "fr", user)


def test_google_translation_is_primary_and_skips_fallbacks(monkeypatch):
    google = Mock(return_value="bonjour")
    deepl = Mock()
    mymemory = Mock()
    monkeypatch.setattr(translator, "translate_with_google", google)
    monkeypatch.setattr(translator, "translate_with_deepl", deepl)
    monkeypatch.setattr(translator, "translate_with_mymemory", mymemory)
    monkeypatch.setattr(translator, "detect", lambda text: "en")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-test-key")
    monkeypatch.setenv("MYMEMORY_API_KEY", "mymemory-test-key")

    result = make_cog()._translate_text_sync("hello", "fr")

    assert result == ("bonjour", "en")
    google.assert_called_once_with("hello", "en", "fr")
    deepl.assert_not_called()
    mymemory.assert_not_called()


def test_deepl_is_first_fallback_and_uses_free_api(monkeypatch):
    calls = []

    def google(text, source, target):
        calls.append("google")
        raise RuntimeError("Google unavailable")

    def deepl(text, source, target, api_key):
        calls.append("deepl")
        assert api_key == "deepl-test-key"
        return "bonjour"

    mymemory = Mock()
    monkeypatch.setattr(translator, "translate_with_google", google)
    monkeypatch.setattr(translator, "translate_with_deepl", deepl)
    monkeypatch.setattr(translator, "translate_with_mymemory", mymemory)
    monkeypatch.setattr(translator, "detect", lambda text: "en")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-test-key")
    monkeypatch.setenv("MYMEMORY_API_KEY", "mymemory-test-key")

    assert make_cog()._translate_text_sync("hello", "fr") == ("bonjour", "en")
    assert calls == ["google", "deepl"]
    mymemory.assert_not_called()


def test_vietnamese_uses_mymemory_locale_when_deepl_does_not_support_it(monkeypatch):
    google = Mock(side_effect=RuntimeError("Google unavailable"))
    deepl = Mock(side_effect=RuntimeError("DeepL unsupported language"))
    mymemory = Mock(return_value="xin chao")
    monkeypatch.setattr(translator, "translate_with_google", google)
    monkeypatch.setattr(translator, "translate_with_deepl", deepl)
    monkeypatch.setattr(translator, "translate_with_mymemory", mymemory)
    monkeypatch.setattr(translator, "detect", lambda text: "en")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-test-key")
    monkeypatch.setenv("MYMEMORY_API_KEY", "mymemory-test-key")

    result = make_cog()._translate_text_sync("hello", "vi")

    assert result == ("xin chao", "en")
    deepl.assert_called_once_with("hello", "en", "vi", "deepl-test-key")
    mymemory.assert_called_once_with("hello", "en", "vi", "mymemory-test-key")


def test_mymemory_is_used_after_google_and_deepl_fail(monkeypatch):
    calls = []

    def google(text, source, target):
        calls.append("google")
        raise RuntimeError("Google unavailable")

    def deepl(text, source, target, api_key):
        calls.append("deepl")
        raise RuntimeError("DeepL unavailable")

    def mymemory(text, source, target, api_key):
        calls.append("mymemory")
        assert api_key == "mymemory-test-key"
        return "bonjour"

    monkeypatch.setattr(translator, "translate_with_google", google)
    monkeypatch.setattr(translator, "translate_with_deepl", deepl)
    monkeypatch.setattr(translator, "translate_with_mymemory", mymemory)
    monkeypatch.setattr(translator, "detect", lambda text: "en")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-test-key")
    monkeypatch.setenv("MYMEMORY_API_KEY", "mymemory-test-key")

    assert make_cog()._translate_text_sync("hello", "fr") == ("bonjour", "en")
    assert calls == ["google", "deepl", "mymemory"]


def test_google_http_adapter_parses_translation_segments(monkeypatch):
    response = Mock()
    response.json.return_value = [
        [["Bonjour", "Hello", None, None], [" monde", " world", None, None]]
    ]
    request = Mock(return_value=response)
    monkeypatch.setattr(translator.requests, "get", request)

    result = translator.translate_with_google("Hello world", "en", "fr")

    assert result == "Bonjour monde"
    request.assert_called_once_with(
        translator.GOOGLE_TRANSLATE_URL,
        params={"client": "gtx", "sl": "en", "tl": "fr", "dt": "t", "q": "Hello world"},
        timeout=15,
    )


def test_deepl_http_adapter_uses_free_api_and_auth_header(monkeypatch):
    response = Mock()
    response.json.return_value = {"translations": [{"text": "bonjour"}]}
    request = Mock(return_value=response)
    monkeypatch.setattr(translator.requests, "post", request)

    result = translator.translate_with_deepl("hello", "en", "fr", "test-key")

    assert result == "bonjour"
    request.assert_called_once_with(
        translator.DEEPL_FREE_TRANSLATE_URL,
        headers={"Authorization": "DeepL-Auth-Key test-key"},
        data={"text": "hello", "target_lang": "FR", "source_lang": "EN"},
        timeout=15,
    )


def test_mymemory_http_adapter_uses_api_key_without_email_and_unescapes(monkeypatch):
    response = Mock()
    response.json.return_value = {
        "responseStatus": 200,
        "responseData": {"translatedText": "bonjour &amp; merci"},
    }
    request = Mock(return_value=response)
    monkeypatch.setattr(translator.requests, "get", request)

    result = translator.translate_with_mymemory(
        "hello", "en", "fr", "mymemory-test-key"
    )

    assert result == "bonjour & merci"
    request.assert_called_once_with(
        translator.MYMEMORY_TRANSLATE_URL,
        params={
            "q": "hello",
            "langpair": "en|fr",
            "key": "mymemory-test-key",
        },
        timeout=15,
    )


def test_mymemory_adapter_preserves_chunk_boundary_whitespace(monkeypatch):
    def fake_get(url, *, params, timeout):
        response = Mock()
        response.json.return_value = {
            "responseStatus": 200,
            "responseData": {"translatedText": params["q"].upper()},
        }
        return response

    monkeypatch.setattr(translator.requests, "get", fake_get)
    text = "hello " * 100

    result = translator.translate_with_mymemory(text, "en", "fr", "test-key")

    assert result == text.upper()


def test_mymemory_can_use_anonymous_request(monkeypatch):
    response = Mock()
    response.json.return_value = {
        "responseStatus": 200,
        "responseData": {"translatedText": "bonjour"},
    }
    request = Mock(return_value=response)
    monkeypatch.setattr(translator.requests, "get", request)

    assert translator.translate_with_mymemory("hello", "en", "fr") == "bonjour"
    assert request.call_args.kwargs["params"] == {
        "q": "hello",
        "langpair": "en|fr",
    }


def test_mymemory_chunks_are_utf8_safe_and_within_byte_limit():
    text = "café 😀 translation " * 80

    chunks = translator.split_text_for_mymemory(text)

    assert "".join(chunks) == text
    assert all(
        len(chunk.encode("utf-8")) <= translator.MYMEMORY_MAX_BYTES for chunk in chunks
    )


def test_all_provider_failures_raise_safe_error_without_logging_keys(
    monkeypatch, caplog
):
    secret = "test-secret-key"
    monkeypatch.setattr(
        translator, "translate_with_google", Mock(side_effect=RuntimeError(secret))
    )
    monkeypatch.setattr(
        translator, "translate_with_deepl", Mock(side_effect=RuntimeError(secret))
    )
    monkeypatch.setattr(
        translator,
        "translate_with_mymemory",
        Mock(side_effect=RuntimeError(secret)),
    )
    monkeypatch.setattr(translator, "detect", lambda text: "en")
    monkeypatch.setenv("DEEPL_API_KEY", secret)
    monkeypatch.setenv("MYMEMORY_API_KEY", secret)

    with pytest.raises(translator.TranslationUnavailable):
        make_cog()._translate_text_sync("hello", "fr")

    assert secret not in caplog.text
