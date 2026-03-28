"""
handlers/order.py — Buyurtma jarayoni (FSM)
"""

import re
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID, ADMIN_IDS, PAYMENT_CARD, CANCEL_TIMEOUT, CARD_OWNER
from database import (
    get_cart, get_cart_total, clear_cart,
    create_order, set_order_payment_photo,
    get_order, update_order_status, set_cancel_requested,
    get_product, increment_order_count, update_user_phones
)
from states import OrderState
from keyboards.reply import main_kb, location_kb, phone_kb
from keyboards.inline import (
    delivery_type_kb, delivery_pay_kb,
    admin_order_kb, my_orders_kb, order_detail_kb,
    admin_cancel_confirm_kb, STATUS_UZ, STATUS_EMOJI,
    night_delivery_kb, night_order_admin_kb, taxi_choice_kb
)

router = Router()

PHONE_RE = re.compile(r"^\+?[\d\s\-]{7,15}$")


async def send_to_admins(bot: Bot, text: str = None, photo: str = None,
                         caption: str = None, reply_markup=None, parse_mode: str = "HTML"):
    """Barcha adminlarga xabar yuboradi"""
    for admin_id in ADMIN_IDS:
        try:
            if photo:
                await bot.send_photo(chat_id=admin_id, photo=photo,
                                     caption=caption, parse_mode=parse_mode,
                                     reply_markup=reply_markup)
            else:
                await bot.send_message(chat_id=admin_id, text=text,
                                       parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception:
            pass


async def _try_use_saved_phones(user_id: int, state: FSMContext):
    """DB da saqlangan phone1 bo'lsa state ga yozadi, phone2 ni qayta so'raydi"""
    from database import get_user
    user = get_user(user_id)
    if user and user["phone1"]:
        await state.update_data(phone1=user["phone1"])
        await state.set_state(OrderState.waiting_phone2)
        return user
    return None


def clean_phone(p: str) -> str:
    return re.sub(r"[\s\-]", "", p)


# ══════════════════════════════════════════
# BUYURTMA BOSHLASH
# ══════════════════════════════════════════

@router.callback_query(F.data == "cart:checkout")
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    current_state = await state.get_state()
    if current_state and current_state.startswith("OrderState"):
        await callback.answer("⚠️ Buyurtma jarayoni allaqachon boshlangan!", show_alert=True)
        return

    items = get_cart(user_id)
    if not items:
        await callback.answer("❌ Savatingiz bo'sh!", show_alert=True)
        return

    total = get_cart_total(user_id)
    await state.update_data(cart_total=total)

    # Ish vaqtini tekshirish
    from datetime import datetime
    from database import get_setting as _gs
    from config import WORK_START as _ws, WORK_END as _we
    is_night = False
    try:
        row = _gs("work_hours")
        if row:
            parts = row.replace(" ", "").split("-")
            ws = int(parts[0].split(":")[0])
            we = int(parts[1].split(":")[0])
        else:
            ws, we = _ws, _we
        if ws is not None and we is not None:
            h = datetime.now().hour
            is_work = (ws <= h < we) if ws <= we else (h >= ws or h < we)
            is_night = not is_work
    except Exception:
        is_night = False

    await state.update_data(is_night=is_night)

    # Kechki rejimda faqat O'zi olib ketish
    if is_night:
        await state.set_state(OrderState.choosing_delivery)
        text = (
            f"🌙 <b>Kechki buyurtma</b>\n\n"
            f"Mahsulotlar: <b>{total:,} so'm</b>\n\n"
            f"⚠️ Kechasi faqat <b>O'zi olib ketish</b> mavjud.\n"
            f"Admin 15 daqiqa ichida tasdiqlaydi."
        )
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=night_delivery_kb())
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=night_delivery_kb())
    else:
        await state.set_state(OrderState.choosing_delivery)
        text = (
            f"📦 <b>Buyurtma berish</b>\n\n"
            f"Mahsulotlar: <b>{total:,} so'm</b>\n\n"
            f"Qanday olmoqchisiz?"
        )
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=delivery_type_kb())
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=delivery_type_kb())
    await callback.answer()


# ══════════════════════════════════════════
# YETKAZIB BERISH TURI
# ══════════════════════════════════════════

@router.callback_query(OrderState.choosing_delivery, F.data == "dlv:night")
async def dlv_night(callback: CallbackQuery, state: FSMContext):
    """Kechki buyurtma — O'zi olib ketish, naqd, 2 telefon"""
    await state.update_data(
        delivery_type="pickup",
        delivery_pay="cash",
        delivery_fee=0,
        address=None,
        latitude=None,
        longitude=None,
    )
    await state.set_state(OrderState.waiting_phone1)
    user = await _try_use_saved_phones(callback.from_user.id, state)
    if user:
        await callback.message.answer(
            f"✅ Telegram raqam saqlandi: <b>{user['phone1']}</b>\n\n"
            f"📱 <b>Shaxsiy telefon raqamingizni kiriting:</b>\n"
            f"(Misol: +998901234567)",
            parse_mode="HTML",
            reply_markup=main_kb()
        )
    else:
        await callback.message.answer(
            "📞 <b>Telegram raqamingizni yuboring:</b>",
            parse_mode="HTML",
            reply_markup=phone_kb()
        )
    await callback.answer()


@router.callback_query(OrderState.choosing_delivery, F.data == "dlv:courier")
async def dlv_courier(callback: CallbackQuery, state: FSMContext):
    await state.update_data(delivery_type="courier")
    await state.set_state(OrderState.choosing_delivery_pay)
    text = (
        "🚚 <b>Yetkazib berish</b>\n\n"
        "ℹ️ Buyurtmangizni taksi orqali yetkazib beramiz.\n"
        "📦 Biz mahsulot pulini taksidan ushlab olamiz.\n\n"
        "💳 <b>Qanday to'lamoqchisiz?</b>"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=delivery_pay_kb())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=delivery_pay_kb())
    await callback.answer()


@router.callback_query(OrderState.choosing_delivery, F.data == "dlv:pickup")
async def dlv_pickup(callback: CallbackQuery, state: FSMContext):
    await state.update_data(
        delivery_type="pickup",
        address=None, latitude=None, longitude=None, delivery_fee=0
    )
    await state.set_state(OrderState.choosing_delivery_pay)
    text = "💳 <b>Qanday to'lamoqchisiz?</b>"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=delivery_pay_kb())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=delivery_pay_kb())
    await callback.answer()


# ══════════════════════════════════════════
# TO'LOV TURI (faqat yetkazib berish uchun)
# ══════════════════════════════════════════

@router.callback_query(OrderState.choosing_delivery_pay, F.data == "dpay:back")
async def dpay_back(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.choosing_delivery)
    data = await state.get_data()
    total = data.get("cart_total", 0)
    if not total:
        from database import get_cart_total
        total = get_cart_total(callback.from_user.id)
        await state.update_data(cart_total=total)

    text = (
        f"📦 <b>Buyurtma berish</b>\n\n"
        f"Mahsulotlar: <b>{total:,} so'm</b>\n\n"
        f"Qanday olmoqchisiz?"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=delivery_type_kb())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=delivery_type_kb())
    await callback.answer()

@router.callback_query(OrderState.choosing_delivery_pay, F.data == "dpay:card")
async def dpay_card(callback: CallbackQuery, state: FSMContext):
    await state.update_data(delivery_pay="card", delivery_fee=0)
    data = await state.get_data()
    if data.get("delivery_type") == "pickup":
        await state.set_state(OrderState.waiting_phone1)
        user = await _try_use_saved_phones(callback.from_user.id, state)
        if user:
            await callback.message.answer(
                f"✅ Telegram raqam saqlandi: <b>{user['phone1']}</b>\n\n"
                f"📱 <b>Shaxsiy telefon raqamingizni kiriting:</b>\n"
                f"(Misol: +998901234567)",
                parse_mode="HTML",
                reply_markup=main_kb()
            )
        else:
            await callback.message.answer(
                "📞 <b>Telegram raqamingizni yuboring:</b>",
                parse_mode="HTML",
                reply_markup=phone_kb()
            )
    else:
        # Kuryer + karta — eslatma
        await state.set_state(OrderState.waiting_location)
        await callback.message.answer(
            "ℹ️ <b>Eslatma:</b>\n\n"
            "💳 Siz mahsulot narxini kartaga to'laysiz.\n"
            "🚚 Yetkazib berish taksi orqali amalga oshiriladi.\n"
            "💰 Taksi haqi — taksi haydovchisi bilan o'zingiz kelishasiz.\n\n"
            "📍 <b>Manzilingizni yuboring:</b>",
            parse_mode="HTML",
            reply_markup=location_kb()
        )
    await callback.answer()


@router.callback_query(OrderState.choosing_delivery_pay, F.data == "dpay:cash")
async def dpay_cash(callback: CallbackQuery, state: FSMContext):
    await state.update_data(delivery_pay="cash", delivery_fee=0)
    data = await state.get_data()
    if data.get("delivery_type") == "pickup":
        await state.set_state(OrderState.waiting_phone1)
        # DB da telefon saqlangan bo'lsa avtomatik o'tkazamiz
        user = await _try_use_saved_phones(callback.from_user.id, state)
        if user:
            await callback.message.answer(
                f"✅ Telegram raqam saqlandi: <b>{user['phone1']}</b>\n\n"
                f"📱 <b>Shaxsiy telefon raqamingizni kiriting:</b>\n"
                f"(Misol: +998901234567)",
                parse_mode="HTML",
                reply_markup=main_kb()
            )
        else:
            await callback.message.answer(
                "📞 <b>Telegram raqamingizni yuboring:</b>",
                parse_mode="HTML",
                reply_markup=phone_kb()
            )
    else:
        # Kuryer + naqd — taksi haqida ogohlantirish
        await state.set_state(OrderState.waiting_location)
        await callback.message.answer(
            "ℹ️ <b>Eslatma:</b>\n\n"
            "🚚 Yetkazib berish taksi orqali amalga oshiriladi.\n"
            "💰 Taksi haqi — taksi haydovchisi bilan o'zingiz kelishasiz.\n"
            "💵 Mahsulot narxini kuryerga naqd to'laysiz.\n\n"
            "📍 <b>Manzilingizni yuboring:</b>",
            parse_mode="HTML",
            reply_markup=location_kb()
        )
    await callback.answer()


# ══════════════════════════════════════════
# LOKATSIYA
# ══════════════════════════════════════════

@router.message(OrderState.waiting_location, F.location)
async def recv_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    await state.update_data(
        latitude=lat, longitude=lon,
        address=f"📍 {lat:.5f}, {lon:.5f}",
        delivery_fee=0
    )
    await state.set_state(OrderState.waiting_phone1)
    user = await _try_use_saved_phones(message.from_user.id, state)
    if user:
        await message.answer(
            f"✅ Manzil saqlandi!\n\n"
            f"✅ Telegram raqam saqlandi: <b>{user['phone1']}</b>\n\n"
            f"📱 <b>Shaxsiy telefon raqamingizni kiriting:</b>\n"
            f"(Misol: +998901234567)",
            parse_mode="HTML",
            reply_markup=main_kb()
        )
    else:
        await message.answer(
            "✅ Manzil saqlandi!\n\n"
            "📞 <b>Telegram raqamingizni yuboring:</b>",
            parse_mode="HTML",
            reply_markup=phone_kb()
        )


@router.message(OrderState.waiting_location, F.text == "⬅️ Ortga")
async def back_from_location(message: Message, state: FSMContext):
    await state.set_state(OrderState.choosing_delivery_pay)
    await message.answer(
        "💳 <b>Qanday to'lamoqchisiz?</b>",
        parse_mode="HTML",
        reply_markup=delivery_pay_kb()
    )


@router.message(OrderState.waiting_location)
async def invalid_location(message: Message):
    await message.answer(
        "❌ Iltimos faqat <b>lokatsiya</b> yuboring!",
        parse_mode="HTML",
        reply_markup=location_kb()
    )


# ══════════════════════════════════════════
# 1-TELEFON (TELEGRAM)
# ══════════════════════════════════════════

@router.message(OrderState.waiting_phone1, F.contact)
async def recv_phone1_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await state.update_data(phone1=phone)
    await state.set_state(OrderState.waiting_phone2)
    await message.answer(
        f"✅ 1-raqam saqlandi: <b>{phone}</b>\n\n"
        f"📱 <b>Shaxsiy telefon raqamingizni kiriting:</b>\n"
        f"(Misol: +998901234567)",
        parse_mode="HTML",
        reply_markup=main_kb()
    )


@router.message(OrderState.waiting_phone1, F.text == "⬅️ Ortga")
async def back_from_phone1(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("is_night"):
        await state.set_state(OrderState.choosing_delivery)
        await message.answer("🌙 Qanday olmoqchisiz?", reply_markup=night_delivery_kb())
    elif data.get("delivery_type") == "pickup":
        # Pickup — to'lov turiga qaytadi
        await state.set_state(OrderState.choosing_delivery_pay)
        await message.answer("💳 <b>Qanday to'lamoqchisiz?</b>", parse_mode="HTML", reply_markup=delivery_pay_kb())
    else:
        # Yetkazib berish — lokatsiyaga qaytadi
        await state.set_state(OrderState.waiting_location)
        await message.answer("📍 Lokatsiyangizni yuboring:", reply_markup=location_kb())

@router.message(OrderState.waiting_phone1)
async def invalid_phone1(message: Message):
    await message.answer(
        "❌ Iltimos tugma orqali <b>Telegram raqamingizni</b> yuboring!",
        parse_mode="HTML",
        reply_markup=phone_kb()
    )


# ══════════════════════════════════════════
# 2-TELEFON (SHAXSIY)
# ══════════════════════════════════════════

@router.message(OrderState.waiting_phone2, F.text)
async def recv_phone2(message: Message, state: FSMContext, bot: Bot):
    text = message.text.strip()

    # Ortga tugmasi
    if text == "⬅️ Ortga":
        await state.set_state(OrderState.waiting_phone1)
        await message.answer(
            "📞 <b>Telegram raqamingizni yuboring:</b>",
            parse_mode="HTML",
            reply_markup=phone_kb()
        )
        return

    cleaned = clean_phone(text)
    if not PHONE_RE.match(cleaned):
        await message.answer(
            "❌ Noto'g'ri raqam formati!\n"
            "Misol: <code>+998901234567</code>",
            parse_mode="HTML"
        )
        return

    await state.update_data(phone2=cleaned)
    await _proceed_to_payment(message, state, bot)


@router.message(OrderState.waiting_phone2)
async def invalid_phone2(message: Message):
    await message.answer(
        "📱 Shaxsiy raqamingizni yozing:\nMisol: <code>+998901234567</code>",
        parse_mode="HTML",
        reply_markup=main_kb()
    )


# ══════════════════════════════════════════
# TO'LOV BOSQICHI
# ══════════════════════════════════════════

async def _proceed_to_payment(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_id = message.from_user.id

    items = get_cart(user_id)
    if not items:
        await message.answer("❌ Savat bo'sh! Qaytadan boshlang.", reply_markup=main_kb())
        await state.clear()
        return

    cart_total = data.get("cart_total") or get_cart_total(user_id)
    delivery_type = data.get("delivery_type")
    delivery_pay = data.get("delivery_pay", "cash")
    phone1 = data.get("phone1", "")
    phone2 = data.get("phone2", "")

    def fmt_qty(item):
        unit = item["unit"] or "dona"
        qty = item["quantity"]
        if unit == "kg":
            qty_str = f"{qty/10:.1f}".rstrip('0').rstrip('.')
            return f"{item['name']} × {qty_str} kg = {item['subtotal']:,} so'm"
        return f"{item['name']} × {qty} {unit} = {item['subtotal']:,} so'm"

    items_text = "\n".join(fmt_qty(item) for item in items)

    # Minimal buyurtma tekshiruvi — DB dan (admin o'zgartirgan bo'lsa), yo'q bo'lsa config dan
    from config import MIN_ORDER_AMOUNT as _cfg_min
    from database import get_setting as _gs
    try:
        _db_min = _gs("min_order")
        _min = int(_db_min) if _db_min else _cfg_min
    except Exception:
        _min = _cfg_min
    if _min and cart_total < _min:
        await message.answer(
            f"❌ Minimal buyurtma narxi: <b>{_min:,} so'm</b>\n"
            f"Hozirgi jami: <b>{cart_total:,} so'm</b>\n\n"
            f"Iltimos, yana mahsulot qo'shing!",
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Buyurtmani DB ga saqlash
    night_order = data.get("is_night", False) and delivery_pay == "cash"
    order_status = "pending" if night_order else "waiting_payment"
    order_id = create_order(
        user_id=user_id,
        items_text=items_text,
        cart_total=cart_total,
        delivery_type=delivery_type,
        delivery_pay=delivery_pay,
        address=data.get("address"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        phone1=phone1,
        phone2=phone2,
        status=order_status
    )

    # Telefonlarni foydalanuvchi profiliga saqlash
    update_user_phones(user_id, phone1, phone2)

    # Mahsulotlar buyurtma sonini oshirish
    for item in items:
        increment_order_count(item["product_id"])

    await state.update_data(order_id=order_id)
    await state.set_state(OrderState.waiting_payment)

    clear_cart(user_id)

    delivery_label = "🚚 Yetkazib berish" if delivery_type == "courier" else "🏠 O'zi olib ketish"
    address_line = f"\n📍 Manzil: {data.get('address', '—')}" if data.get("address") else ""

    fee_line = ""
    if delivery_type == "courier":
        fee_line = "\nℹ️ Buyurtma taksi orqali yetkaziladi. Mahsulot pulini taksidan ushlab olamiz."

    # Naqd pul bo'lsa chek so'rash shart emas
    if delivery_pay == "cash":
        is_night = data.get("is_night", False)
        await state.clear()

        user = message.from_user
        uname = f"@{user.username}" if user.username else "—"

        if is_night:
            # ── KECHKI BUYURTMA ──────────────────────────
            summary = (
                f"🌙 <b>Kechki buyurtma #{order_id}</b>\n\n"
                f"🛒 <b>Tarkib:</b>\n{items_text}\n\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>Jami: {cart_total:,} so'm</b>\n"
                f"━━━━━━━━━━━━━━━━━\n\n"
                f"🏠 O'zi olib ketish\n"
                f"📞 {phone1}\n"
                f"📱 {phone2}\n\n"
                f"⏳ <b>Admin 15 daqiqa ichida tasdiqlaydi.</b>\n"
                f"Tasdiqlansa xabar beramiz!"
            )
            await message.answer(summary, parse_mode="HTML", reply_markup=main_kb())

            # Adminga — kim buyurtma berdi + 15 daqiqa ogohlantirish
            admin_text = (
                f"🌙 <b>KECHKI BUYURTMA #{order_id}</b>\n\n"
                f"👤 <b>{user.full_name}</b>\n"
                f"🆔 {uname} | ID: <code>{user.id}</code>\n"
                f"📞 Telegram: {phone1}\n"
                f"📱 Shaxsiy: {phone2}\n\n"
                f"🛒 <b>Tarkib:</b>\n{items_text}\n\n"
                f"💰 Jami: <b>{cart_total:,} so'm</b>\n"
                f"🏠 O'zi olib ketish | 💵 Naqd\n\n"
                f"⚠️ <b>15 daqiqa ichida javob bering!</b>\n"
                f"Aks holda avtomatik rad etiladi."
            )
            await send_to_admins(bot, text=admin_text,
                               reply_markup=night_order_admin_kb(order_id, user.id))
            asyncio.create_task(
                _auto_reject_night_order(bot, order_id, user.id, 15 * 60)
            )

        else:
            # ── ODDIY NAQD PUL BUYURTMA ──────────────────
            summary = (
                f"📋 <b>Buyurtma #{order_id}</b>\n\n"
                f"🛒 <b>Tarkib:</b>\n{items_text}\n\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"💰 Jami: <b>{cart_total:,} so'm</b>\n"
                f"━━━━━━━━━━━━━━━━━\n\n"
                f"📦 {delivery_label}{address_line}\n"
                f"📞 Telegram: {phone1}\n"
                f"📱 Shaxsiy: {phone2}\n\n"
                f"⏳ <b>Buyurtmangiz ko'rib chiqilmoqda.</b>\n"
                f"Admin tasdiqlasa xabar beramiz!"
            )
            await message.answer(summary, parse_mode="HTML", reply_markup=main_kb())

            admin_text = (
                f"🔔 <b>YANGI BUYURTMA #{order_id}</b>\n"
                f"💵 <b>TO'LOV: NAQD PUL</b>\n\n"
                f"👤 <b>{user.full_name}</b>\n"
                f"🆔 {uname} | ID: <code>{user.id}</code>\n"
                f"📞 Telegram: {phone1}\n"
                f"📱 Shaxsiy: {phone2}\n"
                f"📦 {delivery_label}{address_line}\n\n"
                f"🛒 <b>Tarkib:</b>\n{items_text}\n\n"
                f"💰 Jami: <b>{cart_total:,} so'm</b>\n"
                f"💵 To'lov: Naqd pul"
            )
            await send_to_admins(bot, text=admin_text,
                               reply_markup=admin_order_kb(order_id, "waiting_payment", delivery_type or "courier", "cash"))
            asyncio.create_task(_notify_no_response(bot, user.id, order_id, 15 * 60))
        return

    # Ish vaqti tekshiruvi — DB dan o'qiymiz (admin o'zgartirgan bo'lsa)
    from datetime import datetime
    from database import get_setting as _gs2
    now_hour = datetime.now().hour
    is_off_hours = False
    try:
        wh = _gs2("work_hours")
        if wh:
            parts_wh = wh.replace(" ", "").split("-")
            ws2 = int(parts_wh[0].split(":")[0])
            we2 = int(parts_wh[1].split(":")[0])
        else:
            from config import WORK_START as ws2, WORK_END as we2
        if ws2 is not None and we2 is not None:
            if ws2 <= we2:
                is_off_hours = not (ws2 <= now_hour < we2)
            else:
                is_off_hours = not (now_hour >= ws2 or now_hour < we2)
    except Exception:
        from config import WORK_START, WORK_END
        if WORK_START is not None and WORK_END is not None:
            if WORK_START <= WORK_END:
                is_off_hours = not (WORK_START <= now_hour < WORK_END)
            else:
                is_off_hours = not (now_hour >= WORK_START or now_hour < WORK_END)

    # Tayyorlanish vaqtini hisoblash
    from handlers.cart import _get_max_prep_time
    max_prep = _get_max_prep_time(items)

    prep_msg = f"\n⏱ Taxminiy tayyorlanish: <b>~{max_prep or '30 daqiqa'}</b>"
    work_msg = ""
    if is_off_hours:
        try:
            wh = _gs2("work_hours") or "09:00 - 23:00"
            work_msg = f"⚠️ Ish vaqtimiz: {wh}\nBuyurtmangiz ertaga ishlov beriladi.\n\n"
        except Exception:
            work_msg = "⚠️ Ish vaqtidan tashqari — ertaga ishlov beriladi.\n\n"

    await state.update_data(
        order_id=order_id,
        max_prep_time=max_prep or "30 daqiqa",
        is_off_hours=is_off_hours
    )
    await state.set_state(OrderState.waiting_payment)

    from database import get_setting as _gset
    card = _gset("payment_card") or PAYMENT_CARD
    card_owner = _gset("card_owner") or CARD_OWNER

    summary = (
        f"📋 <b>Buyurtma #{order_id}</b>\n\n"
        f"🛒 <b>Tarkib:</b>\n{items_text}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Jami: {cart_total:,} so'm</b>"
        f"{fee_line}"
        f"{prep_msg}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"📦 {delivery_label}{address_line}\n"
        f"📞 Telegram: {phone1}\n"
        f"📱 Shaxsiy: {phone2}\n\n"
        f"{work_msg}"
        f"💳 <b>To'lov:</b>\n"
        f"Karta: <code>{card}</code>\n"
        f"👤 Karta egasi: <b>{card_owner}</b>\n"
        f"Miqdor: <b>{cart_total:,} so'm</b>\n\n"
        f"📸 <b>To'lov cheki (screenshot) rasmini yuboring!</b>"
    )

    await message.answer(summary, parse_mode="HTML", reply_markup=main_kb())


# ══════════════════════════════════════════
# CHEK QABUL QILISH
# ══════════════════════════════════════════

@router.message(OrderState.waiting_payment, F.photo)
async def recv_payment_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")

    if not order_id:
        await message.answer("❌ Buyurtma topilmadi. Qaytadan boshlang.", reply_markup=main_kb())
        await state.clear()
        return

    photo_id = message.photo[-1].file_id
    set_order_payment_photo(order_id, photo_id)

    max_prep_time = data.get("max_prep_time", "30 daqiqa")
    is_off_hours = data.get("is_off_hours", False)

    await state.clear()

    if is_off_hours:
        await message.answer(
            f"⏳ <b>Chek qabul qilindi!</b>\n\n"
            f"Chekni tekshiryapmiz...\n"
            f"⚠️ Ish vaqtidan tashqari — ertaga ishlov beriladi.\n"
            f"Buyurtma <b>#{order_id}</b>",
            parse_mode="HTML",
            reply_markup=main_kb()
        )
    else:
        await message.answer(
            f"⏳ <b>Chek qabul qilindi!</b>\n\n"
            f"Admin chekni tekshirib tasdiqlaydi, 2 daqiqa kuting...\n"
            f"Tasdiqlangach xabar beramiz 🔔\n\n"
            f"Buyurtma <b>#{order_id}</b>",
            parse_mode="HTML",
            reply_markup=main_kb()
        )

    # Adminga yuborish
    order = get_order(order_id)
    user = message.from_user
    delivery_label = "🚚 Yetkazib berish" if order["delivery_type"] == "courier" else "🏠 O'zi olib ketish"
    address_line = f"\n📍 {order['address']}" if order["address"] else ""
    pay_line = ""
    if order["delivery_type"] == "courier":
        if order["delivery_pay"] == "card":
            pay_line = "\n💳 To'lov: <b>Karta (yetkazib berish narxi admin belgilaydi)</b>"
        elif order["delivery_pay"] == "cash":
            pay_line = "\n💵 To'lov: <b>Naqd pul (kuryerga)</b>"

    # Ish vaqtidan tashqarimi
    off_hours_line = ""
    if data.get("is_off_hours"):
        off_hours_line = "\n⚠️ <b>ISH VAQTIDAN TASHQARI BUYURTMA!</b>"

    admin_text = (
        f"🔔 <b>YANGI BUYURTMA #{order_id}</b>{off_hours_line}\n\n"
        f"👤 <b>{user.full_name}</b>\n"
        f"🆔 @{user.username or '—'} | ID: <code>{user.id}</code>\n"
        f"📞 Telegram: {order['phone1']}\n"
        f"📱 Shaxsiy: {order['phone2']}\n"
        f"📦 {delivery_label}{address_line}{pay_line}\n\n"
        f"🛒 <b>Tarkib:</b>\n{order['items_text']}\n\n"
        f"💰 Mahsulotlar: <b>{order['cart_total']:,} so'm</b>\n"
        f"📊 Holat: To'lov kutilmoqda"
    )

    await send_to_admins(
        bot,
        photo=photo_id,
        caption=admin_text,
        reply_markup=admin_order_kb(order_id, "waiting_payment", order["delivery_type"] or "courier")
    )

    # 5 daqiqadan keyin bekor qilish imkonini yopish
    asyncio.create_task(_close_cancel_option(bot, user.id, order_id, 300))

    # Ish vaqtida bo'lsa — 15 daqiqa javob yo'q bo'lsa foydalanuvchiga telefon raqam
    if not is_off_hours:
        asyncio.create_task(_notify_no_response(bot, user.id, order_id, 15 * 60))


async def _auto_reject_night_order(bot: Bot, order_id: int, user_id: int, delay: int):
    """15 daqiqadan keyin kechki buyurtmani avtomatik rad etadi"""
    await asyncio.sleep(delay)
    from database import get_order, update_order_status
    order = get_order(order_id)
    if not order or order["status"] != "pending":
        return  # Allaqachon tasdiqlangan yoki rad etilgan
    update_order_status(order_id, "cancelled")
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"❌ <b>Buyurtma #{order_id} rad etildi</b>\n\n"
                f"Kechirasiz, hozir buyurtma qabul qilinmaydi.\n"
                f"⏰ Ertaga ish vaqtida qayta urinib ko'ring!"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass


async def _notify_no_response(bot: Bot, user_id: int, order_id: int, delay: int):
    """Ish vaqtida 15 daqiqa javob yo'q bo'lsa foydalanuvchiga telefon raqamlarni yuboradi"""
    await asyncio.sleep(delay)
    order = get_order(order_id)
    # Faqat hali waiting_payment bo'lsa (javob berilmagan)
    if not order or order["status"] != "waiting_payment":
        return
    from database import get_contact_phones
    phones = get_contact_phones()
    if phones:
        phones_text = "\n".join(f"📞 <b>{p}</b>" for p in phones)
    else:
        phones_text = "📞 <b>+998 71 000 00 00</b>"
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"⏳ <b>Buyurtma #{order_id}</b>\n\n"
                f"Biroz noqulaylik bo'layapti, kechirasiz!\n"
                f"Tezroq buyurtma berish uchun quyidagi raqamlarga bog'laning:\n\n"
                f"{phones_text}"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass


async def _close_cancel_option(bot: Bot, user_id: int, order_id: int, delay: int):
    """5 daqiqadan keyin bekor qilish muddati tugaganligi haqida xabar"""
    await asyncio.sleep(delay)
    order = get_order(order_id)
    if order and order["status"] == "waiting_payment" and not order["cancel_requested"]:
        set_cancel_requested(order_id, -1)  # -1 = muddati o'tdi
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"⏰ Buyurtma <b>#{order_id}</b> uchun bekor qilish muddati tugadi.\n"
                     f"Endi buyurtmani bekor qilib bo'lmaydi.",
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.message(OrderState.waiting_payment)
async def invalid_payment(message: Message):
    await message.answer(
        "❌ Faqat <b>to'lov cheki rasmi (screenshot)</b> yuboring!",
        parse_mode="HTML"
    )


# ══════════════════════════════════════════
# BUYURTMALARIM
# ══════════════════════════════════════════

@router.message(F.text == "📦 Buyurtmalarim")
async def my_orders(message: Message, state: FSMContext):
    await state.clear()
    orders = get_user_orders(message.from_user.id)

    if not orders:
        await message.answer(
            "📭 <b>Buyurtmalaringiz yo'q</b>\n\nMenyudan biror narsa buyurtma qiling!",
            parse_mode="HTML"
        )
        return

    await message.answer(
        "📦 <b>Buyurtmalaringiz:</b>\n\nBatafsil ko'rish uchun bosing:",
        parse_mode="HTML",
        reply_markup=my_orders_kb(orders)
    )


def get_user_orders(user_id):
    from database import get_user_orders as _get
    return _get(user_id)


@router.callback_query(F.data.startswith("order:"))
async def show_order_detail(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    order = get_order(order_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    status = STATUS_EMOJI.get(order["status"], "📋")
    status_name = STATUS_UZ.get(order["status"], order["status"])
    delivery_label = "🚚 Yetkazib berish" if order["delivery_type"] == "courier" else "🏠 O'zi olib ketish"
    address_line = f"\n📍 {order['address']}" if order["address"] else ""
    fee_line = f"\n🚚 Yetkazib berish: {order['delivery_fee']:,} so'm" if order["delivery_fee"] else ""

    text = (
        f"📋 <b>Buyurtma #{order['id']}</b>\n"
        f"📅 {order['created_at']}\n\n"
        f"🛒 <b>Tarkib:</b>\n{order['items_text']}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 Mahsulotlar: {order['cart_total']:,} so'm"
        f"{fee_line}\n"
        f"<b>Jami: {order['total_price']:,} so'm</b>\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"📦 {delivery_label}{address_line}\n"
        f"📞 Telegram: {order['phone1']}\n"
        f"📱 Shaxsiy: {order['phone2']}\n\n"
        f"{status} <b>Holat: {status_name}</b>"
    )

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=order_detail_kb(order_id, order["status"], order["cancel_requested"], order["delivery_pay"] or "card")
        )
    except Exception:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=order_detail_kb(order_id, order["status"], order["cancel_requested"], order["delivery_pay"] or "card")
        )
    await callback.answer()


# ══════════════════════════════════════════
# TAKSI TANLOV — O'ZIM OLIB KETAMAN
# ══════════════════════════════════════════

@router.callback_query(F.data.startswith("taxi:"))
async def taxi_choice(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    action = parts[1]
    order_id = int(parts[2])
    order = get_order(order_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if action == "ok":
        await callback.answer("✅ Tushunarli!")
        try:
            await callback.message.delete()
        except Exception:
            pass

    elif action == "self":
        # Foydalanuvchi o'zi olib ketishga qaror qildi
        update_order_status(order_id, "preparing")  # preparing ga qaytamiz
        await callback.answer("✅ Tushunarli, kelishingizni kutamiz!")
        try:
            await callback.message.edit_text(
                f"🏠 <b>Buyurtma #{order_id}</b>\n\n"
                f"O'zingiz olib ketasiz. Tayyor bo'lgach xabar beramiz!",
                parse_mode="HTML"
            )
        except Exception:
            pass
        # Adminga xabar
        user = callback.from_user
        uname = f"@{user.username}" if user.username else "—"
        await send_to_admins(
            bot,
            text=(
                f"ℹ️ <b>Buyurtma #{order_id}</b>\n\n"
                f"👤 {user.full_name} | {uname}\n"
                f"Mijoz taksidan voz kechdi — <b>o'zi olib ketadi!</b>"
            ),
            reply_markup=admin_order_kb(order_id, "preparing", "pickup", order["delivery_pay"] or "card")
        )


@router.callback_query(F.data.startswith("repeat_order:"))
async def repeat_order(callback: CallbackQuery):
    """Oldingi buyurtmani savatchaga qayta qo'shish"""
    order_id = int(callback.data.split(":")[1])
    order = get_order(order_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    import re as _re
    from database import get_conn as _gc
    lines = order["items_text"].split("\n") if order["items_text"] else []
    added = 0
    conn = _gc()
    try:
        for line in lines:
            # Format: "Nomi × 1.5 kg = narx" yoki "Nomi × 2 dona = narx"
            m = _re.match(r"^(.+?) × ([\d.]+)\s*(\w+)", line)
            if not m:
                continue
            name = m.group(1).strip()
            qty_str = m.group(2)
            unit = m.group(3).strip()

            prod = conn.execute(
                "SELECT * FROM products WHERE name=? AND is_active=1 LIMIT 1",
                (name,)
            ).fetchone()
            if not prod:
                continue

            # Miqdorni hisoblash
            if unit == "kg":
                try:
                    import math
                    qty_float = float(qty_str)
                    qty_int = max(5, int(math.floor(qty_float * 2) / 2 * 10))
                except ValueError:
                    qty_int = 5  # default 0.5 kg
            else:
                try:
                    qty_int = max(1, int(float(qty_str)))
                except ValueError:
                    qty_int = 1

            conn.execute(
                """INSERT INTO cart (user_id, product_id, quantity) VALUES (?,?,?)
                   ON CONFLICT(user_id, product_id) DO UPDATE SET quantity=?""",
                (callback.from_user.id, prod["id"], qty_int, qty_int)
            )
            added += 1
        conn.commit()
    finally:
        conn.close()

    if added:
        await callback.answer(f"✅ {added} ta mahsulot savatga qo'shildi!")
        await callback.message.answer(
            f"🔄 <b>Buyurtma #{order_id} savatchaga qo'shildi!</b>\n\n"
            f"🛒 Savatni tekshiring va buyurtma bering.",
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Mahsulotlar topilmadi (o'chirilgan bo'lishi mumkin)", show_alert=True)


@router.callback_query(F.data.startswith("resend_check:"))
async def resend_check(callback: CallbackQuery, state: FSMContext):
    """Foydalanuvchi buyurtmalarim dan qayta chek yuborishi"""
    order_id = int(callback.data.split(":")[1])
    order = get_order(order_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return
    if order["status"] != "waiting_payment":
        await callback.answer("Bu buyurtma uchun chek kerak emas!", show_alert=True)
        return

    from config import PAYMENT_CARD, CARD_OWNER
    from database import get_setting
    card = get_setting("payment_card") or PAYMENT_CARD
    card_owner = get_setting("card_owner") or CARD_OWNER

    await state.update_data(order_id=order_id, max_prep_time="30 daqiqa")
    # Ish vaqtini tekshiramiz
    from handlers.menu import _is_work_time
    is_off = not _is_work_time()
    await state.update_data(is_off_hours=is_off)
    await state.set_state(OrderState.waiting_payment)
    await callback.message.answer(
        f"📸 <b>Buyurtma #{order_id} uchun chek yuboring:</b>\n\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Karta egasi: <b>{card_owner}</b>\n"
        f"💰 Miqdor: <b>{order['cart_total']:,} so'm</b>\n\n"
        f"To'lov cheki (screenshot) rasmini yuboring!",
        parse_mode="HTML",
        reply_markup=main_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "back:orders")
async def back_to_orders(callback: CallbackQuery):
    from database import get_user_orders as _get
    orders = _get(callback.from_user.id)
    text = "📦 <b>Buyurtmalaringiz:</b>"
    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=my_orders_kb(orders)
        )
    except Exception:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=my_orders_kb(orders)
        )
    await callback.answer()


# ══════════════════════════════════════════
# BUYURTMANI BEKOR QILISH SO'ROVI
# ══════════════════════════════════════════

@router.callback_query(F.data.startswith("cancel_req:"))
async def request_cancel(callback: CallbackQuery, bot: Bot):
    order_id = int(callback.data.split(":")[1])
    order = get_order(order_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if order["status"] != "waiting_payment":
        await callback.answer("❌ Bu buyurtmani bekor qilib bo'lmaydi!", show_alert=True)
        return

    if order["cancel_requested"] == -1:
        await callback.answer("⏰ Bekor qilish muddati o'tdi!", show_alert=True)
        return

    if order["cancel_requested"] == 1:
        await callback.answer("⚠️ So'rov allaqachon yuborilgan!", show_alert=True)
        return

    set_cancel_requested(order_id, 1)
    await callback.answer("So'rov yuborildi!")
    await callback.message.edit_reply_markup(
        reply_markup=order_detail_kb(order_id, order["status"], 1, order["delivery_pay"] or "card")
    )

    user = callback.from_user
    await send_to_admins(
        bot,
        text=(
            f"⚠️ <b>BEKOR QILISH SO'ROVI!</b>\n\n"
            f"Buyurtma: <b>#{order_id}</b>\n"
            f"👤 {user.full_name} | @{user.username or '—'}\n"
            f"💰 {order['total_price']:,} so'm\n\n"
            f"🛒 {order['items_text']}"
        ),
        reply_markup=admin_cancel_confirm_kb(order_id)
    )
