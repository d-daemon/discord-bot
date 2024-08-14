import discord
from discord.ext import commands
from discord import app_commands
import instaloader
import os
from pytube import YouTube
from yt_dlp import YoutubeDL
import logging
import json
from datetime import datetime

def unique_filename(directory):
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(directory, f"{current_time}.mp4")

def load_config():
    with open('/app/config/config.json', 'r') as config_file:
        return json.load(config_file)

def download_instagram_video(post_url, download_dir):
    L = instaloader.Instaloader(dirname_pattern=download_dir, filename_pattern="{shortcode}", save_metadata=False)
    L.download_comments = False
    shortcode = post_url.split('/')[-2]
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=download_dir)
    video_files = [f for f in os.listdir(download_dir) if f.endswith('.mp4')]
    if not video_files:
        raise FileNotFoundError("No video file found in the downloaded files!")
    video_path = os.path.join(download_dir, video_files[0])
    new_video_path = unique_filename(download_dir)
    os.rename(video_path, new_video_path)
    return new_video_path

def download_youtube_video(video_url, download_dir):
    yt = YouTube(video_url)
    stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
    output_path = stream.download(output_path=download_dir)
    new_video_path = unique_filename(download_dir)
    os.rename(output_path, new_video_path)
    return new_video_path

def download_with_ytdlp(video_url, download_dir):
    output_template = unique_filename(download_dir)
    ydl_opts = {'outtmpl': output_template, 'format': 'bestvideo+bestaudio/best'}
    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(video_url, download=True)
    return output_template

def download_tiktok_video(video_url, download_dir):
    output_template = unique_filename(download_dir)
    ydl_opts = {'outtmpl': output_template, 'format': 'best'}
    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(video_url, download=True)
    return output_template

def download_facebook_reel(video_url, download_dir):
    output_template = unique_filename(download_dir)
    ydl_opts = {'outtmpl': output_template, 'format': 'best'}
    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(video_url, download=True)
    return output_template

def download_youtube_short(video_url, download_dir):
    output_template = unique_filename(download_dir)
    ydl_opts = {'outtmpl': output_template, 'format': 'best'}
    with YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(video_url, download=True)
    return output_template

class VideoDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.download_dir = "/app/data/DL-Output"
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    async def setup(self):
        logging.info("Fetching guild IDs for VideoDownload cog.")
        guild_ids = await self.fetch_guild_ids()
        for guild_id in guild_ids:
            self.bot.tree.add_command(self.download_video, guild=discord.Object(id=guild_id))
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
        app_commands.Choice(name='Vimeo', value='vimeo'),
        app_commands.Choice(name='YouTube', value='youtube'),
        app_commands.Choice(name='YouTube Shorts', value='youtube_short')])
    async def download_video(self, interaction: discord.Interaction, platform: app_commands.Choice[str], url: str):
        await interaction.response.defer(ephemeral=True)
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

            # Check file size
            file_size = os.path.getsize(video_path)
            if file_size > 25 * 1024 * 1024:  # 25 MB limit
                os.remove(video_path)
                await interaction.followup.send("The downloaded video exceeds the 25 MB size limit.", ephemeral=True)
                return

            self.config = load_config()
            file = discord.File(video_path, filename=os.path.basename(video_path))
            await interaction.channel.send("Here is your downloaded video:", file=file)
            os.remove(video_path)

            # Remove all other files
            for f in os.listdir(self.download_dir):
                file_path = os.path.join(self.download_dir, f)
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
