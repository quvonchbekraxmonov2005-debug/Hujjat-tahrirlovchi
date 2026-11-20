"""Veb-interfeys (Flask) + Telegram Webhook."""
import asyncio
import io
import os
import re
import urllib.request

from flask import Flask, jsonify, render_template, request, send_file
from telegram import Update
from werkzeug.middleware.proxy_fix import ProxyFix

import db
from bot import build_app
from config import BOT_TOKEN, MAX_FILE_MB
from formatter import Options, TitleInfo, format_document, make_reference

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_MB * 1024 * 1024

tg_app = build_app() if BOT_TOKEN else None

_loop = asyncio.new_event_loop()


def _run_async(coro):
    asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)


async def _handle_update(data: dict):
    if not tg_app._initialized:
        await tg_app.initialize()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/set_webhook")
def set_webhook():
    if not BOT_TOKEN:
        return jsonify(error="BOT_TOKEN topilmadi"), 400
    host = request.host_url.rstrip("/").replace("http://", "https://")
    webhook_url = f"{host}/webhook/{BOT_TOKEN}"
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    res = urllib.request.urlopen(api_url).read().decode("utf-8")
    return jsonify(status="Webhook ulandi!", url=webhook_url, telegram_response=res)


@app.post(f"/webhook/{BOT_TOKEN}")
def telegram_webhook():
    if not tg_app:
        return "No bot", 400
    data = request.get_json(force=True)
    _run_async(_handle_update(data))
    return "OK", 200