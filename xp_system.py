import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os
import math
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import aiohttp

MEMORY_FILE = "memory.json"

XP_PER_MESSAGE = 8
DAILY_XP = 80
WEEKLY_XP = 350
STREAK_BONUS = 15

def get_xp_for_level(level: int) -> int:
    return 250 * (level ** 2)

def get_level_from_xp(xp: int) -> int:
    return int(math.sqrt(xp / 250)) + 1

def get_progress(xp: int):
    level = get_level_from_xp(xp)
    current_level_xp = get_xp_for_level(level - 1)
    next_level_xp = get_xp_for_level(level)
    progress_xp = xp - current_level_xp
    needed = next_level_xp - current_level_xp
    percent = (progress_xp / needed) * 100 if needed > 0 else 100
    return progress_xp, needed, percent

def make_progress_bar(percent: float, length: int = 12) -> str:
    filled = int(percent / 100 * length)
    return "█" * filled + "░" * (length - filled)

RANK_TITLES = {
    1: "Newcomer",
    3: "Acquaintance",
    5: "Regular Guest",
    8: "Trusted Visitor",
    12: "House Friend",
    16: "Valued Associate",
    20: "Bat-Family Ally",
    25: "Wayne Manor Regular",
    30: "Alfred's Favourite",
    40: "Distinguished Guest",
    50: "Legendary Companion"
}

def get_rank_title(level: int) -> str:
    title = "Newcomer"
    for lvl, name in sorted(RANK_TITLES.items()):
        if level >= lvl:
            title = name
    return title

ACHIEVEMENTS = {
    "first_steps": {"name": "First Steps", "description": "Spoke with Alfred for the first time", "emoji": "☕"},
    "level_5": {"name": "Rising Through the Ranks", "description": "Reached Level 5", "emoji": "📈"},
    "level_10": {"name": "Respected Guest", "description": "Reached Level 10", "emoji": "🎩"},
    "level_20": {"name": "Bat-Family Ally", "description": "Reached Level 20", "emoji": "🦇"},
    "streak_7": {"name": "Weekly Dedication", "description": "Maintained a 7-day streak", "emoji": "🔥"},
    "streak_30": {"name": "Unwavering Loyalty", "description": "Maintained a 30-day streak", "emoji": "💎"},
    "daily_10": {"name": "Creature of Habit", "description": "Claimed daily reward 10 times", "emoji": "📅"},
    "coffee_lover": {"name": "Coffee Connoisseur", "description": "Asked Alfred for coffee 15 times", "emoji": "☕"}
}

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_xp_data(user_id: str):
    memory = load_memory()
    if user_id not in memory:
        memory[user_id] = {}
    data = memory[user_id]
    data.setdefault("xp", 0)
    data.setdefault("level", 1)
    data.setdefault("last_daily", None)
    data.setdefault("last_weekly", None)
    data.setdefault("streak", 0)
    data.setdefault("last_active_date", None)
    data.setdefault("achievements", [])
    data.setdefault("daily_claims", 0)
    data.setdefault("coffee_count", 0)
    data.setdefault("total_messages_to_alfred", 0)
    return data, memory

def add_xp(user_id: str, amount: int):
    data, memory = get_user_xp_data(user_id)
    old_level = get_level_from_xp(data["xp"])
    data["xp"] += amount
    new_level = get_level_from_xp(data["xp"])
    data["level"] = new_level

    if new_level >= 5 and "level_5" not in data["achievements"]:
        data["achievements"].append("level_5")
    if new_level >= 10 and "level_10" not in data["achievements"]:
        data["achievements"].append("level_10")
    if new_level >= 20 and "level_20" not in data["achievements"]:
        data["achievements"].append("level_20")

    memory[user_id] = data
    save_memory(memory)
    return data, new_level > old_level, new_level

def update_streak(user_id: str):
    data, memory = get_user_xp_data(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    last = data.get("last_active_date")

    if last == today:
        return data

    if last:
        last_date = datetime.strptime(last, "%Y-%m-%d")
        diff = (datetime.now() - last_date).days
        if diff == 1:
            data["streak"] += 1
        elif diff > 1:
            data["streak"] = 1
    else:
        data["streak"] = 1

    data["last_active_date"] = today

    if data["streak"] >= 7 and "streak_7" not in data["achievements"]:
        data["achievements"].append("streak_7")
    if data["streak"] >= 30 and "streak_30" not in data["achievements"]:
        data["achievements"].append("streak_30")

    memory[user_id] = data
    save_memory(memory)
    return data

async def create_profile_card(user: discord.User, data: dict) -> BytesIO:
    level = data["level"]
    xp = data["xp"]
    progress_xp, needed, percent = get_progress(xp)
    title = get_rank_title(level)
    streak = data.get("streak", 0)

    width, height = 900, 320
    img = Image.new("RGBA", (width, height), (20, 20, 30, 255))
    draw = ImageDraw.Draw(img)

    for i in range(height):
        r = int(20 + i * 0.05)
        g = int(20 + i * 0.04)
        b = int(35 + i * 0.08)
        draw.line([(0, i), (width, i)], fill=(r, g, b, 255))

    draw.rounded_rectangle([15, 15, width-15, height-15], radius=20, outline=(80, 80, 120, 180), width=2)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(user.display_avatar.url)) as resp:
                avatar_data = await resp.read()
        avatar = Image.open(BytesIO(avatar_data)).convert("RGBA").resize((160, 160))
        
        mask = Image.new("L", (160, 160), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 160, 160), fill=255)
        avatar.putalpha(mask)
        
        img.paste(avatar, (40, 70), avatar)
    except:
        draw.ellipse([40, 70, 200, 230], fill=(60, 60, 80))

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((230, 50), user.display_name, font=font_large, fill=(240, 240, 255))
    draw.text((230, 100), f"Level {level}  •  {title}", font=font_medium, fill=(180, 180, 220))
    draw.text((230, 140), f"Total XP: {xp:,}", font=font_small, fill=(160, 160, 190))
    draw.text((230, 170), f"Streak: {streak} days", font=font_small, fill=(160, 160, 190))

    bar_x, bar_y = 230, 230
    bar_width, bar_height = 600, 28
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], radius=14, fill=(40, 40, 60))
    
    fill_width = int(bar_width * (percent / 100))
    if fill_width > 0:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_width, bar_y + bar_height], radius=14, fill=(100, 140, 255))

    draw.text((bar_x, bar_y - 28), f"{progress_xp:,} / {needed:,} XP  ({percent:.1f}%)", font=font_small, fill=(200, 200, 230))

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

async def create_simple_card(title: str, lines: list) -> BytesIO:
    width, height = 700, 280
    img = Image.new("RGBA", (width, height), (18, 18, 28, 255))
    draw = ImageDraw.Draw(img)

    for i in range(height):
        r = int(18 + i * 0.04)
        g = int(18 + i * 0.03)
        b = int(28 + i * 0.07)
        draw.line([(0, i), (width, i)], fill=(r, g, b, 255))

    draw.rounded_rectangle([12, 12, width-12, height-12], radius=18, outline=(70, 70, 110, 180), width=2)

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    draw.text((40, 35), title, font=font_title, fill=(230, 230, 255))

    y = 95
    for line in lines:
        draw.text((40, y), line, font=font_text, fill=(190, 190, 220))
        y += 38

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

class XPSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rank", description="Shows your current level and rank")
    async def rank(self, interaction: discord.Interaction):
        data, _ = get_user_xp_data(str(interaction.user.id))
        level = data["level"]
        xp = data["xp"]
        progress_xp, needed, percent = get_progress(xp)
        title = get_rank_title(level)
        bar = make_progress_bar(percent)

        embed = discord.Embed(title=f"🎩 {interaction.user.display_name}'s Rank", color=0x1a1a2e)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="Title", value=f"*{title}*", inline=True)
        embed.add_field(name="Total XP", value=f"**{xp:,}**", inline=True)
        embed.add_field(name="Progress", value=f"`{bar}` **{percent:.1f}%**\n{progress_xp:,} / {needed:,} XP", inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="Alfred Pennyworth • Always keeping score")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="level", description="Detailed information about your XP")
    async def level(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data, _ = get_user_xp_data(str(interaction.user.id))
        level = data["level"]
        xp = data["xp"]
        progress_xp, needed, percent = get_progress(xp)
        title = get_rank_title(level)

        lines = [
            f"Level {level}  •  {title}",
            f"Total XP: {xp:,}",
            f"Progress: {progress_xp:,} / {needed:,} XP",
            f"{percent:.1f}% to next level"
        ]

        card = await create_simple_card("XP Information", lines)
        file = discord.File(card, filename="level.png")
        await interaction.followup.send(file=file)

    @app_commands.command(name="leaderboard", description="Server XP ranking")
    async def leaderboard(self, interaction: discord.Interaction):
        memory = load_memory()
        ranking = []
        for user_id, data in memory.items():
            xp = data.get("xp", 0)
            if xp > 0:
                ranking.append((user_id, xp, data.get("level", 1)))
        ranking.sort(key=lambda x: x[1], reverse=True)
        ranking = ranking[:10]

        if not ranking:
            await interaction.response.send_message("No one has earned XP yet, sir.")
            return

        description = ""
        medals = ["🥇", "🥈", "🥉"]
        for i, (user_id, xp, level) in enumerate(ranking):
            try:
                user = await self.bot.fetch_user(int(user_id))
                name = user.display_name
            except:
                name = f"User {user_id}"
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            title = get_rank_title(level)
            description += f"{medal} **{name}** — Level {level} ({title})\n`{xp:,} XP`\n\n"

        embed = discord.Embed(title="🏆 Server Leaderboard", description=description, color=0x1a1a2e)
        embed.set_footer(text="Alfred Pennyworth • Excellence is noted")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim your daily XP reward")
    async def daily(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data, memory = get_user_xp_data(user_id)
        today = datetime.now().strftime("%Y-%m-%d")

        if data.get("last_daily") == today:
            await interaction.response.send_message("You have already claimed your daily reward today, sir.", ephemeral=True)
            return

        await interaction.response.defer()

        update_streak(user_id)
        data, _ = get_user_xp_data(user_id)

        bonus = data["streak"] * STREAK_BONUS
        total = DAILY_XP + bonus

        data["last_daily"] = today
        data["daily_claims"] = data.get("daily_claims", 0) + 1
        memory[user_id] = data
        save_memory(memory)

        result, leveled_up, new_level = add_xp(user_id, total)

        if data["daily_claims"] >= 10 and "daily_10" not in data["achievements"]:
            data["achievements"].append("daily_10")
            memory[user_id] = data
            save_memory(memory)

        lines = [
            f"+{total} XP received",
            f"Streak bonus: +{bonus} XP",
            f"Current streak: {data['streak']} days"
        ]

        if leveled_up:
            lines.append(f"Level up! You are now Level {new_level}")

        card = await create_simple_card("Daily Reward", lines)
        file = discord.File(card, filename="daily.png")
        await interaction.followup.send("Your daily allowance, sir.", file=file)

    @app_commands.command(name="weekly", description="Claim your weekly XP reward")
    async def weekly(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data, memory = get_user_xp_data(user_id)
        week_id = datetime.now().strftime("%Y-W%W")

        if data.get("last_weekly") == week_id:
            await interaction.response.send_message("You have already claimed your weekly reward this week, sir.", ephemeral=True)
            return

        data["last_weekly"] = week_id
        memory[user_id] = data
        save_memory(memory)

        result, leveled_up, new_level = add_xp(user_id, WEEKLY_XP)

        embed = discord.Embed(title="📦 Weekly Reward Claimed", description=f"A more substantial reward, as befits the occasion.\n\n**+{WEEKLY_XP} XP**", color=0x9b59b6)
        if leveled_up:
            embed.add_field(name="🎉 Level Up!", value=f"You are now **Level {new_level}**!", inline=False)
        embed.set_footer(text="Alfred Pennyworth • A reward for your continued presence")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="streak", description="Shows your current activity streak")
    async def streak(self, interaction: discord.Interaction):
        data, _ = get_user_xp_data(str(interaction.user.id))
        streak = data.get("streak", 0)

        embed = discord.Embed(title="🔥 Activity Streak", description=f"**{interaction.user.display_name}** currently has a streak of **{streak} day{'s' if streak != 1 else ''}**.", color=0xe67e22)
        if streak >= 7:
            embed.add_field(name="Status", value="Impressive dedication.", inline=False)
        elif streak >= 3:
            embed.add_field(name="Status", value="Building good habits.", inline=False)
        else:
            embed.add_field(name="Status", value="A modest beginning. Do keep it up.", inline=False)
        embed.set_footer(text="Alfred Pennyworth • Consistency builds character")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="achievements", description="Shows your unlocked achievements")
    async def achievements(self, interaction: discord.Interaction):
        data, _ = get_user_xp_data(str(interaction.user.id))
        unlocked = data.get("achievements", [])

        if not unlocked:
            await interaction.response.send_message("You haven't unlocked any achievements yet, sir. Perhaps more time spent in productive conversation would help.", ephemeral=True)
            return

        description = ""
        for key in unlocked:
            if key in ACHIEVEMENTS:
                ach = ACHIEVEMENTS[key]
                description += f"{ach['emoji']} **{ach['name']}**\n{ach['description']}\n\n"

        embed = discord.Embed(title="🏅 Achievements", description=description, color=0xf1c40f)
        embed.set_footer(text=f"{len(unlocked)}/{len(ACHIEVEMENTS)} unlocked • Alfred Pennyworth")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="Shows your complete profile card")
    async def profile(self, interaction: discord.Interaction):
        await interaction.response.defer()
        data, _ = get_user_xp_data(str(interaction.user.id))
        card = await create_profile_card(interaction.user, data)
        file = discord.File(card, filename="profile.png")
        await interaction.followup.send(file=file)

async def setup(bot):
    await bot.add_cog(XPSystem(bot))
