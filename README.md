# AutoDoc / KursIshi AI

## Fayllar
- formatter.py — asosiy formatlash (GOST), adabiyot yozuvi generatori
- app.py + templates/index.html — veb-interfeys (Flask)
- bot.py — Telegram bot
- db.py, config.py — limitlar (freemium) va sozlamalar

## O‘rnatish (Ubuntu server)
    sudo apt update && sudo apt install -y python3-venv
    cd /opt/autodoc
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env     # BOT_TOKEN va boshqalarni to‘ldiring
    set -a; source .env; set +a

## Ishga tushirish
    python bot.py                                   # Telegram bot
    gunicorn -w 2 -b 127.0.0.1:8000 app:app         # veb (nginx orqali proxy qiling)

## systemd (doimiy ishlashi uchun) — /etc/systemd/system/autodoc-bot.service
    [Unit]
    Description=AutoDoc bot
    After=network.target
    [Service]
    WorkingDirectory=/opt/autodoc
    EnvironmentFile=/opt/autodoc/.env
    ExecStart=/opt/autodoc/venv/bin/python bot.py
    Restart=always
    [Install]
    WantedBy=multi-user.target

Veb uchun ham shunday, ExecStart=/opt/autodoc/venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 app:app

    sudo systemctl enable --now autodoc-bot

## To‘lov
Hozircha qo‘lda: foydalanuvchi to‘laydi → admin `/add <user_id> <soni>` yuboradi.
Keyin Click/Payme API ulash mumkin.
