"""Telegram bot. Ishga tushirish: python bot.py"""
import asyncio
import io
import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

import db
from config import ADMIN_IDS, BOT_TOKEN, FREE_DOCS, MAX_FILE_MB, PAY_INFO, PRICE_TEXT
from formatter import Options, TitleInfo, format_document

logging.basicConfig(level=logging.INFO)

TITLE_HELP = (
    "Titul varaq uchun 7 qatorni shu tartibda bitta xabarda yuboring:\n\n"
    "Universitet\nFakultet\nIsh turi (masalan: KURS ISHI)\nMavzu\nTalaba (F.I.O., guruh)\nIlmiy rahbar\nShahar va yil"
)


async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(
        "Assalomu alaykum! Men kurs ishi, diplom ishi va hisobotlarni OTM standartiga (Times New Roman 14, "
        "1.5 interval, hoshiyalar, mundarija) keltiraman.\n\n"
        f"📄 .docx yoki .txt faylni yuboring.\nBirinchi {FREE_DOCS} ta hujjat bepul, keyingisi: {PRICE_TEXT}.\n\n"
        "/balans — qolgan limit")


async def balans(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = str(u.effective_user.id)
    await u.message.reply_text(f"Qolgan hujjatlar: {db.left(uid)}\nID: {uid}")


async def add(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id not in ADMIN_IDS:
        return
    try:
        uid, n = c.args[0], int(c.args[1])
    except Exception:
        return await u.message.reply_text("Foydalanish: /add <user_id> <soni>")
    db.add_credits(uid, n)
    await u.message.reply_text(f"{uid} ga {n} ta hujjat qo‘shildi.")
    try:
        await c.bot.send_message(int(uid), f"✅ Hisobingizga {n} ta hujjat qo‘shildi.")
    except Exception:
        pass


async def on_file(u: Update, c: ContextTypes.DEFAULT_TYPE):
    d = u.message.document
    name = d.file_name or "hujjat.docx"
    if not name.lower().endswith((".docx", ".txt")):
        return await u.message.reply_text("Faqat .docx yoki .txt fayl yuboring. (.doc bo‘lsa, Word’da «Saqlash» → .docx qiling.)")
    if d.file_size and d.file_size > min(MAX_FILE_MB, 20) * 1024 * 1024:
        return await u.message.reply_text(f"Fayl juda katta (maks. {min(MAX_FILE_MB, 20)} MB).")
    uid = str(u.effective_user.id)
    if db.left(uid) <= 0:
        return await u.message.reply_text(f"Bepul limit tugadi.\n{PRICE_TEXT}\n\n{PAY_INFO}\n\nID raqamingiz: {uid}")
    f = await d.get_file()
    c.user_data["file"] = (bytes(await f.download_as_bytearray()), name)
    c.user_data["state"] = None
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Titul varaqsiz", callback_data="plain"),
        InlineKeyboardButton("Titul varaq bilan", callback_data="title"),
    ]])
    await u.message.reply_text("Qanday formatlay?", reply_markup=kb)


async def process(u: Update, c: ContextTypes.DEFAULT_TYPE, title):
    uid = str(u.effective_user.id)
    data, name = c.user_data.get("file", (None, None))
    msg = u.effective_message
    if not data:
        return await msg.reply_text("Avval fayl yuboring.")
    if not db.consume(uid):
        return await msg.reply_text(f"Limit tugadi.\n{PAY_INFO}\nID: {uid}")
    await msg.reply_text("⏳ Formatlanmoqda...")
    try:
        out, rep = await asyncio.to_thread(format_document, data, name, Options(title=title))
    except Exception as e:
        db.refund(uid)
        return await msg.reply_text(f"Xatolik: {e}\nLimit qaytarildi.")
    bio = io.BytesIO(out)
    bio.name = re.sub(r"\.[^.]+$", "", name) + "_formatlangan.docx"
    await msg.reply_document(
        bio,
        caption=(f"✅ Tayyor!\nSarlavhalar: {rep['headings']}, adabiyotlar: {rep['references']}, jadvallar: {rep['tables']}\n"
                 "Word’da ochganda «Maydonlarni yangilash» so‘ralsa — «Ha» deng (mundarija shunda to‘ladi).\n"
                 f"Qolgan limit: {db.left(uid)}"))
    c.user_data.clear()


async def on_button(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    if q.data == "plain":
        await process(u, c, None)
    else:
        c.user_data["state"] = "title"
        await q.message.reply_text(TITLE_HELP)


async def on_text(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if c.user_data.get("state") != "title":
        return await u.message.reply_text("Hujjat (.docx / .txt) faylini yuboring.")
    lines = [x.strip() for x in u.message.text.split("\n") if x.strip()]
    if len(lines) < 7:
        return await u.message.reply_text("7 ta qator kerak.\n\n" + TITLE_HELP)
    last = lines[6].split()
    year = last[-1] if last and last[-1].isdigit() else ""
    city = " ".join(last[:-1]) if year else lines[6]
    t = TitleInfo(university=lines[0], faculty=lines[1], work_type=lines[2], topic=lines[3],
                  student=lines[4], supervisor=lines[5], city=city, year=year)
    c.user_data["state"] = None
    await process(u, c, t)


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN o‘rnatilmagan")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balans", balans))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(MessageHandler(filters.Document.ALL, on_file))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling()


if __name__ == "__main__":
    main()
