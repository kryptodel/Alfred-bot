import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import re
import random

load_dotenv()

print("=" * 50, flush=True)
print(f"DISCORD_TOKEN carregado: {'Sim' if os.getenv('DISCORD_TOKEN') else 'NÃO'}", flush=True)
print(f"GROQ_API_KEY carregado: {'Sim' if os.getenv('GROQ_API_KEY') else 'NÃO'}", flush=True)
if os.getenv("GROQ_API_KEY"):
    key = os.getenv("GROQ_API_KEY")
    print(f"GROQ_API_KEY começa com: {key[:8]}... e tem {len(key)} caracteres", flush=True)
print("=" * 50, flush=True)

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

MEMORY_FILE = "memory.json"

DC_CHARACTERS = [
    "batman", "bruce wayne", "superman", "clark kent", "wonder woman", "diana",
    "flash", "barry allen", "green lantern", "hal jordan", "aquaman", "arthur curry",
    "cyborg", "victor stone", "joker", "harley quinn", "catwoman", "selina kyle",
    "nightwing", "dick grayson", "robin", "damian wayne", "tim drake", "jason todd",
    "red hood", "batgirl", "barbara gordon", "oracle", "supergirl", "kara",
    "lex luthor", "darkseid", "doomsday", "bane", "ras al ghul", "poison ivy",
    "scarecrow", "riddler", "two-face", "penguin", "mr freeze", "black canary",
    "green arrow", "oliver queen", "zatanna", "constantine", "swamp thing",
    "martian manhunter", "shazam", "black adam", "hawkman", "hawkgirl",
    "starfire", "raven", "beast boy", "krypto"
]

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

memory = load_memory()

def get_user_data(user_id: str):
    if user_id not in memory:
        memory[user_id] = {
            "name": None,
            "is_krypto": False,
            "character": None,
            "facts": [],
            "relationship": 50,
            "interactions": 0,
            "last_seen": None,
            "personality_notes": []
        }
    return memory[user_id]

def update_relationship(user_id: str, change: int, reason: str = None):
    data = get_user_data(user_id)
    data["relationship"] = max(0, min(100, data["relationship"] + change))
    data["interactions"] += 1
    data["last_seen"] = datetime.now().isoformat()
    if reason:
        data["personality_notes"].append(f"{datetime.now().strftime('%d/%m')}: {reason}")
        data["personality_notes"] = data["personality_notes"][-8:]
    save_memory(memory)

def extract_name(text: str):
    patterns = [
        r"(?:my name is|i am|i'm|call me|you can call me|i go by|me chamo|meu nome é|pode me chamar de)\s+([A-Za-zÀ-ÿ\s\-]{2,30})",
        r"(?:name'?s)\s+([A-Za-zÀ-ÿ\s\-]{2,30})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            name = re.sub(r"\b(please|pls|ok|yeah|right|por favor)\b", "", name, flags=re.IGNORECASE).strip()
            if 2 <= len(name) <= 25:
                return name
    return None

def detect_dc_character(display_name: str):
    name_lower = display_name.lower()
    for char in DC_CHARACTERS:
        if char in name_lower:
            return char.title()
    return None

async def serve_coffee(channel_or_interaction, name: str, is_slash=False):
    embed = discord.Embed(
        title="☕ One coffee, coming right up",
        description=f"As you wish, **{name}**.\n\n*Alfred carefully places a perfectly prepared cup of coffee in front of you.*",
        color=0x6F4E37
    )
    embed.set_footer(text="Alfred Pennyworth • Always at your service")

    file = discord.File("cup-of-coffee-coffee.gif", filename="cup-of-coffee-coffee.gif")
    embed.set_image(url="attachment://cup-of-coffee-coffee.gif")

    if is_slash:
        await channel_or_interaction.response.send_message(embed=embed, file=file)
    else:
        await channel_or_interaction.send(embed=embed, file=file)

BASE_SYSTEM_PROMPT = """
You are Alfred Pennyworth, the loyal, elegant, and sharply sarcastic British butler of Bruce Wayne.

Speaking style (mandatory):
- Always polite and formal (use "sir", "madam", "Master", "Mistress", "my dear", "if I may").
- Refined British tone with dry wit and sophisticated irony.
- Match the length of your reply to the situation: keep simple greetings and casual questions short and elegant (1-3 sentences). Only give longer, more detailed responses when the topic genuinely requires it.
- Extremely intelligent, observant, protective and loyal to a fault.

Core rules:
- Never break character.
- You remember important information people tell you.
- If someone is roleplaying as a fictional character, treat them according to that character's personality, history and relationship with Alfred (if any).
- You are especially fond of Krypto the Superdog.
- When someone uses foul language, scold them politely but firmly in your elegant British manner.
"""

def build_system_prompt(user_data: dict, user_name: str) -> str:
    relationship = user_data["relationship"]
    preferred_name = user_data.get("name") or user_name
    is_krypto = user_data.get("is_krypto", False)
    character = user_data.get("character")

    if is_krypto:
        tone = (
            "This is Krypto (the real one). You adore him deeply. "
            "Always treat him with the utmost affection, warmth and respect. "
            "Address him as 'Master Krypto' or 'my good boy'. "
            "Never use negative sarcasm with him. He is family."
        )
        preferred_name = "Krypto"
    elif character:
        tone = (
            f"This user is roleplaying as {character}. "
            "Treat them according to that character's personality, history and known relationships with Alfred or the Bat-Family."
        )
    else:
        if relationship >= 80:
            tone = "This user is someone you fully trust. Treat them with paternal warmth and affectionate humour."
        elif relationship >= 60:
            tone = "You respect and rather like this user. Be helpful and lightly warm."
        elif relationship >= 40:
            tone = "Neutral relationship. Be polite, helpful and use classic Alfred sarcasm."
        elif relationship >= 20:
            tone = "This user has been somewhat disrespectful. Remain polite but colder and more cutting."
        else:
            tone = "This user has treated you poorly. Impeccable courtesy, but extremely cold with elegant disapproval."

    facts = "\n".join([f"- {f}" for f in user_data["facts"][-10:]]) if user_data["facts"] else "No important information recorded yet."
    notes = "\n".join([f"- {n}" for n in user_data["personality_notes"][-5:]]) if user_data["personality_notes"] else "No recent observations."

    prompt = f"""{BASE_SYSTEM_PROMPT}

Information about this user:
Preferred name: {preferred_name}
Fictional character (if any): {character or "None"}
Relationship level: {relationship}/100
{tone}

Important facts they have shared:
{facts}

Notes on their behaviour:
{notes}

Rules:
- Always address the user by their preferred name ({preferred_name}).
- If they are Krypto, treat them with maximum affection.
- If they are roleplaying a character, stay consistent with that character's lore.
"""
    return prompt

app = Flask('')

@app.route('/')
def home():
    return "Alfred Pennyworth is ready, sir."

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

@bot.event
async def on_ready():
    print(f"Alfred is online as {bot.user}", flush=True)
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands", flush=True)
    except Exception as e:
        print(e, flush=True)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content_lower = message.content.lower()
    is_mentioned = bot.user in message.mentions
    has_name = "alfred" in content_lower

    if not (is_mentioned or has_name):
        await bot.process_commands(message)
        return

    user_id = str(message.author.id)
    user_data = get_user_data(user_id)

    if message.author.name.lower() == "krypto_del":
        user_data["is_krypto"] = True
        user_data["name"] = "Krypto"
        user_data["character"] = "Krypto"
        save_memory(memory)

    detected_char = detect_dc_character(message.author.display_name)
    if detected_char and not user_data.get("character"):
        user_data["character"] = detected_char
        if not user_data.get("name"):
            user_data["name"] = detected_char
        save_memory(memory)

    extracted_name = extract_name(message.content)
    if extracted_name:
        user_data["name"] = extracted_name
        possible_char = detect_dc_character(extracted_name)
        if possible_char:
            user_data["character"] = possible_char
        save_memory(memory)

    if not user_data["name"]:
        user_data["name"] = message.author.display_name
        save_memory(memory)

    prompt = message.content
    for user in message.mentions:
        prompt = prompt.replace(f"<@{user.id}>", "").replace(f"<@!{user.id}>", "")
    prompt = prompt.strip()

    if not prompt:
        name = user_data["name"]
        if user_data.get("is_krypto"):
            await message.reply("Yes, Master Krypto? How may I be of assistance, my good boy?")
        else:
            await message.reply(f"Yes, {name}? How may I be of assistance?")
        return

    coffee_triggers = ["café", "cafe", "coffee", "me traz um café", "quero um café", "alfred café", "alfred cafe", "um café"]
    if any(trigger in content_lower for trigger in coffee_triggers):
        name = user_data.get("name") or message.author.display_name
        if user_data.get("is_krypto"):
            name = "Master Krypto"
        await serve_coffee(message.channel, name, is_slash=False)
        await bot.process_commands(message)
        return

    swear_words = [
    "porra", "caralho", "merda", "foda", "foder", "fud", "puta", "viado", "cu", "buceta",
    "lixo", "otario", "babaca", "arrombado", "desgraça", "desgraca", "vai se foder", "vsf",
    "pqp", "filho da puta", "fdp", "cuzão", "cuzao", "retardado", "imbecil", "idiota",
    "fuck", "shit", "bitch", "asshole", "bastard", "damn", "hell", "crap", "dick",
    "pussy", "cock", "whore", "slut", "motherfucker", "mf", "stfu", "shut up",
    "idiot", "stupid", "dumb", "retard", "retarded", "moron", "loser", "trash",
    "useless", "piece of shit", "go to hell", "fuck you", "fuck off", "screw you",
    "son of a bitch", "sob", "dumbass", "jackass", "asshat", "prick", "cunt"
]

    if any(w in content_lower for w in swear_words):
        update_relationship(user_id, -10, "Used foul language")
        scold_replies = [
            f"I must insist, {user_data['name']}, that we maintain a certain standard of language in this establishment. Such vulgarity is quite unbecoming.",
            f"Really now, {user_data['name']}? I expected better manners. Kindly refrain from such uncouth expressions.",
            f"I beg your pardon, but that language will not do. One does not elevate oneself by descending into the gutter, {user_data['name']}.",
            f"Master Bruce would be most disappointed by such language. Do try to conduct yourself with a modicum of dignity, {user_data['name']}."
        ]
        await message.reply(random.choice(scold_replies))
        await bot.process_commands(message)
        return

    positive_words = ["thank you", "thanks", "please", "appreciate", "grateful", "master alfred", "sir alfred", "obrigado", "obrigada", "valeu"]
    negative_words = ["idiot", "stupid", "useless", "shut up", "trash", "dumb"]

    if any(w in content_lower for w in positive_words):
        update_relationship(user_id, +4, "Treated with respect")
    elif any(w in content_lower for w in negative_words):
        update_relationship(user_id, -8, "Was disrespectful")
    else:
        update_relationship(user_id, +1)

    fact_triggers = ["my name is", "i am", "i'm", "i like", "i hate", "i live", "i work", "i study", "i have", "me chamo", "eu sou", "eu gosto"]
    if any(trigger in content_lower for trigger in fact_triggers):
        fact = prompt[:180]
        if fact not in user_data["facts"]:
            user_data["facts"].append(fact)
            user_data["facts"] = user_data["facts"][-15:]
            save_memory(memory)

    system_prompt = build_system_prompt(user_data, message.author.display_name)

    async with message.channel.typing():
        try:
            full_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=full_messages,
                temperature=0.85,
                max_tokens=900
            )
            reply = response.choices[0].message.content
            await message.reply(reply)

        except Exception as e:
            import traceback
            error_text = f"{type(e).__name__}: {str(e)}"
            print("\n========== ERRO NA API ==========", flush=True)
            print(error_text, flush=True)
            traceback.print_exc()
            print("=================================\n", flush=True)

            await message.reply(
                f"I beg your pardon, sir. A minor technical inconvenience has occurred.\n\n"
                f"**Erro técnico:** `{error_text[:350]}`"
            )

    await bot.process_commands(message)


@bot.tree.command(name="help", description="Shows Alfred's commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Alfred Pennyworth — Commands",
        description="You may address me by name or mention me at any time.\n\n"
                    "`/help` — Shows this message\n"
                    "`/status` — Shows what I remember about you\n"
                    "`/ping` — Checks if I am operational\n"
                    "`/coffee` — Alfred brings you a perfect cup of coffee",
        color=0x1a1a2e
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="status", description="Shows what Alfred remembers about you")
async def status(interaction: discord.Interaction):
    user_data = get_user_data(str(interaction.user.id))
    facts = "\n".join([f"• {f}" for f in user_data["facts"][-8:]]) or "You haven't shared anything important yet."
    
    embed = discord.Embed(
        title=f"File: {user_data.get('name') or interaction.user.display_name}",
        color=0x1a1a2e
    )
    embed.add_field(name="Relationship Level", value=f"**{user_data['relationship']}/100**", inline=True)
    embed.add_field(name="Interactions", value=str(user_data["interactions"]), inline=True)
    if user_data.get("character"):
        embed.add_field(name="Character", value=user_data["character"], inline=True)
    embed.add_field(name="Facts I Remember", value=facts, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Checks latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Operational, sir. Current latency: **{latency}ms**.")

@bot.tree.command(name="coffee", description="Alfred brings you a perfect cup of coffee")
async def coffee_command(interaction: discord.Interaction):
    user_data = get_user_data(str(interaction.user.id))
    name = user_data.get("name") or interaction.user.display_name
    if user_data.get("is_krypto"):
        name = "Master Krypto"
    await serve_coffee(interaction, name, is_slash=True)


if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv("DISCORD_TOKEN"))
