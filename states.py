"""
states.py — Barcha FSM holatlari (tozalangan)
"""

from aiogram.fsm.state import State, StatesGroup


class OrderState(StatesGroup):
    """Buyurtma jarayoni"""
    choosing_delivery     = State()
    choosing_delivery_pay = State()
    waiting_location      = State()
    waiting_phone1        = State()
    waiting_phone2        = State()
    waiting_payment       = State()


class AdminSettingsState(StatesGroup):
    waiting_work_start  = State()
    waiting_work_end    = State()
    waiting_min_order   = State()
    waiting_phone       = State()   # yangi raqam qo'shish
    waiting_edit_phone  = State()   # mavjud raqam tahrirlash
    waiting_card        = State()   # karta raqami
    waiting_card_owner  = State()   # karta egasi ismi
    waiting_address     = State()   # restoran manzili


class AdminEditCategoryState(StatesGroup):
    waiting_name = State()


class AdminCategoryState(StatesGroup):
    """Admin: kategoriya qo'shish"""
    waiting_name  = State()
    waiting_emoji = State()


class AdminProductState(StatesGroup):
    """Admin: mahsulot qo'shish"""
    waiting_category  = State()
    waiting_name      = State()
    waiting_price     = State()
    waiting_unit      = State()
    waiting_prep_time = State()
    waiting_photo     = State()


class AdminEditProductState(StatesGroup):
    """Admin: mahsulot tahrirlash"""
    waiting_name      = State()
    waiting_price     = State()
    waiting_photo     = State()
    waiting_unit      = State()
    waiting_prep_time = State()


class AdminBroadcastState(StatesGroup):
    """Admin: reklam yuborish"""
    waiting_content = State()


class AdminDeliveryFeeState(StatesGroup):
    """Admin: yetkazib berish narxini belgilash"""
    waiting_fee = State()


class AdminSearchState(StatesGroup):
    """Admin: buyurtma qidirish"""
    waiting_order_id = State()
