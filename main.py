import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from dotenv import load_dotenv

# Загрузка .env для локального запуска (на Render это не нужно, там переменные в настройках)
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# Отключаем лишний шум от http-библиотек
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
# Получаем токен
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Получаем ID админа (безопасное преобразование в число)
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
except (ValueError, TypeError):
    ADMIN_ID = None
    logger.warning("⚠️ ADMIN_ID не установлен! Уведомления приходить не будут.")

# Состояния разговора
SERVICE_CHOICE, PROJECT_DETAILS, BUDGET, TIMELINE, CONTACT, CONFIRMATION = range(6)


# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (Keep-Alive) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    """Простой обработчик, чтобы Render видел, что приложение живо"""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running OK")

def start_health_check_server():
    """Запуск веб-сервера в отдельном потоке"""
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"🌍 Fake Web Server запущен на порту {port}")
    server.serve_forever()


# --- ОСНОВНОЙ КЛАСС БОТА ---
class LandingBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("services", self.show_services))
        self.application.add_handler(CommandHandler("price", self.show_prices))
        self.application.add_handler(CommandHandler("contact", self.contact_admin))

        # Диалог заказа (исправленная логика входа)
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("order", self.start_order),
                # Ловим нажатие кнопки "order" как старт диалога
                CallbackQueryHandler(self.start_order_callback, pattern="^order$")
            ],
            states={
                SERVICE_CHOICE: [CallbackQueryHandler(self.choose_service)],
                PROJECT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_project_details)],
                BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_budget)],
                TIMELINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_timeline)],
                CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_contact)],
                CONFIRMATION: [
                    CallbackQueryHandler(self.confirm_order, pattern="^confirm_order$"),
                    CallbackQueryHandler(self.restart_order, pattern="^edit_order$")
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_order)]
        )
        self.application.add_handler(conv_handler)

        # Обработка остальных кнопок и текста
        self.application.add_handler(CallbackQueryHandler(self.button_click))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    # --- ЛОГИКА ---
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        text = f"👋 Привет, {user.first_name}!\nЯ помогу заказать сайт или бота."
        keyboard = [
            [InlineKeyboardButton("🚀 Оформить заказ", callback_data="order")],
            [InlineKeyboardButton("💼 Услуги", callback_data="services"), InlineKeyboardButton("💰 Цены", callback_data="price")],
            [InlineKeyboardButton("📞 Контакты", callback_data="contact")]
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("💡 Нажмите /order для заказа или /contact для связи.")

    async def show_services(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = "🛠 **Мои услуги:**\n1. Лендинги\n2. Telegram боты\n3. AI интеграции"
        keyboard = [[InlineKeyboardButton("🚀 Заказать", callback_data="order")]]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(keyboard))

    async def show_prices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = "💰 **Цены:**\nЛендинг: от 15к ₽\nБот: от 10к ₽"
        keyboard = [[InlineKeyboardButton("🚀 Заказать расчет", callback_data="order")]]
        await self._send_or_edit(update, text, InlineKeyboardMarkup(keyboard))

    async def contact_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = "📞 **Связь:** @ваш_юзернейм"
        await self._send_or_edit(update, text, None)

    # Вспомогательная функция для отправки или редактирования
    async def _send_or_edit(self, update, text, markup):
        if update.callback_query:
            await update.callback_query.answer()
            # Чтобы не было ошибки "Message is not modified", оборачиваем в try
            try:
                await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode='Markdown')
            except Exception:
                await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')

    # --- ДИАЛОГ ЗАКАЗА ---
    def _get_services_kb(self):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("Лендинг", callback_data="srv_landing"), InlineKeyboardButton("Бот", callback_data="srv_bot")],
            [InlineKeyboardButton("AI / Другое", callback_data="srv_other")]
        ])

    async def start_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🎯 Что будем разрабатывать?", reply_markup=self._get_services_kb())
        return SERVICE_CHOICE

    async def start_order_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🎯 Что будем разрабатывать?", reply_markup=self._get_services_kb())
        return SERVICE_CHOICE

    async def choose_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        srv_map = {"srv_landing": "Лендинг", "srv_bot": "Бот", "srv_other": "Другое"}
        service = srv_map.get(query.data, "Неизвестно")
        context.user_data['service'] = service
        await query.edit_message_text(f"✅ Выбрано: **{service}**.\n\n📝 Опишите кратко суть задачи:")
        return PROJECT_DETAILS

    async def get_project_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['details'] = update.message.text
        await update.message.reply_text("💰 Укажите примерный бюджет:")
        return BUDGET

    async def get_budget(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['budget'] = update.message.text
        await update.message.reply_text("⏱ Желаемые сроки?")
        return TIMELINE

    async def get_timeline(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['timeline'] = update.message.text
        await update.message.reply_text("📞 Оставьте контакт (Telegram или телефон):")
        return CONTACT

    async def get_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['contact'] = update.message.text
        data = context.user_data
        summary = (
            f"📋 **Подтверждение заказа:**\n\n"
            f"🛠 Услуга: {data['service']}\n"
            f"📝 Задача: {data['details']}\n"
            f"💰 Бюджет: {data['budget']}\n"
            f"⏱ Сроки: {data['timeline']}\n"
            f"📞 Контакт: {data['contact']}"
        )
        context.user_data['summary'] = summary
        kb = [[InlineKeyboardButton("✅ Отправить", callback_data="confirm_order"), InlineKeyboardButton("✏️ Исправить", callback_data="edit_order")]]
        await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return CONFIRMATION

    async def confirm_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        # Отправка админу
        if ADMIN_ID:
            try:
                user = update.effective_user
                admin_text = f"🚨 **НОВЫЙ ЗАКАЗ!**\nОт: {user.mention_markdown()}\n{context.user_data['summary']}"
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Ошибка отправки админу: {e}")

        await query.edit_message_text("🎉 Заявка принята! Я свяжусь с вами в ближайшее время.")
        context.user_data.clear()
        return ConversationHandler.END

    async def restart_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("🔄 Давайте заполним заново. Выберите услугу:", reply_markup=self._get_services_kb())
        return SERVICE_CHOICE

    async def cancel_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("❌ Заказ отменен.")
        return ConversationHandler.END

    async def button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "services": await self.show_services(update, context)
        elif query.data == "price": await self.show_prices(update, context)
        elif query.data == "contact": await self.contact_admin(update, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if "привет" in update.message.text.lower():
            await update.message.reply_text("Привет!")
        else:
            await update.message.reply_text("Используйте меню (/start).")

    def run(self):
        logger.info("🤖 Запуск бота...")
        self.application.run_polling()

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ ОШИБКА: Не задан BOT_TOKEN")
    else:
        # 1. Запускаем веб-сервер в фоне (чтобы Render не убил нас)
        threading.Thread(target=start_health_check_server, daemon=True).start()
        
        # 2. Запускаем бота
        bot = LandingBot(BOT_TOKEN)
        bot.run()
