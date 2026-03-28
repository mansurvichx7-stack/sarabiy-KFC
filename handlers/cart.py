"""
handlers/cart.py — Savat boshqaruvi
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import (
    get_cart, get_cart_total,
    cart_plus, cart_minus, cart_remove, clear_cart,
    get_product, check_spam
)
from config import SPAM_TIMEOUT
from keyboards.inline import cart_kb
from keyboards.reply import main_kb

router = Router()


def build_cart_text(items: list, total: int) -> str:
    lines = ["🛒 <b>Sizning savatingiz:</b>\n"]
    for item in items:
        unit = item["unit"] if "unit" in item.keys() else "dona"
        qty = item["quantity"]
        if unit == "kg":
            qty_str = f"{qty/10:.1f}".rstrip('0').rstrip('.')
            lines.append(f"• {item['name']} × {qty_str} kg = {item['subtotal']:,} so'm")
        else:
            lines.append(f"• {item['name']} × {qty} {unit} = {item['subtotal']:,} so'm")

    lines.append(f"\n💰 <b>Jami: {total:,} so'm</b>")
    max_prep = _get_max_prep_time(items)
    if max_prep:
        lines.append(f"⏱ <b>Taxminiy kutish: ~{max_prep}</b>")

    from config import MIN_ORDER_AMOUNT
    from database import get_setting
    try:
        db_min = get_setting("min_order")
        min_amt = int(db_min) if db_min else MIN_ORDER_AMOUNT
    except Exception:
        min_amt = MIN_ORDER_AMOUNT
    if min_amt and total < min_amt:
        lines.append(f"\n⚠️ Minimal buyurtma: <b>{min_amt:,} so'm</b>")
    return "\n".join(lines)


def _get_max_prep_time(items: list) -> str:
    from database import get_product, parse_prep_minutes
    max_minutes = 0
    max_text = ""
    for item in items:
        p = get_product(item["product_id"])
        if not p or not p["prep_time"]:
            continue
        minutes = parse_prep_minutes(p["prep_time"])
        if minutes > max_minutes:
            max_minutes = minutes
            max_text = p["prep_time"]
    return max_text


async def refresh_cart(target, user_id: int, edit: bool = False):
    items = get_cart(user_id)
    if not items:
        text = "🛒 <b>Savatingiz bo'sh</b>\n\n🍗 Menyudan mahsulot qo'shing!"
        if edit:
            try:
                await target.edit_text(text, parse_mode="HTML")
            except Exception:
                await target.answer(text, parse_mode="HTML")
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=main_kb())
        return

    total = get_cart_total(user_id)
    text = build_cart_text(items, total)
    kb = cart_kb(items)

    if edit:
        try:
            await target.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "🛒 Savat")
async def open_cart(message: Message, state: FSMContext):
    # Faqat pending (kechki) buyurtmani bekor qilamiz
    # waiting_payment (chek yuborilgan) ni BEKOR QILMAYMIZ
    current = await state.get_state()
    if current and current.startswith("OrderState"):
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id:
            from database import get_order, update_order_status
            o = get_order(order_id)
            if o and o["status"] == "pending":
                update_order_status(order_id, "cancelled")
    await state.clear()
    await refresh_cart(message, message.from_user.id, edit=False)


@router.callback_query(F.data.startswith("cplus:"))
async def cb_plus(callback: CallbackQuery):
    if check_spam(callback.from_user.id, 0.5):
        await callback.answer("⏳ Biroz kuting...")
        return
    pid = int(callback.data.split(":")[1])
    cart_plus(callback.from_user.id, pid)
    await refresh_cart(callback.message, callback.from_user.id, edit=True)
    await callback.answer("➕")


@router.callback_query(F.data.startswith("cminus:"))
async def cb_minus(callback: CallbackQuery):
    if check_spam(callback.from_user.id, 0.5):
        await callback.answer("⏳ Biroz kuting...")
        return
    pid = int(callback.data.split(":")[1])
    cart_minus(callback.from_user.id, pid)
    await refresh_cart(callback.message, callback.from_user.id, edit=True)
    await callback.answer("➖")


@router.callback_query(F.data.startswith("cremove:"))
async def cb_remove(callback: CallbackQuery):
    pid = int(callback.data.split(":")[1])
    p = get_product(pid)
    name = p["name"] if p else "Mahsulot"
    cart_remove(callback.from_user.id, pid)
    await refresh_cart(callback.message, callback.from_user.id, edit=True)
    await callback.answer(f"❌ {name} o'chirildi")


@router.callback_query(F.data == "cart:clear")
async def cb_clear(callback: CallbackQuery):
    clear_cart(callback.from_user.id)
    await callback.message.edit_text(
        "🗑 <b>Savat tozalandi!</b>\n\n🍗 Menyudan yangi mahsulotlar tanlang.",
        parse_mode="HTML"
    )
    await callback.answer("Savat tozalandi")
