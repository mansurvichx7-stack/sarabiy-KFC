"""
keyboards/inline.py — Inline klaviaturalar (rangli tugmalar)
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ══════════════════════════════════════════
# OBUNA
# ══════════════════════════════════════════

def admin_menu_kb() -> InlineKeyboardMarkup:
    """Admin menyu boshqaruvi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍽 Kategoriyalar",  callback_data="amenu:cats")
    builder.button(text="🍔 Mahsulotlar",    callback_data="amenu:prods")
    builder.button(text="➕ Kategoriya qo'sh", callback_data="amenu:addcat")
    builder.button(text="➕ Mahsulot qo'sh",   callback_data="amenu:addprod")
    builder.adjust(2)
    return builder.as_markup()


def admin_settings_kb(bot_open: bool = True) -> InlineKeyboardMarkup:
    """Admin sozlamalar"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏰ Ish vaqti",           callback_data="settings:work_hours")
    builder.button(text="💰 Minimal buyurtma",     callback_data="settings:min_order")
    builder.button(text="📞 Telefon raqamlari",    callback_data="settings:phones")
    builder.button(text="💳 Karta tahrirlash",     callback_data="settings:card")
    builder.button(text="📍 Manzil tahrirlash",    callback_data="settings:address")
    builder.adjust(1)
    return builder.as_markup()


def settings_phones_kb(phones: list) -> InlineKeyboardMarkup:
    """Telefon raqamlar boshqaruvi"""
    builder = InlineKeyboardBuilder()
    for i, phone in enumerate(phones):
        builder.button(text=f"📞 {phone}", callback_data=f"noop:ph")
        builder.button(text="✏️", callback_data=f"sphone:edit:{i}")
        builder.button(text="🗑", callback_data=f"sphone:del:{i}")
    if len(phones) < 5:
        builder.button(text="➕ Raqam qo'shish", callback_data="sphone:add")
    builder.adjust(*([3] * len(phones)), 1)
    return builder.as_markup()



def subscribe_kb(channel_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Kanalga obuna bo'lish", url=channel_link)
    builder.button(text="✅ Obuna bo'ldim — Tekshirish", callback_data="check_sub")
    builder.adjust(1)
    return builder.as_markup()


# ══════════════════════════════════════════
# MENYU — KATEGORIYALAR
# ══════════════════════════════════════════

CAT_COLORS = ["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛"]

def categories_kb(categories: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, cat in enumerate(categories):
        color = CAT_COLORS[i % len(CAT_COLORS)]
        builder.button(
            text=f"{color} {cat['emoji']} {cat['name']}",
            callback_data=f"cat:{cat['id']}"
        )
    builder.adjust(2)
    return builder.as_markup()


def products_kb(products: list, category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in products:
        unit = p["unit"] if "unit" in p.keys() else "dona"
        prep = p["prep_time"] if "prep_time" in p.keys() else "30 daqiqa"
        builder.button(
            text=f"🍽 {p['name']} — {p['price']:,} so'm/{unit} | ⏱~{prep}",
            callback_data=f"prod:{p['id']}"
        )
    builder.button(text="◀️ Kategoriyalar", callback_data="back:cats")
    builder.adjust(1)
    return builder.as_markup()


def product_detail_kb(product_id: int, cat_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Savatga qo'shish", callback_data=f"add:{product_id}")
    builder.button(text="◀️ Ortga",            callback_data=f"cat:{cat_id}")
    builder.adjust(1)
    return builder.as_markup()


# ══════════════════════════════════════════
# SAVAT
# ══════════════════════════════════════════

def cart_kb(cart_items: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    widths = []
    for item in cart_items:
        pid = item["product_id"]
        unit = item["unit"] if item["unit"] else "dona"
        qty = item["quantity"]
        if unit == "kg":
            qty_display = f"{qty/10:.1f}".rstrip('0').rstrip('.') + " kg"
        else:
            qty_display = str(qty)
        builder.button(
            text=f"🍽 {item['name']} — {item['subtotal']:,} so'm",
            callback_data=f"noop:{pid}"
        )
        widths.append(1)
        builder.button(text="➖", callback_data=f"cminus:{pid}")
        builder.button(text=qty_display, callback_data=f"noop:{pid}")
        builder.button(text="➕", callback_data=f"cplus:{pid}")
        builder.button(text="❌", callback_data=f"cremove:{pid}")
        widths.append(4)
    builder.button(text="🗑 Savatni tozalash", callback_data="cart:clear")
    builder.button(text="✅ Buyurtma berish",  callback_data="cart:checkout")
    widths.append(2)
    builder.adjust(*widths)
    return builder.as_markup()


# ══════════════════════════════════════════
# BUYURTMA JARAYONI
# ══════════════════════════════════════════

def night_delivery_kb() -> InlineKeyboardMarkup:
    """Kechki buyurtma — faqat o'zi olib ketish"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 O'zi olib ketish (Naqd)", callback_data="dlv:night")
    builder.adjust(1)
    return builder.as_markup()


def night_order_admin_kb(order_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Kechki buyurtma — admin qabul/rad tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Qabul — kelsin",    callback_data=f"night:accept:{order_id}:{user_id}")
    builder.button(text="❌ Rad etish",          callback_data=f"night:reject:{order_id}:{user_id}")
    builder.adjust(1)
    return builder.as_markup()


def delivery_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚚 Yetkazib berish",  callback_data="dlv:courier")
    builder.button(text="🏠 O'zi olib ketish", callback_data="dlv:pickup")
    builder.adjust(1)
    return builder.as_markup()


def delivery_pay_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Karta orqali to'layman",  callback_data="dpay:card")
    builder.button(text="💵 Naqd pul to'layman",      callback_data="dpay:cash")
    builder.button(text="⬅️ Ortga",                   callback_data="dpay:back")
    builder.adjust(1)
    return builder.as_markup()




# ══════════════════════════════════════════
# BUYURTMALARIM
# ══════════════════════════════════════════

STATUS_EMOJI = {
    "pending":         "⏳",
    "waiting_payment": "💳",
    "paid":            "✅",
    "preparing":       "👨‍🍳",
    "on_the_way":      "🚚",
    "shipped":         "🚚",
    "delivered":       "📦",
    "cancelled":       "❌",
}

STATUS_UZ = {
    "pending":         "Kutilmoqda",
    "waiting_payment": "To'lov kutilmoqda",
    "paid":            "To'landi",
    "preparing":       "Tayyorlanmoqda",
    "on_the_way":      "Yo'lda",
    "shipped":         "Chiqarib yuborildi",
    "delivered":       "Yetkazildi",
    "cancelled":       "Bekor qilindi",
}


def my_orders_kb(orders: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "📋")
        # Buyurtma tarkibini qisqacha ko'rsatish (birinchi mahsulot)
        items_short = o["items_text"].split("\n")[0] if o["items_text"] else "—"
        if len(items_short) > 25:
            items_short = items_short[:25] + "..."
        builder.button(
            text=f"{emoji} #{o['id']} | {items_short}",
            callback_data=f"order:{o['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def order_detail_kb(order_id: int, status: str, cancel_requested: int, delivery_pay: str = "card") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "waiting_payment":
        # Chek yuborish faqat karta uchun
        if delivery_pay == "card":
            builder.button(
                text="📸 Chek yuborish",
                callback_data=f"resend_check:{order_id}"
            )
        if not cancel_requested:
            builder.button(
                text="❌ Bekor qilish",
                callback_data=f"cancel_req:{order_id}"
            )
    if status == "delivered":
        builder.button(
            text="🔄 Takrorlash",
            callback_data=f"repeat_order:{order_id}"
        )
    builder.button(text="◀️ Ortga", callback_data="back:orders")
    builder.adjust(1)
    return builder.as_markup()


# ══════════════════════════════════════════
# REYTING
# ══════════════════════════════════════════

def rating_kb(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1 ⭐",         callback_data=f"rate:{order_id}:1")
    builder.button(text="2 ⭐⭐",       callback_data=f"rate:{order_id}:2")
    builder.button(text="3 ⭐⭐⭐",     callback_data=f"rate:{order_id}:3")
    builder.button(text="4 ⭐⭐⭐⭐",   callback_data=f"rate:{order_id}:4")
    builder.button(text="5 ⭐⭐⭐⭐⭐", callback_data=f"rate:{order_id}:5")
    builder.adjust(5)
    return builder.as_markup()


# ══════════════════════════════════════════
# ADMIN — BUYURTMA BOSHQARUVI
# ══════════════════════════════════════════

def admin_order_kb(order_id: int, status: str, delivery_type: str = "courier", delivery_pay: str = "card") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "pending":
        # Kechki buyurtma ro'yxatdan ko'rilganda
        builder.button(text="✅ Qabul — kelsin",  callback_data=f"night:accept:{order_id}:0")
        builder.button(text="❌ Rad etish",        callback_data=f"night:reject:{order_id}:0")
    elif status == "waiting_payment":
        if delivery_pay == "cash":
            builder.button(text="✅ Qabul qilish",       callback_data=f"adm:paid:{order_id}")
        else:
            builder.button(text="✅ To'lovni tasdiqlash", callback_data=f"adm:paid:{order_id}")
        builder.button(text="❌ Rad etish", callback_data=f"adm:cancel:{order_id}")
    elif status == "paid":
        builder.button(text="👨‍🍳 Tayyorlanmoqda", callback_data=f"adm:prep:{order_id}")
    elif status == "preparing":
        if delivery_type == "pickup":
            builder.button(text="✅ Tayyor — olib ketishingiz mumkin", callback_data=f"adm:ready:{order_id}")
        else:
            builder.button(text="🚚 Taksiga berib yuborildi",         callback_data=f"adm:way:{order_id}")
    elif status == "on_the_way":
        pass  # Tugma kerak emas — taksi o'zi yetkazadi
    builder.adjust(1)
    return builder.as_markup()


def taxi_choice_kb(order_id: int) -> InlineKeyboardMarkup:
    """Taksi xabarida foydalanuvchiga tanlov"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 O'zim olib ketaman", callback_data=f"taxi:self:{order_id}")
    builder.button(text="✅ Tushunarli",          callback_data=f"taxi:ok:{order_id}")
    builder.adjust(1)
    return builder.as_markup()


def admin_cancel_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    """Foydalanuvchi bekor qilish so'rovini tasdiqlash"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, bekor qilinsin",    callback_data=f"adm:cancelok:{order_id}")
    builder.button(text="❌ Yo'q, bekor qilinmasin", callback_data=f"adm:cancelnok:{order_id}")
    builder.adjust(2)
    return builder.as_markup()


# ══════════════════════════════════════════
# ADMIN — MAHSULOT BOSHQARUVI
# ══════════════════════════════════════════

def admin_categories_kb(categories: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        status = "🟢" if cat["is_active"] else "🔴"
        builder.button(
            text=f"{status} {cat['emoji']} {cat['name']}",
            callback_data=f"editcat:{cat['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def admin_edit_category_kb(cat_id: int, always_open: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Nomini o'zgartirish", callback_data=f"ec:name:{cat_id}")
    if always_open:
        builder.button(text="🌙 Doim ochiq: HA ✅",  callback_data=f"ec:toggle:{cat_id}")
    else:
        builder.button(text="🌙 Doim ochiq: YO'Q ❌", callback_data=f"ec:toggle:{cat_id}")
    builder.button(text="🗑 O'chirish", callback_data=f"delcat:{cat_id}")
    builder.adjust(1)
    return builder.as_markup()


def admin_products_kb(products: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in products:
        status = "🟢" if p["is_active"] else "🔴"
        builder.button(
            text=f"{status} {p['name']} — {p['price']:,} so'm",
            callback_data=f"editp:{p['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def admin_edit_product_kb(product_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Nomini o'zgartirish",       callback_data=f"ep:name:{product_id}")
    builder.button(text="💰 Narxini o'zgartirish",      callback_data=f"ep:price:{product_id}")
    builder.button(text="🍽 O'lchov birligini o'zg.",   callback_data=f"ep:unit:{product_id}")
    builder.button(text="⏱ Tayyorlanish vaqtini o'zg.", callback_data=f"ep:prep:{product_id}")
    builder.button(text="🖼 Rasmini o'zgartirish",      callback_data=f"ep:photo:{product_id}")
    if is_active:
        builder.button(text="🔴 Vaqtincha yopish",      callback_data=f"ep:toggle:{product_id}")
    else:
        builder.button(text="🟢 Ochish (mavjud)",        callback_data=f"ep:toggle:{product_id}")
    builder.button(text="🗑 O'chirish",                  callback_data=f"ep:delete:{product_id}")
    builder.adjust(2)
    return builder.as_markup()


def admin_select_category_kb(categories: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, cat in enumerate(categories):
        color = CAT_COLORS[i % len(CAT_COLORS)]
        builder.button(
            text=f"{color} {cat['emoji']} {cat['name']}",
            callback_data=f"selcat:{cat['id']}"
        )
    builder.adjust(2)
    return builder.as_markup()


def unit_kb() -> InlineKeyboardMarkup:
    """O'lchov birligi tanlash"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🍽 Dona",    callback_data="unit:dona")
    builder.button(text="⚖️ kg",      callback_data="unit:kg")
    builder.button(text="🥣 Porsiya", callback_data="unit:porsiya")
    builder.adjust(3)
    return builder.as_markup()


def admin_delete_confirm_kb(item_type: str, item_id: int) -> InlineKeyboardMarkup:
    """O'chirish tasdiqlash klaviaturasi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Ha, o'chirish",  callback_data=f"confirmdelete:{item_type}:{item_id}")
    builder.button(text="❌ Bekor qilish",   callback_data=f"canceldelete:{item_type}:{item_id}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_save_kb(confirm_data: str, cancel_data: str = "confirm:cancel") -> InlineKeyboardMarkup:
    """Saqlashni tasdiqlash — har qanday tahrirlash uchun"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, saqlash",   callback_data=confirm_data)
    builder.button(text="❌ Bekor qilish",  callback_data=cancel_data)
    builder.adjust(2)
    return builder.as_markup()


def confirm_phone_delete_kb(idx: int) -> InlineKeyboardMarkup:
    """Telefon raqamni o'chirishni tasdiqlash"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Ha, o'chirish",  callback_data=f"sphone:delok:{idx}")
    builder.button(text="❌ Bekor qilish",   callback_data="sphone:delcancel")
    builder.adjust(2)
    return builder.as_markup()


def admin_user_kb(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    return builder.as_markup()
