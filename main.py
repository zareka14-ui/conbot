import os
import logging
import threading
import re
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

# Состояния (убран BUDGET)
SERVICE_CHOICE, PROJECT_DETAILS, TIMELINE, CONTACT, CONFIRMATION = range(5)

# Ссылка на вашу заставку (логотип, который мы делали ранее или любое фото)
START_IMAGE_URL = "https://belayarod.ru/leto/imagebot.png" # Замените на реальную ссылку

# --- ВЕБ-СЕРВЕР ---
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
        text = (
            f"✨ **Добрый день, {user.first_name}!**\n\n"
            "Мы рады приветствовать вас. Наша миссия — помочь в автоматизации вашего пространства, "
            "сделать его удобным, технологичным и эстетичным.\n\n"
            "Для предоставления услуг нам необходимо познакомиться и узнать ваше техническое задание. "
            "Это поможет нам предложить решение, идеально подходящее именно вам."
        )
        keyboard = [
            [InlineKeyboardButton("💎 Начать знакомство", callback_data="order")],
            [InlineKeyboardButton("💼 Услуги", callback_data="services"), InlineKeyboardButton("📞 Контакты", callback_data="contact")]
        ]
        
        # Пытаемся отправить фото с подписью, если ссылка валидна
        try:
            await update.message.reply_photo(
                photo=START_IMAGE_URL,
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def start_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🌿 **С чего мы начнем?**\nВыберите интересующее направление:", 
                                       reply_markup=self._get_services_kb())
        return SERVICE_CHOICE

    async def start_order_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🌿 **С чего мы начнем?**\nВыберите интересующее направление:", 
                                     reply_markup=self._get_services_kb())
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
        await query.edit_message_text(f"✅ Выбрано: **{service}**.\n\n📝 Опишите кратко суть задачи (ваши пожелания):")
        return PROJECT_DETAILS

    async def get_project_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Защита: слишком короткое описание
        if len(update.message.text) < 10:
            await update.message.reply_text("🌸 Пожалуйста, опишите задачу чуть подробнее (хотя бы пару предложений), чтобы мы могли вас понять.")
            return PROJECT_DETAILS
            
        context.user_data['details'] = update.message.text
        await update.message.reply_text("⏱ **Желаемые сроки реализации?**")
        return TIMELINE

    async def get_timeline(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['timeline'] = update.message.text
        await update.message.reply_text("📱 **Как мастер может с вами связаться?**\nОставьте ваш @username или номер телефона:")
        return CONTACT

    async def get_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Защита: проверка на пустоту или слишком короткий ввод
        contact = update.message.text
        if len(contact) < 5:
            await update.message.reply_text("⚠️ Пожалуйста, укажите корректные данные (например, @username или номер), чтобы мы не потеряли связь.")
            return CONTACT

        context.user_data['contact'] = contact
        data = context.user_data
        summary = (
            f"📋 **Ваша заявка сформирована:**\n\n"
            f"💠 **Услуга:** {data['service']}\n"
            f"📝 **Задача:** {data['details']}\n"
            f"⏱ **Сроки:** {data['timeline']}\n"
            f"📞 **Контакт:** {data['contact']}\n\n"
            "✨ *Отправить данные нашему специалисту?*"
        )
        context.user_data['summary'] = summary
        kb = [[InlineKeyboardButton("✅ Отправить", callback_data="confirm_order"), InlineKeyboardButton("✏️ Исправить", callback_data="edit_order")]]
        await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return CONFIRMATION

    async def confirm_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if ADMIN_ID:
            try:
                user = update.effective_user
                admin_text = f"🚨 **НОВЫЙ ЗАКАЗ!**\nОт: {user.mention_markdown()}\n\n{context.user_data['summary']}"
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Ошибка отправки админу: {e}")

        await query.edit_message_text("🌸 **Благодарим за доверие!**\nЗаявка принята. Мастер свяжется с вами для обсуждения деталей в ближайшее время.")
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
            text = "🛠 **Наши возможности:**\n\n• Индивидуальные Telegram-боты\n• Эстетичные лендинги\n• Системы записи и автоматизации"
            await self._send_or_edit(update, text, InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]]))
        elif query.data == "contact":
            await self._send_or_edit(update, "📞 Для прямой связи с мастером: @ваш_юзернейм", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]]))
        elif query.data == "back":
            # Возврат к стартовому меню (без повторной отправки фото, если это был колбэк)
            text = "✨ Пожалуйста, выберите нужный раздел меню:"
            kb = [
                [InlineKeyboardButton("💎 Начать знакомство", callback_data="order")],
                [InlineKeyboardButton("💼 Услуги", callback_data="services"), InlineKeyboardButton("📞 Контакты", callback_data="contact")]
            ]
            await self._send_or_edit(update, text, InlineKeyboardMarkup(kb))

    async def _send_or_edit(self, update, text, markup):
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode='Markdown')
            except:
                await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')

    def run(self):
        logger.info("🤖 Бот запущен...")
        self.application.run_polling()

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ ОШИБКА: Не задан BOT_TOKEN")
    else:
        threading.Thread(target=start_health_check_server, daemon=True).start()
        bot = LandingBot(BOT_TOKEN)
        bot.run()
