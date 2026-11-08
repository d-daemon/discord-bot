import asyncio
import html
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import discord
import requests
from discord.ext import commands, tasks
from discord.ui import Button
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from utils.__language_data import (
    ADDITIONAL_LANGUAGE_NAMES,
    EMOJI_TO_LANG,
    LANG_CODE_MAP,
    LANGUAGE_EMOJI_MAP,
    MULTI_LANG_COUNTRIES,
)
from utils.helpers import send_ephemeral
from utils.paginator import PaginatorView

logger = logging.getLogger(__name__)

TRANSLATION_BACKEND_ERRORS = (
    requests.RequestException,
    TimeoutError,
    RuntimeError,
    ValueError,
    TypeError,
    IndexError,
)

MYMEMORY_MAX_BYTES = 500
GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
DEEPL_FREE_TRANSLATE_URL = "https://api-free.deepl.com/v2/translate"
MYMEMORY_TRANSLATE_URL = "https://api.mymemory.translated.net/get"


class TranslationUnavailable(RuntimeError):
    pass


def translate_with_google(text: str, source: str, target: str) -> str:
    response = requests.get(
        GOOGLE_TRANSLATE_URL,
        params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    segments = payload[0]
    translated = "".join(segment[0] for segment in segments if segment and segment[0])
    if not translated:
        raise RuntimeError("Google Translate returned an empty translation")
    return translated


def translate_with_deepl(
    text: str,
    source: str,
    target: str,
    api_key: str,
) -> str:
    params = {"text": text, "target_lang": target.upper()}
    if source.lower() != "auto":
        params["source_lang"] = source.upper()
    response = requests.post(
        DEEPL_FREE_TRANSLATE_URL,
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        data=params,
        timeout=15,
    )
    response.raise_for_status()
    translations = response.json().get("translations", [])
    translated = translations[0].get("text") if translations else None
    if not translated:
        raise RuntimeError("DeepL returned an empty translation")
    return translated


def split_text_for_mymemory(
    text: str, max_bytes: int = MYMEMORY_MAX_BYTES
) -> list[str]:
    """Split text into UTF-8-safe chunks that fit MyMemory's per-query limit."""
    if max_bytes < 4:
        raise ValueError("MyMemory chunk limit must be at least 4 bytes")
    if not text:
        return [""]

    chunks = []
    start = 0
    while start < len(text):
        end = start
        byte_count = 0
        last_whitespace = None
        while end < len(text):
            char_bytes = len(text[end].encode("utf-8"))
            if byte_count + char_bytes > max_bytes:
                break
            byte_count += char_bytes
            end += 1
            if text[end - 1].isspace():
                last_whitespace = end

        if end < len(text) and last_whitespace is not None and last_whitespace > start:
            end = last_whitespace
        if end == start:
            end += 1
        chunks.append(text[start:end])
        start = end
    return chunks


def translate_with_mymemory(
    text: str,
    source: str,
    target: str,
    api_key: str | None = None,
) -> str:
    translations = []
    for chunk in split_text_for_mymemory(text):
        if not chunk.strip():
            translations.append(chunk)
            continue
        prefix = chunk[: len(chunk) - len(chunk.lstrip())]
        suffix = chunk[len(chunk.rstrip()) :]
        params = {"q": chunk.strip(), "langpair": f"{source}|{target}"}
        if api_key:
            params["key"] = api_key
        response = requests.get(MYMEMORY_TRANSLATE_URL, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("responseStatus")) != "200":
            raise RuntimeError("MyMemory returned an unsuccessful response")
        translated = payload.get("responseData", {}).get("translatedText")
        if not isinstance(translated, str) or not translated:
            raise RuntimeError("MyMemory returned an empty translation")
        translations.append(prefix + html.unescape(translated) + suffix)
    return "".join(translations)


class LanguageButtons(discord.ui.View):
    def __init__(self, cog, message, user, options):
        super().__init__()
        self.cog = cog
        self.message = message
        self.user = user
        self.selected_language = None
        self.prompt: discord.Message | None = None
        for code, name in options.items():
            button = Button(
                label=name, custom_id=code, style=discord.ButtonStyle.primary
            )

            async def select_language(interaction, language=code):
                await interaction.response.defer()
                self.selected_language = language
                self.stop()

            button.callback = select_language
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await send_ephemeral(interaction, "This language selection is not for you.")
            return False
        return True

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.selected_language = None
        self.stop()

    async def on_timeout(self):
        if self.prompt is not None:
            try:
                await self.prompt.delete()
            except discord.NotFound:
                pass
            except discord.HTTPException:
                logger.exception("Failed to delete expired language selection")


class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.char_limit = 1000
        self.user_cooldowns = {}
        self.language_emoji_map = LANGUAGE_EMOJI_MAP
        self.multi_lang_countries = MULTI_LANG_COUNTRIES
        self.lang_code_map = LANG_CODE_MAP
        self.emoji_to_lang = EMOJI_TO_LANG
        self.translated_messages = {}
        self.language_names: dict[str, str] = {}
        self.FLAG_EMOJI_PATTERN = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")
        self.cleanup_translations.start()

    async def cog_load(self):
        try:
            self.language_names = await asyncio.to_thread(self.get_language_names)
        except TRANSLATION_BACKEND_ERRORS:
            logger.exception("Failed to load translation language names")
            self.language_names = {code: code for code in self.language_emoji_map}

    def cog_unload(self):
        self.cleanup_translations.cancel()

    @tasks.loop(minutes=15)
    async def cleanup_translations(self):
        current_time = datetime.now(timezone.utc)
        to_remove = []
        for message_id, translations in self.translated_messages.items():
            for lang, (translation_id, timestamp) in translations.items():
                if current_time - timestamp > timedelta(hours=1):
                    to_remove.append((message_id, lang))

        for message_id, lang in to_remove:
            del self.translated_messages[message_id][lang]
            if not self.translated_messages[message_id]:
                del self.translated_messages[message_id]

        logger.info("Cleaned up %s old translations", len(to_remove))

    def get_language_names(self):
        return {
            code: ADDITIONAL_LANGUAGE_NAMES.get(code, code)
            for code in self.language_emoji_map
        }

    async def translate_text(self, text, dest_lang):
        return await asyncio.to_thread(self._translate_text_sync, text, dest_lang)

    def _translate_text_sync(self, text, dest_lang):
        try:
            detected_source = detect(text)
        except LangDetectException:
            detected_source = "auto"
        source = self.lang_code_map.get(detected_source.lower()) or detected_source
        target = self.lang_code_map.get(dest_lang.lower()) or dest_lang

        try:
            translation = translate_with_google(text, source, target)
            if translation:
                return translation, source
            raise ValueError("Google Translate returned an empty translation")
        except TRANSLATION_BACKEND_ERRORS as error:
            logger.warning("Google translation failed (%s)", type(error).__name__)

        deepl_api_key = os.getenv("DEEPL_API_KEY")
        if deepl_api_key:
            try:
                translation = translate_with_deepl(text, source, target, deepl_api_key)
                if translation:
                    logger.info("Translation fallback succeeded using DeepL")
                    return translation, source
                raise ValueError("DeepL returned an empty translation")
            except TRANSLATION_BACKEND_ERRORS as error:
                logger.warning("DeepL translation failed (%s)", type(error).__name__)

        mymemory_api_key = os.getenv("MYMEMORY_API_KEY")
        try:
            translation = translate_with_mymemory(
                text,
                source,
                target,
                mymemory_api_key,
            )
            logger.info("Translation fallback succeeded using MyMemory")
            return translation, source
        except TRANSLATION_BACKEND_ERRORS as error:
            logger.warning("MyMemory translation failed (%s)", type(error).__name__)

        raise TranslationUnavailable(
            "All configured translation services failed"
        ) from None

    async def _reaction_user(self, payload):
        user = payload.member or self.bot.get_user(payload.user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(payload.user_id)
            except discord.HTTPException:
                logger.exception("Failed to resolve user for flag reaction")
        return user

    async def _reaction_channel(self, channel_id):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        return channel

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        emoji = str(payload.emoji)
        if not self.FLAG_EMOJI_PATTERN.match(emoji) or (
            emoji not in self.multi_lang_countries and emoji not in self.emoji_to_lang
        ):
            return

        user = await self._reaction_user(payload)
        if user is None or user.bot:
            return
        if self.bot.user is not None and payload.user_id == self.bot.user.id:
            return

        try:
            channel = await self._reaction_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            logger.exception("Failed to fetch message for flag reaction")
            return
        if message.author.bot:
            return

        logger.info("Reaction added: %s by %s", emoji, user)
        if emoji in self.multi_lang_countries:
            options = self.multi_lang_countries[emoji]
            view = LanguageButtons(self, message, user, options)
            prompt = await message.channel.send(
                f"{user.mention} Please select a language:", view=view
            )
            view.prompt = prompt
            try:
                await view.wait()
                if view.selected_language:
                    await self.translate_message(message, view.selected_language, user)
            finally:
                try:
                    await prompt.delete()
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    logger.exception("Failed to delete language selection prompt")
        else:
            await self.translate_message(message, self.emoji_to_lang[emoji], user)

    async def translate_message(self, message, target_lang, user):
        message_id = message.id
        if (
            message_id in self.translated_messages
            and target_lang in self.translated_messages[message_id]
        ):
            await message.add_reaction("❤️")
            return

        now = asyncio.get_running_loop().time()
        retry_after = self.user_cooldowns.get(user.id, 0) - now
        if retry_after > 0:
            await message.channel.send(
                f"{user.mention} Please wait {retry_after:.2f} seconds before translating again.",
                delete_after=10,
            )
            return
        self.user_cooldowns[user.id] = now + 10
        if len(self.user_cooldowns) > 4096:
            self.user_cooldowns = {
                user_id: expiry
                for user_id, expiry in self.user_cooldowns.items()
                if expiry > now
            }

        if len(message.content) > self.char_limit:
            await message.channel.send(
                f"{user.mention} The message is too long to translate (max {self.char_limit} characters).",
                delete_after=10,
            )
            return

        try:
            translated_text, src_lang = await self.translate_text(
                message.content, target_lang
            )

            embed = discord.Embed(title="Translation", color=discord.Color.blue())
            embed.add_field(
                name=f"Original ({src_lang})", value=message.content, inline=False
            )
            embed.add_field(
                name=f"Translation ({target_lang})",
                value=translated_text[:1021] + "..."
                if len(translated_text) > 1024
                else translated_text,
                inline=False,
            )
            embed.set_footer(text=f"Requested by {user.name}")

            sent_message = await message.channel.send(embed=embed)

            if message_id not in self.translated_messages:
                self.translated_messages[message_id] = {}
            self.translated_messages[message_id][target_lang] = (
                sent_message.id,
                datetime.now(timezone.utc),
            )

            await message.add_reaction("❤️")

        except Exception:
            logger.exception("Translation failed")
            await message.channel.send(
                "Translation failed. Please try again later or choose another language.",
                delete_after=20,
            )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        emoji = str(payload.emoji)
        if not self.FLAG_EMOJI_PATTERN.match(emoji):
            return

        if emoji in self.emoji_to_lang:
            user = await self._reaction_user(payload)
            if user is None or user.bot:
                return
            if self.bot.user is not None and payload.user_id == self.bot.user.id:
                return

            message_id = payload.message_id
            target_lang = self.emoji_to_lang[emoji]
            if (
                message_id in self.translated_messages
                and target_lang in self.translated_messages[message_id]
            ):
                translation_id, _ = self.translated_messages[message_id][target_lang]
                try:
                    channel = await self._reaction_channel(payload.channel_id)
                    translation_message = await channel.fetch_message(translation_id)
                    await translation_message.delete()
                except discord.errors.NotFound:
                    pass
                except discord.HTTPException:
                    logger.exception(
                        "Failed to delete translation for removed flag reaction"
                    )
                    return

                del self.translated_messages[message_id][target_lang]
                if not self.translated_messages[message_id]:
                    del self.translated_messages[message_id]

    @commands.command(name="translate")
    async def translate_command(self, ctx, lang: str, *, text: str):
        """Translate text to a specified language"""
        target_lang = self.lang_code_map.get(lang.lower(), lang.lower())
        if target_lang not in self.language_emoji_map:
            await ctx.send(
                "Invalid language code. Use `!languages` to see available options."
            )
            return
        if len(text) > self.char_limit:
            await ctx.send(
                f"Text is too long to translate (max {self.char_limit} characters)."
            )
            return

        try:
            translated_text, src_lang = await self.translate_text(text, target_lang)
            embed = discord.Embed(title="Translation", color=discord.Color.blue())
            embed.add_field(name=f"Original ({src_lang})", value=text, inline=False)
            embed.add_field(
                name=f"Translation ({target_lang})",
                value=translated_text[:1021] + "..."
                if len(translated_text) > 1024
                else translated_text,
                inline=False,
            )
            await ctx.send(embed=embed)
        except Exception:
            logger.exception("Translation command failed")
            await ctx.send("Translation failed. Please try again later.")

    @commands.command(name="languages", aliases=["lang"])
    async def list_languages(self, ctx):
        """List all supported languages with pagination"""
        languages_per_page = 10
        all_languages = sorted(
            self.language_emoji_map.items(),
            key=lambda x: self.language_names.get(x[0], x[0]),
        )
        pages = []

        for i in range(0, len(all_languages), languages_per_page):
            page_languages = all_languages[i : i + languages_per_page]
            embed = discord.Embed(
                title="Supported Languages", color=discord.Color.blue()
            )

            language_list = ""
            for code, flags in page_languages:
                language_name = self.language_names.get(code, code)
                flags_str = " ".join(flags[:4])
                language_list += f"**{language_name}** (`{code}`) {flags_str}\n"

            embed.description = language_list

            embed.add_field(
                name="Usage",
                value="React with a flag emoji or use `!translate [code] [text]` to translate",
                inline=False,
            )

            pages.append(embed)

        paginator = PaginatorView(pages, ctx.author)
        await paginator.send(ctx)

    @commands.command(name="translation_info")
    async def translation_info(self, ctx):
        """Display information about translation limitations"""
        embed = discord.Embed(
            title="Translation Information", color=discord.Color.blue()
        )
        embed.add_field(
            name="Character Limit", value=f"{self.char_limit} characters", inline=False
        )
        embed.add_field(
            name="Cooldown", value="1 translation per 10 seconds per user", inline=False
        )
        embed.add_field(
            name="Usage",
            value="React to a message with a flag emoji to translate\nor use !translate [lang_code] [text]",
            inline=False,
        )
        embed.add_field(
            name="Multi-language Countries",
            value="Some country flags (e.g., 🇨🇦, 🇨🇭, 🇧🇪) will prompt for language selection",
            inline=False,
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TranslationCog(bot))
    logger.info("TranslationCog has been set up")
