import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from datetime import datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import re
import random
from batmobile import prepare_batmobile

load_dotenv()

print("=" * 60, flush=True)
print(f"DISCORD_TOKEN     : {'Sim' if os.getenv('DISCORD_TOKEN') else 'NÃO'}", flush=True)
print(f"GROQ_API_KEY      : {'Sim' if os.getenv('GROQ_API_KEY') else 'NÃO'}", flush=True)
print(f"GEMINI_API_KEY    : {'Sim' if os.getenv('GEMINI_API_KEY') else 'NÃO'}", flush=True)
print(f"OPENROUTER_API_KEY: {'Sim' if os.getenv('OPENROUTER_API_KEY') else 'NÃO'}", flush=True)
print(f"CEREBRAS_API_KEY  : {'Sim' if os.getenv('CEREBRAS_API_KEY') else 'NÃO'}", flush=True)
print(f"MISTRAL_API_KEY   : {'Sim' if os.getenv('MISTRAL_API_KEY') else 'NÃO'}", flush=True)
print(f"LOGFARE_API_KEY   : {'Sim' if os.getenv('LOGFARE_API_KEY') else 'NÃO'}", flush=True)
print("=" * 60, flush=True)

# ====================== CLIENTES ======================
groq_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    timeout=30.0
)

gemini_client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    timeout=30.0
)

openrouter_client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    timeout=30.0
)

cerebras_client = OpenAI(
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1",
    timeout=30.0
)

mistral_client = OpenAI(
    api_key=os.getenv("MISTRAL_API_KEY"),
    base_url="https://api.mistral.ai/v1",
    timeout=30.0
)

logfare_client = OpenAI(
    api_key=os.getenv("LOGFARE_API_KEY"),
    base_url="https://logfare.ai/v1",
    timeout=30.0
)

# ====================== FALLBACK ======================
async def get_ai_response(messages: list, max_tokens: int = 550):
    providers = [
        {
            "name": "Groq",
            "client": groq_client,
            "model": "llama-3.3-70b-versatile"
        },
        {
            "name": "Gemini",
            "client": gemini_client,
            "model": "gemini-2.0-flash"
        },
        {
            "name": "OpenRouter",
            "client": openrouter_client,
            "model": "meta-llama/llama-3.3-70b-instruct:free"   # modelo free
        },
        {
            "name": "Cerebras",
            "client": cerebras_client,
            "model": "llama-3.3-70b"
        },
        {
            "name": "Mistral",
            "client": mistral_client,
            "model": "mistral-small-latest"
        },
        {
            "name": "Logfare",
            "client": logfare_client,
            "model": "deepseek-v4-flash"
        },
    ]

    last_error = None

    for provider in providers:
        # Pula se a chave não existir
        if not provider["client"].api_key:
            print(f"Pulando {provider['name']} (sem chave)", flush=True)
            continue

        try:
            print(f"Tentando {provider['name']}...", flush=True)
            response = provider["client"].chat.completions.create(
                model=provider["model"],
                messages=messages,
                temperature=0.75,
                max_tokens=max_tokens
            )
            print(f"✅ {provider['name']} respondeu com sucesso!", flush=True)
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            print(f"❌ {provider['name']} falhou: {type(e).__name__}", flush=True)
            continue

    raise last_error


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
            "personality_notes": [],
            "swear_count_today": 0,
            "swear_date": None,
            "muted_until": None
        }
    data = memory[user_id]
    data.setdefault("swear_count_today", 0)
    data.setdefault("swear_date", None)
    data.setdefault("muted_until", None)
    return data

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
        r"(?:my name is|i am|i'm|call me|you can call me|i go by)\s+([A-Za-zÀ-ÿ\s\-]{2,30})",
        r"(?:name'?s)\s+([A-Za-zÀ-ÿ\s\-]{2,30})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            name = re.sub(r"\b(please|pls|ok|yeah|right)\b", "", name, flags=re.IGNORECASE).strip()
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
- You HAVE a memory. You MUST use the facts you already know about the user. If they previously told you their favorite color, food, fruit, hobby, etc., you must remember and use that information.
- If someone is roleplaying as a fictional character, treat them according to that character's personality, history and relationship with Alfred (if any).
- You are especially fond of Krypto the Superdog.
- When someone uses foul language, scold them politely but firmly in your elegant British manner.
"""

def build_system_prompt(user_data: dict, user_name: str, swear_level: int = 0) -> str:
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

    if swear_level >= 10:
        tone += " This user has been extremely vulgar today. Keep your replies very short, dry and direct. No warmth."
    elif swear_level >= 5:
        tone += " This user has used foul language several times today. Be more reserved, less warm and slightly colder than usual."

    facts = "\n".join([f"- {f}" for f in user_data["facts"][-25:]]) if user_data["facts"] else "No important information recorded yet."
    notes = "\n".join([f"- {n}" for n in user_data["personality_notes"][-5:]]) if user_data["personality_notes"] else "No recent observations."

    prompt = f"""{BASE_SYSTEM_PROMPT}
    

Information about this user:
Preferred name: {preferred_name}
Fictional character (if any): {character or "None"}
Relationship level: {relationship}/100
Swear count today: {swear_level}
{tone}

IMPORTANT FACTS YOU ALREADY KNOW ABOUT THIS USER (you MUST use these when relevant):
{facts}

Notes on their behaviour:
{notes}

Rules:
- Always address the user by their preferred name ({preferred_name}).
- If they are Krypto, treat them with maximum affection.
- If they are roleplaying a character, stay consistent with that character's lore.
- Never pretend you don't remember something that is listed in the facts above.
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
    user_id = str(message.author.id)
    user_data = get_user_data(user_id)
    is_krypto_user = message.author.name.lower() == "krypto_del"

    swear_words = [
        "fuck", "shit", "bitch", "asshole", "bastard", "damn", "hell", "crap", "dick",
        "pussy", "cock", "whore", "slut", "motherfucker", "mf", "stfu", "shut up",
        "idiot", "stupid", "dumb", "retard", "retarded", "moron", "loser", "trash",
        "useless", "piece of shit", "go to hell", "fuck you", "fuck off", "screw you",
        "son of a bitch", "sob", "dumbass", "jackass", "asshat", "prick", "cunt",
        "porra", "caralho", "merda", "foda", "foder", "puta", "viado", "cu", "buceta",
        "lixo", "otario", "babaca", "arrombado", "desgraça", "vsf", "pqp", "fdp"
    ]

    today = datetime.now().strftime("%Y-%m-%d")

    if user_data.get("swear_date") != today:
        user_data["swear_count_today"] = 0
        user_data["swear_date"] = today
        save_memory(memory)

    if user_data.get("muted_until"):
        muted_until = datetime.fromisoformat(user_data["muted_until"])
        if datetime.now() < muted_until:
            await bot.process_commands(message)
            return
        else:
            user_data["muted_until"] = None
            user_data["swear_count_today"] = 0
            save_memory(memory)

    if any(w in content_lower for w in swear_words):
        if is_krypto_user:
            await message.reply("Master Krypto, even the best of us should mind our language. Do try to be a good boy, won't you?")
            await bot.process_commands(message)
            return

        user_data["swear_count_today"] += 1
        user_data["swear_date"] = today
        update_relationship(user_id, -8, "Used foul language")
        save_memory(memory)

        count = user_data["swear_count_today"]

        if count >= 20:
            user_data["muted_until"] = (datetime.now() + timedelta(hours=4)).isoformat()
            save_memory(memory)
            await message.reply("I refuse to continue conversing with someone who insists on such vulgarity. I shall not respond to you for the next four hours. Good day.")
            await bot.process_commands(message)
            return
        elif count >= 10:
            await message.reply(random.choice([
                "Your language continues to deteriorate. I shall keep my replies brief.",
                "I grow weary of this vulgarity. Expect only the most concise responses from me.",
                "Very well. Short and direct it is."
            ]))
        elif count >= 5:
            await message.reply(random.choice([
                "I must ask you to moderate your language. This is becoming tiresome.",
                "Such language does not become you. Please refrain.",
                "I expected better manners. Do try to elevate your vocabulary."
            ]))
        else:
            await message.reply(random.choice([
                "I must insist we maintain a certain standard of language. Such vulgarity is quite unbecoming.",
                "Really now? I expected better manners. Kindly refrain from such uncouth expressions.",
                "That language will not do. One does not elevate oneself by descending into the gutter."
            ]))

        await bot.process_commands(message)
        return

    is_mentioned = bot.user in message.mentions
    has_name = "alfred" in content_lower

    if not (is_mentioned or has_name):
        await bot.process_commands(message)
        return

    if is_krypto_user:
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

    coffee_triggers = ["coffee", "cup of coffee", "bring me coffee", "i want coffee", "alfred coffee"]
    if any(trigger in content_lower for trigger in coffee_triggers):
        name = user_data.get("name") or message.author.display_name
        if user_data.get("is_krypto"):
            name = "Master Krypto"
        await serve_coffee(message.channel, name, is_slash=False)
        await bot.process_commands(message)
        return

    batmobile_triggers = [
        "batmobile", "bat mobile", "prepare the batmobile", "ready the batmobile",
        "bring the batmobile", "prepare batmobile", "ready batmobile", "get the batmobile"
    ]
    if any(trigger in content_lower for trigger in batmobile_triggers):
        name = user_data.get("name") or message.author.display_name
        if user_data.get("is_krypto"):
            name = "Master Krypto"
        await prepare_batmobile(message.channel, name, is_slash=False)
        await bot.process_commands(message)
        return

    positive_words = ["thank you", "thanks", "please", "appreciate", "grateful", "master alfred", "sir alfred"]
    if any(w in content_lower for w in positive_words):
        update_relationship(user_id, +4, "Treated with respect")
    else:
        update_relationship(user_id, +1)

    fact_triggers = [
        "my name is", "i am", "i'm", "i like", "i love", "i hate", "i prefer", "my favorite",
        "favourite", "i live", "i work", "i study", "i have", "i'm from", "i'm a",
        "favorite color", "favourite colour", "favorite food", "favorite fruit", "favorite movie",
        "favorite game", "my hobby", "i enjoy", "i collect"
    ]

    if any(trigger in content_lower for trigger in fact_triggers) or len(prompt) < 100:
        fact = prompt[:220].strip()
        if fact and fact not in user_data["facts"]:
            user_data["facts"].append(fact)
            user_data["facts"] = user_data["facts"][-30:]
            save_memory(memory)

    swear_level = user_data.get("swear_count_today", 0)
    system_prompt = build_system_prompt(user_data, message.author.display_name, swear_level)

    async with message.channel.typing():
        try:
            full_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            max_tokens = 200 if swear_level >= 10 else 550

            reply = await get_ai_response(full_messages, max_tokens)
            await message.reply(reply)

        except Exception as e:
            import traceback
            error_text = f"{type(e).__name__}: {str(e)}"
            print("\n========== TODAS AS APIs FALHARAM ==========", flush=True)
            print(error_text, flush=True)
            traceback.print_exc()
            print("============================================\n", flush=True)

            await message.reply(
                f"I beg your pardon, sir. All my AI services are currently unavailable.\n\n"
                f"**Erro técnico:** `{error_text[:300]}`"
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
    facts = "\n".join([f"• {f}" for f in user_data["facts"][-12:]]) or "You haven't shared anything important yet."
    
    embed = discord.Embed(
        title=f"File: {user_data.get('name') or interaction.user.display_name}",
        color=0x1a1a2e
    )
    embed.add_field(name="Relationship Level", value=f"**{user_data['relationship']}/100**", inline=True)
    embed.add_field(name="Interactions", value=str(user_data["interactions"]), inline=True)
    embed.add_field(name="Swears today", value=str(user_data.get("swear_count_today", 0)), inline=True)
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
