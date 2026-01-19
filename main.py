"""
Telegram бот для контакта с клиентами
Бизнес: разработка лендингов, телеграм ботов, AI-контент
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    WebAppInfo
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

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для состояний разговора
SERVICE_CHOICE, PROJECT_DETAILS, BUDGET, TIMELINE, CONTACT, CONFIRMATION = range(6)

# ID вашего телеграм аккаунта (замените на свой)
ADMIN_ID = os.getenv("ADMIN_ID", "ваш_telegram_id")

class LandingBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        
        # Регистрируем обработчики
        self._setup_handlers()
        
        # Хранилище данных пользователей (в реальном проекте лучше использовать БД)
        self.user_data_store = {}
    
    def _setup_handlers(self):
        """Настройка всех обработчиков команд"""
        
        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("services", self.show_services))
        self.application.add_handler(CommandHandler("portfolio", self.show_portfolio))
        self.application.add_handler(CommandHandler("contact", self.contact_admin))
        self.application.add_handler(CommandHandler("price", self.show_prices))
        
        # Обработчик разговора для заказа
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("order", self.start_order)],
            states={
                SERVICE_CHOICE: [CallbackQueryHandler(self.choose_service)],
                PROJECT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_project_details)],
                BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_budget)],
                TIMELINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_timeline)],
                CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_contact)],
                CONFIRMATION: [CallbackQueryHandler(self.confirm_order)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_order)]
        )
        
        self.application.add_handler(conv_handler)
        
        # Обработчик текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработчик обратных вызовов (кнопок)
        self.application.add_handler(CallbackQueryHandler(self.button_click))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        welcome_text = f"""
👋 Привет, {user.first_name}!

Я — помощник в разработке цифровых решений:

🎯 **Что я делаю:**
• Создаю продающие лендинги
• Разрабатываю Telegram-боты
• Помогаю с AI-генерацией контента


💡 **Как я могу вам помочь:**
/order - Оформить заказ
/services - Посмотреть услуги
/price - Стоимость услуг
/contact - Связаться со мной
/help - Помощь по боту

📞 Пишите, если есть вопросы! Отвечаю быстро.
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🚀 Оформить заказ", callback_data="order"),
                InlineKeyboardButton("💼 Услуги", callback_data="services")
            ],
            [
                InlineKeyboardButton("💰 Стоимость", callback_data="price"),
                InlineKeyboardButton("📞 Контакты", callback_data="contact")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🤖 **Доступные команды:**

/start - Главное меню
/order - Оформить заказ на разработку
/services - Посмотреть все услуги
/price - Узнать стоимость услуг
/contact - Связаться напрямую
/help - Эта справка

💡 **Как работать с ботом:**
1. Нажмите /order для оформления заказа
2. Выберите нужную услугу
3. Заполните информацию о проекте
4. Получите расчет стоимости и сроков

📞 **Связь:**
• Отвечаю в течение 15 минут
• Консультирую бесплатно
• Предоставляю ТЗ шаблон
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def show_services(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все услуги"""
        services_text = """
🎯 **Мои услуги:**

🏗️ **1. Лендинги (Landing Page)**
• Адаптивный дизайн
• Интеграция с CRM/Telegram
• SEO-оптимизация
• Скорость загрузки 90+ баллов
• Конверсия от 3%

🤖 **2. Telegram-боты**
• Боты для бизнеса
• Автоматизация продаж
• Интеграция с базами данных
• Парсинг данных
• Рассылки и уведомления

🤖 **3. AI-контент и автоматизация**
• Настройка ChatGPT/нейросетей
• Генерация текстов/изображений
• Автоматизация контент-планов
• AI-ассистенты для бизнеса
• Обучение работе с AI

⚡ **4. Дополнительно**
• Доработка существующих сайтов
• Техническая поддержка
• Консультации по digital
• Создание презентаций
        """
        
        keyboard = [
            [InlineKeyboardButton("🚀 Заказать лендинг", callback_data="service_landing")],
            [InlineKeyboardButton("🤖 Заказать Telegram бота", callback_data="service_bot")],
            [InlineKeyboardButton("🎨 Заказать AI-решение", callback_data="service_ai")],
            [InlineKeyboardButton("💬 Консультация", callback_data="service_consult")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            services_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать портфолио"""
        portfolio_text = """
📁 **Примеры работ:**

🏪 **Лендинг для Мистерии**
• Конверсия: 4.2%
• Срок: 5 дней
• Стек: HTML/CSS/JS + Telegram бот
• [Посмотреть](https://belayarod.ru/mist.html)

🤖 **Telegram-бот длятрансформационной игры**
• Запись клиентов
• Уведомления
• База клиентов
• Отчетность
• [Посмотреть бота](https://t.me/@Rgamepay_bot)
📈 **Результаты:**
• 50+ успешных проектов
• Средняя конверсия: 3.8%
• Срок разработки: 3-14 дней
• Поддержка 24/7
        """
        
        keyboard = [
            [InlineKeyboardButton("📱 Пример лендинга", web_app=WebAppInfo(url="https://example-landing.com"))],
            [InlineKeyboardButton("🤖 Тестовый бот", url="https://t.me/test_demo_bot")],
            [InlineKeyboardButton("📊 Полное портфолио", callback_data="full_portfolio")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            portfolio_text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
    
    async def show_prices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать цены"""
        prices_text = """
💰 **Стоимость услуг:**

🏗️ **Лендинг (Landing Page)**
• Базовый: 15 000 - 25 000 ₽ (3-7 дней)
• Профессиональный: 25 000 - 40 000 ₽ (7-14 дней)
• Премиум: от 40 000 ₽ (14+ дней)

🤖 **Telegram-бот**
• Простой: 10 000 - 20 000 ₽ (3-5 дней)
• Средний: 20 000 - 35 000 ₽ (5-10 дней)
• Сложный: от 35 000 ₽ (10+ дней)

💎 **Что входит:**
• Бесплатная консультация
• ТЗ и прототип
• Разработка и тестирование
• Обучение использованию
• Техподдержка 1 месяц

🎁 **Акции:**
• При заказе 2х услуг - скидка 15%
• Реферальная программа
• Рассрочка платежа
        """
        
        keyboard = [
            [InlineKeyboardButton("💎 Рассчитать точную стоимость", callback_data="calculate_price")],
            [InlineKeyboardButton("💬 Получить консультацию", callback_data="get_consultation")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            prices_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def contact_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Связаться с администратором"""
        contact_text = """
📞 **Мои контакты:**

👨‍💻 **Телеграм:** @ваш_username
📧 **Email:** ваш@email.com
🌐 **Сайт:** ваш-сайт.ru
⏰ **Время работы:** 10:00 - 20:00 (МСК)

💡 **Как связаться:**
1. Напишите мне в Telegram
2. Отправьте заявку через /order
3. Закажите бесплатную консультацию

🚀 **Гарантии:**
• Ответ в течение 15 минут
• Бесплатная консультация
• Договор и ТЗ
• Поэтапная оплата
        """
        
        keyboard = [
            [InlineKeyboardButton("💬 Написать в Telegram", url="https://t.me/ваш_username")],
            [InlineKeyboardButton("📧 Отправить Email", callback_data="send_email")],
            [InlineKeyboardButton("📝 Оставить заявку", callback_data="order")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            contact_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    # Разговор для оформления заказа
    async def start_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало оформления заказа"""
        await update.message.reply_text(
            "🎯 Отлично! Давайте оформим заказ.\n\n"
            "Выберите услугу:",
            reply_markup=self._get_services_keyboard()
        )
        return SERVICE_CHOICE
    
    def _get_services_keyboard(self):
        """Клавиатура выбора услуги"""
        keyboard = [
            [
                InlineKeyboardButton("🏗️ Лендинг", callback_data="service_landing"),
                InlineKeyboardButton("🤖 Telegram бот", callback_data="service_bot")
            ],
            [
                InlineKeyboardButton("🎨 AI-решение", callback_data="service_ai"),
                InlineKeyboardButton("⚡ Другое", callback_data="service_other")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def choose_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора услуги"""
        query = update.callback_query
        await query.answer()
        
        service_map = {
            "service_landing": "Лендинг (Landing Page)",
            "service_bot": "Telegram бот",
            "service_other": "Другая услуга"
        }
        
        service = service_map.get(query.data, "Неизвестная услуга")
        context.user_data['service'] = service
        
        await query.edit_message_text(
            f"✅ Выбрана услуга: *{service}*\n\n"
            "📝 Теперь опишите ваш проект:\n"
            "• Цели проекта\n"
            "• Ключевые функции\n"
            "• Референсы (если есть)\n"
            "• Особые пожелания\n\n"
            "Чем подробнее опишете — точнее оценю!",
            parse_mode='Markdown'
        )
        
        return PROJECT_DETAILS
    
    async def get_project_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение описания проекта"""
        context.user_data['project_details'] = update.message.text
        
        await update.message.reply_text(
            "💼 Отлично! Теперь укажите примерный бюджет:\n\n"
            "• До 15 000 ₽\n"
            "• 15 000 - 30 000 ₽\n"
            "• 30 000 - 50 000 ₽\n"
            "• 50 000+ ₽\n"
            "• Пока не знаю, нужна консультация\n\n"
            "Напишите сумму или выберите из вариантов выше.",
            parse_mode='Markdown'
        )
        
        return BUDGET
    
    async def get_budget(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение бюджета"""
        context.user_data['budget'] = update.message.text
        
        await update.message.reply_text(
            "⏱️ Теперь укажите желаемые сроки:\n\n"
            "• Срочно (до 3 дней)\n"
            "• Быстро (3-7 дней)\n"
            "• Стандарт (7-14 дней)\n"
            "• Не срочно (14+ дней)\n"
            "• Нужна консультация\n\n"
            "Напишите сроки или выберите вариант.",
            parse_mode='Markdown'
        )
        
        return TIMELINE
    
    async def get_timeline(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение сроков"""
        context.user_data['timeline'] = update.message.text
        
        await update.message.reply_text(
            "📞 Остался последний шаг!\n\n"
            "Как с вами связаться?\n"
            "• Укажите ваш Telegram username (например, @username)\n"
            "• Или номер телефона\n"
            "• Или email\n\n"
            "Я свяжусь с вами в течение 15 минут!",
            parse_mode='Markdown'
        )
        
        return CONTACT
    
    async def get_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение контактов"""
        context.user_data['contact'] = update.message.text
        user = update.effective_user
        
        # Формируем сводку заказа
        order_summary = f"""
📋 *Сводка заказа*

👤 *Клиент:* {user.first_name} {user.last_name or ''} (@{user.username or 'нет'})
🎯 *Услуга:* {context.user_data.get('service', 'Не указано')}
📝 *Описание проекта:*
{context.user_data.get('project_details', 'Не указано')}

💰 *Бюджет:* {context.user_data.get('budget', 'Не указано')}
⏱️ *Сроки:* {context.user_data.get('timeline', 'Не указано')}
📞 *Контакты:* {context.user_data.get('contact', 'Не указано')}

🆔 *User ID:* {user.id}
        """
        
        context.user_data['order_summary'] = order_summary
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Отправить заявку", callback_data="confirm_order"),
                InlineKeyboardButton("✏️ Изменить данные", callback_data="edit_order")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            order_summary + "\n\n✅ Все верно? Отправляю заявку!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return CONFIRMATION
    
    async def confirm_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение и отправка заказа"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "confirm_order":
            # Отправляем заказ администратору
            order_summary = context.user_data.get('order_summary', '')
            user = update.effective_user
            
            admin_message = f"""
🚀 *НОВАЯ ЗАЯВКА!*

{order_summary}

🕒 *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M')}
            """
            
            try:
                # Отправляем администратору
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                )
                
                # Отправляем клиенту подтверждение
                await query.edit_message_text(
                    "🎉 *Заявка отправлена!*\n\n"
                    "Спасибо за заказ! Я уже получил вашу заявку.\n\n"
                    "📞 *Что дальше:*\n"
                    "1. Я свяжусь с вами в течение 15 минут\n"
                    "2. Проведем бесплатную консультацию\n"
                    "3. Подготовлю ТЗ и коммерческое предложение\n"
                    "4. Начнем работу!\n\n"
                    "💬 *Мои контакты:*\n"
                    "Telegram: @ваш_username\n"
                    "Email: ваш@email.com\n\n"
                    "До связи! 👋",
                    parse_mode='Markdown'
                )
                
                # Очищаем данные пользователя
                context.user_data.clear()
                
            except Exception as e:
                logger.error(f"Ошибка отправки заявки: {e}")
                await query.edit_message_text(
                    "⚠️ *Ошибка отправки заявки*\n\n"
                    "Попробуйте позже или свяжитесь напрямую:\n"
                    "@ваш_username",
                    parse_mode='Markdown'
                )
        
        elif query.data == "edit_order":
            await query.edit_message_text(
                "✏️ Давайте начнем заново. Выберите услугу:",
                reply_markup=self._get_services_keyboard()
            )
            return SERVICE_CHOICE
        
        return ConversationHandler.END
    
    async def cancel_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена заказа"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Заказ отменен.\n\n"
            "Если передумаете — просто напишите /order\n"
            "Или задайте вопрос через /contact",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных сообщений"""
        user_message = update.message.text.lower()
        user = update.effective_user
        
        # Простые ответы на частые вопросы
        responses = {
            'привет': f"Привет, {user.first_name}! Чем могу помочь?",
            'здравствуйте': f"Здравствуйте, {user.first_name}! Задавайте вопросы!",
            'как дела': "Отлично, готов помочь с вашим проектом! А у вас?",
            'стоимость': "Стоимость зависит от сложности проекта. Используйте /price для подробностей",
            'сколько стоит': "Цены от 10 000 ₽. Подробнее: /price",
            'сроки': "Сроки от 3 дней. Зависит от сложности. /order для расчета",
            'примеры': "Примеры работ: /portfolio",
            'контакты': "Мои контакты: /contact",
            'помощь': "Справка: /help",
            'заказ': "Оформить заказ: /order",
            'услуги': "Мои услуги: /services"
        }
        
        for keyword, response in responses.items():
            if keyword in user_message:
                await update.message.reply_text(response)
                return
        
        # Если не нашли ключевые слова
        await update.message.reply_text(
            f"Не совсем понял ваш вопрос 😊\n\n"
            f"Можете:\n"
            f"• Использовать команды из меню\n"
            f"• Написать /help для справки\n"
            f"• Написать /order для оформления заказа\n"
            f"• Связаться напрямую: /contact"
        )
    
    async def button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на inline-кнопки"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "order":
            await self.start_order(update, context)
        elif query.data == "services":
            await self.show_services(update, context)
        elif query.data == "price":
            await self.show_prices(update, context)
        elif query.data == "contact":
            await self.contact_admin(update, context)
        elif query.data == "portfolio":
            await self.show_portfolio(update, context)
        elif query.data.startswith("service_"):
            await self.choose_service(update, context)
        elif query.data == "calculate_price":
            await query.edit_message_text(
                "💰 Для точного расчета стоимости:\n\n"
                "1. Опишите проект через /order\n"
                "2. Или свяжитесь со мной через /contact\n\n"
                "Я подготовлю детальный расчет в течение часа!",
                parse_mode='Markdown'
            )
        elif query.data == "get_consultation":
            await query.edit_message_text(
                "🎯 Отличный выбор! Консультация бесплатна.\n\n"
                "📞 Свяжитесь со мной:\n"
                "Telegram: @ваш_username\n"
                "Или оформите заявку через /order\n\n"
                "Обсудим ваш проект и найдем лучшее решение!",
                parse_mode='Markdown'
            )
    
    async def run(self):
        """Запуск бота"""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("🤖 Бот запущен и готов к работе!")
        
        # Бесконечный цикл
        await asyncio.Event().wait()

def main():
    """Основная функция"""
    # Получаем токен из переменных окружения
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не найден!")
        print("Создайте файл .env и добавьте BOT_TOKEN=ваш_токен")
        return
    
    # Создаем и запускаем бота
    bot = LandingBot(BOT_TOKEN)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")

if __name__ == "__main__":
    main()
