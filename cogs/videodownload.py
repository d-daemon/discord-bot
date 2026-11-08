import asyncio
import ipaddress
import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import uuid4

import discord
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL

from utils.helpers import (
    do_sleep,
    edit_ephemeral_response,
    send_ephemeral,
)

logger = logging.getLogger(__name__)


def unique_directory(directory):
    path = os.path.join(directory, uuid4().hex)
    os.makedirs(path, exist_ok=True)
    return path


def unique_filename(directory, source_path=None):
    extension = Path(source_path).suffix if source_path else ".mp4"
    return os.path.join(directory, f"{uuid4().hex}{extension}")


def build_gallery_dl_command(url, download_dir, is_instagram=False):
    command = ["gallery-dl", "-d", str(download_dir)]
    cookie_file = None

    if is_instagram:
        cookies = os.environ.get("INSTAGRAM_COOKIES", "").strip()
        if cookies:
            cookie_file = write_instagram_cookie_file(cookies)
            if cookie_file:
                command.extend(["--cookies", cookie_file])

    command.append(url)
    return command, cookie_file


def write_instagram_cookie_file(cookie_value):
    if not cookie_value:
        return None

    cookie_pairs = []
    if "=" in cookie_value:
        for part in cookie_value.replace("&", ";").split(";"):
            if "=" in part:
                name, value = part.split("=", 1)
                cookie_pairs.append((name.strip(), value.strip()))

    if not cookie_pairs:
        cookie_pairs = [("sessionid", cookie_value)]

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as handle:
        handle.write("# Netscape HTTP Cookie File\n")
        for name, value in cookie_pairs:
            handle.write(f".instagram.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
        return handle.name


def build_ytdlp_options(output_path, **overrides):
    options = {
        "outtmpl": output_path,
        "format": "bestvideo+bestaudio/best",
        "format_sort": ["vcodec:h264", "acodec:aac"],
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }
    options.update(overrides)
    return options


MIB = 1024 * 1024
DEFAULT_ATTACHMENT_SIZE = 10 * MIB
SERVER_ATTACHMENT_SIZES = {
    0: 10 * MIB,
    1: 10 * MIB,
    2: 50 * MIB,
    3: 100 * MIB,
}


def get_attachment_size_limit(interaction: discord.Interaction) -> int:
    """Return Discord's live upload limit, with a tier fallback for older clients."""
    interaction_limit = getattr(interaction, "filesize_limit", None)
    if isinstance(interaction_limit, int) and interaction_limit > 0:
        return interaction_limit

    guild = getattr(interaction, "guild", None)
    premium_tier = getattr(guild, "premium_tier", 0)
    return SERVER_ATTACHMENT_SIZES.get(premium_tier, DEFAULT_ATTACHMENT_SIZE)


COMPRESSION_PROFILES = (
    (28, 854, "96k"),
    (34, 640, "64k"),
    (40, 480, "48k"),
)


class VideoCompressionError(RuntimeError):
    pass


def build_ffmpeg_command(
    input_path, output_path, *, crf=28, width=854, audio_bitrate="96k"
):
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        f"scale={width}:trunc(ow/a/2)*2,fps=30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(crf),
        "-profile:v",
        "main",
        "-level",
        "3.1",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        audio_bitrate,
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def compress_video_for_discord(video_path, max_size):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not installed or not available on PATH.")

    if max_size <= 0:
        raise ValueError("Maximum attachment size must be positive")

    source_path = Path(video_path)
    last_size = None
    for attempt, (crf, width, audio_bitrate) in enumerate(
        COMPRESSION_PROFILES, start=1
    ):
        if attempt == 1:
            output_path = source_path.with_suffix(".compressed.mp4")
        else:
            output_path = source_path.with_name(
                f"{source_path.stem}.compressed-{attempt}.mp4"
            )

        command = build_ffmpeg_command(
            source_path,
            output_path,
            crf=crf,
            width=width,
            audio_bitrate=audio_bitrate,
        )
        command[0] = ffmpeg
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            output_path.unlink(missing_ok=True)
            raise VideoCompressionError(
                "ffmpeg failed while compressing the video"
            ) from error

        if completed.returncode != 0:
            output_path.unlink(missing_ok=True)
            details = (completed.stderr or completed.stdout).strip()
            logger.error("ffmpeg compression failed: %s", details)
            raise VideoCompressionError("ffmpeg failed while compressing the video")

        if not output_path.is_file() or output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
            raise VideoCompressionError("ffmpeg did not create a compressed video")

        last_size = output_path.stat().st_size
        if last_size <= max_size:
            try:
                source_path.unlink()
            except OSError:
                logger.warning(
                    "Could not remove the uncompressed video %s", source_path
                )
            return str(output_path)

        logger.info(
            "Compressed video attempt %s is %s bytes; trying a smaller profile",
            attempt,
            last_size,
        )
        output_path.unlink()

    if last_size is None:
        raise VideoCompressionError("No compression profiles are configured")

    raise VideoTooLargeError(
        f"Could not compress the video below the {max_size / MIB:.1f} MiB attachment limit "
        f"(smallest attempt was {last_size / MIB:.1f} MiB)."
    )


def find_downloaded_media(download_dir):
    download_path = Path(download_dir)
    if not download_path.exists():
        return []

    video_extensions = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}
    video_files = [
        path
        for path in download_path.rglob("*")
        if path.is_file() and path.suffix.lower() in video_extensions
    ]
    return sorted(video_files)


def download_via_gallery_dl(video_url, download_dir, is_instagram=False):
    gallery_dl = shutil.which("gallery-dl")
    if not gallery_dl:
        raise RuntimeError("gallery-dl is not installed or not available on PATH.")

    do_sleep()
    os.makedirs(download_dir, exist_ok=True)
    target_dir = unique_directory(download_dir)
    cookie_file = None
    try:
        command, cookie_file = build_gallery_dl_command(
            video_url, target_dir, is_instagram=is_instagram
        )
        command[0] = gallery_dl
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=600, check=False
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(stderr or "gallery-dl failed to download the media.")

        downloaded_media = find_downloaded_media(target_dir)
        if not downloaded_media:
            raise FileNotFoundError("No video file found in the downloaded files!")

        media_path = downloaded_media[0]
        final_path = unique_filename(download_dir, media_path)
        os.replace(media_path, final_path)
        return final_path
    finally:
        if cookie_file and os.path.exists(cookie_file):
            os.remove(cookie_file)
        shutil.rmtree(target_dir, ignore_errors=True)


def download_instagram_video(post_url, download_dir):
    return download_via_gallery_dl(post_url, download_dir, is_instagram=True)


def download_tiktok_video(video_url, download_dir):
    return download_with_ytdlp(
        video_url,
        download_dir,
        socket_timeout=30,
        retries=10,
        extractor_retries=10,
        http_headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    )


def download_with_ytdlp(video_url, download_dir, **option_overrides):
    do_sleep()
    os.makedirs(download_dir, exist_ok=True)
    output_path = unique_filename(download_dir)
    ydl_opts = build_ytdlp_options(output_path, **option_overrides)
    with YoutubeDL(cast(Any, ydl_opts)) as ydl:
        ydl.extract_info(video_url, download=True)

    if not os.path.exists(output_path) and os.path.exists(output_path + ".mp4"):
        output_path += ".mp4"

    if not os.path.exists(output_path):
        raise FileNotFoundError("No video file found in the downloaded files!")

    return output_path


def probe_media(file_path: str) -> dict:
    """Run ffprobe on the given file and return parsed JSON streams info.

    Note: This calls the ffprobe binary synchronously and should be run
    from a thread (e.g. `await asyncio.to_thread(probe_media, path)`).
    """
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is not installed or available on PATH")

    cmd = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        str(file_path),
    ]
    completed = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(
            (completed.stderr or completed.stdout).strip() or "ffprobe failed"
        )

    return json.loads(completed.stdout)


def needs_reencode(probe_info: dict) -> bool:
    """Return True if the file should be re-encoded to H264/AAC/yuv420p.

    Criteria:
      - video codec is not h264
      - video pixel format is not yuv420p
      - audio codec is not aac (if an audio stream exists)
    """
    streams = probe_info.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream:
        return True

    vcodec = video_stream.get("codec_name", "").lower()
    pix_fmt = video_stream.get("pix_fmt", "").lower()

    if vcodec not in ("h264", "avc1"):
        return True

    if pix_fmt and "yuv420" not in pix_fmt:
        return True

    if audio_stream:
        acodec = audio_stream.get("codec_name", "").lower()
        if acodec not in ("aac", "mp4a"):
            return True

    return False


def reencode_to_h264(input_path: str, output_path: str) -> str:
    """Re-encode the input to H.264/AAC using ffmpeg and return output path.

    This is a synchronous operation and should be executed in a thread.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not installed or not available on PATH.")

    cmd = build_ffmpeg_command(input_path, output_path)
    cmd[0] = ffmpeg
    completed = subprocess.run(
        cmd, capture_output=True, text=True, timeout=1200, check=False
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(stderr or "ffmpeg re-encode failed")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        try:
            os.remove(input_path)
        except OSError:
            pass
        return output_path

    raise RuntimeError("Re-encoded file not created")


VIDEO_HOSTS = {
    "facebook": ("facebook.com", "fb.watch"),
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
    "twitter": ("twitter.com", "x.com"),
    "youtube": ("youtube.com", "youtu.be"),
}


class UnsupportedVideoUrl(ValueError):
    pass


class VideoTooLargeError(Exception):
    pass


def resolve_video_platform(video_url: str) -> str:
    """Resolve a known downloader, otherwise allow yt-dlp's generic extractor for public hosts."""
    try:
        parsed = urlsplit(video_url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        raise UnsupportedVideoUrl from error

    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise UnsupportedVideoUrl("Use a valid public HTTP or HTTPS video URL.")

    for platform, allowed_hosts in VIDEO_HOSTS.items():
        if any(
            hostname == host or hostname.endswith(f".{host}") for host in allowed_hosts
        ):
            return platform

    if (
        hostname == "localhost"
        or hostname.endswith((".localhost", ".local"))
        or "." not in hostname
    ):
        raise UnsupportedVideoUrl("Generic downloads require a public hostname.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            resolved_addresses = {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(
                    hostname, port, type=socket.SOCK_STREAM
                )
            }
        except (OSError, ValueError) as error:
            raise UnsupportedVideoUrl(
                "The video URL host could not be resolved safely."
            ) from error
        if not resolved_addresses or any(
            not address.is_global for address in resolved_addresses
        ):
            raise UnsupportedVideoUrl("Generic downloads require a public hostname.")
    else:
        if not address.is_global:
            raise UnsupportedVideoUrl(
                "Generic downloads cannot target private or local IP addresses."
            )

    return "generic"


def validate_video_url(platform: str, video_url: str) -> None:
    if resolve_video_platform(video_url) != platform:
        raise UnsupportedVideoUrl("Use a valid URL from the selected video platform.")


def download_video_for_discord(video_url: str, download_dir: str, max_size: int) -> str:
    platform = resolve_video_platform(video_url)
    downloaders = {
        "facebook": download_with_ytdlp,
        "instagram": download_instagram_video,
        "tiktok": download_tiktok_video,
        "twitter": download_with_ytdlp,
        "youtube": download_with_ytdlp,
        "generic": download_with_ytdlp,
    }
    video_path = downloaders[platform](video_url, download_dir)

    try:
        if needs_reencode(probe_media(video_path)):
            output_path = str(Path(video_path).with_suffix(".reencoded.mp4"))
            video_path = reencode_to_h264(video_path, output_path)
    except Exception:
        logger.exception(
            "Media compatibility check failed; using the original download"
        )

    if os.path.getsize(video_path) > max_size:
        video_path = compress_video_for_discord(video_path, max_size)

    file_size = os.path.getsize(video_path)
    if file_size > max_size:
        raise VideoTooLargeError(
            f"The downloaded video is still too large to send ({file_size / (1024 * 1024):.1f} MB)."
        )
    return video_path


class VideoDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.download_dir = Path(os.environ.get("BOT_DATA_DIR", "/app/data")) / "videos"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    @app_commands.command(
        name="video_dl", description="Download a video from various platforms"
    )
    @app_commands.describe(url="URL of the video to download")
    async def download_video(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await send_ephemeral(
                interaction, "Use this command in a server text channel."
            )
            return

        try:
            hostname = urlsplit(url).hostname or "unknown-host"
        except ValueError:
            hostname = "invalid-url"
        logger.info(
            "User %s requested a video download from %s: %s",
            interaction.user.id,
            hostname,
            url,
        )
        request_dir = None
        try:
            request_dir = Path(
                tempfile.mkdtemp(prefix="request-", dir=self.download_dir)
            )
            max_size = get_attachment_size_limit(interaction)
            download_task = asyncio.create_task(
                asyncio.to_thread(
                    download_video_for_discord,
                    url,
                    str(request_dir),
                    max_size,
                )
            )
            try:
                video_path = await asyncio.shield(download_task)
            except asyncio.CancelledError:
                try:
                    await download_task
                except Exception:
                    logger.exception(
                        "Video download failed after its interaction was cancelled"
                    )
                raise

            file = discord.File(video_path, filename=os.path.basename(video_path))
            try:
                await channel.send(
                    f"{interaction.user.mention} Here is your downloaded video.",
                    file=file,
                )
                await edit_ephemeral_response(
                    interaction, "Your video was sent to the channel."
                )
            finally:
                file.close()
        except UnsupportedVideoUrl:
            await send_ephemeral(
                interaction, "Use a valid public URL from a supported video source."
            )
        except VideoTooLargeError as error:
            await send_ephemeral(interaction, str(error))
        except Exception:
            logger.exception("Failed to download or send a video")
            await send_ephemeral(
                interaction, "The video could not be downloaded or sent."
            )
        finally:
            if request_dir is not None:
                await asyncio.to_thread(shutil.rmtree, request_dir, True)


async def setup(bot):
    await bot.add_cog(VideoDownload(bot))
