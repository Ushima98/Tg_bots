import openai
import gspread
import re
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, ContextTypes, filters, CommandHandler
from datetime import datetime
from collections import deque

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "7602071981:AAHNZrSY-t-Ugcx4WWaF7dlUC0RG8hg8TN0"
OPENAI_API_KEY = "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"
DOCUMENT_ID = "171aUnZqALyEUXxRq78165PwhVRy9YiUNhsCn_nLOIxg"
GOOGLE_SHEET_ID = "1kfytBMdv__jyvmWyWyOZdWn5twf15EcxrT85Kcbqow4"
SERVICE_ACCOUNT_FILE = "aiwork-462523-a43dd894c81b.json"

# === GOOGLE AUTH ===
SCOPES = ['https://www.googleapis.com/auth/documents.readonly', 'https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
doc_service = build('docs', 'v1', credentials=creds)
gsheet_client = gspread.authorize(creds)
sheet = gsheet_client.open_by_key(GOOGLE_SHEET_ID)
log_sheet = sheet.worksheet("Логи")
buttons_sheet = sheet.worksheet("Кнопки")
users_sheet = sheet.worksheet("Пользователи")

# === LOAD SYSTEM PROMPT ===
system_prompt = (
    "Ты представляешь компанию AIwork, отвечай только на вопросы связанные с ней. "
    "Ты — дружелюбный маркетолог и эксперт по ИИ-ботам 🤖 для бизнеса. "
    "Объясняй просто, ясно, с воодушевлением, добавляй смайлы и примеры 🛍️📈. "
    "Твоя цель — заинтересовать, показать выгоды, автоматизацию и экономию времени ⏳. "
    "Не используй форматирование с * или _. Пиши легко и по-человечески 😊."
)

# === MEMORY & STATE ===
user_memory = {}
user_states = {}

def get_gdoc_content():
    doc = doc_service.documents().get(documentId=DOCUMENT_ID).execute()
    content = ''
    for element in doc.get("body", {}).get("content", []):
        for e in element.get("paragraph", {}).get("elements", []):
            if 'textRun' in e:
                content += e['textRun']['content']
    return content

def get_bottom_example_keyboard():
    keyboard = [
        ["ИИ-бот в вашем бизнесе 🤖"],
        ["Контакты 📞", "Кейсы 💼"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def log_to_sheet(user_id, username, message, response):
    log_sheet.append_row([
        str(datetime.now()), str(user_id), username or "", message, response
    ])

def add_or_update_user(user_id, username):
    str_user_id = str(user_id)
    all_data = users_sheet.get_all_values()
    headers = all_data[0]
    records = all_data[1:]

    id_column = [row[0] for row in records]
    now_str = str(datetime.now())

    if str_user_id in id_column:
        row_index = id_column.index(str_user_id) + 2  # +2: 1 for header, 1 for 1-based indexing
        users_sheet.update_cell(row_index, 3, now_str)
    else:
        users_sheet.append_row([str_user_id, username or "", now_str])

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("Кнопки через Google Sheets временно не поддерживаются.")

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    add_or_update_user(user_id, username)
    user_states[user_id] = "normal"

    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=10)

    welcome_text = (
        "Привет! 👋 Я бот AIwork 🤖. "
        "Хотите узнать, как автоматизировать задачи, увеличить продажи и сэкономить время с помощью ИИ-помощника? ⏳ "
        "Просто задайте вопрос или нажмите на кнопку ниже 👇, чтобы узнать, как ИИ-бот может помочь конкретно в вашем бизнесе."
    )
    await update.message.reply_text(welcome_text, reply_markup=get_bottom_example_keyboard())
    log_to_sheet(user_id, username, "/start", welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    add_or_update_user(user_id, username)
    state = user_states.get(user_id, "normal")

    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=10)

    openai.api_key = OPENAI_API_KEY

    if user_message == "ИИ-бот в вашем бизнесе 🤖":
        user_states[user_id] = "awaiting_business"
        await update.message.reply_text(
            "Расскажите, пожалуйста, немного о своём бизнесе, чтобы я мог показать пример работы ИИ-бота именно для вас.",
            reply_markup=None
        )
        return

    if user_message == "Контакты 📞":
        contacts_text = (
            "📞 Наши контакты:\n"
            "Телефон: +7 901 368 56 09\n"
            "Телеграм: @AIwork_mozhaev\n"
            "Будем рады помочь! 😊"
        )
        await update.message.reply_text(contacts_text, reply_markup=get_bottom_example_keyboard())
        log_to_sheet(user_id, username, user_message, contacts_text)
        return

    if user_message == "Кейсы 💼":
        cases_text = "Готовых ботов можно посмотреть здесь - @AIwork_bots"
        await update.message.reply_text(cases_text, reply_markup=get_bottom_example_keyboard())
        log_to_sheet(user_id, username, user_message, cases_text)
        return

    if state == "awaiting_business":
        business_desc = user_message.strip()
        prompt_for_example = (
            f"Пожалуйста, представь, что у пользователя бизнес: {business_desc}. "
            "Опиши дружелюбно и вдохновляюще, как ИИ-бот может помочь именно этому бизнесу, "
            "расскажи о выгодах, автоматизации, экономии времени и денег, приведи примеры. "
            "При объяснении делай упор на обратную связь, экономии времени и денег на менеджеров. "
            "Пиши просто, понятно, добавь смайлы и избегай формата диалога."
        )

        messages_for_example = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_for_example}
        ]

        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=messages_for_example,
            temperature=0.7,
            max_tokens=600
        )

        reply = response['choices'][0]['message']['content']
        user_states[user_id] = "normal"
        await update.message.reply_text(reply, reply_markup=get_bottom_example_keyboard())
        log_to_sheet(user_id, username, user_message, reply)
        return

    # --- Нормальный режим: обработка через OpenAI ---
    gdoc_content = get_gdoc_content()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Вот информация о моей деятельности:\n{gdoc_content}"}
    ]
    messages.extend(user_memory[user_id])
    messages.append({"role": "user", "content": user_message})

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=500
    )

    raw_reply = response['choices'][0]['message']['content']
    clean_reply = re.sub(r'[*]', '', raw_reply)
    readable_reply = re.sub(r'([:!.])\s*', r'\1\n', clean_reply)

    user_memory[user_id].append({"role": "user", "content": user_message})
    user_memory[user_id].append({"role": "assistant", "content": readable_reply})

    await update.message.reply_text(readable_reply, reply_markup=get_bottom_example_keyboard())
    log_to_sheet(user_id, username, user_message, readable_reply)

# === MAIN ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("Бот запущен")
    app.run_polling()