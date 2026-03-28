"""
handlers/menu.py — Menyu, kategoriyalar, mahsulotlar
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    get_categories, get_products, get_product,
    add_to_cart, check_spam, get_setting
)
from config import SPAM_TIMEOUT, CHANNEL_LINK, CHANNEL_NAME
from keyboards.inline import categories_kb, products_kb, product_detail_kb

router = Router()


class CartAddState(StatesGroup):
    waiting_quantity = State()


def _is_work_time() -> bool:
    """Ish vaqtini DB dan tekshiradi (config dan emas)"""
    from datetime import datetime
    try:
        wh = get_setting("work_hours")
        if wh:
            parts = wh.replace(" ", "").split("-")
            ws = int(parts[0].split(":")[0])
            we = int(parts[1].split(":")[0])
        else:
            from config import WORK_START as ws, WORK_END as we
        if ws is None or we is None:
            return True
        h = datetime.now().hour
        if ws <= we:
            return ws <= h < we
        return h >= ws or h < we
    except Exception:
        return True


def _get_work_hours_text() -> str:
    try:
        wh = get_setting("work_hours")
        return wh or "09:00 - 23:00"
    except Exception:
        return "09:00 - 23:00"


@router.message(F.text == "🍗 Menyu")
async def show_menu(message: Message, state: FSMContext):
    # Faqat chek YUBORILMAGAN (DB ga yozilmagan) buyurtmalarni bekor qilamiz
    current = await state.get_state()
    if current and current.startswith("OrderState"):
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id:
            from database import get_order, update_order_status
            o = get_order(order_id)
            # FAQAT pending (kechki) buyurtmani bekor qilamiz
            # waiting_payment (chek yuborilgan) ni BEKOR QILMAYMIZ
            if o and o["status"] == "pending":
                update_order_status(order_id, "cancelled")
    await state.clear()

    is_work = _is_work_time()
    cats = get_categories(check_work_hours=True)

    if not is_work:
        if not cats:
            phones = _get_phones_text()
            wh = _get_work_hours_text()
            await message.answer(
                f"🌙 <b>Hozir ish vaqtimiz emas</b>\n"
                f"⏰ Ish vaqti: {wh}\n\n"
                f"Buyurtma uchun bog'laning:\n{phones}\n\n"
                f"Ertaga xizmatdamiz!",
                parse_mode="HTML"
            )
            return
        wh = _get_work_hours_text()
        text = (
            f"🌙 <b>Kechki menyu</b>\n"
            f"⏰ Ish vaqti: {wh}\n\n"
            f"Kategoriyani tanlang:"
        )
    else:
        if not cats:
            await message.answer("😔 Hozircha menyu bo'sh.\nAdmin tez orada to'ldiradi!")
            return
        text = "🍗 <b>Bizning menyumiz</b>\n\nKategoriyani tanlang:"

    await message.answer(text, parse_mode="HTML", reply_markup=categories_kb(cats))


def _get_phones_text() -> str:
    from database import get_contact_phones
    phones = get_contact_phones()
    if phones:
        return "\n".join(f"📞 <b>{p}</b>" for p in phones)
    return "📞 <b>+998 71 000 00 00</b>"


@router.callback_query(F.data.startswith("cat:"))
async def show_category(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    products = get_products(cat_id)

    if not products:
        await callback.answer("Bu kategoriyada mahsulot yo'q!", show_alert=True)
        return

    from database import get_category
    cat = get_category(cat_id)
    name = f"{cat['emoji']} {cat['name']}" if cat else "Mahsulotlar"
    text = f"<b>{name}</b>\n\nMahsulotni tanlang:"

    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=products_kb(products, cat_id)
        )
    except Exception:
        await callback.message.answer(
            text, parse_mode="HTML", reply_markup=products_kb(products, cat_id)
        )
    await callback.answer()


@router.callback_query(F.data == "back:cats")
async def back_to_cats(callback: CallbackQuery):
    # Ish vaqtini tekshirib to'g'ri kategoriyalarni ko'rsatamiz
    cats = get_categories(check_work_hours=True)
    is_work = _is_work_time()

    if not is_work and not cats:
        await callback.answer("Hozir ish vaqti emas!", show_alert=True)
        return

    text = "🍗 <b>Bizning menyumiz</b>\n\nKategoriyani tanlang:"
    if not is_work:
        wh = _get_work_hours_text()
        text = f"🌙 <b>Kechki menyu</b>\n⏰ {wh}\n\nKategoriyani tanlang:"

    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=categories_kb(cats)
        )
    except Exception:
        await callback.message.answer(
            text, parse_mode="HTML", reply_markup=categories_kb(cats)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:"))
async def show_product(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    product = get_product(product_id)

    if not product:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    unit = product["unit"] or "dona"
    prep_time = product["prep_time"] or "30 daqiqa"

    text = (
        f"<b>{product['name']}</b>\n\n"
        f"💰 Narx: <b>{product['price']:,} so'm / {unit}</b>\n"
        f"⏱ Tayyorlanish: <b>~{prep_time}</b>"
    )

    try:
        await callback.message.delete()
    except Exception:
        pass

    # Rasm yo'q bo'lsa matn ko'rsatamiz
    if product["photo_id"]:
        await callback.message.answer_photo(
            photo=product["photo_id"],
            caption=text,
            parse_mode="HTML",
            reply_markup=product_detail_kb(product_id, product["category_id"])
        )
    else:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=product_detail_kb(product_id, product["category_id"])
        )
    await callback.answer()


@router.callback_query(F.data.startswith("add:"))
async def add_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])
    product = get_product(product_id)
    if not product:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    if not product["is_active"]:
        from database import get_top_products
        tops = get_top_products(3)
        top_text = ""
        if tops:
            top_text = "\n\n🏆 <b>Mashhur taomlar:</b>\n" + "\n".join(
                f"• {p['name']} — {p['price']:,} so'm" for p in tops
            )
        await callback.message.answer(
            f"😔 <b>{product['name']}</b> hozircha mavjud emas.\n"
            f"Tez orada qayta tiklanadi!{top_text}",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    unit = product["unit"] or "dona"

    if unit == "kg":
        await state.set_state(CartAddState.waiting_quantity)
        await state.update_data(
            add_product_id=product_id,
            add_unit=unit,
            add_name=product["name"],
            add_price=product["price"]
        )
        await callback.message.answer(
            f"⚖️ <b>{product['name']}</b>\n\n"
            f"Necha kg kerak?\n"
            f"Misol: <code>0.5</code> · <code>1</code> · <code>1.5</code> · <code>2</code>",
            parse_mode="HTML"
        )
        await callback.answer()
    else:
        added = add_to_cart(callback.from_user.id, product_id)
        if added:
            await callback.answer(f"✅ {product['name']} savatga qo'shildi!")
        else:
            await callback.answer("⏳ Biroz kuting...", show_alert=False)


@router.message(CartAddState.waiting_quantity)
async def recv_quantity(message: Message, state: FSMContext):
    """kg miqdorini qabul qiladi"""
    import math
    text = message.text.strip().replace(",", ".")
    try:
        qty = float(text)
        if qty < 0.5 or qty > 50:
            raise ValueError
        
        nearest_qty = max(0.5, math.floor(qty * 2) / 2)
        is_exact = abs(qty - nearest_qty) < 0.001
        
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri miqdor!\n"
            "Minimum: <code>0.5</code> kg\n"
            "Misol: <code>0.5</code> · <code>1</code> · <code>1.5</code> · <code>2</code>",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    product_id = data.get("add_product_id")
    name = data.get("add_name")
    await state.clear()

    qty_int = int(nearest_qty * 10)

    from database import get_conn
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO cart (user_id, product_id, quantity) VALUES (?,?,?)
               ON CONFLICT(user_id, product_id) DO UPDATE SET quantity=quantity+?""",
            (message.from_user.id, product_id, qty_int, qty_int)
        )
        conn.commit()
    finally:
        conn.close()

    nearest_display = f"{int(nearest_qty)}" if nearest_qty == int(nearest_qty) else f"{nearest_qty}"
    if not is_exact:
        next_display = f"{int(nearest_qty + 0.5)}" if (nearest_qty + 0.5) == int(nearest_qty + 0.5) else f"{nearest_qty + 0.5}"
        await message.answer(
            f"⚖️ Bu mahsulot faqat 0.5 kg qadam bilan qo‘shiladi. {text} kg buyurtma berib bo‘lmaydi. Hozir savatga {nearest_display} kg qo‘shildi. Istasangiz, savatda uni {next_display} kg qilib oshirishingiz mumkin.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"✅ <b>{name}</b> — {nearest_display} kg savatga qo'shildi!\n\n"
            f"🛒 Savatni ko'rish uchun <b>Savat</b> tugmasini bosing.",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("noop:"))
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.message(F.text == "🏆 Top taomlar")
async def top_products(message: Message):
    from database import get_top_products
    tops = get_top_products(5)
    if not tops:
        await message.answer(
            "🏆 <b>Top taomlar</b>\n\n"
            "Hozircha ma'lumot yo'q.\n"
            "Birinchi buyurtmangizni bering! 😊",
            parse_mode="HTML"
        )
        return
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = ["🏆 <b>Eng mashhur taomlar:</b>\n"]
    for i, p in enumerate(tops):
        unit = p["unit"] if "unit" in p.keys() else "dona"
        lines.append(
            f"{medals[i]} <b>{p['name']}</b>\n"
            f"   💰 {p['price']:,} so'm/{unit}  |  📦 {p['order_count']} marta buyurtma"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")
