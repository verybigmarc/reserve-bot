import os
import json
import discord
from discord.ext import commands
import difflib

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# File paths
CONFIG_PATH = "data/config.json"
RESERVATIONS_PATH = "data/reservations.json"

# Load JSON files
def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# Reservation data
def get_reservations():
    return load_json(RESERVATIONS_PATH, [])

def save_reservations(data):
    save_json(RESERVATIONS_PATH, data)

def get_config():
    return load_json(CONFIG_PATH, {})

def save_config(data):
    save_json(CONFIG_PATH, data)

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

def build_reservation_text():
    reservations = get_reservations()
    res_dict = {r["country"]: r["user_id"] for r in reservations}

    def status(country):
        return f"{country} – <@{res_dict[country]}>" if country in res_dict else f"{country} – available"

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

    text = "# SATURDAY HISTO RESERVATION SHEET\n📋\n\nThe Host will always try to honor reservations if possible...\n"
    for title, countries in sections.items():
        text += f"\n{title}\n"
        text += "\n".join(status(c) for c in countries) + "\n"
    return text[:2000]

async def update_reservation_message():
    config = get_config()
    if not config.get("channel_id") or not config.get("message_id"):
        return
    channel = bot.get_channel(config["channel_id"])
    if not channel:
        return
    try:
        message = await channel.fetch_message(config["message_id"])
        await message.edit(content=build_reservation_text())
    except Exception as e:
        print("Update failed:", e)

@bot.event
async def on_ready():
    print(f"{bot.user} is online!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    config = get_config()
    config["channel_id"] = ctx.channel.id
    save_config(config)
    await ctx.send(f"✅ Reservation channel set to {ctx.channel.mention}")

@bot.command()
async def startlist(ctx):
    config = get_config()
    if ctx.channel.id != config.get("channel_id"):
        await ctx.send("❌ Use this in the configured reservation channel.")
        return
    message = await ctx.send(build_reservation_text())
    config["message_id"] = message.id
    save_config(config)
    await ctx.send("✅ Reservation list started.")

@bot.command()
async def reserve(ctx, *, country_input):
    config = get_config()
    if ctx.channel.id != config.get("channel_id"):
        await ctx.send("❌ Use this in the reservation channel.")
        return

    reservations = get_reservations()
    if any(r["user_id"] == ctx.author.id for r in reservations):
        await ctx.send("❌ You already have a reservation.")
        return

    norm_input = normalize(country_input)
    slots_map = {normalize(s): s for s in reservable_slots}
    match = difflib.get_close_matches(norm_input, slots_map.keys(), n=1, cutoff=0.6)
    if not match:
        await ctx.send("❌ Country not recognized.")
        return

    chosen = slots_map[match[0]]
    if any(r["country"] == chosen for r in reservations):
        await ctx.send(f"❌ {chosen} is already reserved.")
        return

    reservations.append({"user_id": ctx.author.id, "country": chosen})
    save_reservations(reservations)
    await ctx.send(f"{ctx.author.mention} has reserved {chosen} ✅")
    await update_reservation_message()

@bot.command()
async def cancel(ctx):
    reservations = get_reservations()
    new_res = [r for r in reservations if r["user_id"] != ctx.author.id]
    if len(new_res) == len(reservations):
        await ctx.send("❌ You don't have a reservation.")
        return
    save_reservations(new_res)
    await ctx.send("✅ Your reservation has been cancelled.")
    await update_reservation_message()

@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx):
    save_reservations([])
    await ctx.send("🧹 All reservations cleared.")
    await update_reservation_message()

@bot.command()
@commands.has_permissions(administrator=True)
async def cleanbelow(ctx):
    config = get_config()
    if ctx.channel.id != config.get("channel_id"):
        await ctx.send("❌ Use this in the reservation channel.")
        return
    after_id = config.get("message_id")
    if not after_id:
        await ctx.send("❌ No message to clean under.")
        return

    deleted = 0
    async for msg in ctx.channel.history(after=discord.Object(id=after_id)):
        if not msg.author.bot:
            try:
                await msg.delete()
                deleted += 1
            except:
                continue
    await ctx.send(f"🧹 Deleted {deleted} messages below the list.")

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    config = get_config()
    if message.channel.id == config.get("channel_id") and message.id != config.get("message_id"):
        if not message.author.bot:
            try:
                await message.delete()
            except:
                pass

bot.run(os.getenv("DISCORD_TOKEN"))
