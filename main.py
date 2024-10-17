import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from colorama import Fore, Style, init


bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())




@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.CustomActivity(name="https://github.com/qSoakt"))

    design = """
██████╗ ██╗   ██╗    ███████╗ ██████╗  █████╗ ██╗  ██╗
██╔══██╗╚██╗ ██╔╝    ██╔════╝██╔═══██╗██╔══██╗██║ ██╔╝
██████╔╝ ╚████╔╝     ███████╗██║   ██║███████║█████╔╝ 
██╔══██╗  ╚██╔╝      ╚════██║██║   ██║██╔══██║██╔═██╗ 
██████╔╝   ██║       ███████║╚██████╔╝██║  ██║██║  ██╗
╚═════╝    ╚═╝       ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
                                                                                        
    """
    
    print(Fore.GREEN,design)
    print(Fore.GREEN, "Bot is now online!")



initial_cogs = [
    "cogs.configurator",
]

for cog in initial_cogs:
    bot.load_extension(cog)

load_dotenv()

bot.run(os.getenv("TOKEN"))
