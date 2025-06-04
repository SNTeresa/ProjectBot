import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    ConversationHandler,
    filters
)
import requests
import random
import wikipedia
import sqlite3

# Настройки
TOKEN = "7778655865:AAGz5DQnaJyrpFmtwMz01ehRkkTKiGsFmhw"
wikipedia.set_lang("ru")

def init_db():
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (chat_id int, reminder_text text, time int)''')
    conn.commit()
    conn.close()

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для ConversationHandler
TYPING_REMINDER = range(1)

# Клавиатура
main_keyboard = [['Напоминание', 'Конвертер валют'], ['Пароль', 'Википедия'], ['Помощь']]
reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)


# Команда /start
async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\nВыбери функцию:",
        reply_markup=reply_markup
    )


# Обработчик кнопок меню
async def button_handler(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    if text == 'Напоминание':
        await update.message.reply_text(
            "Чтобы установить напоминание, используй формат:\n\n"
            "`<текст> через <минуты>`\n\n"
            "Пример: \"Сделать дз через 30\"",
            parse_mode="Markdown"
        )
    elif text == 'Конвертер валют':
        await update.message.reply_text(
            "Для конвертации валют используй команду:\n\n"
            "`/convert <сумма> <валюта1> <валюта2>`\n\n"
            "Пример: `/convert 100 USD RUB`",
            parse_mode="Markdown"
        )
    elif text == 'Пароль':
        await update.message.reply_text(
            "Для генерации пароля используй команду:\n\n"
            "`/password <длина>`\n\n"
            "Пример: `/password 52`",
            parse_mode="Markdown"
        )
    elif text == 'Википедия':
        await update.message.reply_text(
            "Для поиска в вики используй команду:\n\n"
            "`/wiki <запрос>`\n\n"
            "Пример: `/wiki Python`",
            parse_mode="Markdown"
        )
    elif text == 'Помощь':
        await help_command(update, context)


# Функция помощи
async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
*Доступные команды:*

*/convert* [сумма] [валюта1] [валюта2]  
Конвертирует валюту. Пример:  
`/convert 100 USD RUB`

*/password* [длина]  
Сгенерирует пароль. Пример:  
`/password 12`

*/wiki* [запрос]  
Ищет в вики. Пример:  
`/wiki Python`

*Напоминание*  
Формат: "Текст через X", где X — минуты.  
Пример: `Сделать дз через 30`
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")


# Напоминания
async def reminder(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "Напиши, о чём напомнить и через сколько минут (например: 'Сделать уроки через 30').")
    return TYPING_REMINDER


async def set_reminder(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if "через" in text:
        task, _, time_str = text.partition("через")
        try:
            minutes = int(time_str.strip())
            context.job_queue.run_once(
                callback=send_reminder,
                when=minutes * 60,
                data=task.strip(),
                chat_id=update.message.chat_id
            )
            await update.message.reply_text(f"Ок, напомню: '{task.strip()}' через {minutes} минут.")
        except ValueError:
            await update.message.reply_text("Неверный формат времени. Попробуй ещё раз.")
    else:
        await update.message.reply_text("Используй формат: 'Текст через X' (X — минуты).")
    return ConversationHandler.END


async def send_reminder(context: CallbackContext) -> None:
    job = context.job
    await context.bot.send_message(job.chat_id, text=f"Напоминаю: {job.data}")


# Конвертер валют
def get_exchange_rate(base: str, target: str) -> float:
    url = f"https://api.exchangerate-api.com/v4/latest/{base}"
    response = requests.get(url)
    data = response.json()
    return data["rates"].get(target, 1.0)


async def currency_converter(update: Update, context: CallbackContext) -> None:
    try:
        amount = float(context.args[0])
        base_cur = context.args[1].upper()
        target_cur = context.args[2].upper()
        rate = get_exchange_rate(base_cur, target_cur)
        result = amount * rate
        await update.message.reply_text(f"{amount} {base_cur} = {result:.2f} {target_cur}")
    except (IndexError, ValueError):
        await update.message.reply_text("Используй: /convert 100 USD RUB")


# Генератор паролей
async def generate_password(update: Update, context: CallbackContext) -> None:
    length = 8 if not context.args else int(context.args[0])
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!@#$%^&*"
    password = "".join(random.sample(chars, length))
    await update.message.reply_text(f"Твой пароль: {password}")


# Поиск в Википедии
async def wiki_search(update: Update, context: CallbackContext) -> None:
    query = " ".join(context.args)
    try:
        summary = wikipedia.summary(query, sentences=2)
        await update.message.reply_text(summary)
    except wikipedia.exceptions.DisambiguationError as e:
        await update.message.reply_text("Уточни запрос. Возможные варианты: " + ", ".join(e.options[:5]))
    except wikipedia.exceptions.PageError:
        await update.message.reply_text("Ничего не найдено.")


def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()

    # ConversationHandler для напоминаний
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Напоминание$'), reminder)],
        states={
            TYPING_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_reminder)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )

    # Регистрация обработчиков
    handlers = [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("convert", currency_converter),
        CommandHandler("password", generate_password),
        CommandHandler("wiki", wiki_search),
        MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler),  # Обработчик кнопок
        conv_handler,
    ]

    for handler in handlers:
        application.add_handler(handler)

    application.run_polling()


if __name__ == '__main__':
    main()
