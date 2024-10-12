import asyncio
import logging
import sqlite3
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

import nest_asyncio
nest_asyncio.apply()

# Логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),  # Запис в файл
        logging.StreamHandler()  # Вивід в консоль
    ]
)
logger = logging.getLogger(__name__)

# Токен бота та API ключ
TOKEN = '7682500744:AAFFw5lYbvaO9piwOTk_Ljc1ALNcnHnktA8'
NEWS_API_KEY = '92d5b5293bea437281d886c00ffbf842'

# Підключення до бази даних SQLite
def init_db():
    conn = sqlite3.connect('fact_check_bot.db')
    with conn:
        conn.execute(''' 
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                query TEXT,
                result TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute(''' 
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                email TEXT UNIQUE
            )
        ''')
    return conn

# Функція для старту
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # Перевірка, чи користувач зареєстрований
    conn = sqlite3.connect('fact_check_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:  # Якщо користувач не зареєстрований
        await update.message.reply_text(
            'Щоб продовжити, будь ласка, введіть ваш Telegram ID для реєстрації.'
        )
        # Надсилаємо ID користувача як окреме повідомлення
        await update.message.reply_text(f'Ваш Telegram ID: {user_id}')
        await update.message.reply_text('Натисніть на це посилання для реєстрації: [Реєстрація](http://127.0.0.1:5000/)')

        return

    # Якщо користувач зареєстрований, показуємо меню
    await show_main_menu(update)

# Функція для обробки Telegram ID
async def handle_telegram_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.message.text.strip()
    user_id = update.effective_user.id

    # Надсилаємо Telegram ID на сайт для реєстрації
    response = requests.post('http://127.0.0.1:5000/register', json={
        'telegram_id': telegram_id,
        'user_id': user_id
    })

    if response.status_code == 200:
        await update.message.reply_text('Ви успішно зареєстровані! Тепер ви можете користуватися ботом.')
        await show_main_menu(update)
    else:
        await update.message.reply_text('Помилка реєстрації. Будь ласка, спробуйте ще раз.')

# Показуємо основне меню
async def show_main_menu(update: Update) -> None:
    keyboard = [
        [InlineKeyboardButton("📰 Перевірити новини", callback_data='check_news')],
        [InlineKeyboardButton("📜 Історія перевірок", callback_data='history')],
        [InlineKeyboardButton("🔍 Перевірка фактів", callback_data='check_fact')],
        [InlineKeyboardButton("📢 Опитування", callback_data='poll')],
        [InlineKeyboardButton("ℹ️ Допомога", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        '👋 Привіт! Я бот для перевірки фактів. Виберіть дію:',
        reply_markup=reply_markup
    )

# Функція для запиту новин
async def fetch_news(user_message: str) -> str:
    api_url = f"https://newsapi.org/v2/everything?q={user_message}&apiKey={NEWS_API_KEY}"

    # Логування запиту
    logger.info(f"Відправляю запит до API: {api_url}")

    response = requests.get(api_url)

    # Логування відповіді
    if response.status_code == 200:
        data = response.json()
        logger.info(f"Отримано дані з API: {data}")  # Логування отриманих даних
        articles = data.get('articles', [])
        if articles:
            result_message = "📰 Ось останні новини:\n"
            for article in articles[:5]:  # Виводимо перші 5 статей
                title = article['title']
                url = article['url']
                result_message += f"🔗 {title}\n{url}\n\n"
            return result_message
        else:
            logger.warning("Не вдалося знайти новин за запитом.")
            return '❌ Не вдалося знайти новин за вашим запитом. Спробуйте ще раз.'
    else:
        logger.error(f"Помилка при зверненні до API: {response.status_code}, текст: {response.text}")
        return '⚠️ Помилка при зверненні до API. Спробуйте ще раз пізніше.'

# Функція для перевірки фактів
async def fetch_duckduckgo_answer(query: str) -> str:
    url = f"https://api.duckduckgo.com/?q={query}&format=json"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if "RelatedTopics" in data and data["RelatedTopics"]:
            answer = data["RelatedTopics"][0].get("Text", "❌ Не вдалося знайти відповідь.")
            return answer
        else:
            return "❌ Не вдалося знайти відповідь."
    else:
        return "⚠️ Помилка при зверненні до DuckDuckGo API."

async def check_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    await update.message.reply_text('🔍 Перевіряю інформацію...')

    duckduckgo_result = await fetch_duckduckgo_answer(user_message)
    await update.message.reply_text(duckduckgo_result)

    log_result(update.effective_user.id, user_message, duckduckgo_result)

# Обробка запитів
async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # Відповідь на запит

    if query.data == 'check_news':
        await query.message.reply_text('📩 Надішліть мені новину для перевірки.')
        return

    if query.data == 'history':
        await show_history(update, context)

    if query.data == 'check_fact':
        await query.message.reply_text('📩 Надішліть текст факту для перевірки.')
        return

    if query.data == 'poll':
        await create_poll(update, context)

    if query.data == 'help':
        await query.message.reply_text('🆘 Допомога: \n\n'
                                        '📰 Для перевірки новин натисніть кнопку "Перевірити новини" '
                                        'і надішліть текст новини.\n'
                                        '📜 Ви можете переглянути історію ваших запитів, натиснувши "Історія перевірок".\n'
                                        '🔍 Ви можете перевірити факти, натиснувши "Перевірка фактів".\n'
                                        '📢 Створити опитування, натиснувши "Опитування".\n'
                                        '💡 Я тут, щоб допомогти вам з перевіркою фактів!')

# Функція для створення опитування
async def create_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.message.reply_text("📊 Введіть питання для опитування:")

# Логування результатів у базу даних
def log_result(user_id, query, result):
    conn = sqlite3.connect('fact_check_bot.db')
    with conn:
        conn.execute('INSERT INTO checks (user_id, query, result) VALUES (?, ?, ?)', (user_id, query, result))

# Функція для перегляду історії запитів
async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = sqlite3.connect('fact_check_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT query, result FROM checks WHERE user_id = ?', (update.effective_user.id,))
    rows = cursor.fetchall()
    conn.close()

    if rows:
        history_message = "📜 Історія ваших перевірок:\n"
        for row in rows:
            history_message += f"🔍 Запит: {row[0]}\n✅ Результат: {row[1]}\n\n"
    else:
        history_message = "📜 У вас немає історії перевірок."

    await update.callback_query.message.reply_text(history_message)

# Основна функція запуску бота
async def main() -> None:
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_id))
    app.add_handler(CallbackQueryHandler(handle_query))

    await app.initialize()
    await app.run_polling()  # Використання run_polling()
    await app.idle()

# Ініціалізація бази даних
init_db()

# Запуск бота
if __name__ == '__main__':
    asyncio.run(main())
