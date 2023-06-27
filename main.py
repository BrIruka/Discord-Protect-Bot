import discord
import json
import transliterate
import re
import sqlite3
from discord.ext import commands
from censored_words import CENSORED_WORDS


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
    'х': 'kh, x',
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

@bot.event
async def on_ready():
    print('Bot connected')


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

    # Transliterate the message from Cyrillic to Latin characters
    msg_translit = transliterate.translit(msg, 'ru')

    # Create a regular expression pattern for matching and replacing letters in CENSORED_WORDS
    pattern = '|'.join(map(re.escape, CENSORED_WORDS))
    pattern = f'(?i)\\b({pattern})\\b'

    # Function for replacing letters
    def replace_letters(match):
        word = match.group(0)
        for latin_letter, cyrillic_letter in LETTER_MAPPING.items():
            word = word.replace(cyrillic_letter, latin_letter)
        return word


    censored_words_translit = [transliterate.translit(word, 'ru') for word in CENSORED_WORDS]


    msg_replaced = re.sub(pattern, replace_letters, msg_translit)

    if any(word in msg or word in msg_translit or word in msg_replaced for word in CENSORED_WORDS):
        await message.delete()

        author = message.author

        if author.bot:
            return

        dm_channel = await author.create_dm()

        await dm_channel.send(f"Ви використали заборонене слово в повідомленні на сервері {message.guild.name}. Будь ласка, дотримуйтесь правил поведінки на сервері.")

        if message.reference:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
            await replied_message.delete()

@bot.command()
async def help(message):
    author = message.author
    if author.bot:
        return

    dm_channel = await author.create_dm()

    await dm_channel.send(f" {message.guild.name} \n Команди бота: \n .badadmin - Знімання/Наложення границь на слова для користувача. ")


@bot.command()
@commands.has_permissions(administrator=True)
async def badadmin(ctx, member: discord.Member):
    admin_tag = c.execute("SELECT admin_tag FROM database WHERE server_id=? AND user_id=?",
                          (ctx.guild.id, member.id)).fetchone()
    if admin_tag is not None and admin_tag[0] == 1:

        c.execute("UPDATE database SET admin_tag=? WHERE server_id=? AND user_id=?",
                  (0, ctx.guild.id, member.id))
        conn.commit()
        await ctx.send(f"{member.mention} Тепер має границі на слова.")
    else:
        # Give admin privileges
        c.execute("UPDATE database SET admin_tag=? WHERE server_id=? AND user_id=?",
                  (1, ctx.guild.id, member.id))
        conn.commit()
        await ctx.send(f"{member.mention} Тепер не має границь на слова.")

bot.run('token_bot')

