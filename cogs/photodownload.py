import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import discord
from discord import app_commands
from discord.ext import commands
from cogs.videodownload import build_gallery_dl_command
from utils.helpers import do_sleep


def unique_filename(directory, base_name, index):
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(directory, f"{base_name}_{current_time}_{index}.jpg")

def load_config():
    # TODO: Avoid hardcoding the config path; use `BOT_CONFIG_PATH` env
    # variable or the project's `load_config()` helper for consistency.
    with open('/app/config/config.json', 'r') as config_file:
        return json.load(config_file)

def download_instagram_photos(post_url, download_dir):
    with tempfile.TemporaryDirectory(dir=download_dir) as work_dir:
        do_sleep()
        download_photos_via_gallery_dl(post_url, work_dir)

        photo_files = sorted(
            path for path in Path(work_dir).rglob("*")
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        if not photo_files:
            raise FileNotFoundError("No photo file found in the downloaded files!")

        downloaded_files = []
        for index, photo_file in enumerate(photo_files, 1):
            new_filename = os.path.join(download_dir, f"{uuid4().hex}_{index}{photo_file.suffix.lower()}")
            os.replace(photo_file, new_filename)
            downloaded_files.append(new_filename)
        return downloaded_files


def download_photos_via_gallery_dl(post_url, download_dir):
    if not shutil.which("gallery-dl"):
        raise RuntimeError("gallery-dl is not installed or not available on PATH.")

    command, cookie_file = build_gallery_dl_command(post_url, download_dir, is_instagram=True)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
        if completed.returncode != 0:
            logging.error("gallery-dl failed: %s", (completed.stderr or completed.stdout).strip())
            raise RuntimeError(
                "gallery-dl could not download the photos. Check the bot logs and Instagram session."
            )
    finally:
        if cookie_file and os.path.exists(cookie_file):
            os.remove(cookie_file)

class PhotoDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.download_dir = "/app/data/images"
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    async def setup(self):
        logging.info("Fetching guild IDs for PhotoDownload cog.")
        guild_ids = await self.fetch_guild_ids()
        # for guild_id in guild_ids:
        #     self.bot.tree.add_command(self.download_photo, guild=discord.Object(id=guild_id))
        logging.info("PhotoDownload cog commands added for guilds.")

    async def fetch_guild_ids(self):
        async with self.bot.db_pool.acquire() as connection:
            records = await connection.fetch("SELECT guild_id FROM guilds")
            return [record['guild_id'] for record in records]

    @app_commands.command(name="ig_photo", description="Download a photo from Instagram")
    @app_commands.describe(url="URL of the Instagram post")
    async def download_photo(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)
        
        logging.info(f"{interaction.user} requested to download a photo from Instagram with URL: {url}")
        
        try:
            photo_paths = await asyncio.to_thread(download_instagram_photos, url, self.download_dir)
            
            if len(photo_paths) == 1:
                selected_photos = [photo_paths[0]]
            else:
                options = [
                    discord.SelectOption(label=f"Image {i+1}", value=str(i))
                    for i in range(len(photo_paths))
                ]

                class MultiPhotoSelect(discord.ui.Select):
                    def __init__(self, download_dir):
                        self.download_dir = download_dir
                        super().__init__(placeholder="Choose images to download", min_values=1, max_values=len(options), options=options)

                    async def callback(self, select_interaction: discord.Interaction):
                        selected_indexes = [int(i) for i in self.values]
                        selected_photos = [photo_paths[i] for i in selected_indexes]

                        files = []
                        for photo in selected_photos:
                            files.append(discord.File(photo, filename=os.path.basename(photo)))

                        await select_interaction.channel.send(f"{interaction.user.mention} Here are your selected photos:", files=files)

                        # Dismiss the interaction
                        await select_interaction.response.defer()

                        # Delete the original message with the dropdown
                        await interaction.delete_original_response()

                        # Clean up after sending
                        for photo in photo_paths:
                            os.remove(photo)

                view = discord.ui.View(timeout=30)  # Set the timeout to 30 seconds
                view.add_item(MultiPhotoSelect(self.download_dir))

                async def on_timeout():
                    # If timeout occurs, send all photos
                    files = [discord.File(photo, filename=os.path.basename(photo)) for photo in photo_paths]
                    await interaction.channel.send(f"{interaction.user.mention} You did not respond in time, so here are all the photos:", files=files)

                    # Clean up after sending
                    for photo in photo_paths:
                        os.remove(photo)

                    # Delete the original message with the dropdown
                    await interaction.delete_original_response()

                view.on_timeout = on_timeout
                await interaction.followup.send("Please select the photos you want to download:", view=view)
                return

            # If there's only one image, send it directly
            for selected_photo in selected_photos:
                file = discord.File(selected_photo, filename=os.path.basename(selected_photo))
                await interaction.channel.send(f"{interaction.user.mention} Here is your downloaded photo:", file=file)

            # Clean up download directory
            for photo in photo_paths:
                os.remove(photo)

        except Exception as e:
            logging.exception("Failed to download or send the photo")
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

async def setup(bot):
    cog = PhotoDownload(bot)
    await cog.setup()
    await bot.add_cog(cog)