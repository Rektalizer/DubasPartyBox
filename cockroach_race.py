import json
import random
import asyncio
import telegram
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

# Глобальное хранилище состояния игр для каждого чата
game_states = {}

# Обработчик команды /buyin
async def buyin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or user.first_name
    user_id = str(user.id)

    # Загрузка данных пользователей
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}

    if user_id in users:
        await update.message.reply_text(f"{username}, вы уже зарегистрированы!")
    else:
        users[user_id] = {
            'username': username,
            'balance': 1000,
            'times_below_100': 0,
            'consecutive_wins': 0,
            'achievements': []  # Новый список достижений
        }
        with open('users.json', 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False)
        await update.message.reply_text(f"{username}, вы успешно зарегистрировались и получили 1000 монет!")


# Обработчик команды /stats
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}

    if not users:
        await update.message.reply_text("Нет зарегистрированных игроков.")
    else:
        leaderboard = sorted(users.items(), key=lambda x: x[1]['balance'], reverse=True)
        message = "Таблица лидеров:\n"
        for idx, (user_id, data) in enumerate(leaderboard, start=1):
            times_below_100 = data.get('times_below_100', 0)
            message += f"{idx}. {data['username']}: {data['balance']} монет (Баланс падал ниже 100 монет: {times_below_100} раз)\n"
        await update.message.reply_text(message)

# Обработчик команды /start
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in game_states:
        await update.message.reply_text("Игра уже запущена!")
        return

    # Загрузка имен тараканов
    try:
        with open('cockroach_names.json', 'r', encoding='utf-8') as f:
            cockroach_names = json.load(f)
    except FileNotFoundError:
        cockroach_names = ['Быстрый', 'Удачливый', 'Целеустремлённый', 'Скоростной', 'Резвый', 'Проворный']

    # Генерация случайного количества тараканов от 2 до 6
    num_cockroaches = random.randint(2, 6)
    random.shuffle(cockroach_names)
    selected_names = cockroach_names[:num_cockroaches]

    cockroaches = []
    for i, name in enumerate(selected_names, start=1):
        cockroach = {
            'name': name,
            'speed': random.randint(0, 100),
            'determination': random.randint(0, 100),
            'luck': random.randint(0, 100),
            'position': 0,
            'symbol': str(i),  # Используем номер таракана как символ
            'number': i
        }
        cockroaches.append(cockroach)

    # Расчет силы и коэффициентов
    strengths = [c['speed'] + c['determination'] + c['luck'] for c in cockroaches]
    total_strength = sum(strengths)

    for c in cockroaches:
        strength = c['speed'] + c['determination'] + c['luck']
        # Расчёт вероятности победы
        win_probability = strength / total_strength
        # Коэффициент рассчитывается как обратная величина вероятности победы
        odds = round((1 / win_probability), 2)
        c['odds'] = odds

    # Сохранение состояния игры
    game_states[chat_id] = {
        'cockroaches': cockroaches,
        'bets': {},
        'betting_open': True,
    }

    message = "Тараканьи бега начались!\n" \
              "Сделайте ставку командой /bet номер_таракана сумма_ставки\n"
    for c in cockroaches:
        message += f"{c['number']}. {c['name']} (коэффициент {c['odds']})\n"
    message += "Ставки принимаются в течение одной минуты."

    await update.message.reply_text(message)

    # Закрытие ставок и запуск гонки через минуту
    asyncio.create_task(close_betting_and_start_race(chat_id, context))


# Обработчик команды /bet
async def bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name

    if chat_id not in game_states or not game_states[chat_id]['betting_open']:
        await update.message.reply_text("Сейчас нельзя делать ставки.")
        return

    # Парсинг аргументов
    try:
        cockroach_number = int(context.args[0])
        bet_amount = int(context.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("Используйте формат: /bet номер_таракана сумма_ставки")
        return

    # Проверка номера таракана
    cockroach_numbers = [c['number'] for c in game_states[chat_id]['cockroaches']]
    if cockroach_number not in cockroach_numbers:
        await update.message.reply_text("Неверный номер таракана.")
        return

    # Загрузка баланса пользователя
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}

    if user_id not in users:
        await update.message.reply_text("Вы не зарегистрированы. Используйте команду /buyin для регистрации.")
        return

    if bet_amount <= 0:
        await update.message.reply_text("Сумма ставки должна быть положительной.")
        return

    if users[user_id]['balance'] < bet_amount:
        await update.message.reply_text("У вас недостаточно средств для этой ставки.")
        return

    # Списание ставки
    users[user_id]['balance'] -= bet_amount

    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False)

    # Запись ставки
    if user_id not in game_states[chat_id]['bets']:
        game_states[chat_id]['bets'][user_id] = []
    game_states[chat_id]['bets'][user_id].append({
        'cockroach_number': cockroach_number,
        'bet_amount': bet_amount,
    })

    await update.message.reply_text(f"{username}, ваша ставка на таракана {cockroach_number} в размере {bet_amount} монет принята!")


# Функция для закрытия ставок и запуска гонки
async def close_betting_and_start_race(chat_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        await asyncio.sleep(60)

        if chat_id not in game_states:
            return

        game_state = game_states[chat_id]
        game_state['betting_open'] = False

        cockroaches = game_state['cockroaches']
        positions = {c['number']: c['position'] for c in cockroaches}
        symbols = {c['number']: c['symbol'] for c in cockroaches}

        # Загрузка событий из events.json и применение их к тараканам
        try:
            with open('events.json', 'r', encoding='utf-8') as f:
                events = json.load(f)
        except FileNotFoundError:
            events = []

        # Обработка случайных событий для каждого таракана
        event_messages = []
        for cockroach in cockroaches:
            if random.randint(1, 100) <= 20 and events:  # 20% шанс события и наличие событий
                event = random.choice(events)
                # Применение эффектов события
                speed = cockroach['speed']
                determination = cockroach['determination']
                luck = cockroach['luck']

                # Создаём локальный словарь для exec
                local_vars = {
                    'speed': speed,
                    'determination': determination,
                    'luck': luck
                }

                # Выполняем выражения эффектов
                try:
                    exec(event['effectSpeed'], {}, local_vars)
                    exec(event['effectDetermination'], {}, local_vars)
                    exec(event['effectLuck'], {}, local_vars)
                except Exception as e:
                    print(f"Ошибка при применении эффекта: {e}")

                # Обновляем характеристики таракана
                cockroach['speed'] = max(0, min(100, int(local_vars['speed'])))
                cockroach['determination'] = max(0, min(100, int(local_vars['determination'])))
                cockroach['luck'] = max(0, min(100, int(local_vars['luck'])))

                # Формируем сообщение о событии
                description = event['description'].replace('ROACH_NAME', cockroach['name'])
                event_messages.append(description)

        # Отправляем сообщения о событиях
        if event_messages:
            await context.bot.send_message(chat_id, "Случайные события перед гонкой:\n" + "\n".join(event_messages))

        # Инициализация сообщения гонки
        race_message_content = get_race_message(positions, symbols)
        race_message = await context.bot.send_message(chat_id, race_message_content)
        previous_race_message_content = race_message_content

        finish_line = 20
        winners = []

        while not winners:
            await asyncio.sleep(2)
            for c in cockroaches:
                if c['number'] in winners:
                    continue
                move = calculate_move(c)
                positions[c['number']] += move
                if positions[c['number']] >= finish_line:
                    winners.append(c['number'])

            # Обновление сообщения гонки
            race_message_content = get_race_message(positions, symbols)
            if race_message_content != previous_race_message_content:
                try:
                    await race_message.edit_text(race_message_content)
                    previous_race_message_content = race_message_content
                except telegram.error.BadRequest as e:
                    if "Message is not modified" in str(e):
                        pass  # Игнорируем эту ошибку
                    else:
                        print(f"Ошибка при обновлении сообщения гонки: {e}")

        # Если несколько тараканов достигли финиша одновременно, выбираем победителя случайно
        winning_cockroach_number = random.choice(winners)
        winning_cockroach = next(c for c in cockroaches if c['number'] == winning_cockroach_number)

        # Загрузка баланса пользователей
        try:
            with open('users.json', 'r', encoding='utf-8') as f:
                users = json.load(f)
        except FileNotFoundError:
            users = {}

        # Расчет выплат
        payouts = []
        for user_id, bets in game_state['bets'].items():
            user_id_str = str(user_id)
            username = users.get(user_id_str, {}).get('username', 'Игрок')
            user_data = users.get(user_id_str, {
                'username': username,
                'balance': 0,
                'times_below_100': 0,
                'consecutive_wins': 0,
                'achievements': []
            })

            total_win = 0
            total_bet = 0
            detailed_bet_results = []

            for bet in bets:
                bet_amount = bet['bet_amount']
                cockroach_number = bet['cockroach_number']
                total_bet += bet_amount

                if cockroach_number == winning_cockroach_number:
                    odds = next(c['odds'] for c in cockroaches if c['number'] == cockroach_number)
                    winnings = int(round(bet_amount * odds))
                    total_win += winnings
                    detailed_bet_results.append(f"вы выиграли {winnings} монет по ставке на таракана {cockroach_number}")
                else:
                    detailed_bet_results.append(f"вы проиграли {bet_amount} монет по ставке на таракана {cockroach_number}")

            net_result = total_win - total_bet
            user_data['balance'] += total_win

            if net_result > 0:
                payouts.append(f"{username}, вы выиграли! {'; '.join(detailed_bet_results)}. Вы в плюсе на {net_result} монет!\n")
                # Обработка победных ставок подряд
                user_data['consecutive_wins'] = user_data.get('consecutive_wins', 0) + 1

                # Проверка достижения 3 побед подряд
                if user_data['consecutive_wins'] >= 3:
                    achievements = user_data.get('achievements', [])
                    if '🍀' not in achievements:
                        achievements.append('🍀')
                        user_data['achievements'] = achievements
                        payouts.append(f"{username} получил достижение 🍀 за 3 победных ставки подряд!\n")
            else:
                payouts.append(f"{username}, вы проиграли. {'; '.join(detailed_bet_results)}. Вы в минусе на {-net_result} монет.\n")
                # Сброс победных ставок подряд
                user_data['consecutive_wins'] = 0

            # Проверка баланса и пополнение, если он ниже или равен 100 монет
            if user_data['balance'] <= 100:
                user_data['balance'] += 500
                user_data['times_below_100'] = user_data.get('times_below_100', 0) + 1
                payouts.append(f"{username}, ваш баланс ниже или равен 100 монет после гонки. Вам начислено 500 монет для отыгрыша.\n")

            # Проверка достижения баланса 10000 монет
            if user_data['balance'] >= 10000:
                achievements = user_data.get('achievements', [])
                if '🏆' not in achievements:
                    achievements.append('🏆')
                    user_data['achievements'] = achievements
                    payouts.append(f"{username} получил достижение 🏆 за достижение баланса в 10000 монет!\n")

            # Обновляем данные пользователя
            users[user_id_str] = user_data

        # Сохранение баланса пользователей
        with open('users.json', 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False)

        # Отправка результатов
        result_message = f"Победил таракан {winning_cockroach['name']}!\n"
        result_message += "\n".join(payouts)

        await context.bot.send_message(chat_id, result_message)

        # Удаление состояния игры
        del game_states[chat_id]

    except Exception as e:
        # Обработка любых неожиданных ошибок
        print(f"Ошибка в функции close_betting_and_start_race: {e}")
        await context.bot.send_message(chat_id, "Произошла ошибка во время гонки. Пожалуйста, попробуйте снова позже.")




# Функция для формирования сообщения гонки
def get_race_message(positions, symbols):
    finish_line = 20
    race_lines = []
    for number in positions:
        position = positions[number]
        symbol = symbols[number]
        line = '-' * min(position, finish_line) + symbol + '-' * max(finish_line - position, 0) + ':'
        race_lines.append(line)
    return "\n".join(race_lines)

# Функция для расчета движения таракана
def calculate_move(cockroach):
    speed = cockroach['speed']
    determination = cockroach['determination']
    luck = cockroach['luck']

    max_move = (speed // 20) + 1

    moves = False
    if random.randint(1, 100) <= determination:
        moves = True
    else:
        if random.randint(1, 100) <= luck:
            moves = True

    if not moves:
        return 0

    move_distance = random.randint(1, max_move)

    if random.randint(1, 100) <= luck:
        move_distance *= 2

    return move_distance

async def shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if update.effective_chat.type != 'private':
        await update.message.reply_text("Меню покупок доступно только в личной переписке с ботом.")
        return

    await update.message.reply_text(
        "Добро пожаловать в магазин!\nЗа 1000 монет вы можете добавить новое имя таракана.\n"
        "Введите имя (до 30 символов), которое хотите добавить:",
    )

    return "WAITING_FOR_NAME"

async def add_cockroach_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name
    new_name = update.message.text.strip()

    if len(new_name) > 30:
        await update.message.reply_text("Имя слишком длинное. Пожалуйста, введите имя не длиннее 30 символов.")
        return "WAITING_FOR_NAME"

    # Загрузка данных пользователей
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}

    if user_id not in users:
        await update.message.reply_text("Вы не зарегистрированы. Используйте команду /buyin для регистрации.")
        return ConversationHandler.END

    if users[user_id]['balance'] < 1000:
        await update.message.reply_text("У вас недостаточно средств для этой покупки.")
        return ConversationHandler.END

    # Списание средств
    users[user_id]['balance'] -= 1000

    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False)

    # Добавление имени в cockroach_names.json
    try:
        with open('cockroach_names.json', 'r', encoding='utf-8') as f:
            cockroach_names = json.load(f)
    except FileNotFoundError:
        cockroach_names = []

    cockroach_names.append(new_name)

    with open('cockroach_names.json', 'w', encoding='utf-8') as f:
        json.dump(cockroach_names, f, ensure_ascii=False)

    await update.message.reply_text(f"Имя '{new_name}' успешно добавлено в список тараканов!")

    return ConversationHandler.END
# Главная функция

# Обработчик команды /rewards
async def rewards_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open('rewards.json', 'r', encoding='utf-8') as f:
            rewards = json.load(f)
    except FileNotFoundError:
        rewards = []

    if not rewards:
        await update.message.reply_text("Список достижений пуст.")
        return

    message = "Список достижений:\n"
    for reward in rewards:
        message += f"{reward['Reward']} - {reward['Description']}\n"

    await update.message.reply_text(message)


from telegram.ext import ConversationHandler, MessageHandler, filters

# Определяем состояние для ConversationHandler
WAITING_FOR_NAME = "WAITING_FOR_NAME"

# Создаем ConversationHandler для /shop
shop_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('shop', shop_handler)],
    states={
        WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cockroach_name_handler)],
    },
    fallbacks=[],
)

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}

    if not users:
        await update.message.reply_text("Нет зарегистрированных игроков.")
    else:
        leaderboard = sorted(users.items(), key=lambda x: x[1]['balance'], reverse=True)
        message = "Таблица лидеров:\n"
        for idx, (user_id, data) in enumerate(leaderboard, start=1):
            times_below_100 = data.get('times_below_100', 0)
            achievements = ''.join(data.get('achievements', []))  # Получаем достижения
            message += f"{idx}. {data['username']}: {data['balance']} монет {achievements} (Баланс падал ниже 100 монет: {times_below_100} раз)\n"
    await update.message.reply_text(message)

cockroach_handlers = [
            CommandHandler('buyin', buyin_handler),
            CommandHandler('stats', stats_handler),
            CommandHandler('start', start_handler),
            CommandHandler('bet', bet_handler),
            CommandHandler('rewards', rewards_handler),  # Добавим позже
            ]