import discord
import json
import transliterate
import re
import sqlite3
from discord.ext import commands
from censored_words import CENSORED_WORDS
from pytils import translit

PREFIX = '!'

bot = commands.Bot(command_prefix=PREFIX, intents=discord.Intents.all())
bot.remove_command('help')

LETTER_MAPPING = {
    'а': 'a',
    'б': 'b',
    'в': 'v',
    'г': 'h, g',
    'ґ': 'g',
    'д': 'd',
    'е': 'e',
    'є': 'ye',
    'ж': 'zh',
    'з': 'z',
    'и': 'y, u',
    'і': 'i',
    'ї': 'yi, y',
    'й': 'y',
    'к': 'c, k',
    'л': 'l',
    'м': 'm',
    'н': 'n',
    'о': 'o',
    'п': 'p',
    'р': 'r',
    'с': 's',
    'т': 't',
    'у': 'u, y',
    'ф': 'f',
    'х': 'kh, x, h',
    'ц': 'ts',
    'ч': 'ch',
    'ш': 'sh',
    'щ': 'shch',
    'ь': '',
    'ю': 'yu',
    'я': 'ya, a'
}

# Connect to SQLite database
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Create table for admin tags if it doesn't exist
c.execute('''CREATE TABLE IF NOT EXISTS database (
                server_id INTEGER,
                user_id INTEGER,
                user_name TEXT,
                admin_tag INTEGER,
                PRIMARY KEY (server_id, user_id)
            )''')
conn.commit()

# Connect to servers SQLite database
conn_servers = sqlite3.connect('servers.db')
c_servers = conn_servers.cursor()

# Create table for servers if it doesn't exist
c_servers.execute('''CREATE TABLE IF NOT EXISTS servers (
                server_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'eng'
            )''')

conn_servers.commit()


def replace_letters(match):
    word = match.group(0)
    for cyrillic_letter, latin_letters in LETTER_MAPPING.items():
        cyrillic_letters = cyrillic_letter.split(', ')
        for cyrillic_letter in cyrillic_letters:
            word = word.replace(cyrillic_letter, latin_letters)
    return word


@bot.event
async def on_ready():
    print('Bot connected')

@bot.event
async def on_guild_join(guild):
    server_id = guild.id

    # Check if the server already exists in the database
    server_exists = c_servers.execute("SELECT * FROM servers WHERE server_id=?", (server_id,)).fetchone()
    if server_exists is None:
        # Add the server to the database with default language 'eng'
        c_servers.execute("INSERT INTO servers (server_id, language) VALUES (?, ?)", (server_id, 'eng'))
        conn_servers.commit()




@bot.event
async def on_message(message):
    await bot.process_commands(message)
    msg = message.content.lower()

    # Check if the message was sent in a guild (not in DMs)
    if message.guild is None:
        return

    # Check if the user has admin privileges
    admin_tag = c.execute("SELECT admin_tag FROM database WHERE server_id=? AND user_id=?",
                          (message.guild.id, message.author.id)).fetchone()
    if admin_tag is not None and admin_tag[0] == 1:
        return

    # Check if the user is already in the database
    user_exists = c.execute("SELECT * FROM database WHERE server_id=? AND user_id=?",
                            (message.guild.id, message.author.id)).fetchone()
    if user_exists is None:
        # Add the user to the database
        c.execute("INSERT INTO database (server_id, user_id, user_name, admin_tag) VALUES (?, ?, ?, ?)",
                  (message.guild.id, message.author.id, message.author.name, 0))
        conn.commit()

    # Get the language setting for the server
    server_language = c_servers.execute("SELECT language FROM servers WHERE server_id=?", (message.guild.id,)).fetchone()
    if server_language is None:
        server_language = 'eng'
    else:
        server_language = server_language[0]

    # Create a regular expression pattern for matching and replacing letters in the message
    pattern = '|'.join(map(re.escape, LETTER_MAPPING.keys()))
    pattern = f'(?i)\\b({pattern})\\b'

    # Function for replacing letters
    def replace_letters(match):
        letter = match.group(0).lower()
        return LETTER_MAPPING.get(letter, letter)

    # Replace letters in the message based on the server language
    if server_language == 'eng':
        msg_replaced = re.sub(pattern, replace_letters, msg)
    elif server_language == 'ru':
        msg_replaced = re.sub(pattern, replace_letters, msg)
    elif server_language == 'ua':
        msg_replaced = re.sub(pattern, replace_letters, msg)
    else:
        msg_replaced = msg

    if any(word in msg or word in msg_replaced for word in CENSORED_WORDS):
        await message.delete()

        author = message.author

        if author.bot:
            return

        dm_channel = await author.create_dm()

        if server_language == 'ru':
            await dm_channel.send(f"Вы использовали запрещенное слово в сообщении на сервере {message.guild.name}. Пожалуйста, соблюдайте правила поведения на сервере.")
        elif server_language == 'ua':
            await dm_channel.send(f"Ви використали заборонене слово в повідомленні на сервері {message.guild.name}. Будь ласка, дотримуйтесь правил поведінки на сервері.")
        else:
            await dm_channel.send(f"You used a forbidden word in a message on the server {message.guild.name}. Please follow the server rules.")

        if message.reference:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
            await replied_message.delete()



@bot.command()
async def help(ctx):
    author = ctx.author
    if author.bot:
        return

    dm_channel = await author.create_dm()

    await dm_channel.send(f"{ctx.guild.name} \n Bot commands: \n !badadmin - Toggle word restrictions for a user. \n !language - Change the bot language.")


@bot.command()
@commands.has_permissions(administrator=True)
async def badadmin(ctx, member: discord.Member):
    admin_tag = c.execute("SELECT admin_tag FROM database WHERE server_id=? AND user_id=?",
                          (ctx.guild.id, member.id)).fetchone()
    if admin_tag is not None and admin_tag[0] == 1:
        c.execute("UPDATE database SET admin_tag=? WHERE server_id=? AND user_id=?",
                  (0, ctx.guild.id, member.id))
        conn.commit()
        await ctx.send(f"{member.mention} now has word restrictions.")
    else:
        # Give admin privileges
        c.execute("UPDATE database SET admin_tag=? WHERE server_id=? AND user_id=?",
                  (1, ctx.guild.id, member.id))
        conn.commit()
        await ctx.send(f"{member.mention} no longer has word restrictions.")


@bot.command()
@commands.has_permissions(administrator=True)
async def language(ctx, lang):
    server_id = ctx.guild.id
    if lang.lower() in ['eng', 'ru', 'ua']:
        c_servers.execute("UPDATE servers SET language=? WHERE server_id=?", (lang.lower(), server_id))
        conn_servers.commit()
        await ctx.send(f"The bot language has been set to {lang.upper()}.")
    else:
        await ctx.send("Invalid language. Available languages: ENG, RU, UA.")



bot.run('MTA3ODQyMjk3Njk1MDcxODYxNA.GCwvxv.jHTNqC36N9Vqzen8NwJORsnjgYyR2W0_RTpim8')
