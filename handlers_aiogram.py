import re
import asyncio
import time
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from fetchers import fetch_all
from parser import parse
from scorer import score
from formatters import build_full_report, build_score_card
from config import REPORT_URL, TG_CHANNEL

SOL_RE = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")
_last: dict[int, float] = {}

def _limited(uid):
    now = time.time()
    if now - _last.get(uid, 0) < 8:
        return True
    _last[uid] = now
    return False

def report_kb(dex_url=None):
    rows = []
    if dex_url:
        rows.append([InlineKeyboardButton(text="📈 DexScreener", url=dex_url)])
    rows.append([
        InlineKeyboardButton(text="🌐 Web Scanner", url=REPORT_URL),
        InlineKeyboardButton(text="⚡ $FLASH", url=TG_CHANNEL),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def do_analyze(message: Message, mint: str, full=True):
    if _limited(message.from_user.id):
        await message.answer("⏳ Please wait a few seconds before scanning again.")
        return
    if not SOL_RE.fullmatch(mint):
        await message.answer("❌ *Invalid address.* Please paste a valid Solana token address.", parse_mode="Markdown")
        return

    msg = await message.answer(
        "☀️ *Solar Signal scanning...*\n\n"
        "⛓ Fetching on-chain data\n"
        "📊 Pulling market intelligence\n"
        "🧠 Running risk analysis\n"
        "⊙ Generating AI signal",
        parse_mode="Markdown"
    )
    try:
        raw    = await asyncio.wait_for(fetch_all(mint), timeout=25)
        data   = parse(mint, raw)
        scores = score(data)
        text   = build_full_report(data, scores) if full else build_score_card(data, scores)
        await msg.edit_text(text, parse_mode="Markdown",
                            reply_markup=report_kb(data.get("dexUrl")),
                            disable_web_page_preview=True)
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ *Analysis timed out.* Please try again.", parse_mode="Markdown")
    except Exception as e:
        print(f"Error: {e}")
        await msg.edit_text("❌ *Could not analyze this token.*\n\nCheck the address and try again.", parse_mode="Markdown")

def register_handlers(dp: Dispatcher):

    @dp.message(Command("start"))
    async def cmd_start(message: Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Web Scanner", url=REPORT_URL)],
            [InlineKeyboardButton(text="⚡ Join $FLASH", url=TG_CHANNEL)],
        ])
        await message.answer(
            "☀️ *SOLAR SIGNAL BOT*\n"
            "_by Solar Flash — Elite Solana Intelligence_\n\n"
            "Paste any Solana token address to get a full risk report.\n\n"
            "/analyze `<address>` — Full report\n"
            "/score `<address>` — Quick score\n"
            "/help — How to use\n"
            "/about — About $FLASH",
            parse_mode="Markdown", reply_markup=kb
        )

    @dp.message(Command("help"))
    async def cmd_help(message: Message):
        await message.answer(
            "☀️ *HOW TO USE*\n\n"
            "Just paste a Solana token address:\n"
            "`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`\n\n"
            "Or:\n"
            "/analyze `<address>` — Full intelligence report\n"
            "/score `<address>` — Quick score card",
            parse_mode="Markdown"
        )

    @dp.message(Command("about"))
    async def cmd_about(message: Message):
        await message.answer(
            "⊙ *SOLAR SIGNAL BOT — by Solar Flash*\n\n"
            "_Built to detect signal before noise._\n\n"
            "📡 Data: Helius · DexScreener · RugCheck\n"
            f"🌐 {REPORT_URL}\n"
            f"⚡ {TG_CHANNEL}",
            parse_mode="Markdown", disable_web_page_preview=True
        )

    @dp.message(Command("analyze"))
    async def cmd_analyze(message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.answer("⚠️ Usage: `/analyze <token_address>`", parse_mode="Markdown")
            return
        await do_analyze(message, args[1].strip(), full=True)

    @dp.message(Command("score"))
    async def cmd_score(message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.answer("⚠️ Usage: `/score <token_address>`", parse_mode="Markdown")
            return
        await do_analyze(message, args[1].strip(), full=False)

    @dp.message()
    async def handle_msg(message: Message):
        text  = message.text or ""
        match = SOL_RE.search(text)
        if match:
            await do_analyze(message, match.group(), full=True)
        else:
            await message.answer(
                "⊙ Paste a Solana token address to scan.\n\n"
                "Example:\n`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`",
                parse_mode="Markdown"
            )
