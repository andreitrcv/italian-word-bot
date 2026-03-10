import asyncio
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from italian_word_bot import ItalianWordBot


class ItalianWordBotTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.words_file = f"{self.temp_dir.name}/words.json"
        self.sent_words_file = f"{self.temp_dir.name}/sent_words.json"

        with open(self.words_file, 'w', encoding='utf-8') as f:
            json.dump({
                'words': [
                    {
                        'word': 'Ciao',
                        'ukrainian': 'Привіт',
                        'meaning': 'Saluto informale'
                    },
                    {
                        'word': 'Arrivederci',
                        'ukrainian': 'До побачення',
                        'meaning': 'Saluto di commiato'
                    }
                ]
            }, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_bot(self, send_message=None):
        bot = SimpleNamespace(send_message=send_message or AsyncMock())
        application = SimpleNamespace(bot=bot)
        return ItalianWordBot(
            application=application,
            words_file=self.words_file,
            sent_words_file=self.sent_words_file
        )

    def load_sent_words(self):
        with open(self.sent_words_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_get_random_word_skips_words_in_current_cycle(self):
        with open(self.sent_words_file, 'w', encoding='utf-8') as f:
            json.dump({
                'history': [{'word': 'Ciao', 'sent_at': '2026-03-10T08:00:00+01:00'}],
                'current_cycle': ['Ciao']
            }, f)

        bot = self.create_bot()
        chosen_word = bot.get_random_word()

        self.assertEqual(chosen_word['word'], 'Arrivederci')

    def test_get_random_word_resets_cycle_after_all_words_are_used(self):
        with open(self.sent_words_file, 'w', encoding='utf-8') as f:
            json.dump({
                'history': [
                    {'word': 'Ciao', 'sent_at': '2026-03-10T08:00:00+01:00'},
                    {'word': 'Arrivederci', 'sent_at': '2026-03-11T08:00:00+01:00'}
                ],
                'current_cycle': ['Ciao', 'Arrivederci']
            }, f)

        bot = self.create_bot()

        with patch('italian_word_bot.random.choice', side_effect=lambda words: words[0]):
            chosen_word = bot.get_random_word()

        self.assertEqual(chosen_word['word'], 'Ciao')
        self.assertEqual(self.load_sent_words()['current_cycle'], [])

    def test_send_morning_message_records_sent_word_after_successful_send(self):
        send_message = AsyncMock()
        bot = self.create_bot(send_message=send_message)

        with patch('italian_word_bot.random.choice', side_effect=lambda words: words[0]):
            asyncio.run(bot.send_morning_message())

        send_message.assert_awaited_once()
        sent_words = self.load_sent_words()
        self.assertEqual(sent_words['current_cycle'], ['Ciao'])
        self.assertEqual(sent_words['history'][0]['word'], 'Ciao')


if __name__ == '__main__':
    unittest.main()
