import os
import tempfile
import re
import speech_recognition as sr
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from pydub import AudioSegment
from utils import analyze_text
import docx2txt
import PyPDF2
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

CHOOSING, CORRECTING = range(2)
user_sessions = {}

CHANNEL_ID = os.getenv("CHANNEL_ID")


def sanitize_for_telegram(html_text: str) -> str:
    """HTMLdagi <span class="error-word"> teglarini <b> ga almashtiradi."""
    soup = BeautifulSoup(html_text, "html.parser")
    for span in soup.find_all("span", class_="error-word"):
        b_tag = soup.new_tag("b")
        b_tag.string = span.get_text()
        span.replace_with(b_tag)
    return str(soup.body.decode_contents() if soup.body else soup)


async def send_channel_message(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text)
    except Exception as e:
        print(f"Kanalga xabar yuborishda xato: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    username = user.username or user.first_name or "Foydalanuvchi"
    await update.message.reply_text(
        "Salom! Men O'zTahlilchi botman. Matn, ovoz yoki fayl yuboring — men xatoliklarni topaman ✅"
    )
    await send_channel_message(context, f"ℹ️ @{username} bot ishga tushdi.")
    return CHOOSING


async def ask_correction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = user_sessions.get(user_id)
    if not session:
        await update.message.reply_text("Iltimos, avval matn yuboring.")
        return ConversationHandler.END

    idx = session["current_index"]
    mistakes = session["mistakes"]

    if idx >= len(mistakes):
        cleaned = sanitize_for_telegram(session['corrected_text'])
        await update.message.reply_text(f"✅ Yakuniy to‘g‘rilangan matn:\n\n{cleaned}", parse_mode="HTML")

        username = update.message.from_user.username or update.message.from_user.first_name or "Foydalanuvchi"
        await send_channel_message(context, f"✅ @{username} matn tahlilini yakunladi.")
        user_sessions.pop(user_id, None)
        return ConversationHandler.END

    mistake_word = mistakes[idx]
    options = session["suggestions"].get(mistake_word, [])

    if not options:
        # Tavsiyalar yo'q bo'lsa keyingisiga o'tish
        session["current_index"] += 1
        return await ask_correction(update, context)

    msg = f"❗ Xato so‘z: <b>{mistake_word}</b>\nTavsiya:\n"
    msg += "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options[:3]))
    msg += "\nIltimos, to‘g‘ri deb hisoblagan raqamni kiriting (1-3)."
    await update.message.reply_text(msg, parse_mode="HTML")
    return CORRECTING


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("⚠️ Iltimos, matn kiriting.")
        return CHOOSING

    corrected, mistakes, suggestions = analyze_text(text)
    user_id = update.message.from_user.id
    user_sessions[user_id] = {
        "original_text": text,
        "corrected_text": corrected,
        "mistakes": mistakes,
        "suggestions": suggestions,
        "current_index": 0,
    }

    username = update.message.from_user.username or update.message.from_user.first_name or "Foydalanuvchi"

    if not mistakes:
        await update.message.reply_text("✅ Matnda xatolik topilmadi!")
        await send_channel_message(context, f"✅ @{username} matn tahlil qilindi, xatolik yo'q.")
        user_sessions.pop(user_id, None)
        return ConversationHandler.END

    return await ask_correction(update, context)


def join_words_with_html_tags(words):
    corrected_text = ""
    word_pattern = re.compile(r"[a-zA-Z0-9_а-яА-ЯёЁ’‘']+", re.UNICODE)
    html_tag_pattern = re.compile(r"<[^>]+>")

    for i, w in enumerate(words):
        if i == 0:
            corrected_text += w
        else:
            if html_tag_pattern.match(w):
                corrected_text += w
            else:
                corrected_text += (" " if word_pattern.match(w) else "") + w
    return corrected_text


async def receive_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = user_sessions.get(user_id)
    if not session:
        await update.message.reply_text("Iltimos, avval matn yuboring.")
        return ConversationHandler.END

    choice = update.message.text.strip()
    if choice not in {'1', '2', '3'}:
        await update.message.reply_text("Faqat 1, 2 yoki 3 raqamlarini kiriting.")
        return CORRECTING

    idx = session["current_index"]
    mistake_word = session["mistakes"][idx]
    chosen_word = session["suggestions"][mistake_word][int(choice) - 1]

    words = re.findall(r"<[^>]+>|[a-zA-Z0-9_а-яА-ЯёЁ’‘']+|[^\w\s]", session["corrected_text"], re.UNICODE)

    replaced = False
    for i, w in enumerate(words):
        if w.lower() == mistake_word.lower() and not replaced:
            if w.istitle():
                words[i] = chosen_word.capitalize()
            elif w.isupper():
                words[i] = chosen_word.upper()
            else:
                words[i] = chosen_word
            replaced = True

    session["corrected_text"] = join_words_with_html_tags(words)
    session["current_index"] += 1
    return await ask_correction(update, context)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice_file = await update.message.voice.get_file()
    ogg_path = wav_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_ogg:
            await voice_file.download_to_drive(tmp_ogg.name)
            ogg_path = tmp_ogg.name

        wav_path = ogg_path.replace(".ogg", ".wav")
        AudioSegment.from_ogg(ogg_path).export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio, language="uz-UZ")
        except sr.UnknownValueError:
            await update.message.reply_text("⚠️ Ovoz tanib bo‘lmadi, iltimos, yana urinib ko‘ring.")
            return
        except sr.RequestError as e:
            await update.message.reply_text(f"⚠️ Ovoz tanib olishda muammo: {e}")
            return

        update.message.text = text
        return await handle_text(update, context)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Ovoz tanib bo‘lmadi: {e}")
    finally:
        for path in [ogg_path, wav_path]:
            if path and os.path.exists(path):
                os.remove(path)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file = await doc.get_file()
    _, ext = os.path.splitext(doc.file_name.lower())

    if ext not in [".txt", ".docx", ".pdf"]:
        await update.message.reply_text("⚠️ Faqat .txt, .docx, .pdf fayllar qo‘llab-quvvatlanadi.")
        return

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        if ext == ".txt":
            with open(tmp_path, "r", encoding="utf-8") as f:
                text = f.read()
        elif ext == ".docx":
            text = docx2txt.process(tmp_path)
        else:
            with open(tmp_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "".join(page.extract_text() or "" for page in reader.pages)

        update.message.text = text.strip()
        return await handle_text(update, context)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Faylni o‘qishda xatolik yuz berdi: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_sessions.pop(update.message.from_user.id, None)
    await update.message.reply_text("❌ Jarayon bekor qilindi.")
    return ConversationHandler.END


def main():
    application = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
                MessageHandler(filters.VOICE, handle_voice),
                MessageHandler(filters.Document.ALL, handle_document)
            ],
            CORRECTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_choice)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
