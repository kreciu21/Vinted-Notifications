import asyncio
import re
from contextlib import suppress
from queue import Empty
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import core
import db
from logger import get_logger

logger = get_logger(__name__)


class DiscordBot(commands.Bot):
    def __init__(self, queue):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned_or("!"), intents=intents)

        self.new_items_queue = queue
        self.queue_task: Optional[asyncio.Task] = None
        self.version_task: Optional[asyncio.Task] = None
        self.command_guild: Optional[discord.Object] = self._load_command_guild()

    def _load_command_guild(self) -> Optional[discord.Object]:
        guild_id = db.get_parameter("discord_guild_id")
        if not guild_id:
            return None
        try:
            guild_object = discord.Object(id=int(guild_id))
            logger.info("Restricting Discord slash commands to guild %s", guild_id)
            return guild_object
        except ValueError:
            logger.error("Invalid Discord guild ID configured: %s", guild_id)
            return None

    async def setup_hook(self) -> None:
        self.queue_task = asyncio.create_task(self.process_queue())
        self.version_task = asyncio.create_task(self.version_checker())
        await self.sync_application_commands()

    async def sync_application_commands(self) -> None:
        try:
            if self.command_guild is not None:
                await self.tree.sync(guild=self.command_guild)
                logger.info("Discord application commands synced for guild %s", self.command_guild.id)
            else:
                await self.tree.sync()
                logger.info("Discord application commands synced globally")
        except Exception as e:
            logger.error("Failed to sync Discord application commands: %s", e, exc_info=True)

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
                    message = (
                        f"Version {latest_version} is now available. "
                        f"Current version: {current_version}."
                    )
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

    def slash_command(*args, **kwargs):
        if bot.command_guild is not None:
            kwargs.setdefault("guild", bot.command_guild)
        return bot.tree.command(*args, **kwargs)

    @slash_command(name="hello", description="Check if the Vinted Notifications bot is running")
    async def hello(interaction: discord.Interaction):
        try:
            version = db.get_parameter("version") or "unknown"
            await interaction.response.send_message(
                f"Hello {interaction.user.display_name}! Vinted-Notifications is running version {version}.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error("Error in Discord hello command: %s", e, exc_info=True)
            await _send_error(interaction)

    @slash_command(name="add_query", description="Add a new Vinted search query")
    @app_commands.describe(query_url="Full Vinted search URL", name="Optional display name for the query")
    async def add_query(interaction: discord.Interaction, query_url: str, name: Optional[str] = None):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message, is_new_query = core.process_query(query_url, name if name else None)
            if is_new_query:
                query_list = core.get_formatted_query_list()
                response = f"{message}\nCurrent queries:\n{query_list}"
            else:
                response = message
            await interaction.followup.send(response, ephemeral=True)
        except Exception as e:
            logger.error("Error adding query from Discord: %s", e, exc_info=True)
            await _send_error(interaction)

    @slash_command(name="remove_query", description="Remove a query by its number or remove all queries")
    @app_commands.describe(selector="Enter the query number from /queries or use 'all'")
    async def remove_query(interaction: discord.Interaction, selector: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message, success = core.process_remove_query(selector)
            if success and selector.lower() != "all":
                query_list = core.get_formatted_query_list()
                response = f"{message}\nCurrent queries:\n{query_list}"
            else:
                response = message
            await interaction.followup.send(response, ephemeral=True)
        except Exception as e:
            logger.error("Error removing query from Discord: %s", e, exc_info=True)
            await _send_error(interaction)

    @slash_command(name="queries", description="List configured Vinted queries")
    async def queries(interaction: discord.Interaction):
        try:
            query_list = core.get_formatted_query_list()
            if not query_list.strip():
                query_list = "No queries configured yet. Use /add_query to add one."
            await interaction.response.send_message(
                f"Current queries:\n{query_list}", ephemeral=True
            )
        except Exception as e:
            logger.error("Error retrieving queries from Discord: %s", e, exc_info=True)
            await _send_error(interaction)

    @slash_command(name="clear_allowlist", description="Allow items from all countries")
    async def clear_allowlist(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            db.clear_allowlist()
            await interaction.followup.send(
                "Allowlist cleared. All countries are allowed.", ephemeral=True
            )
        except Exception as e:
            logger.error("Error clearing allowlist from Discord: %s", e, exc_info=True)
            await _send_error(interaction)

    @slash_command(name="add_country", description="Add a country to the allowlist")
    @app_commands.describe(country="Country name or code to allow")
    async def add_country(interaction: discord.Interaction, country: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message, country_list = core.process_add_country(country)
            await interaction.followup.send(
                f"{message} Current allowlist: {country_list}", ephemeral=True
            )
        except Exception as e:
            logger.error("Error adding country from Discord: %s", e, exc_info=True)
            await _send_error(interaction)

    @slash_command(name="remove_country", description="Remove a country from the allowlist")
    @app_commands.describe(country="Country name or code to remove")
    async def remove_country(interaction: discord.Interaction, country: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message, country_list = core.process_remove_country(country)
            await interaction.followup.send(
                f"{message} Current allowlist: {country_list}", ephemeral=True
            )
        except Exception as e:
            logger.error("Error removing country from Discord: %s", e, exc_info=True)
            await _send_error(interaction)

    @slash_command(name="allowlist", description="Display the active allowlist")
    async def allowlist(interaction: discord.Interaction):
        try:
            countries = db.get_allowlist()
            if countries == 0:
                message = "No allowlist set. All countries are allowed."
            else:
                message = f"Current allowlist: {countries}"
            await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            logger.error("Error retrieving allowlist from Discord: %s", e, exc_info=True)
            await _send_error(interaction)

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        logger.error("Unhandled Discord slash command error: %s", error, exc_info=True)
        await _send_error(interaction)

    return bot


async def _send_error(interaction: discord.Interaction) -> None:
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                "An unexpected error occurred. Please try again later.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An unexpected error occurred. Please try again later.", ephemeral=True
            )
    except Exception as followup_error:
        logger.error("Failed to send error response on Discord: %s", followup_error, exc_info=True)


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
