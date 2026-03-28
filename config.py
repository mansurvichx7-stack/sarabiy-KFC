"""
config.py — Bot sozlamalari
"""

# Telegram Bot tokeni (@BotFather dan olinadi)
BOT_TOKEN = "8427553547:AAHMLbF8f5y6zOa2LDhYnIYZ5lVUCXGlFRc"

# ══════════════════════════════════════════
# ADMINLAR
# Yangi admin qo'shish uchun ID ni ro'yxatga qo'shing:
# ADMIN_IDS = [111111111, 222222222, 333333333]
# Barcha buyurtmalar va xabarlar HAMMAGA yuboriladi
# ══════════════════════════════════════════
ADMIN_IDS = [971066267, 8381977336, 899657434]
ADMIN_ID = ADMIN_IDS[0]  # Xatolik xabarlari uchun (faqat texnik maqsadda)

# Majburiy kanal obuna
# MUHIM: Bot kanalda admin bo'lishi shart!
# Agar kerak bo'lmasa: CHANNEL_ID = None
CHANNEL_ID = "@sarabiykfc"
CHANNEL_LINK = "https://t.me/sarabiykfc"
CHANNEL_NAME = "Sarabiy KFC"

# To'lov kartasi
PAYMENT_CARD = "8600 0000 0000 0000"
CARD_OWNER = "FAMILIYA ISM"

# Restoran nomi
RESTAURANT_NAME = "Sarabiy KFC 🍗"

# Buyurtmani bekor qilish muddati (soniyada)
CANCEL_TIMEOUT = 300  # 5 daqiqa

# Spam himoya (soniyada)
SPAM_TIMEOUT = 3

# Minimal buyurtma narxi (so'mda). 0 = cheklov yo'q
MIN_ORDER_AMOUNT = 35000

# Ish vaqti (24 soat formatida). None = doim ochiq
WORK_START = 9   # 09:00
WORK_END   = 23  # 23:00
