import logging
import asyncio
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

# Токен и вики
TOKEN = "7778655865:AAGz5DQnaJyrpFmtwMz01ehRkkTKiGsFmhw"
wikipedia.set_lang("ru")

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния
SETTING_REMINDER = 1

# Менюшка в боте
main_keyboard = [['Напоминание', 'Конвертер валют'], ['Пароль', 'Википедия'], ['Помощь']]
reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Привет! Выбери функцию:",
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: CallbackContext):
    help_text = """
📌 Доступные команды:

/start - Запустить бота
/help - Помощь по командам

🔔 Напоминания:
Нажми кнопку "Напоминание" или напиши:
"<текст> через <минуты>"
Пример: "Сделать презентацию через 30"

💱 /convert <сумма> <валюта1> <валюта2>
Конвертирует валюты
Пример: /convert 100 USD RUB

🔑 /password <длина>
Генерирует пароль
Пример: /password 12

🔍 /wiki <запрос>
Ищет в Википедии
Пример: /wiki Python
"""
    await update.message.reply_text(help_text)


async def reminder(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "📝 Введи напоминание в формате:\n"
        "<текст> через <минуты>\n\n"
        "Пример: Сделать презентацию через 30"
    )
    return SETTING_REMINDER


async def set_reminder(update: Update, context: CallbackContext) -> int:
    try:
        text = update.message.text
        if "через" not in text:
            raise ValueError

        task, _, minutes_str = text.partition("через")
        task = task.strip()
        minutes = int(minutes_str.strip())

        if minutes <= 0:
            await update.message.reply_text("Время должно быть больше 0 минут!")
            return SETTING_REMINDER

        # Сохранение данных о напоминаниях
        context.user_data['reminder'] = {
            'text': task,
            'minutes': minutes,
            'chat_id': update.message.chat_id
        }

        # Запуска напоминания
        asyncio.create_task(
            send_reminder_after_delay(
                minutes * 60,
                update.message.chat_id,
                task,
                context
            )
        )

        await update.message.reply_text(
            f"⏰ Напоминание установлено!\n"
            f"Я напомню: '{task}'\n"
            f"Через {minutes} минут"
        )

    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат! Используй:\n"
            "<текст> через <минуты>\n\n"
            "Пример: Сделать презентацию через 30"
        )
        return SETTING_REMINDER

    return ConversationHandler.END


async def send_reminder_after_delay(delay: int, chat_id: int, text: str, context: CallbackContext):
    try:
        await asyncio.sleep(delay)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🔔 Напоминаю: {text}"
        )
        logger.info(f"Напоминание отправлено: {text}")
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания: {e}")


async def currency_converter(update: Update, context: CallbackContext):
    try:
        if len(context.args) != 3:
            raise ValueError

        amount = float(context.args[0])
        base_cur = context.args[1].upper()
        target_cur = context.args[2].upper()

        rate = get_exchange_rate(base_cur, target_cur)
        if rate is None:
            await update.message.reply_text("⚠️ Ошибка получения курса. Попробуйте позже.")
            return

        result = amount * rate
        await update.message.reply_text(
            f"💱 Конвертация:\n"
            f"{amount:.2f} {base_cur} = {result:.2f} {target_cur}\n"
            f"Курс: 1 {base_cur} = {rate:.4f} {target_cur}"
        )
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Неверный формат. Используй:\n"
            "/convert <сумма> <валюта1> <валюта2>\n\n"
            "Пример: /convert 100 USD RUB"
        )


def get_exchange_rate(base: str, target: str) -> float:
    url = f"https://api.exchangerate-api.com/v4/latest/{base}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data["rates"].get(target, 1.0)
    except Exception as e:
        logger.error(f"Ошибка API валют: {e}")
        return None


async def generate_password(update: Update, context: CallbackContext):
    try:
        length = int(context.args[0]) if context.args else 12
        length = max(4, min(length, 32))  # Ограничение

        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!@#$%^&*"
        password = "".join(random.choice(chars) for _ in range(length))

        await update.message.reply_text(
            f"🔐 Сгенерирован пароль:\n\n"
            f"<code>{password}</code>\n\n"
            f"Длина: {length} символов",
            parse_mode="HTML"
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Укажите длину пароля числом\n"
            "Пример: /password 12"
        )


async def wiki_search(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("❌ Укажите поисковый запрос")
        return

    query = " ".join(context.args)
    try:
        summary = wikipedia.summary(query, sentences=3)
        await update.message.reply_text(
            f"🔍 Результат по запросу '{query}':\n\n"
            f"{summary}"
        )
    except wikipedia.exceptions.DisambiguationError as e:
        await update.message.reply_text(
            f"❓ Запрос плохо понят. Уточните:\n\n"
            f"{', '.join(e.options[:5])}"
        )
    except wikipedia.exceptions.PageError:
        await update.message.reply_text("❌ Ничего не найдено")
    except Exception as e:
        logger.error(f"Ошибка Wikipedia: {e}")
        await update.message.reply_text("⚠️ Ошибка поиска. Попробуйте другой запрос.")


async def button_handler(update: Update, context: CallbackContext):
    text = update.message.text
    if text == 'Напоминание':
        await reminder(update, context)
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
            "Пример: `/password 12`",
            parse_mode="Markdown"
        )
    elif text == 'Википедия':
        await update.message.reply_text(
            "Для поиска в Википедии используй команду:\n\n"
            "`/wiki <запрос>`\n\n"
            "Пример: `/wiki Python`",
            parse_mode="Markdown"
        )
    elif text == 'Помощь':
        await help_command(update, context)


def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Настройка обработчиков
    reminder_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Напоминание$'), reminder)],
        states={
            SETTING_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_reminder)]
        },
        fallbacks=[]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("convert", currency_converter))
    application.add_handler(CommandHandler("password", generate_password))
    application.add_handler(CommandHandler("wiki", wiki_search))
    application.add_handler(reminder_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

    application.run_polling()


if __name__ == '__main__':
    print("Бот запущен и готов к работе!")
    main()
