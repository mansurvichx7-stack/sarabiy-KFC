"""
handlers/admin.py — Admin panel
"""

import asyncio

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Filter

from config import ADMIN_IDS, ADMIN_ID
from database import (
    get_order, update_order_status,
    set_cancel_requested, get_user, get_all_users, get_users_count,
    get_user_stats, get_all_categories, get_all_products,
    add_category, delete_category, update_category_name, toggle_always_open,
    add_product, delete_product,
    update_product_name, update_product_price, update_product_photo,
    update_product_unit, update_product_prep_time, toggle_product,
    get_product, get_categories, get_today_stats,
    save_rating, get_conn, get_setting, set_setting,
    get_contact_phones, set_contact_phones,
    get_available_months, get_monthly_stats, get_orders_by_month, delete_orders_by_month
)
from states import (
    AdminCategoryState, AdminEditCategoryState, AdminProductState, AdminEditProductState,
    AdminBroadcastState, AdminSearchState,
    AdminSettingsState
)
from keyboards.reply import admin_kb
from keyboards.inline import (
    admin_order_kb, admin_categories_kb, admin_products_kb,
    admin_edit_product_kb, admin_edit_category_kb, admin_select_category_kb,
    admin_user_kb, admin_delete_confirm_kb, unit_kb,
    admin_menu_kb, admin_settings_kb, night_order_admin_kb,
    settings_phones_kb, confirm_save_kb, confirm_phone_delete_kb,
    STATUS_UZ, STATUS_EMOJI, rating_kb
)

router = Router()

# Admin panel tugmalari ro'yxati — FSM da bosilsa state tozalanadi
ADMIN_BUTTONS = [
    "📦 Buyurtmalar", "📊 Statistika", "🍽 Menyu",
    "📢 Reklam", "👥 Foydalanuvchilar", "🔍 Qidirish",
    "⚙️ Sozlamalar"
]


class IsAdmin(Filter):
    async def __call__(self, event) -> bool:
        uid = getattr(getattr(event, "from_user", None), "id", None)
        return uid in ADMIN_IDS


# ══════════════════════════════════════════
# BUYURTMA HOLAT BOSHQARUVI
# ══════════════════════════════════════════

async def notify_user(bot: Bot, user_id: int, text: str):
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(IsAdmin(), F.data.startswith("adm:"))
async def admin_action(callback: CallbackQuery, bot: Bot, state: FSMContext):
    parts = callback.data.split(":")
    action = parts[1]
    order_id = int(parts[2])
    order = get_order(order_id)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi!", show_alert=True)
        return

    cur = order["status"]

    if action == "paid":
        if cur != "waiting_payment":
            await callback.answer("⚠️ Allaqachon qayta ishlangan!", show_alert=True)
            return
        update_order_status(order_id, "paid")
        fee_text = f"\n🚚 Yetkazib berish: {order['delivery_fee']:,} so'm" if order["delivery_fee"] else ""
        is_pickup = order["delivery_type"] == "pickup"
        is_cash = order["delivery_pay"] == "cash"

        if is_cash and is_pickup:
            await notify_user(bot, order["user_id"],
                f"✅ <b>Buyurtma #{order_id} qabul qilindi!</b>\n"
                f"💰 Jami: <b>{order['total_price']:,} so'm</b>\n\n"
                f"🏠 Tayyor bo'lgach xabar beramiz!"
            )
        elif is_cash and not is_pickup:
            await notify_user(bot, order["user_id"],
                f"✅ <b>Buyurtma #{order_id} qabul qilindi!</b>\n"
                f"💰 Jami: <b>{order['total_price']:,} so'm</b>\n\n"
                f"🚚 Tayyor bo'lgach kuryer jo'natamiz!"
            )
        elif is_pickup:
            await notify_user(bot, order["user_id"],
                f"✅ <b>Buyurtma #{order_id} tasdiqlandi!</b>\n"
                f"💰 Jami: <b>{order['total_price']:,} so'm</b>\n\n"
                f"🏠 Tayyor bo'lgach xabar beramiz!"
            )
        else:
            await notify_user(bot, order["user_id"],
                f"✅ <b>Buyurtma #{order_id} tasdiqlandi!</b>\n"
                f"💰 Mahsulotlar: {order['cart_total']:,} so'm{fee_text}\n"
                f"<b>Jami: {order['total_price']:,} so'm</b>\n\n"
                f"🚚 Tayyor bo'lgach kuryer jo'natamiz!"
            )

    elif action == "cancel":
        if cur in ("delivered", "cancelled"):
            await callback.answer("⚠️ Bekor qilib bo'lmaydi!", show_alert=True)
            return
        update_order_status(order_id, "cancelled")
        await notify_user(bot, order["user_id"],
            f"❌ <b>Buyurtma #{order_id} bekor qilindi.</b>\n\nMuammo bo'lsa, aloqa bo'limiga murojaat qiling."
        )

    elif action == "prep":
        if cur != "paid":
            await callback.answer("⚠️ Avval to'lovni tasdiqlang (✅ tugmasini bosing)!", show_alert=True)
            return
        update_order_status(order_id, "preparing")

        # Taxminiy tayyorlanish vaqtini hisoblash
        prep_note = ""
        try:
            import re as _re
            from database import parse_prep_minutes, get_conn as _gc3
            names = _re.findall(r'^(.+?) ×', order["items_text"], _re.MULTILINE)
            max_min = 0
            max_txt = ""
            conn = _gc3()
            for name in names:
                row = conn.execute(
                    "SELECT prep_time FROM products WHERE name=? LIMIT 1", (name.strip(),)
                ).fetchone()
                if row and row["prep_time"]:
                    mins = parse_prep_minutes(row["prep_time"])
                    if mins > max_min:
                        max_min = mins
                        max_txt = row["prep_time"]
            conn.close()
            if max_txt:
                prep_note = f"\n⏱ Taxminiy: ~{max_txt}"
        except Exception:
            pass

        if order["delivery_type"] == "pickup":
            await notify_user(bot, order["user_id"],
                f"✅ <b>Chek tasdiqlandi!</b>\n\n"
                f"👨‍🍳 Buyurtma #{order_id} tayyorlanmoqda!{prep_note}\n"
                f"Tayyor bo'lgach xabar beramiz 🏠"
            )
        else:
            await notify_user(bot, order["user_id"],
                f"✅ <b>Chek tasdiqlandi!</b>\n\n"
                f"👨‍🍳 Buyurtma #{order_id} tayyorlanmoqda!{prep_note}\n"
                f"Tayyor bo'lgach kuryer jo'natamiz 🚚"
            )

    elif action == "ready":
        if cur != "preparing":
            await callback.answer("⚠️ Avval tayyorlanmoqda bosing!", show_alert=True)
            return
        if order["delivery_type"] != "pickup":
            await callback.answer("⚠️ Bu buyurtma yetkazib berish orqali!", show_alert=True)
            return
        update_order_status(order_id, "delivered")
        is_cash = order["delivery_pay"] == "cash"
        pay_note = "💵 To'lovni kassaga naqd qiling." if is_cash else ""
        await notify_user(bot, order["user_id"],
            f"✅ <b>Buyurtma #{order_id} tayyor!</b>\n\n"
            f"🏠 Olib ketishingiz mumkin!\n"
            f"{pay_note}\n"
            f"Ishtahangiz chog' bo'lsin 😊"
        )
        try:
            await bot.send_message(
                chat_id=order["user_id"],
                text="⭐ <b>Xizmatimizni baholang:</b>",
                parse_mode="HTML",
                reply_markup=rating_kb(order_id)
            )
        except Exception:
            pass

    elif action == "way":
        if cur != "preparing":
            await callback.answer("⚠️ Buyurtma hali tayyorlanmagan!", show_alert=True)
            return
        update_order_status(order_id, "on_the_way")
        await notify_user(bot, order["user_id"],
            f"🚚 <b>Buyurtma #{order_id} yo'lda!</b>\n\n"
            f"Buyurtmangizni taksiga topshirdik.\n"
            f"💰 Yetkazib berish to'lovini taksi haydovchisi bilan "
            f"o'zingiz kelishib oling.\n\n"
            f"Ishtahangiz chog' bo'lsin! 😊"
        )
        try:
            await bot.send_message(
                chat_id=order["user_id"],
                text="⭐ <b>Xizmatimizni baholang:</b>",
                parse_mode="HTML",
                reply_markup=rating_kb(order_id)
            )
        except Exception:
            pass

    elif action == "cancelok":
        update_order_status(order_id, "cancelled")
        set_cancel_requested(order_id, 0)
        await notify_user(bot, order["user_id"],
            f"✅ <b>Buyurtma #{order_id} bekor qilindi.</b>"
        )
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ Bekor qilish tasdiqlandi",
                parse_mode="HTML"
            )
        except Exception:
            pass
        await callback.answer("Bekor qilindi")
        return

    elif action == "cancelnok":
        set_cancel_requested(order_id, 0)
        await notify_user(bot, order["user_id"],
            f"❌ <b>Buyurtma #{order_id} bekor qilinmadi.</b>\n\nEndi bekor qilib bo'lmaydi."
        )
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ Bekor qilish rad etildi",
                parse_mode="HTML"
            )
        except Exception:
            pass
        await callback.answer("Rad etildi")
        return

    new_order = get_order(order_id)
    new_status = new_order["status"]
    dlv_type = new_order["delivery_type"] or "courier"
    dpay_type = new_order["delivery_pay"] or "card"
    status_label = f"{STATUS_EMOJI.get(new_status, '')} {STATUS_UZ.get(new_status, new_status)}"

    # Bosilgan admin xabarini yangilaymiz
    try:
        await callback.message.edit_caption(
            callback.message.caption + f"\n\n📊 Yangi holat: <b>{status_label}</b>",
            parse_mode="HTML",
            reply_markup=admin_order_kb(order_id, new_status, dlv_type, dpay_type)
        )
    except Exception:
        try:
            await callback.message.edit_text(
                (callback.message.text or "") + f"\n\n📊 Yangi holat: <b>{status_label}</b>",
                parse_mode="HTML",
                reply_markup=admin_order_kb(order_id, new_status, dlv_type, dpay_type)
            )
        except Exception:
            pass

    # Boshqa adminlarga yangilangan status haqida xabar
    acted_by = callback.from_user.id
    acted_name = callback.from_user.full_name
    for other_admin_id in ADMIN_IDS:
        if other_admin_id == acted_by:
            continue
        try:
            await bot.send_message(
                chat_id=other_admin_id,
                text=(
                    f"ℹ️ <b>Buyurtma #{order_id}</b> yangilandi\n"
                    f"👤 {acted_name} tomonidan\n"
                    f"📊 Yangi holat: <b>{status_label}</b>"
                ),
                parse_mode="HTML",
                reply_markup=admin_order_kb(order_id, new_status, dlv_type, dpay_type)
            )
        except Exception:
            pass

    await callback.answer(f"✅ {status_label}")


# ══════════════════════════════════════════
# REYTING
# ══════════════════════════════════════════

@router.callback_query(F.data.startswith("rate:"))
async def recv_rating(callback: CallbackQuery):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    stars = int(parts[2])

    order = get_order(order_id)
    if order and order["rating"] > 0:
        await callback.answer("⭐ Siz allaqachon baho berdingiz!", show_alert=True)
        return

    save_rating(callback.from_user.id, order_id, stars)
    star_text = "⭐" * stars
    await callback.message.edit_text(
        f"✅ Bahoyingiz qabul qilindi!\n\n{star_text}\n\nRahmat! 🙏"
    )
    await callback.answer(f"{'⭐' * stars} Rahmat!")


# ══════════════════════════════════════════
# STATISTIKA
# ══════════════════════════════════════════

@router.message(IsAdmin(), F.text == "📊 Statistika")
async def admin_statistics(message: Message, state: FSMContext):
    await state.clear()
    stats = get_today_stats()

    top_text = ""
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(stats["top_products"]):
        top_text += f"\n{medals[i]} {p['name']} — {p['order_count']} ta"

    from database import get_users_count as _guc
    total_users = _guc()

    await message.answer(
        f"📊 <b>Bugungi statistika</b>\n\n"
        f"📦 Buyurtmalar: <b>{stats['order_count']} ta</b>\n"
        f"💰 Tushum: <b>{stats['total']:,} so'm</b>\n"
        f"⭐ O'rtacha reyting: <b>{stats['avg_rating']}</b>\n"
        f"👤 Yangi foydalanuvchilar: <b>{stats['new_users']} ta</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n\n"
        f"🏆 <b>Mashhur taomlar:</b>{top_text or chr(10)+'Ma`lumot yo`q'}",
        parse_mode="HTML"
    )


# ══════════════════════════════════════════
# MENYU BOSHQARUVI (ADMIN)
# ══════════════════════════════════════════

@router.message(IsAdmin(), F.text == "🍽 Menyu")
async def admin_menu(message: Message, state: FSMContext):
    await state.clear()
    cats = get_all_categories()
    prods = get_all_products()
    await message.answer(
        f"🍽 <b>Menyu boshqaruvi</b>\n\n"
        f"📂 Kategoriyalar: <b>{len(cats)} ta</b>\n"
        f"🍔 Mahsulotlar: <b>{len(prods)} ta</b>\n\n"
        f"Nima qilmoqchisiz?",
        parse_mode="HTML",
        reply_markup=admin_menu_kb()
    )


@router.callback_query(IsAdmin(), F.data.startswith("amenu:"))
async def admin_menu_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "cats":
        cats = get_all_categories()
        if not cats:
            await callback.message.answer("📭 Kategoriyalar yo'q.")
            await callback.answer()
            return
        await callback.message.answer(
            "🍽 <b>Kategoriyalar:</b>",
            parse_mode="HTML",
            reply_markup=admin_categories_kb(cats)
        )

    elif action == "prods":
        prods = get_all_products()
        if not prods:
            await callback.message.answer("📭 Mahsulotlar yo'q.")
            await callback.answer()
            return
        await callback.message.answer(
            "🍔 <b>Mahsulotlar:</b>",
            parse_mode="HTML",
            reply_markup=admin_products_kb(prods)
        )

    elif action == "addcat":
        await state.set_state(AdminCategoryState.waiting_name)
        await callback.message.answer(
            "➕ <b>Yangi kategoriya nomi:</b>\n\n"
            "<i>Bekor qilish uchun istalgan tugmani bosing</i>",
            parse_mode="HTML"
        )

    elif action == "addprod":
        cats = get_all_categories()
        if not cats:
            await callback.message.answer("❌ Avval kategoriya qo'shing!")
            await callback.answer()
            return
        await state.set_state(AdminProductState.waiting_category)
        await callback.message.answer(
            "🍔 <b>Kategoriyani tanlang:</b>",
            parse_mode="HTML",
            reply_markup=admin_select_category_kb(cats)
        )

    await callback.answer()


# ══════════════════════════════════════════
# KATEGORIYA QO'SHISH
# ══════════════════════════════════════════

@router.message(IsAdmin(), AdminCategoryState.waiting_name)
async def recv_category_name(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    name = message.text.strip()
    if not name or len(name) > 50:
        await message.answer("❌ Noto'g'ri nom! (1-50 belgi)")
        return
    await state.update_data(cat_name=name)
    await state.set_state(AdminCategoryState.waiting_emoji)
    await message.answer(
        "🎨 <b>Kategoriya emoji kiriting:</b>\n"
        "Misol: 🍗 yoki 🍔 yoki 🥗\n\n"
        "<i>Default: 🍽</i>",
        parse_mode="HTML"
    )


@router.message(IsAdmin(), AdminCategoryState.waiting_emoji)
async def recv_category_emoji(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    emoji = message.text.strip() or "🍽"
    data = await state.get_data()
    await state.clear()

    try:
        cat_id = add_category(data["cat_name"], emoji)
        await message.answer(
            f"✅ <b>Kategoriya qo'shildi!</b>\n\n"
            f"{emoji} <b>{data['cat_name']}</b>\n"
            f"🆔 ID: {cat_id}",
            parse_mode="HTML",
            reply_markup=admin_kb()
        )
    except Exception:
        await message.answer(
            "❌ Bu nom allaqachon mavjud! Boshqa nom kiriting.",
            reply_markup=admin_kb()
        )


@router.callback_query(IsAdmin(), F.data.startswith("editcat:"))
async def admin_edit_category(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    from database import get_category
    cat = get_category(cat_id)
    if not cat:
        await callback.answer("Kategoriya topilmadi!", show_alert=True)
        return
    always_open = bool(cat["always_open"]) if "always_open" in cat.keys() else False
    status = "🌙 Doim ochiq" if always_open else "☀️ Faqat ish vaqtida"
    await callback.message.answer(
        f"🍽 <b>{cat['emoji']} {cat['name']}</b>\n\n"
        f"Holat: {status}\n\n"
        f"Nima qilmoqchisiz?",
        parse_mode="HTML",
        reply_markup=admin_edit_category_kb(cat_id, always_open)
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("ec:toggle:"))
async def toggle_cat_always_open(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[2])
    new_val = toggle_always_open(cat_id)
    status = "🌙 Doim ochiq — ish vaqtidan tashqari ham ko'rinadi" if new_val else "☀️ Faqat ish vaqtida ko'rinadi"
    await callback.message.edit_text(
        f"✅ O'zgartirildi!\n\n{status}",
        parse_mode="HTML",
        reply_markup=admin_edit_category_kb(cat_id, new_val)
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("ec:name:"))
async def admin_edit_cat_name(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[2])
    await state.set_state(AdminEditCategoryState.waiting_name)
    await state.update_data(edit_cat_id=cat_id)
    await callback.message.answer(
        "✏️ Kategoriyaning yangi nomini kiriting:\n\n"
        "<i>Bekor qilish uchun istalgan tugmani bosing</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(IsAdmin(), AdminEditCategoryState.waiting_name)
async def recv_edit_cat_name(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    name = message.text.strip()
    if not name or len(name) > 50:
        await message.answer("❌ Noto'g'ri nom! (1-50 belgi)")
        return
    data = await state.get_data()
    cat_id = data.get("edit_cat_id")
    await state.update_data(pending_cat_name=name)
    await message.answer(
        f"💾 <b>Saqlaysizmi?</b>\n\nYangi nom: <b>{name}</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb(f"savecat:name:{cat_id}")
    )


@router.callback_query(IsAdmin(), F.data.startswith("delcat:"))
async def admin_delete_category(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    from database import get_category
    cat = get_category(cat_id)
    if not cat:
        await callback.answer("Kategoriya topilmadi!", show_alert=True)
        return
    await callback.message.answer(
        f"⚠️ <b>'{cat['name']}'</b> kategoriyasini o'chirmoqchimisiz?\n\n"
        f"❗ Uning barcha mahsulotlari ham o'chadi!",
        parse_mode="HTML",
        reply_markup=admin_delete_confirm_kb("cat", cat_id)
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("confirmdelete:"))
async def confirm_delete(callback: CallbackQuery):
    parts = callback.data.split(":")
    item_type = parts[1]
    item_id = int(parts[2])

    if item_type == "cat":
        from database import get_category
        cat = get_category(item_id)
        name = cat["name"] if cat else str(item_id)
        delete_category(item_id)
        await callback.message.edit_text(
            f"🔴 <b>'{name}'</b> kategoriyasi o'chirildi!\nUning barcha mahsulotlari ham o'chirildi.",
            parse_mode="HTML"
        )
        await callback.answer("O'chirildi!")

    elif item_type == "prod":
        p = get_product(item_id)
        name = p["name"] if p else str(item_id)
        delete_product(item_id)
        await callback.message.edit_text(
            f"🔴 <b>'{name}'</b> mahsuloti o'chirildi!",
            parse_mode="HTML"
        )
        await callback.answer("O'chirildi!")


@router.callback_query(IsAdmin(), F.data.startswith("canceldelete:"))
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("✅ O'chirish bekor qilindi.")
    await callback.answer("Bekor qilindi")


# ══════════════════════════════════════════
# MAHSULOT BOSHQARUVI
# ══════════════════════════════════════════

@router.callback_query(IsAdmin(), F.data.startswith("selcat:"))
async def recv_product_cat(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(AdminProductState.waiting_name)
    await callback.message.answer("✏️ <b>Mahsulot nomini kiriting:</b>", parse_mode="HTML")
    await callback.answer()


@router.message(IsAdmin(), AdminProductState.waiting_name)
async def recv_product_name(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    name = message.text.strip()
    if not name or len(name) > 100:
        await message.answer("❌ Noto'g'ri nom!")
        return
    await state.update_data(prod_name=name)
    await state.set_state(AdminProductState.waiting_price)
    await message.answer(
        "💰 <b>Narxini kiriting (so'mda):</b>\nMisol: <code>25000</code>",
        parse_mode="HTML"
    )


@router.message(IsAdmin(), AdminProductState.waiting_price)
async def recv_product_price(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri narx! Misol: <code>25000</code>", parse_mode="HTML")
        return
    await state.update_data(prod_price=price)
    await state.set_state(AdminProductState.waiting_unit)
    await message.answer(
        "🍽 <b>O'lchov birligini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=unit_kb()
    )


@router.callback_query(IsAdmin(), AdminProductState.waiting_unit, F.data.startswith("unit:"))
async def recv_product_unit(callback: CallbackQuery, state: FSMContext):
    unit = callback.data.split(":")[1]
    await state.update_data(prod_unit=unit)
    await state.set_state(AdminProductState.waiting_prep_time)
    await callback.message.answer(
        "⏱ <b>Tayyorlanish vaqtini kiriting:</b>\n\n"
        "Misol:\n"
        "• <code>15 daqiqa</code>\n"
        "• <code>1 soat</code>\n"
        "• <code>2 soat 30 daqiqa</code>\n"
        "• <code>1 kun</code>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(IsAdmin(), AdminProductState.waiting_prep_time)
async def recv_product_prep_time(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    prep_time = message.text.strip()
    if not prep_time or len(prep_time) > 50:
        await message.answer("❌ Noto'g'ri vaqt! Misol: <code>15 daqiqa</code>", parse_mode="HTML")
        return
    await state.update_data(prod_prep_time=prep_time)
    await state.set_state(AdminProductState.waiting_photo)
    await message.answer("🖼 <b>Mahsulot rasmini yuboring:</b>", parse_mode="HTML")


@router.message(IsAdmin(), AdminProductState.waiting_photo, F.photo)
async def recv_product_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    await state.update_data(prod_photo=photo_id)

    # Tasdiqlash so'rash
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Saqlash", callback_data="newprod:yes")
    builder.button(text="❌ Bekor qilish", callback_data="newprod:no")
    builder.adjust(2)

    unit = data.get("prod_unit", "dona")
    prep = data.get("prod_prep_time", "30 daqiqa")
    await message.answer_photo(
        photo=photo_id,
        caption=(
            f"📋 <b>Tekshirib ko'ring:</b>\n\n"
            f"📌 Nom: <b>{data['prod_name']}</b>\n"
            f"💰 Narx: <b>{data['prod_price']:,} so'm / {unit}</b>\n"
            f"⏱ Tayyorlanish: <b>{prep}</b>\n\n"
            f"Saqlaymi?"
        ),
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(IsAdmin(), F.data.startswith("newprod:"))
async def save_product_confirm(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    if action == "no":
        await state.clear()
        await callback.message.reply("❌ Mahsulot qo'shish bekor qilindi.")
        await callback.answer()
        return
    data = await state.get_data()
    await state.clear()
    prod_id = add_product(
        category_id=data["category_id"],
        name=data["prod_name"],
        price=data["prod_price"],
        photo_id=data["prod_photo"],
        unit=data.get("prod_unit", "dona"),
        prep_time=data.get("prod_prep_time", "30 daqiqa")
    )
    await callback.message.reply(
        f"✅ <b>Mahsulot qo'shildi!</b>\n\n"
        f"🆔 ID: {prod_id}\n"
        f"📌 {data['prod_name']}\n"
        f"💰 {data['prod_price']:,} so'm / {data.get('prod_unit', 'dona')}\n"
        f"⏱ {data.get('prod_prep_time', '30 daqiqa')}",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )
    await callback.answer()


@router.message(IsAdmin(), AdminProductState.waiting_photo)
async def invalid_product_photo(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    await message.answer("🖼 Iltimos faqat <b>rasm</b> yuboring!", parse_mode="HTML")


@router.callback_query(IsAdmin(), F.data.startswith("editp:"))
async def admin_edit_product(callback: CallbackQuery):
    prod_id = int(callback.data.split(":")[1])
    p = get_product(prod_id)
    if not p:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return
    status = "🟢 Faol" if p["is_active"] else "🔴 Yopiq"
    unit = p["unit"] or "dona"
    prep = p["prep_time"] or "—"
    await callback.message.answer(
        f"🍽 <b>{p['name']}</b>\n"
        f"💰 {p['price']:,} so'm / {unit}\n"
        f"⏱ Tayyorlanish: ~{prep}\n"
        f"📊 {status}\n\n"
        f"Nima o'zgartirmoqchisiz?",
        parse_mode="HTML",
        reply_markup=admin_edit_product_kb(prod_id, bool(p["is_active"]))
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("ep:"))
async def handle_edit_product(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    action = parts[1]
    prod_id = int(parts[2])

    if action == "toggle":
        new_status = toggle_product(prod_id)
        status_text = "🟢 Ochildi — endi menyuda ko'rinadi" if new_status else "🔴 Yopildi — menyuda ko'rinmaydi"
        await callback.message.answer(
            f"✅ <b>{status_text}</b>",
            parse_mode="HTML",
            reply_markup=admin_edit_product_kb(prod_id, new_status)
        )
        await callback.answer("O'zgartirildi!")
        return

    if action == "delete":
        p = get_product(prod_id)
        name = p["name"] if p else str(prod_id)
        await callback.message.answer(
            f"⚠️ <b>'{name}'</b> mahsulotini o'chirmoqchimisiz?",
            parse_mode="HTML",
            reply_markup=admin_delete_confirm_kb("prod", prod_id)
        )
        await callback.answer()
        return

    await state.update_data(edit_prod_id=prod_id)
    if action == "name":
        await state.set_state(AdminEditProductState.waiting_name)
        await callback.message.answer("✏️ Yangi nomini kiriting:")
    elif action == "price":
        await state.set_state(AdminEditProductState.waiting_price)
        await callback.message.answer("💰 Yangi narxini kiriting:")
    elif action == "unit":
        await state.set_state(AdminEditProductState.waiting_unit)
        await callback.message.answer("🍽 Yangi o'lchov birligini tanlang:", reply_markup=unit_kb())
    elif action == "prep":
        await state.set_state(AdminEditProductState.waiting_prep_time)
        await callback.message.answer(
            "⏱ Yangi tayyorlanish vaqtini kiriting:\nMisol: <code>20 daqiqa</code>",
            parse_mode="HTML"
        )
    elif action == "photo":
        await state.set_state(AdminEditProductState.waiting_photo)
        await callback.message.answer("🖼 Yangi rasmini yuboring:")
    await callback.answer()


@router.message(IsAdmin(), AdminEditProductState.waiting_name)
async def edit_prod_name(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    name = message.text.strip()
    data = await state.get_data()
    prod_id = data["edit_prod_id"]
    await state.update_data(pending_value=name)
    await message.answer(
        f"💾 <b>Saqlaysizmi?</b>\n\nYangi nom: <b>{name}</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb(f"saveprod:name:{prod_id}")
    )


@router.message(IsAdmin(), AdminEditProductState.waiting_price)
async def edit_prod_price(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Noto'g'ri narx!")
        return
    data = await state.get_data()
    prod_id = data["edit_prod_id"]
    await state.update_data(pending_value=price)
    await message.answer(
        f"💾 <b>Saqlaysizmi?</b>\n\nYangi narx: <b>{price:,} so'm</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb(f"saveprod:price:{prod_id}")
    )


@router.message(IsAdmin(), AdminEditProductState.waiting_photo, F.photo)
async def edit_prod_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    prod_id = data["edit_prod_id"]
    photo_id = message.photo[-1].file_id
    await state.update_data(pending_value=photo_id)
    await message.answer_photo(
        photo=photo_id,
        caption="💾 <b>Ushbu rasmni saqlaysizmi?</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb(f"saveprod:photo:{prod_id}")
    )


@router.message(IsAdmin(), AdminEditProductState.waiting_photo)
async def edit_prod_photo_invalid(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    await message.answer("🖼 Iltimos faqat rasm yuboring!")


@router.callback_query(IsAdmin(), AdminEditProductState.waiting_unit, F.data.startswith("unit:"))
async def edit_prod_unit(callback: CallbackQuery, state: FSMContext):
    unit = callback.data.split(":")[1]
    data = await state.get_data()
    prod_id = data["edit_prod_id"]
    await state.update_data(pending_value=unit)
    unit_names = {"dona": "Dona 🍽", "kg": "Kilogramm ⚖️", "porsiya": "Porsiya 🥣"}
    await callback.message.answer(
        f"💾 <b>Saqlaysizmi?</b>\n\nYangi birlik: <b>{unit_names.get(unit, unit)}</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb(f"saveprod:unit:{prod_id}")
    )
    await callback.answer()


@router.message(IsAdmin(), AdminEditProductState.waiting_prep_time)
async def edit_prod_prep_time(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    prep_time = message.text.strip()
    data = await state.get_data()
    prod_id = data["edit_prod_id"]
    await state.update_data(pending_value=prep_time)
    await message.answer(
        f"💾 <b>Saqlaysizmi?</b>\n\nYangi vaqt: <b>{prep_time}</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb(f"saveprod:prep:{prod_id}")
    )


# ══════════════════════════════════════════
# FOYDALANUVCHILAR
# ══════════════════════════════════════════

@router.message(IsAdmin(), F.text == "👥 Foydalanuvchilar")
async def admin_users(message: Message, state: FSMContext):
    await state.clear()
    users = get_all_users()
    if not users:
        await message.answer("📭 Foydalanuvchilar yo'q.")
        return
    await _send_users_page(message, users, page=0)


async def _send_users_page(message, users: list, page: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    per_page = 10
    total = len(users)
    start = page * per_page
    end = min(start + per_page, total)
    page_users = users[start:end]

    lines = [f"👥 <b>Foydalanuvchilar: {total} ta</b> (sahifa {page+1}/{max(1,(total-1)//per_page+1)})\n"]
    for i, u in enumerate(page_users, start+1):
        uname = f"@{u['username']}" if u["username"] else "—"
        phone = u["phone1"] or "—"
        lines.append(
            f"{i}. 👤 <b>{u['full_name']}</b> | {uname}\n"
            f"    📞 {phone} | 📅 {u['created_at'][:10]}"
        )

    builder = InlineKeyboardBuilder()
    for u in page_users:
        uname = f"@{u['username']}" if u["username"] else u["full_name"]
        builder.button(
            text=f"👤 {u['full_name']} | {uname}",
            callback_data=f"viewuser:{u['telegram_id']}"
        )
    builder.adjust(1)

    if page > 0:
        builder.button(text="⬅️ Oldingi", callback_data=f"userspage:{page-1}")
    if end < total:
        builder.button(text="Keyingi ➡️", callback_data=f"userspage:{page+1}")
    if page > 0 or end < total:
        builder.adjust(*([1] * len(page_users)), 2 if (page > 0 and end < total) else 1)

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(IsAdmin(), F.data.startswith("userspage:"))
async def users_page_cb(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    users = get_all_users()
    await callback.message.delete()
    await _send_users_page(callback.message, users, page)
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("viewuser:"))
async def view_user_cb(callback: CallbackQuery):
    tid = int(callback.data.split(":")[1])
    await _show_user_profile(callback.message, tid)
    await callback.answer()


@router.message(IsAdmin(), F.text.regexp(r"^/user_(\d+)$"))
async def admin_user_profile(message: Message):
    import re
    m = re.match(r"^/user_(\d+)$", message.text)
    if not m:
        return
    tid = int(m.group(1))
    await _show_user_profile(message, tid)


async def _show_user_profile(message, tid: int):
    user = get_user(tid)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi!")
        return

    stats = get_user_stats(tid)
    last_orders_text = ""
    for o in stats["last_orders"]:
        s = STATUS_EMOJI.get(o["status"], "")
        items_short = o["items_text"].split("\n")[0] if o["items_text"] else "—"
        if len(items_short) > 25:
            items_short = items_short[:25] + "..."
        last_orders_text += f"\n  {s} #{o['id']} — {items_short} | {o['total_price']:,} so'm"

    uname = f"@{user['username']}" if user["username"] else "—"

    await message.answer(
        f"👤 <b>{user['full_name']}</b>\n"
        f"🆔 <code>{tid}</code> | {uname}\n"
        f"🔗 <a href='tg://user?id={tid}'>Profilni ochish</a>\n\n"
        f"📞 Telegram: {user['phone1'] or '—'}\n"
        f"📱 Shaxsiy: {user['phone2'] or '—'}\n\n"
        f"📅 Ro'yxatdan: {user['created_at']}\n"
        f"🕐 Oxirgi faollik: {user['last_active']}\n\n"
        f"📦 Buyurtmalar: <b>{stats['order_count']} ta</b>\n"
        f"💰 Jami sarflagan: <b>{stats['total_spent']:,} so'm</b>\n"
        f"⭐ O'rtacha reyting: <b>{stats['avg_rating']}</b>\n\n"
        f"📋 Oxirgi buyurtmalar:{last_orders_text if last_orders_text else ' yo`q'}",
        parse_mode="HTML",
        reply_markup=admin_user_kb(tid)
    )



# ══════════════════════════════════════════
# REKLAM YUBORISH
# ══════════════════════════════════════════

@router.message(IsAdmin(), F.text == "📢 Reklam")
async def admin_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AdminBroadcastState.waiting_content)
    await message.answer(
        "📢 <b>Reklam xabarini yuboring:</b>\n\n"
        "Rasm, video yoki matn yuboring.\n"
        "Bu barcha foydalanuvchilarga yuboriladi!\n\n"
        "<i>Bekor qilish uchun istalgan tugmani bosing</i>",
        parse_mode="HTML"
    )


@router.message(IsAdmin(), AdminBroadcastState.waiting_content)
async def recv_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.text and message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Reklam bekor qilindi.", reply_markup=admin_kb())
        return

    await state.clear()
    users = get_all_users()
    sent = 0
    failed_users = []
    await message.answer(f"📤 Yuborilmoqda... ({len(users)} ta foydalanuvchi)")

    for user in users:
        try:
            if message.photo:
                await bot.send_photo(
                    user["telegram_id"],
                    message.photo[-1].file_id,
                    caption=message.caption or "",
                    parse_mode="HTML"
                )
            elif message.video:
                await bot.send_video(
                    user["telegram_id"],
                    message.video.file_id,
                    caption=message.caption or "",
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    user["telegram_id"],
                    message.text,
                    parse_mode="HTML"
                )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed_users.append(user)

    result = (
        f"✅ <b>Reklam yuborildi!</b>\n\n"
        f"📨 Jami: {len(users)} ta\n"
        f"✅ Yetdi: {sent} ta\n"
        f"❌ Yetmadi: {len(failed_users)} ta"
    )
    if failed_users:
        result += " (botni bloklagan):\n"
        for u in failed_users:
            uname = f"@{u['username']}" if u["username"] else "—"
            phone = u["phone1"] or "—"
            result += f"\n• <b>{u['full_name']}</b> | {uname} | {phone}"

    await message.answer(result, parse_mode="HTML", reply_markup=admin_kb())


# ══════════════════════════════════════════
# BUYURTMA QIDIRISH
# ══════════════════════════════════════════

@router.message(IsAdmin(), F.text == "🔍 Qidirish")
async def admin_search(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AdminSearchState.waiting_order_id)
    await message.answer(
        "🔍 Buyurtma ID ni kiriting:\n\n<i>Bekor qilish uchun istalgan tugmani bosing</i>",
        parse_mode="HTML"
    )


@router.message(IsAdmin(), AdminSearchState.waiting_order_id)
async def recv_search_id(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return

    await state.clear()
    try:
        order_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat son kiriting!")
        return

    order = get_order(order_id)
    if not order:
        await message.answer(f"❌ Buyurtma #{order_id} topilmadi!")
        return

    user = get_user(order["user_id"])
    uname = f"@{user['username']}" if user and user["username"] else "—"
    status = f"{STATUS_EMOJI.get(order['status'], '')} {STATUS_UZ.get(order['status'], order['status'])}"
    dlv = "🚚 Yetkazib berish" if order["delivery_type"] == "courier" else "🏠 O'zi olib ketish"
    adr = f"\n📍 {order['address']}" if order["address"] else ""

    await message.answer(
        f"📋 <b>Buyurtma #{order_id}</b>\n\n"
        f"👤 {user['full_name'] if user else '—'} | {uname}\n"
        f"📞 {order['phone1']} / {order['phone2']}\n"
        f"📦 {dlv}{adr}\n\n"
        f"🛒 {order['items_text']}\n\n"
        f"💰 {order['total_price']:,} so'm\n"
        f"📅 {order['created_at']}\n"
        f"📊 {status}",
        parse_mode="HTML",
        reply_markup=admin_order_kb(order_id, order["status"], order["delivery_type"] or "courier", order["delivery_pay"] or "card")
    )


@router.message(IsAdmin(), F.text == "⚙️ Sozlamalar")
async def admin_settings(message: Message, state: FSMContext):
    await state.clear()
    from config import WORK_START, WORK_END, MIN_ORDER_AMOUNT, PAYMENT_CARD, CARD_OWNER

    work_hours  = get_setting("work_hours")  or f"{WORK_START:02d}:00 - {WORK_END:02d}:00"
    min_order   = get_setting("min_order")   or str(MIN_ORDER_AMOUNT)
    card        = get_setting("payment_card") or PAYMENT_CARD
    card_owner  = get_setting("card_owner")  or CARD_OWNER
    address     = get_setting("address")     or "Toshkent sh."
    phones      = get_contact_phones()
    phones_text = "\n".join(f"  • {p}" for p in phones) if phones else "  —"

    from keyboards.inline import admin_settings_kb
    await message.answer(
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"⏰ Ish vaqti: <b>{work_hours}</b>\n"
        f"💰 Minimal buyurtma: <b>{int(min_order):,} so'm</b>\n\n"
        f"📞 Telefon raqamlar:\n{phones_text}\n\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Karta egasi: <b>{card_owner}</b>\n\n"
        f"📍 Manzil: <b>{address}</b>",
        parse_mode="HTML",
        reply_markup=admin_settings_kb()
    )


@router.callback_query(IsAdmin(), F.data.startswith("settings:"))
async def settings_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "work_hours":
        work_hours = get_setting("work_hours") or "09:00 - 23:00"
        await state.set_state(AdminSettingsState.waiting_work_start)
        await callback.message.answer(
            f"⏰ <b>Ish vaqtini kiriting:</b>\n\n"
            f"Hozirgi: <b>{work_hours}</b>\n\n"
            f"Misol: <code>9-23</code> yoki <code>9 23</code> yoki <code>09:00-23:00</code>",
            parse_mode="HTML"
        )

    elif action == "min_order":
        await state.set_state(AdminSettingsState.waiting_min_order)
        await callback.message.answer(
            "💰 <b>Minimal buyurtma narxini kiriting (so'mda):</b>\n"
            "Misol: <code>20000</code>\n"
            "<code>0</code> — cheklov yo'q",
            parse_mode="HTML"
        )

    elif action == "phones":
        phones = get_contact_phones()
        phones_text = "\n".join(f"• {p}" for p in phones) if phones else "Hozircha yo'q"
        await callback.message.answer(
            f"📞 <b>Telefon raqamlar:</b>\n\n{phones_text}",
            parse_mode="HTML",
            reply_markup=settings_phones_kb(phones)
        )

    elif action == "card":
        from config import PAYMENT_CARD, CARD_OWNER
        card = get_setting("payment_card") or PAYMENT_CARD
        owner = get_setting("card_owner") or CARD_OWNER
        await state.set_state(AdminSettingsState.waiting_card)
        await callback.message.answer(
            f"💳 <b>Hozirgi karta:</b>\n"
            f"<code>{card}</code>\n"
            f"👤 Egasi: <b>{owner}</b>\n\n"
            f"Yangi karta raqamini kiriting:\n"
            f"Misol: <code>8600 1234 5678 9012</code>",
            parse_mode="HTML"
        )

    elif action == "address":
        address = get_setting("address") or "Toshkent sh."
        await state.set_state(AdminSettingsState.waiting_address)
        await callback.message.answer(
            f"📍 <b>Hozirgi manzil:</b> {address}\n\n"
            f"Yangi manzilni kiriting:",
            parse_mode="HTML"
        )

    elif action == "phone":
        phones = get_contact_phones()
        await callback.message.answer(
            f"📞 <b>Telefon raqamlar:</b>",
            parse_mode="HTML",
            reply_markup=settings_phones_kb(phones)
        )

    await callback.answer()


# ══════════════════════════════════════════
# TELEFON O'CHIRISH / TAHRIRLASH TASDIQLARI
# ══════════════════════════════════════════

@router.callback_query(IsAdmin(), F.data.startswith("sphone:editok:"))
async def phone_edit_confirmed(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[2])
    data = await state.get_data()
    new_phone = data.get("pending_edit_phone", "")
    await state.clear()
    phones = get_contact_phones()
    if idx < len(phones):
        old = phones[idx]
        phones[idx] = new_phone
        set_contact_phones(phones)
        await callback.answer("✅ Saqlandi!")
        try:
            await callback.message.edit_text(
                f"✅ <b>Raqam yangilandi!</b>\n\nEski: {old}\nYangi: <b>{new_phone}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        await callback.answer("Raqam topilmadi!", show_alert=True)


@router.callback_query(IsAdmin(), F.data.startswith("sphone:delok:"))
async def phone_delete_confirmed(callback: CallbackQuery):
    idx = int(callback.data.split(":")[2])
    phones = get_contact_phones()
    if idx < len(phones):
        deleted = phones.pop(idx)
        set_contact_phones(phones)
        await callback.answer(f"🗑 O'chirildi!")
        new_phones = get_contact_phones()
        phones_text = "\n".join(f"• {p}" for p in new_phones) if new_phones else "Hozircha yo'q"
        try:
            await callback.message.edit_text(
                f"✅ <b>{deleted}</b> o'chirildi.\n\n"
                f"📞 <b>Telefon raqamlar:</b>\n{phones_text}",
                parse_mode="HTML",
                reply_markup=settings_phones_kb(new_phones)
            )
        except Exception:
            pass
    else:
        await callback.answer("Raqam topilmadi!", show_alert=True)


@router.callback_query(IsAdmin(), F.data == "sphone:delcancel")
async def phone_delete_cancelled(callback: CallbackQuery):
    await callback.answer("Bekor qilindi")
    try:
        await callback.message.delete()
    except Exception:
        pass


# ══════════════════════════════════════════
# TELEFON RAQAMLAR BOSHQARUVI
# ══════════════════════════════════════════

@router.callback_query(IsAdmin(), F.data.startswith("sphone:"))
async def settings_phone_action(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    action = parts[1]
    phones = get_contact_phones()

    if action == "add":
        await state.set_state(AdminSettingsState.waiting_phone)
        await callback.message.answer(
            "➕ <b>Yangi telefon raqam kiriting:</b>\n"
            "Misol: <code>+998901234567</code>",
            parse_mode="HTML"
        )

    elif action == "edit":
        idx = int(parts[2])
        if idx >= len(phones):
            await callback.answer("Raqam topilmadi!", show_alert=True)
            return
        await state.set_state(AdminSettingsState.waiting_edit_phone)
        await state.update_data(edit_phone_idx=idx)
        await callback.message.answer(
            f"✏️ <b>Hozirgi raqam:</b> {phones[idx]}\n\n"
            f"Yangi raqamni kiriting:",
            parse_mode="HTML"
        )

    elif action == "del":
        idx = int(parts[2])
        phones = get_contact_phones()
        if idx >= len(phones):
            await callback.answer("Raqam topilmadi!", show_alert=True)
            return
        await callback.message.answer(
            f"🗑 <b>Rostan ham o'chirmoqchimisiz?</b>\n\n📞 {phones[idx]}",
            parse_mode="HTML",
            reply_markup=confirm_phone_delete_kb(idx)
        )
        await callback.answer()


@router.message(IsAdmin(), AdminSettingsState.waiting_phone)
async def recv_settings_phone(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    phone = message.text.strip()
    await state.clear()
    phones = get_contact_phones()
    phones.append(phone)
    set_contact_phones(phones)
    phones_text = "\n".join(f"• {p}" for p in phones)
    await message.answer(
        f"✅ <b>Raqam qo'shildi!</b>\n\n📞 {phone}\n\n"
        f"Barcha raqamlar:\n{phones_text}",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


@router.message(IsAdmin(), AdminSettingsState.waiting_edit_phone)
async def recv_edit_phone(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    data = await state.get_data()
    idx = data.get("edit_phone_idx", 0)
    new_phone = message.text.strip()
    phones = get_contact_phones()
    if idx < len(phones):
        old = phones[idx]
        await state.update_data(pending_edit_phone=new_phone)
        await message.answer(
            f"💾 <b>Saqlaysizmi?</b>\n\n"
            f"Eski: {old}\n"
            f"Yangi: <b>{new_phone}</b>",
            parse_mode="HTML",
            reply_markup=confirm_save_kb(f"sphone:editok:{idx}")
        )
    else:
        await state.clear()
        await message.answer("❌ Raqam topilmadi!", reply_markup=admin_kb())


# ══════════════════════════════════════════
# KARTA TAHRIRLASH
# ══════════════════════════════════════════

@router.message(IsAdmin(), AdminSettingsState.waiting_card)
async def recv_settings_card(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    card = message.text.strip()
    await state.update_data(new_card=card)
    await state.set_state(AdminSettingsState.waiting_card_owner)
    await message.answer(
        f"✅ Karta: <code>{card}</code>\n\n"
        f"👤 Karta egasining ismini kiriting:\n"
        f"Misol: <code>KARIMOV MUROD</code>",
        parse_mode="HTML"
    )


@router.message(IsAdmin(), AdminSettingsState.waiting_card_owner)
async def recv_settings_card_owner(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    data = await state.get_data()
    card = data.get("new_card", "")
    owner = message.text.strip()
    await state.update_data(new_card_owner=owner)
    await message.answer(
        f"💾 <b>Saqlaysizmi?</b>\n\n"
        f"💳 <code>{card}</code>\n"
        f"👤 <b>{owner}</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb("set:card:save")
    )


# ══════════════════════════════════════════
# MANZIL TAHRIRLASH
# ══════════════════════════════════════════

@router.message(IsAdmin(), AdminSettingsState.waiting_address)
async def recv_settings_address(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    address = message.text.strip()
    await state.update_data(pending_address=address)
    await message.answer(
        f"💾 <b>Saqlaysizmi?</b>\n\n📍 <b>{address}</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb("set:address:save")
    )


# ══════════════════════════════════════════
# BARCHA TASDIQ CALLBACK LARI
# ══════════════════════════════════════════

@router.callback_query(IsAdmin(), F.data.startswith("confirm:cancel"))
async def confirm_cancelled(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("❌ Bekor qilindi")
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(IsAdmin(), F.data.startswith("savecat:"))
async def savecat_confirm(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    field = parts[1]
    cat_id = int(parts[2])
    data = await state.get_data()
    await state.clear()
    if field == "name":
        name = data.get("pending_cat_name", "")
        if not name:
            await callback.answer("❌ Ma'lumot topilmadi, qayta urinib ko'ring!", show_alert=True)
            return
        try:
            update_category_name(cat_id, name)
            await callback.message.edit_text(
                f"✅ <b>Kategoriya nomi yangilandi!</b>\n\n📂 {name}",
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.edit_text("❌ Bu nom allaqachon mavjud!")
    await callback.answer("✅ Saqlandi!")


@router.callback_query(IsAdmin(), F.data.startswith("saveprod:"))
async def saveprod_confirm(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    field = parts[1]
    prod_id = int(parts[2])
    data = await state.get_data()
    await state.clear()
    val = data.get("pending_value")

    if val is None:
        await callback.answer("❌ Ma'lumot topilmadi, qayta urinib ko'ring!", show_alert=True)
        return

    if field == "name":
        update_product_name(prod_id, val)
        await callback.message.edit_text(f"✅ <b>Nom yangilandi:</b> {val}", parse_mode="HTML")
    elif field == "price":
        update_product_price(prod_id, int(val))
        await callback.message.edit_text(f"✅ <b>Narx yangilandi:</b> {int(val):,} so'm", parse_mode="HTML")
    elif field == "photo":
        update_product_photo(prod_id, val)
        try:
            await callback.message.edit_caption("✅ <b>Rasm yangilandi!</b>", parse_mode="HTML")
        except Exception:
            await callback.message.answer("✅ Rasm yangilandi!")
    elif field == "unit":
        update_product_unit(prod_id, val)
        await callback.message.edit_text(f"✅ <b>Birlik yangilandi:</b> {val}", parse_mode="HTML")
    elif field == "prep":
        update_product_prep_time(prod_id, val)
        await callback.message.edit_text(f"✅ <b>Vaqt yangilandi:</b> {val}", parse_mode="HTML")
    await callback.answer("✅ Saqlandi!")


@router.callback_query(IsAdmin(), F.data.startswith("set:"))
async def settings_confirm(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    key = parts[1]
    data = await state.get_data()
    await state.clear()

    if key == "work_hours":
        work_str = data.get("pending_work_str", "")
        start = data.get("work_start", 9)
        end = data.get("pending_work_end", 23)
        set_setting("work_hours", work_str)
        import config
        config.WORK_START = start
        config.WORK_END = end
        await callback.message.edit_text(
            f"✅ <b>Ish vaqti yangilandi!</b>\n\n⏰ {work_str}",
            parse_mode="HTML"
        )

    elif key == "min_order":
        amount = data.get("pending_min_order", 0)
        set_setting("min_order", str(amount))
        import config
        config.MIN_ORDER_AMOUNT = amount
        label = f"{amount:,} so'm" if amount else "Cheklov yo'q"
        await callback.message.edit_text(
            f"✅ <b>Minimal buyurtma yangilandi!</b>\n\n💰 {label}",
            parse_mode="HTML"
        )

    elif key == "card":
        card = data.get("new_card", "")
        owner = data.get("new_card_owner", "")
        set_setting("payment_card", card)
        set_setting("card_owner", owner)
        import config
        config.PAYMENT_CARD = card
        config.CARD_OWNER = owner
        await callback.message.edit_text(
            f"✅ <b>Karta yangilandi!</b>\n\n💳 <code>{card}</code>\n👤 {owner}",
            parse_mode="HTML"
        )

    elif key == "address":
        address = data.get("pending_address", "")
        set_setting("address", address)
        await callback.message.edit_text(
            f"✅ <b>Manzil yangilandi!</b>\n\n📍 {address}",
            parse_mode="HTML"
        )

    await callback.answer("✅ Saqlandi!")


@router.message(IsAdmin(), AdminSettingsState.waiting_work_start)
async def recv_work_hours(message: Message, state: FSMContext):
    """Ish vaqtini bir qatorda qabul qiladi: 9-23, 9 23, 09:00-23:00"""
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    import re as _re
    text = message.text.strip()
    # Raqamlarni ajratib olamiz (daqiqa qismini olib tashlaymiz)
    clean_text = _re.sub(r':\d{2}', '', text)
    nums = _re.findall(r'\d+', clean_text)
    if len(nums) < 2:
        await message.answer(
            "❌ Noto'g'ri format!\n"
            "Misol: <code>9-23</code> yoki <code>9 23</code>",
            parse_mode="HTML"
        )
        return
    try:
        start = int(nums[0])
        end = int(nums[1])
        if not (0 <= start <= 23 and 0 <= end <= 23):
            raise ValueError
    except ValueError:
        await message.answer("❌ Soat 0-23 oralig'ida bo'lishi kerak!")
        return

    work_str = f"{start:02d}:00 - {end:02d}:00"
    await state.update_data(
        work_start=start,
        pending_work_str=work_str,
        pending_work_end=end
    )
    await message.answer(
        f"💾 <b>Saqlaysizmi?</b>\n\n⏰ Ish vaqti: <b>{work_str}</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb("set:work_hours:save")
    )


@router.message(IsAdmin(), AdminSettingsState.waiting_work_end)
async def recv_work_end(message: Message, state: FSMContext):
    """Eski ikki bosqichli kiritish — endi birinchi bosqichda hal qilinadi"""
    await recv_work_hours(message, state)


@router.message(IsAdmin(), AdminSettingsState.waiting_min_order)
async def recv_min_order(message: Message, state: FSMContext):
    if message.text in ADMIN_BUTTONS:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_kb())
        return
    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri narx! Misol: <code>20000</code>", parse_mode="HTML")
        return
    await state.update_data(pending_min_order=amount)
    label = f"{amount:,} so'm" if amount else "Cheklov yo'q"
    await message.answer(
        f"💾 <b>Saqlaysizmi?</b>\n\n💰 Minimal buyurtma: <b>{label}</b>",
        parse_mode="HTML",
        reply_markup=confirm_save_kb("set:min_order:save")
    )




# ══════════════════════════════════════════
# BUYURTMALAR RO'YXATI
# ══════════════════════════════════════════

@router.callback_query(IsAdmin(), F.data.startswith("night:"))
async def night_order_action(callback: CallbackQuery, bot: Bot):
    """Kechki buyurtmani qabul qilish yoki rad etish"""
    parts = callback.data.split(":")
    action = parts[1]
    order_id = int(parts[2])
    user_id = int(parts[3]) if len(parts) > 3 else 0

    from database import get_order, update_order_status
    order = get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return
    if order["status"] != "pending":
        await callback.answer("Bu buyurtma allaqachon hal qilingan!", show_alert=True)
        return

    # user_id 0 bo'lsa DB dan olamiz
    if not user_id:
        user_id = order["user_id"]

    if action == "accept":
        update_order_status(order_id, "paid")
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>Qabul qilindi!</b>",
                parse_mode="HTML",
                reply_markup=admin_order_kb(order_id, "paid", "pickup", "cash")
            )
        except Exception:
            pass
        await callback.answer("✅ Qabul qilindi!")
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ <b>Buyurtma #{order_id} tasdiqlandi!</b>\n\n"
                    f"🏠 Olib ketish uchun keling.\n"
                    f"📞 Savollar uchun: {order['phone2']}"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    elif action == "reject":
        update_order_status(order_id, "cancelled")
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ <b>Rad etildi!</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
        await callback.answer("❌ Rad etildi!")
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"❌ <b>Buyurtma #{order_id} rad etildi</b>\n\n"
                    f"Kechirasiz, hozir buyurtma qabul qilinmaydi.\n"
                    f"⏰ Ish vaqtimizda qayta urinib ko'ring!"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.callback_query(IsAdmin(), F.data.startswith("adm_order:"))
async def admin_order_from_list(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    order = get_order(order_id)
    if not order:
        await callback.answer("Topilmadi!", show_alert=True)
        return
    user = get_user(order["user_id"])
    uname = f"@{user['username']}" if user and user["username"] else "—"
    status = f"{STATUS_EMOJI.get(order['status'], '')} {STATUS_UZ.get(order['status'], order['status'])}"
    dlv = "🚚 Yetkazib berish" if order["delivery_type"] == "courier" else "🏠 O'zi olib ketish"
    adr = f"\n📍 {order['address']}" if order["address"] else ""
    fee = f"\n🚚 Yetkazib berish: {order['delivery_fee']:,} so'm" if order["delivery_fee"] else ""

    await callback.message.answer(
        f"📋 <b>Buyurtma #{order_id}</b>\n\n"
        f"👤 {user['full_name'] if user else '—'} | {uname}\n"
        f"📞 {order['phone1']} | {order['phone2']}\n"
        f"📦 {dlv}{adr}\n\n"
        f"🛒 {order['items_text']}\n\n"
        f"💰 {order['cart_total']:,} so'm{fee}\n"
        f"<b>Jami: {order['total_price']:,} so'm</b>\n"
        f"📅 {order['created_at'][:16]}\n"
        f"📊 {status}",
        parse_mode="HTML",
        reply_markup=admin_order_kb(order_id, order["status"], order["delivery_type"] or "courier", order["delivery_pay"] or "card")
    )
    await callback.answer()


@router.message(IsAdmin(), F.text == "📦 Buyurtmalar")
async def admin_orders_list(message: Message, state: FSMContext):
    await state.clear()
    months = get_available_months()

    if not months:
        await message.answer("📭 Hozircha buyurtmalar yo'q.")
        return

    # Joriy oy statistikasi
    current_month = months[0]
    await _send_month_orders(message, current_month, months)


async def _send_month_orders(target, month: str, months: list, edit: bool = False, page: int = 0):
    """Oylik statistika + buyurtmalar ro'yxati (pagination bilan)"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    MONTH_NAMES = {
        "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
        "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
        "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr"
    }
    PER_PAGE = 20

    stats = get_monthly_stats(month)
    orders = get_orders_by_month(month)

    year, mon = month.split("-")
    month_label = f"{MONTH_NAMES.get(mon, mon)} {year}"

    total_pages = max(1, (len(orders) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    page_orders = orders[page * PER_PAGE:(page + 1) * PER_PAGE]

    top_users_text = ""
    for i, u in enumerate(stats["top_users"], 1):
        uname = f"@{u['username']}" if u["username"] else "—"
        top_users_text += f"\n{i}. {u['full_name']} | {uname} — {u['spent']:,} so'm ({u['order_cnt']} ta)"

    page_info = f" ({page+1}/{total_pages} sahifa)" if total_pages > 1 else ""
    text = (
        f"📦 <b>{month_label} — Buyurtmalar</b>\n\n"
        f"📊 <b>Oylik ko'rsatkich:</b>\n"
        f"✅ Bajarilgan: <b>{stats['order_count']} ta</b>\n"
        f"❌ Bekor qilingan: <b>{stats['cancelled']} ta</b>\n"
        f"💰 Tushum: <b>{stats['total']:,} so'm</b>\n"
        f"⭐ O'rtacha reyting: <b>{stats['avg_rating']}</b>\n"
        f"👤 Yangi mijozlar: <b>{stats['new_users']} ta</b>\n"
        f"\n👑 <b>Top mijozlar:</b>"
        f"{top_users_text or ' Yo`q'}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📋 Jami: <b>{len(orders)} ta buyurtma</b>{page_info}"
    )

    builder = InlineKeyboardBuilder()

    # Buyurtmalar tugmalari — sahifadagi 20 ta
    for o in page_orders:
        s = STATUS_EMOJI.get(o["status"], "📋")
        user = get_user(o["user_id"])
        uname = (user["full_name"] if user else "—")[:12]
        builder.button(
            text=f"{s} #{o['id']} {uname} — {o['total_price']:,} so'm",
            callback_data=f"adm_order:{o['id']}"
        )
    builder.adjust(1)

    # Pagination
    if total_pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️ Oldingi", callback_data=f"orders_page:{month}:{page-1}")
        nav.button(text=f"{page+1}/{total_pages}", callback_data="noop:p")
        if page < total_pages - 1:
            nav.button(text="Keyingi ➡️", callback_data=f"orders_page:{month}:{page+1}")
        nav.adjust(3)
        builder.attach(nav)

    # Oy tanlash
    if len(months) > 1:
        nav2 = InlineKeyboardBuilder()
        for m in months[:6]:  # max 6 ta oy tugma
            y2, mn2 = m.split("-")
            lbl = f"{MONTH_NAMES.get(mn2, mn2)} {y2}"
            if m == month:
                lbl = f"✅ {lbl}"
            nav2.button(text=lbl, callback_data=f"orders_month:{m}")
        nav2.adjust(3)
        builder.attach(nav2)

    # O'chirish tugmasi
    builder.button(
        text=f"🗑 {month_label} — O'chirish",
        callback_data=f"orders_delete:{month}"
    )

    if edit and hasattr(target, 'edit_text'):
        try:
            await target.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
            return
        except Exception:
            pass
    await target.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(IsAdmin(), F.data.startswith("orders_page:"))
async def orders_page_cb(callback: CallbackQuery):
    parts = callback.data.split(":")
    month = parts[1]
    page = int(parts[2])
    months = get_available_months()
    await _send_month_orders(callback.message, month, months, edit=True, page=page)
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("orders_month:"))
async def orders_month_cb(callback: CallbackQuery):
    month = callback.data.split(":", 1)[1]
    months = get_available_months()
    await _send_month_orders(callback.message, month, months, edit=True)
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("orders_delete:"))
async def orders_delete_confirm(callback: CallbackQuery):
    month = callback.data.split(":", 1)[1]
    month_names = {
        "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
        "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
        "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr"
    }
    year, mon = month.split("-")
    month_label = f"{month_names.get(mon, mon)} {year}"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Ha, o'chirish", callback_data=f"orders_delete_ok:{month}")
    builder.button(text="❌ Bekor",          callback_data=f"orders_month:{month}")
    builder.adjust(2)
    await callback.message.answer(
        f"⚠️ <b>Rostan ham {month_label} oyining barcha buyurtmalarini o'chirmoqchimisiz?</b>\n\n"
        f"Bu amalni qaytarib bo'lmaydi!",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("orders_delete_ok:"))
async def orders_delete_ok(callback: CallbackQuery):
    month = callback.data.split(":", 1)[1]
    month_names = {
        "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
        "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
        "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr"
    }
    year, mon = month.split("-")
    month_label = f"{month_names.get(mon, mon)} {year}"
    cnt = delete_orders_by_month(month)
    await callback.answer("✅ O'chirildi!")
    try:
        await callback.message.edit_text(
            f"🗑 <b>{month_label} oyining {cnt} ta buyurtmasi o'chirildi.</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.message(IsAdmin(), F.text.regexp(r"^/order_(\d+)$"))
async def admin_order_detail(message: Message):
    import re
    m = re.match(r"^/order_(\d+)$", message.text)
    order_id = int(m.group(1))
    order = get_order(order_id)
    if not order:
        await message.answer("❌ Topilmadi!")
        return

    user = get_user(order["user_id"])
    status = f"{STATUS_EMOJI.get(order['status'], '')} {STATUS_UZ.get(order['status'], order['status'])}"
    dlv = "🚚 Yetkazib berish" if order["delivery_type"] == "courier" else "🏠 O'zi olib ketish"
    adr = f"\n📍 {order['address']}" if order["address"] else ""

    await message.answer(
        f"📋 <b>Buyurtma #{order_id}</b>\n\n"
        f"👤 {user['full_name'] if user else '—'}\n"
        f"📞 {order['phone1']} / {order['phone2']}\n"
        f"📦 {dlv}{adr}\n\n"
        f"🛒 {order['items_text']}\n\n"
        f"💰 {order['total_price']:,} so'm\n"
        f"📅 {order['created_at']}\n"
        f"📊 {status}",
        parse_mode="HTML",
        reply_markup=admin_order_kb(order_id, order["status"], order["delivery_type"] or "courier", order["delivery_pay"] or "card")
    )
