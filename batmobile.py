import discord
from discord.ext import commands
from discord import app_commands

class Batmobile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def prepare_batmobile(self, channel_or_interaction, name: str, is_slash=False):
        embed = discord.Embed(
            title="🦇 The Batmobile is ready",
            description=f"As you wish, **{name}**.\n\n*Alfred carefully prepares the Batmobile, checking every system and ensuring it is in perfect working order for your departure.*",
            color=0x1A1A1A
        )
        embed.set_footer(text="Alfred Pennyworth • Always at your service")

        file = discord.File("batman-batmóvel.gif", filename="batman-batmóvel.gif)
        embed.set_image(url="attachment://batmobile.gif")

        if is_slash:
            await channel_or_interaction.response.send_message(embed=embed, file=file)
        else:
            await channel_or_interaction.send(embed=embed, file=file)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content_lower = message.content.lower()

  
        is_mentioned = self.bot.user in message.mentions
        has_name = "alfred" in content_lower

        if not (is_mentioned or has_name):
            return

        batmobile_triggers = [
            "batmobile", "bat mobile", "prepare the batmobile", "ready the batmobile",
            "bring the batmobile", "prepare batmobile", "ready batmobile", "get the batmobile"
        ]

        if any(trigger in content_lower for trigger in batmobile_triggers):
            
            name = message.author.display_name
            try:
                from __main__ import get_user_data  
                user_data = get_user_data(str(message.author.id))
                name = user_data.get("name") or message.author.display_name
                if user_data.get("is_krypto"):
                    name = "Master Krypto"
            except:
                pass

            await self.prepare_batmobile(message.channel, name, is_slash=False)

    @app_commands.command(name="batmobile", description="Alfred prepares the Batmobile for you")
    async def batmobile_slash(self, interaction: discord.Interaction):
        name = interaction.user.display_name
        try:
            from __main__ import get_user_data
            user_data = get_user_data(str(interaction.user.id))
            name = user_data.get("name") or interaction.user.display_name
            if user_data.get("is_krypto"):
                name = "Master Krypto"
        except:
            pass

        await self.prepare_batmobile(interaction, name, is_slash=True)


async def setup(bot):
    await bot.add_cog(Batmobile(bot))
