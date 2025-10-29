import asyncio
import re
from contextlib import suppress
from queue import Empty

import discord
from discord.ext import commands

import core
import db
from logger import get_logger

logger = get_logger(__name__)


class DiscordBot(commands.Bot):
    def __init__(self, queue):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self.new_items_queue = queue
        self.queue_task = None
        self.version_task = None

    async def setup_hook(self) -> None:
        self.queue_task = asyncio.create_task(self.process_queue())
        self.version_task = asyncio.create_task(self.version_checker())

    async def close(self) -> None:
        for task in (self.queue_task, self.version_task):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        await super().close()

    async def on_ready(self) -> None:
        logger.info("Discord bot connected as %s (ID: %s)", self.user, getattr(self.user, "id", "unknown"))

    async def process_queue(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                content, url, text, buy_url, buy_text = self.new_items_queue.get_nowait()
            except Empty:
                await asyncio.sleep(0.5)
                continue
            except Exception as e:
                logger.error("Unexpected error while reading discord queue: %s", e, exc_info=True)
                await asyncio.sleep(1)
                continue

            try:
                await self.send_new_post(content, url, text, buy_url, buy_text)
            except Exception as e:
                logger.error("Error sending discord notification: %s", e, exc_info=True)

    async def version_checker(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                is_up_to_date, current_version, latest_version, github_url = core.check_version()
                if not is_up_to_date:
                    message = (f"Version {latest_version} is now available. "
                               f"Current version: {current_version}.")
                    await self.send_simple_message(message, github_url, "Open GitHub")
            except Exception as e:
                logger.error("Error while checking version for Discord notifications: %s", e, exc_info=True)
            await asyncio.sleep(86400)

    async def get_target_channel(self):
        channel_id = db.get_parameter("discord_channel_id")
        if not channel_id:
            logger.warning("Discord channel ID is not configured. Skipping notification.")
            return None
        try:
            channel_id_int = int(channel_id)
        except ValueError:
            logger.error("Discord channel ID is invalid: %s", channel_id)
            return None

        channel = self.get_channel(channel_id_int)
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id_int)
            except Exception as e:
                logger.error("Unable to fetch Discord channel %s: %s", channel_id_int, e, exc_info=True)
                return None
        return channel

    def build_embed(self, content: str, url: str) -> discord.Embed:
        title = "New Vinted Item"
        price = None
        brand = None
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("🆕 Title :"):
                title = line.split(":", 1)[1].strip()
            elif line.startswith("💶 Price :"):
                price = line.split(":", 1)[1].strip()
            elif line.startswith("🛍️ Brand :"):
                brand = line.split(":", 1)[1].strip()

        embed = discord.Embed(title=title, url=url, colour=discord.Colour.blurple())

        description_parts = []
        if price:
            description_parts.append(f"**Price:** {price}")
        if brand and brand.lower() != "none":
            description_parts.append(f"**Brand:** {brand}")
        if description_parts:
            embed.description = "\n".join(description_parts)

        image_match = re.search(r"href=['\"]([^'\"]+)['\"]", content)
        if image_match:
            embed.set_image(url=image_match.group(1))

        return embed

    def build_view(self, url: str, text: str, buy_url: str, buy_text: str):
        view = discord.ui.View()
        if url and text:
            view.add_item(discord.ui.Button(label=text, url=url))
        if buy_url and buy_text:
            view.add_item(discord.ui.Button(label=buy_text, url=buy_url))
        return view if len(view.children) > 0 else None

    async def send_new_post(self, content, url, text, buy_url=None, buy_text=None):
        channel = await self.get_target_channel()
        if channel is None:
            return

        embed = self.build_embed(content, url)
        view = self.build_view(url, text, buy_url, buy_text)

        try:
            await channel.send(embed=embed, view=view)
        except Exception as e:
            logger.error("Failed to send Discord notification: %s", e, exc_info=True)

    async def send_simple_message(self, message: str, url: str = None, button_text: str = None):
        channel = await self.get_target_channel()
        if channel is None:
            return

        view = None
        if url and button_text:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label=button_text, url=url))

        try:
            await channel.send(content=message, view=view)
        except Exception as e:
            logger.error("Failed to send Discord simple message: %s", e, exc_info=True)


def create_bot(queue):
    bot = DiscordBot(queue)

    @bot.command(name="hello")
    async def hello(ctx: commands.Context):
        try:
            version = db.get_parameter("version") or "unknown"
            await ctx.reply(f"Hello {ctx.author.display_name}! Vinted-Notifications is running version {version}.")
        except Exception as e:
            logger.error("Error in Discord hello command: %s", e, exc_info=True)
            await ctx.reply("An error occurred. Please try again later.")

    @bot.command(name="add_query")
    async def add_query(ctx: commands.Context, *, query: str = None):
        if not query:
            await ctx.reply("No query provided. Usage: !add_query <url> or name=url")
            return
        try:
            name = None
            url = query
            if "=http" in query:
                name, url = query.split("=", 1)
            message, is_new_query = core.process_query(url, name if name else None)
            if is_new_query:
                query_list = core.get_formatted_query_list()
                await ctx.reply(f"{message}\nCurrent queries:\n{query_list}")
            else:
                await ctx.reply(message)
        except Exception as e:
            logger.error("Error adding query from Discord: %s", e, exc_info=True)
            await ctx.reply("An error occurred while adding the query.")

    @bot.command(name="remove_query")
    async def remove_query(ctx: commands.Context, query_number: str = None):
        if not query_number:
            await ctx.reply("No number provided. Usage: !remove_query <number|all>")
            return
        try:
            message, success = core.process_remove_query(query_number)
            if success and query_number != "all":
                query_list = core.get_formatted_query_list()
                await ctx.reply(f"{message}\nCurrent queries:\n{query_list}")
            else:
                await ctx.reply(message)
        except Exception as e:
            logger.error("Error removing query from Discord: %s", e, exc_info=True)
            await ctx.reply("An error occurred while removing the query.")

    @bot.command(name="queries")
    async def queries(ctx: commands.Context):
        try:
            query_list = core.get_formatted_query_list()
            await ctx.reply(f"Current queries:\n{query_list}")
        except Exception as e:
            logger.error("Error retrieving queries from Discord: %s", e, exc_info=True)
            await ctx.reply("An error occurred while retrieving the queries.")

    @bot.command(name="clear_allowlist")
    async def clear_allowlist(ctx: commands.Context):
        try:
            db.clear_allowlist()
            await ctx.reply("Allowlist cleared. All countries are allowed.")
        except Exception as e:
            logger.error("Error clearing allowlist from Discord: %s", e, exc_info=True)
            await ctx.reply("An error occurred while clearing the allowlist.")

    @bot.command(name="add_country")
    async def add_country(ctx: commands.Context, *, country: str = None):
        if not country:
            await ctx.reply("No country provided. Usage: !add_country <country name>")
            return
        try:
            message, country_list = core.process_add_country(country)
            await ctx.reply(f"{message} Current allowlist: {country_list}")
        except Exception as e:
            logger.error("Error adding country from Discord: %s", e, exc_info=True)
            await ctx.reply("An error occurred while adding the country to the allowlist.")

    @bot.command(name="remove_country")
    async def remove_country(ctx: commands.Context, *, country: str = None):
        if not country:
            await ctx.reply("No country provided. Usage: !remove_country <country name>")
            return
        try:
            message, country_list = core.process_remove_country(country)
            await ctx.reply(f"{message} Current allowlist: {country_list}")
        except Exception as e:
            logger.error("Error removing country from Discord: %s", e, exc_info=True)
            await ctx.reply("An error occurred while removing the country from the allowlist.")

    @bot.command(name="allowlist")
    async def allowlist(ctx: commands.Context):
        try:
            countries = db.get_allowlist()
            if countries == 0:
                await ctx.reply("No allowlist set. All countries are allowed.")
            else:
                await ctx.reply(f"Current allowlist: {countries}")
        except Exception as e:
            logger.error("Error retrieving allowlist from Discord: %s", e, exc_info=True)
            await ctx.reply("An error occurred while retrieving the allowlist.")

    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return
        logger.error("Unhandled Discord command error: %s", error, exc_info=True)
        await ctx.reply("An unexpected error occurred while processing the command.")

    return bot


async def run_discord_bot(queue):
    token = db.get_parameter("discord_token")
    if not token:
        logger.error("Discord token is not configured. Unable to start bot.")
        return

    bot = create_bot(queue)
    try:
        await bot.start(token)
    finally:
        await bot.close()
