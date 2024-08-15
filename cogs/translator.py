import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from langdetect import detect
import asyncio
import logging

class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.char_limit = 500  # Character limit for translation
        self.cooldown = commands.CooldownMapping.from_cooldown(1, 10.0, commands.BucketType.user)
        self.language_emoji_map = {
            'en': ('🇺🇸', 'flag_us', 'us'),
            'gb': ('🇬🇧', 'flag_gb', 'gb'),
            'fr': ('🇫🇷', 'flag_fr', 'fr'),
            'de': ('🇩🇪', 'flag_de', 'de'),
            'es': ('🇪🇸', 'flag_es', 'es'),
            'it': ('🇮🇹', 'flag_it', 'it'),
            'ja': ('🇯🇵', 'flag_jp', 'jp'),
            'ko': ('🇰🇷', 'flag_kr', 'kr'),
            'nl': ('🇳🇱', 'flag_nl', 'nl'),
            'pt': ('🇵🇹', 'flag_pt', 'pt'),
            'ru': ('🇷🇺', 'flag_ru', 'ru'),
            'zh-CN': ('🇨🇳', 'flag_cn', 'cn'),
            'zh-TW': ('🇭🇰', 'flag_hk', 'hk'),
            'ar': ('🇸🇦', 'flag_sa', 'sa'),
            'hi': ('🇮🇳', 'flag_in', 'in'),
            'bn': ('🇧🇩', 'flag_bd', 'bd'),
            'pa': ('🇮🇳', 'flag_in', 'in'),
            'te': ('🇮🇳', 'flag_in', 'in'),
            'mr': ('🇮🇳', 'flag_in', 'in'),
            'ta': ('🇮🇳', 'flag_in', 'in'),
            'ur': ('🇵🇰', 'flag_pk', 'pk'),
            'fa': ('🇮🇷', 'flag_ir', 'ir'),
            'tr': ('🇹🇷', 'flag_tr', 'tr'),
            'id': ('🇮🇩', 'flag_id', 'id'),
            'th': ('🇹🇭', 'flag_th', 'th'),
            'vi': ('🇻🇳', 'flag_vn', 'vn'),
            'uk': ('🇺🇦', 'flag_ua', 'ua'),
            'pl': ('🇵🇱', 'flag_pl', 'pl'),
            'sv': ('🇸🇪', 'flag_se', 'se'),
            'fi': ('🇫🇮', 'flag_fi', 'fi'),
            'no': ('🇳🇴', 'flag_no', 'no'),
            'da': ('🇩🇰', 'flag_dk', 'dk'),
            'hu': ('🇭🇺', 'flag_hu', 'hu'),
            'cs': ('🇨🇿', 'flag_cz', 'cz'),
            'el': ('🇬🇷', 'flag_gr', 'gr'),
            'bg': ('🇧🇬', 'flag_bg', 'bg'),
            'he': ('🇮🇱', 'flag_il', 'il'),
            'sk': ('🇸🇰', 'flag_sk', 'sk'),
        }
        # Create reverse mappings for easier lookup
        self.unicode_to_lang = {}
        self.custom_to_lang = {}
        self.text_to_lang = {}
        for lang, (unicode, custom, text) in self.language_emoji_map.items():
            self.unicode_to_lang[unicode] = lang
            self.custom_to_lang[custom] = lang
            self.text_to_lang[text] = lang

    def normalize_language_code(self, lang_code):
        # Normalize language codes
        if lang_code.lower() in ['zh-cn', 'zh', 'zh_cn']:
            return 'zh-CN'
        elif lang_code.lower() in ['zh-tw', 'zh_tw', 'zh_hk', 'zh-hk']:
            return 'zh-TW'
        return lang_code

    async def translate_text(self, text, dest_lang):
        try:
            src_lang = self.normalize_language_code(detect(text))
            dest_lang = self.normalize_language_code(dest_lang)
            
            translator = GoogleTranslator(source=src_lang, target=dest_lang)
            translation = translator.translate(text)
            
            return translation, src_lang
        except Exception as e:
            logging.error(f"Translation error: {str(e)}")
            raise

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or reaction.message.author.bot:
            return

        emoji = str(reaction.emoji)
        logging.info(f"Reaction added: {emoji} by {user}")

        target_lang = self.unicode_to_lang.get(emoji) or (
            self.custom_to_lang.get(reaction.emoji.name.lower()) if isinstance(reaction.emoji, discord.Emoji) else None
        )

        if target_lang:
            logging.info(f"Target language: {target_lang}")
            bucket = self.cooldown.get_bucket(reaction.message)
            retry_after = bucket.update_rate_limit()
            if retry_after:
                await reaction.message.channel.send(f"{user.mention} Please wait {retry_after:.2f} seconds before translating again.", delete_after=10)
                return

            if len(reaction.message.content) > self.char_limit:
                await reaction.message.channel.send(f"{user.mention} The message is too long to translate (max {self.char_limit} characters).", delete_after=10)
                return

            try:
                translated_text, src_lang = await self.translate_text(reaction.message.content, target_lang)

                embed = discord.Embed(title="Translation", color=discord.Color.blue())
                embed.add_field(name=f"Original ({src_lang})", value=reaction.message.content, inline=False)
                embed.add_field(name=f"Translation ({target_lang})", value=translated_text, inline=False)
                embed.set_footer(text=f"Requested by {user.name}")

                await reaction.message.channel.send(embed=embed)
            except Exception as e:
                logging.error(f"Translation error: {str(e)}")
                await reaction.message.channel.send(f"An error occurred during translation. Please try again later.", delete_after=10)
        else:
            logging.info(f"No target language found for emoji: {emoji}")

    @commands.command(name='translate')
    async def translate_command(self, ctx, lang: str, *, text: str):
        """Translate text to a specified language"""
        target_lang = self.text_to_lang.get(lang.lower()) or lang.lower()
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
            await ctx.send(f"An error occurred during translation. Please try again later.")

    @commands.command(name='languages')
    async def list_languages(self, ctx):
        """List all supported languages"""
        lang_list = [f"{unicode} :{custom}: {text}: {lang}" 
                     for lang, (unicode, custom, text) in self.language_emoji_map.items()]
        
        # Split the list into chunks of 20 languages
        chunks = [lang_list[i:i + 20] for i in range(0, len(lang_list), 20)]
        
        for i, chunk in enumerate(chunks):
            embed = discord.Embed(title=f"Supported Languages (Page {i+1}/{len(chunks)})", 
                                  description="\n".join(chunk), 
                                  color=discord.Color.blue())
            await ctx.send(embed=embed)

    @commands.command(name='translation_info')
    async def translation_info(self, ctx):
        """Display information about translation limitations"""
        embed = discord.Embed(title="Translation Information", color=discord.Color.blue())
        embed.add_field(name="Character Limit", value=f"{self.char_limit} characters", inline=False)
        embed.add_field(name="Cooldown", value="1 translation per 10 seconds per user", inline=False)
        embed.add_field(name="Usage", value="React to a message with a flag emoji to translate\nor use !translate [lang] [text]", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TranslationCog(bot))
    logging.info("TranslationCog has been set up")