# pole_chudes.py

import json
import random
import time
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

# Глобальное хранилище состояния игр для каждого чата
pole_games = {}

# Загрузка списка слов из pole_words.json
try:
    with open('pole_words.json', 'r', encoding='utf-8') as f:
        pole_words = json.load(f)
except FileNotFoundError:
    pole_words = ['ПРИМЕР', 'СЛОВО', 'ИГРОК', 'БОТ', 'ПИТОН']  # Слова по умолчанию

# Обработчик команды /pole для запуска игры
async def pole_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id in pole_games:
        await update.message.reply_text("Игра уже запущена!")
        return

    word = random.choice(pole_words).upper()
    game_state = {
        'word': word,
        'display_word': ['■' for _ in word],
        'guessed_letters': set(),
        'players': {},
        'last_guess_time': {},
    }

    pole_games[chat_id] = game_state
    await update.message.reply_text(f"Загаданное слово:\n{''.join(game_state['display_word'])}")
    pass

# Обработчик сообщений игроков
async def pole_guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in pole_games:
        return

    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name
    message_text = update.message.text.strip().upper()

    game_state = pole_games[chat_id]

    if len(message_text) == 1 and message_text.isalpha():
        # Проверка временного ограничения (5 секунд)
        last_time = game_state['last_guess_time'].get(user_id, 0)
        current_time = time.time()
        if current_time - last_time < 5:
            await update.message.reply_text(f"{username}, нельзя отправлять буквы чаще чем раз в 5 секунд!")
            return

        game_state['last_guess_time'][user_id] = current_time

        # Обработка буквы
        letter = message_text

        if letter in game_state['guessed_letters']:
            game_state['players'][user_id] = game_state['players'].get(user_id, 0) - 1
            await update.message.reply_text(f"Буква {letter} уже называлась, {username} теряет 1 очко!")
        else:
            game_state['guessed_letters'].add(letter)
            if letter in game_state['word']:
                indices = [i for i, l in enumerate(game_state['word']) if l == letter]
                for i in indices:
                    game_state['display_word'][i] = letter

                points = len(indices)
                game_state['players'][user_id] = game_state['players'].get(user_id, 0) + points

                await update.message.reply_text(f"{username} получает {points} очко(а), угадав букву {letter}!")
                await update.message.reply_text(''.join(game_state['display_word']))

                if '■' not in game_state['display_word']:
                    await end_pole_game(chat_id, context, winner_id=None)
            else:
                await update.message.reply_text(f"Буквы {letter} нет в этом слове!")

    elif message_text.isalpha() and message_text == game_state['word']:
        # Обработка верно отгаданного слова
        unguessed_letters = game_state['display_word'].count('■')
        points = (len(game_state['word']) // 2) + unguessed_letters
        game_state['players'][user_id] = game_state['players'].get(user_id, 0) + points

        await update.message.reply_text(f"{username} отгадал слово {game_state['word']} и получает {points} очков!")
        await end_pole_game(chat_id, context, winner_id=user_id)
    else:
        # Игнорируем остальные сообщения
        return


# Функция завершения игры и отображения результатов
async def end_pole_game(chat_id, context, winner_id=None):
    game_state = pole_games[chat_id]

    result_message = "Результат игры:\n"
    for user_id, score in game_state['players'].items():
        try:
            user = await context.bot.get_chat_member(chat_id, int(user_id))
            username = user.user.username or user.user.first_name
        except:
            username = "Игрок"

        result_message += f"{username}: {score} очков\n"

        # Обновление users_pole.json
        try:
            with open('users_pole.json', 'r', encoding='utf-8') as f:
                users_pole = json.load(f)
        except FileNotFoundError:
            users_pole = {}

        user_data = users_pole.get(user_id, {'username': username, 'score': 0, 'words_guessed': 0})
        user_data['score'] += score

        # Проверка на победителя
        if winner_id is not None and user_id == winner_id:
            user_data['words_guessed'] += 1

        users_pole[user_id] = user_data

    with open('users_pole.json', 'w', encoding='utf-8') as f:
        json.dump(users_pole, f, ensure_ascii=False)

    await context.bot.send_message(chat_id, result_message)
    del pole_games[chat_id]


# Обработчик команды /stats_pole для отображения статистики
async def stats_pole_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open('users_pole.json', 'r', encoding='utf-8') as f:
            users_pole = json.load(f)
    except FileNotFoundError:
        users_pole = {}

    if not users_pole:
        await update.message.reply_text("Нет данных об игроках.")
        return

    message = "Статистика игроков в 'Поле чудес':\n"
    sorted_users = sorted(users_pole.items(), key=lambda x: x[1]['score'], reverse=True)
    for user_id, data in sorted_users:
        message += f"{data['username']}: {data['score']} очков, {data['words_guessed']} отгаданных слов\n"

    await update.message.reply_text(message)

# Список обработчиков для экспорта
pole_handlers = [
    CommandHandler('pole', pole_handler),
    CommandHandler('stats_pole', stats_pole_handler),
    MessageHandler(filters.TEXT & ~filters.COMMAND, pole_guess_handler),  # Убедитесь, что фильтр настроен правильно
]
