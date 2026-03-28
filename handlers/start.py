"""
handlers/start.py — /start, obuna tekshiruvi
"""

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, CHANNEL_ID, CHANNEL_LINK, CHANNEL_NAME, RESTAURANT_NAME
from database import register_user
from keyboards.reply import main_kb, admin_kb
from keyboards.inline import subscribe_kb

router = Router()


async def check_subscription(bot: Bot, user_id: int) -> bool:
    """Kanalga obuna tekshiradi"""
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return False


async def require_subscription(message_or_cb, bot: Bot, user_id: int) -> bool:
    """Obuna yo'q bo'lsa xabar yuboradi va False qaytaradi"""
    if not CHANNEL_ID:
        return True
    if await check_subscription(bot, user_id):
        return True

    text = (
        f"📢 <b>Botdan foydalanish uchun</b>\n"
        f"<b>{CHANNEL_NAME}</b> kanaliga obuna bo'ling!\n\n"
        f"Obuna bo'lgandan keyin ✅ <b>Tekshirish</b> tugmasini bosing:"
    )
    kb = subscribe_kb(CHANNEL_LINK)

    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
        await message_or_cb.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message_or_cb.answer(text, parse_mode="HTML", reply_markup=kb)
    return False


async def send_main_menu(message, user_id: int):
    if user_id in ADMIN_IDS:
        await message.answer(
            "👑 <b>Admin paneliga xush kelibsiz!</b>",
            parse_mode="HTML",
            reply_markup=admin_kb()
        )
    else:
        await message.answer(
            f"🍗 <b>{RESTAURANT_NAME}</b> ga xush kelibsiz!\n\n"
            f"Mazali taomlarimizni buyurtma qiling 😋",
            parse_mode="HTML",
            reply_markup=main_kb()
        )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = message.from_user
    register_user(user.id, user.full_name, user.username)

    if user.id in ADMIN_IDS:
        await send_main_menu(message, user.id)
        return

    # Vaqtincha obuna majburiy emas
    # if not await require_subscription(message, bot, user.id):
    #     return

    await send_main_menu(message, user.id)


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    if not await check_subscription(bot, user.id):
        await callback.answer(
            "❌ Siz hali obuna bo'lmadingiz!\nObuna bo'lib, qayta bosing.",
            show_alert=True
        )
        return
    await callback.message.delete()
    register_user(user.id, user.full_name, user.username)
    await send_main_menu(callback.message, user.id)
    await callback.answer()



