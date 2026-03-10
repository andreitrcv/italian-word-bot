# italian_word_bot.py
import os
import json
import random
from datetime import datetime, time
from telegram.ext import Application, CommandHandler, ContextTypes
import pytz

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
TIMEZONE = pytz.timezone('Europe/Rome')
WORDS_FILE = 'italian_words.json'
SENT_WORDS_FILE = 'sent_words.json'

class ItalianWordBot:
    def __init__(self, application=None, words_file=WORDS_FILE, sent_words_file=SENT_WORDS_FILE):
        self.words_file = words_file
        self.sent_words_file = sent_words_file
        self.application = application or Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.bot = self.application.bot

    def load_words(self):
        """Load Italian words from JSON file"""
        with open(self.words_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_sent_words(self):
        """Load sent words tracking data"""
        if not os.path.exists(self.sent_words_file):
            return {'history': [], 'current_cycle': []}

        with open(self.sent_words_file, 'r', encoding='utf-8') as f:
            sent_words = json.load(f)

        return {
            'history': sent_words.get('history', []),
            'current_cycle': sent_words.get('current_cycle', [])
        }

    def save_sent_words(self, sent_words):
        """Persist sent words tracking data"""
        with open(self.sent_words_file, 'w', encoding='utf-8') as f:
            json.dump(sent_words, f, ensure_ascii=False, indent=2)
            f.write('\n')

    def get_random_word(self):
        """Get a random Italian word that has not been sent in the current cycle"""
        words = self.load_words()['words']
        sent_words = self.load_sent_words()
        current_cycle = set(sent_words['current_cycle'])
        available_words = [word for word in words if word['word'] not in current_cycle]

        if not available_words:
            sent_words['current_cycle'] = []
            self.save_sent_words(sent_words)
            available_words = words

        return random.choice(available_words)

    def record_sent_word(self, word_data):
        """Track sent words for future reuse and duplicate prevention"""
        sent_words = self.load_sent_words()
        word = word_data['word']

        sent_words['history'].append({
            'word': word,
            'sent_at': datetime.now(TIMEZONE).isoformat()
        })

        if word not in sent_words['current_cycle']:
            sent_words['current_cycle'].append(word)

        self.save_sent_words(sent_words)

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
        self.record_sent_word(word_data)
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
