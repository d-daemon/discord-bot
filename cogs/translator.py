import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from langdetect import detect
import asyncio
import logging
from discord.ui import Button, View, Select
from .language_data import (
    LANGUAGE_EMOJI_MAP,
    MULTI_LANG_COUNTRIES,
    LANG_CODE_MAP,
    EMOJI_TO_LANG,
    ADDITIONAL_LANGUAGE_NAMES
)

class LanguagePaginator(View):
    def __init__(self, pages):
        super().__init__(timeout=60)
        self.pages = pages
        self.current_page = 0
        self.update_buttons()

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    def update_buttons(self):
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page == len(self.pages) - 1)

    async def on_timeout(self):
        message = await self.message.fetch()
        await message.delete()

class LanguageSelector(discord.ui.Select):
    def __init__(self, cog, message, user, options):
        super().__init__(placeholder="Select a language", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.message = message
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This selection is not for you.", ephemeral=True)
            return

        selected_lang = self.values[0]
        await interaction.response.defer()
        await self.cog.translate_message(self.message, selected_lang, self.user)
        await interaction.message.delete()

class LanguageSelectorView(discord.ui.View):
    def __init__(self, cog, message, user, options):
        super().__init__()
        self.add_item(LanguageSelector(cog, message, user, options))

class LanguageButtons(discord.ui.View):
    def __init__(self, cog, message, user, options):
        super().__init__()
        self.cog = cog
        self.message = message
        self.user = user
        for code, name in options.items():
            self.add_item(discord.ui.Button(label=name, custom_id=code, style=discord.ButtonStyle.primary))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        await self.message.delete()

class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.char_limit = 1000
        self.cooldown = commands.CooldownMapping.from_cooldown(1, 10.0, commands.BucketType.user)
        self.language_emoji_map = LANGUAGE_EMOJI_MAP
        self.multi_lang_countries = MULTI_LANG_COUNTRIES
        self.lang_code_map = LANG_CODE_MAP
        self.emoji_to_lang = EMOJI_TO_LANG
        self.translated_messages = {}
        self.language_names = self.get_language_names()

    def get_language_names(self):
        translator = GoogleTranslator()
        languages = translator.get_supported_languages(as_dict=True)
        languages.update(ADDITIONAL_LANGUAGE_NAMES)
        return languages

    async def translate_text(self, text, dest_lang):
        try:
            src_lang = detect(text)
            logging.info(f"Detected source language: {src_lang}")
            
            original_src_lang = src_lang
            original_dest_lang = dest_lang
            
            src_lang = self.lang_code_map.get(src_lang.lower(), src_lang)
            dest_lang = self.lang_code_map.get(dest_lang.lower(), dest_lang)

            logging.info(f"Original source language: {original_src_lang}, Mapped to: {src_lang}")
            logging.info(f"Original destination language: {original_dest_lang}, Mapped to: {dest_lang}")

            translator = GoogleTranslator(source=src_lang, target=dest_lang)
            translation = translator.translate(text)
            
            if not translation:
                raise ValueError(f"Translation failed for {src_lang} to {dest_lang}")
            
            return translation, src_lang
        except Exception as e:
            logging.error(f"Translation error: {str(e)}")
            raise

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or reaction.message.author.bot:
            return

        emoji = str(reaction.emoji)
        if emoji in self.multi_lang_countries:
            options = self.multi_lang_countries[emoji]
            view = LanguageButtons(self, reaction.message, user, options)
            prompt = await reaction.message.channel.send(f"{user.mention} Please select a language:", view=view)
            
            def check(i: discord.Interaction):
                return i.data["custom_id"] in options and i.user.id == user.id

            try:
                interaction = await self.bot.wait_for("interaction", timeout=30.0, check=check)
                selected_lang = interaction.data["custom_id"]
                await self.translate_message(reaction.message, selected_lang, user)
                await prompt.delete()
            except asyncio.TimeoutError:
                await prompt.delete()        

    async def translate_message(self, message, target_lang, user):
        message_id = message.id
        if message_id in self.translated_messages and target_lang in self.translated_messages[message_id]:
            await message.add_reaction('❤️')
            return

        bucket = self.cooldown.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            await message.channel.send(f"{user.mention} Please wait {retry_after:.2f} seconds before translating again.", delete_after=10)
            return

        if len(message.content) > self.char_limit:
            await message.channel.send(f"{user.mention} The message is too long to translate (max {self.char_limit} characters).", delete_after=10)
            return

        try:
            translated_text, src_lang = await self.translate_text(message.content, target_lang)

            embed = discord.Embed(title="Translation", color=discord.Color.blue())
            embed.add_field(name=f"Original ({src_lang})", value=message.content, inline=False)
            embed.add_field(name=f"Translation ({target_lang})", value=translated_text, inline=False)
            embed.set_footer(text=f"Requested by {user.name}")

            sent_message = await message.channel.send(embed=embed)
            
            if message_id not in self.translated_messages:
                self.translated_messages[message_id] = {}
            self.translated_messages[message_id][target_lang] = sent_message.id

            await message.add_reaction('❤️')

        except Exception as e:
            logging.error(f"Translation error: {str(e)}")
            error_message = f"An error occurred during translation: {str(e)}\nPlease try again later or use a different language code."
            await message.channel.send(error_message, delete_after=20)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot or reaction.message.author.bot:
            return

        emoji = str(reaction.emoji)
        if emoji in self.multi_lang_countries or emoji in self.emoji_to_lang:
            message_id = reaction.message.id
            if message_id in self.translated_messages:
                for lang, translation_id in self.translated_messages[message_id].items():
                    try:
                        translation_message = await reaction.message.channel.fetch_message(translation_id)
                        await translation_message.delete()
                    except discord.errors.NotFound:
                        pass
                
                try:
                    await reaction.message.remove_reaction('❤️', self.bot.user)
                except discord.errors.NotFound:
                    pass

                del self.translated_messages[message_id]

    @commands.command(name='translate')
    async def translate_command(self, ctx, lang: str, *, text: str):
        """Translate text to a specified language"""
        target_lang = self.lang_code_map.get(lang.lower(), lang.lower())
        if target_lang not in self.language_emoji_map:
            await ctx.send(f"Invalid language code. Use `!languages` to see available options.")
            return

        try:
            translated_text, src_lang = await self.translate_text(text, target_lang)
            embed = discord.Embed(title="Translation", color=discord.Color.blue())
            embed.add_field(name=f"Original ({src_lang})", value=text, inline=False)
            embed.add_field(name=f"Translation ({target_lang})", value=translated_text, inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred during translation: {str(e)}. Please try again later.")

    @commands.command(name='languages', aliases=['lang'])
    async def list_languages(self, ctx):
        """List all supported languages with pagination"""
        languages_per_page = 10
        all_languages = sorted(self.language_emoji_map.items(), key=lambda x: self.language_names.get(x[0], x[0]))
        pages = []

        for i in range(0, len(all_languages), languages_per_page):
            page_languages = all_languages[i:i+languages_per_page]
            embed = discord.Embed(title="Supported Languages", color=discord.Color.blue())
            
            language_list = ""
            for code, flags in page_languages:
                language_name = self.language_names.get(code, code)
                flags_str = " ".join(flags[:4])
                language_list += f"**{language_name}** (`{code}`) {flags_str}\n"
            
            embed.description = language_list
            
            embed.add_field(name="Usage", value="React with a flag emoji or use `!translate [code] [text]` to translate", inline=False)
            
            pages.append(embed)

        paginator = LanguagePaginator(pages)
        message = await ctx.send(embed=pages[0], view=paginator)
        paginator.message = message

    @commands.command(name='translation_info')
    async def translation_info(self, ctx):
        """Display information about translation limitations"""
        embed = discord.Embed(title="Translation Information", color=discord.Color.blue())
        embed.add_field(name="Character Limit", value=f"{self.char_limit} characters", inline=False)
        embed.add_field(name="Cooldown", value="1 translation per 10 seconds per user", inline=False)
        embed.add_field(name="Usage", value="React to a message with a flag emoji to translate\nor use !translate [lang_code] [text]", inline=False)
        embed.add_field(name="Multi-language Countries", value="Some country flags (e.g., 🇨🇦, 🇨🇭, 🇧🇪) will prompt for language selection", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TranslationCog(bot))
    logging.info("TranslationCog has been set up")