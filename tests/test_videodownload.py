import asyncio
import inspect
import socket
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from yt_dlp.cookies import YoutubeDLCookieJar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs import videodownload


def test_build_gallery_dl_command_uses_explicit_download_directory(tmp_path):
    command, cookie_file = videodownload.build_gallery_dl_command(
        "https://example.com/video", tmp_path
    )

    assert command[0] == "gallery-dl"
    assert "-d" in command
    assert command[command.index("-d") + 1] == str(tmp_path)
    assert command[-1] == "https://example.com/video"
    assert cookie_file is None


def test_find_downloaded_media_prefers_video_files(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "cover.jpg").write_bytes(b"image")
    video_path = media_dir / "clip.mp4"
    video_path.write_bytes(b"video")

    found = videodownload.find_downloaded_media(media_dir)

    assert found == [video_path]


def test_build_gallery_dl_command_uses_instagram_cookies(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_COOKIES", "sessionid=abc123")

    command, cookie_file = videodownload.build_gallery_dl_command(
        "https://www.instagram.com/reel/example/", tmp_path, is_instagram=True
    )

    assert command[0] == "gallery-dl"
    assert "--cookies" in command
    assert cookie_file is not None
    assert "# Netscape HTTP Cookie File" in Path(cookie_file).read_text(
        encoding="utf-8"
    )
    assert "sessionid" in Path(cookie_file).read_text(encoding="utf-8")
    cookie_jar = YoutubeDLCookieJar()
    cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
    assert any(cookie.name == "sessionid" for cookie in cookie_jar)
    Path(cookie_file).unlink()


def test_build_ffmpeg_command_uses_h264_settings(tmp_path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"

    command = videodownload.build_ffmpeg_command(input_path, output_path)

    assert command[0] == "ffmpeg"
    assert str(input_path) in command
    assert str(output_path) in command
    assert "-c:v" in command
    assert "libx264" in command


def test_build_ffmpeg_command_accepts_compression_profile(tmp_path):
    command = videodownload.build_ffmpeg_command(
        tmp_path / "input.mp4",
        tmp_path / "output.mp4",
        crf=36,
        width=640,
        audio_bitrate="64k",
    )

    assert command[command.index("-crf") + 1] == "36"
    assert command[command.index("-vf") + 1].startswith("scale=640:")
    assert command[command.index("-b:a") + 1] == "64k"


def test_compress_video_retries_until_output_fits(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original")
    outputs = []

    def run(command, **kwargs):
        output = Path(command[-1])
        outputs.append(output)
        output.write_bytes(b"x" * (120 if len(outputs) == 1 else 80))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(videodownload.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(videodownload.subprocess, "run", run)

    compressed = Path(videodownload.compress_video_for_discord(source, max_size=100))

    assert len(outputs) == 2
    assert not outputs[0].exists()
    assert compressed == outputs[1]
    assert compressed.stat().st_size <= 100
    assert not source.exists()


def test_compress_video_failure_removes_partial_output_and_preserves_source(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original")
    partial_outputs = []

    def run(command, **kwargs):
        output = Path(command[-1])
        output.write_bytes(b"partial")
        partial_outputs.append(output)
        return subprocess.CompletedProcess(command, 1, "", "ffmpeg failed")

    monkeypatch.setattr(videodownload.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(videodownload.subprocess, "run", run)

    try:
        videodownload.compress_video_for_discord(source, max_size=100)
    except videodownload.VideoCompressionError:
        pass
    else:
        raise AssertionError("Expected compression failure")

    assert source.read_bytes() == b"original"
    assert partial_outputs and all(not output.exists() for output in partial_outputs)


def test_compress_video_reports_limit_when_all_profiles_are_too_large(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original")
    outputs = []

    def run(command, **kwargs):
        output = Path(command[-1])
        output.write_bytes(b"x" * 120)
        outputs.append(output)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(videodownload.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(videodownload.subprocess, "run", run)

    try:
        videodownload.compress_video_for_discord(source, max_size=100)
    except videodownload.VideoTooLargeError:
        pass
    else:
        raise AssertionError("Expected the compression size limit to be reported")

    assert source.read_bytes() == b"original"
    assert len(outputs) == len(videodownload.COMPRESSION_PROFILES)
    assert all(not output.exists() for output in outputs)


def test_download_video_passes_attachment_limit_to_compressor(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"x" * 101)
    compressed = tmp_path / "compressed.mp4"
    compressed.write_bytes(b"x" * 80)
    monkeypatch.setattr(
        videodownload, "download_with_ytdlp", Mock(return_value=str(source))
    )
    monkeypatch.setattr(
        videodownload,
        "probe_media",
        lambda path: {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p"}
            ]
        },
    )
    compressor = Mock(return_value=str(compressed))
    monkeypatch.setattr(videodownload, "compress_video_for_discord", compressor)

    result = videodownload.download_video_for_discord(
        "https://youtube.com/watch?v=test", str(tmp_path), 100
    )

    assert result == str(compressed)
    compressor.assert_called_once_with(str(source), 100)


def test_build_ytdlp_options_prefers_h264_and_aac(tmp_path):
    options = videodownload.build_ytdlp_options(
        tmp_path / "download.mp4", socket_timeout=30
    )

    assert options["format"] == "bestvideo+bestaudio/best"
    assert options["format_sort"] == ["vcodec:h264", "acodec:aac"]
    assert options["socket_timeout"] == 30
    with videodownload.YoutubeDL(options) as ydl:
        assert ydl.params["format_sort"] == options["format_sort"]


def test_tiktok_downloader_uses_shared_ytdlp_with_platform_overrides(
    monkeypatch, tmp_path
):
    download = Mock(return_value="download.mp4")
    monkeypatch.setattr(videodownload, "download_with_ytdlp", download)

    result = videodownload.download_tiktok_video("https://tiktok.com/video/1", tmp_path)

    assert result == "download.mp4"
    download.assert_called_once()
    assert download.call_args.args == ("https://tiktok.com/video/1", tmp_path)
    assert download.call_args.kwargs["socket_timeout"] == 30
    assert download.call_args.kwargs["retries"] == 10
    assert download.call_args.kwargs["extractor_retries"] == 10


def test_validate_video_url_accepts_supported_domains():
    assert videodownload.resolve_video_platform("https://youtu.be/example") == "youtube"
    assert (
        videodownload.resolve_video_platform("https://www.youtube.com/shorts/example")
        == "youtube"
    )
    assert (
        videodownload.resolve_video_platform("https://www.facebook.com/reel/example")
        == "facebook"
    )
    assert (
        videodownload.resolve_video_platform("https://fb.watch/example") == "facebook"
    )
    assert (
        videodownload.resolve_video_platform("https://www.instagram.com/reel/example/")
        == "instagram"
    )


def test_video_command_only_accepts_a_url():
    parameters = list(
        inspect.signature(
            videodownload.VideoDownload.download_video.callback
        ).parameters
    )

    assert parameters == ["self", "interaction", "url"]


def test_generic_fallback_allows_public_hostname(monkeypatch):
    monkeypatch.setattr(
        videodownload.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", 443),
            )
        ],
    )

    assert (
        videodownload.resolve_video_platform("https://media.example/video") == "generic"
    )


def test_generic_fallback_rejects_private_or_unresolvable_hosts(monkeypatch):
    monkeypatch.setattr(
        videodownload.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.0.0.2", 443),
            )
        ],
    )
    with pytest.raises(videodownload.UnsupportedVideoUrl):
        videodownload.resolve_video_platform("https://media.example/video")

    with pytest.raises(videodownload.UnsupportedVideoUrl):
        videodownload.resolve_video_platform("http://127.0.0.1/video")


def test_facebook_and_youtube_dispatch_directly_to_ytdlp(tmp_path, monkeypatch):
    video_path = tmp_path / "download.mp4"
    video_path.write_bytes(b"video")
    downloader = Mock(return_value=str(video_path))
    monkeypatch.setattr(videodownload, "download_with_ytdlp", downloader)
    monkeypatch.setattr(
        videodownload,
        "probe_media",
        lambda path: {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p"}
            ]
        },
    )

    assert videodownload.download_video_for_discord(
        "https://facebook.com/watch/example", str(tmp_path), 100
    ) == str(video_path)
    assert videodownload.download_video_for_discord(
        "https://youtube.com/watch?v=example", str(tmp_path), 100
    ) == str(video_path)
    assert downloader.call_count == 2


def test_unknown_public_url_uses_generic_ytdlp(tmp_path, monkeypatch):
    video_path = tmp_path / "download.mp4"
    video_path.write_bytes(b"video")
    downloader = Mock(return_value=str(video_path))
    monkeypatch.setattr(videodownload, "download_with_ytdlp", downloader)
    monkeypatch.setattr(
        videodownload.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", 443),
            )
        ],
    )
    monkeypatch.setattr(
        videodownload,
        "probe_media",
        lambda path: {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p"}
            ]
        },
    )

    video_url = "https://media.example/video"
    result = videodownload.download_video_for_discord(video_url, str(tmp_path), 100)

    assert result == str(video_path)
    downloader.assert_called_once_with(video_url, str(tmp_path))


def test_validate_video_url_rejects_wrong_platform_and_non_http_urls():
    for url in (
        "file:///etc/passwd",
        "https://youtube.com.evil.example/video",
        "https://user:password@youtube.com/video",
    ):
        try:
            videodownload.validate_video_url("youtube", url)
        except videodownload.UnsupportedVideoUrl:
            continue
        raise AssertionError(f"Expected URL to be rejected: {url}")

    try:
        videodownload.validate_video_url("instagram", "https://youtube.com/video")
    except videodownload.UnsupportedVideoUrl:
        return
    raise AssertionError("Expected a URL from a different platform to be rejected")


def test_attachment_size_limit_prefers_discord_interaction_value():
    interaction = SimpleNamespace(
        filesize_limit=75 * 1024 * 1024,
        guild=SimpleNamespace(premium_tier=0),
    )

    assert videodownload.get_attachment_size_limit(interaction) == 75 * 1024 * 1024


def test_attachment_size_limit_falls_back_to_server_boost_tier():
    expected_limits = {
        0: 10,
        1: 10,
        2: 50,
        3: 100,
    }

    for tier, expected_mib in expected_limits.items():
        interaction = SimpleNamespace(guild=SimpleNamespace(premium_tier=tier))
        assert (
            videodownload.get_attachment_size_limit(interaction)
            == expected_mib * 1024 * 1024
        )


def test_attachment_size_limit_uses_base_default_outside_guild():
    interaction = SimpleNamespace(guild=None)

    assert videodownload.get_attachment_size_limit(interaction) == 10 * 1024 * 1024


def test_video_command_closes_file_and_cleans_request_directory(tmp_path, monkeypatch):
    class FakeTextChannel:
        def __init__(self):
            self.send = AsyncMock()

    monkeypatch.setattr(videodownload.discord, "TextChannel", FakeTextChannel)
    monkeypatch.setenv("BOT_DATA_DIR", str(tmp_path))
    downloaded_paths = []

    def download(*args):
        video_path = Path(args[1]) / "download.mp4"
        video_path.write_bytes(b"video")
        downloaded_paths.append(video_path)
        return str(video_path)

    monkeypatch.setattr(videodownload, "download_video_for_discord", download)
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        channel=FakeTextChannel(),
        user=SimpleNamespace(id=42, mention="<@42>"),
        filesize_limit=1024,
        edit_original_response=AsyncMock(),
    )
    cog = videodownload.VideoDownload(SimpleNamespace())
    command = type(cog).download_video

    asyncio.run(
        command.callback(
            cog,
            interaction,
            "https://youtube.com/watch?v=test",
        )
    )

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    interaction.channel.send.assert_awaited_once()
    interaction.edit_original_response.assert_awaited_once_with(
        content="Your video was sent to the channel."
    )
    sent_file = interaction.channel.send.await_args.kwargs["file"]
    assert sent_file.fp.closed
    assert downloaded_paths and not downloaded_paths[0].exists()
    assert list(cog.download_dir.iterdir()) == []


def test_video_command_send_failure_closes_file_and_cleans_request_directory(
    tmp_path, monkeypatch
):
    class FakeTextChannel:
        def __init__(self):
            self.send = AsyncMock(side_effect=RuntimeError("send failed"))

    monkeypatch.setattr(videodownload.discord, "TextChannel", FakeTextChannel)
    monkeypatch.setenv("BOT_DATA_DIR", str(tmp_path))
    downloaded_paths = []

    def download(*args):
        video_path = Path(args[1]) / "download.mp4"
        video_path.write_bytes(b"video")
        downloaded_paths.append(video_path)
        return str(video_path)

    monkeypatch.setattr(videodownload, "download_video_for_discord", download)
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        channel=FakeTextChannel(),
        user=SimpleNamespace(id=42, mention="<@42>"),
        filesize_limit=1024,
    )
    cog = videodownload.VideoDownload(SimpleNamespace())
    command = type(cog).download_video

    asyncio.run(
        command.callback(
            cog,
            interaction,
            "https://youtube.com/watch?v=test",
        )
    )

    assert interaction.followup.send.await_count == 1
    assert interaction.followup.send.await_args.kwargs["ephemeral"] is True
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    sent_file = interaction.channel.send.await_args.kwargs["file"]
    assert sent_file.fp.closed
    assert downloaded_paths and not downloaded_paths[0].exists()
    assert list(cog.download_dir.iterdir()) == []


def test_extension_setup_registers_video_cog(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_DATA_DIR", str(tmp_path))
    bot = SimpleNamespace(add_cog=AsyncMock())

    asyncio.run(videodownload.setup(bot))

    bot.add_cog.assert_awaited_once()
    assert isinstance(bot.add_cog.await_args.args[0], videodownload.VideoDownload)
