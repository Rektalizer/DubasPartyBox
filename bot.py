import json
import random
import asyncio
import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler
from telegram import ReplyKeyboardMarkup, KeyboardButton
from cockroach_race import cockroach_handlers
from pole_chudes import pole_handlers

def main():
    application = ApplicationBuilder().token('7532037848:AAHwDa2d0Y_9Mx0iqddQZcCRe-a7MEN_CFY').build()

    # Добавление обработчиков из cockroach_race.py
    for handler in cockroach_handlers:
        application.add_handler(handler)

    # Добавление обработчиков из pole_chudes.py
    for handler in pole_handlers:
        application.add_handler(handler)

    application.run_polling()

if __name__ == '__main__':
    main()