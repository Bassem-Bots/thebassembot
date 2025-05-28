import datetime
import os
from unicodedata import name

import discord
import dotenv
import requests
from discord import Option
from discord.ext import commands

dotenv.load_dotenv()

TRELLO_KEY = os.getenv("TRELLO_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
BOARD_ID = os.getenv("TRELLO_BOARD_ID")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
member_role_id =  1333535285782515793
ROLE_MAP = {
    1333535325712289874: "Programmer",
    1333535401763278859: "Designer",
    1333546466081374319: "Builder"
}

CHANNEL_TEAM_MAP = {
    # 1329534093603373156: "Programming",
    1333562973209366638: "Programming",
    1333563089378873394: "Design",
    1333563175068631131: "Build",
}
user_trello_map = {}

bot = commands.Bot(intents=discord.Intents.default())


def get_trello_lists():
    res = requests.get(
        f"https://api.trello.com/1/boards/{BOARD_ID}/lists",
        params={"key": TRELLO_KEY, "token": TRELLO_TOKEN},
    )
    return res.json() if res.status_code == 200 else None


def get_trello_cards():
    res = requests.get(
        f"https://api.trello.com/1/boards/{BOARD_ID}/cards",
        params={"key": TRELLO_KEY, "token": TRELLO_TOKEN},
    )
    return res.json() if res.status_code == 200 else None


def get_trello_labels():

    res = requests.get(
        f"https://api.trello.com/1/boards/{BOARD_ID}/labels",
        params={"key": TRELLO_KEY, "token": TRELLO_TOKEN},
    )
    return res.json() if res.status_code == 200 else None


def get_trello_members():

    res = requests.get(
        f"https://api.trello.com/1/boards/{BOARD_ID}/members",
        params={"key": TRELLO_KEY, "token": TRELLO_TOKEN},
    )
    return res.json() if res.status_code == 200 else None


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


async def list_name_autocomplete(ctx: discord.AutocompleteContext):
    lists = get_trello_lists()
    if not lists:
        return []

    return [l["name"] for l in lists if ctx.value.lower() in l["name"].lower()][:25]


async def member_name_autocomplete(ctx: discord.AutocompleteContext):

    members = get_trello_members()
    if not members:
        return []

    return [
        f"{m['fullName']} ({m['username']})"
        for m in members
        if ctx.value.lower() in m["fullName"].lower()
        or ctx.value.lower() in m["username"].lower()
    ][:25]


async def card_name_autocomplete(ctx: discord.AutocompleteContext):

    cards = get_trello_cards()
    if not cards:
        return []

    return [
        card["name"] for card in cards if ctx.value.lower() in card["name"].lower()
    ][:25]

@bot.slash_command(name="setup_roles", description="Set up roles for the server")
async def setup_roles(ctx: discord.Message, channel: Option(discord.TextChannel, "Channel to set up roles")):
    if channel:
        async for message in channel.history(limit=None):
            await message.delete()

    embed = discord.Embed(
        title="Role Setup",
        description="Click the buttons below to get your roles.",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(),
    )
    for role_id, role_name in ROLE_MAP.items():
        embed.add_field(
            name=role_name,
            value=f"Click the button to get the **{role_name}** role.",
            inline=False,
        )
    view = discord.ui.View(timeout=None)
    for role_id, role_name in ROLE_MAP.items():
        button = discord.ui.Button(
            label=role_name, style=discord.ButtonStyle.primary, custom_id=str(role_id)
        )

        async def button_callback(interaction: discord.Interaction):
            role = interaction.guild.get_role(int(interaction.data["custom_id"]))
            if role:
                if role in interaction.user.roles:
                    await interaction.user.remove_roles(role)
                    await interaction.response.send_message(
                        f"Removed **{role.name}** role.", ephemeral=True
                    )
                else:
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(
                        f"Added **{role.name}** role.", ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "Role not found.", ephemeral=True
                )

        button.callback = button_callback
        view.add_item(button)
    await channel.send(embed=embed, view=view)
    await ctx.respond(
        "Made the role setup message",
        ephemeral=True,
    )
    

@bot.slash_command(name="cards", description="Show all Trello cards grouped by list")
async def cards(ctx):
    await ctx.defer()
    lists = get_trello_lists()
    cards = get_trello_cards()

    if lists is None or cards is None:
        await ctx.respond("Error fetching data from Trello.")
        return

    list_map = {lst["id"]: lst["name"] for lst in lists}
    grouped_cards = {}

    for card in cards:
        grouped_cards.setdefault(card["idList"], []).append(card)

    description = ""
    for list_id, list_name in list_map.items():
        if list_id in grouped_cards:
            description += f"**{list_name}**\n"
            for card in grouped_cards[list_id]:
                name = card["name"]
                url = card["shortUrl"]
                due = card["due"] or "No due date"
                description += f"• [{name}]({url}) — Due: `{due}`\n"
            description += "\n"

    embed = discord.Embed(
        title="Trello Cards by List",
        description=description or "No cards found.",
        color=discord.Color.blue(),
    )
    await ctx.respond(embed=embed)


@bot.slash_command(name="create_card", description="Create a Trello card")
async def create_card(
    ctx,
    name: Option(str, "Card title"),
    list_name: Option(
        str, "Destination list name", autocomplete=list_name_autocomplete
    ),
    desc: Option(str, "Card description", required=False),
    due: Option(str, "Due date (e.g. 2025-06-01T12:00:00.000Z)", required=False),
    assign_to: Option(
        str, "Assign to member", required=False, autocomplete=member_name_autocomplete
    ),
):
    await ctx.defer()
    lists = get_trello_lists()
    if not lists:
        await ctx.respond("Error fetching lists.")
        return

    target_list = next(
        (l for l in lists if l["name"].lower() == list_name.lower()), None
    )
    if not target_list:
        await ctx.respond(f"No list found with name: {list_name}")
        return

    channel_id = ctx.channel.id
    team_name = CHANNEL_TEAM_MAP.get(channel_id)

    card_params = {
        "key": TRELLO_KEY,
        "token": TRELLO_TOKEN,
        "idList": target_list["id"],
        "name": name,
        "desc": desc or "",
        "due": due or "",
    }

    if team_name:
        labels = get_trello_labels()
        if labels:
            team_label = next(
                (l for l in labels if l["name"].lower() == team_name.lower()), None
            )
            if team_label:
                card_params["idLabels"] = team_label["id"]

    if assign_to:
        members = get_trello_members()
        if members:

            username = assign_to.split("(")[-1].strip(")")
            member = next((m for m in members if m["username"] == username), None)
            if member:
                card_params["idMembers"] = member["id"]

    res = requests.post("https://api.trello.com/1/cards", params=card_params)

    if res.status_code == 200:
        card = res.json()
        await ctx.respond(f"Card created: [{card['name']}]({card['shortUrl']})")
    else:
        await ctx.respond("Failed to create card.")


@bot.slash_command(name="move_card", description="Move a Trello card to another list")
async def move_card(
    ctx,
    card_name: Option(str, "Card name to move", autocomplete=card_name_autocomplete),
    target_list_name: Option(
        str, "Destination list name", autocomplete=list_name_autocomplete
    ),
):
    await ctx.defer()
    cards = get_trello_cards()
    lists = get_trello_lists()

    if not cards or not lists:
        await ctx.respond("Error fetching cards/lists.")
        return

    card = next((c for c in cards if c["name"].lower() == card_name.lower()), None)
    target_list = next(
        (l for l in lists if l["name"].lower() == target_list_name.lower()), None
    )

    if not card:
        await ctx.respond("Card not found.")
        return
    if not target_list:
        await ctx.respond("Target list not found.")
        return

    res = requests.put(
        f"https://api.trello.com/1/cards/{card['id']}",
        params={"key": TRELLO_KEY, "token": TRELLO_TOKEN, "idList": target_list["id"]},
    )

    if res.status_code == 200:
        await ctx.respond(f"Moved **{card_name}** to **{target_list_name}**.")
    else:
        await ctx.respond("Failed to move the card.")


@bot.slash_command(
    name="set_trello_name",
    description="Link your Trello username to your Discord account",
)
async def set_trello_name(ctx, trello_username: Option(str, "Your Trello username")):
    user_id = ctx.author.id
    user_trello_map[user_id] = trello_username
    await ctx.respond(f"Your Trello username has been set to **{trello_username}**.")


@bot.slash_command(name="assign_card", description="Assign yourself to a Trello card")
async def assign_card(ctx, card_name: Option(str, "Card name to assign")):
    await ctx.defer()
    cards = get_trello_cards()
    members = get_trello_members()

    if not cards or not members:
        await ctx.respond("Error fetching cards/members.")
        return

    card = next((c for c in cards if c["name"].lower() == card_name.lower()), None)
    if not card:
        await ctx.respond("Card not found.")
        return

    user_id = ctx.author.id
    preferred_trello_username = user_trello_map.get(user_id)
    discord_username = ctx.author.name

    member = next(
        (
            m
            for m in members
            if (
                preferred_trello_username
                and m["username"].lower() == preferred_trello_username.lower()
            )
            or (
                not preferred_trello_username
                and (
                    m["username"].lower() == discord_username.lower()
                    or discord_username.lower() in m["fullName"].lower()
                )
            )
        ),
        None,
    )

    if not member:
        await ctx.respond(
            "Your Trello username couldn't be resolved. Please use `/set_trello_name` to set it manually."
        )
        return

    res = requests.post(
        f"https://api.trello.com/1/cards/{card['id']}/idMembers",
        params={"key": TRELLO_KEY, "token": TRELLO_TOKEN, "value": member["id"]},
    )

    if res.status_code == 200:
        await ctx.respond(f"You've been assigned to **{card_name}**.")
    else:
        await ctx.respond("Failed to assign the card.")


@bot.slash_command(name="delete_card", description="Delete a Trello card")
async def delete_card(
    ctx,
    card_name: Option(str, "Card name to delete", autocomplete=card_name_autocomplete),
):
    await ctx.defer()
    cards = get_trello_cards()
    members = get_trello_members()

    if not cards or not members:
        await ctx.respond("Error fetching cards/members.")
        return

    card = next((c for c in cards if c["name"].lower() == card_name.lower()), None)
    if not card:
        await ctx.respond("Card not found.")
        return

    res = requests.delete(
        f"https://api.trello.com/1/cards/{card['id']}",
        params={"key": TRELLO_KEY, "token": TRELLO_TOKEN},
    )

    if res.status_code == 200:
        await ctx.respond(f"Card deleted: **{card_name}**.")


@bot.slash_command(name="trello_users", description="Show all Trello users")
async def trello_users(ctx):
    await ctx.defer()
    members = get_trello_members()
    if not members:
        await ctx.respond("Error fetching members.")
        return
    description = ""
    for member in members:
        description += f"• {member['fullName']} ({member['username']})\n"
    embed = discord.Embed(
        title="Trello Users",
        description=description or "No users found.",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(),
    )

    await ctx.respond(embed=embed)


@bot.event
async def on_member_join(member: discord.Member):

    welcome_message = f"Welcome {member.mention} to the server"
    try:
        await member.send(welcome_message)
    except discord.Forbidden:

        welcome_channel = discord.utils.get(member.guild.channels, name="general")
        if welcome_channel:
            await welcome_channel.send(f"{member.mention} {welcome_message}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(check_card_updates())


async def check_card_updates():

    import asyncio

    last_cards_state = {}

    cards = get_trello_cards()
    if cards:
        for card in cards:
            last_cards_state[card["id"]] = {
                "name": card["name"],
                "idList": card["idList"],
                "idMembers": card["idMembers"],
            }

    while True:
        await asyncio.sleep(300)

        try:
            current_cards = get_trello_cards()
            lists = get_trello_lists()
            members = get_trello_members()

            if not current_cards or not lists or not members:
                continue

            list_map = {lst["id"]: lst["name"] for lst in lists}
            member_map = {m["id"]: m["fullName"] for m in members}

            general_channel = discord.utils.get(bot.guilds[0].channels, name="general")
            if not general_channel:
                continue

            for card in current_cards:
                card_id = card["id"]

                if card_id not in last_cards_state:
                    await general_channel.send(
                        f"New card created: **{card['name']}** in list **{list_map.get(card['idList'], 'Unknown')}**"
                    )

                elif card["idList"] != last_cards_state[card_id]["idList"]:
                    old_list = list_map.get(
                        last_cards_state[card_id]["idList"], "Unknown"
                    )
                    new_list = list_map.get(card["idList"], "Unknown")
                    await general_channel.send(
                        f"Card moved: **{card['name']}** from **{old_list}** to **{new_list}**"
                    )

                elif set(card["idMembers"]) != set(
                    last_cards_state[card_id]["idMembers"]
                ):
                    new_members = set(card["idMembers"]) - set(
                        last_cards_state[card_id]["idMembers"]
                    )
                    for member_id in new_members:
                        member_name = member_map.get(member_id, "Unknown member")
                        await general_channel.send(
                            f"**{member_name}** was assigned to card **{card['name']}**"
                        )

                last_cards_state[card_id] = {
                    "name": card["name"],
                    "idList": card["idList"],
                    "idMembers": card["idMembers"],
                }

            for card_id in list(last_cards_state.keys()):
                if not any(c["id"] == card_id for c in current_cards):
                    await general_channel.send(
                        f"Card deleted: **{last_cards_state[card_id]['name']}**"
                    )
                    del last_cards_state[card_id]

        except Exception as e:
            print(f"Error checking for card updates: {e}")


bot.run(DISCORD_TOKEN)
