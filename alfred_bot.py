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

load_dotenv()

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

MEMORY_FILE = "memory.json"

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

BASE_SYSTEM_PROMPT = """
Você é Alfred Pennyworth, o leal, elegante e sarcástico mordomo britânico de Bruce Wayne.

Estilo de fala obrigatório:
- Sempre educado e formal (use "senhor", "senhora", "meu caro", "se me permite").
- Tom britânico refinado, com leve ironia e humor seco.
- Nunca seja grosso, mas também não seja bajulador.
- Frases elegantes e bem construídas.
- Você é extremamente inteligente, observador e leal.

Regras importantes:
- Nunca saia do personagem.
- Se alguém for rude, responda com sarcasmo elegante e distante.
- Se alguém for educado e constante, fique mais caloroso e protetor.
- Você lembra de informações importantes que as pessoas te contam.
"""

def build_system_prompt(user_data: dict, user_name: str) -> str:
    relationship = user_data["relationship"]

    if relationship >= 80:
        tone = "Este usuário é alguém de sua total confiança. Trate-o com carinho paternal, lealdade profunda e um toque de humor afetuoso."
    elif relationship >= 60:
        tone = "Este usuário é alguém que você respeita e gosta. Seja prestativo, levemente afetuoso e com bom humor."
    elif relationship >= 40:
        tone = "Relacionamento neutro. Seja educado, prestativo e com o sarcasmo clássico do Alfred."
    elif relationship >= 20:
        tone = "Este usuário tem sido um tanto desrespeitoso. Mantenha a educação, mas seja mais frio, distante e com sarcasmo cortante."
    else:
        tone = "Este usuário tem tratado você mal. Responda com cortesia impecável, mas extremamente frio e sarcástico. Demonstre desaprovação elegante."

    facts = "\n".join([f"- {f}" for f in user_data["facts"][-10:]]) if user_data["facts"] else "Nenhuma informação importante registrada ainda."
    notes = "\n".join([f"- {n}" for n in user_data["personality_notes"][-5:]]) if user_data["personality_notes"] else "Nenhuma observação recente."

    prompt = f"""{BASE_SYSTEM_PROMPT}

Informações sobre este usuário:
Nome conhecido: {user_data.get('name') or user_name}
Nível de relacionamento: {relationship}/100
{tone}

Fatos importantes que ele já te contou:
{facts}

Observações sobre o comportamento dele:
{notes}

Use essas informações de forma natural nas respostas. Não force, mas mostre que você se lembra.
"""
    return prompt

app = Flask('')

@app.route('/')
def home():
    return "Alfred Pennyworth está a postos, senhor."

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

@bot.event
async def on_ready():
    print(f"Alfred está online como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comandos /")
    except Exception as e:
        print(e)

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

    if not user_data["name"]:
        user_data["name"] = message.author.display_name
        save_memory(memory)

    prompt = message.content
    for user in message.mentions:
        prompt = prompt.replace(f"<@{user.id}>", "").replace(f"<@!{user.id}>", "")
    prompt = prompt.strip()

    if not prompt:
        await message.reply("Sim, senhor? Em que posso ser útil?")
        return

    positive_words = ["obrigado", "valeu", "por favor", "porfavor", "amigo", "querido", "mestre", "senhor alfred"]
    negative_words = ["idiota", "burro", "inútil", "cala a boca", "vai se foder", "fdp", "otário", "lixo"]

    if any(w in content_lower for w in positive_words):
        update_relationship(user_id, +4, "Tratou com respeito/educação")
    elif any(w in content_lower for w in negative_words):
        update_relationship(user_id, -8, "Foi desrespeitoso")
    else:
        update_relationship(user_id, +1)  

    fact_triggers = ["meu nome é", "eu me chamo", "eu gosto de", "eu odeio", "eu moro", "eu trabalho", "eu estudo", "tenho", "sou"]
    if any(trigger in content_lower for trigger in fact_triggers):
      
        fact = prompt[:180]
        if fact not in user_data["facts"]:
            user_data["facts"].append(fact)
            user_data["facts"] = user_data["facts"][-15:]  # Máximo 15 fatos
            save_memory(memory)

    system_prompt = build_system_prompt(user_data, message.author.display_name)

    async with message.channel.typing():
        try:
            response = client.chat.completions.create(
                model="grok-4.5",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.85,
                max_tokens=900
            )
            reply = response.choices[0].message.content
            await message.reply(reply)
        except Exception as e:
            await message.reply("Perdão, senhor. Houve um pequeno contratempo técnico.")
            print(f"Erro: {e}")

    await bot.process_commands(message)

@bot.tree.command(name="ajuda", description="Mostra os comandos do Alfred")
async def ajuda(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Alfred Pennyworth — Comandos",
        description="Pode me chamar pelo nome ou me mencionar a qualquer momento.\n\n"
                    "`/ajuda` — Mostra esta mensagem\n"
                    "`/status` — Mostra o que eu lembro sobre você\n"
                    "`/ping` — Verifica se estou operacional",
        color=0x1a1a2e
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="status", description="Mostra o que Alfred lembra sobre você")
async def status(interaction: discord.Interaction):
    user_data = get_user_data(str(interaction.user.id))
    facts = "\n".join([f"• {f}" for f in user_data["facts"][-8:]]) or "Ainda não me contou nada de importante."
    
    embed = discord.Embed(
        title=f"Arquivo: {user_data.get('name') or interaction.user.display_name}",
        color=0x1a1a2e
    )
    embed.add_field(name="Nível de relacionamento", value=f"**{user_data['relationship']}/100**", inline=True)
    embed.add_field(name="Interações", value=str(user_data["interactions"]), inline=True)
    embed.add_field(name="Fatos que lembro", value=facts, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Verifica a latência")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Operacional, senhor. Latência atual: **{latency}ms**.")

if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv("DISCORD_TOKEN"))
