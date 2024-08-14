import discord
from discord.ext import commands
from discord import app_commands
import instaloader
import os
import logging
from datetime import datetime

def unique_filename(directory, base_name, index):
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(directory, f"{base_name}_{current_time}_{index}.jpg")

def load_config():
    with open('/app/config/config.json', 'r') as config_file:
        return json.load(config_file)

def download_instagram_photos(post_url, download_dir):
    L = instaloader.Instaloader(dirname_pattern=download_dir, filename_pattern="{shortcode}", save_metadata=False)
    shortcode = post_url.split('/')[-2]
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    
    L.download_post(post, target=download_dir)
    
    photo_files = [f for f in os.listdir(download_dir) if f.endswith('.jpg')]
    if not photo_files:
        raise FileNotFoundError("No photo file found in the downloaded files!")
    
    downloaded_files = []
    for index, photo_file in enumerate(photo_files):
        new_filename = unique_filename(download_dir, shortcode, index + 1)
        os.rename(os.path.join(download_dir, photo_file), new_filename)
        downloaded_files.append(new_filename)
    
    return downloaded_files

class PhotoDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.download_dir = "/app/data/Photo-Output"
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    async def setup(self):
        logging.info("Fetching guild IDs for PhotoDownload cog.")
        guild_ids = await self.fetch_guild_ids()
        for guild_id in guild_ids:
            self.bot.tree.add_command(self.download_photo, guild=discord.Object(id=guild_id))
        logging.info("PhotoDownload cog commands added for guilds.")

    async def fetch_guild_ids(self):
        async with self.bot.db_pool.acquire() as connection:
            records = await connection.fetch("SELECT guild_id FROM guilds")
            return [record['guild_id'] for record in records]

    @app_commands.command(name="ig_photo", description="Download a photo from Instagram")
    @app_commands.describe(url="URL of the Instagram post")
    async def download_photo(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)
        
        # Log the user's request
        logging.info(f"{interaction.user} requested to download a photo from Instagram with URL: {url}")
        
        try:
            photo_paths = download_instagram_photos(url, self.download_dir)
            
            if len(photo_paths) == 1:
                selected_photos = [photo_paths[0]]
            else:
                # Let the user select which images to download
                options = [
                    discord.SelectOption(label=f"Image {i+1}", value=str(i))
                    for i in range(len(photo_paths))
                ]

                class MultiPhotoSelect(discord.ui.Select):
                    def __init__(self):
                        super().__init__(placeholder="Choose images to download", min_values=1, max_values=len(options), options=options)

                    async def callback(self, select_interaction: discord.Interaction):
                        selected_indexes = [int(i) for i in self.values]
                        selected_photos = [photo_paths[i] for i in selected_indexes]

                        for photo in selected_photos:
                            file = discord.File(photo, filename=os.path.basename(photo))
                            await select_interaction.channel.send(f"{interaction.user.mention} Here is one of your selected photos:", file=file)

                        # Clean up after sending
                        for f in os.listdir(self.download_dir):
                            file_path = os.path.join(self.download_dir, f)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                        
                        await select_interaction.followup.send(f"The photos have been sent to the '{select_interaction.channel.name}' channel.", ephemeral=True)

                view = discord.ui.View()
                view.add_item(MultiPhotoSelect())
                await interaction.followup.send("Please select the photos you want to download:", view=view)
                return

            # If there's only one image, send it directly
            for selected_photo in selected_photos:
                file = discord.File(selected_photo, filename=os.path.basename(selected_photo))
                await interaction.channel.send(f"{interaction.user.mention} Here is your downloaded photo:", file=file)

            # Clean up download directory
            for f in os.listdir(self.download_dir):
                file_path = os.path.join(self.download_dir, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)

            await interaction.followup.send(f"The photos have been sent to the '{interaction.channel.name}' channel.", ephemeral=True)
        except Exception as e:
            logging.exception("Failed to download or send the photo")
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

async def setup(bot):
    cog = PhotoDownload(bot)
    await cog.setup()
    await bot.add_cog(cog)
