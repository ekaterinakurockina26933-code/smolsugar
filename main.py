# File: main.py — основной бот для записи на шугаринг (логика Telegram-бота)

import os
import json
import csv
from datetime import datetime
from warnings import filterwarnings
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from telegram.warnings import PTBUserWarning

# Скрываем предупреждение PTB
filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

# Загружаем переменные из .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not TOKEN or not ADMIN_CHAT_ID:
    raise ValueError("Ошибка: добавьте TELEGRAM_TOKEN и ADMIN_CHAT_ID в файл .env")

# Состояния для ConversationHandler
WAITING_FOR_ZONE, WAITING_FOR_SLOT, WAITING_FOR_PHONE = range(3)

# Ручные данные (загружаются при старте)
PRICE_LIST = {
    "Голень": 1500,
    "Бикини": 2000,
    "Подмышки": 1000
}

# Фиксированный календарь мастера (слоты на сегодня)
MASTER_SLOTS = [
    "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"
]

# FAQ данные
FAQ_DATA = {
    "📍 Адрес салона": "📍 Наш адрес: ул. Примерная, д. 1, 2 этаж.\n🕒 Работаем с 10:00 до 20:00 без выходных.",
    "🚫 Противопоказания": "❌ Противопоказания к шугарингу:\n\n• Сахарный диабет\n• Варикозное расширение вен\n• Повреждения кожи (раны, царапины)\n• Герпес в активной стадии\n• Беременность (требуется консультация врача)\n• Приём некоторых лекарств (ретиноиды, антикоагулянты)",
    "🧴 Подготовка к процедуре": "✅ Как подготовиться к шугарингу:\n\n1. Длина волос - от 3 до 7 мм (оптимально 5 мм)\n2. За 2 дня до процедуры сделайте мягкий скраб\n3. За 24 часа не загорайте\n4. За 2 часа до процедуры не наносите кремы и масла\n5. Примите душ, кожа должна быть чистой\n6. Возьмите с собой свободное бельё",
    "⚠️ Ограничения после процедуры": "❗ Что нельзя делать после шугаринга:\n\n• 24 часа - не загорать и не ходить в солярий\n• 24 часа - не посещать бассейн, сауну, баню\n• 24 часа - не носить синтетическое бельё\n• Не наносить агрессивные косметические средства 2 дня\n• Не использовать скрабы 3 дня\n• Не расчёсывать и не тереть кожу",
    "🤕 Больно ли?": "😊 Ощущения при шугаринге:\n\n• Это менее болезненно, чем восковая эпиляция\n• Боль сравнима с щипком или комариным укусом\n• Первые процедуры могут быть чувствительнее\n• Со временем кожа привыкает, боль уменьшается\n• Мастер использует специальную технику, которая снижает боль\n• Можно принять обезболивающее за 30 минут до процедуры (по желанию)"
}

MEMO_TEXT = "📍 Адрес: ул. Примерная, д. 1\n🧴 Подготовка: чистая сухая кожа, без крема за 2 часа до процедуры."

# Хранилище записей (файл)
BOOKINGS_FILE = "bookings.json"
if os.path.exists(BOOKINGS_FILE):
    with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
        bookings = json.load(f)
else:
    bookings = {}

def save_bookings():
    with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)

def get_free_slots():
    """Возвращает слоты, которые ещё не заняты"""
    all_slots = MASTER_SLOTS.copy()
    taken = [b["slot"] for b in bookings.values() if b["slot"] in all_slots]
    return [s for s in all_slots if s not in taken]

def add_faq_and_operator_buttons(keyboard):
    """Добавляет кнопки FAQ и Связаться с оператором"""
    keyboard.append([InlineKeyboardButton("❓ FAQ", callback_data="faq_menu")])
    keyboard.append([InlineKeyboardButton("👩‍💼 Связаться с оператором", callback_data="contact_operator")])
    return keyboard

def add_back_button(keyboard, back_callback):
    """Добавляет кнопку назад"""
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=back_callback)])
    return keyboard

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text=None):
    """Показывает главное меню с кнопками"""
    keyboard = [
        [InlineKeyboardButton("💰 Узнать стоимость", callback_data="price")],
        [InlineKeyboardButton("📅 Выбрать время", callback_data="time")]
    ]
    keyboard = add_faq_and_operator_buttons(keyboard)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = message_text if message_text else "Добро пожаловать! Выберите действие:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def show_faq_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню FAQ с вопросами"""
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for question in FAQ_DATA.keys():
        keyboard.append([InlineKeyboardButton(question, callback_data=f"faq_{question}")])
    keyboard = add_faq_and_operator_buttons(keyboard)
    keyboard = add_back_button(keyboard, "main_menu")
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text("📖 Часто задаваемые вопросы:\n\nВыберите интересующий вас вопрос:", reply_markup=reply_markup)

async def show_faq_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str):
    """Показывает ответ на FAQ вопрос"""
    query = update.callback_query
    await query.answer()
    
    answer = FAQ_DATA.get(question, "Информация временно недоступна")
    
    keyboard = [
        [InlineKeyboardButton("❓ Другие вопросы", callback_data="faq_menu")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    keyboard = add_faq_and_operator_buttons(keyboard)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(f"📌 *{question}*\n\n{answer}", reply_markup=reply_markup, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    context.user_data.clear()
    await show_main_menu(update, context)

async def contact_operator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Связаться с оператором'"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")]]
    keyboard = add_faq_and_operator_buttons(keyboard)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👩‍💼 Напишите ваш вопрос. Оператор скоро ответит.\n\n"
        "Чтобы вернуться в меню, нажмите кнопку ниже.",
        reply_markup=reply_markup
    )
    
    context.user_data["waiting_for_operator"] = True

async def price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Узнать стоимость'"""
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for zone in PRICE_LIST.keys():
        keyboard.append([InlineKeyboardButton(zone, callback_data=f"select_zone_{zone}")])
    keyboard = add_faq_and_operator_buttons(keyboard)
    keyboard = add_back_button(keyboard, "main_menu")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите зону обработки:", reply_markup=reply_markup)
    return WAITING_FOR_ZONE

async def select_zone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора зоны"""
    query = update.callback_query
    await query.answer()
    
    zone = query.data.replace("select_zone_", "")
    price = PRICE_LIST.get(zone)
    
    if not price:
        keyboard = add_faq_and_operator_buttons([[]])
        keyboard = add_back_button(keyboard, "price")
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Информация временно недоступна", reply_markup=reply_markup)
        return
    
    context.user_data["zone"] = zone
    context.user_data["price"] = price
    
    keyboard = [
        [InlineKeyboardButton("📅 Записаться", callback_data="start_booking")],
        [InlineKeyboardButton("🔙 Другие зоны", callback_data="price")]
    ]
    keyboard = add_faq_and_operator_buttons(keyboard)
    keyboard = add_back_button(keyboard, "main_menu")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"💵 {zone}: {price} ₽\n\nХотите записаться?", reply_markup=reply_markup)

async def start_booking_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса записи - показываем слоты"""
    query = update.callback_query
    await query.answer()
    
    free_slots = get_free_slots()
    if not free_slots:
        keyboard = add_faq_and_operator_buttons([[]])
        keyboard = add_back_button(keyboard, "main_menu")
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Нет доступного времени", reply_markup=reply_markup)
        return
    
    keyboard = []
    for slot in free_slots:
        keyboard.append([InlineKeyboardButton(slot, callback_data=f"select_slot_{slot}")])
    keyboard = add_faq_and_operator_buttons(keyboard)
    keyboard = add_back_button(keyboard, "main_menu")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите свободное время:", reply_markup=reply_markup)
    return WAITING_FOR_SLOT

async def select_slot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора слота"""
    query = update.callback_query
    await query.answer()
    
    slot = query.data.replace("select_slot_", "")
    
    # Проверяем, не занят ли слот
    if slot not in get_free_slots():
        free_slots = get_free_slots()
        if not free_slots:
            keyboard = add_faq_and_operator_buttons([[]])
            keyboard = add_back_button(keyboard, "main_menu")
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Это время уже занято. Свободных слотов нет.", reply_markup=reply_markup)
            return
        keyboard = []
        for s in free_slots:
            keyboard.append([InlineKeyboardButton(s, callback_data=f"select_slot_{s}")])
        keyboard = add_faq_and_operator_buttons(keyboard)
        keyboard = add_back_button(keyboard, "main_menu")
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Это время уже занято. Выберите другое:", reply_markup=reply_markup)
        return
    
    context.user_data["slot"] = slot
    
    # Спрашиваем телефон
    keyboard = add_faq_and_operator_buttons([[]])
    keyboard = add_back_button(keyboard, "main_menu")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Вы выбрали {slot}.\n\nВведите ваш номер телефона для связи (например, +79991234567):",
        reply_markup=reply_markup
    )
    return WAITING_FOR_PHONE

async def phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода номера телефона"""
    phone = update.message.text.strip()
    
    # Проверяем формат телефона
    if not any(c.isdigit() for c in phone) or len(phone) < 10:
        await update.message.reply_text("❌ Введите корректный номер телефона (не менее 10 цифр). Попробуйте ещё раз:")
        return WAITING_FOR_PHONE
    
    # Проверяем, что есть все данные
    if "zone" not in context.user_data or "price" not in context.user_data or "slot" not in context.user_data:
        await update.message.reply_text(
            "❌ Что-то пошло не так. Пожалуйста, начните запись заново с /start"
        )
        context.user_data.clear()
        await show_main_menu(update, context)
        return ConversationHandler.END
    
    user_id = str(update.effective_user.id)
    
    booking = {
        "user_id": user_id,
        "zone": context.user_data["zone"],
        "price": context.user_data["price"],
        "slot": context.user_data["slot"],
        "phone": phone,
        "created_at": datetime.now().isoformat()
    }
    bookings[user_id] = booking
    save_bookings()
    
    # Сохраняем в CSV
    leads_file = "leads.csv"
    file_exists = os.path.exists(leads_file)
    
    try:
        with open(leads_file, "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Дата", "Имя пользователя", "ID пользователя", "Телефон", "Зона", "Время", "Цена"])
            writer.writerow([
                booking["created_at"],
                update.effective_user.first_name or "Не указано",
                user_id,
                phone,
                booking["zone"],
                booking["slot"],
                booking["price"]
            ])
        print(f"✅ Запись сохранена в leads.csv")
    except Exception as e:
        print(f"❌ Ошибка сохранения CSV: {e}")
    
    # Отправляем подтверждение
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
    keyboard = add_faq_and_operator_buttons(keyboard)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"✅ Вы записаны!\n\n"
        f"🕒 Время: {booking['slot']}\n"
        f"💵 Цена: {booking['price']} ₽\n"
        f"📞 Ваш телефон: {booking['phone']}\n\n"
        f"{MEMO_TEXT}\n\n"
        f"Спасибо за запись!",
        reply_markup=reply_markup
    )
    
    # Уведомление админу
    user = update.effective_user
    if user_id != ADMIN_CHAT_ID:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"📅 Новая запись!\n"
                 f"Пользователь: {user.first_name} (ID: {user_id})\n"
                 f"Зона: {booking['zone']}\n"
                 f"Время: {booking['slot']}\n"
                 f"Телефон: {booking['phone']}"
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    await update.message.reply_text("Действие отменено.")
    context.user_data.clear()
    await show_main_menu(update, context)
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех текстовых сообщений"""
    user_id = str(update.effective_user.id)
    
    # Если пользователь в режиме ожидания оператора
    if context.user_data.get("waiting_for_operator"):
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✉️ От пользователя {update.effective_user.first_name} (ID: {user_id}):\n{update.message.text}"
        )
        await update.message.reply_text("✅ Сообщение отправлено оператору. Ожидайте ответа.")
        context.user_data["waiting_for_operator"] = False
        return
    
    # Если это админ и сообщение начинается с /reply
    if user_id == ADMIN_CHAT_ID and update.message.text.startswith("/reply "):
        parts = update.message.text.split(maxsplit=2)
        if len(parts) < 3:
            await update.message.reply_text(
                "❗ Формат: `/reply ID_пользователя текст_ответа`\n\n"
                "Пример: `/reply 123456789 Здравствуйте!`",
                parse_mode="Markdown"
            )
            return
        target_user_id = parts[1]
        reply_text = parts[2]
        try:
            await context.bot.send_message(chat_id=int(target_user_id), text=f"👩‍💼 Оператор: {reply_text}")
            await update.message.reply_text("✅ Сообщение отправлено пользователю.")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
        return
    
    # Если пользователь написал что-то без кнопок
    await update.message.reply_text(
        "Пожалуйста, используйте кнопки меню.\n"
        "Нажмите /start для начала."
    )

def main():
    app = Application.builder().token(TOKEN).build()
    
    # ConversationHandler для процесса записи
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(price_callback, pattern="^price$"),
            CallbackQueryHandler(start_booking_callback, pattern="^start_booking$")
        ],
        states={
            WAITING_FOR_ZONE: [CallbackQueryHandler(select_zone_callback, pattern="^select_zone_")],
            WAITING_FOR_SLOT: [CallbackQueryHandler(select_slot_callback, pattern="^select_slot_")],
            WAITING_FOR_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv_handler)
    
    # Обработчики команд и кнопок
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(contact_operator, pattern="^contact_operator$"))
    app.add_handler(CallbackQueryHandler(show_faq_menu, pattern="^faq_menu$"))
    app.add_handler(CallbackQueryHandler(show_faq_answer, pattern="^faq_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот успешно запущен!")
    print(f"Администратор: {ADMIN_CHAT_ID}")
    app.run_polling()

if __name__ == "__main__":
    main()