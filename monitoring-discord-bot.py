#!/bin/env python

import discord
from discord.ext import commands, tasks
from discord import Embed
from dotenv import load_dotenv
import aiohttp
import asyncio
import logging
import os

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Load configurations from environment variables or use defaults
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE")
DEV_CHANNEL_ID = int(os.getenv("DEV_CHANNEL_ID"))
DEV_API_URL = os.getenv("DEV_API_URL")
API_URL = os.getenv("API_URL")
API_ENDPOINT = os.getenv("API_ENDPOINT")
API_FACTORY_ID = os.getenv("API_FACTORY_ID")
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN")
THRESHOLD_WEIGHT = int(os.getenv("THRESHOLD_WEIGHT"))
MAX_WEIGHT = int(os.getenv("MAX_WEIGHT"))
SLEEP_TIMER = 1 if DEVELOPMENT_MODE == "True" else 600  # 10min

intents = discord.Intents.all()
client = commands.Bot(command_prefix="!", intents=intents)

previous_items = {}
weight_notification_sent = False
bot_paused = False


async def send_embed(content, embed):
    try:
        await client.wait_until_ready()
        channel_id = DEV_CHANNEL_ID if DEVELOPMENT_MODE == "True" else CHANNEL_ID
        channel = client.get_channel(channel_id)
        if channel:
            await channel.send(content=content, embed=embed)
        else:
            logger.error("Channel not found.")
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")


async def fetch_data(url, headers):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            return data


async def get_total_weight_and_items():
    try:
        url = (
            DEV_API_URL
            if DEVELOPMENT_MODE == "True"
            else f"{API_URL}{API_ENDPOINT}{API_FACTORY_ID}"
        )
        headers = {"authorization": f"Bearer {API_BEARER_TOKEN}"}
        data = await fetch_data(url, headers)
        total_weight = data.get("totalWeight", 0)
        items = {item["item"]: item for item in data.get("items", {})}
        return total_weight, items
    except Exception as e:
        logger.error(f"Failed to fetch data from API: {str(e)}")
        return 0, {}


async def monitor_api_updates():
    global previous_items, weight_notification_sent, bot_paused
    try:
        previous_total_weight, _ = await get_total_weight_and_items()
        logger.info(
            f"DEV MODE: {DEVELOPMENT_MODE} - API Request Time: {SLEEP_TIMER} seconds"
        )
        embed = Embed(title="Monitoring Started", color=0x0000FF)
        embed.add_field(
            name="Total Storage weight",
            value=f"{previous_total_weight}/{MAX_WEIGHT} KG",
            inline=False,
        )
        embed.add_field(
            name="Info",
            value=f"DEV MODE: {DEVELOPMENT_MODE} - API Request Time: {SLEEP_TIMER} seconds",
            inline=False,
        )

        await send_embed("<@&1222362557495382047>", embed)
        while True:
            if not bot_paused:
                current_total_weight, current_items = await get_total_weight_and_items()
                if current_total_weight != previous_total_weight:
                    previous_total_weight = current_total_weight

                if (
                    current_total_weight > THRESHOLD_WEIGHT
                    and not weight_notification_sent
                ):

                    message = f"## Storage nearly full! {MAX_WEIGHT - current_total_weight} KG left until user cannot add more items!"

                    embed = Embed(
                        title="Storage Alert", description=message, color=0xFF0000
                    )

                    await send_embed("@everyone", embed)
                    weight_notification_sent = True

                if current_total_weight <= THRESHOLD_WEIGHT:
                    weight_notification_sent = False
                for item, current_item_data in current_items.items():
                    previous_item_data = previous_items.get(item)
                    if previous_item_data != current_item_data:
                        previous_amount = (
                            previous_item_data.get("amount", 0)
                            if previous_item_data
                            else 0
                        )
                        current_amount = current_item_data.get("amount", 0)
                        if current_amount != previous_amount:
                            message_type = (
                                "added to"
                                if current_amount > previous_amount
                                else "removed from"
                            )

                            logger.info(
                                f"Item {message_type} storage; {item}: {abs(current_amount - previous_amount)}"
                            )

                            embed = Embed(
                                title=f"Item **{message_type}** storage",
                                color=(
                                    int(0x00FF00)
                                    if message_type == "added to"
                                    else int(0xFFA500)
                                ),
                            )

                            embed.add_field(
                                name="Total Storage weight",
                                value=f"{current_total_weight}/{MAX_WEIGHT} KG",
                                inline=False,
                            )

                            embed.add_field(
                                name="Info",
                                value=f"{item}: {abs(current_amount - previous_amount)}x ({previous_amount}x -> **{current_amount}x**)",
                                inline=False,
                            )

                            await send_embed("<@&1222362557495382047>", embed)

                for item, previous_item_data in previous_items.items():
                    if item not in current_items:

                        logger.info(f"Last Item removed from storage: {item}")

                        embed = Embed(
                            title=f"Last Item **removed from** storage",
                            color=(int(0xFFA500)),
                        )

                        embed.add_field(
                            name="Total Storage weight",
                            value=f"{current_total_weight}/{MAX_WEIGHT} KG",
                            inline=False,
                        )

                        embed.add_field(
                            name="Info",
                            value=f"{item}",
                            inline=False,
                        )

                        await send_embed("<@&1222362557495382047>", embed)
                previous_items = current_items
            await asyncio.sleep(SLEEP_TIMER)
    except Exception as e:
        logger.error(f"An error occurred in monitoring: {str(e)}")


@client.event
async def on_ready():
    global previous_items
    logger.info(f"We have logged in as {client.user}")
    _, previous_items = await get_total_weight_and_items()
    client.loop.create_task(monitor_api_updates())


@client.command()
async def pause(ctx):
    global bot_paused
    bot_paused = True
    logger.info("Bot paused!")
    await ctx.send("StateV monitoring paused.")


@client.command()
async def resume(ctx):
    global bot_paused
    bot_paused = False
    logger.info("Bot resumed!")
    await ctx.send("StateV monitoring resumed.")


@client.command()
async def info(ctx):
    try:
        total_weight, current_items = await get_total_weight_and_items()
        logger.info(f"Bot Info: {total_weight} - {current_items}")

        embed = Embed(title="Storage Information", color=0x00FF00)
        embed.add_field(
            name="Storage weight", value=f"{total_weight}/{MAX_WEIGHT} KG", inline=False
        )

        items_string = "\n".join(
            [
                f"{item['item']} - {item['amount']}x - {item['singleWeight']} KG - {item['totalWeight']} KG"
                for item in current_items.values()
            ]
        )
        embed.add_field(
            name="Current items in storage", value=items_string, inline=False
        )

        await ctx.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to fetch info: {str(e)}")


client.run(DISCORD_TOKEN)
