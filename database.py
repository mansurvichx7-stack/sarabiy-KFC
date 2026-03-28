"""
database.py — SQLite ma'lumotlar bazasi
"""

import sqlite3
from datetime import datetime
from typing import Optional

DB_PATH = "sarabiy_kfc.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def backup_db():
    """DB ning nusxasini oladi"""
    import shutil
    from datetime import datetime
    backup_name = f"sarabiy_kfc_backup_{datetime.now().strftime('%Y%m%d')}.db"
    try:
        shutil.copy2(DB_PATH, backup_name)
    except Exception:
        pass


# ══════════════════════════════════════════
# JADVALLAR
# ══════════════════════════════════════════

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Foydalanuvchilar
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            full_name   TEXT,
            username    TEXT,
            phone1      TEXT,
            phone2      TEXT,
            created_at  TEXT,
            last_active TEXT
        )
    """)

    # Kategoriyalar
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT UNIQUE,
            emoji     TEXT DEFAULT '🍽',
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        )
    """)

    # Mahsulotlar
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name        TEXT,
            price       INTEGER,
            photo_id    TEXT,
            unit        TEXT DEFAULT 'dona',
            prep_time   TEXT DEFAULT '30 daqiqa',
            is_active   INTEGER DEFAULT 1,
            order_count INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    # Savat
    c.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            product_id INTEGER,
            quantity   INTEGER DEFAULT 1,
            UNIQUE(user_id, product_id)
        )
    """)

    # Buyurtmalar
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER,
            items_text      TEXT,
            cart_total      INTEGER,
            delivery_fee    INTEGER DEFAULT 0,
            total_price     INTEGER,
            delivery_type   TEXT,
            delivery_pay    TEXT DEFAULT 'cash',
            address         TEXT,
            latitude        REAL,
            longitude       REAL,
            phone1          TEXT,
            phone2          TEXT,
            payment_photo   TEXT,
            status          TEXT DEFAULT 'pending',
            cancel_requested INTEGER DEFAULT 0,
            rating          INTEGER DEFAULT 0,
            created_at      TEXT
        )
    """)

    # Chegirmalar
    c.execute("""
        CREATE TABLE IF NOT EXISTS discounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER UNIQUE,
            type        TEXT,
            amount      INTEGER,
            created_at  TEXT
        )
    """)

    # Reytinglar
    c.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            order_id   INTEGER UNIQUE,
            stars      INTEGER,
            created_at TEXT
        )
    """)

    # Bot sozlamalari (ish vaqti, holat)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Spam himoya
    c.execute("""
        CREATE TABLE IF NOT EXISTS spam_log (
            user_id    INTEGER PRIMARY KEY,
            last_time  REAL
        )
    """)

    conn.commit()
    _init_settings(c, conn)
    _migrate_db(c, conn)
    conn.close()


def _init_settings(c, conn):
    defaults = [
        ("bot_open", "1"),
        ("work_hours", "09:00 - 23:00"),
        ("delivery_fee", "0"),
    ]
    for key, val in defaults:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    conn.commit()


def _migrate_db(c, conn):
    """Eski bazaga yangi ustunlarni qo'shadi"""
    try:
        c.execute("ALTER TABLE products ADD COLUMN unit TEXT DEFAULT 'dona'")
        conn.commit()
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE products ADD COLUMN prep_time TEXT DEFAULT '30 daqiqa'")
        conn.commit()
    except Exception:
        pass
    # categories jadvaliga always_open ustuni
    try:
        c.execute("ALTER TABLE categories ADD COLUMN always_open INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass


# ══════════════════════════════════════════
# SOZLAMALAR
# ══════════════════════════════════════════

def get_contact_phones() -> list:
    """Aloqa telefon raqamlar ro'yxati"""
    raw = get_setting("contact_phones") or get_setting("contact_phone") or ""
    phones = [p.strip() for p in raw.split("\n") if p.strip()]
    return phones


def set_contact_phones(phones: list):
    """Aloqa raqamlarni saqlash"""
    value = "\n".join(p.strip() for p in phones if p.strip())
    set_setting("contact_phones", value)
    # Eski kalit ham yangilansin (contact.py uchun fallback)
    set_setting("contact_phone", phones[0] if phones else "")


def get_setting(key: str) -> Optional[str]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def set_setting(key: str, value: str):
    conn = get_conn()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        conn.commit()
    finally:
        conn.close()


def parse_prep_minutes(prep_time: str) -> int:
    """Tayyorlanish vaqtini daqiqaga aylantiradi. Misol: '20 daqiqa' -> 20"""
    import re as _re
    prep_time = prep_time.lower()
    total = 0
    m = _re.search(r"(\d+)\s*kun", prep_time)
    if m:
        total += int(m.group(1)) * 24 * 60
    m = _re.search(r"(\d+)\s*soat", prep_time)
    if m:
        total += int(m.group(1)) * 60
    m = _re.search(r"(\d+)\s*daqiqa", prep_time)
    if m:
        total += int(m.group(1))
    return total or 30


def is_bot_open() -> bool:
    return get_setting("bot_open") == "1"


# ══════════════════════════════════════════
# SPAM HIMOYA
# ══════════════════════════════════════════

def check_spam(user_id: int, timeout: float = 3.0) -> bool:
    """True = spam (blok), False = normal"""
    import time
    now = time.time()
    conn = get_conn()
    try:
        row = conn.execute("SELECT last_time FROM spam_log WHERE user_id=?", (user_id,)).fetchone()
        if row and (now - row["last_time"]) < timeout:
            return True
        conn.execute(
            "INSERT OR REPLACE INTO spam_log (user_id, last_time) VALUES (?,?)",
            (user_id, now)
        )
        conn.commit()
        return False
    finally:
        conn.close()


# ══════════════════════════════════════════
# FOYDALANUVCHILAR
# ══════════════════════════════════════════

def register_user(telegram_id: int, full_name: str, username: Optional[str]):
    conn = get_conn()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute(
            """INSERT OR IGNORE INTO users
               (telegram_id, full_name, username, created_at, last_active)
               VALUES (?,?,?,?,?)""",
            (telegram_id, full_name, username, now, now)
        )
        conn.execute(
            "UPDATE users SET last_active=?, full_name=?, username=? WHERE telegram_id=?",
            (now, full_name, username, telegram_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_user(telegram_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
        ).fetchone()
    finally:
        conn.close()


def update_user_phones(telegram_id: int, phone1: str, phone2: str):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE users SET phone1=?, phone2=? WHERE telegram_id=?",
            (phone1, phone2, telegram_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_all_users() -> list:
    from config import ADMIN_IDS
    conn = get_conn()
    try:
        placeholders = ",".join("?" * len(ADMIN_IDS))
        return conn.execute(
            f"SELECT * FROM users WHERE telegram_id NOT IN ({placeholders}) ORDER BY id DESC",
            ADMIN_IDS
        ).fetchall()
    finally:
        conn.close()


def get_users_count() -> int:
    from config import ADMIN_IDS
    conn = get_conn()
    try:
        placeholders = ",".join("?" * len(ADMIN_IDS))
        return conn.execute(
            f"SELECT COUNT(*) as cnt FROM users WHERE telegram_id NOT IN ({placeholders})",
            ADMIN_IDS
        ).fetchone()["cnt"]
    finally:
        conn.close()


def get_user_stats(telegram_id: int) -> dict:
    """Foydalanuvchi to'liq statistikasi"""
    conn = get_conn()
    try:
        orders = conn.execute(
            """SELECT COUNT(*) as cnt, SUM(total_price) as total
               FROM orders WHERE user_id=? AND status='delivered'""",
            (telegram_id,)
        ).fetchone()
        last_orders = conn.execute(
            """SELECT * FROM orders WHERE user_id=?
               ORDER BY id DESC LIMIT 3""",
            (telegram_id,)
        ).fetchall()
        avg_rating = conn.execute(
            "SELECT AVG(stars) as avg FROM ratings WHERE user_id=?",
            (telegram_id,)
        ).fetchone()
        return {
            "order_count": orders["cnt"] or 0,
            "total_spent": orders["total"] or 0,
            "last_orders": last_orders,
            "avg_rating": round(avg_rating["avg"] or 0, 1),
        }
    finally:
        conn.close()


# ══════════════════════════════════════════
# KATEGORIYALAR
# ══════════════════════════════════════════

def get_categories(check_work_hours: bool = True) -> list:
    """Kategoriyalarni qaytaradi. Ish vaqtidan tashqari faqat always_open=1 lar."""
    conn = get_conn()
    try:
        from datetime import datetime
        from config import WORK_START as CFG_START, WORK_END as CFG_END

        # DB dagi sozlamalarni birinchi o'qiymiz
        row = conn.execute("SELECT value FROM settings WHERE key='work_hours'").fetchone()
        if row and row["value"]:
            try:
                parts = row["value"].replace(" ", "").split("-")
                start = int(parts[0].split(":")[0])
                end = int(parts[1].split(":")[0])
            except Exception:
                start, end = CFG_START, CFG_END
        else:
            start, end = CFG_START, CFG_END

        is_work_time = True
        if check_work_hours and start is not None and end is not None:
            h = datetime.now().hour
            if start <= end:
                is_work_time = start <= h < end
            else:
                is_work_time = h >= start or h < end

        if is_work_time:
            return conn.execute(
                "SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order, id"
            ).fetchall()
        else:
            return conn.execute(
                "SELECT * FROM categories WHERE is_active=1 AND always_open=1 ORDER BY sort_order, id"
            ).fetchall()
    finally:
        conn.close()


def get_all_categories() -> list:
    conn = get_conn()
    try:
        return conn.execute("SELECT * FROM categories ORDER BY sort_order, id").fetchall()
    finally:
        conn.close()


def add_category(name: str, emoji: str) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO categories (name, emoji) VALUES (?,?)", (name, emoji)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def toggle_always_open(cat_id: int) -> bool:
    """Kategoriyani 'doim ochiq' holatini o'zgartiradi"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT always_open FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not row:
            return False
        new_val = 0 if row["always_open"] else 1
        conn.execute("UPDATE categories SET always_open=? WHERE id=?", (new_val, cat_id))
        conn.commit()
        return bool(new_val)
    finally:
        conn.close()


def update_category_name(cat_id: int, name: str):
    conn = get_conn()
    try:
        conn.execute("UPDATE categories SET name=? WHERE id=?", (name, cat_id))
        conn.commit()
    finally:
        conn.close()


def delete_category(cat_id: int):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM products WHERE category_id=?", (cat_id,))
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit()
    finally:
        conn.close()


def get_category(cat_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM categories WHERE id=?", (cat_id,)
        ).fetchone()
    finally:
        conn.close()


# ══════════════════════════════════════════
# MAHSULOTLAR
# ══════════════════════════════════════════

def get_products(category_id: int) -> list:
    conn = get_conn()
    try:
        return conn.execute(
            """SELECT p.*, c.name as cat_name, c.emoji as cat_emoji
               FROM products p JOIN categories c ON c.id=p.category_id
               WHERE p.category_id=? AND p.is_active=1
               ORDER BY p.id""",
            (category_id,)
        ).fetchall()
    finally:
        conn.close()


def get_product(product_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            """SELECT p.*, c.name as cat_name, c.emoji as cat_emoji
               FROM products p JOIN categories c ON c.id=p.category_id
               WHERE p.id=?""",
            (product_id,)
        ).fetchone()
    finally:
        conn.close()


def get_all_products() -> list:
    conn = get_conn()
    try:
        return conn.execute(
            """SELECT p.*, c.name as cat_name
               FROM products p JOIN categories c ON c.id=p.category_id
               ORDER BY c.sort_order, p.id"""
        ).fetchall()
    finally:
        conn.close()


def add_product(category_id: int, name: str, price: int, photo_id: str,
                unit: str = "dona", prep_time: str = "30 daqiqa") -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO products (category_id, name, price, photo_id, unit, prep_time) VALUES (?,?,?,?,?,?)",
            (category_id, name, price, photo_id, unit, prep_time)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_product_name(product_id: int, name: str):
    conn = get_conn()
    try:
        conn.execute("UPDATE products SET name=? WHERE id=?", (name, product_id))
        conn.commit()
    finally:
        conn.close()


def update_product_price(product_id: int, price: int):
    conn = get_conn()
    try:
        conn.execute("UPDATE products SET price=? WHERE id=?", (price, product_id))
        conn.commit()
    finally:
        conn.close()


def update_product_photo(product_id: int, photo_id: str):
    conn = get_conn()
    try:
        conn.execute("UPDATE products SET photo_id=? WHERE id=?", (photo_id, product_id))
        conn.commit()
    finally:
        conn.close()


def update_product_unit(product_id: int, unit: str):
    conn = get_conn()
    try:
        conn.execute("UPDATE products SET unit=? WHERE id=?", (unit, product_id))
        conn.commit()
    finally:
        conn.close()


def update_product_prep_time(product_id: int, prep_time: str):
    conn = get_conn()
    try:
        conn.execute("UPDATE products SET prep_time=? WHERE id=?", (prep_time, product_id))
        conn.commit()
    finally:
        conn.close()


def toggle_product(product_id: int) -> bool:
    """Mahsulotni yoq/bor qiladi. Yangi holatni qaytaradi (True=faol)"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT is_active FROM products WHERE id=?", (product_id,)).fetchone()
        if not row:
            return False
        new_status = 0 if row["is_active"] else 1
        conn.execute("UPDATE products SET is_active=? WHERE id=?", (new_status, product_id))
        conn.commit()
        return bool(new_status)
    finally:
        conn.close()


def delete_product(product_id: int):
    conn = get_conn()
    try:
        conn.execute("UPDATE products SET is_active=0 WHERE id=?", (product_id,))
        conn.commit()
    finally:
        conn.close()


def get_top_products(limit: int = 5) -> list:
    conn = get_conn()
    try:
        return conn.execute(
            """SELECT p.name, p.price, p.order_count, p.unit, c.emoji
               FROM products p JOIN categories c ON c.id=p.category_id
               WHERE p.is_active=1 AND p.order_count > 0
               ORDER BY p.order_count DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    finally:
        conn.close()


def increment_order_count(product_id: int):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE products SET order_count=order_count+1 WHERE id=?", (product_id,)
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════
# SAVAT
# ══════════════════════════════════════════

_cart_add_lock = {}
_CART_LOCK_TIMEOUT = 1.0  # 1 soniya debounce (qulf)

def add_to_cart(user_id: int, product_id: int) -> bool:
    import time
    now = time.time()
    
    if len(_cart_add_lock) > 500:
        expired = [k for k, v in _cart_add_lock.items() if now - v > 60]
        for k in expired:
            del _cart_add_lock[k]

    lock_key = f"{user_id}_{product_id}"
    if lock_key in _cart_add_lock and now - _cart_add_lock[lock_key] < _CART_LOCK_TIMEOUT:
        return False  # Tez bosib yuborilgan (debounce)
    _cart_add_lock[lock_key] = now

    conn = get_conn()
    try:
        p = conn.execute("SELECT unit FROM products WHERE id=?", (product_id,)).fetchone()
        step = 5 if p and p["unit"] == "kg" else 1

        conn.execute(
            """INSERT INTO cart (user_id, product_id, quantity) VALUES (?,?,?)
               ON CONFLICT(user_id, product_id) DO UPDATE SET quantity=quantity+?""",
            (user_id, product_id, step, step)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_cart(user_id: int) -> list:
    """Faqat faol mahsulotlarni qaytaradi. O'chirilganlar avtomatik o'chadi."""
    conn = get_conn()
    try:
        # O'chirilgan mahsulotlarni savatdan butunlay o'chirish
        conn.execute(
            """DELETE FROM cart WHERE user_id=? AND product_id NOT IN
               (SELECT id FROM products)""",
            (user_id,)
        )
        conn.commit()
        # Faqat faol mahsulotlar
        return conn.execute(
            """SELECT c.id, c.product_id, c.quantity,
                      p.name, p.price, p.photo_id, p.unit, p.prep_time,
                      CASE WHEN p.unit='kg'
                           THEN CAST(p.price * c.quantity / 10 AS INTEGER)
                           ELSE c.quantity * p.price
                      END as subtotal
               FROM cart c JOIN products p ON p.id=c.product_id
               WHERE c.user_id=? AND p.is_active=1""",
            (user_id,)
        ).fetchall()
    finally:
        conn.close()


def get_cart_total(user_id: int) -> int:
    """Jami narx — kg uchun quantity/10 × narx"""
    conn = get_conn()
    try:
        items = conn.execute(
            """SELECT c.quantity, p.price, p.unit
               FROM cart c JOIN products p ON p.id=c.product_id
               WHERE c.user_id=? AND p.is_active=1""",
            (user_id,)
        ).fetchall()
        total = 0
        for item in items:
            if item["unit"] == "kg":
                total += int(item["price"] * item["quantity"] / 10)
            else:
                total += item["price"] * item["quantity"]
        return total
    finally:
        conn.close()


def cart_plus(user_id: int, product_id: int):
    """kg uchun +5 (=0.5kg), boshqalar uchun +1"""
    conn = get_conn()
    try:
        p = conn.execute("SELECT unit FROM products WHERE id=?", (product_id,)).fetchone()
        step = 5 if p and p["unit"] == "kg" else 1
        conn.execute(
            "UPDATE cart SET quantity=quantity+? WHERE user_id=? AND product_id=?",
            (step, user_id, product_id)
        )
        conn.commit()
    finally:
        conn.close()


def cart_minus(user_id: int, product_id: int):
    """kg uchun -5 (=0.5kg), boshqalar uchun -1"""
    conn = get_conn()
    try:
        p = conn.execute("SELECT unit FROM products WHERE id=?", (product_id,)).fetchone()
        step = 5 if p and p["unit"] == "kg" else 1
        row = conn.execute(
            "SELECT quantity FROM cart WHERE user_id=? AND product_id=?",
            (user_id, product_id)
        ).fetchone()
        if row:
            new_qty = max(step, row["quantity"] - step)
            conn.execute(
                "UPDATE cart SET quantity=? WHERE user_id=? AND product_id=?",
                (new_qty, user_id, product_id)
            )
            conn.commit()
    finally:
        conn.close()


def cart_remove(user_id: int, product_id: int):
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM cart WHERE user_id=? AND product_id=?",
            (user_id, product_id)
        )
        conn.commit()
    finally:
        conn.close()


def clear_cart(user_id: int):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════
# BUYURTMALAR
# ══════════════════════════════════════════

def create_order(
    user_id: int, items_text: str, cart_total: int,
    delivery_type: str, delivery_pay: str,
    address: Optional[str], latitude: Optional[float], longitude: Optional[float],
    phone1: str, phone2: str,
    status: str = "waiting_payment"
) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO orders
               (user_id, items_text, cart_total, delivery_fee, total_price,
                delivery_type, delivery_pay, address, latitude, longitude,
                phone1, phone2, status, created_at)
               VALUES (?,?,?,0,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, items_text, cart_total, cart_total,
             delivery_type, delivery_pay, address, latitude, longitude,
             phone1, phone2, status, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def set_order_payment_photo(order_id: int, file_id: str):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE orders SET payment_photo=? WHERE id=?", (file_id, order_id)
        )
        conn.commit()
    finally:
        conn.close()


def set_delivery_fee(order_id: int, fee: int):
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE orders SET delivery_fee=?,
               total_price=cart_total+? WHERE id=?""",
            (fee, fee, order_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_order_status(order_id: int, status: str):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE orders SET status=? WHERE id=?", (status, order_id)
        )
        conn.commit()
    finally:
        conn.close()


def set_cancel_requested(order_id: int, val: int):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE orders SET cancel_requested=? WHERE id=?", (val, order_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_order(order_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM orders WHERE id=?", (order_id,)
        ).fetchone()
    finally:
        conn.close()


def get_user_orders(user_id: int) -> list:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (user_id,)
        ).fetchall()
    finally:
        conn.close()


def get_available_months() -> list:
    """Buyurtmalar mavjud bo'lgan oylar ro'yxati (YYYY-MM formatida)"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT DISTINCT substr(created_at, 1, 7) as month
               FROM orders
               ORDER BY month DESC"""
        ).fetchall()
        return [r["month"] for r in rows]
    finally:
        conn.close()


def get_monthly_stats(month: str) -> dict:
    """Berilgan oy (YYYY-MM) statistikasi"""
    conn = get_conn()
    try:
        from config import ADMIN_IDS
        placeholders = ",".join("?" * len(ADMIN_IDS))

        orders = conn.execute(
            """SELECT COUNT(*) as cnt,
                      COALESCE(SUM(total_price), 0) as total
               FROM orders
               WHERE substr(created_at,1,7)=?
                 AND status NOT IN ('cancelled','pending')""",
            (month,)
        ).fetchone()

        cancelled = conn.execute(
            "SELECT COUNT(*) as cnt FROM orders WHERE substr(created_at,1,7)=? AND status='cancelled'",
            (month,)
        ).fetchone()

        avg = conn.execute(
            """SELECT COALESCE(AVG(stars), 0) as avg
               FROM ratings
               WHERE substr(created_at,1,7)=?""",
            (month,)
        ).fetchone()

        new_users = conn.execute(
            f"""SELECT COUNT(*) as cnt FROM users
                WHERE substr(created_at,1,7)=?
                  AND telegram_id NOT IN ({placeholders})""",
            (month, *ADMIN_IDS)
        ).fetchone()

        top_users = conn.execute(
            """SELECT u.full_name, u.username, u.phone1,
                      COUNT(o.id) as order_cnt,
                      COALESCE(SUM(o.total_price),0) as spent
               FROM orders o
               JOIN users u ON u.telegram_id = o.user_id
               WHERE substr(o.created_at,1,7)=?
                 AND o.status NOT IN ('cancelled','pending')
               GROUP BY o.user_id
               ORDER BY spent DESC LIMIT 5""",
            (month,)
        ).fetchall()

        top_products = conn.execute(
            """SELECT p.name, COUNT(*) as cnt
               FROM orders o
               JOIN products p ON instr(o.items_text, p.name) > 0
               WHERE substr(o.created_at,1,7)=?
                 AND o.status NOT IN ('cancelled','pending')
               GROUP BY p.name
               ORDER BY cnt DESC LIMIT 5""",
            (month,)
        ).fetchall()

        return {
            "order_count": orders["cnt"] or 0,
            "total":       orders["total"] or 0,
            "cancelled":   cancelled["cnt"] or 0,
            "avg_rating":  round(avg["avg"] or 0, 1),
            "new_users":   new_users["cnt"] or 0,
            "top_users":   top_users,
            "top_products": top_products,
        }
    finally:
        conn.close()


def get_orders_by_month(month: str) -> list:
    """Berilgan oydagi barcha buyurtmalar"""
    conn = get_conn()
    try:
        return conn.execute(
            """SELECT * FROM orders
               WHERE substr(created_at,1,7)=?
               ORDER BY id DESC""",
            (month,)
        ).fetchall()
    finally:
        conn.close()


def delete_orders_by_month(month: str) -> int:
    """Berilgan oydagi buyurtmalarni o'chiradi, sonini qaytaradi"""
    conn = get_conn()
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) as cnt FROM orders WHERE substr(created_at,1,7)=?",
            (month,)
        ).fetchone()["cnt"]
        conn.execute(
            "DELETE FROM orders WHERE substr(created_at,1,7)=?", (month,)
        )
        conn.commit()
        return cnt
    finally:
        conn.close()


def get_weekly_stats() -> dict:
    """Haftalik statistika"""
    conn = get_conn()
    try:
        from datetime import datetime, timedelta
        today = datetime.now()
        week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")

        r = conn.execute(
            """SELECT COUNT(*) as order_count,
                      COALESCE(SUM(total_price),0) as total,
                      COALESCE(AVG(NULLIF(rating,0)),0) as avg_rating
               FROM orders
               WHERE status='delivered' AND created_at >= ?""",
            (week_ago,)
        ).fetchone()

        from config import ADMIN_IDS
        placeholders = ",".join("?" * len(ADMIN_IDS))
        new_users = conn.execute(
            f"SELECT COUNT(*) as cnt FROM users WHERE created_at >= ? AND telegram_id NOT IN ({placeholders})",
            (week_ago, *ADMIN_IDS)
        ).fetchone()["cnt"]

        # Top mahsulotlar
        top_products = conn.execute(
            """SELECT p.name, p.order_count
               FROM products p
               WHERE p.is_active=1
               ORDER BY p.order_count DESC LIMIT 3""",
        ).fetchall()

        return {
            "order_count": r["order_count"],
            "total": r["total"],
            "avg_rating": round(r["avg_rating"], 1),
            "new_users": new_users,
            "top_products": top_products,
            "week_ago": week_ago,
            "today": today.strftime("%Y-%m-%d"),
        }
    finally:
        conn.close()


def get_today_stats() -> dict:
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        orders = conn.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(total_price),0) as total
               FROM orders WHERE created_at LIKE ? AND status NOT IN ('cancelled','pending')""",
            (f"{today}%",)
        ).fetchone()
        avg = conn.execute(
            "SELECT AVG(stars) as avg FROM ratings WHERE created_at LIKE ?",
            (f"{today}%",)
        ).fetchone()
        from config import ADMIN_IDS
        placeholders = ",".join("?" * len(ADMIN_IDS))
        new_users = conn.execute(
            f"SELECT COUNT(*) as cnt FROM users WHERE created_at LIKE ? AND telegram_id NOT IN ({placeholders})",
            (f"{today}%", *ADMIN_IDS)
        ).fetchone()
        top_products = conn.execute(
            """SELECT name, order_count FROM products
               WHERE is_active=1 AND order_count > 0
               ORDER BY order_count DESC LIMIT 3"""
        ).fetchall()
        return {
            "order_count": orders["cnt"] or 0,
            "total":       orders["total"] or 0,
            "avg_rating":  round(avg["avg"] or 0, 1),
            "new_users":   new_users["cnt"] or 0,
            "top_products": top_products,
        }
    finally:
        conn.close()


# ══════════════════════════════════════════
# CHEGIRMALAR
# ══════════════════════════════════════════

def set_discount(user_id: int, dtype: str, amount: int):
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO discounts (user_id, type, amount, created_at)
               VALUES (?,?,?,?)""",
            (user_id, dtype, amount, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
    finally:
        conn.close()


def get_discount(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM discounts WHERE user_id=?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


def remove_discount(user_id: int):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM discounts WHERE user_id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def apply_discount(user_id: int, price: int) -> tuple:
    """Chegirmani qo'llaydi. (yangi_narx, chegirma_matni) qaytaradi"""
    disc = get_discount(user_id)
    if not disc:
        return price, ""
    if disc["type"] == "percent":
        amount = int(price * disc["amount"] / 100)
        new_price = price - amount
        text = f"🎁 Chegirma: -{disc['amount']}% (-{amount:,} so'm)"
    else:
        amount = disc["amount"]
        new_price = max(0, price - amount)
        text = f"🎁 Chegirma: -{amount:,} so'm"
    return new_price, text


# ══════════════════════════════════════════
# REYTING
# ══════════════════════════════════════════

def save_rating(user_id: int, order_id: int, stars: int):
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO ratings (user_id, order_id, stars, created_at)
               VALUES (?,?,?,?)""",
            (user_id, order_id, stars, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.execute(
            "UPDATE orders SET rating=? WHERE id=?", (stars, order_id)
        )
        conn.commit()
    finally:
        conn.close()
