import sqlite3
import datetime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)

TOKEN = "8676554727:AAFZW6M2y6h3DBchuHCXu7mRTJ9anY4O00Q"
DB = "ledger.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            category TEXT,
            note TEXT,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_record(user_id, rtype, amount, category, note=""):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO records (user_id, type, amount, category, note, date) VALUES (?,?,?,?,?,?)",
        (user_id, rtype, amount, category, note, datetime.date.today().isoformat())
    )
    conn.commit()
    conn.close()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 记账机器人已启动\n\n"
        "/add 金额 分类 [备注] 记支出\n"
        "/income 金额 分类 [备注] 记收入\n"
        "/today 今日收支\n"
        "/month 本月收支\n"
        "/list 最近10笔\n"
        "/del ID 删除记录\n"
        "/stats 本月分类统计"
    )

async def add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("用法：/add 金额 分类 [备注]")
        return
    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("金额格式不对")
        return
    category = args[1]
    note = " ".join(args[2:]) if len(args) > 2 else ""
    add_record(update.effective_user.id, "expense", amount, category, note)
    await update.message.reply_text(f"✅ 已记录支出 {amount} 元 · {category} {note}")

async def income(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("用法：/income 金额 分类 [备注]")
        return
    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("金额格式不对")
        return
    category = args[1]
    note = " ".join(args[2:]) if len(args) > 2 else ""
    add_record(update.effective_user.id, "income", amount, category, note)
    await update.message.reply_text(f"✅ 已记录收入 {amount} 元 · {category} {note}")

def query_sum(user_id, start_date):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "SELECT type, SUM(amount) FROM records WHERE user_id=? AND date>=? GROUP BY type",
        (user_id, start_date)
    )
    rows = c.fetchall()
    conn.close()
    d = {"expense": 0, "income": 0}
    for t, s in rows:
        d[t] = s or 0
    return d

async def today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    d = query_sum(update.effective_user.id, datetime.date.today().isoformat())
    await update.message.reply_text(
        f"📅 今日\n支出：{d['expense']:.2f} 元\n收入：{d['income']:.2f} 元\n结余：{d['income']-d['expense']:.2f} 元"
    )

async def month(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    first = datetime.date.today().replace(day=1).isoformat()
    d = query_sum(update.effective_user.id, first)
    await update.message.reply_text(
        f"🗓 本月\n支出：{d['expense']:.2f} 元\n收入：{d['income']:.2f} 元\n结余：{d['income']-d['expense']:.2f} 元"
    )

async def list_records(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "SELECT id, type, amount, category, note, date FROM records WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (update.effective_user.id,)
    )
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("暂无记录")
        return
    lines = []
    for r in rows:
        sign = "-" if r[1] == "expense" else "+"
        lines.append(f"#{r[0]} {r[5]} {sign}{r[2]:.2f} {r[3]} {r[4]}")
    await update.message.reply_text("\n".join(lines))

async def delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("用法：/del ID")
        return
    try:
        rid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("ID 格式不对")
        return
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM records WHERE id=? AND user_id=?", (rid, update.effective_user.id))
    conn.commit()
    conn.close()
    await update.message.reply_text("🗑 已删除" if c.rowcount else "未找到该记录")

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    first = datetime.date.today().replace(day=1).isoformat()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "SELECT category, SUM(amount) FROM records WHERE user_id=? AND type='expense' AND date>=? GROUP BY category ORDER BY SUM(amount) DESC",
        (update.effective_user.id, first)
    )
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("本月暂无支出")
        return
    total = sum(r[1] for r in rows)
    lines = [f"📊 本月支出统计（共 {total:.2f} 元）"]
    for cat, s in rows:
        pct = s / total * 100
        lines.append(f"{cat}：{s:.2f} 元（{pct:.1f}%）")
    await update.message.reply_text("\n".join(lines))

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("income", income))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("month", month))
    app.add_handler(CommandHandler("list", list_records))
    app.add_handler(CommandHandler("del", delete))
    app.add_handler(CommandHandler("stats", stats))
    print("Bot 启动中...")
    app.run_polling()

if __name__ == "__main__":
    main()
