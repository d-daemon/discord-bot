import discord
from discord.ext import commands
import instaloader
import os
from pytube import YouTube
from yt_dlp import YoutubeDL
import logging

def unique_filename(directory, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    unique_name = filename
    while os.path.exists(os.path.join(directory, unique_name)):
        unique_name = f"{base}_{counter}{ext}"
        counter += 1
    return unique_name

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
    ydl_opts = {
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best'
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(video_url, download=True)
        video_filename = ydl.prepare_filename(info_dict)
    return video_filename

class VDL(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.download_dir = "/app/data/VDL-Output"
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    @commands.command(name="vdl", help="Download a video from a URL. Usage: ??vdl [platform] [url]")
    async def download_video(self, ctx, platform: str, url: str):
        """Download video using a prefix command."""
        platform = platform.lower()
        try:
            if platform == 'instagram':
                video_path = download_instagram_video(url, self.download_dir)
            elif platform == 'youtube':
                video_path = download_youtube_video(url, self.download_dir)
            else:
                video_path = download_with_ytdlp(url, self.download_dir)

            channel_name = self.config['videoddownload_channel']
            channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
            file = discord.File(video_path, filename=os.path.basename(video_path))
            if channel:
                await channel.send("Here is the downloaded video:", file=file)
            os.remove(video_path)
            await ctx.send(f"The video has been sent to the '{channel_name}' channel.")

        except Exception as e:
            logging.exception("Failed to download or send the video")
            await ctx.send(f"An error occurred: {e}")

async def setup(bot):
    await bot.add_cog(VDL(bot))
