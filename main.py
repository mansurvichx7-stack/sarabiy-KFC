"""
main.py — Sarabiy KFC Bot
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from typing import Any, Callable, Awaitable

from config import BOT_TOKEN, ADMIN_ID, ADMIN_IDS, CHANNEL_ID, CHANNEL_LINK, CHANNEL_NAME
from database import init_db, backup_db, get_weekly_stats
from handlers import start, menu, cart, order, contact, admin
from handlers.start import check_subscription, subscribe_kb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def daily_backup():
    """Har 24 soatda DB backup oladi"""
    while True:
        await asyncio.sleep(86400)
        backup_db()
        logger.info("✅ DB backup olindi")


async def weekly_stats(bot: Bot):
    """Har shanba kuni adminga haftalik statistika yuboradi"""
    from datetime import datetime, timedelta
    while True:
        now = datetime.now()
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.hour >= 9:
            days_until_saturday = 7
        next_saturday = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_until_saturday)
        wait_seconds = (next_saturday - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        try:
            stats = get_weekly_stats()
            top_text = ""
            medals = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(stats["top_products"]):
                top_text += f"\n{medals[i]} {p['name']} — {p['order_count']} ta"

            text = (
                f"📊 <b>Haftalik hisobot</b>\n"
                f"📅 {stats['week_ago']} — {stats['today']}\n\n"
                f"📦 Buyurtmalar: <b>{stats['order_count']} ta</b>\n"
                f"💰 Tushum: <b>{stats['total']:,} so'm</b>\n"
                f"⭐ O'rtacha reyting: <b>{stats['avg_rating']}</b>\n"
                f"👤 Yangi foydalanuvchilar: <b>{stats['new_users']} ta</b>\n\n"
                f"🏆 <b>Eng mashhur taomlar:</b>{top_text or chr(10)+'Malumot yoq'}"
            )
            for admin_id in ADMIN_IDS:
                await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
            logger.info("✅ Haftalik statistika yuborildi")
        except Exception as e:
            logger.error(f"Haftalik statistika xatosi: {e}")


async def check_night_menu(bot: Bot):
    """Har kuni ish vaqti tugashidan 30 daqiqa oldin tekshiradi"""
    from datetime import datetime, timedelta
    from database import get_conn as _gc

    while True:
        import config as _cfg
        WORK_END = _cfg.WORK_END

        if WORK_END is not None:
            now = datetime.now()
            check_hour = WORK_END - 1 if WORK_END > 0 else 23
            next_check = now.replace(hour=check_hour, minute=30, second=0, microsecond=0)
            if now >= next_check:
                next_check += timedelta(days=1)
            await asyncio.sleep((next_check - now).total_seconds())
        else:
            await asyncio.sleep(3600)
            continue

        try:
            conn = _gc()
            always_open = conn.execute(
                "SELECT COUNT(*) as cnt FROM categories WHERE is_active=1 AND always_open=1"
            ).fetchone()["cnt"]
            conn.close()

            if always_open == 0:
                import config as _cfg2
                we = _cfg2.WORK_END
                for admin_id in ADMIN_IDS:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"⚠️ <b>Diqqat!</b>\n\n"
                            f"Ish vaqti {we:02d}:00 da tugaydi.\n\n"
                            f"🌙 <b>\"Doim ochiq\" kategoriya yo'q!</b>\n"
                            f"Kechasi foydalanuvchilar menyu ko'ra olmaydi.\n\n"
                            f"🍽 Kategoriyalar → kategoriyani tanlang → 🌙 Doim ochiq qilish"
                        ),
                        parse_mode="HTML"
                    )
        except Exception as e:
            logger.error(f"Night menu check xatosi: {e}")


import time as _time
_sub_cache: dict = {}  # {user_id: timestamp} — obunali foydalanuvchilar cache
_SUB_CACHE_TTL = 3600  # 1 soat

class SubMiddleware(BaseMiddleware):
    """Kanal obuna tekshiruvi — Message va CallbackQuery uchun"""

    async def __call__(
        self,
        handler: Callable[[Update, dict], Awaitable[Any]],
        event: Update,
        data: dict
    ) -> Any:
        if not CHANNEL_ID:
            return await handler(event, data)

        # aiogram 3.x: event bu Update emas, balki Message yoki CallbackQuery
        # data["event_from_user"] — aiogram 3 da har doim mavjud
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # Admin tekshiruvi
        if user.id in ADMIN_IDS:
            return await handler(event, data)

        # check_sub callback — cacheni tozalab o'tkazib yuboramiz
        if hasattr(event, 'data') and event.data == "check_sub":
            _sub_cache.pop(user.id, None)
            return await handler(event, data)

        # /start komandasi — o'tkazib yuboramiz
        if hasattr(event, 'text') and event.text and event.text.startswith('/start'):
            return await handler(event, data)

        # Cache tekshiruvi — 1 soat ichida obunali bo'lsa qayta tekshirmaymiz
        now = _time.time()
        cached = _sub_cache.get(user.id)
        if cached and now - cached < _SUB_CACHE_TTL:
            return await handler(event, data)

        bot: Bot = data.get("bot")
        if not bot:
            return await handler(event, data)

        if not await check_subscription(bot, user.id):
            text = (
                f"📢 <b>Botdan foydalanish uchun</b>\n"
                f"<b>{CHANNEL_NAME}</b> kanaliga obuna bo'ling!\n\n"
                f"Obuna bo'lgandan keyin ✅ <b>Tekshirish</b> tugmasini bosing:"
            )
            kb = subscribe_kb(CHANNEL_LINK)
            try:
                if hasattr(event, 'data'):
                    # CallbackQuery
                    await event.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
                    await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
                else:
                    # Message
                    await event.answer(text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                pass
            return None

        # Obunali — cachega yozamiz
        _sub_cache[user.id] = now
        return await handler(event, data)


async def main():
    init_db()
    backup_db()
    logger.info("✅ Ma'lumotlar bazasi tayyor")

    # Bot restart bo'lganida osilib qolgan kechki buyurtmalarni bekor qilish
    try:
        from database import get_conn as _gc
        conn = _gc()
        stale = conn.execute(
            "SELECT id, user_id FROM orders WHERE status='pending'"
        ).fetchall()
        for o in stale:
            conn.execute("UPDATE orders SET status='cancelled' WHERE id=?", (o["id"],))
        conn.commit()
        conn.close()
        if stale:
            logger.info(f"⚠️ {len(stale)} ta osilib qolgan kechki buyurtma bekor qilindi")
    except Exception as e:
        logger.error(f"Startup cleanup xatosi: {e}")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Routerlar (admin birinchi)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(cart.router)
    dp.include_router(order.router)
    dp.include_router(contact.router)

    # Xatolik logi
    from aiogram.types import ErrorEvent
    @dp.errors()
    async def on_error(event: ErrorEvent):
        logger.error(f"Xatolik: {event.exception}", exc_info=True)
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🚨 <b>Xatolik!</b>\n\n"
                f"<code>{type(event.exception).__name__}: {event.exception}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    # Vaqtincha majburiy obuna o'chirilgan
    dp.message.middleware(SubMiddleware())
    dp.callback_query.middleware(SubMiddleware())

    logger.info("🚀 Sarabiy KFC Bot ishga tushmoqda...")
    try:
        asyncio.create_task(daily_backup())
        asyncio.create_task(weekly_stats(bot))
        asyncio.create_task(check_night_menu(bot))
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
