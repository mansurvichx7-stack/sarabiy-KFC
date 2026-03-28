"""
keyboards/reply.py — Reply klaviaturalar
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🍗 Menyu"),          KeyboardButton(text="🛒 Savat")],
        [KeyboardButton(text="📦 Buyurtmalarim"),  KeyboardButton(text="🏆 Top taomlar")],
        [KeyboardButton(text="☎️ Aloqa")],
    ], resize_keyboard=True)


def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📦 Buyurtmalar"),    KeyboardButton(text="🔍 Qidirish")],
        [KeyboardButton(text="📊 Statistika"),     KeyboardButton(text="👥 Foydalanuvchilar")],
        [KeyboardButton(text="🍽 Menyu"),           KeyboardButton(text="📢 Reklam")],
        [KeyboardButton(text="⚙️ Sozlamalar")],
    ], resize_keyboard=True)


def location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📍 Lokatsiyamni yuborish", request_location=True)],
        [KeyboardButton(text="⬅️ Ortga")],
    ], resize_keyboard=True)


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📞 Telegram raqamimni yuborish", request_contact=True)],
        [KeyboardButton(text="⬅️ Ortga")],
    ], resize_keyboard=True)


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
