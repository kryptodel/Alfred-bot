
import discord

async def prepare_batmobile(channel_or_interaction, name: str, is_slash=False):
    embed = discord.Embed(
        title="🦇 The Batmobile is ready",
        description=f"As you wish, **{name}**.\n\n*Alfred carefully prepares the Batmobile, checking every system and ensuring it is in perfect working order for your departure.*",
        color=0x1A1A1A
    )
    embed.set_footer(text="Alfred Pennyworth • Always at your service")

    file = discord.File("batman-batmóvel.gif", filename="batman-batmóvel.gif)
    embed.set_image(url="attachment://batman-batmóvel.gif")

    if is_slash:
        await channel_or_interaction.response.send_message(embed=embed, file=file)
    else:
        await channel_or_interaction.send(embed=embed, file=file)
