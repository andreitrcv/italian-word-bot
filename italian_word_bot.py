import os
import json
import random
import asyncio
from datetime import datetime, time
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import pytz

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')  # Your girlfriend's chat ID
TIMEZONE = pytz.timezone('Europe/Rome')  # Italian timezone

# File to store state
STATE_FILE = 'bot_state.json'
WORDS_FILE = 'italian_words.json'

class ItalianWordBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.bot = self.application.bot
        self.current_word = None
        self.morning_message_id = None
        self.load_state()
        
    def load_state(self):
        """Load the bot state from file"""
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                self.current_word = state.get('current_word')
                self.morning_message_id = state.get('morning_message_id')
    
    def save_state(self):
        """Save the bot state to file"""
        state = {
            'current_word': self.current_word,
            'morning_message_id': self.morning_message_id
        }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def load_words(self):
        """Load Italian words from JSON file"""
        with open(WORDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_random_word(self):
        """Get a random Italian word"""
        words = self.load_words()
        return random.choice(words['words'])
    
    def generate_quiz_options(self, correct_meaning):
        """Generate multiple choice options including the correct answer"""
        words = self.load_words()
        all_meanings = [w['meaning'] for w in words['words']]
        
        # Remove the correct meaning from the pool
        other_meanings = [m for m in all_meanings if m != correct_meaning]
        
        # Select 3 random wrong answers
        wrong_answers = random.sample(other_meanings, min(3, len(other_meanings)))
        
        # Combine and shuffle
        options = wrong_answers + [correct_meaning]
        random.shuffle(options)
        
        # Find the index of the correct answer
        correct_index = options.index(correct_meaning)
        
        return options, correct_index
    
    async def send_morning_message(self):
        """Send the word of the day with meaning at 8:00 AM"""
        word_data = self.get_random_word()
        self.current_word = word_data
        
        message = f"🌅 *Parola del Giorno* 🌅\n\n"
        message += f"🇮🇹 *{word_data['word']}*\n"
        message += f"🇺🇦 *{word_data['ukrainian']}*\n\n"
        message += f"*Significato:*\n{word_data['meaning']}\n\n"
        
        if 'example' in word_data:
            message += f"*Esempio:*\n_{word_data['example']}_"
        
        sent_message = await self.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='Markdown'
        )
        
        self.morning_message_id = sent_message.message_id
        self.save_state()
        print(f"Morning message sent: {word_data['word']} ({word_data['ukrainian']})")
    
    async def send_evening_quiz(self):
        """Delete meaning and send quiz at 8:30 PM"""
        if not self.current_word:
            print("No current word found for quiz")
            return
        
        # Generate quiz options
        options, correct_index = self.generate_quiz_options(self.current_word['meaning'])
        
        # Create inline keyboard
        keyboard = []
        for i, option in enumerate(options):
            callback_data = f"answer_{i}_{correct_index}"
            keyboard.append([InlineKeyboardButton(option, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        quiz_message = f"🌙 *Quiz della Sera* 🌙\n\n"
        quiz_message += f"Qual è il significato di:\n\n"
        quiz_message += f"🇮🇹 *{self.current_word['word']}*\n"
        quiz_message += f"🇺🇦 *{self.current_word['ukrainian']}*\n\n"
        quiz_message += f"Scegli la risposta corretta:"
        
        await self.bot.send_message(
            chat_id=CHAT_ID,
            text=quiz_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        print(f"Evening quiz sent: {self.current_word['word']} ({self.current_word['ukrainian']})")
    
    async def handle_quiz_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle quiz answer callback"""
        query = update.callback_query
        await query.answer()
        
        # Parse callback data
        parts = query.data.split('_')
        selected_index = int(parts[1])
        correct_index = int(parts[2])
        
        if selected_index == correct_index:
            response = f"✅ *Corretto!* Bravissima! 🎉\n\n"
            response += f"🇮🇹 *{self.current_word['word']}*\n"
            response += f"🇺🇦 *{self.current_word['ukrainian']}*\n\n"
            response += f"*Significato:*\n{self.current_word['meaning']}"
            if 'example' in self.current_word:
                response += f"\n\n*Esempio:*\n_{self.current_word['example']}_"
        else:
            response = f"❌ *Sbagliato!* Ma non ti preoccupare! 💪\n\n"
            response += f"🇮🇹 *{self.current_word['word']}*\n"
            response += f"🇺🇦 *{self.current_word['ukrainian']}*\n\n"
            response += f"*Significato:*\n{self.current_word['meaning']}"
            if 'example' in self.current_word:
                response += f"\n\n*Esempio:*\n_{self.current_word['example']}_"
        
        await query.edit_message_text(text=response, parse_mode='Markdown')
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "👋 Ciao! Sono il bot delle parole italiane!\n\n"
            "Ogni giorno:\n"
            "🌅 Alle 8:00 - Parola del giorno con significato (IT/UK)\n"
            "🌙 Alle 20:30 - Quiz per testare la memoria!\n\n"
            "Usa /test_morning per testare il messaggio mattutino\n"
            "Usa /test_evening per testare il quiz serale"
        )
    
    async def test_morning(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test command for morning message"""
        await self.send_morning_message()
        await update.message.reply_text("✅ Messaggio mattutino inviato!")
    
    async def test_evening(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test command for evening quiz"""
        await self.send_evening_quiz()
        await update.message.reply_text("✅ Quiz serale inviato!")
    
    async def scheduled_morning_task(self, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled task for morning message"""
        await self.send_morning_message()
    
    async def scheduled_evening_task(self, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled task for evening quiz"""
        await self.send_evening_quiz()
    
    def setup_handlers(self):
        """Setup command and callback handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("test_morning", self.test_morning))
        self.application.add_handler(CommandHandler("test_evening", self.test_evening))
        self.application.add_handler(CallbackQueryHandler(self.handle_quiz_answer))
    
    def setup_scheduled_jobs(self):
        """Setup scheduled jobs"""
        job_queue = self.application.job_queue
        
        # Morning message at 8:00 AM Italian time
        morning_time = time(hour=8, minute=0, tzinfo=TIMEZONE)
        job_queue.run_daily(
            self.scheduled_morning_task,
            time=morning_time,
            name='morning_message'
        )
        
        # Evening quiz at 8:30 PM Italian time
        evening_time = time(hour=20, minute=30, tzinfo=TIMEZONE)
        job_queue.run_daily(
            self.scheduled_evening_task,
            time=evening_time,
            name='evening_quiz'
        )
        
        print(f"Scheduled jobs set up:")
        print(f"  Morning: {morning_time}")
        print(f"  Evening: {evening_time}")
    
    def run(self):
        """Start the bot"""
        self.setup_handlers()
        self.setup_scheduled_jobs()
        
        print("Bot is running...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = ItalianWordBot()
    bot.run()
