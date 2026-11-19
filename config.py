import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
FREE_DOCS = int(os.getenv("FREE_DOCS", "1"))          # bepul hujjatlar soni
PRICE_TEXT = os.getenv("PRICE_TEXT", "1 hujjat — 5 000 so‘m")
PAY_INFO = os.getenv("PAY_INFO", "To‘lov: Click/Payme karta 8600 xxxx xxxx xxxx. Chekni @admin ga yuboring.")
DB_PATH = os.getenv("DB_PATH", "autodoc.db")
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "15"))
