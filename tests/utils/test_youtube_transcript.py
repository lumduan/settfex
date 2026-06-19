"""Tests for the YouTube transcript utility (youtube-transcript-api fully mocked)."""

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from settfex.utils.youtube_transcript import fetch_youtube_transcript


def _api_returning(snippets: list[dict[str, Any]]) -> MagicMock:
    """Mock YouTubeTranscriptApi whose fetch().to_raw_data() returns `snippets`."""
    api = MagicMock()
    api.fetch.return_value.to_raw_data.return_value = snippets
    return api


class TestFetchYoutubeTranscript:
    @pytest.mark.asyncio
    async def test_joins_snippets_into_string(self) -> None:
        api = _api_returning([{"text": "สวัสดี"}, {"text": "ครับ"}])
        with patch("youtube_transcript_api.YouTubeTranscriptApi", return_value=api):
            text = await fetch_youtube_transcript("vid", languages=("th",))
        assert text == "สวัสดี ครับ"
        assert api.fetch.call_args.kwargs["languages"] == ["th"]

    @pytest.mark.asyncio
    async def test_custom_join_separator(self) -> None:
        api = _api_returning([{"text": "a"}, {"text": "b"}])
        with patch("youtube_transcript_api.YouTubeTranscriptApi", return_value=api):
            text = await fetch_youtube_transcript("vid", join_with="\n")
        assert text == "a\nb"

    @pytest.mark.asyncio
    async def test_empty_snippets_returns_none(self) -> None:
        api = _api_returning([])
        with patch("youtube_transcript_api.YouTubeTranscriptApi", return_value=api):
            assert await fetch_youtube_transcript("vid") is None

    @pytest.mark.asyncio
    async def test_retrieval_failure_returns_none(self) -> None:
        # Any retrieval failure (disabled / blocked / unavailable) -> None, never raises.
        api = MagicMock()
        api.fetch.side_effect = RuntimeError("IpBlocked")
        with patch("youtube_transcript_api.YouTubeTranscriptApi", return_value=api):
            assert await fetch_youtube_transcript("vid") is None

    @pytest.mark.asyncio
    async def test_missing_library_raises_importerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "youtube_transcript_api", None)
        with pytest.raises(ImportError, match=r"settfex\[transcript\]"):
            await fetch_youtube_transcript("vid")

    @pytest.mark.asyncio
    async def test_proxies_build_generic_config(self) -> None:
        api = _api_returning([{"text": "x"}])
        with (
            patch("youtube_transcript_api.YouTubeTranscriptApi", return_value=api) as ctor,
            patch("youtube_transcript_api.proxies.GenericProxyConfig") as proxy_cls,
        ):
            await fetch_youtube_transcript("vid", proxies={"http": "http://p", "https": "http://p"})
        assert proxy_cls.called
        assert ctor.call_args.kwargs["proxy_config"] is proxy_cls.return_value
