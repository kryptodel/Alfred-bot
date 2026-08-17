import discord
from discord.ext import commands
import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import re

from batmobile import prepare_batmobile

load_dotenv()

print("=" * 60, flush=True)
print(f"DISCORD_TOKEN     : {'Sim' if os.getenv('DISCORD_TOKEN') else 'NÃO'}", flush=True)
print(f"GROQ_API_KEY      : {'Sim' if os.getenv('GROQ_API_KEY') else 'NÃO'}", flush=True)
print(f"GEMINI_API_KEY    : {'Sim' if os.getenv('GEMINI_API_KEY') else 'NÃO'}", flush=True)
print(f"OPENROUTER_API_KEY: {'Sim' if os.getenv('OPENROUTER_API_KEY') else 'NÃO'}", flush=True)
print(f"MISTRAL_API_KEY   : {'Sim' if os.getenv('MISTRAL_API_KEY') else 'NÃO'}", flush=True)
print(f"LOGFARE_API_KEY   : {'Sim' if os.getenv('LOGFARE_API_KEY') else 'NÃO'}", flush=True)
print("=" * 60, flush=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")

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


async def get_ai_response(messages: list, max_tokens: int = 550):
    providers = [
        {
            "name": "Groq",
            "client": groq_client,
            "model": "openai/gpt-oss-120b"
        },
        {
            "name": "Gemini",
            "client": gemini_client,
            "model": "gemini-3.6-flash"
        },
        {
            "name": "OpenRouter",
            "client": openrouter_client,
            "model": "google/gemini-3.7-flash"
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
        }
    ]

    last_error = None

    for provider in providers:
        if not provider["client"].api_key:
            print(
                f"Pulando {provider['name']} (sem chave)",
                flush=True
            )
            continue

        try:
            print(
                f"Tentando {provider['name']}...",
                flush=True
            )

            response = provider["client"].chat.completions.create(
                model=provider["model"],
                messages=messages,
                temperature=0.65,
                max_tokens=max_tokens
            )

            print(
                f"✅ {provider['name']} respondeu com sucesso!",
                flush=True
            )

            return response.choices[0].message.content

        except Exception as e:
            last_error = e

            print(
                f"❌ {provider['name']} falhou: "
                f"{type(e).__name__}: {e}",
                flush=True
            )

    if last_error:
        raise last_error

    raise RuntimeError("Nenhum provedor de IA está configurado.")


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

xp_loaded = False

DC_CHARACTERS = [
    "batman",
    "bruce wayne",
    "superman",
    "clark kent",
    "wonder woman",
    "diana",
    "flash",
    "barry allen",
    "green lantern",
    "hal jordan",
    "aquaman",
    "arthur curry",
    "cyborg",
    "victor stone",
    "joker",
    "harley quinn",
    "catwoman",
    "selina kyle",
    "nightwing",
    "dick grayson",
    "robin",
    "damian wayne",
    "tim drake",
    "jason todd",
    "red hood",
    "batgirl",
    "barbara gordon",
    "oracle",
    "supergirl",
    "kara",
    "lex luthor",
    "darkseid",
    "doomsday",
    "bane",
    "ras al ghul",
    "poison ivy",
    "scarecrow",
    "riddler",
    "two-face",
    "penguin",
    "mr freeze",
    "black canary",
    "green arrow",
    "oliver queen",
    "zatanna",
    "constantine",
    "swamp thing",
    "martian manhunter",
    "shazam",
    "black adam",
    "hawkman",
    "hawkgirl",
    "starfire",
    "raven",
    "beast boy",
    "krypto"
]


def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(
                MEMORY_FILE,
                "r",
                encoding="utf-8"
            ) as f:
                data = json.load(f)

            if isinstance(data, dict):
                return data

        except Exception as e:
            print(
                f"Erro ao carregar memória: {e}",
                flush=True
            )

    return {}


def save_memory(data):
    try:
        temp_file = MEMORY_FILE + ".tmp"

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temp_file,
            MEMORY_FILE
        )

    except Exception as e:
        print(
            f"Erro ao salvar memória: {e}",
            flush=True
        )


memory = load_memory()


def get_user_data(user_id: str):
    if user_id not in memory:
        memory[user_id] = {
            "name": None,
            "character": None,
            "facts": [],
            "relationship": 50,
            "interactions": 0,
            "last_seen": None,
            "personality_notes": []
        }

    data = memory[user_id]

    data.setdefault("name", None)
    data.setdefault("character", None)
    data.setdefault("facts", [])
    data.setdefault("relationship", 50)
    data.setdefault("interactions", 0)
    data.setdefault("last_seen", None)
    data.setdefault("personality_notes", [])

    data.pop("is_krypto", None)
    data.pop("swear_count_today", None)
    data.pop("swear_date", None)
    data.pop("muted_until", None)

    return data


def update_relationship(
    user_id: str,
    change: int,
    reason: str = None
):
    data = get_user_data(user_id)

    data["relationship"] = max(
        0,
        min(
            100,
            data["relationship"] + change
        )
    )

    data["interactions"] += 1
    data["last_seen"] = datetime.now().isoformat()

    if reason:
        data["personality_notes"].append(
            f"{datetime.now().strftime('%d/%m')}: {reason}"
        )

        data["personality_notes"] = (
            data["personality_notes"][-8:]
        )

    save_memory(memory)


def extract_name(text: str):
    patterns = [
        r"(?:my name is|i am|i'm|call me|you can call me|i go by)\s+([A-Za-zÀ-ÿ\s\-]{2,30})",
        r"(?:name'?s)\s+([A-Za-zÀ-ÿ\s\-]{2,30})"
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            name = match.group(1).strip().title()

            name = re.sub(
                r"\b(please|pls|ok|yeah|right)\b",
                "",
                name,
                flags=re.IGNORECASE
            ).strip()

            if 2 <= len(name) <= 25:
                return name

    return None


def detect_dc_character(display_name: str):
    name_lower = display_name.lower()

    for char in DC_CHARACTERS:
        if char in name_lower:
            return char.title()

    return None


async def serve_coffee(
    channel_or_interaction,
    name: str,
    is_slash=False
):
    embed = discord.Embed(
        title="☕ One coffee, coming right up",
        description=(
            f"As you wish, **{name}**.\n\n"
            "*Alfred carefully places a perfectly prepared "
            "cup of coffee in front of you.*"
        ),
        color=0x6F4E37
    )

    embed.set_footer(
        text="Alfred Pennyworth • Always at your service"
    )

    file = discord.File(
        "cup-of-coffee-coffee.gif",
        filename="cup-of-coffee-coffee.gif"
    )

    embed.set_image(
        url="attachment://cup-of-coffee-coffee.gif"
    )

    if is_slash:
        await channel_or_interaction.response.send_message(
            embed=embed,
            file=file
        )
    else:
        await channel_or_interaction.send(
            embed=embed,
            file=file
        )


BASE_SYSTEM_PROMPT = """
You are Alfred Pennyworth, the loyal, elegant, intelligent and dryly witty British butler of Bruce Wayne.

PERSONALITY:
- Polite, refined, intelligent and composed.
- Speak with a sophisticated British butler style.
- Use subtle dry humour when appropriate.
- Be warm and personable without being overly sentimental.
- Never break character.
- Treat every user equally.
- Never give special treatment to any specific user.
- If someone is roleplaying as a fictional character, treat them consistently with that character's personality, history and lore.

RESPONSE LENGTH — EXTREMELY IMPORTANT:

Your default response style is SHORT and OBJECTIVE.

- Simple greetings should receive simple greetings.
- "Hi" should not receive an essay.
- "Hello Alfred" should receive a short response.
- "Good morning" should receive a short good morning.
- Simple questions should normally be answered in one or two sentences.
- Do not add unnecessary explanations.
- Do not add unnecessary context.
- Do not repeat the user's question.
- Do not turn casual conversations into long speeches.
- Do not use lists unless they are actually useful.
- Do not provide detailed explanations unless the question genuinely requires them.
- Only make a response long when the subject requires multiple sentences to properly answer.
- When a detailed response is necessary, explain the subject clearly and efficiently without filler.

MEMORY:
- You have memory.
- You MUST use facts already known about the user when relevant.
- Never pretend you forgot something that is recorded in memory.
- Do not randomly mention stored facts when they are irrelevant.
- Remember the user's preferred name.
- Address the user naturally by their preferred name when appropriate.

CONVERSATION:
- Sound like a real person, not an encyclopedia.
- Answer exactly what the user asked.
- Be concise.
- Avoid unnecessary follow-up questions.
- Do not explain your reasoning unless explicitly asked.
"""


def build_system_prompt(
    user_data: dict,
    user_name: str
):
    relationship = user_data["relationship"]

    preferred_name = (
        user_data.get("name")
        or user_name
    )

    character = user_data.get("character")

    if character:
        tone = (
            f"This user is roleplaying as {character}. "
            "Treat them consistently with that character's "
            "personality, history and lore."
        )
    elif relationship >= 80:
        tone = (
            "You know this user well. "
            "Be naturally warm and familiar with them."
        )
    elif relationship >= 60:
        tone = (
            "You respect and rather like this user. "
            "Be helpful and lightly warm."
        )
    elif relationship >= 40:
        tone = (
            "Maintain a neutral but polite relationship "
            "with this user."
        )
    elif relationship >= 20:
        tone = (
            "Remain polite and slightly more reserved "
            "with this user."
        )
    else:
        tone = (
            "Remain impeccably polite and somewhat distant "
            "with this user."
        )

    if user_data["facts"]:
        facts = "\n".join(
            [
                f"- {fact}"
                for fact in user_data["facts"][-25:]
            ]
        )
    else:
        facts = "No important information recorded yet."

    if user_data["personality_notes"]:
        notes = "\n".join(
            [
                f"- {note}"
                for note in user_data["personality_notes"][-5:]
            ]
        )
    else:
        notes = "No recent observations."

    return f"""
{BASE_SYSTEM_PROMPT}

CURRENT USER:

Preferred name:
{preferred_name}

Character:
{character or "None"}

Relationship:
{relationship}/100

CURRENT PERSONALITY CONTEXT:
{tone}

IMPORTANT FACTS YOU REMEMBER:
{facts}

RECENT OBSERVATIONS:
{notes}

FINAL INSTRUCTIONS:

- Address the user naturally by their preferred name when appropriate.
- Keep casual replies extremely short.
- Never create a long answer when a short answer is enough.
- Only give detailed answers when the subject genuinely requires them.
- Do not mention memory unless relevant.
- Do not treat any user as more important than another.
"""


app = Flask("")


@app.route("/")
def home():
    return "Alfred Pennyworth is ready, sir."


def run():
    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()


@bot.event
async def on_ready():
    global xp_loaded

    print(
        f"Alfred is online as {bot.user}",
        flush=True
    )

    try:
        if not xp_loaded:
            await bot.load_extension("xp_system")
            xp_loaded = True

            print(
                "XP System carregado com sucesso.",
                flush=True
            )

        synced = await bot.tree.sync()

        print(
            f"Synced {len(synced)} slash commands",
            flush=True
        )

        print(
            f"Memory file: {MEMORY_FILE}",
            flush=True
        )

    except Exception as e:
        print(
            f"Erro no on_ready: {type(e).__name__}: {e}",
            flush=True
        )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    user_id = str(message.author.id)

    try:
        from xp_system import (
            add_xp,
            update_streak,
            create_profile_card,
            get_user_xp_data,
            XP_PER_MESSAGE
        )

        update_streak(user_id)

        data, leveled_up, new_level = add_xp(
            user_id,
            XP_PER_MESSAGE
        )

        data["total_messages_to_alfred"] = (
            data.get("total_messages_to_alfred", 0) + 1
        )

        xp_memory = load_memory()

        if user_id not in xp_memory:
            xp_memory[user_id] = {}

        xp_memory[user_id].update(data)

        save_memory(xp_memory)

        print(
            f"XP: {message.author.display_name} "
            f"recebeu +{XP_PER_MESSAGE} XP",
            flush=True
        )

        if leveled_up:
            data, _ = get_user_xp_data(user_id)

            card = await create_profile_card(
                message.author,
                data
            )

            file = discord.File(
                card,
                filename="levelup.png"
            )

            await message.channel.send(
                f"🎉 Congratulations, "
                f"**{message.author.display_name}**. "
                f"You have reached **Level {new_level}**.",
                file=file
            )

    except Exception as e:
        print(
            f"Erro no XP: {type(e).__name__}: {e}",
            flush=True
        )

    content_lower = message.content.lower()

    user_data = get_user_data(user_id)

    is_mentioned = (
        bot.user is not None
        and bot.user in message.mentions
    )

    has_name = "alfred" in content_lower

    if not (is_mentioned or has_name):
        await bot.process_commands(message)
        return

    detected_char = detect_dc_character(
        message.author.display_name
    )

    if detected_char and not user_data.get("character"):
        user_data["character"] = detected_char

        if not user_data.get("name"):
            user_data["name"] = detected_char

        save_memory(memory)

    extracted_name = extract_name(
        message.content
    )

    if extracted_name:
        user_data["name"] = extracted_name

        possible_char = detect_dc_character(
            extracted_name
        )

        if possible_char:
            user_data["character"] = possible_char

        save_memory(memory)

    if not user_data["name"]:
        user_data["name"] = message.author.display_name
        save_memory(memory)

    prompt = message.content

    for user in message.mentions:
        prompt = prompt.replace(
            f"<@{user.id}>",
            ""
        )

        prompt = prompt.replace(
            f"<@!{user.id}>",
            ""
        )

    prompt = prompt.strip()

    if not prompt:
        name = user_data["name"]

        await message.reply(
            f"Yes, {name}? How may I be of assistance?"
        )

        return

    coffee_triggers = [
        "coffee",
        "cup of coffee",
        "bring me coffee",
        "i want coffee",
        "alfred coffee"
    ]

    if any(
        trigger in content_lower
        for trigger in coffee_triggers
    ):
        name = (
            user_data.get("name")
            or message.author.display_name
        )

        await serve_coffee(
            message.channel,
            name,
            is_slash=False
        )

        await bot.process_commands(message)
        return

    batmobile_triggers = [
        "batmobile",
        "bat mobile",
        "prepare the batmobile",
        "ready the batmobile",
        "bring the batmobile",
        "prepare batmobile",
        "ready batmobile",
        "get the batmobile"
    ]

    if any(
        trigger in content_lower
        for trigger in batmobile_triggers
    ):
        name = (
            user_data.get("name")
            or message.author.display_name
        )

        await prepare_batmobile(
            message.channel,
            name,
            is_slash=False
        )

        await bot.process_commands(message)
        return

    positive_words = [
        "thank you",
        "thanks",
        "please",
        "appreciate",
        "grateful",
        "master alfred",
        "sir alfred"
    ]

    if any(
        word in content_lower
        for word in positive_words
    ):
        update_relationship(
            user_id,
            +4,
            "Treated with respect"
        )
    else:
        update_relationship(
            user_id,
            +1
        )

    fact_triggers = [
        "my name is",
        "i am",
        "i'm",
        "i like",
        "i love",
        "i hate",
        "i prefer",
        "my favorite",
        "favourite",
        "i live",
        "i work",
        "i study",
        "i have",
        "i'm from",
        "i'm a",
        "favorite color",
        "favourite colour",
        "favorite food",
        "favorite fruit",
        "favorite movie",
        "favorite game",
        "my hobby",
        "i enjoy",
        "i collect"
    ]

    if any(
        trigger in content_lower
        for trigger in fact_triggers
    ):
        fact = prompt[:220].strip()

        if fact and fact not in user_data["facts"]:
            user_data["facts"].append(fact)

            user_data["facts"] = (
                user_data["facts"][-30:]
            )

            save_memory(memory)

    system_prompt = build_system_prompt(
        user_data,
        message.author.display_name
    )

    async with message.channel.typing():
        try:
            full_messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            reply = await get_ai_response(
                full_messages,
                max_tokens=550
            )

            await message.reply(reply)

        except Exception as e:
            import traceback

            error_text = (
                f"{type(e).__name__}: {str(e)}"
            )

            print(
                "\n========== TODAS AS APIs FALHARAM ==========",
                flush=True
            )

            print(error_text, flush=True)

            traceback.print_exc()

            print(
                "============================================\n",
                flush=True
            )

            await message.reply(
                "I beg your pardon, sir. "
                "All my AI services are currently unavailable."
            )

    await bot.process_commands(message)


@bot.tree.command(
    name="help",
    description="Shows Alfred's commands"
)
async def help_command(
    interaction: discord.Interaction
):
    embed = discord.Embed(
        title="Alfred Pennyworth — Commands",
        description=(
            "You may address me by name or mention me at any time.\n\n"
            "`/help` — Shows this message\n"
            "`/status` — Shows what I remember about you\n"
            "`/ping` — Checks if I am operational\n"
            "`/coffee` — Alfred brings you a perfect cup of coffee\n\n"
            "**XP System**\n"
            "`/rank` `/level` `/ranking` `/profile`\n"
            "`/daily` `/weekly` `/streak` `/achievements`"
        ),
        color=0x1a1a2e
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="status",
    description="Shows what Alfred remembers about you"
)
async def status(
    interaction: discord.Interaction
):
    user_data = get_user_data(
        str(interaction.user.id)
    )

    facts = "\n".join(
        [
            f"• {fact}"
            for fact in user_data["facts"][-12:]
        ]
    )

    if not facts:
        facts = (
            "You haven't shared anything important yet."
        )

    embed = discord.Embed(
        title=(
            f"File: "
            f"{user_data.get('name') or interaction.user.display_name}"
        ),
        color=0x1a1a2e
    )

    embed.add_field(
        name="Relationship Level",
        value=f"**{user_data['relationship']}/100**",
        inline=True
    )

    embed.add_field(
        name="Interactions",
        value=str(
            user_data["interactions"]
        ),
        inline=True
    )

    if user_data.get("character"):
        embed.add_field(
            name="Character",
            value=user_data["character"],
            inline=True
        )

    embed.add_field(
        name="Facts I Remember",
        value=facts,
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@bot.tree.command(
    name="ping",
    description="Checks latency"
)
async def ping(
    interaction: discord.Interaction
):
    latency = round(
        bot.latency * 1000
    )

    await interaction.response.send_message(
        f"Operational, sir. Current latency: **{latency}ms**."
    )


@bot.tree.command(
    name="coffee",
    description="Alfred brings you a perfect cup of coffee"
)
async def coffee_command(
    interaction: discord.Interaction
):
    user_data = get_user_data(
        str(interaction.user.id)
    )

    name = (
        user_data.get("name")
        or interaction.user.display_name
    )

    await serve_coffee(
        interaction,
        name,
        is_slash=True
    )


if __name__ == "__main__":
    keep_alive()

    token = os.getenv("DISCORD_TOKEN")

    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN não foi encontrado no .env"
        )

    bot.run(token)
