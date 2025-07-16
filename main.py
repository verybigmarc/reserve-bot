import os
import discord
from discord.ext import commands
import difflib
from pymongo import MongoClient

TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

# Ensure MongoDB connection is valid
try:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    client.server_info()
except Exception as e:
    print("❌ Failed to connect to MongoDB:", e)
    exit(1)

db = client["hoi4_reservations"]
reservations_col = db["reservations"]
config_col = db["config"]

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

reservable_slots = [
    "🇩🇪 Germany", "🇩🇪 Germany (coop)", "🇩🇪 Germany (coop 2)",
    "🇮🇹 Italy", "🇮🇹 Italy (coop)",
    "🇯🇵 Japan", "🇯🇵 Japan (coop)", "🇯🇵 Japan (coop 2)",
    "🇷🇴 Romania", "🇭🇺 Hungary", "🇧🇬 Bulgaria", "🇪🇸 Spain", "🇫🇮 Finland",
    "🇬🇧 UK", "🇬🇧 UK (coop)",
    "🇺🇸 USA", "🇺🇸 USA (coop)",
    "🇫🇷 France",
    "🇷🇺 USSR", "🇷🇺 USSR (coop)", "🇷🇺 USSR (coop 2)",
    "🇨🇦 Canada", "🇮🇳 India", "🇦🇺 Australia", "🇿🇦 South Africa",
    "🇲🇽 Mexico", "🇧🇷 Brazil", "🇵🇭 Philippines",
    "Filler 1", "Filler 2", "Filler 3", "Filler 4", "Filler 5"
]

def normalize(text):
    return ''.join(filter(str.isalnum, text.lower()))

def get_config():
    return config_col.find_one({"_id": "settings"}) or {}

def set_config(data):
    config_col.update_one({"_id": "settings"}, {"$set": data}, upsert=True)

def build_reservation_text():
    all_reservations = {r["country"]: r["user_id"] for r in reservations_col.find()}
    def status(c):
        user_id = all_reservations.get(c)
        return f"{c} – <@{user_id}>" if user_id else f"{c} – available"

    sections = {
        "**AXIS MAJORS:**": [
            "🇩🇪 Germany", "🇩🇪 Germany (coop)", "🇩🇪 Germany (coop 2)",
            "🇮🇹 Italy", "🇮🇹 Italy (coop)",
            "🇯🇵 Japan", "🇯🇵 Japan (coop)", "🇯🇵 Japan (coop 2)"
        ],
        "**AXIS MINORS:**": [
            "🇷🇴 Romania", "🇭🇺 Hungary", "🇧🇬 Bulgaria", "🇪🇸 Spain", "🇫🇮 Finland"
        ],
        "**ALLIED MAJORS:**": [
            "🇬🇧 UK", "🇬🇧 UK (coop)",
            "🇺🇸 USA", "🇺🇸 USA (coop)",
            "🇫🇷 France",
            "🇷🇺 USSR", "🇷🇺 USSR (coop)", "🇷🇺 USSR (coop 2)"
        ],
        "**ALLIED MINORS:**": [
            "🇨🇦 Canada", "🇮🇳 India", "🇦🇺 Australia", "🇿🇦 South Africa",
            "🇲🇽 Mexico", "🇧🇷 Brazil", "🇵🇭 Philippines"
        ],
        "**FILLER:**": [
            "Filler 1", "Filler 2", "Filler 3", "Filler 4", "Filler 5"
        ]
    }

    text = """# SATURDAY HISTO RESERVATION SHEET
📋

The Host will always try to honor reservations if possible, however sometimes players will be moved for a more balanced lobby, in such cases please be understanding and comply.

~ Minimum Player count to start: 7 (all majors)  
~ Maximum Player capacity: 28 (coops included)
"""
    for title, countries in sections.items():
        text += f"\n{title}\n"
        text += "\n".join([status(c) for c in countries]) + "\n"
    return text

def safe_build_reservation_text():
    text = build_reservation_text()
    if len(text) <= 2000:
        return text
    lines = text.splitlines()
    result = ""
    for line in lines:
        if len(result) + len(line) + 1 > 2000:
            break
        result += line + "\n"
    return result

async def update_reservation_message():
    config = get_config()
    channel_id = config.get("channel_id")
    message_id = config.get("message_id")
    if not channel_id or not message_id:
        return
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    try:
        message = await channel.fetch_message(message_id)
        await message.edit(content=safe_build_reservation_text())
    except Exception as e:
        print("Failed to update reservation message:", e)

@bot.event
async def on_ready():
    print(f"{bot.user} is online!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    set_config({"channel_id": ctx.channel.id})
    await ctx.send(f"✅ Reservation channel set to {ctx.channel.mention}")

@bot.command()
async def startlist(ctx):
    config = get_config()
    if config.get("channel_id") != ctx.channel.id:
        await ctx.send("❌ This isn't the configured reservation channel. Use `!setchannel` to set it.")
        return
    message = await ctx.send(safe_build_reservation_text())
    set_config({"channel_id": ctx.channel.id, "message_id": message.id})
    await ctx.send("✅ Reservation list started.")

@bot.command(aliases=["r"])
async def reserve(ctx, *, country_input):
    config = get_config()
    if ctx.channel.id != config.get("channel_id"):
        await ctx.send("❌ Please use this command in the reservation channel.")
        return

    user_id = ctx.author.id
    existing = reservations_col.find_one({"user_id": user_id})
    if existing:
        await ctx.send(f"{ctx.author.mention}, you already reserved: {existing['country']}")
        return

    normalized_input = normalize(country_input)
    normalized_slots = {normalize(slot): slot for slot in reservable_slots}
    matches = difflib.get_close_matches(normalized_input, normalized_slots.keys(), n=1, cutoff=0.6)
    if not matches:
        await ctx.send("❌ Country not recognized. Please try again.")
        return
    matched_country = normalized_slots[matches[0]]
    if reservations_col.find_one({"country": matched_country}):
        await ctx.send(f"{matched_country} is already reserved.")
        return

    reservations_col.insert_one({"user_id": user_id, "country": matched_country})
    await ctx.send(f"{ctx.author.mention} has reserved {matched_country} ✅")
    await update_reservation_message()

@bot.command()
async def cancel(ctx):
    config = get_config()
    if ctx.channel.id != config.get("channel_id"):
        await ctx.send("❌ Please use this command in the reservation channel.")
        return
    result = reservations_col.delete_one({"user_id": ctx.author.id})
    if result.deleted_count == 0:
        await ctx.send("You have no reservation to cancel.")
        return
    await ctx.send(f"{ctx.author.mention}'s reservation has been cancelled ❌")
    await update_reservation_message()

@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx):
    config = get_config()
    if ctx.channel.id != config.get("channel_id"):
        await ctx.send("❌ Please use this command in the reservation channel.")
        return
    reservations_col.delete_many({})
    await ctx.send("All reservations cleared 🧹")
    await update_reservation_message()

@bot.command()
@commands.has_permissions(administrator=True)
async def cleanbelow(ctx):
    config = get_config()
    if ctx.channel.id != config.get("channel_id"):
        await ctx.send("❌ This isn't the reservation channel.")
        return
    message_id = config.get("message_id")
    if not message_id:
        await ctx.send("❌ Reservation message not found.")
        return
    deleted = 0
    async for msg in ctx.channel.history(after=discord.Object(id=message_id), limit=100):
        if not msg.author.bot:
            try:
                await msg.delete()
                deleted += 1
            except:
                pass
    await ctx.send(f"🧹 Deleted {deleted} messages below the reservation list.")

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    config = get_config()
    if message.channel.id == config.get("channel_id"):
        if config.get("message_id") and message.id != config["message_id"] and not message.author.bot:
            try:
                await message.delete()
            except:
                pass

bot.run(TOKEN)
