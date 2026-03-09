# italian_word_bot.py
import os
import json
import random
import asyncio
from datetime import time, datetime, timedelta
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import pytz

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
TIMEZONE = pytz.timezone('Europe/Rome')
WORDS_FILE = 'italian_words.json'
SEEN_WORDS_FILE = 'seen_words.json'
WEEKLY_HISTORY_FILE = 'weekly_history.json'
QUIZ_QUESTIONS_COUNT = 5

# Quiz timing configuration (in seconds)
QUIZ_INTRO_DELAY_SECONDS = 3
QUIZ_QUESTION_DELAY_SECONDS = 30  # Time between questions for users to answer
QUIZ_FINAL_WAIT_SECONDS = 30  # Time to wait before showing results

class ItalianWordBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.bot = self.application.bot
        self.quiz_scores = {}  # Track scores for current quiz session

    def load_words(self):
        """Load Italian words from JSON file"""
        with open(WORDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_seen_words(self):
        """Load the set of already-seen word indices from JSON"""
        try:
            with open(SEEN_WORDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('seen', []))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def save_seen_words(self, seen):
        """Persist the set of seen word indices to JSON"""
        with open(SEEN_WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'seen': list(seen)}, f)

    def load_weekly_history(self):
        """Load the history of words sent during the week"""
        try:
            with open(WEEKLY_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'history': []}

    def save_weekly_history(self, history):
        """Persist the weekly history to JSON"""
        with open(WEEKLY_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def add_to_weekly_history(self, word_data):
        """Add a word to the weekly history with timestamp"""
        history = self.load_weekly_history()
        entry = {
            'word': word_data['word'],
            'ukrainian': word_data['ukrainian'],
            'meaning': word_data['meaning'],
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }
        history['history'].append(entry)
        self.save_weekly_history(history)

    def get_words_from_last_week(self):
        """Get words sent in the last 7 days"""
        history = self.load_weekly_history()
        now = datetime.now(TIMEZONE)
        week_ago = now - timedelta(days=7)
        
        recent_words = []
        for entry in history['history']:
            entry_time = datetime.fromisoformat(entry['timestamp'])
            if entry_time >= week_ago:
                recent_words.append(entry)
        
        return recent_words

    def clear_old_history(self):
        """Remove entries older than 7 days from history"""
        history = self.load_weekly_history()
        now = datetime.now(TIMEZONE)
        week_ago = now - timedelta(days=7)
        
        filtered_history = []
        for entry in history['history']:
            entry_time = datetime.fromisoformat(entry['timestamp'])
            if entry_time >= week_ago:
                filtered_history.append(entry)
        
        self.save_weekly_history({'history': filtered_history})

    def get_random_word(self):
        """Get a random Italian word, avoiding repetition until all words are cycled"""
        words = self.load_words()['words']
        seen = self.load_seen_words()

        # Reset if all words have been cycled through
        if len(seen) >= len(words):
            seen = set()

        available = list(set(range(len(words))) - seen)
        if not available:
            seen = set()
            available = list(range(len(words)))

        chosen_index = random.choice(available)
        seen.add(chosen_index)
        self.save_seen_words(seen)
        return words[chosen_index]

    async def send_morning_message(self):
        """Send the word of the day"""
        word_data = self.get_random_word()
        
        # Add to weekly history for quiz
        self.add_to_weekly_history(word_data)
        
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
        print(f"Morning message sent: {word_data['word']} ({word_data['ukrainian']})")

    async def scheduled_morning_task(self, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled task for morning message"""
        await self.send_morning_message()

    def get_quiz_words(self):
        """Get words for the quiz - from history if available, otherwise random"""
        weekly_words = self.get_words_from_last_week()
        all_words = self.load_words()['words']
        
        quiz_words = []
        
        # Use words from history if we have enough
        if len(weekly_words) >= QUIZ_QUESTIONS_COUNT:
            quiz_words = random.sample(weekly_words, QUIZ_QUESTIONS_COUNT)
        elif len(weekly_words) > 0:
            # Use all available history words and fill the rest with random words
            quiz_words = weekly_words.copy()
            needed = QUIZ_QUESTIONS_COUNT - len(quiz_words)
            # Get random words that aren't already in the quiz
            quiz_word_names = [w['word'] for w in quiz_words]
            available_random = [w for w in all_words if w['word'] not in quiz_word_names]
            if len(available_random) >= needed:
                quiz_words.extend(random.sample(available_random, needed))
            else:
                quiz_words.extend(available_random)
        else:
            # No history, use random words
            quiz_words = random.sample(all_words, min(QUIZ_QUESTIONS_COUNT, len(all_words)))
        
        return quiz_words

    def get_wrong_options(self, correct_word, count=3):
        """Get wrong answer options for a quiz question"""
        all_words = self.load_words()['words']
        wrong_options = []
        
        for word in all_words:
            if word['word'] != correct_word['word']:
                wrong_options.append(word['ukrainian'])
        
        return random.sample(wrong_options, min(count, len(wrong_options)))

    async def send_quiz_intro(self):
        """Send an engaging quiz introduction message"""
        intro_messages = [
            "🎉 *Buongiorno e benvenuti al Quiz della Settimana!* 🎉\n\n"
            "Ciao caro studente! È domenica, il giorno perfetto per mettere alla prova "
            "quello che hai imparato questa settimana! 📚✨\n\n"
            "Ti proporrò alcune parole che abbiamo studiato insieme. "
            "Riesci a ricordare il significato di ognuna? 🤔\n\n"
            "Preparati, si comincia! Buona fortuna! 🍀",
            
            "🌟 *È arrivato il momento del Quiz Settimanale!* 🌟\n\n"
            "Che bella domenica per ripassare insieme! 🌞\n\n"
            "Spero che tu abbia riposato bene, perché adesso metteremo alla prova "
            "la tua memoria con le parole della settimana! 🧠💪\n\n"
            "Non ti preoccupare, sono sicuro che farai un ottimo lavoro! "
            "Andiamo! 🚀",
            
            "🎊 *Quiz Time! È domenica, amici!* 🎊\n\n"
            "Buongiorno carissimo! Come stai oggi? 😊\n\n"
            "È il momento di fare un piccolo gioco insieme! "
            "Ti mostrerò il significato di alcune parole e tu dovrai "
            "indovinare quale parola italiana corrisponde! 🇮🇹🇺🇦\n\n"
            "Sei pronto? Via! 🎯"
        ]
        
        message = random.choice(intro_messages)
        await self.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='Markdown'
        )

    async def send_quiz_question(self, question_num, total, word_data, context):
        """Send a single quiz question with multiple choice options"""
        correct_answer = word_data['word']
        wrong_options = self.get_wrong_options(word_data)
        
        # Create options list and shuffle
        options = [correct_answer] + wrong_options
        random.shuffle(options)
        
        # Store correct answer in context for later verification
        quiz_key = f"quiz_{question_num}"
        context.bot_data[quiz_key] = correct_answer
        
        # Engaging question phrases
        question_phrases = [
            f"*Domanda {question_num}/{total}* 🤓\n\n",
            f"*Ecco la domanda {question_num} di {total}!* 🎯\n\n",
            f"*Numero {question_num} su {total} - Forza!* 💪\n\n",
        ]
        
        message = random.choice(question_phrases)
        message += f"Quale parola italiana significa:\n\n"
        message += f"🇺🇦 *{word_data['ukrainian']}*\n\n"
        message += f"📖 _{word_data['meaning']}_"
        
        # Create inline keyboard with options
        keyboard = []
        for i, option in enumerate(options):
            callback_data = f"quiz_{question_num}_{option}"
            keyboard.append([InlineKeyboardButton(option, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def handle_quiz_answer(self, update, context):
        """Handle quiz answer callback"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        if not data.startswith("quiz_"):
            return
        
        parts = data.split("_", 2)
        if len(parts) < 3:
            return
        
        question_num = parts[1]
        user_answer = parts[2]
        quiz_key = f"quiz_{question_num}"
        
        correct_answer = context.bot_data.get(quiz_key, "")
        
        if user_answer == correct_answer:
            # Correct answer responses
            correct_responses = [
                "✅ *Bravissimo!* Hai risposto correttamente! 🎉",
                "✅ *Esatto!* Che memoria fantastica! 🌟",
                "✅ *Perfetto!* Sei davvero bravo! 💯",
                "✅ *Giusto!* Complimenti, continua così! 👏",
                "✅ *Eccellente!* La risposta è corretta! 🏆"
            ]
            response = random.choice(correct_responses)
            
            # Update score
            user_id = str(query.from_user.id) if query.from_user else "default"
            if user_id not in self.quiz_scores:
                self.quiz_scores[user_id] = 0
            self.quiz_scores[user_id] += 1
        else:
            # Wrong answer responses
            wrong_responses = [
                f"❌ *Ops!* La risposta corretta era: *{correct_answer}*\n"
                "Non ti preoccupare, succede a tutti! 💪",
                f"❌ *Quasi!* Era *{correct_answer}*\n"
                "La prossima volta andrà meglio! 🌈",
                f"❌ *Peccato!* La parola giusta era *{correct_answer}*\n"
                "Continua a studiare, ce la farai! 📚",
                f"❌ *Non proprio!* Cercavamo *{correct_answer}*\n"
                "Ma non mollare, stai imparando! 🌱"
            ]
            response = random.choice(wrong_responses)
        
        await query.edit_message_text(
            text=f"{query.message.text}\n\n{response}",
            parse_mode='Markdown'
        )

    async def send_quiz_results(self):
        """Send the final quiz results with encouraging message"""
        result_messages = []
        
        for user_id, score in self.quiz_scores.items():
            percentage = (score / QUIZ_QUESTIONS_COUNT) * 100
            
            if percentage == 100:
                praise = (
                    "🏆 *PERFETTO!* 🏆\n\n"
                    "Incredibile! Hai risposto correttamente a TUTTE le domande! "
                    "Sei un vero campione! 🌟🎉\n\n"
                    f"Punteggio: *{score}/{QUIZ_QUESTIONS_COUNT}* (100%)"
                )
            elif percentage >= 80:
                praise = (
                    "🌟 *Ottimo lavoro!* 🌟\n\n"
                    "Fantastico! Hai fatto davvero bene questa settimana! "
                    "Continua così! 💪\n\n"
                    f"Punteggio: *{score}/{QUIZ_QUESTIONS_COUNT}* ({int(percentage)}%)"
                )
            elif percentage >= 60:
                praise = (
                    "👍 *Buon risultato!* 👍\n\n"
                    "Bravo! Stai facendo progressi! "
                    "Con un po' più di pratica sarai perfetto! 📚\n\n"
                    f"Punteggio: *{score}/{QUIZ_QUESTIONS_COUNT}* ({int(percentage)}%)"
                )
            elif percentage >= 40:
                praise = (
                    "💪 *Non male!* 💪\n\n"
                    "Ci stai provando e questo è importante! "
                    "Ricorda di ripassare le parole durante la settimana! 🌱\n\n"
                    f"Punteggio: *{score}/{QUIZ_QUESTIONS_COUNT}* ({int(percentage)}%)"
                )
            else:
                praise = (
                    "📚 *Continua a studiare!* 📚\n\n"
                    "Non ti scoraggiare! Imparare una nuova lingua richiede tempo e pazienza. "
                    "La prossima settimana andrà meglio! 🌈\n\n"
                    f"Punteggio: *{score}/{QUIZ_QUESTIONS_COUNT}* ({int(percentage)}%)"
                )
            
            result_messages.append(praise)
        
        # If no one answered, send a general message
        if not result_messages:
            result_messages.append(
                "🎯 *Quiz completato!* 🎯\n\n"
                "Spero che ti sia divertito! "
                "Ci vediamo la prossima settimana con nuove parole! 👋"
            )
        
        closing = (
            "\n\n────────────────\n"
            "Grazie per aver partecipato al quiz! 🙏\n"
            "Ci vediamo la prossima settimana con nuove parole da imparare! "
            "Buona domenica! ☀️🇮🇹"
        )
        
        for msg in result_messages:
            await self.bot.send_message(
                chat_id=CHAT_ID,
                text=msg + closing,
                parse_mode='Markdown'
            )
        
        # Reset scores for next week
        self.quiz_scores = {}
        
        # Clean up old history
        self.clear_old_history()

    async def run_weekly_quiz(self, context: ContextTypes.DEFAULT_TYPE):
        """Run the complete weekly quiz session"""
        print("Starting weekly quiz session...")
        
        # Reset scores
        self.quiz_scores = {}
        
        # Send introduction
        await self.send_quiz_intro()
        
        # Wait a moment before sending questions
        await asyncio.sleep(QUIZ_INTRO_DELAY_SECONDS)
        
        # Get quiz words
        quiz_words = self.get_quiz_words()
        total_questions = len(quiz_words)
        
        # Send each question with a delay to give users time to answer
        for i, word_data in enumerate(quiz_words, 1):
            await self.send_quiz_question(i, total_questions, word_data, context)
            await asyncio.sleep(QUIZ_QUESTION_DELAY_SECONDS)
        
        # Wait for final answers and send results
        await asyncio.sleep(QUIZ_FINAL_WAIT_SECONDS)
        await self.send_quiz_results()
        
        print("Weekly quiz session completed.")

    async def test_command(self, update, context):
        """Test command to send message immediately"""
        await self.send_morning_message()
        await update.message.reply_text("✅ Messaggio inviato!")

    async def test_quiz_command(self, update, context):
        """Test command to run quiz immediately"""
        await update.message.reply_text("🎯 Avvio del quiz di prova...")
        await self.run_weekly_quiz(context)

    def setup_handlers(self):
        """Setup command handlers"""
        self.application.add_handler(CommandHandler("test", self.test_command))
        self.application.add_handler(CommandHandler("quiz", self.test_quiz_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_quiz_answer, pattern="^quiz_"))

    def setup_scheduled_jobs(self):
        """Setup scheduled jobs for morning message and weekly quiz"""
        job_queue = self.application.job_queue
        
        # Morning message at 8:00 AM Italian time
        morning_time = time(hour=8, minute=0, tzinfo=TIMEZONE)
        job_queue.run_daily(
            self.scheduled_morning_task,
            time=morning_time,
            name='morning_message'
        )
        print(f"Scheduled morning message at: {morning_time}")
        
        # Weekly quiz every Sunday at 13:00 Italian time
        quiz_time = time(hour=13, minute=0, tzinfo=TIMEZONE)
        job_queue.run_daily(
            self.run_weekly_quiz,
            time=quiz_time,
            days=(6,),  # 6 = Sunday (0 = Monday in python-telegram-bot)
            name='weekly_quiz'
        )
        print(f"Scheduled weekly quiz at: {quiz_time} on Sundays")

    def run(self):
        """Start the bot"""
        self.setup_handlers()
        self.setup_scheduled_jobs()
        print("Bot is running...")
        self.application.run_polling()

if __name__ == '__main__':
    bot = ItalianWordBot()
    bot.run()
