"""Veb-interfeys (Flask). Ishga tushirish: gunicorn -w 2 -b 127.0.0.1:8000 app:app"""
import io
import re

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

import db
from config import MAX_FILE_MB
from formatter import Options, TitleInfo, format_document, make_reference

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_MB * 1024 * 1024


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/format")
def format_route():
    f = request.files.get("file")
    pasted = request.form.get("text", "").strip()
    if not f and not pasted:
        return jsonify(error="Fayl yuklang yoki matn kiriting."), 400

    uid = f"web:{request.remote_addr}"
    if not db.consume(uid):
        return jsonify(error="Bepul limit tugadi. Davom etish uchun Telegram botimizdan foydalaning."), 402

    try:
        if f:
            data, name = f.read(), f.filename or "hujjat.docx"
        else:
            data, name = pasted.encode("utf-8"), "matn.txt"
        title = None
        if request.form.get("titul") == "1":
            title = TitleInfo(
                university=request.form.get("university", ""),
                faculty=request.form.get("faculty", ""),
                work_type=request.form.get("work_type", "KURS ISHI"),
                topic=request.form.get("topic", ""),
                student=request.form.get("student", ""),
                supervisor=request.form.get("supervisor", ""),
                city=request.form.get("city", "Toshkent"),
                year=request.form.get("year", ""),
            )
        out, rep = format_document(data, name, Options(title=title, toc=request.form.get("toc", "1") == "1"))
    except Exception as e:  # noto‘g‘ri fayl va h.k.
        db.refund(uid)
        return jsonify(error=f"Faylni qayta ishlab bo‘lmadi: {e}"), 400

    base = re.sub(r"\.[^.]+$", "", name) or "hujjat"
    return send_file(io.BytesIO(out), as_attachment=True, download_name=f"{base}_formatlangan.docx",
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.post("/reference")
def reference_route():
    d = request.get_json(force=True)
    try:
        ref = make_reference(
            d.get("kind", "kitob"), d.get("author", ""), d.get("title", ""), d.get("city", ""),
            d.get("publisher", ""), d.get("year", ""), d.get("pages", ""), d.get("journal", ""),
            d.get("number", ""), d.get("url", ""), d.get("accessed", ""))
        return jsonify(reference=ref)
    except Exception as e:
        return jsonify(error=str(e)), 400


if __name__ == "__main__":
    app.run(debug=True, port=8000)
