
import asyncio
import logging
import re
import sqlite3
from datetime import datetime, timedelta, date
from typing import Optional

from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


BOT_TOKEN    = "8760297319:AAHdKthxeUHiTRzsL3gMaucrSiuqjYVOJxA"
BOT_USERNAME = "@joyicelandbot"
BOT_NAME     = "Joyland"

OWNER_IDS = [7797867149, 6980874774]

DB_FILE = "joyland.db"

BULAN_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei",     6: "Juni",     7: "Juli",  8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}
BULAN_EMOJI = {
    1: "❄️", 2: "💝", 3: "🌸", 4: "🌷",
    5: "🌿", 6: "☀️", 7: "🌴", 8: "🍦",
    9: "🍂", 10: "🎃", 11: "🍁", 12: "🎄",
}


(
    S_IDLE,
    S_UPLOAD_BUKTI,
    S_CHAT_LAPORAN,
    S_ADMIN_REPLY,
    S_ADMIN_SEND_MSG_TF,
    S_BUTTON_BUILDER,
    S_EDIT_WELCOME_TEXT,
    S_EDIT_WELCOME_MEDIA,
    S_EDIT_PAYMENT_TEXT,
    S_EDIT_PAYMENT_MEDIA,
    S_EDIT_VIP_TEXT,
    S_EDIT_VIP_MEDIA,
    S_EDIT_VIP_LINK,
    S_BROADCAST,
    S_ADD_ADMIN,
    S_BROADCAST_USERNAME,
    S_EDIT_REMINDER_TEXT_1,
    S_EDIT_REMINDER_TEXT_2,
) = range(18)


logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("joyland.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id         INTEGER PRIMARY KEY,
                username        TEXT DEFAULT '',
                first_name      TEXT DEFAULT '',
                last_name       TEXT DEFAULT '',
                is_banned       INTEGER DEFAULT 0,
                ban_reason      TEXT DEFAULT '',
                membership_type TEXT DEFAULT '',
                membership_acc_at TEXT DEFAULT '',
                vip_start_date  TEXT DEFAULT '',
                vip_end_date    TEXT DEFAULT '',
                joined_at       TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS admins (
                admin_id          INTEGER PRIMARY KEY,
                username          TEXT DEFAULT '',
                added_by          INTEGER,
                perm_acc_tf       INTEGER DEFAULT 1,
                perm_reply_chat   INTEGER DEFAULT 1,
                perm_edit_bot     INTEGER DEFAULT 0,
                perm_tambah_admin INTEGER DEFAULT 0,
                perm_broadcast    INTEGER DEFAULT 0,
                added_at          TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS custom_buttons (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                button_text  TEXT NOT NULL,
                button_type  TEXT NOT NULL,
                button_value TEXT NOT NULL,
                created_by   INTEGER,
                created_at   TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS pending_tf (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                file_id      TEXT NOT NULL,
                paket_type   TEXT DEFAULT '',
                status       TEXT DEFAULT 'pending',
                processed_by INTEGER DEFAULT 0,
                created_at   TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS admin_tf_notif (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                tf_id    INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                msg_id   INTEGER NOT NULL,
                chat_id  INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                user_msg   TEXT NOT NULL,
                status     TEXT DEFAULT 'open',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS admin_chat_notif (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                admin_id   INTEGER NOT NULL,
                msg_id     INTEGER NOT NULL,
                chat_id    INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS vip_links (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                link       TEXT NOT NULL,
                is_active  INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS used_links (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tf_id   INTEGER NOT NULL,
                used_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(user_id, tf_id)
            );

            CREATE TABLE IF NOT EXISTS sent_reminders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                paket_type   TEXT NOT NULL,
                reminder_day INTEGER NOT NULL,
                sent_at      TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(user_id, paket_type, reminder_day)
            );

            CREATE TABLE IF NOT EXISTS subscription_periods (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                paket_type    TEXT NOT NULL,
                periode_bulan TEXT NOT NULL,
                start_periode TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(user_id, paket_type, start_periode, periode_bulan)
            );
        """)

        for alter_sql in [
            "ALTER TABLE users ADD COLUMN membership_type TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN membership_acc_at TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN vip_start_date TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN vip_end_date TEXT DEFAULT ''",
            "ALTER TABLE pending_tf ADD COLUMN paket_type TEXT DEFAULT ''",
        ]:
            try:
                conn.execute(alter_sql)
            except Exception:
                pass

        defaults = {
            "welcome_text": (
                "🎡 *Welcome to Joyland\\!*\n\n"
                "Halo Kak\\! Selamat datang di pusat layanan *VIP Access*\\.\n"
                "Dapatkan update tercepat dan kualitas terbaik hanya di sini\\.\n\n"
                "_Pilih menu di bawah untuk melanjutkan_ 👇"
            ),
            "welcome_media": "",
            "payment_text": (
                "💳 *CARA BERLANGGANAN*\n\n"
                "1\\. Transfer sesuai nominal paket\n"
                "2\\. Kirim bukti transfer via tombol *Kirim Bukti TF*\n"
                "3\\. Admin memverifikasi dalam 1\\-5 menit\n"
                "4\\. Link VIP dikirim otomatis setelah disetujui\\!\n\n"
                "💰 *Paket Tersedia:*\n"
                "• 1 Bulan — Akses penuh 30 hari\n"
                "• 2 Bulan — Akses penuh 60 hari \\(Lebih Hemat\\!\\)"
            ),
            "payment_media": "",
            "vip_info_text": (
                "📚 *INFO VIP ACCESS*\n\n"
                "Dapatkan akses eksklusif ke konten premium Joyland\\!\n\n"
                "✨ *Keunggulan Member VIP:*\n"
                "• Akses konten eksklusif setiap hari\n"
                "• Update tercepat di channel VIP\n"
                "• Kualitas konten terbaik \\& terjamin\n"
                "• Support admin responsif 24/7\n\n"
                "💰 *Paket Tersedia:*\n"
                "• 1 Bulan — Akses penuh 30 hari\n"
                "• 2 Bulan — Akses penuh 60 hari \\(Lebih Hemat\\!\\)"
            ),
            "vip_info_media": "",
            "maintenance_mode": "0",
            "auto_delete_button": "1",
            "bot_version": "6.0",
            "reminder_days_1_bulan": "3",
            "reminder_days_2_bulan": "3",
            "reminder_text_1_bulan": (
                "🔔 PENGINGAT MASA AKTIF VIP\n\n"
                "Halo Kak {nama}! Kami ingin menginfokan bahwa masa langganan {paket} kamu "
                "akan berakhir pada {tanggal_exp}.\n\n"
                "Yuk perpanjang sekarang agar akses VIP kamu tidak terputus! 🙏"
            ),
            "reminder_text_2_bulan": (
                "🔔 PENGINGAT MASA AKTIF VIP\n\n"
                "Halo Kak {nama}! Kami ingin menginfokan bahwa masa langganan {paket} kamu "
                "akan berakhir pada {tanggal_exp}.\n\n"
                "Yuk perpanjang sekarang agar akses VIP kamu tidak terputus! 🙏"
            ),
        }

        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )

        _migrate_existing_to_periods(conn)

    logger.info("✅ Database OK (v6.0)")


def _migrate_existing_to_periods(conn: sqlite3.Connection):
    """Buat baris subscription_periods untuk member lama yang belum punya data periode."""
    rows = conn.execute(
        "SELECT user_id, membership_type, vip_start_date FROM users "
        "WHERE membership_type != '' AND vip_start_date != '' AND vip_start_date IS NOT NULL"
    ).fetchall()
    for row in rows:
        uid        = row["user_id"]
        paket_type = row["membership_type"]
        start_raw  = row["vip_start_date"]
        if not start_raw:
            continue
        try:
            start_month = start_raw[:7]
            _insert_period_rows(conn, uid, paket_type, start_month)
        except Exception:
            pass


def _insert_period_rows(conn: sqlite3.Connection, user_id: int, paket_type: str, start_month: str):
    """Masukkan baris subscription_periods sesuai jumlah bulan paket."""
    n_months = 2 if paket_type == "2_bulan" else 1
    try:
        y, m = int(start_month[:4]), int(start_month[5:7])
    except ValueError:
        return
    for i in range(n_months):
        month_offset = m + i - 1
        cy = y + month_offset // 12
        cm = month_offset % 12 + 1
        periode = f"{cy:04d}-{cm:02d}"
        try:
            conn.execute(
                "INSERT OR IGNORE INTO subscription_periods "
                "(user_id, paket_type, periode_bulan, start_periode) VALUES (?,?,?,?)",
                (user_id, paket_type, periode, start_month),
            )
        except Exception:
            pass



def cfg_get(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def cfg_set(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )



def upsert_user(user):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?,?,?,?)",
            (user.id, user.username or "", user.first_name or "", user.last_name or ""),
        )
        conn.execute(
            "UPDATE users SET username=?, first_name=?, last_name=? WHERE user_id=?",
            (user.username or "", user.first_name or "", user.last_name or "", user.id),
        )


def is_banned(uid: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT is_banned FROM users WHERE user_id=?", (uid,)).fetchone()
    return bool(row and row["is_banned"])


def ban_user(uid: int, reason: str = ""):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=1, ban_reason=? WHERE user_id=?", (reason, uid))


def unban_user(uid: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=0, ban_reason='' WHERE user_id=?", (uid,))


def get_user_info(uid: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    return dict(row) if row else None


def count_users() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=0").fetchone()[0]


def count_banned() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]


def all_user_ids() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
    return [r["user_id"] for r in rows]


def get_users_paginated(page: int, limit: int = 10) -> list:
    offset = (page - 1) * limit
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE is_banned=0 ORDER BY joined_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    return [dict(r) for r in rows]


def get_banned_paginated(page: int, limit: int = 10) -> list:
    offset = (page - 1) * limit
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE is_banned=1 ORDER BY joined_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    return [dict(r) for r in rows]


def get_user_id_by_username(username: str) -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM users WHERE LOWER(username)=LOWER(?)",
            (username.lstrip("@"),)
        ).fetchone()
    return row["user_id"] if row else None



def update_user_membership(user_id: int, paket_type: str):
    """
    Set membership + vip_start_date + vip_end_date saat TF di-ACC.
    Juga membuat baris subscription_periods untuk tiap bulan kalender paket.
    """
    today     = datetime.now()
    start_str = today.strftime("%Y-%m-%d")
    if paket_type == "1_bulan":
        end_date = today + timedelta(days=30)
    elif paket_type == "2_bulan":
        end_date = today + timedelta(days=60)
    else:
        end_date = today + timedelta(days=30)
    end_str = end_date.strftime("%Y-%m-%d")

    with get_conn() as conn:
        conn.execute(
            """UPDATE users
               SET membership_type=?,
                   membership_acc_at=datetime('now','localtime'),
                   vip_start_date=?,
                   vip_end_date=?
               WHERE user_id=?""",
            (paket_type, start_str, end_str, user_id),
        )
        start_month = today.strftime("%Y-%m")
        _insert_period_rows(conn, user_id, paket_type, start_month)

    with get_conn() as conn:
        conn.execute(
            "DELETE FROM sent_reminders WHERE user_id=? AND paket_type=?",
            (user_id, paket_type)
        )


def count_members_by_type(paket_type: str) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE membership_type=? AND is_banned=0",
            (paket_type,)
        ).fetchone()[0]


def get_member_ids_by_type(paket_type: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id FROM users WHERE membership_type=? AND is_banned=0",
            (paket_type,)
        ).fetchall()
    return [r["user_id"] for r in rows]


def get_members_paginated(paket_type: str, page: int, limit: int = 10) -> list:
    offset = (page - 1) * limit
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE membership_type=? AND is_banned=0 "
            "ORDER BY membership_acc_at DESC LIMIT ? OFFSET ?",
            (paket_type, limit, offset)
        ).fetchall()
    return [dict(r) for r in rows]


def get_members_for_reminder(paket_type: str) -> list:
    """Ambil semua member aktif paket ini yang punya vip_end_date."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT user_id, first_name, last_name, username, membership_type, vip_end_date
               FROM users
               WHERE membership_type=? AND is_banned=0
                 AND vip_end_date != '' AND vip_end_date IS NOT NULL""",
            (paket_type,)
        ).fetchall()
    return [dict(r) for r in rows]



def get_distinct_periods(paket_type: str) -> list:
    """
    Kembalikan list start_periode unik yang ada di subscription_periods
    untuk paket_type tertentu, diurutkan terbaru dulu.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT sp.start_periode
               FROM subscription_periods sp
               JOIN users u ON u.user_id = sp.user_id
               WHERE sp.paket_type=? AND u.is_banned=0
               ORDER BY sp.start_periode DESC""",
            (paket_type,)
        ).fetchall()
    return [r["start_periode"] for r in rows]


def count_users_by_period(paket_type: str, start_periode: str) -> int:
    """Hitung user unik untuk start_periode tertentu."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT COUNT(DISTINCT sp.user_id)
               FROM subscription_periods sp
               JOIN users u ON u.user_id = sp.user_id
               WHERE sp.paket_type=? AND sp.start_periode=? AND u.is_banned=0""",
            (paket_type, start_periode)
        ).fetchone()[0]


def get_user_ids_by_period(paket_type: str, start_periode: str) -> list:
    """Ambil list user_id untuk periode tertentu."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT sp.user_id
               FROM subscription_periods sp
               JOIN users u ON u.user_id = sp.user_id
               WHERE sp.paket_type=? AND sp.start_periode=? AND u.is_banned=0""",
            (paket_type, start_periode)
        ).fetchall()
    return [r["user_id"] for r in rows]


def get_users_detail_by_period(paket_type: str, start_periode: str,
                                page: int = 1, limit: int = 5) -> list:
    """Ambil detail user untuk periode tertentu (paginated)."""
    offset = (page - 1) * limit
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT u.user_id, u.username, u.first_name, u.last_name,
                      u.vip_end_date, u.vip_start_date
               FROM subscription_periods sp
               JOIN users u ON u.user_id = sp.user_id
               WHERE sp.paket_type=? AND sp.start_periode=? AND u.is_banned=0
               ORDER BY u.first_name ASC
               LIMIT ? OFFSET ?""",
            (paket_type, start_periode, limit, offset)
        ).fetchall()
    return [dict(r) for r in rows]



def is_owner(uid: int) -> bool:
    return uid in OWNER_IDS


def is_admin(uid: int) -> bool:
    if is_owner(uid):
        return True
    with get_conn() as conn:
        return bool(conn.execute("SELECT 1 FROM admins WHERE admin_id=?", (uid,)).fetchone())


def has_perm(uid: int, perm: str) -> bool:
    if is_owner(uid):
        return True
    safe_perms = {
        "perm_acc_tf", "perm_reply_chat", "perm_edit_bot",
        "perm_tambah_admin", "perm_broadcast",
    }
    if perm not in safe_perms:
        return False
    with get_conn() as conn:
        row = conn.execute(f"SELECT {perm} FROM admins WHERE admin_id=?", (uid,)).fetchone()
    return bool(row and row[perm])


def add_admin(admin_id: int, added_by: int, username: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO admins (admin_id, added_by, username) VALUES (?,?,?)",
            (admin_id, added_by, username),
        )


def remove_admin(admin_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM admins WHERE admin_id=?", (admin_id,))


def count_admins() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]


def all_admins() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM admins").fetchall()
    return [dict(r) for r in rows]


def get_admin_info(admin_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM admins WHERE admin_id=?", (admin_id,)).fetchone()
    return dict(row) if row else None


def toggle_admin_perm(admin_id: int, perm: str):
    safe_perms = {
        "perm_acc_tf", "perm_reply_chat", "perm_edit_bot",
        "perm_tambah_admin", "perm_broadcast",
    }
    if perm not in safe_perms:
        return
    with get_conn() as conn:
        conn.execute(f"UPDATE admins SET {perm} = 1 - {perm} WHERE admin_id=?", (admin_id,))



def get_custom_buttons() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM custom_buttons ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def add_custom_button(text: str, btype: str, value: str, uid: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO custom_buttons (button_text, button_type, button_value, created_by) VALUES (?,?,?,?)",
            (text, btype, value, uid),
        )


def del_custom_button(bid: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM custom_buttons WHERE id=?", (bid,))



def get_active_vip_link() -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM vip_links WHERE is_active=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def set_vip_link(link: str, uid: int):
    with get_conn() as conn:
        conn.execute("UPDATE vip_links SET is_active=0")
        conn.execute("INSERT INTO vip_links (link, created_by) VALUES (?,?)", (link, uid))



def create_tf(user_id: int, file_id: str, paket_type: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO pending_tf (user_id, file_id, paket_type) VALUES (?,?,?)",
            (user_id, file_id, paket_type)
        )
        return cur.lastrowid


def save_admin_tf_notif(tf_id: int, admin_id: int, msg_id: int, chat_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO admin_tf_notif (tf_id, admin_id, msg_id, chat_id) VALUES (?,?,?,?)",
            (tf_id, admin_id, msg_id, chat_id),
        )


def get_tf(tf_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM pending_tf WHERE id=?", (tf_id,)).fetchone()
    return dict(row) if row else None


def get_tf_admin_notifs(tf_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM admin_tf_notif WHERE tf_id=?", (tf_id,)).fetchall()
    return [dict(r) for r in rows]


def update_tf_status(tf_id: int, status: str, by: int = 0):
    with get_conn() as conn:
        conn.execute(
            "UPDATE pending_tf SET status=?, processed_by=? WHERE id=?", (status, by, tf_id)
        )


def count_pending_tf() -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM pending_tf WHERE status='pending'"
        ).fetchone()[0]


def get_pending_tf_paginated(page: int, limit: int = 5) -> list:
    offset = (page - 1) * limit
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.*, u.first_name, u.last_name, u.username
               FROM pending_tf p
               LEFT JOIN users u ON u.user_id = p.user_id
               WHERE p.status = 'pending'
               ORDER BY p.created_at ASC
               LIMIT ? OFFSET ?""",
            (limit, offset)
        ).fetchall()
    return [dict(r) for r in rows]


def mark_link_used(user_id: int, tf_id: int) -> bool:
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO used_links (user_id, tf_id) VALUES (?,?)", (user_id, tf_id)
            )
        return True
    except sqlite3.IntegrityError:
        return False



def create_chat_session(user_id: int, msg: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO chat_sessions (user_id, user_msg) VALUES (?,?)", (user_id, msg)
        )
        return cur.lastrowid


def save_admin_chat_notif(session_id: int, admin_id: int, msg_id: int, chat_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO admin_chat_notif (session_id, admin_id, msg_id, chat_id) VALUES (?,?,?,?)",
            (session_id, admin_id, msg_id, chat_id),
        )


def get_chat_session(sid: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM chat_sessions WHERE id=?", (sid,)).fetchone()
    return dict(row) if row else None


def get_chat_admin_notifs(sid: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM admin_chat_notif WHERE session_id=?", (sid,)
        ).fetchall()
    return [dict(r) for r in rows]


def close_chat_session(sid: int):
    with get_conn() as conn:
        conn.execute("UPDATE chat_sessions SET status='closed' WHERE id=?", (sid,))


def count_pending_chat() -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM chat_sessions WHERE status='open'"
        ).fetchone()[0]


def get_pending_chat_paginated(page: int, limit: int = 5) -> list:
    offset = (page - 1) * limit
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT cs.*, u.first_name, u.last_name, u.username
               FROM chat_sessions cs
               LEFT JOIN users u ON u.user_id = cs.user_id
               WHERE cs.status = 'open'
               ORDER BY cs.created_at ASC
               LIMIT ? OFFSET ?""",
            (limit, offset)
        ).fetchall()
    return [dict(r) for r in rows]



def get_reminder_days(paket_type: str) -> list:
    """Kembalikan list integer hari pengingat, misal [3, 1, 0]."""
    raw = cfg_get(f"reminder_days_{paket_type}", "3")
    days = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            days.append(int(part))
    return sorted(set(days), reverse=True)


def has_reminder_sent(user_id: int, paket_type: str, day: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM sent_reminders WHERE user_id=? AND paket_type=? AND reminder_day=?",
            (user_id, paket_type, day)
        ).fetchone()
    return row is not None


def mark_reminder_sent(user_id: int, paket_type: str, day: int):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sent_reminders (user_id, paket_type, reminder_day) VALUES (?,?,?)",
                (user_id, paket_type, day)
            )
    except Exception:
        pass


def format_reminder_text(template: str, nama: str, paket: str, tanggal_exp: str) -> str:
    return (
        template
        .replace("{nama}", nama)
        .replace("{paket}", paket)
        .replace("{tanggal_exp}", tanggal_exp)
    )



def sanitize_text(text) -> str:
    """
    Hapus karakter kontrol berbahaya (null bytes, BEL, dll) yang bisa
    menyebabkan error parse Telegram.  Newline & tab tetap dipertahankan.
    """
    text = str(text) if text is not None else ""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]', '', text)
    return text


def mdescape(text) -> str:
    """Escape teks untuk MarkdownV2 Telegram, termasuk sanitasi simbol berbahaya."""
    text = sanitize_text(text)
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def html_escape(text) -> str:
    """Escape teks untuk HTML Telegram, termasuk sanitasi simbol berbahaya."""
    text = sanitize_text(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def safe_display_name(first: str = "", last: str = "", username: str = "",
                       fallback: str = "Unknown") -> str:
    """
    Kembalikan nama tampilan yang sudah dibersihkan dari semua simbol berbahaya.
    Urutan prioritas: first+last → username → fallback.
    """
    name = (sanitize_text(first) + " " + sanitize_text(last)).strip()
    if name:
        return name
    if username:
        return sanitize_text(username.lstrip("@"))
    return fallback


def time_ago(dt_str: str) -> str:
    try:
        dt = datetime.strptime(dt_str[:19], "%Y-%m-%d %H:%M:%S")
        diff = datetime.now() - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return f"{secs} detik lalu"
        elif secs < 3600:
            return f"{secs // 60} menit lalu"
        elif secs < 86400:
            return f"{secs // 3600} jam lalu"
        else:
            return f"{secs // 86400} hari lalu"
    except Exception:
        return dt_str


def _label_periode(start_periode: str, paket_type: str) -> str:
    """Kembalikan label periode seperti 'JUNI 2026' atau 'JUNI - JULI 2026'."""
    try:
        y, m = int(start_periode[:4]), int(start_periode[5:7])
    except (ValueError, IndexError):
        return start_periode
    nama_bulan = BULAN_ID.get(m, f"{m:02d}")
    if paket_type == "2_bulan":
        m2 = m % 12 + 1
        y2 = y + (1 if m == 12 else 0)
        nama_bulan2 = BULAN_ID.get(m2, f"{m2:02d}")
        return f"{nama_bulan.upper()} - {nama_bulan2.upper()} {y}"
    return f"{nama_bulan.upper()} {y}"


def _emoji_periode(start_periode: str) -> str:
    """Kembalikan emoji sesuai bulan awal periode."""
    try:
        m = int(start_periode[5:7])
    except (ValueError, IndexError):
        return "🗓"
    return BULAN_EMOJI.get(m, "🗓")


def _status_periode(start_periode: str, paket_type: str) -> str:
    """Deteksi apakah periode sedang berjalan, akan datang, atau sudah lewat."""
    today_ym = datetime.now().strftime("%Y-%m")
    try:
        y, m = int(start_periode[:4]), int(start_periode[5:7])
    except (ValueError, IndexError):
        return "❓ Tidak Diketahui"
    n_months = 2 if paket_type == "2_bulan" else 1
    end_m_offset = m + n_months - 2
    ey = y + end_m_offset // 12
    em = end_m_offset % 12 + 1
    end_ym = f"{ey:04d}-{em:02d}"
    if today_ym < start_periode:
        return "⏳ Akan Datang"
    elif today_ym > end_ym:
        return "✅ Selesai"
    else:
        return "🟢 Sedang Berjalan"



def kb_user(custom_btns: list) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("📚 Info VIP", callback_data="u:info_vip"),
            InlineKeyboardButton("💳 Cara Langganan", callback_data="u:cara_langganan"),
        ],
        [
            InlineKeyboardButton("📨 Kirim Bukti TF", callback_data="u:kirim_bukti"),
            InlineKeyboardButton("💬 Hubungi Admin", callback_data="u:hubungi_admin"),
        ],
    ]
    buf = []
    for btn in custom_btns:
        if btn["button_type"] == "url":
            buf.append(InlineKeyboardButton(btn["button_text"], url=btn["button_value"]))
        else:
            buf.append(InlineKeyboardButton(btn["button_text"], callback_data=f"u:custom:{btn['id']}"))
        if len(buf) == 2:
            rows.append(buf)
            buf = []
    if buf:
        rows.append(buf)
    return InlineKeyboardMarkup(rows)


def kb_owner() -> InlineKeyboardMarkup:
    n_tf   = count_pending_tf()
    n_chat = count_pending_chat()
    tf_label   = f"📋 Antrean TF ({n_tf})" + (" ⚠️" if n_tf > 0 else "")
    chat_label = f"💬 Chat Belum Dibalas ({n_chat})" + (" ⚠️" if n_chat > 0 else "")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(tf_label,   callback_data="o:pending_tf_list:1"),
            InlineKeyboardButton(chat_label, callback_data="o:pending_chat_list:1"),
        ],
        [InlineKeyboardButton("⏰ Atur Pengingat VIP", callback_data="o:reminder_settings")],
        [
            InlineKeyboardButton("👥 Kelola Membership",  callback_data="o:kelola_membership"),
            InlineKeyboardButton("📢 Broadcast Center",   callback_data="o:broadcast_system"),
        ],
        [
            InlineKeyboardButton("🖼 Edit Welcome & Media", callback_data="o:edit_welcome"),
            InlineKeyboardButton("🔗 Button Builder",       callback_data="o:button_builder"),
        ],
        [
            InlineKeyboardButton("💳 Atur Payment",    callback_data="o:edit_payment"),
            InlineKeyboardButton("🔑 Update Link VIP", callback_data="o:update_vip"),
        ],
        [InlineKeyboardButton("📚 Edit Info VIP", callback_data="o:edit_vip_info")],
        [
            InlineKeyboardButton("👥 Kelola Admin",       callback_data="o:kelola_admin"),
            InlineKeyboardButton("⚙️ Pengaturan Sistem", callback_data="o:settings"),
        ],
        [InlineKeyboardButton("🌐 Preview Tampilan User", callback_data="o:preview")],
        [InlineKeyboardButton("👥 Daftar Pengguna", callback_data="o:users:1")],
        [InlineKeyboardButton("🚫 Daftar Ban",      callback_data="o:banned_list:1")],
    ])


def kb_admin() -> InlineKeyboardMarkup:
    n_tf   = count_pending_tf()
    n_chat = count_pending_chat()
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📋 Pending TF ({n_tf})",    callback_data="a:pending_tf_list:1"),
            InlineKeyboardButton(f"💬 Chat Masuk ({n_chat})",  callback_data="a:pending_chat_list:1"),
        ],
        [
            InlineKeyboardButton("🔑 Update Link VIP", callback_data="a:update_vip"),
            InlineKeyboardButton("📢 Broadcast",       callback_data="a:broadcast"),
        ],
        [InlineKeyboardButton("📊 Statistik", callback_data="a:statistik")],
    ])


def kb_back(data: str = "nav:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data=data)]])



async def safe_edit(
    query: CallbackQuery,
    text: str,
    keyboard=None,
    protect: bool = False,
    parse_mode: str = ParseMode.MARKDOWN_V2,
):
    try:
        if query.message.photo:
            await query.message.edit_caption(
                caption=text, parse_mode=parse_mode, reply_markup=keyboard
            )
        else:
            await query.message.edit_text(
                text=text, parse_mode=parse_mode, reply_markup=keyboard
            )
    except BadRequest:
        await query.message.reply_text(
            text=text, parse_mode=parse_mode,
            reply_markup=keyboard, protect_content=protect,
        )


async def safe_edit_html(query: CallbackQuery, text: str, keyboard=None, protect: bool = False):
    await safe_edit(query, text, keyboard, protect, parse_mode=ParseMode.HTML)



async def send_owner_menu(target, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    admins = all_admins()
    admin_str = (
        ", ".join(
            f"@{a['username']}" if a.get("username") else str(a["admin_id"])
            for a in admins
        ) or "—"
    )
    m1     = count_members_by_type("1_bulan")
    m2     = count_members_by_type("2_bulan")
    n_tf   = count_pending_tf()
    n_chat = count_pending_chat()

    r1_days = cfg_get("reminder_days_1_bulan", "3")
    r2_days = cfg_get("reminder_days_2_bulan", "3")

    def days_label(raw: str) -> str:
        days = [d.strip() for d in raw.split(",") if d.strip().isdigit()]
        labels = [("Hari-H" if d == "0" else f"H-{d}") for d in days]
        return ", ".join(labels) if labels else "Tidak diatur"

    text = (
        f"👑 *Selamat Bekerja, Owner Mutlak\\!*\n\n"
        f"📊 *Statistik {mdescape(BOT_NAME)}:*\n"
        f"• Total User: *{count_users():,}*\n"
        f"• Member 1 Bulan: *{m1:,}*\n"
        f"• Member 2 Bulan: *{m2:,}*\n"
        f"• Staf Aktif: *{count_admins()}* — {mdescape(admin_str)}\n"
        f"• Pending TF: *{n_tf}*" + (" ⚠️" if n_tf > 0 else "") + "\n"
        f"• Chat Belum Dibalas: *{n_chat}*" + (" ⚠️" if n_chat > 0 else "") + "\n\n"
        f"⏰ *Jadwal Pengingat VIP:*\n"
        f"• Paket 1 Bulan: _{mdescape(days_label(r1_days))}_\n"
        f"• Paket 2 Bulan: _{mdescape(days_label(r2_days))}_\n\n"
        f"🕐 {mdescape(datetime.now().strftime('%d %b %Y, %H:%M'))} WIB"
    )
    kb = kb_owner()

    if isinstance(target, CallbackQuery) and edit:
        await safe_edit(target, text, kb)
    else:
        msg_obj = target.message if isinstance(target, CallbackQuery) else target
        media = cfg_get("welcome_media")
        if media:
            try:
                await msg_obj.reply_photo(
                    photo=media, caption=text,
                    parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb,
                )
                return
            except TelegramError:
                pass
        await msg_obj.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)


async def send_admin_menu(target, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    text = f"🛡 *Panel Admin {mdescape(BOT_NAME)}*\n\nPilih aksi di bawah:"
    kb   = kb_admin()
    if isinstance(target, CallbackQuery) and edit:
        await safe_edit(target, text, kb)
    else:
        msg_obj = target.message if isinstance(target, CallbackQuery) else target
        await msg_obj.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)


async def send_user_menu(target, context: ContextTypes.DEFAULT_TYPE, edit: bool = False, protect: bool = True):
    custom_btns = get_custom_buttons()
    text  = cfg_get("welcome_text")
    media = cfg_get("welcome_media")
    kb    = kb_user(custom_btns)

    if isinstance(target, CallbackQuery) and edit:
        await safe_edit(target, text, kb, protect=protect)
        return

    msg_obj = target.message if isinstance(target, CallbackQuery) else target
    if media:
        try:
            await msg_obj.reply_photo(
                photo=media, caption=text,
                parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb, protect_content=protect,
            )
            return
        except TelegramError:
            pass
    await msg_obj.reply_text(
        text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb, protect_content=protect
    )



async def show_user_list(query: CallbackQuery, page: int = 1):
    limit = 10
    users = get_users_paginated(page, limit)
    total = count_users()
    total_pages = max(1, (total + limit - 1) // limit)

    if not users and page == 1:
        await query.answer("Belum ada pengguna terdaftar.", show_alert=True)
        return

    text = f"👥 *DAFTAR PENGGUNA BOT*\nHal: {page}/{total_pages} \\| Total: {total}\n\n"
    for i, u in enumerate(users, 1):
        name  = f"{u['first_name']} {u['last_name']}".strip() or "Unknown"
        uname = f"@{u['username']}" if u['username'] else "no username"
        idx   = i + (page - 1) * limit
        text += f"{idx}\\. *{mdescape(name)}* \\({mdescape(uname)}\\)\n└ ID: `{u['user_id']}`\n\n"

    nav = _nav_row(page, total_pages, "o:users")
    kb  = InlineKeyboardMarkup([nav, [InlineKeyboardButton("🔙 Kembali ke Panel", callback_data="nav:main")]])
    await safe_edit(query, text, kb)


async def show_banned_list(query: CallbackQuery, page: int = 1):
    limit = 10
    users = get_banned_paginated(page, limit)
    total = count_banned()
    total_pages = max(1, (total + limit - 1) // limit)

    if not users and page == 1:
        await query.answer("Belum ada user yang di-ban.", show_alert=True)
        return

    text = f"🚫 *DAFTAR USER TER\\-BAN*\nHal: {page}/{total_pages} \\| Total: {total}\n\n"
    for i, u in enumerate(users, 1):
        name   = f"{u['first_name']} {u['last_name']}".strip() or "Unknown"
        uname  = f"@{u['username']}" if u['username'] else "no username"
        reason = u['ban_reason'] or 'Tidak ada'
        idx    = i + (page - 1) * limit
        text  += f"{idx}\\. *{mdescape(name)}* \\({mdescape(uname)}\\)\n"
        text  += f"└ ID: `{u['user_id']}`\n"
        text  += f"└ Alasan: _{mdescape(reason)}_\n\n"

    nav = _nav_row(page, total_pages, "o:banned_list")
    kb  = InlineKeyboardMarkup([nav, [InlineKeyboardButton("🔙 Kembali", callback_data="nav:main")]])
    await safe_edit(query, text, kb)


async def show_member_list(query: CallbackQuery, paket_type: str, page: int = 1):
    limit = 10
    users = get_members_paginated(paket_type, page, limit)
    total = count_members_by_type(paket_type)
    total_pages = max(1, (total + limit - 1) // limit)
    paket_label = "1 Bulan" if paket_type == "1_bulan" else "2 Bulan"
    slug = "1" if paket_type == "1_bulan" else "2"

    if not users and page == 1:
        await query.answer(f"Belum ada member paket {paket_label}.", show_alert=True)
        return

    text = (
        f"<b>📋 MEMBER PAKET {paket_label.upper()}</b>\n"
        f"Hal: {page}/{total_pages}  |  Total: {total}\n\n"
    )
    for i, u in enumerate(users, 1):
        name  = f"{u['first_name']} {u['last_name']}".strip() or "Unknown"
        uname = f"@{u['username']}" if u['username'] else "no username"
        idx   = i + (page - 1) * limit
        exp   = u.get("vip_end_date", "-") or "-"
        text += (
            f"{idx}. <b>{html_escape(name)}</b> ({html_escape(uname)})\n"
            f"└ ID: <code>{u['user_id']}</code>  |  Berakhir: {html_escape(exp)}\n\n"
        )

    nav = _nav_row(page, total_pages, f"o:member_list_{slug}", html=True)
    kb  = InlineKeyboardMarkup([nav, [InlineKeyboardButton("🔙 Kembali", callback_data="o:kelola_membership")]])
    await safe_edit_html(query, text, kb)


def _nav_row(page, total_pages, prefix, html=False):
    prev_cb = f"{prefix}:{page-1}" if page > 1 else "none"
    next_cb = f"{prefix}:{page+1}" if page < total_pages else "none"
    return [
        InlineKeyboardButton("⬅️", callback_data=prev_cb),
        InlineKeyboardButton("🏠", callback_data="nav:main"),
        InlineKeyboardButton("➡️", callback_data=next_cb),
    ]



async def show_pending_tf_list(query: CallbackQuery, page: int = 1, prefix: str = "o"):
    limit = 5
    items = get_pending_tf_paginated(page, limit)
    total = count_pending_tf()
    total_pages = max(1, (total + limit - 1) // limit)

    if not items and page == 1:
        await query.answer("Tidak ada pending TF saat ini.", show_alert=True)
        return
    if not items and page > 1:
        await show_pending_tf_list(query, 1, prefix)
        return

    text = (
        f"<b>📋 ANTREAN PENDING TRANSFER</b>\n"
        f"Total: <b>{total}</b> transaksi  |  Hal {page}/{total_pages}\n\n"
    )
    process_btns = []
    for i, item in enumerate(items, 1):
        name  = f"{item.get('first_name','')} {item.get('last_name','')}".strip() or "Unknown"
        uname = f"@{item['username']}" if item.get('username') else f"ID:{item['user_id']}"
        if item.get("paket_type") == "1_bulan":
            paket_label = "1 Bulan"
        elif item.get("paket_type") == "2_bulan":
            paket_label = "2 Bulan"
        else:
            paket_label = "Belum dipilih"
        idx   = i + (page - 1) * limit
        masuk = time_ago(item.get("created_at", ""))
        text += (
            f"{idx}. <b>#{item['id']} — {html_escape(name)}</b>\n"
            f"   └ {html_escape(uname)}  |  Paket: {html_escape(paket_label)}\n"
            f"   └ Masuk: {html_escape(masuk)}\n\n"
        )
        process_btns.append(
            InlineKeyboardButton(f"⚙️ #{item['id']}", callback_data=f"tf:view:{item['id']}")
        )

    nav  = _nav_row(page, total_pages, f"{prefix}:pending_tf_list")
    rows = [nav]
    for i in range(0, len(process_btns), 2):
        rows.append(process_btns[i:i+2])
    rows.append([InlineKeyboardButton("🔙 Kembali ke Panel", callback_data="nav:main")])
    await safe_edit_html(query, text, InlineKeyboardMarkup(rows))



async def show_pending_chat_list(query: CallbackQuery, page: int = 1, prefix: str = "o"):
    limit = 5
    items = get_pending_chat_paginated(page, limit)
    total = count_pending_chat()
    total_pages = max(1, (total + limit - 1) // limit)

    if not items and page == 1:
        await query.answer("Tidak ada chat yang belum dibalas.", show_alert=True)
        return
    if not items and page > 1:
        await show_pending_chat_list(query, 1, prefix)
        return

    text = (
        f"<b>💬 CHAT BELUM DIBALAS</b>\n"
        f"Total: <b>{total}</b> pesan  |  Hal {page}/{total_pages}\n\n"
    )
    reply_btns = []
    for i, item in enumerate(items, 1):
        name  = f"{item.get('first_name','')} {item.get('last_name','')}".strip() or "Unknown"
        uname = f"@{item['username']}" if item.get('username') else f"ID:{item['user_id']}"
        pesan = item.get("user_msg", "")
        pesan_short = pesan[:60] + ("..." if len(pesan) > 60 else "")
        idx   = i + (page - 1) * limit
        waktu = time_ago(item.get("created_at", ""))
        text += (
            f"{idx}. <b>#{item['id']} — {html_escape(uname)}</b>\n"
            f"   └ \"<i>{html_escape(pesan_short)}</i>\"\n"
            f"   └ {html_escape(waktu)}\n\n"
        )
        reply_btns.append(
            InlineKeyboardButton(f"💬 Balas #{item['id']}", callback_data=f"chat:reply:{item['id']}")
        )

    nav  = _nav_row(page, total_pages, f"{prefix}:pending_chat_list")
    rows = [nav]
    for i in range(0, len(reply_btns), 2):
        rows.append(reply_btns[i:i+2])
    rows.append([InlineKeyboardButton("🔙 Kembali ke Panel", callback_data="nav:main")])
    await safe_edit_html(query, text, InlineKeyboardMarkup(rows))



async def show_reminder_settings(query: CallbackQuery):
    r1_days = cfg_get("reminder_days_1_bulan", "3")
    r2_days = cfg_get("reminder_days_2_bulan", "3")
    r1_text = cfg_get("reminder_text_1_bulan", "").strip()
    r2_text = cfg_get("reminder_text_2_bulan", "").strip()

    def days_label(raw: str) -> str:
        parts = [d.strip() for d in raw.split(",") if d.strip().isdigit()]
        return ", ".join(("Hari-H" if d == "0" else f"H-{d}") for d in parts) or "Tidak diatur"

    text = (
        "<b>⏰ PENGATURAN PENGINGAT VIP OTOMATIS</b>\n\n"
        "Bot akan mengirim pesan pengingat ke member sebelum masa VIP mereka berakhir.\n\n"
        f"<b>📦 Paket 1 Bulan:</b>\n"
        f"• Jadwal kirim: <b>{html_escape(days_label(r1_days))}</b>\n"
        f"• Teks: <b>{'Sudah diatur ✅' if r1_text else 'Default ℹ️'}</b>\n\n"
        f"<b>📦 Paket 2 Bulan:</b>\n"
        f"• Jadwal kirim: <b>{html_escape(days_label(r2_days))}</b>\n"
        f"• Teks: <b>{'Sudah diatur ✅' if r2_text else 'Default ℹ️'}</b>\n\n"
        "<i>💡 Placeholder teks: <code>{nama}</code>, <code>{paket}</code>, <code>{tanggal_exp}</code></i>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏳ Jadwal Paket 1 Bulan", callback_data="o:reminder_days_menu:1_bulan"),
            InlineKeyboardButton("📝 Teks Paket 1 Bulan",   callback_data="o:reminder_text_edit:1_bulan"),
        ],
        [
            InlineKeyboardButton("⏳ Jadwal Paket 2 Bulan", callback_data="o:reminder_days_menu:2_bulan"),
            InlineKeyboardButton("📝 Teks Paket 2 Bulan",   callback_data="o:reminder_text_edit:2_bulan"),
        ],
        [InlineKeyboardButton("🔙 Kembali ke Panel", callback_data="nav:main")],
    ])
    await safe_edit_html(query, text, kb)


async def show_reminder_days_menu(query: CallbackQuery, paket_type: str):
    current_raw  = cfg_get(f"reminder_days_{paket_type}", "3")
    current_days = [d.strip() for d in current_raw.split(",") if d.strip().isdigit()]
    paket_label  = "1 Bulan" if paket_type == "1_bulan" else "2 Bulan"

    def ico(d: str) -> str:
        return "✅" if d in current_days else "☐"

    aktif_str = ", ".join(
        ("Hari-H" if d == "0" else f"H-{d}") for d in current_days
    ) if current_days else "Belum diatur"

    text = (
        f"<b>⏳ JADWAL PENGINGAT — Paket {paket_label}</b>\n\n"
        f"Aktif: <b>{html_escape(aktif_str)}</b>\n\n"
        f"Tekan untuk aktifkan/nonaktifkan hari:"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{ico('7')} H-7", callback_data=f"o:reminder_toggle:{paket_type}:7"),
            InlineKeyboardButton(f"{ico('3')} H-3", callback_data=f"o:reminder_toggle:{paket_type}:3"),
            InlineKeyboardButton(f"{ico('2')} H-2", callback_data=f"o:reminder_toggle:{paket_type}:2"),
        ],
        [
            InlineKeyboardButton(f"{ico('1')} H-1",   callback_data=f"o:reminder_toggle:{paket_type}:1"),
            InlineKeyboardButton(f"{ico('0')} Hari-H", callback_data=f"o:reminder_toggle:{paket_type}:0"),
        ],
        [InlineKeyboardButton("🔙 Kembali ke Pengaturan Pengingat", callback_data="o:reminder_settings")],
    ])
    await safe_edit_html(query, text, kb)



async def show_broadcast_center(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Menu utama Broadcast Center v2.0."""
    total = count_users()
    m1    = count_members_by_type("1_bulan")
    m2    = count_members_by_type("2_bulan")

    text = (
        "📢 <b>BROADCAST CENTER v2.0</b>\n\n"
        f"🌍 <b>Global:</b> {total:,} user\n"
        f"📦 <b>1 Bulan:</b> {m1:,} member\n"
        f"📦 <b>2 Bulan:</b> {m2:,} member\n\n"
        "Pilih segmentasi target broadcast agar link channel tidak bocor ke member periode lain.\n\n"
        "<b>┌ 🌍 TARGET GLOBAL</b>\n"
        "<b>├ 📦 TARGET BERDASARKAN DURASI</b>\n"
        "<b>└ 📅 TARGET BERDASARKAN PERIODE BULAN</b>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Broadcast ke Semua User", callback_data="o:broadcast_global")],
        [
            InlineKeyboardButton("📦 Member 1 Bulan", callback_data="o:broadcast_1_bulan"),
            InlineKeyboardButton("📦 Member 2 Bulan", callback_data="o:broadcast_2_bulan"),
        ],
        [
            InlineKeyboardButton("🗓 Paket VIP 1 Bulan", callback_data="o:bc_period_1b"),
            InlineKeyboardButton("🗓 Paket VIP 2 Bulan", callback_data="o:bc_period_2b"),
        ],
        [InlineKeyboardButton("📝 Spesifik Username",     callback_data="o:broadcast_username")],
        [InlineKeyboardButton("🔙 Kembali ke Panel",      callback_data="nav:main")],
    ])
    await safe_edit_html(query, text, kb)


async def show_period_picker(query: CallbackQuery, paket_type: str):
    """Tampilkan pilihan periode bulan untuk paket tertentu."""
    periods    = get_distinct_periods(paket_type)
    paket_label = "VIP 1 BULAN" if paket_type == "1_bulan" else "VIP 2 BULAN"
    cb_prefix  = "o:bc_period_detail"
    short      = "1b" if paket_type == "1_bulan" else "2b"

    if not periods:
        await query.answer(f"Belum ada data periode untuk {paket_label}.", show_alert=True)
        return

    text = (
        f"📅 <b>TARGET BROADCAST — {paket_label}</b>\n\n"
        f"Pilih kelompok periode yang ingin ditarget:\n"
        f"<i>Hanya member periode yang dipilih yang akan menerima broadcast.</i>"
    )
    rows = []
    for sp in periods:
        emoji  = _emoji_periode(sp)
        label  = _label_periode(sp, paket_type)
        count  = count_users_by_period(paket_type, sp)
        status = _status_periode(sp, paket_type)
        rows.append([InlineKeyboardButton(
            f"{emoji} {label} ({count} member)",
            callback_data=f"{cb_prefix}:{paket_type}:{sp}"
        )])

    rows.append([
        InlineKeyboardButton("🔙 Kembali", callback_data="o:broadcast_system"),
        InlineKeyboardButton("🏠 Menu Utama", callback_data="nav:main"),
    ])
    await safe_edit_html(query, text, InlineKeyboardMarkup(rows))


async def show_period_detail(query: CallbackQuery, paket_type: str, start_periode: str, page: int = 1):
    """Tampilkan detail member + tombol broadcast untuk periode tertentu."""
    limit       = 5
    total       = count_users_by_period(paket_type, start_periode)
    total_pages = max(1, (total + limit - 1) // limit)
    users       = get_users_detail_by_period(paket_type, start_periode, page, limit)
    paket_label = "VIP 1 BULAN" if paket_type == "1_bulan" else "VIP 2 BULAN"
    label_bln   = _label_periode(start_periode, paket_type)
    status      = _status_periode(start_periode, paket_type)
    short       = "1b" if paket_type == "1_bulan" else "2b"

    text = (
        f"📅 <b>DETAIL PERIODE: {paket_label} ({html_escape(label_bln)})</b>\n\n"
        f"📊 <b>Ringkasan Data:</b>\n"
        f"• Total Member Aktif: <b>{total} User</b>\n"
        f"• Status Periode: <b>{html_escape(status)}</b>\n\n"
        f"👥 <b>Daftar User (Hal {page}/{total_pages}):</b>\n"
    )

    for i, u in enumerate(users, 1):
        name  = f"{u.get('first_name','')}{' '+u['last_name'] if u.get('last_name') else ''}".strip() or "Unknown"
        uname = f"@{u['username']}" if u.get("username") else f"ID:{u['user_id']}"
        exp   = u.get("vip_end_date", "-") or "-"
        idx   = i + (page - 1) * limit
        if paket_type == "2_bulan":
            try:
                y, m = int(start_periode[:4]), int(start_periode[5:7])
                m2 = m % 12 + 1
                y2 = y + (1 if m == 12 else 0)
                end_m = f"{BULAN_ID.get(m2,str(m2))} {y2}"
                start_m = BULAN_ID.get(m, str(m))
                keterangan = f"Paket 2 Bulan (Awal: {start_m}, Akhir: {end_m})"
            except Exception:
                keterangan = f"Aktif s/d {exp}"
        else:
            keterangan = f"Aktif s/d {exp}"
        text += f"{idx}. 👤 <b>{html_escape(name)}</b> ({html_escape(uname)})\n    └ {html_escape(keterangan)}\n"

    text += (
        "\n──────────────────────────\n"
        f"Pilih tindakan untuk kelompok <b>{html_escape(label_bln)}</b>:"
    )

    prev_cb = f"o:bc_period_page:{paket_type}:{start_periode}:{page-1}" if page > 1 else "none"
    next_cb = f"o:bc_period_page:{paket_type}:{start_periode}:{page+1}" if page < total_pages else "none"

    rows = []
    if total > 0:
        rows.append([InlineKeyboardButton(
            f"📢 Kirim Broadcast Ke Kelompok Ini ({total} member)",
            callback_data=f"o:bc_period_exec:{paket_type}:{start_periode}"
        )])
    rows.append([
        InlineKeyboardButton("⬅️", callback_data=prev_cb),
        InlineKeyboardButton("🔙 Kembali", callback_data=f"o:bc_period_{short}"),
        InlineKeyboardButton("➡️", callback_data=next_cb),
    ])
    rows.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="nav:main")])
    await safe_edit_html(query, text, InlineKeyboardMarkup(rows))



async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()
    upsert_user(user)

    if is_banned(user.id):
        await update.message.reply_text(
            "🚫 *Akses Ditolak*\n\nAkun kamu telah dibanned dari layanan Joyland\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if cfg_get("maintenance_mode") == "1" and not is_owner(user.id):
        await update.message.reply_text(
            "🔧 *Mode Maintenance*\n\n"
            "Bot sedang dalam perbaikan\\. Coba beberapa saat lagi\\. 🙏",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if is_owner(user.id):
        await send_owner_menu(update.message, context)
    elif is_admin(user.id):
        await send_admin_menu(update.message, context)
    else:
        await send_user_menu(update.message, context)



async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    if is_banned(user.id):
        return
    text = (
        f"📖 *Panduan {mdescape(BOT_NAME)}*\n\n"
        "*Cara Berlangganan:*\n"
        "1\\. Tap 💳 *Cara Langganan* — lihat paket \\& rekening\n"
        "2\\. Lakukan transfer sesuai nominal\n"
        "3\\. Tap 📨 *Kirim Bukti TF* dan pilih paket\n"
        "4\\. Upload foto bukti transfer\n"
        "5\\. Tunggu notif dari bot \\(maks 5 menit\\)\n"
        "6\\. Link VIP dikirim otomatis setelah disetujui\\! 🎉\n\n"
        "*Butuh Bantuan?*\n"
        "Tap 💬 *Hubungi Admin* untuk chat langsung\\.\n\n"
        f"_Bot {mdescape(BOT_NAME)} \\| {mdescape(BOT_USERNAME)}_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2, protect_content=True)



async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()
    if not is_admin(user.id):
        await update.message.reply_text(
            "⛔ Kamu tidak punya akses panel admin\\.", parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    if is_owner(user.id):
        await send_owner_menu(update.message, context)
    else:
        await send_admin_menu(update.message, context)



async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text(
            "⛔ Perintah ini hanya untuk *Owner Mutlak*\\.", parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    context.user_data["state"] = S_ADD_ADMIN
    await update.message.reply_text(
        "👤 *Tambah Admin Baru*\n\n"
        "Kirimkan ID Telegram staf baru:\n_Contoh: `123456789`_\n\n"
        "Ketik /batal untuk membatalkan\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )



async def cmd_bc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_perm(user.id, "perm_broadcast"):
        await update.message.reply_text(
            "⚠️ <b>AKSES DITOLAK</b>\n\nKamu tidak punya izin <b>Broadcast Global</b>.",
            parse_mode=ParseMode.HTML,
        )
        return
    context.user_data["state"] = S_BROADCAST
    context.user_data["broadcast_target"] = "global"
    await update.message.reply_text(
        "📢 <b>BROADCAST GLOBAL</b>\n\n"
        "Kirimkan pesan yang ingin dikirim ke semua user.\n"
        "<i>Bisa berupa teks, foto, atau video.</i>\n\nKetik /batal untuk membatalkan.",
        parse_mode=ParseMode.HTML,
    )



async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text(
            "⛔ Perintah ini hanya untuk *Owner Mutlak*\\.", parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    if not context.args:
        await update.message.reply_text(
            "❌ Gunakan format: `/unban <id_user atau @username>`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    input_target = context.args[0].lstrip("@").strip()
    target_id    = None
    if input_target.isdigit():
        target_id = int(input_target)
    else:
        with get_conn() as conn:
            res = conn.execute("SELECT user_id FROM users WHERE username=?", (input_target,)).fetchone()
            if res:
                target_id = res[0]
    if not target_id:
        await update.message.reply_text("❌ User tidak ditemukan di database\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    unban_user(target_id)
    await update.message.reply_text(
        f"✅ User `{target_id}` telah berhasil di\\-unban\\.", parse_mode=ParseMode.MARKDOWN_V2
    )



async def cmd_batal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Aksi dibatalkan\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu Utama", callback_data="nav:main")]]),
    )



async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = query.from_user
    data  = query.data or ""

    if data.startswith("vip:open:"):
        await handle_vip_open(query, user)
        return

    await query.answer()

    if is_banned(user.id) and not (data.startswith("o:") or data.startswith("a:")):
        return

    if data == "nav:main":
        context.user_data.clear()
        if is_owner(user.id):
            await send_owner_menu(query, context, edit=True)
        elif is_admin(user.id):
            await send_admin_menu(query, context, edit=True)
        else:
            await send_user_menu(query, context, edit=True, protect=True)
        return

    if data == "none":
        return

    if data == "u:info_vip":
        text  = cfg_get("vip_info_text") or "📚 *INFO VIP ACCESS*\n\nBelum ada informasi\\."
        media = cfg_get("vip_info_media")
        vip   = get_active_vip_link()
        note  = (
            "\n\n🔗 _Link aktif tersedia \\— serahkan bukti TF untuk akses\\!_"
            if vip else "\n\n⚠️ _Link VIP sedang diperbarui admin\\._"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Cara Berlangganan", callback_data="u:cara_langganan")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="nav:main")],
        ])
        if media:
            try:
                await query.message.reply_photo(
                    photo=media, caption=text + note,
                    parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb, protect_content=True,
                )
                return
            except TelegramError:
                pass
        await safe_edit(query, text + note, kb, protect=True)
        return

    if data == "u:cara_langganan":
        text  = cfg_get("payment_text")
        media = cfg_get("payment_media")
        kb    = InlineKeyboardMarkup([
            [InlineKeyboardButton("📨 Kirim Bukti Transfer", callback_data="u:kirim_bukti")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="nav:main")],
        ])
        if media:
            try:
                await query.message.reply_photo(
                    photo=media, caption=text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb,
                )
                return
            except TelegramError:
                pass
        await safe_edit(query, text, kb)
        return

    if data == "u:kirim_bukti":
        text = (
            f"💰 <b>PILIH PAKET LANGGANAN VIP</b>\n\n"
            f"Halo {html_escape(user.first_name or 'Kak')}! Pilih durasi paket langganan:\n\n"
            f"📦 <b>Paket 1 Bulan</b> — Akses penuh 30 hari\n"
            f"📦 <b>Paket 2 Bulan</b> — Akses penuh 60 hari <i>(Lebih Hemat!)</i>"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📦 Paket 1 Bulan", callback_data="u:pilih_paket:1_bulan"),
                InlineKeyboardButton("📦 Paket 2 Bulan", callback_data="u:pilih_paket:2_bulan"),
            ],
            [InlineKeyboardButton("🔙 Kembali", callback_data="nav:main")],
        ])
        await safe_edit_html(query, text, kb)
        return

    if data.startswith("u:pilih_paket:"):
        paket       = data.split(":")[2]
        paket_label = "1 Bulan" if paket == "1_bulan" else "2 Bulan"
        context.user_data["state"]      = S_UPLOAD_BUKTI
        context.user_data["paket_type"] = paket
        text = (
            f"📸 <b>KIRIM BUKTI TRANSFER (Paket {paket_label})</b>\n\n"
            f"Upload foto bukti transfer kamu sekarang, Kak!\n\n"
            f"⚠️ <i>Pastikan foto terlihat jelas, tidak terpotong, dan nominalnya sesuai.</i>\n\n"
            f"Ketik /batal untuk membatalkan."
        )
        await safe_edit_html(query, text, InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="u:kirim_bukti")]]))
        return

    if data == "u:hubungi_admin":
        context.user_data["state"] = S_CHAT_LAPORAN
        await safe_edit(query, "💬 *HUBUNGI ADMIN*\n\nKetikkan pesan kamu\\. Admin akan segera membalas\\!\n\nKetik /batal untuk membatalkan\\.", kb_back())
        return

    if data.startswith("u:custom:"):
        bid  = int(data.split(":")[2])
        btns = get_custom_buttons()
        btn  = next((b for b in btns if b["id"] == bid), None)
        if btn and btn["button_type"] == "text":
            await query.message.reply_text(mdescape(btn["button_value"]), parse_mode=ParseMode.MARKDOWN_V2, protect_content=True)
        return

    if data.startswith("o:pending_tf_list:"):
        await show_pending_tf_list(query, int(data.split(":")[2]), prefix="o")
        return

    if data.startswith("a:pending_tf_list:"):
        await show_pending_tf_list(query, int(data.split(":")[2]), prefix="a")
        return

    if data.startswith("o:pending_chat_list:"):
        await show_pending_chat_list(query, int(data.split(":")[2]), prefix="o")
        return

    if data.startswith("a:pending_chat_list:"):
        await show_pending_chat_list(query, int(data.split(":")[2]), prefix="a")
        return

    if data.startswith("tf:view:"):
        tf_id = int(data.split(":")[2])
        tf    = get_tf(tf_id)
        if not tf:
            await query.answer("Data TF tidak ditemukan.", show_alert=True)
            return
        if tf["status"] != "pending":
            await query.answer("TF ini sudah diproses.", show_alert=True)
            return
        uinfo = get_user_info(tf["user_id"]) or {}
        name  = (uinfo.get("first_name","") + " " + uinfo.get("last_name","")).strip() or "Unknown"
        uname = f"@{uinfo['username']}" if uinfo.get("username") else "No Username"
        if tf.get("paket_type") == "1_bulan":
            pl = "1 Bulan"
        elif tf.get("paket_type") == "2_bulan":
            pl = "2 Bulan"
        else:
            pl = "Belum dipilih"
        caption = (
            f"📩 *SETORAN \\#TF{tf_id}*\n\n"
            f"👤 *{mdescape(name)}*\n"
            f"🔗 {mdescape(uname)}\n"
            f"🆔 `{tf['user_id']}`\n"
            f"📦 Paket: *{mdescape(pl)}*\n"
            f"🕐 {mdescape((tf.get('created_at','')[:16]))}"
        )
        list_prefix = "o" if is_owner(user.id) else "a"
        tf_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Terima & Kirim Link", callback_data=f"tf:acc:{tf_id}")],
            [
                InlineKeyboardButton("❌ Tolak (Salah Nominal)", callback_data=f"tf:tolak:{tf_id}:nominal"),
                InlineKeyboardButton("❌ Tolak (Bukti Palsu)",   callback_data=f"tf:tolak:{tf_id}:palsu"),
            ],
            [InlineKeyboardButton("💬 Kirim Pesan ke User", callback_data=f"tf:msg:{tf_id}")],
            [InlineKeyboardButton("🚫 Ban User",            callback_data=f"tf:ban:{tf_id}")],
            [InlineKeyboardButton("🔙 Kembali ke Daftar TF", callback_data=f"{list_prefix}:pending_tf_list:1")],
        ])
        try:
            await context.bot.send_photo(
                chat_id=user.id, photo=tf["file_id"],
                caption=caption, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=tf_kb,
            )
        except TelegramError as e:
            await query.message.reply_text(f"⚠️ Gagal tampilkan struk: {html_escape(str(e))}", parse_mode=ParseMode.HTML)
        return

    if data == "o:reminder_settings":
        if not is_owner(user.id):
            await query.answer("⚠️ Hanya Owner Mutlak.", show_alert=True)
            return
        await show_reminder_settings(query)
        return

    if data.startswith("o:reminder_days_menu:"):
        if not is_owner(user.id):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        await show_reminder_days_menu(query, data.split(":", 2)[2])
        return

    if data.startswith("o:reminder_toggle:"):
        if not is_owner(user.id):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        parts        = data.split(":")
        paket_type   = parts[2]
        day_str      = parts[3]
        current_raw  = cfg_get(f"reminder_days_{paket_type}", "3")
        current_days = [d.strip() for d in current_raw.split(",") if d.strip().isdigit()]
        if day_str in current_days:
            current_days.remove(day_str)
        else:
            current_days.append(day_str)
        current_days = sorted(set(current_days), key=lambda x: int(x), reverse=True)
        cfg_set(f"reminder_days_{paket_type}", ",".join(current_days))
        await show_reminder_days_menu(query, paket_type)
        return

    if data.startswith("o:reminder_text_edit:"):
        if not is_owner(user.id):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        paket_type  = data.split(":", 2)[2]
        paket_label = "1 Bulan" if paket_type == "1_bulan" else "2 Bulan"
        cur_text    = cfg_get(f"reminder_text_{paket_type}", "").strip()
        state       = S_EDIT_REMINDER_TEXT_1 if paket_type == "1_bulan" else S_EDIT_REMINDER_TEXT_2
        context.user_data["state"] = state
        context.user_data["editing_reminder_paket"] = paket_type
        teks_aktif = html_escape(cur_text[:400]) if cur_text else "<i>(Belum diatur — menggunakan teks default)</i>"
        text = (
            f"<b>📝 EDIT TEKS PENGINGAT — Paket {paket_label}</b>\n\n"
            f"Teks aktif:\n<code>{'─'*32}</code>\n{teks_aktif}\n<code>{'─'*32}</code>\n\n"
            f"Ketik dan kirim teks baru.\n\n"
            f"Placeholder yang bisa dipakai:\n"
            f"• <code>{{nama}}</code> — Nama user\n"
            f"• <code>{{paket}}</code> — Nama paket\n"
            f"• <code>{{tanggal_exp}}</code> — Tanggal berakhir\n\n"
            f"(Ketik /batal untuk membatalkan)"
        )
        await safe_edit_html(query, text, InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="o:reminder_settings")]]))
        return

    if data == "o:preview":
        custom_btns = get_custom_buttons()
        text = cfg_get("welcome_text")
        kb   = InlineKeyboardMarkup([
            *kb_user(custom_btns).inline_keyboard,
            [InlineKeyboardButton("🔙 Kembali ke Panel Owner", callback_data="nav:main")],
        ])
        await safe_edit(query, f"👁 *PREVIEW TAMPILAN USER:*\n\n{text}", kb)
        return

    if data == "o:edit_welcome":
        if not has_perm(user.id, "perm_edit_bot"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        media_status = "✅ Ada" if cfg_get("welcome_media") else "❌ Tidak Ada"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ Edit Teks", callback_data="o:welcome_text"),
                InlineKeyboardButton("🖼 Ganti Foto", callback_data="o:welcome_media"),
            ],
            [InlineKeyboardButton("🗑 Hapus Foto", callback_data="o:welcome_del_media")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="nav:main")],
        ])
        await safe_edit(query, f"🖼 *EDIT WELCOME MESSAGE*\n\n📸 Status Foto: {mdescape(media_status)}", kb)
        return

    if data == "o:welcome_text":
        context.user_data["state"] = S_EDIT_WELCOME_TEXT
        await safe_edit(query, "✏️ *Edit Teks Welcome*\n\nKirimkan teks baru\\.\nKetik /batal untuk membatalkan\\.", kb_back("o:edit_welcome"))
        return

    if data == "o:welcome_media":
        context.user_data["state"] = S_EDIT_WELCOME_MEDIA
        await safe_edit(query, "🖼 *Ganti Foto Welcome*\n\nKirimkan foto banner baru:\nKetik /batal untuk membatalkan\\.", kb_back("o:edit_welcome"))
        return

    if data == "o:welcome_del_media":
        cfg_set("welcome_media", "")
        await query.answer("✅ Foto welcome dihapus.")
        await send_owner_menu(query, context, edit=True)
        return

    if data == "o:button_builder":
        if not has_perm(user.id, "perm_edit_bot"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        await show_button_builder(query, context, user)
        return

    if data == "o:btn_add":
        context.user_data["state"] = S_BUTTON_BUILDER
        await safe_edit(query, "➕ *Tambah Tombol Baru*\n\n*URL:* `Nama | https://link\\.com`\n*Teks:* `Nama | Teks: isi pesan`\n\nKetik /batal untuk membatalkan\\.", kb_back("o:button_builder"))
        return

    if data.startswith("o:btn_del:"):
        del_custom_button(int(data.split(":")[2]))
        await query.answer("🗑 Tombol dihapus.")
        await show_button_builder(query, context, user)
        return

    if data == "o:edit_payment":
        if not has_perm(user.id, "perm_edit_bot"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        media_status = "✅ Ada" if cfg_get("payment_media") else "❌ Tidak Ada"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ Edit Teks",  callback_data="o:payment_text"),
                InlineKeyboardButton("🖼 Ganti QRIS", callback_data="o:payment_media"),
            ],
            [InlineKeyboardButton("🗑 Hapus Foto", callback_data="o:payment_del_media")],
            [InlineKeyboardButton("🔙 Kembali",    callback_data="nav:main")],
        ])
        await safe_edit(query, f"💳 *PAYMENT SETTINGS*\n\n📸 Status Foto QRIS: {mdescape(media_status)}", kb)
        return

    if data == "o:payment_text":
        context.user_data["state"] = S_EDIT_PAYMENT_TEXT
        await safe_edit(query, "✏️ *Edit Teks Payment*\n\nKirimkan teks info pembayaran baru:", kb_back("o:edit_payment"))
        return

    if data == "o:payment_media":
        context.user_data["state"] = S_EDIT_PAYMENT_MEDIA
        await safe_edit(query, "🖼 *Ganti Foto QRIS*\n\nKirimkan foto QRIS atau rekening baru:", kb_back("o:edit_payment"))
        return

    if data == "o:payment_del_media":
        cfg_set("payment_media", "")
        await query.answer("✅ Foto payment dihapus.")
        await send_owner_menu(query, context, edit=True)
        return

    if data == "o:edit_vip_info":
        if not has_perm(user.id, "perm_edit_bot"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        media_status = "✅ Ada" if cfg_get("vip_info_media") else "❌ Tidak Ada"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ Edit Teks", callback_data="o:vip_info_text"),
                InlineKeyboardButton("🖼 Ganti Foto", callback_data="o:vip_info_media"),
            ],
            [InlineKeyboardButton("🗑 Hapus Foto", callback_data="o:vip_info_del_media")],
            [InlineKeyboardButton("🔙 Kembali",    callback_data="nav:main")],
        ])
        await safe_edit(query, f"📚 *VIP INFO SETTINGS*\n\n📸 Status Foto: {mdescape(media_status)}", kb)
        return

    if data == "o:vip_info_text":
        context.user_data["state"] = S_EDIT_VIP_TEXT
        await safe_edit(query, "✏️ *Edit Teks Info VIP*\n\nKirimkan teks informasi VIP baru:", kb_back("o:edit_vip_info"))
        return

    if data == "o:vip_info_media":
        context.user_data["state"] = S_EDIT_VIP_MEDIA
        await safe_edit(query, "🖼 *Ganti Media Info VIP*\n\nKirimkan foto/media baru:", kb_back("o:edit_vip_info"))
        return

    if data == "o:vip_info_del_media":
        cfg_set("vip_info_media", "")
        await query.answer("✅ Foto Info VIP dihapus.")
        await send_owner_menu(query, context, edit=True)
        return

    if data in ("o:update_vip", "a:update_vip"):
        if data == "a:update_vip" and not has_perm(user.id, "perm_edit_bot"):
            await query.answer("⚠️ Kamu tidak punya izin.", show_alert=True)
            return
        vip      = get_active_vip_link()
        link_info = (
            f"\n\n🔗 Link aktif:\n`{mdescape(vip['link'])}`" if vip
            else "\n\n⚠️ _Belum ada link VIP aktif\\._"
        )
        context.user_data["state"] = S_EDIT_VIP_LINK
        await safe_edit(query, "🔑 *UPDATE LINK VIP*\n\nKirimkan link VIP terbaru:" + link_info + "\n\nKetik /batal untuk membatalkan\\.", kb_back())
        return

    if data == "o:kelola_admin":
        await show_kelola_admin(query, context)
        return

    if data.startswith("o:adm_perm:"):
        await show_admin_perm(query, context, int(data.split(":")[2]))
        return

    if data.startswith("o:adm_del:"):
        remove_admin(int(data.split(":")[2]))
        await query.answer("🗑 Admin dihapus.")
        await show_kelola_admin(query, context)
        return

    if data.startswith("o:perm:"):
        parts = data.split(":", 3)
        toggle_admin_perm(int(parts[2]), parts[3])
        await show_admin_perm(query, context, int(parts[2]))
        return

    if data.startswith("o:users:"):
        await show_user_list(query, int(data.split(":")[2]))
        return

    if data.startswith("o:banned_list:"):
        await show_banned_list(query, int(data.split(":")[2]))
        return

    if data.startswith("o:unban:"):
        unban_user(int(data.split(":")[2]))
        await query.answer("✅ User telah di-unban!", show_alert=True)
        return

    if data == "o:settings":
        await show_settings(query, context)
        return

    if data == "o:toggle_autodel":
        cfg_set("auto_delete_button", "0" if cfg_get("auto_delete_button") == "1" else "1")
        await show_settings(query, context)
        return

    if data == "o:toggle_maintenance":
        cfg_set("maintenance_mode", "0" if cfg_get("maintenance_mode") == "1" else "1")
        await show_settings(query, context)
        return

    if data == "o:broadcast_system":
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        await show_broadcast_center(query, context)
        return

    if data == "o:broadcast_global":
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        context.user_data["state"]            = S_BROADCAST
        context.user_data["broadcast_target"] = "global"
        await safe_edit_html(query, "🌍 <b>BROADCAST GLOBAL</b>\n\nKirimkan pesan ke seluruh user.\nBisa teks, foto, atau video.\n\nKetik /batal untuk membatalkan.", kb_back("o:broadcast_system"))
        return

    if data == "o:broadcast_1_bulan":
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        context.user_data["state"]            = S_BROADCAST
        context.user_data["broadcast_target"] = "1_bulan"
        await safe_edit_html(query, f"📦 <b>BROADCAST TARGET 1 BULAN</b>\n\nTarget: <b>{count_members_by_type('1_bulan'):,} member</b>.\n\nKirimkan pesan.\nKetik /batal untuk membatalkan.", kb_back("o:broadcast_system"))
        return

    if data == "o:broadcast_2_bulan":
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        context.user_data["state"]            = S_BROADCAST
        context.user_data["broadcast_target"] = "2_bulan"
        await safe_edit_html(query, f"📦 <b>BROADCAST TARGET 2 BULAN</b>\n\nTarget: <b>{count_members_by_type('2_bulan'):,} member</b>.\n\nKirimkan pesan.\nKetik /batal untuk membatalkan.", kb_back("o:broadcast_system"))
        return

    if data == "o:broadcast_username":
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        context.user_data["state"] = S_BROADCAST_USERNAME
        await safe_edit_html(query, "📝 <b>BROADCAST VIA LIST USERNAME</b>\n\nFormat:\n<code>@user1, @user2\n======\nIsi pesan...</code>\n\nKetik /batal untuk membatalkan.", kb_back("o:broadcast_system"))
        return

    if data in ("o:broadcast", "a:broadcast"):
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        context.user_data["state"]            = S_BROADCAST
        context.user_data["broadcast_target"] = "global"
        await safe_edit(query, "📢 *BROADCAST GLOBAL*\n\nKirimkan pesan\\.\nKetik /batal untuk membatalkan\\.", kb_back())
        return

    if data == "o:bc_period_1b":
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        await show_period_picker(query, "1_bulan")
        return

    if data == "o:bc_period_2b":
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        await show_period_picker(query, "2_bulan")
        return

    if data.startswith("o:bc_period_detail:"):
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        parts        = data.split(":", 4)
        paket_type   = parts[2]
        start_periode = parts[3]
        await show_period_detail(query, paket_type, start_periode, page=1)
        return

    if data.startswith("o:bc_period_page:"):
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        parts        = data.split(":", 5)
        paket_type   = parts[2]
        start_periode = parts[3]
        page         = int(parts[4])
        await show_period_detail(query, paket_type, start_periode, page=page)
        return

    if data.startswith("o:bc_period_exec:"):
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        parts        = data.split(":", 4)
        paket_type   = parts[2]
        start_periode = parts[3]
        total_target = count_users_by_period(paket_type, start_periode)
        label_bln    = _label_periode(start_periode, paket_type)
        context.user_data["state"]            = S_BROADCAST
        context.user_data["broadcast_target"] = f"period:{paket_type}:{start_periode}"
        text = (
            f"🚀 <b>PROSES BROADCAST — PERIODE {html_escape(label_bln.upper())}</b>\n\n"
            f"🎯 Target Terdeteksi: <b>{total_target} Member Aktif</b>\n"
            f"📦 Paket: <b>{'1 Bulan' if paket_type == '1_bulan' else '2 Bulan'}</b>\n"
            f"📊 Status: <b>{html_escape(_status_periode(start_periode, paket_type))}</b>\n\n"
            f"Silakan kirimkan pesan broadcast (Teks, Foto, atau Video).\n"
            f"<i>Member di luar periode ini tidak akan menerima pesan ini.</i>\n\n"
            f"Ketik /batal untuk membatalkan."
        )
        await safe_edit_html(query, text, kb_back(f"o:bc_period_detail:{paket_type}:{start_periode}"))
        return

    if data == "o:kelola_membership":
        await show_kelola_membership(query, context)
        return

    if data.startswith("o:member_list_1:"):
        await show_member_list(query, "1_bulan", int(data.split(":")[2]))
        return

    if data.startswith("o:member_list_2:"):
        await show_member_list(query, "2_bulan", int(data.split(":")[2]))
        return

    if data == "o:bc_member_1":
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        context.user_data["state"]            = S_BROADCAST
        context.user_data["broadcast_target"] = "1_bulan"
        await safe_edit_html(query, f"📦 <b>BC KE MEMBER 1 BULAN</b>\n\nTarget: <b>{count_members_by_type('1_bulan'):,}</b>.\nKetik /batal untuk membatalkan.", kb_back("o:kelola_membership"))
        return

    if data == "o:bc_member_2":
        if not has_perm(user.id, "perm_broadcast"):
            await query.answer("⚠️ Akses ditolak.", show_alert=True)
            return
        context.user_data["state"]            = S_BROADCAST
        context.user_data["broadcast_target"] = "2_bulan"
        await safe_edit_html(query, f"📦 <b>BC KE MEMBER 2 BULAN</b>\n\nTarget: <b>{count_members_by_type('2_bulan'):,}</b>.\nKetik /batal untuk membatalkan.", kb_back("o:kelola_membership"))
        return

    if data == "a:statistik":
        with get_conn() as conn:
            acc_tf = conn.execute("SELECT COUNT(*) FROM pending_tf WHERE status='acc'").fetchone()[0]
            rej_tf = conn.execute("SELECT COUNT(*) FROM pending_tf WHERE status IN ('tolak','banned')").fetchone()[0]
        text = (
            f"📊 *STATISTIK {mdescape(BOT_NAME)}*\n\n"
            f"👥 Total User: *{count_users():,}*\n"
            f"📦 Member 1 Bulan: *{count_members_by_type('1_bulan'):,}*\n"
            f"📦 Member 2 Bulan: *{count_members_by_type('2_bulan'):,}*\n"
            f"🚫 User Banned: *{count_banned()}*\n"
            f"🛡 Staf Aktif: *{count_admins()}*\n\n"
            f"📋 *Bukti Transfer:*\n"
            f"• Pending: *{count_pending_tf()}*\n"
            f"• Diterima: *{acc_tf}*\n"
            f"• Ditolak: *{rej_tf}*\n\n"
            f"💬 Chat Belum Dibalas: *{count_pending_chat()}*\n\n"
            f"🕐 {mdescape(datetime.now().strftime('%d %b %Y, %H:%M'))} WIB"
        )
        await safe_edit(query, text, kb_back())
        return

    if data.startswith("tf:acc:"):
        await process_tf_acc(query, context, user, int(data.split(":")[2]))
        return

    if data.startswith("tf:tolak:"):
        parts  = data.split(":")
        alasan = {"nominal": "Salah Nominal", "palsu": "Bukti Palsu"}.get(parts[3], "Tidak Diketahui")
        await process_tf_tolak(query, context, int(parts[2]), alasan)
        return

    if data.startswith("tf:msg:"):
        tf_id      = int(data.split(":")[2])
        admin_name = query.from_user.first_name
        context.user_data["target_tf_id"] = tf_id
        context.user_data["state"]        = S_ADMIN_SEND_MSG_TF
        try:
            cur_cap = query.message.caption or ""
            await query.edit_message_caption(
                caption=cur_cap + f"\n\n⏳ _Sedang dibalas oleh {mdescape(admin_name)}_",
                parse_mode=ParseMode.MARKDOWN_V2, reply_markup=None,
            )
        except Exception:
            pass
        await query.message.reply_text(
            f"💬 *Kirim Pesan ke User*\nAdmin: {mdescape(admin_name)}\n\nSilahkan ketik pesan:",
            parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb_back(),
        )
        return

    if data.startswith("tf:ban:"):
        tf_id = int(data.split(":")[2])
        tf    = get_tf(tf_id)
        if tf and tf["status"] == "pending":
            ban_user(tf["user_id"], "Bukti transfer palsu")
            update_tf_status(tf_id, "banned", user.id)
            await _update_all_tf_notifs(context, tf_id, f"🚫 User `{tf['user_id']}` di\\-BAN")
            try:
                await context.bot.send_message(tf["user_id"], "🚫 Akun kamu telah *dibanned* dari Joyland\\.", parse_mode=ParseMode.MARKDOWN_V2)
            except TelegramError:
                pass
        else:
            await query.answer("TF sudah diproses.", show_alert=True)
        return

    if data.startswith("chat:reply:"):
        session_id = int(data.split(":")[2])
        if not has_perm(user.id, "perm_reply_chat"):
            await query.answer("⚠️ Kamu tidak punya izin membalas chat.", show_alert=True)
            return
        context.user_data["state"]            = S_ADMIN_REPLY
        context.user_data["reply_session_id"] = session_id
        await query.message.reply_text(
            "💬 *Balas Pesan User*\n\nKetikkan balasan kamu:\n\nKetik /batal untuk membatalkan\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if data.startswith("chat:ban:"):
        session_id = int(data.split(":")[2])
        session    = get_chat_session(session_id)
        if session and session["status"] == "open":
            ban_user(session["user_id"], "Perilaku tidak pantas di chat")
            close_chat_session(session_id)
            await _update_all_chat_notifs(context, session_id, f"🚫 User `{session['user_id']}` di\\-BAN")
            try:
                await context.bot.send_message(session["user_id"], "🚫 Akun kamu telah *dibanned* dari Joyland\\.", parse_mode=ParseMode.MARKDOWN_V2)
            except TelegramError:
                pass
        else:
            await query.answer("Session sudah ditutup.", show_alert=True)
        return

    if data.startswith("unban:"):
        unban_user(int(data.split(":")[1]))
        await query.answer("✅ User di-unban.", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except TelegramError:
            pass
        return



async def show_kelola_membership(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    m1 = count_members_by_type("1_bulan")
    m2 = count_members_by_type("2_bulan")
    text = (
        "👥 <b>KELOLA DATA MEMBERSHIP</b>\n\n"
        f"Paket 1 Bulan: <b>{m1:,} Pengguna</b>\n"
        f"Paket 2 Bulan: <b>{m2:,} Pengguna</b>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 List User 1 Bulan", callback_data="o:member_list_1:1"),
            InlineKeyboardButton("📢 BC ke 1 Bulan",     callback_data="o:bc_member_1"),
        ],
        [
            InlineKeyboardButton("📋 List User 2 Bulan", callback_data="o:member_list_2:1"),
            InlineKeyboardButton("📢 BC ke 2 Bulan",     callback_data="o:bc_member_2"),
        ],
        [InlineKeyboardButton("🔙 Kembali ke Panel", callback_data="nav:main")],
    ])
    await safe_edit_html(query, text, kb)



async def show_button_builder(query, context, user):
    btns = get_custom_buttons()
    text = "🔗 *BUTTON BUILDER*\n\n"
    if btns:
        text += "*Tombol custom aktif:*\n"
        for b in btns:
            ico = "🔗" if b["button_type"] == "url" else "📝"
            text += f"{ico} `{mdescape(b['button_text'])}` — {b['button_type']}\n"
    else:
        text += "_Belum ada tombol custom\\._\n"
    text += "\n*Format tambah tombol:*\n`Nama \\| https://link\\.com`\natau\n`Nama \\| Teks: isi pesan`"
    rows = [[InlineKeyboardButton("➕ Tambah Tombol", callback_data="o:btn_add")]]
    for b in btns:
        rows.append([InlineKeyboardButton(f"🗑 Hapus: {b['button_text'][:25]}", callback_data=f"o:btn_del:{b['id']}")])
    rows.append([InlineKeyboardButton("🔙 Kembali", callback_data="nav:main")])
    await safe_edit(query, text, InlineKeyboardMarkup(rows))



async def show_kelola_admin(query, context):
    admins = all_admins()
    text   = "👥 *KELOLA ADMIN / STAFF*\n\n"
    if admins:
        text += "*Daftar Staf Aktif:*\n"
        for a in admins:
            un    = f"@{a['username']}" if a.get("username") else "no username"
            text += f"• `{a['admin_id']}` — {mdescape(un)}\n"
    else:
        text += "_Belum ada admin\\. Gunakan /addadmin\\._\n"
    rows = []
    for a in admins:
        un = a.get("username") or str(a["admin_id"])
        rows.append([
            InlineKeyboardButton(f"⚙️ {un[:20]}", callback_data=f"o:adm_perm:{a['admin_id']}"),
            InlineKeyboardButton("🗑 Hapus",      callback_data=f"o:adm_del:{a['admin_id']}"),
        ])
    rows.append([InlineKeyboardButton("🔙 Kembali", callback_data="nav:main")])
    await safe_edit(query, text, InlineKeyboardMarkup(rows))



async def show_admin_perm(query, context, admin_id: int):
    adm = get_admin_info(admin_id)
    if not adm:
        await query.answer("Admin tidak ditemukan.", show_alert=True)
        return
    un   = f"@{adm['username']}" if adm.get("username") else "no username"
    text = f"⚙️ *SETTING IZIN STAFF*\n\nStaff: `{admin_id}` \\({mdescape(un)}\\)\nAtur akses:"
    def ico(v): return "✅" if v else "❌"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{ico(adm['perm_acc_tf'])} Acc Bukti TF",        callback_data=f"o:perm:{admin_id}:perm_acc_tf")],
        [InlineKeyboardButton(f"{ico(adm['perm_reply_chat'])} Balas Chat User", callback_data=f"o:perm:{admin_id}:perm_reply_chat")],
        [InlineKeyboardButton(f"{ico(adm['perm_edit_bot'])} Edit Tampilan Bot", callback_data=f"o:perm:{admin_id}:perm_edit_bot")],
        [InlineKeyboardButton(f"{ico(adm['perm_tambah_admin'])} Tambah Admin",  callback_data=f"o:perm:{admin_id}:perm_tambah_admin")],
        [InlineKeyboardButton(f"{ico(adm['perm_broadcast'])} Broadcast",        callback_data=f"o:perm:{admin_id}:perm_broadcast")],
        [InlineKeyboardButton("💾 Selesai", callback_data="o:kelola_admin")],
    ])
    await safe_edit(query, text, kb)



async def show_settings(query, context):
    auto_del = cfg_get("auto_delete_button") == "1"
    maint    = cfg_get("maintenance_mode")   == "1"
    def ico(v): return "✅ Aktif" if v else "❌ Nonaktif"
    text = (
        "⚙️ *PENGATURAN SISTEM*\n\n"
        f"🔗 *Auto\\-Delete Link Button:* {ico(auto_del)}\n"
        f"_Tombol VIP hilang setelah diklik user_\n\n"
        f"🔧 *Mode Maintenance:* {ico(maint)}\n"
        f"_User biasa tidak bisa akses bot_\n\n"
        f"🚫 *User Banned:* {count_banned()} akun\n"
        f"🤖 Versi Bot: v{mdescape(cfg_get('bot_version', '6.0'))}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{'✅' if auto_del else '❌'} Auto-Delete Button", callback_data="o:toggle_autodel")],
        [InlineKeyboardButton(f"{'✅' if maint else '❌'} Mode Maintenance",     callback_data="o:toggle_maintenance")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="nav:main")],
    ])
    await safe_edit(query, text, kb)



async def _update_all_tf_notifs(context, tf_id: int, label: str):
    for n in get_tf_admin_notifs(tf_id):
        try:
            await context.bot.edit_message_reply_markup(chat_id=n["chat_id"], message_id=n["msg_id"], reply_markup=None)
            await context.bot.send_message(n["chat_id"], f"📋 TF \\#{tf_id} — {label}", parse_mode=ParseMode.MARKDOWN_V2)
        except TelegramError:
            pass


async def _update_all_chat_notifs(context, session_id: int, label: str):
    for n in get_chat_admin_notifs(session_id):
        try:
            await context.bot.edit_message_reply_markup(chat_id=n["chat_id"], message_id=n["msg_id"], reply_markup=None)
            await context.bot.send_message(n["chat_id"], f"💬 Session \\#{session_id} — {label}", parse_mode=ParseMode.MARKDOWN_V2)
        except TelegramError:
            pass



async def handle_vip_open(query: CallbackQuery, user):
    parts  = query.data.split(":")
    tf_id  = int(parts[2])
    vip_id = int(parts[3])

    if not mark_link_used(user.id, tf_id):
        await query.answer("⚠️ Tombol ini sudah pernah kamu gunakan!", show_alert=True)
        return

    with get_conn() as conn:
        row = conn.execute("SELECT link FROM vip_links WHERE id=?", (vip_id,)).fetchone()

    if not row:
        await query.answer("⚠️ Link tidak ditemukan. Hubungi admin.", show_alert=True)
        return

    vip_url    = row["link"].strip()
    url_opened = False
    try:
        await query.answer(url=vip_url)
        url_opened = True
    except (BadRequest, TelegramError):
        try:
            await query.answer()
        except Exception:
            pass

    try:
        if url_opened:
            await query.edit_message_reply_markup(reply_markup=None)
        else:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👉 Tap Di Sini — Buka Channel VIP", url=vip_url)
                ]])
            )
    except Exception:
        pass



async def process_tf_acc(query, context, admin_user, tf_id: int):
    if not has_perm(admin_user.id, "perm_acc_tf"):
        await query.answer("⚠️ Kamu tidak punya izin Acc Bukti TF.", show_alert=True)
        return

    tf = get_tf(tf_id)
    if not tf:
        await query.answer("Data TF tidak ditemukan.", show_alert=True)
        return
    if tf["status"] != "pending":
        await query.answer("TF ini sudah diproses sebelumnya.", show_alert=True)
        return

    vip = get_active_vip_link()
    if not vip:
        await query.answer("⚠️ Belum ada link VIP aktif! Update dulu di panel → Update Link VIP.", show_alert=True)
        return

    update_tf_status(tf_id, "acc", admin_user.id)

    uid        = tf["user_id"]
    paket_type = tf.get("paket_type", "")
    vip_id     = vip["id"]

    if paket_type:
        update_user_membership(uid, paket_type)

    paket_label = (
        "\n📦 Paket: <b>1 Bulan</b>" if paket_type == "1_bulan" else
        "\n📦 Paket: <b>2 Bulan</b>" if paket_type == "2_bulan" else ""
    )
    body = (
        "🎉 <b>Pembayaran Berhasil!</b> 🔓\n\n"
        f"Terima kasih telah bergabung di <b>Joyland</b>!{paket_label}\n"
        "Klik tombol di bawah untuk masuk ke channel VIP.\n\n"
        "<i>⚠️ Tombol hanya berlaku satu kali.</i>"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔓 MASUK KE CHANNEL VIP — Klik Di Sini", callback_data=f"vip:open:{tf_id}:{vip_id}")
    ]])

    try:
        await context.bot.send_message(chat_id=uid, text=body, parse_mode=ParseMode.HTML, reply_markup=kb, protect_content=True)
    except TelegramError as e:
        logger.error(f"Gagal kirim link ke user {uid}: {e}")
        await query.answer("❌ Gagal kirim ke user. User mungkin blokir bot.", show_alert=True)
        update_tf_status(tf_id, "pending", 0)
        return

    admin_name = mdescape(admin_user.first_name or str(admin_user.id))
    await _update_all_tf_notifs(context, tf_id, f"✅ *DITERIMA* oleh {admin_name} \\— Link VIP telah dikirim\\.")
    await query.answer("✅ TF diterima! Link VIP sudah dikirim ke user.")


async def process_tf_tolak(query, context, tf_id: int, alasan: str):
    tf = get_tf(tf_id)
    if not tf:
        await query.answer("Data tidak ditemukan.", show_alert=True)
        return
    if tf["status"] != "pending":
        await query.answer("TF sudah diproses.", show_alert=True)
        return

    update_tf_status(tf_id, "tolak")
    try:
        await context.bot.send_message(
            chat_id=tf["user_id"],
            text=(
                f"❌ *Pembayaran Ditolak*\n\n"
                f"Maaf Kak, bukti transfer kamu ditolak\\.\n"
                f"Alasan: *{mdescape(alasan)}*\n\n"
                f"Silakan kirim ulang dengan bukti yang benar atau hubungi admin\\."
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except TelegramError:
        pass

    await _update_all_tf_notifs(context, tf_id, f"❌ *DITOLAK* — Alasan: {mdescape(alasan)}")
    await query.answer(f"❌ TF ditolak: {alasan}")



async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg  = update.message
    if not msg or not user:
        return

    upsert_user(user)

    if is_banned(user.id):
        await msg.reply_text("🚫 Akun kamu telah dibanned dari Joyland\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    if cfg_get("maintenance_mode") == "1" and not is_owner(user.id):
        await msg.reply_text("🔧 *Mode Maintenance* — Coba lagi nanti\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    state = context.user_data.get("state", S_IDLE)

    if state == S_UPLOAD_BUKTI:
        if msg.photo:
            paket_type = context.user_data.get("paket_type", "")
            context.user_data.clear()
            await handle_incoming_bukti(update, context, user, msg.photo[-1].file_id, paket_type)
        else:
            await msg.reply_text("📸 Harap kirim *foto* bukti transfer ya Kak\\!", parse_mode=ParseMode.MARKDOWN_V2)
        return

    if state == S_ADMIN_SEND_MSG_TF:
        tf_id      = context.user_data.get("target_tf_id")
        admin_name = msg.from_user.first_name
        tf_data    = get_tf(tf_id)
        if not tf_data:
            await msg.reply_text("❌ Data TF tidak ditemukan.")
            context.user_data.clear()
            return
        user_id     = tf_data["user_id"]
        pesan_admin = msg.text or msg.caption or ""
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📩 *Pesan dari Admin {mdescape(admin_name)} terkait Bukti TF Anda:*\n\n\"{mdescape(pesan_admin)}\"",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✍️ Balas Pesan Admin", callback_data="u:hubungi_admin")]]),
            )
            await msg.reply_text(
                "✅ Pesan berhasil terkirim ke user\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ ACC & Kirim Link", callback_data=f"tf:acc:{tf_id}")],
                    [
                        InlineKeyboardButton("❌ Tolak (Salah Nominal)", callback_data=f"tf:tolak:{tf_id}:nominal"),
                        InlineKeyboardButton("❌ Tolak (Bukti Palsu)",   callback_data=f"tf:tolak:{tf_id}:palsu"),
                    ],
                    [InlineKeyboardButton(f"✅ Sudah Dibalas ({admin_name})", callback_data="none")],
                ]),
            )
        except Exception as e:
            logger.error(f"Gagal kirim pesan TF ke user: {e}")
            await msg.reply_text(f"❌ Gagal mengirim pesan ke user: {mdescape(str(e))}", parse_mode=ParseMode.MARKDOWN_V2)
        context.user_data.clear()
        return

    if state == S_CHAT_LAPORAN:
        text = msg.text or msg.caption or ""
        if not text.strip():
            await msg.reply_text("Ketikkan pesan teks dulu ya Kak\\!", parse_mode=ParseMode.MARKDOWN_V2)
            return
        context.user_data.clear()
        await handle_incoming_chat(update, context, user, text)
        return

    if state == S_ADMIN_REPLY:
        session_id = context.user_data.get("reply_session_id")
        if not session_id:
            context.user_data.clear()
            return
        reply_text = msg.text or msg.caption or ""
        if not reply_text.strip():
            await msg.reply_text("Harap kirim pesan teks\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return
        context.user_data.clear()
        await handle_admin_reply(update, context, user, session_id, reply_text)
        return

    if state == S_BROADCAST:
        target = context.user_data.get("broadcast_target", "global")
        context.user_data.clear()
        asyncio.create_task(
            _safe_broadcast_task(update, context, user, target),
            name=f"bc_{user.id}_{int(asyncio.get_event_loop().time())}",
        )
        return

    if state == S_BROADCAST_USERNAME:
        context.user_data.clear()
        asyncio.create_task(
            _safe_broadcast_username_task(update, context, user),
            name=f"bc_user_{user.id}_{int(asyncio.get_event_loop().time())}",
        )
        return

    if state == S_BUTTON_BUILDER:
        context.user_data.clear()
        await handle_button_builder_input(update, context, user)
        return

    if state == S_EDIT_WELCOME_TEXT:
        new_text = msg.text or ""
        if new_text.strip():
            cfg_set("welcome_text", mdescape(new_text))
            context.user_data.clear()
            await msg.reply_text("✅ Teks welcome berhasil diperbarui\\!", parse_mode=ParseMode.MARKDOWN_V2,
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ke Panel", callback_data="nav:main")]]))
        return

    if state == S_EDIT_WELCOME_MEDIA:
        if msg.photo:
            cfg_set("welcome_media", msg.photo[-1].file_id)
            context.user_data.clear()
            await msg.reply_text("✅ Foto welcome berhasil diperbarui\\!", parse_mode=ParseMode.MARKDOWN_V2,
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ke Panel", callback_data="nav:main")]]))
        else:
            await msg.reply_text("📸 Kirimkan foto ya Kak\\!", parse_mode=ParseMode.MARKDOWN_V2)
        return

    if state == S_EDIT_PAYMENT_TEXT:
        new_text = msg.text or ""
        if new_text.strip():
            cfg_set("payment_text", mdescape(new_text))
            context.user_data.clear()
            await msg.reply_text("✅ Teks payment berhasil diperbarui\\!", parse_mode=ParseMode.MARKDOWN_V2,
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ke Panel", callback_data="nav:main")]]))
        return

    if state == S_EDIT_PAYMENT_MEDIA:
        if msg.photo:
            cfg_set("payment_media", msg.photo[-1].file_id)
            context.user_data.clear()
            await msg.reply_text("✅ Foto QRIS berhasil diperbarui\\!", parse_mode=ParseMode.MARKDOWN_V2,
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ke Panel", callback_data="nav:main")]]))
        else:
            await msg.reply_text("📸 Kirimkan foto QRIS ya Kak\\!", parse_mode=ParseMode.MARKDOWN_V2)
        return

    if state == S_EDIT_VIP_TEXT:
        new_text = msg.text or ""
        if new_text.strip():
            cfg_set("vip_info_text", mdescape(new_text))
            context.user_data.clear()
            await msg.reply_text("✅ *Info VIP berhasil diupdate\\!*", parse_mode=ParseMode.MARKDOWN_V2,
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ke Panel", callback_data="nav:main")]]))
        return

    if state == S_EDIT_VIP_MEDIA:
        if msg.photo:
            cfg_set("vip_info_media", msg.photo[-1].file_id)
            context.user_data.clear()
            await msg.reply_text("✅ *Foto VIP berhasil diupdate\\!*", parse_mode=ParseMode.MARKDOWN_V2,
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ke Panel", callback_data="nav:main")]]))
        else:
            await msg.reply_text("📸 *Harap kirim foto untuk Info VIP ya Kak\\!*", parse_mode=ParseMode.MARKDOWN_V2)
        return

    if state == S_EDIT_VIP_LINK:
        link = (msg.text or "").strip()
        if link.startswith("http"):
            set_vip_link(link, user.id)
            context.user_data.clear()
            await msg.reply_text(
                f"✅ *Link VIP berhasil diperbarui\\!*\n\n🔗 `{mdescape(link)}`",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ke Panel", callback_data="nav:main")]]),
            )
        else:
            await msg.reply_text("⚠️ Format tidak valid\\. Link harus diawali `https://`\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    if state == S_ADD_ADMIN:
        if not is_owner(user.id):
            context.user_data.clear()
            return
        try:
            new_id = int((msg.text or "").strip())
        except ValueError:
            await msg.reply_text("⚠️ Format ID tidak valid\\. Kirimkan angka ID Telegram\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return
        if is_owner(new_id):
            await msg.reply_text("⚠️ ID tersebut adalah Owner Mutlak, tidak perlu ditambah\\.", parse_mode=ParseMode.MARKDOWN_V2)
            context.user_data.clear()
            return
        add_admin(new_id, user.id)
        context.user_data.clear()
        await msg.reply_text(
            f"✅ *Admin baru berhasil ditambahkan\\!*\n\nID: `{new_id}`\n\n"
            "Gunakan menu *Kelola Admin* untuk atur izin akses\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Atur Izin", callback_data=f"o:adm_perm:{new_id}")],
                [InlineKeyboardButton("🔙 Ke Panel",  callback_data="nav:main")],
            ]),
        )
        return

    if state == S_EDIT_REMINDER_TEXT_1:
        new_text = (msg.text or "").strip()
        if not new_text:
            await msg.reply_text("⚠️ Teks tidak boleh kosong\\. Coba lagi atau ketik /batal\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return
        cfg_set("reminder_text_1_bulan", new_text)
        context.user_data.clear()
        await msg.reply_text(
            "✅ <b>Teks pengingat Paket 1 Bulan berhasil diperbarui!</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Ke Pengaturan Pengingat", callback_data="o:reminder_settings")],
                [InlineKeyboardButton("🏠 Ke Panel",                callback_data="nav:main")],
            ]),
        )
        return

    if state == S_EDIT_REMINDER_TEXT_2:
        new_text = (msg.text or "").strip()
        if not new_text:
            await msg.reply_text("⚠️ Teks tidak boleh kosong\\. Coba lagi atau ketik /batal\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return
        cfg_set("reminder_text_2_bulan", new_text)
        context.user_data.clear()
        await msg.reply_text(
            "✅ <b>Teks pengingat Paket 2 Bulan berhasil diperbarui!</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Ke Pengaturan Pengingat", callback_data="o:reminder_settings")],
                [InlineKeyboardButton("🏠 Ke Panel",                callback_data="nav:main")],
            ]),
        )
        return

    if not is_admin(user.id):
        await send_user_menu(msg, context, protect=True)



async def handle_incoming_bukti(update, context, user, file_id: str, paket_type: str = ""):
    uinfo = get_user_info(user.id) or {}
    name  = (uinfo.get("first_name","") + " " + uinfo.get("last_name","")).strip() or "Unknown"
    uname = f"@{uinfo['username']}" if uinfo.get("username") else "No Username"

    tf_id = create_tf(user.id, file_id, paket_type)

    paket_label_md = (
        "\n📦 Paket: *1 Bulan*" if paket_type == "1_bulan" else
        "\n📦 Paket: *2 Bulan*" if paket_type == "2_bulan" else ""
    )
    caption = (
        f"📩 *SETORAN BARU MASUK\\!* \\#TF{tf_id}\n\n"
        f"👤 *{mdescape(name)}*\n"
        f"🔗 {mdescape(uname)}\n"
        f"🆔 `{user.id}`"
        f"{paket_label_md}\n"
        f"🕐 {mdescape(datetime.now().strftime('%d %b %Y, %H:%M'))} WIB"
    )
    tf_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Terima & Kirim Link", callback_data=f"tf:acc:{tf_id}")],
        [
            InlineKeyboardButton("❌ Tolak (Salah Nominal)", callback_data=f"tf:tolak:{tf_id}:nominal"),
            InlineKeyboardButton("❌ Tolak (Bukti Palsu)",   callback_data=f"tf:tolak:{tf_id}:palsu"),
        ],
        [InlineKeyboardButton("💬 Kirim Pesan ke User", callback_data=f"tf:msg:{tf_id}")],
        [InlineKeyboardButton("🚫 Ban User",            callback_data=f"tf:ban:{tf_id}")],
    ])

    targets = list(OWNER_IDS)
    for adm in all_admins():
        if adm.get("perm_acc_tf") and adm["admin_id"] not in targets:
            targets.append(adm["admin_id"])

    for target_id in targets:
        try:
            sent = await context.bot.send_photo(
                chat_id=target_id, photo=file_id, caption=caption,
                parse_mode=ParseMode.MARKDOWN_V2, reply_markup=tf_kb,
            )
            save_admin_tf_notif(tf_id, target_id, sent.message_id, target_id)
        except TelegramError as e:
            logger.warning(f"Gagal kirim notif TF ke {target_id}: {e}")

    paket_confirm = (
        "\n📦 Paket: *1 Bulan*" if paket_type == "1_bulan" else
        "\n📦 Paket: *2 Bulan*" if paket_type == "2_bulan" else ""
    )
    await update.message.reply_text(
        "✅ *Bukti transfer diterima\\!*\n\n"
        "Admin sedang memverifikasi pembayaran kamu\\.\n"
        f"{paket_confirm}\n"
        "⏱ Estimasi: *1\\-5 menit*\n\n"
        "Kamu akan menerima link VIP otomatis setelah disetujui 🎉",
        parse_mode=ParseMode.MARKDOWN_V2,
        protect_content=True,
    )



async def handle_incoming_chat(update, context, user, text: str):
    uinfo      = get_user_info(user.id) or {}
    name       = (uinfo.get("first_name","") + " " + uinfo.get("last_name","")).strip() or "Unknown"
    uname      = f"@{uinfo['username']}" if uinfo.get("username") else "No Username"
    session_id = create_chat_session(user.id, text)

    admin_text = (
        f"📥 *PESAN BARU* \\#CS{session_id}\n\n"
        f"👤 *{mdescape(name)}*\n"
        f"🔗 {mdescape(uname)}\n"
        f"🆔 `{user.id}`\n\n"
        f"💬 _\"{mdescape(text[:300])}\"_\n\n"
        f"🕐 {mdescape(datetime.now().strftime('%d %b %Y, %H:%M'))} WIB"
    )
    chat_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Balas", callback_data=f"chat:reply:{session_id}")],
        [InlineKeyboardButton("🚫 Ban User", callback_data=f"chat:ban:{session_id}")],
    ])

    targets = list(OWNER_IDS)
    for adm in all_admins():
        if adm.get("perm_reply_chat") and adm["admin_id"] not in targets:
            targets.append(adm["admin_id"])

    for target_id in targets:
        try:
            sent = await context.bot.send_message(
                chat_id=target_id, text=admin_text,
                parse_mode=ParseMode.MARKDOWN_V2, reply_markup=chat_kb,
            )
            save_admin_chat_notif(session_id, target_id, sent.message_id, target_id)
        except TelegramError as e:
            logger.warning(f"Gagal kirim notif chat ke {target_id}: {e}")

    await update.message.reply_text(
        "✅ *Pesan diterima\\!*\n\nAdmin akan segera membalas\\. Harap tunggu ya Kak\\! 🙏\n⏱ Estimasi: *1\\-15 menit*",
        parse_mode=ParseMode.MARKDOWN_V2,
        protect_content=True,
    )



async def handle_admin_reply(update, context, admin_user, session_id: int, reply: str):
    session = get_chat_session(session_id)
    if not session:
        await update.message.reply_text("⚠️ Sesi chat tidak ditemukan\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    uid = session["user_id"]
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=(
                f"💬 *Balasan dari Admin {mdescape(BOT_NAME)}*\n\n"
                f"{mdescape(reply)}\n\n"
                f"_— Tim {mdescape(BOT_NAME)}_"
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
            protect_content=True,
        )
        close_chat_session(session_id)
        await _update_all_chat_notifs(
            context, session_id,
            f"✅ *Dibalas* oleh {mdescape(admin_user.first_name or str(admin_user.id))}",
        )
        await update.message.reply_text(
            f"✅ Balasan terkirim ke user `{uid}`\\!",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ke Panel", callback_data="nav:main")]]),
        )
    except TelegramError as e:
        logger.error(f"Gagal kirim balasan ke {uid}: {e}")
        await update.message.reply_text("❌ Gagal kirim\\. User mungkin memblokir bot\\.", parse_mode=ParseMode.MARKDOWN_V2)



async def _safe_broadcast_task(update, context, admin_user, target: str):
    """Wrapper aman untuk broadcast — error apapun tidak crash bot."""
    try:
        await handle_broadcast(update, context, admin_user, target)
    except Exception as e:
        logger.error(f"[BROADCAST] Error fatal di broadcast task: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                f"❌ <b>Broadcast berhenti karena error tidak terduga.</b>\n"
                f"<code>{html_escape(str(e)[:300])}</code>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


async def _safe_broadcast_username_task(update, context, admin_user):
    """Wrapper aman untuk broadcast username."""
    try:
        await handle_broadcast_username(update, context, admin_user)
    except Exception as e:
        logger.error(f"[BROADCAST_USER] Error fatal: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                f"❌ <b>Broadcast username berhenti karena error.</b>\n"
                f"<code>{html_escape(str(e)[:300])}</code>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


async def _send_broadcast_msg(bot, uid: int, msg) -> bool:
    """
    Kirim satu pesan broadcast ke uid.
    Coba dengan HTML dulu, fallback ke plain text jika gagal parse.
    Return True jika berhasil, False jika gagal permanen.
    """
    from telegram.error import RetryAfter, Forbidden, ChatMigrated
    caption_raw  = sanitize_text(msg.caption or "")
    text_raw     = sanitize_text(msg.text or "")

    for attempt in range(2):
        parse = ParseMode.HTML if attempt == 0 else None
        cap   = caption_raw if attempt == 0 else re.sub(r'<[^>]+>', '', caption_raw)
        txt   = text_raw    if attempt == 0 else re.sub(r'<[^>]+>', '', text_raw)
        try:
            if msg.photo:
                await bot.send_photo(uid, msg.photo[-1].file_id,
                                     caption=cap or None, parse_mode=parse)
            elif msg.video:
                await bot.send_video(uid, msg.video.file_id,
                                     caption=cap or None, parse_mode=parse)
            elif msg.animation:
                await bot.send_animation(uid, msg.animation.file_id,
                                         caption=cap or None, parse_mode=parse)
            elif msg.document:
                await bot.send_document(uid, msg.document.file_id,
                                        caption=cap or None, parse_mode=parse)
            elif msg.sticker:
                await bot.send_sticker(uid, msg.sticker.file_id)
            elif msg.voice:
                await bot.send_voice(uid, msg.voice.file_id,
                                     caption=cap or None, parse_mode=parse)
            elif msg.audio:
                await bot.send_audio(uid, msg.audio.file_id,
                                     caption=cap or None, parse_mode=parse)
            elif txt:
                await bot.send_message(uid, txt, parse_mode=parse)
            else:
                return True
            return True
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            continue
        except Forbidden:
            return False
        except ChatMigrated:
            return False
        except BadRequest:
            if attempt == 0:
                continue
            return False
        except TelegramError:
            return False
        except Exception:
            return False
    return False


async def handle_broadcast(update, context, admin_user, target: str = "global"):
    msg = update.message

    if target == "1_bulan":
        users        = get_member_ids_by_type("1_bulan")
        target_label = "member 1 Bulan"
    elif target == "2_bulan":
        users        = get_member_ids_by_type("2_bulan")
        target_label = "member 2 Bulan"
    elif target.startswith("period:"):
        parts         = target.split(":", 2)
        paket_type    = parts[1]
        start_periode = parts[2]
        users         = get_user_ids_by_period(paket_type, start_periode)
        label_bln     = _label_periode(start_periode, paket_type)
        paket_str     = "1 Bulan" if paket_type == "1_bulan" else "2 Bulan"
        target_label  = f"member {paket_str} — Periode {label_bln}"
    else:
        users        = all_user_ids()
        target_label = "semua user"

    total      = len(users)
    status_msg = await msg.reply_text(
        f"📢 <b>Broadcast dimulai!</b>\n"
        f"Target: <b>{html_escape(target_label)}</b>\n"
        f"Mengirim ke <b>{total:,}</b> user...\n"
        f"<i>Bot tetap aktif dan bisa menerima pesan selama broadcast berlangsung.</i>",
        parse_mode=ParseMode.HTML,
    )

    success = failed = 0
    UPDATE_EVERY = 50
    for i, uid in enumerate(users, 1):
        ok = await _send_broadcast_msg(context.bot, uid, msg)
        if ok:
            success += 1
        else:
            failed += 1

        if i % UPDATE_EVERY == 0 or i == total:
            try:
                await status_msg.edit_text(
                    f"📢 <b>Broadcast berjalan...</b>\n"
                    f"🎯 Target: <b>{html_escape(target_label)}</b>\n"
                    f"📨 Progress: <b>{i}/{total}</b>\n"
                    f"✅ Berhasil: <b>{success:,}</b>  ❌ Gagal: <b>{failed:,}</b>",
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass

        await asyncio.sleep(0.05)

    try:
        await status_msg.edit_text(
            f"📊 <b>Broadcast Selesai!</b>\n\n"
            f"🎯 Target: <b>{html_escape(target_label)}</b>\n"
            f"✅ Berhasil: <b>{success:,}</b>\n"
            f"❌ Gagal: <b>{failed:,}</b>\n"
            f"📨 Total: <b>{total:,}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Kembali ke Broadcast Center",
                                     callback_data="o:broadcast_system")
            ]]),
        )
    except TelegramError:
        pass


async def handle_broadcast_username(update, context, admin_user):
    msg       = update.message
    raw       = sanitize_text(msg.text or "").strip()
    SEPARATOR = "======"
    if SEPARATOR not in raw:
        await msg.reply_text(
            "❌ <b>Format salah!</b>\n\nGunakan:\n<code>@user1, @user2\n======\nIsi pesan...</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="o:broadcast_system")]]),
        )
        return

    parts         = raw.split(SEPARATOR, 1)
    usernames_raw = parts[0].strip()
    pesan         = parts[1].strip() if len(parts) > 1 else ""
    if not pesan:
        await msg.reply_text("❌ Isi pesan tidak boleh kosong!", parse_mode=ParseMode.HTML)
        return

    username_list = [
        u.strip().lstrip("@")
        for u in usernames_raw.replace("\n", ",").split(",")
        if u.strip().lstrip("@")
    ]
    if not username_list:
        await msg.reply_text("❌ Tidak ada username yang valid.", parse_mode=ParseMode.HTML)
        return

    status_msg = await msg.reply_text(
        f"📝 <b>Broadcast Username dimulai...</b>\n"
        f"Memproses <b>{len(username_list)}</b> username...\n"
        f"<i>Bot tetap aktif selama proses berlangsung.</i>",
        parse_mode=ParseMode.HTML,
    )
    success = failed = 0
    not_found = []
    for uname in username_list:
        uid = get_user_id_by_username(uname)
        if uid is None:
            not_found.append(f"@{html_escape(uname)}")
            failed += 1
            continue
        try:
            sent = False
            for attempt in range(2):
                try:
                    await context.bot.send_message(
                        uid, pesan,
                        parse_mode=ParseMode.HTML if attempt == 0 else None,
                    )
                    sent = True
                    break
                except BadRequest:
                    if attempt == 0:
                        continue
                    break
            if sent:
                success += 1
            else:
                failed += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)

    not_found_text = ""
    if not_found:
        safe_list = ', '.join(not_found[:20])
        not_found_text = f"\n\n⚠️ <b>Tidak ditemukan di DB:</b>\n{safe_list}"
        if len(not_found) > 20:
            not_found_text += f" (+{len(not_found)-20} lainnya)"
    try:
        await status_msg.edit_text(
            f"📊 <b>Broadcast Username Selesai!</b>\n\n"
            f"✅ Berhasil: <b>{success}</b>\n"
            f"❌ Gagal/Tidak ditemukan: <b>{failed}</b>\n"
            f"📨 Total: <b>{len(username_list)}</b>{not_found_text}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Kembali", callback_data="o:broadcast_system")]]),
        )
    except TelegramError:
        pass



async def handle_button_builder_input(update, context, admin_user):
    text = (update.message.text or "").strip()
    if "|" not in text:
        await update.message.reply_text(
            "⚠️ Format salah\\!\n\n*URL:* `Nama | https://t\\.me/link`\n*Teks:* `Nama | Teks: isi pesan`",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ke Button Builder", callback_data="o:button_builder")]]),
        )
        return

    name_part, value_part = text.split("|", 1)
    name_part  = name_part.strip()
    value_part = value_part.strip()
    if not name_part or not value_part:
        await update.message.reply_text("⚠️ Nama tombol dan nilai tidak boleh kosong\\!", parse_mode=ParseMode.MARKDOWN_V2)
        return

    if value_part.startswith("http"):
        btype = "url"
    elif value_part.lower().startswith("teks:"):
        btype      = "text"
        value_part = value_part[5:].strip()
    else:
        btype = "text"

    add_custom_button(name_part, btype, value_part, admin_user.id)
    await update.message.reply_text(
        f"✅ *Tombol berhasil ditambahkan\\!*\n\n📝 Nama: `{mdescape(name_part)}`\n🔗 Tipe: `{btype}`",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Lihat Button Builder", callback_data="o:button_builder")],
            [InlineKeyboardButton("🔙 Ke Panel",             callback_data="nav:main")],
        ]),
    )



async def job_vip_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Cron job harian — kirim pengingat perpanjangan VIP ke member
    yang masa aktifnya mendekati habis.
    Antrian terpisah untuk paket 1 bulan dan 2 bulan.
    Pengiriman ulang dicegah oleh tabel sent_reminders.
    """
    today = datetime.now().date()
    logger.info(f"[REMINDER] Menjalankan job harian — {today}")

    for paket_type in ("1_bulan", "2_bulan"):
        reminder_days = get_reminder_days(paket_type)
        if not reminder_days:
            continue

        paket_label       = "Paket 1 Bulan" if paket_type == "1_bulan" else "Paket 2 Bulan"
        reminder_template = cfg_get(f"reminder_text_{paket_type}", "").strip()
        if not reminder_template:
            reminder_template = (
                f"🔔 PENGINGAT MASA AKTIF VIP\n\n"
                f"Halo Kak {{nama}}! Masa langganan {{paket}} kamu akan berakhir pada {{tanggal_exp}}.\n\n"
                f"Yuk perpanjang sekarang agar akses VIP kamu tidak terputus! 🙏"
            )

        members = get_members_for_reminder(paket_type)
        logger.info(f"[REMINDER] {paket_type}: {len(members)} member diperiksa, hari={reminder_days}")

        for member in members:
            uid         = member["user_id"]
            vip_end_raw = member.get("vip_end_date", "")
            if not vip_end_raw:
                continue
            try:
                vip_end = datetime.strptime(vip_end_raw[:10], "%Y-%m-%d").date()
            except ValueError:
                continue

            days_left = (vip_end - today).days
            if days_left not in reminder_days:
                continue
            if has_reminder_sent(uid, paket_type, days_left):
                continue

            nama = safe_display_name(
                first    = member.get("first_name", ""),
                last     = member.get("last_name", ""),
                username = member.get("username", ""),
                fallback = "Kak",
            )
            tanggal_exp = vip_end.strftime("%d %B %Y")
            teks_kirim  = format_reminder_text(reminder_template, nama, paket_label, tanggal_exp)

            reminder_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Perpanjang Sekarang", callback_data="u:kirim_bukti")],
                [InlineKeyboardButton("💬 Hubungi Admin",       callback_data="u:hubungi_admin")],
            ])

            try:
                await context.bot.send_message(chat_id=uid, text=teks_kirim, reply_markup=reminder_kb)
                mark_reminder_sent(uid, paket_type, days_left)
                logger.info(f"[REMINDER] ✅ Kirim ke {uid} ({paket_type}) H-{days_left}")
            except TelegramError as e:
                logger.warning(f"[REMINDER] ❌ Gagal kirim ke {uid}: {e}")

            await asyncio.sleep(0.1)

    logger.info("[REMINDER] Job selesai.")



async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if err is None:
        return
    err_name = type(err).__name__

    if isinstance(err, BadRequest):
        ignored = [
            "Message is not modified", "Query is too old",
            "MESSAGE_ID_INVALID", "Message to edit not found",
            "There is no text in the message to edit",
            "Can't parse entities",
        ]
        if any(x in str(err) for x in ignored):
            return

    if err_name in ("NetworkError", "TimedOut", "RetryAfter", "Forbidden",
                    "ChatMigrated", "InvalidToken"):
        return

    logger.error(f"Unhandled error [{err_name}]: {err}", exc_info=err)



def main():
    import datetime as _dt
    print()
    print("=" * 60)
    print(f"  🎡  {BOT_NAME} Bot v6.0 — {BOT_USERNAME}")
    print("=" * 60)
    print(f"  Owner IDs  : {OWNER_IDS}")
    print(f"  Database   : {DB_FILE}")
    print(f"  Log file   : joyland.log")
    print(f"  Broadcast Center v2.0 (Periode Kalender) ✅")
    print("=" * 60)
    print()

    init_db()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    job_queue = app.job_queue
    if job_queue is not None:
        job_queue.run_daily(
            job_vip_reminder,
            time=_dt.time(hour=2, minute=0, second=0),
            name="vip_daily_reminder",
        )
        logger.info("✅ Cron job VIP reminder terdaftar (02:00 UTC / 09:00 WIB)")
    else:
        logger.warning(
            "⚠️  JobQueue tidak tersedia.\n"
            "    Install: pip install \"python-telegram-bot[job-queue]==20.7\"\n"
            "    Fitur reminder otomatis tidak akan berjalan."
        )

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("panel",    cmd_panel))
    app.add_handler(CommandHandler("addadmin", cmd_addadmin))
    app.add_handler(CommandHandler("bc",       cmd_bc))
    app.add_handler(CommandHandler("unban",    cmd_unban))
    app.add_handler(CommandHandler("batal",    cmd_batal))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)

    print("✅ Bot aktif! Tekan Ctrl+C untuk berhenti.\n")
    logger.info(f"🟢 {BOT_NAME} Bot v6.0 dimulai")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
        poll_interval=0.0,
        timeout=30,
        close_loop=False,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot dihentikan oleh user.")
    except Exception as e:
        logger.critical(f"Bot berhenti total karena error: {e}", exc_info=True)
