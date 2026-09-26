import random
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from PIL import Image, ImageDraw, ImageFont

TOKEN = "8625559038:AAG2kfcvIfm1SLBSZ_O2ovs2UPZdWQFTYy8"
MY_ID = 709900282  # твой Telegram ID

STATE_FILE = "ufc_state.json"
IMG_W, IMG_H = 1080, 1080


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"champion": None, "challenger": None, "history": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


state = load_state()


def only_me(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != MY_ID:
            return
        return await func(update, ctx)
    return wrapper


def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_octagon(draw, cx, cy, radius, color=(40, 40, 40), width=8):
    import math
    points = []
    for i in range(8):
        angle = math.pi / 8 + i * math.pi / 4
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        points.append((x, y))
    draw.polygon(points, outline=color, width=width)


def draw_fighter(draw, cx, cy, scale=1.0, color=(200, 200, 200)):
    head_r = int(28 * scale)
    draw.ellipse(
        [cx - head_r, cy - int(120 * scale) - head_r,
         cx + head_r, cy - int(120 * scale) + head_r],
        fill=color
    )
    draw.polygon([
        (cx - int(30 * scale), cy - int(90 * scale)),
        (cx + int(30 * scale), cy - int(90 * scale)),
        (cx + int(25 * scale), cy + int(10 * scale)),
        (cx - int(25 * scale), cy + int(10 * scale)),
    ], fill=color)
    draw.line([
        (cx - int(28 * scale), cy - int(80 * scale)),
        (cx - int(60 * scale), cy - int(120 * scale)),
        (cx - int(70 * scale), cy - int(160 * scale)),
    ], fill=color, width=int(14 * scale))
    draw.line([
        (cx + int(28 * scale), cy - int(80 * scale)),
        (cx + int(55 * scale), cy - int(40 * scale)),
        (cx + int(50 * scale), cy + int(10 * scale)),
    ], fill=color, width=int(14 * scale))
    draw.line([
        (cx - int(18 * scale), cy + int(10 * scale)),
        (cx - int(25 * scale), cy + int(70 * scale)),
        (cx - int(20 * scale), cy + int(120 * scale)),
    ], fill=color, width=int(16 * scale))
    draw.line([
        (cx + int(18 * scale), cy + int(10 * scale)),
        (cx + int(25 * scale), cy + int(70 * scale)),
        (cx + int(20 * scale), cy + int(120 * scale)),
    ], fill=color, width=int(16 * scale))


def draw_belt(draw, cx, cy, w=300, h=60):
    draw.rectangle(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
        fill=(180, 140, 20)
    )
    plate_w, plate_h = 120, 90
    draw.rectangle(
        [cx - plate_w // 2, cy - plate_h // 2,
         cx + plate_w // 2, cy + plate_h // 2],
        fill=(255, 215, 0)
    )
    draw.rectangle(
        [cx - plate_w // 2 + 10, cy - plate_h // 2 + 10,
         cx - plate_w // 2 + 30, cy + plate_h // 2 - 10],
        fill=(255, 240, 150)
    )
    font = get_font(36, bold=True)
    text = "UFC"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 5), text,
              font=font, fill=(80, 40, 0))


def generate_image(nick, status):
    img = Image.new("RGB", (IMG_W, IMG_H), (10, 10, 12))
    draw = ImageDraw.Draw(img)

    for pos in [(200, 150), (880, 150), (540, 80)]:
        draw.ellipse(
            [pos[0] - 120, pos[1] - 120, pos[0] + 120, pos[1] + 120],
            fill=(25, 25, 30)
        )

    draw_octagon(draw, IMG_W // 2, IMG_H // 2 + 50, 420,
                 color=(90, 90, 90), width=10)
    draw_octagon(draw, IMG_W // 2, IMG_H // 2 + 50, 380,
                 color=(50, 50, 50), width=4)

    draw_fighter(draw, IMG_W // 2, IMG_H // 2 + 50, scale=2.2,
                 color=(230, 230, 230))

    draw_belt(draw, IMG_W // 2, IMG_H // 2 + 130)

    font_big = get_font(90, bold=True)
    text_top = "AND NEW" if status == "new" else "AND STILL"
    color_top = (255, 60, 60) if status == "new" else (255, 215, 0)
    bbox = draw.textbbox((0, 0), text_top, font=font_big)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2, 60), text_top,
              font=font_big, fill=color_top)

    font_nick = get_font(70, bold=True)
    bbox = draw.textbbox((0, 0), nick, font=font_nick)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2, IMG_H - 160), nick,
              font=font_nick, fill=(255, 255, 255))

    font_sub = get_font(40)
    text_sub = "CHAMPION"
    bbox = draw.textbbox((0, 0), text_sub, font=font_sub)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2, IMG_H - 80), text_sub,
              font=font_sub, fill=(180, 180, 180))

    path = f"result_{nick.lstrip('@')}.png"
    img.save(path)
    return path


@only_me
async def add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global state
    args = ctx.args
    if not args:
        await update.message.reply_text("Формат: /add @nick")
        return

    nick = args[0]
    state["challenger"] = {"nick": nick}
    save_state(state)

    if state["champion"]:
        champ = state["champion"]
        await update.message.reply_text(
            f"🥊 Претендент: {nick}\n\n"
            f"Чемпион: {champ['nick']}\n"
            f"  Защит: {champ['defenses']}\n\n"
            f"Пиши /fight"
        )
    else:
        await update.message.reply_text(
            f"🥊 {nick} добавлен.\n\n"
            f"Чемпиона нет — /fight сделает его первым."
        )


@only_me
async def fight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global state

    if not state["challenger"]:
        await update.message.reply_text("Сначала /add @nick")
        return

    challenger = state["challenger"]

    if not state["champion"]:
        challenger["defenses"] = 0
        state["champion"] = challenger
        state["challenger"] = None
        save_state(state)
        img_path = generate_image(challenger["nick"], "new")
        await update.message.reply_photo(
            photo=open(img_path, "rb"),
            caption=f"🏆 {challenger['nick']} — первый чемпион!"
        )
        return

    champ = state["champion"]

    champ_luck = random.randint(0, 10)
    chall_luck = random.randint(0, 10)
    champ_total = champ_luck
    chall_total = chall_luck

    while champ_total == chall_total:
        champ_luck = random.randint(0, 10)
        chall_luck = random.randint(0, 10)
        champ_total = champ_luck
        chall_total = chall_luck

    text = (
        f"🥊 БОЙ!\n\n"
        f"ЧЕМПИОН {champ['nick']}\n"
        f"  🎲 Кубик: {champ_luck}\n\n"
        f"ПРЕТЕНДЕНТ {challenger['nick']}\n"
        f"  🎲 Кубик: {chall_luck}\n\n"
    )

    if chall_total > champ_total:
        challenger["defenses"] = 0
        state["champion"] = challenger
        state["challenger"] = None
        text += f"🏆 AND NEW! {challenger['nick']} — новый чемпион!"
        status = "new"
        winner_nick = challenger["nick"]
    else:
        champ["defenses"] += 1
        state["champion"] = champ
        state["challenger"] = None
        text += f"🏆 AND STILL! {champ['nick']} защитил пояс!\nЗащит: {champ['defenses']}"
        status = "still"
        winner_nick = champ["nick"]

    state["history"].append({
        "champ": champ["nick"],
        "challenger": challenger["nick"],
        "champ_total": champ_total,
        "chall_total": chall_total,
        "winner": winner_nick
    })
    save_state(state)

    img_path = generate_image(winner_nick, status)
    await update.message.reply_photo(
        photo=open(img_path, "rb"),
        caption=text
    )


@only_me
async def champion(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not state["champion"]:
        await update.message.reply_text("Чемпиона пока нет.")
        return
    c = state["champion"]
    await update.message.reply_text(
        f"🏆 Чемпион: {c['nick']}\n"
        f"Защит: {c['defenses']}"
    )


@only_me
async def history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not state["history"]:
        await update.message.reply_text("История пуста.")
        return
    text = "📜 История:\n\n"
    for i, h in enumerate(state["history"][-10:], 1):
        if h.get("type") == "first_champion":
            text += f"{i}. {h['nick']} — первый чемпион\n"
        else:
            text += (
                f"{i}. {h['champ']} ({h['champ_total']}) vs "
                f"{h['challenger']} ({h['chall_total']}) → "
                f"🏆 {h['winner']}\n"
            )
    await update.message.reply_text(text)


@only_me
async def reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global state
    state = {"champion": None, "challenger": None, "history": []}
    save_state(state)
    await update.message.reply_text("Сброшено.")


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("fight", fight))
    app.add_handler(CommandHandler("champion", champion))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("reset", reset))
    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
