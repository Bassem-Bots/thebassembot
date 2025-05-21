import discord
from discord import app_commands
import requests
import os
from dotenv import load_dotenv
load_dotenv()
# Set up intents and bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Discord Role IDs
programmer_role_id = 1333535325712289874
designer_role_id = 1333535401763278859
builder_role_id = 1333546466081374319
member_role_id = 1333535285782515793

# Discord Channel ID
channel_id = 1333539938628534374



# Environment variables
TRELLO_KEY = os.environ.get("TRELLO_KEY")
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN")
BOARD_ID = os.environ.get("TRELLO_BOARD_ID")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    await tree.sync()  # Sync slash commands with Discord
    print("Slash commands synced.")


# Slash Command: Role Selection Setup
@tree.command(name="setup_roles", description="Set up the role selection message.")
async def setup_roles(interaction: discord.Interaction):
    channel = bot.get_channel(channel_id)

    if channel:
        async for message in channel.history(limit=None):
            await message.delete()

        message = await channel.send(
            "React to claim roles:\n"
            "<:program:1333543210374402119> - Programmer\n"
            "<:designer:1333544306996285540> - Designer\n"
            "<:builder:1333544319696634020> - Builder\n"
            "More to be added soon.."
        )

        await message.add_reaction("<:program:1333543210374402119>")
        await message.add_reaction("<:designer:1333544306996285540>")
        await message.add_reaction("<:builder:1333544319696634020>")

        await interaction.response.send_message("Role selection message set up!", ephemeral=True)

# Handle Reaction Add for Roles
@bot.event
async def on_raw_reaction_add(payload):
    if payload.channel_id != channel_id or payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    roles_emojis = {
        "program": programmer_role_id,
        "designer": designer_role_id,
        "builder": builder_role_id
    }

    emoji_name = payload.emoji.name

    if emoji_name in roles_emojis:
        role_to_add = guild.get_role(roles_emojis[emoji_name])

        for role_id in roles_emojis.values():
            role = guild.get_role(role_id)
            if role in member.roles and role != role_to_add:
                await member.remove_roles(role)

        await member.add_roles(role_to_add)

# Handle Reaction Remove for Roles
@bot.event
async def on_raw_reaction_remove(payload):
    if payload.channel_id != channel_id:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    roles_emojis = {
        "program": programmer_role_id,
        "designer": designer_role_id,
        "builder": builder_role_id
    }

    emoji_name = payload.emoji.name

    if emoji_name in roles_emojis:
        role_to_remove = guild.get_role(roles_emojis[emoji_name])
        await member.remove_roles(role_to_remove)

# Slash Command: Fetch Trello Cards
@tree.command(name="trello_cards", description="Fetch Trello cards from a specific board.")
async def trello_cards(interaction: discord.Interaction):
    url = f"https://api.trello.com/1/boards/{BOARD_ID}/cards"
    params = {
        "key": TRELLO_KEY,
        "token": TRELLO_TOKEN
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        cards = response.json()
        if cards:
            message = "**Trello Cards:**\n```\n"
            message += f"{'Card Name':<30} | {'Short URL':<40}\n"
            message += "-" * 72 + "\n"

            for card in cards:
                message += f"{card['name']:<30} | {card['shortUrl']:<40}\n"

            message += "```"
            await interaction.response.send_message(message)
        else:
            await interaction.response.send_message("No cards found on the Trello board.")
    else:
        await interaction.response.send_message("Failed to fetch Trello cards. Check your API credentials or board ID.")

# Slash Command: Add a Card to Trello
@tree.command(name="add_card", description="Add a card to a Trello list.")
@app_commands.describe(list_id="The ID of the Trello list", card_name="The name of the card to create")
async def add_card(interaction: discord.Interaction, list_id: str, card_name: str):
    url = "https://api.trello.com/1/cards"
    params = {
        "key": TRELLO_KEY,
        "token": TRELLO_TOKEN,
        "idList": list_id,
        "name": card_name
    }

    response = requests.post(url, params=params)
    if response.status_code == 200:
        await interaction.response.send_message(f"Card '{card_name}' created successfully!")
    else:
        await interaction.response.send_message("Failed to create card. Check your API credentials or list ID.")

# Slash Command: Fetch Trello Lists
@tree.command(name="trello_lists", description="Fetch and display Trello lists from a board.")
async def trello_lists(interaction: discord.Interaction):
    url = f"https://api.trello.com/1/boards/{BOARD_ID}/lists"
    params = {
        "key": TRELLO_KEY,
        "token": TRELLO_TOKEN
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        lists = response.json()
        if lists:
            message = "**Trello Lists:**\n"
            for lst in lists:
                message += f"- {lst['name']} (ID: {lst['id']})\n"
            await interaction.response.send_message(message)
        else:
            await interaction.response.send_message("No lists found on the Trello board.")
    else:
        await interaction.response.send_message("Failed to fetch Trello lists.")
from keep_alive import keep_alive

keep_alive()

# Run the bot
bot.run(DISCORD_TOKEN)
