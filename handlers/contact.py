"""
handlers/contact.py — Aloqa
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from config import RESTAURANT_NAME, CHANNEL_NAME, CHANNEL_LINK

router = Router()


@router.message(F.text == "☎️ Aloqa")
async def contact(message: Message, state: FSMContext):
    await state.clear()
    from database import get_setting, get_contact_phones
    phones = get_contact_phones()
    work_hours = get_setting("work_hours") or "09:00 - 23:00"
    address = get_setting("address") or "Toshkent sh."

    phones_text = "\n".join(f"📞 <b>{p}</b>" for p in phones) if phones else "📞 <b>+998 71 000 00 00</b>"
    channel_line = f"📢 Kanal: {CHANNEL_LINK}" if CHANNEL_LINK else ""

    await message.answer(
        f"☎️ <b>{RESTAURANT_NAME} — Aloqa</b>\n\n"
        f"{phones_text}\n"
        f"📍 Manzil: {address}\n"
        f"⏰ Ish vaqti: {work_hours}\n\n"
        f"{channel_line}",
        parse_mode="HTML"
    )
