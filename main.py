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
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
except (ValueError, TypeError):
    ADMIN_ID = None

# Состояния
SERVICE_CHOICE, PROJECT_DETAILS, TIMELINE, CONTACT, CONFIRMATION = range(5)

# Ссылка на заставку
START_IMAGE_URL = "https://belayarod.ru/leto/imagebot.png"

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER/HEROKU ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running OK")

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- БОТ ---
class LandingBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("order", self.start_order),
                CallbackQueryHandler(self.start_order_callback, pattern="^order$")
            ],
            states={
                SERVICE_CHOICE: [CallbackQueryHandler(self.choose_service)],
                PROJECT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_project_details)],
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
        self.application.add_handler(CallbackQueryHandler(self.button_click))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        # Обновленный универсальный текст
        text = (
            f"<b>Приветствуем, {user.first_name}!</b>\n\n"
            "Мы создаем цифровую упаковку для ваших проектов и практик под ключ.\n\n"
            "Для проводников, менторов, психологов и организаторов ретритов. "
            "Наша задача — создать эстетичное и функциональное пространство, которое созвучно вашим ценностям."
        )
        keyboard = [
            [InlineKeyboardButton("💎 Начать знакомство", callback_data="order")],
            [InlineKeyboardButton("💼 Услуги", callback_data="services"), InlineKeyboardButton("📞 Контакты", callback_data="contact")]
        ]
        
        try:
            await update.message.reply_photo(
                photo=START_IMAGE_URL,
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def start_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("<b>🌿 С чего мы начнем?</b>\nВыберите интересующее направление:", 
                                       reply_markup=self._get_services_kb(), parse_mode='HTML')
        return SERVICE_CHOICE

    async def start_order_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("<b>🌿 С чего мы начнем?</b>\nВыберите интересующее направление:", 
                                     reply_markup=self._get_services_kb(), parse_mode='HTML')
        return SERVICE_CHOICE

    def _get_services_kb(self):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 Чат-бот", callback_data="srv_bot"), InlineKeyboardButton("💻 Лендинг", callback_data="srv_landing")],
            [InlineKeyboardButton("✨ Другое / Комплекс", callback_data="srv_other")]
        ])

    async def choose_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        srv_map = {"srv_landing": "Лендинг", "srv_bot": "Бот", "srv_other": "Комплекс"}
        service = srv_map.get(query.data, "Неизвестно")
        context.user_data['service'] = service
        await query.edit_message_text(f"✅ Выбрано: <b>{service}</b>.\n\n📝 Опишите кратко суть задачи (ваши пожелания):", parse_mode='HTML')
        return PROJECT_DETAILS

    async def get_project_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if len(update.message.text) < 10:
            await update.message.reply_text("🌸 Пожалуйста, опишите задачу чуть подробнее, чтобы мы могли лучше вас понять.")
            return PROJECT_DETAILS
            
        context.user_data['details'] = update.message.text
        await update.message.reply_text("<b>⏱ Желаемые сроки реализации?</b>", parse_mode='HTML')
        return TIMELINE

    async def get_timeline(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['timeline'] = update.message.text
        await update.message.reply_text("<b>📱 Как мастер может с вами связаться?</b>\nОставьте ваш @username или номер телефона:", parse_mode='HTML')
        return CONTACT

    async def get_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        contact = update.message.text
        if len(contact) < 5:
            await update.message.reply_text("⚠️ Пожалуйста, укажите корректные данные для связи.")
            return CONTACT

        context.user_data['contact'] = contact
        data = context.user_data
        summary = (
            f"<b>📋 Ваша заявка сформирована:</b>\n\n"
            f"💠 <b>Услуга:</b> {data['service']}\n"
            f"📝 <b>Задача:</b> {data['details']}\n"
            f"⏱ <b>Сроки:</b> {data['timeline']}\n"
            f"📞 <b>Контакт:</b> {data['contact']}\n\n"
            "<i>Отправить данные нашему специалисту?</i>"
        )
        context.user_data['summary'] = summary
        kb = [[InlineKeyboardButton("✅ Отправить", callback_data="confirm_order"), InlineKeyboardButton("✏️ Исправить", callback_data="edit_order")]]
        await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        return CONFIRMATION

    async def confirm_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if ADMIN_ID:
            try:
                user = update.effective_user
                # В админ-панель шлем тоже HTML
                admin_text = f"🚨 <b>НОВЫЙ ЗАКАЗ!</b>\nОт: {user.mention_html()}\n\n{context.user_data['summary']}"
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Ошибка отправки админу: {e}")

        await query.edit_message_text("🌸 <b>Благодарим за доверие!</b>\nЗаявка принята. Мастер свяжется с вами в ближайшее время.")
        context.user_data.clear()
        return ConversationHandler.END

    async def restart_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("🔄 Давайте уточним данные. Выберите услугу:", reply_markup=self._get_services_kb())
        return SERVICE_CHOICE

    async def cancel_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("🕊 Мы будем рады помочь вам в любое другое время. Всего доброго!")
        return ConversationHandler.END

    async def button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "services":
            text = (
                "<b>🛠 Наши возможности:</b>\n\n"
                "• Индивидуальные Telegram-боты\n"
                "• Эстетичные лендинги и сайты\n"
                "• Системы автоматизации и записи"
            )
            await self._send_or_edit(update, text, InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]]))
        
        elif query.data == "contact":
            # ТЕПЕРЬ НЕ БУДЕТ ОШИБКИ ИЗ-ЗА НИЖНЕГО ПОДЧЕРКИВАНИЯ
            text = "📞 Для прямой связи с мастером: @ваш_юзернейм"
            await self._send_or_edit(update, text, InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]]))
            
        elif query.data == "back":
            text = "✨ Пожалуйста, выберите нужный раздел меню:"
            kb = [
                [InlineKeyboardButton("💎 Начать знакомство", callback_data="order")],
                [InlineKeyboardButton("💼 Услуги", callback_data="services"), InlineKeyboardButton("📞 Контакты", callback_data="contact")]
            ]
            await self._send_or_edit(update, text, InlineKeyboardMarkup(kb))

    async def _send_or_edit(self, update, text, markup):
        """Вспомогательный метод для обновления сообщений с HTML"""
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode='HTML')
            except Exception:
                # Если сообщение нельзя редактировать (например, оно старое или с фото)
                await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=markup, parse_mode='HTML')

    def run(self):
        logger.info("🤖 Бот запущен...")
        self.application.run_polling()

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ ОШИБКА: Не задан BOT_TOKEN")
    else:
        # Запуск веб-сервера в отдельном потоке (нужно для Render)
        threading.Thread(target=start_health_check_server, daemon=True).start()
        bot = LandingBot(BOT_TOKEN)
        bot.run()
