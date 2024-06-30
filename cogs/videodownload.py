import discord
from discord.ext import commands
from discord import app_commands
import instaloader
import os
from pytube import YouTube
from yt_dlp import YoutubeDL
import logging
import json

def unique_filename(directory, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    unique_name = filename
    while os.path.exists(os.path.join(directory, unique_name)):
        unique_name = f"{base}_{counter}{ext}"
        counter += 1
    return unique_name

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
    return video_path

def download_youtube_video(video_url, download_dir):
    yt = YouTube(video_url)
    stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
    output_path = stream.download(output_path=download_dir)
    return output_path

def download_with_ytdlp(video_url, download_dir):
    ydl_opts = {'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'), 'format': 'bestvideo+bestaudio/best'}
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(video_url, download=True)
        video_filename = ydl.prepare_filename(info_dict)
    return video_filename

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

    @app_commands.command(name="video _download", description="Download a video from various platforms")
    @app_commands.describe(platform="Platform to download video from", url="URL of the video")
    @app_commands.choices(platform=[
        app_commands.Choice(name='Instagram', value='instagram'),
        app_commands.Choice(name='YouTube', value='youtube'),
        app_commands.Choice(name='Twitter', value='twitter'),
        app_commands.Choice(name='Facebook', value='facebook'),
        app_commands.Choice(name='Vimeo', value='vimeo')])
    async def download_video(self, interaction: discord.Interaction, platform: app_commands.Choice[str], url: str):
        await interaction.response.defer(ephemeral=True)
        try:
            if platform.value == 'instagram':
                video_path = download_instagram_video(url, self.download_dir)
            elif platform.value == 'youtube':
                video_path = download_youtube_video(url, self.download_dir)
            else:
                video_path = download_with_ytdlp(url, self.download_dir)
            
            self.config = load_config()
            channel_name = self.config.get('videodownload_channel', 'general')
            channel = discord.utils.get(interaction.guild.text_channels, name=channel_name)
            file = discord.File(video_path, filename=os.path.basename(video_path))
            if channel:
                await channel.send("Here is your downloaded video:", file=file)
            os.remove(video_path)
            await interaction.followup.send(f"The video has been sent to the '{channel_name}' channel.", ephemeral=True)
        except Exception as e:
            logging.exception("Failed to download or send the video")
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

async def setup(bot):
    cog = VideoDownload(bot)
    await cog.setup()
    await bot.add_cog(cog)
