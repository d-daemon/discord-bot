import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import do_sleep
from yt_dlp import YoutubeDL


def unique_directory(directory):
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(directory, current_time)
    os.makedirs(path, exist_ok=True)
    return path


def unique_filename(directory, source_path=None):
    # TODO: current implementation uses second-resolution timestamps which
    # can collide if multiple files are created in the same second. Consider
    # including microseconds ("%f") or using a UUID to guarantee uniqueness.
    extension = Path(source_path).suffix if source_path else ".mp4"
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(directory, f"{current_time}{extension}")


def load_config():
    config_path = os.environ.get("BOT_CONFIG_PATH", "/app/config/config.json")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


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

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write("# Netscape HTTP Cookie File\n")
        for name, value in cookie_pairs:
            handle.write(f".instagram.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
            handle.write(f"www.instagram.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
        return handle.name


DISCORD_MAX_ATTACHMENT_SIZE = 6 * 1024 * 1024


def build_ffmpeg_command(input_path, output_path):
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        "scale=854:trunc(ow/a/2)*2,fps=30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-profile:v",
        "main",
        "-level",
        "3.1",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def compress_video_for_discord(video_path):
    # TODO: `subprocess.run` is blocking. Run ffmpeg in a thread via
    # `asyncio.to_thread()` or use `asyncio.create_subprocess_exec` when
    # called from async code to avoid blocking the event loop.
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not available on PATH.")

    output_path = str(Path(video_path).with_suffix(".compressed.mp4"))
    completed = subprocess.run(
        build_ffmpeg_command(video_path, output_path),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(stderr or "Failed to compress the video for Discord.")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        os.remove(video_path)
        return output_path

    raise RuntimeError("Compressed video was not created.")


def find_downloaded_media(download_dir):
    download_path = Path(download_dir)
    if not download_path.exists():
        return []

    video_extensions = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}
    video_files = [
        path for path in download_path.rglob("*") if path.is_file() and path.suffix.lower() in video_extensions
    ]
    if video_files:
        return sorted(video_files)
    return sorted(path for path in download_path.rglob("*") if path.is_file())


def download_via_gallery_dl(video_url, download_dir, is_instagram=False):
    # TODO: `do_sleep()` blocks the thread. Either make it async or call
    # this function inside `asyncio.to_thread()` so the bot's event loop
    # is not blocked by sleeps between downloads.
    do_sleep()
    os.makedirs(download_dir, exist_ok=True)
    target_dir = unique_directory(download_dir)

    command, cookie_file = build_gallery_dl_command(video_url, target_dir, is_instagram=is_instagram)
    gallery_dl = shutil.which("gallery-dl")
    # TODO: we detect `gallery-dl` with `shutil.which()` but we don't use
    # the absolute path when building the command. Consider replacing
    # the command[0] with `gallery_dl` to avoid PATH inconsistencies.
    if not gallery_dl:
        raise RuntimeError("gallery-dl is not installed or not available on PATH.")

    try:
        # TODO: `subprocess.run` is blocking; run in a thread to avoid
        # blocking the async event loop (e.g., `await asyncio.to_thread(subprocess.run, ...)`).
        completed = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(stderr or "gallery-dl failed to download the media.")

        downloaded_media = find_downloaded_media(target_dir)
        if not downloaded_media:
            raise FileNotFoundError("No video file found in the downloaded files!")

        media_path = downloaded_media[0]
        final_path = unique_filename(download_dir, media_path)
        os.replace(media_path, final_path)

        for path in Path(target_dir).iterdir():
            if path.is_file():
                path.unlink()
        try:
            os.rmdir(target_dir)
        except OSError:
            pass

        return final_path
    finally:
        if cookie_file and os.path.exists(cookie_file):
            os.remove(cookie_file)

    # NOTE: the code below was duplicated earlier; keep cleanup centralized
    # above in the try/finally and return the final path there. Consider
    # refactoring to ensure a single return/cleanup path.


def download_instagram_video(post_url, download_dir):
    return download_via_gallery_dl(post_url, download_dir, is_instagram=True)


def download_youtube_video(video_url, download_dir):
    return download_with_ytdlp(video_url, download_dir)


def download_tiktok_video(video_url, download_dir):
    # TODO: blocking `do_sleep()` call — see utils.helpers note.
    do_sleep()
    os.makedirs(download_dir, exist_ok=True)
    output_path = unique_filename(download_dir)
    ydl_opts = {
        "outtmpl": output_path,
        "format": "bestvideo+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "socket_timeout": 30,
        "retries": 10,
        "extractor_retries": 10,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(video_url, download=True)

    if not os.path.exists(output_path) and os.path.exists(output_path + ".mp4"):
        output_path += ".mp4"

    if not os.path.exists(output_path):
        raise FileNotFoundError("No video file found in the downloaded files!")

    return output_path


def download_facebook_reel(video_url, download_dir):
    return download_with_ytdlp(video_url, download_dir)


def download_youtube_short(video_url, download_dir):
    return download_with_ytdlp(video_url, download_dir)


def download_with_ytdlp(video_url, download_dir):
    # TODO: yt_dlp `extract_info` is blocking (downloads and merges). Run
    # the extractor in a thread (e.g., `await asyncio.to_thread`) to avoid
    # blocking the event loop when invoked from async command handlers.
    do_sleep()
    os.makedirs(download_dir, exist_ok=True)
    output_path = unique_filename(download_dir)
    ydl_opts = {
        "outtmpl": output_path,
        "format": "bestvideo+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(video_url, download=True)

    if not os.path.exists(output_path) and os.path.exists(output_path + ".mp4"):
        output_path += ".mp4"

    if not os.path.exists(output_path):
        raise FileNotFoundError("No video file found in the downloaded files!")

    return output_path


class VideoDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.download_dir = os.environ.get("VIDEO_DOWNLOAD_DIR", "/app/data/DL-Output")
        os.makedirs(self.download_dir, exist_ok=True)

    async def setup(self):
        logging.info("Fetching guild IDs for VideoDownload cog.")
        guild_ids = await self.fetch_guild_ids()
        # for guild_id in guild_ids:
        #     self.bot.tree.add_command(self.download_video, guild=discord.Object(id=guild_id))
        logging.info("VideoDownload cog commands added for guilds.")

    async def fetch_guild_ids(self):
        async with self.bot.db_pool.acquire() as connection:
            records = await connection.fetch("SELECT guild_id FROM guilds")
            return [record['guild_id'] for record in records]

    @app_commands.command(name="video_dl", description="Download a video from various platforms")
    @app_commands.describe(platform="Platform to download video from", url="URL of the video")
    @app_commands.choices(platform=[
        app_commands.Choice(name='Facebook', value='facebook'),
        app_commands.Choice(name='Facebook Reels', value='facebook_reels'),
        app_commands.Choice(name='Instagram', value='instagram'),
        app_commands.Choice(name='TikTok', value='tiktok'),
        app_commands.Choice(name='Twitter', value='twitter'),
        app_commands.Choice(name='YouTube', value='youtube'),
        app_commands.Choice(name='YouTube Shorts', value='youtube_short')])
    async def download_video(self, interaction: discord.Interaction, platform: app_commands.Choice[str], url: str):
        await interaction.response.defer(ephemeral=True)
        logging.info(f"{interaction.user} requested to download a video from {platform.name} with URL: {url}")
        try:
            if platform.value == 'instagram':
                video_path = download_instagram_video(url, self.download_dir)
            elif platform.value == 'youtube':
                video_path = download_youtube_video(url, self.download_dir)
            elif platform.value == 'tiktok':
                video_path = download_tiktok_video(url, self.download_dir)
            elif platform.value == 'facebook_reels':
                video_path = download_facebook_reel(url, self.download_dir)
            elif platform.value == 'youtube_short':
                video_path = download_youtube_short(url, self.download_dir)
            else:
                video_path = download_with_ytdlp(url, self.download_dir)

            file_size = os.path.getsize(video_path)
            if file_size > DISCORD_MAX_ATTACHMENT_SIZE:
                try:
                    compressed_path = compress_video_for_discord(video_path)
                    video_path = compressed_path
                    file_size = os.path.getsize(video_path)
                except Exception as compression_error:
                    os.remove(video_path)
                    await interaction.followup.send(
                        f"The downloaded video is too large to send to Discord and compression failed: {compression_error}",
                        ephemeral=True,
                    )
                    return

            if file_size > DISCORD_MAX_ATTACHMENT_SIZE:
                os.remove(video_path)
                await interaction.followup.send(
                    f"The downloaded video is still too large to send to Discord ({file_size / (1024 * 1024):.1f} MB). Please try a smaller clip.",
                    ephemeral=True,
                )
                return

            self.config = load_config()
            file = discord.File(video_path, filename=os.path.basename(video_path))
            await interaction.channel.send(f"{interaction.user.mention} Here is your downloaded video:", file=file)
            os.remove(video_path)

            for entry in os.listdir(self.download_dir):
                file_path = os.path.join(self.download_dir, entry)
                if os.path.isfile(file_path):
                    os.remove(file_path)

            await interaction.followup.send(f"The video has been sent to the '{interaction.channel.name}' channel.", ephemeral=True)
        except Exception as e:
            logging.exception("Failed to download or send the video")
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)


async def setup(bot):
    cog = VideoDownload(bot)
    await cog.setup()
    await bot.add_cog(cog)
