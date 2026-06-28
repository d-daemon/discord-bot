import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs import videodownload


def test_build_gallery_dl_command_uses_explicit_download_directory(tmp_path):
    command, cookie_file = videodownload.build_gallery_dl_command("https://example.com/video", tmp_path)

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
    assert "# Netscape HTTP Cookie File" in Path(cookie_file).read_text(encoding="utf-8")
    assert "sessionid" in Path(cookie_file).read_text(encoding="utf-8")


def test_build_ffmpeg_command_uses_h264_settings(tmp_path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"

    command = videodownload.build_ffmpeg_command(input_path, output_path)

    assert command[0] == "ffmpeg"
    assert str(input_path) in command
    assert str(output_path) in command
    assert "-c:v" in command
    assert "libx264" in command
