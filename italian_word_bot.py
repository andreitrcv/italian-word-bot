# italian_word_bot.py
import os
import json
import random
from datetime import time, datetime
from telegram.ext import Application, CommandHandler, ContextTypes
import pytz

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
TIMEZONE = pytz.timezone('Europe/Rome')
WORDS_FILE = 'italian_words.json'
SENT_WORDS_FILE = 'sent_words.json'

class ItalianWordBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.bot = self.application.bot

    def load_words(self):
        """Load Italian words from JSON file"""
        with open(WORDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_sent_words(self):
        """Load the list of previously sent words from JSON file"""
        try:
            with open(SENT_WORDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"sent": []}

    def save_sent_word(self, word):
        """Save a word to the sent words history"""
        sent_data = self.load_sent_words()
        sent_data["sent"].append({
            "word": word,
            "date": datetime.now(TIMEZONE).strftime("%Y-%m-%d")
        })
        with open(SENT_WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sent_data, f, ensure_ascii=False, indent=2)

    def get_random_word(self):
        """Get a random Italian word that hasn't been sent yet.
        If all words have been sent, reset the history and start over."""
        words = self.load_words()
        sent_data = self.load_sent_words()
        sent_word_names = {entry["word"] for entry in sent_data["sent"]}

        unsent_words = [w for w in words['words'] if w['word'] not in sent_word_names]

        if not unsent_words:
            # All words have been sent — reset and start a new cycle
            sent_data["sent"] = []
            with open(SENT_WORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(sent_data, f, ensure_ascii=False, indent=2)
            unsent_words = words['words']

        return random.choice(unsent_words)

    async def send_morning_message(self):
        """Send the word of the day"""
        word_data = self.get_random_word()
        message = f"🌅 *Parola del Giorno* 🌅\n\n"
        message += f"🇮🇹 *{word_data['word']}*\n"
        message += f"🇺🇦 *{word_data['ukrainian']}*\n\n"
        message += f"*Significato:*\n{word_data['meaning']}\n\n"
        
        if 'example' in word_data:
            message += f"*Esempio:*\n🇮🇹 _{word_data['example']}_\n"
        
        if 'ukrainian_example' in word_data:
            message += f"🇺🇦 _{word_data['ukrainian_example']}_"
        
        await self.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='Markdown'
        )
        self.save_sent_word(word_data['word'])
        print(f"Morning message sent: {word_data['word']} ({word_data['ukrainian']})")

    async def scheduled_morning_task(self, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled task for morning message"""
        await self.send_morning_message()

    async def test_command(self, update, context):
        """Test command to send message immediately"""
        await self.send_morning_message()
        await update.message.reply_text("✅ Messaggio inviato!")

    def setup_handlers(self):
        """Setup command handlers"""
        self.application.add_handler(CommandHandler("test", self.test_command))

    def setup_scheduled_jobs(self):
        """Setup scheduled job for morning message"""
        job_queue = self.application.job_queue
        # Morning message at 8:00 AM Italian time
        morning_time = time(hour=8, minute=0, tzinfo=TIMEZONE)
        job_queue.run_daily(
            self.scheduled_morning_task,
            time=morning_time,
            name='morning_message'
        )
        print(f"Scheduled morning message at: {morning_time}")

    def run(self):
        """Start the bot"""
        self.setup_handlers()
        self.setup_scheduled_jobs()
        print("Bot is running...")
        self.application.run_polling()

if __name__ == '__main__':
    bot = ItalianWordBot()
    bot.run()
