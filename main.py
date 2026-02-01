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

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
except (ValueError, TypeError):
    ADMIN_ID = None

# Состояния (убрали детали и сроки для скорости)
SERVICE_CHOICE, CONTACT, CONFIRMATION = range(3)

START_IMAGE_URL = "https://belayarod.ru/leto/imagebot.png"

# --- ВЕБ-СЕРВЕР ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever()

# --- БОТ ---
class LandingBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                CallbackQueryHandler(self.start_order_callback, pattern="^order$")
            ],
            states={
                SERVICE_CHOICE: [CallbackQueryHandler(self.choose_service)],
                CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_contact)],
                CONFIRMATION: [
                    CallbackQueryHandler(self.confirm_order, pattern="^confirm_order$"),
                    CallbackQueryHandler(self.start_order_callback, pattern="^edit_order$")
                ]
            },
            fallbacks=[CommandHandler("start", self.start)]
        )
        self.application.add_handler(conv_handler)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        text = (
            f"<b>Приветствуем, {user.first_name}!</b>\n\n"
            "Мы создаем цифровую упаковку для ваших проектов под ключ.\n"
            "Эстетичные лендинги и умные чат-боты."
        )
        keyboard = [[InlineKeyboardButton("💎 Оставить заявку", callback_data="order")]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_photo(photo=START_IMAGE_URL, caption=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.callback_query.edit_message_caption(caption=text, reply_markup=reply_markup, parse_mode='HTML')
        return ConversationHandler.END # Выходим, чтобы ждать нажатия кнопки

    async def start_order_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        kb = [
            [InlineKeyboardButton("🤖 Чат-бот", callback_data="srv_bot"), 
             InlineKeyboardButton("💻 Лендинг", callback_data="srv_landing")],
            [InlineKeyboardButton("✨ Комплекс", callback_data="srv_other")]
        ]
        text = "<b>🌿 Что вас интересует?</b>\nВыберите направление:"
        await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        return SERVICE_CHOICE

    async def choose_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        srv_map = {"srv_landing": "Лендинг", "srv_bot": "Бот", "srv_other": "Комплекс"}
        context.user_data['service'] = srv_map.get(query.data, "Неизвестно")
        
        await query.edit_message_caption(
            caption=f"✅ Выбрано: <b>{context.user_data['service']}</b>\n\n"
                    "📱 <b>Введите ваш номер телефона</b> или @username для связи:",
            parse_mode='HTML'
        )
        return CONTACT

    async def get_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['contact'] = update.message.text
        user = update.effective_user
        
        summary = (
            f"<b>📋 Ваша заявка:</b>\n"
            f"💠 Услуга: {context.user_data['service']}\n"
            f"📞 Контакт: {context.user_data['contact']}\n\n"
            f"<i>Отправить данные мастеру?</i>"
        )
        
        kb = [[
            InlineKeyboardButton("✅ Да", callback_data="confirm_order"),
            InlineKeyboardButton("✏️ Изменить", callback_data="edit_order")
        ]]
        await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        return CONFIRMATION

    async def confirm_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user = update.effective_user
        await query.answer()

        if ADMIN_ID:
            admin_text = (
                f"🚨 <b>НОВЫЙ ЗАКАЗ!</b>\n"
                f"👤 Клиент: {user.mention_html()}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"💠 Услуга: {context.user_data['service']}\n"
                f"📞 Контакт: {context.user_data['contact']}"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='HTML')

        await query.edit_message_text("🌸 <b>Спасибо!</b> Мастер свяжется с вами в ближайшее время.")
        context.user_data.clear()
        return ConversationHandler.END

    def run(self):
        self.application.run_polling()

if __name__ == "__main__":
    if BOT_TOKEN:
        threading.Thread(target=start_health_check_server, daemon=True).start()
        LandingBot(BOT_TOKEN).run()
    else:
        print("Ошибка: Токен не найден.")
