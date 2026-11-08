import asyncio
import logging
import os
import shutil
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

from cogs.videodownload import (
    build_gallery_dl_command,
    build_ytdlp_options,
    resolve_video_platform,
    write_instagram_cookie_file,
)
from utils.helpers import do_sleep

logger = logging.getLogger(__name__)


def download_instagram_photos(post_url, download_dir):
    with tempfile.TemporaryDirectory(dir=download_dir) as work_dir:
        do_sleep()
        download_photos_via_gallery_dl(post_url, work_dir)

        photo_files = sorted(
            path
            for path in Path(work_dir).rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        if not photo_files:
            raise FileNotFoundError("No photo file found in the downloaded files!")

        downloaded_files = []
        for index, photo_file in enumerate(photo_files, 1):
            new_filename = os.path.join(
                download_dir, f"{uuid4().hex}_{index}{photo_file.suffix.lower()}"
            )
            os.replace(photo_file, new_filename)
            downloaded_files.append(new_filename)
        return downloaded_files


def download_video_cover(video_url, download_dir):
    os.makedirs(download_dir, exist_ok=True)
    platform = resolve_video_platform(video_url)
    cookie_file = None
    try:
        do_sleep()
        if platform == "instagram":
            cookies = os.environ.get("INSTAGRAM_COOKIES", "").strip()
            if cookies:
                cookie_file = write_instagram_cookie_file(cookies)

        output_template = str(Path(download_dir) / "%(id)s.%(ext)s")
        options = build_ytdlp_options(
            output_template,
            skip_download=True,
            writethumbnail=True,
        )
        if cookie_file:
            options["cookiefile"] = cookie_file

        with YoutubeDL(cast(Any, options)) as ydl:
            ydl.extract_info(video_url, download=True)

        cover_paths = sorted(
            path
            for path in Path(download_dir).rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        if not cover_paths:
            raise FileNotFoundError("No video cover thumbnail was found.")
        return [str(cover_paths[0])]
    finally:
        if cookie_file and os.path.exists(cookie_file):
            os.remove(cookie_file)


def is_instagram_video_url(post_url):
    path_segments = {segment.lower() for segment in urlsplit(post_url).path.split("/")}
    return bool(path_segments & {"reel", "reels", "tv"})


def download_media_assets(media_url, download_dir):
    platform = resolve_video_platform(media_url)
    if platform != "instagram" or is_instagram_video_url(media_url):
        return download_video_cover(media_url, download_dir)

    try:
        return download_instagram_photos(media_url, download_dir)
    except (FileNotFoundError, RuntimeError) as photo_error:
        logger.info("No still images found; trying the video's cover")
        try:
            return download_video_cover(media_url, download_dir)
        except Exception as cover_error:
            raise cover_error from photo_error


def download_photos_via_gallery_dl(post_url, download_dir):
    gallery_dl = shutil.which("gallery-dl")
    if not gallery_dl:
        raise RuntimeError("gallery-dl is not installed or not available on PATH.")

    command, cookie_file = build_gallery_dl_command(
        post_url, download_dir, is_instagram=True
    )
    command[0] = gallery_dl
    command[-1:-1] = ["--filename", "{num:02}.{extension}"]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=600, check=False
        )
        if completed.returncode != 0:
            logger.error(
                "gallery-dl failed: %s", (completed.stderr or completed.stdout).strip()
            )
            raise RuntimeError(
                "gallery-dl could not download the photos. Check the bot logs and Instagram session."
            )
    finally:
        if cookie_file and os.path.exists(cookie_file):
            os.remove(cookie_file)


async def send_photos(channel, user, photo_paths, message):
    for start in range(0, len(photo_paths), 10):
        batch = photo_paths[start : start + 10]
        files = [discord.File(path, filename=os.path.basename(path)) for path in batch]
        try:
            content = message if start == 0 else f"{user.mention} (continued)"
            await channel.send(content, files=files)
        finally:
            for file in files:
                file.close()


class PhotoSelectionView(discord.ui.View):
    def __init__(self, interaction, photo_paths, request_dir):
        super().__init__(timeout=30)
        self.interaction = interaction
        self.photo_paths = photo_paths
        self.request_dir = request_dir
        self.prompt_message: discord.WebhookMessage | None = None
        self.cleaned = False
        self.add_item(PhotoSelection(self))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message(
                "This image selection is not for you.", ephemeral=True
            )
            return False
        return True

    async def cleanup(self):
        if self.cleaned:
            return
        self.cleaned = True
        self.stop()
        await asyncio.to_thread(shutil.rmtree, self.request_dir, True)

    async def on_timeout(self):
        try:
            await send_photos(
                self.interaction.channel,
                self.interaction.user,
                self.photo_paths,
                f"{self.interaction.user.mention} No images were selected; here are all the photos:",
            )
        except Exception:
            logger.exception("Failed to send photos after selection timed out")
        finally:
            await self.cleanup()
            if self.prompt_message is not None:
                try:
                    await self.prompt_message.delete()
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    logger.exception("Failed to delete the expired photo selection")


class PhotoSelection(discord.ui.Select):
    def __init__(self, selection_view):
        self.selection_view = selection_view
        photo_paths = selection_view.photo_paths
        options = [
            discord.SelectOption(label=f"Image {index + 1}", value=str(index))
            for index in range(min(len(photo_paths), 20))
        ]
        super().__init__(
            placeholder="Choose images to download",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        selected_photos = [
            self.selection_view.photo_paths[int(index)] for index in self.values
        ]
        try:
            await send_photos(
                self.selection_view.interaction.channel,
                self.selection_view.interaction.user,
                selected_photos,
                f"{self.selection_view.interaction.user.mention} Here are your selected photos:",
            )
            await interaction.edit_original_response(
                content="Your photos were sent to the channel."
            )
        except Exception:
            logger.exception("Failed to send selected photos")
            try:
                await interaction.followup.send(
                    "The selected photos could not be sent.", ephemeral=True
                )
            except discord.HTTPException:
                logger.exception("Failed to report the photo send error")
        finally:
            await self.selection_view.cleanup()
            if interaction.message is not None:
                try:
                    await interaction.message.delete()
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    logger.exception("Failed to delete the photo selection")


class PhotoDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.download_dir = Path(os.environ.get("BOT_DATA_DIR", "/app/data")) / "images"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    @app_commands.command(
        name="ig_photo", description="Download Instagram photos or a video cover"
    )
    @app_commands.describe(url="Instagram photo post or video URL")
    async def download_photo(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)
        logger.info(
            "User %s requested a photo or video cover download", interaction.user.id
        )
        request_dir = None
        try:
            request_dir = Path(
                tempfile.mkdtemp(prefix="request-", dir=self.download_dir)
            )
            photo_paths = await asyncio.to_thread(
                download_media_assets, url, str(request_dir)
            )

            if len(photo_paths) > 1:
                view = PhotoSelectionView(interaction, photo_paths, request_dir)
                prompt = (
                    "Choose image(s) to send."
                )
                view.prompt_message = await interaction.followup.send(
                    prompt, view=view, ephemeral=True, wait=True
                )
                request_dir = None
                return

            await send_photos(
                interaction.channel,
                interaction.user,
                photo_paths,
                f"{interaction.user.mention} Here is your downloaded photo:",
            )
            await interaction.edit_original_response(
                content="Your photos were sent to the channel."
            )
        except ValueError:
            await interaction.followup.send(
                "Use a valid Instagram photo or video URL from a public post.", ephemeral=True
            )
        except Exception:
            logger.exception("Failed to download or send Instagram photo(s)")
            await interaction.followup.send(
                "The photos could not be downloaded or sent.",
                ephemeral=True,
            )
        finally:
            if request_dir is not None:
                await asyncio.to_thread(shutil.rmtree, request_dir, True)


async def setup(bot):
    await bot.add_cog(PhotoDownload(bot))
