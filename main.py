import random
import json
import os
import math
import wave
import struct
import subprocess
import tempfile
import asyncio
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import imageio_ffmpeg

TOKEN = "8625559038:AAG2kfcvIfm1SLBSZ_O2ovs2UPZdWQFTYy8"
MY_ID = 709900282

STATE_FILE = "cell_state.json"
IMG_W, IMG_H = 1080, 1080

BELT_PATH = "belt.png"
COFFEE_PATH = "coffee.png"
CAGE_OPEN_PATH = "cage_open.png"
CAGE_CLOSED_PATH = "cage_closed.png"

state = {"history": []}
game = {
    "active": False,
    "nicks": [],
    "photos": [],
    "current_idx": 0,
    "last_msg_id": None,
    "chat_id": None
}


def load_state():
    global state
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)


def save_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


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


def circular_photo(path, size, border_color=(255, 215, 0), border_width=6):
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        img = Image.new("RGB", (size, size), (60, 60, 70))
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)

    total = size + border_width * 2
    border = Image.new("RGBA", (total, total), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.ellipse((0, 0, total, total), fill=border_color + (255,))

    result = Image.new("RGBA", (total, total), (0, 0, 0, 0))
    result.paste(border, (0, 0))
    result.paste(img, (border_width, border_width), mask)
    return result


def grayscale_circular(path, size, border_color=(70, 70, 70), border_width=4):
    img = circular_photo(path, size, border_color, border_width)
    gray = img.convert("L").convert("RGBA")
    d = ImageDraw.Draw(gray)
    total = size + border_width * 2
    s = total // 3
    cx, cy = total // 2, total // 2
    d.line([cx - s, cy - s, cx + s, cy + s], fill=(200, 50, 50, 255), width=8)
    d.line([cx - s, cy + s, cx + s, cy - s], fill=(200, 50, 50, 255), width=8)
    return gray


def draw_dice(draw, cx, cy, number, size=170):
    half = size // 2
    draw.rounded_rectangle(
        [cx - half, cy - half, cx + half, cy + half],
        radius=18, fill=(255, 255, 255), outline=(30, 30, 40), width=6
    )
    font = get_font(int(size * 0.72), bold=True)
    text = str(number)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 6), text, font=font, fill=(20, 20, 30))


def make_bg():
    img = Image.new("RGB", (IMG_W, IMG_H), (8, 8, 14))
    draw = ImageDraw.Draw(img)
    for pos in [(180, 100), (900, 100), (540, 40)]:
        for r in range(220, 0, -20):
            factor = r / 220
            c = int(30 * (1 - factor) + 6)
            draw.ellipse(
                [pos[0] - r, pos[1] - r, pos[0] + r, pos[1] + r],
                fill=(c, c, c + 6)
            )
    for _ in range(60):
        x = random.randint(0, IMG_W)
        y = random.randint(IMG_H - 200, IMG_H)
        w = random.randint(30, 70)
        h = random.randint(60, 120)
        c = random.randint(20, 45)
        draw.ellipse([x, y, x + w, y + h], fill=(c, c, c + 5))
    return img


def paste_cage(img, path, cx, cy, size):
    try:
        cage = Image.open(path).convert("RGBA")
        w, h = cage.size
        ratio = size / max(w, h)
        nw, nh = int(w * ratio), int(h * ratio)
        cage = cage.resize((nw, nh))
        img.paste(cage, (cx - nw // 2, cy - nh // 2), cage)
        return True
    except Exception:
        return False


def draw_text_center(draw, text, y, size, color, bold=True, shadow=True):
    font = get_font(size, bold=bold)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (IMG_W - tw) // 2
    if shadow:
        draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=color)


def draw_frame1(photos, nicks):
    img = make_bg()
    draw = ImageDraw.Draw(img)

    draw_text_center(draw, "ЛАКИ ПАНЧ", 40, 86, (255, 60, 60))

    px, py = IMG_W // 2, 155
    draw.ellipse([px - 55, py - 35, px + 55, py + 35], fill=(200, 40, 40))
    draw.ellipse([px - 30, py + 25, px + 30, py + 55], fill=(180, 30, 30))
    draw.ellipse([px + 20, py - 20, px + 60, py + 20], fill=(220, 60, 60))

    draw_text_center(draw, "5 БОЙЦОВ · ОДИН КОФЕ", 230, 40, (220, 220, 220))

    paste_cage(img, CAGE_OPEN_PATH, IMG_W // 2, 590, 460)

    positions = [
        (140, 400), (140, 720),
        (940, 400), (940, 720),
        (540, 950)
    ]
    for i in range(5):
        x, y = positions[i]
        cp = circular_photo(photos[i], 130)
        img.paste(cp, (x - cp.width // 2, y - cp.height // 2), cp)
        font = get_font(28, bold=True)
        nick = nicks[i]
        bbox = draw.textbbox((0, 0), nick, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x - tw // 2 + 2, y + 75 + 2), nick, font=font, fill=(0, 0, 0))
        draw.text((x - tw // 2, y + 75), nick, font=font, fill=(255, 255, 255))

    return img


def draw_frame2(photos, nicks, dice):
    img = make_bg()
    draw = ImageDraw.Draw(img)

    draw_text_center(draw, "ЖЁСТКАЯ ЗАРУБА", 20, 74, (255, 60, 60))
    draw_text_center(draw, "НАЧАЛАСЬ", 105, 74, (255, 60, 60))

    paste_cage(img, CAGE_CLOSED_PATH, IMG_W // 2, 560, 480)

    positions = [
        (540, 340), (200, 530), (880, 530),
        (340, 730), (740, 730)
    ]

    for i in range(5):
        x, y = positions[i]

        cp = circular_photo(photos[i], 110)
        img.paste(cp, (x - cp.width // 2, y - cp.height // 2), cp)

        font = get_font(26, bold=True)
        nick = nicks[i]
        bbox = draw.textbbox((0, 0), nick, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x - tw // 2 + 2, y + 65 + 2), nick, font=font, fill=(0, 0, 0))
        draw.text((x - tw // 2, y + 65), nick, font=font, fill=(255, 255, 255))

        draw_dice(draw, x, y + 190, dice[i], size=170)

    return img


def draw_frame3(photos, nicks, winner_idx):
    img = make_bg()
    draw = ImageDraw.Draw(img)
    for r in range(500, 0, -20):
        factor = r / 500
        c = int(60 * (1 - factor))
        draw.ellipse(
            [IMG_W // 2 - r, 500 - r, IMG_W // 2 + r, 500 + r],
            fill=(c, int(c * 0.7), 0)
        )

    draw_text_center(draw, "ПОБЕДИТЕЛЬ", 40, 76, (255, 215, 0))

    wx, wy = IMG_W // 2, 420
    cp = circular_photo(photos[winner_idx], 280, border_color=(255, 215, 0), border_width=10)
    img.paste(cp, (wx - cp.width // 2, wy - cp.height // 2), cp)

    font_nick = get_font(64, bold=True)
    nick = nicks[winner_idx]
    bbox = draw.textbbox((0, 0), nick, font=font_nick)
    tw = bbox[2] - bbox[0]
    draw.text((wx - tw // 2 + 3, wy + 170 + 3), nick, font=font_nick, fill=(0, 0, 0))
    draw.text((wx - tw // 2, wy + 170), nick, font=font_nick, fill=(255, 215, 0))

    belt_y = wy + 280
    try:
        belt = Image.open(BELT_PATH).convert("RGBA")
        bw = 500
        ratio = bw / belt.width
        bh = int(belt.height * ratio)
        belt = belt.resize((bw, bh))
        img.paste(belt, (wx - bw // 2, belt_y), belt)
    except Exception:
        draw.rectangle([wx - 250, belt_y, wx + 250, belt_y + 80],
                       fill=(180, 140, 20), outline=(255, 215, 0), width=4)

    try:
        coffee = Image.open(COFFEE_PATH).convert("RGBA")
        cw = 200
        ratio = cw / coffee.width
        ch = int(coffee.height * ratio)
        coffee = coffee.resize((cw, ch))
        img.paste(coffee, (wx + 260, wy - 100), coffee)
    except Exception:
        draw.rectangle([wx + 280, wy - 50, wx + 380, wy + 150],
                       fill=(160, 120, 80), outline=(90, 60, 30), width=3)

    losers = [i for i in range(5) if i != winner_idx]
    loser_pos = [(110, 850), (970, 850), (110, 1000), (970, 1000)]
    for j, idx in enumerate(losers):
        x, y = loser_pos[j]
        gp = grayscale_circular(photos[idx], 90)
        img.paste(gp, (x - gp.width // 2, y - gp.height // 2), gp)

    draw_text_center(draw, f"КОФЕЙНЫЙ ЧЕМПИОН: {nick}", IMG_H - 60, 38, (255, 255, 255))

    return img


def generate_sound(duration, path):
    sr = 44100
    n = int(sr * duration)
    samples = [0.0] * n

    for i in range(n):
        t = i / sr
        s = 0.0

        if 0 <= t < 3:
            fade = min(t / 0.5, 1.0) * min((3 - t) / 0.5, 1.0)
            s += (math.sin(2 * math.pi * 70 * t) * 0.25 +
                  math.sin(2 * math.pi * 110 * t) * 0.15 +
                  random.uniform(-1, 1) * 0.12) * fade

        if 3 <= t < 3.5:
            dt = t - 3
            s += random.uniform(-1, 1) * math.exp(-8 * dt) * 0.9

        if 3.5 <= t < 8.5:
            for hit_t in [4.2, 5.6, 6.8, 7.8]:
                if hit_t <= t < hit_t + 0.3:
                    dt = t - hit_t
                    s += (random.uniform(-1, 1) * 0.9 +
                          math.sin(2 * math.pi * 80 * dt) * 0.7) * math.exp(-14 * dt)

        if 8.5 <= t < 9.5:
            dt = t - 8.5
            s += (math.sin(2 * math.pi * 220 * dt) * 0.5 +
                  math.sin(2 * math.pi * 440 * dt) * 0.25) * math.exp(-3 * dt)

        if 9 <= t < 14:
            dt = t - 9
            env = min(dt / 0.2, 1.0) * math.exp(-0.5 * dt)
            s += (math.sin(2 * math.pi * 262 * dt) * 0.25 +
                  math.sin(2 * math.pi * 330 * dt) * 0.2 +
                  math.sin(2 * math.pi * 392 * dt) * 0.2) * env

        samples[i] = max(-1.0, min(1.0, s))

    with wave.open(path, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        data = struct.pack('<' + 'h' * n, *[int(x * 32767) for x in samples])
        w.writeframes(data)


def generate_video(photos, nicks, dice, winner_idx, output_path):
    tmp = tempfile.mkdtemp()
    try:
        f1 = draw_frame1(photos, nicks)
        f2 = draw_frame2(photos, nicks, dice)
        f3 = draw_frame3(photos, nicks, winner_idx)

        p1 = os.path.join(tmp, "f1.png")
        p2 = os.path.join(tmp, "f2.png")
        p3 = os.path.join(tmp, "f3.png")
        f1.save(p1)
        f2.save(p2)
        f3.save(p3)

        del f1, f2, f3

        sound_path = os.path.join(tmp, "sound.wav")
        generate_sound(14.0, sound_path)

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([
            ffmpeg_exe, "-y", "-loglevel", "error",
            "-loop", "1", "-t", "3", "-i", p1,
            "-loop", "1", "-t", "4", "-i", p2,
            "-loop", "1", "-t", "5", "-i", p3,
            "-i", sound_path,
            "-filter_complex",
            "[0:v]scale=720:720,fps=10[a];"
            "[1:v]scale=720:720,fps=10[b];"
            "[2:v]scale=720:720,fps=10[c];"
            "[a][b][c]concat=n=3:v=1:a=0[v]",
            "-map", "[v]",
            "-map", "3:a",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            output_path
        ], check=True, timeout=180)
    finally:
        for f in os.listdir(tmp):
            try:
                os.remove(os.path.join(tmp, f))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def roll_dice(nicks):
    dice = [random.randint(0, 10) for _ in nicks]
    while True:
        max_val = max(dice)
        leaders = [i for i, d in enumerate(dice) if d == max_val]
        if len(leaders) == 1:
            break
        for i in leaders:
            dice[i] = random.randint(0, 10)
    return dice


@only_me
async def cmd_cell(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global game
    args = ctx.args
    if len(args) != 5:
        await update.message.reply_text(
            "Формат: /cell @nick1 @nick2 @nick3 @nick4 @nick5\n"
            "Нужно ровно 5 ников."
        )
        return

    if game["active"]:
        await update.message.reply_text("Игра уже идёт. Заверши её или /reset.")
        return

    nicks = args[:5]
    if len(set(nicks)) != 5:
        await update.message.reply_text("Ники должны быть разными.")
        return

    game = {
        "active": True,
        "nicks": nicks,
        "photos": [],
        "current_idx": 0,
        "last_msg_id": None,
        "chat_id": update.effective_chat.id
    }

    await update.message.reply_text(
        f"🥊 Клетка открывается!\n\n"
        f"Пришли фото для {nicks[0]}\n"
        f"(осталось: 5)"
    )


@only_me
async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global game
    if not game["active"]:
        return

    idx = game["current_idx"]
    nick = game["nicks"][idx]

    photo = update.message.photo[-1]
    file = await photo.get_file()
    path = f"cell_photo_{idx}.png"
    await file.download_to_drive(path)
    game["photos"].append(path)
    game["current_idx"] += 1

    try:
        await update.message.delete()
    except Exception:
        pass

    if game.get("last_msg_id") and game.get("chat_id"):
        try:
            await ctx.bot.delete_message(
                chat_id=game["chat_id"],
                message_id=game["last_msg_id"]
            )
        except Exception:
            pass

    if game["current_idx"] < 5:
        next_nick = game["nicks"][game["current_idx"]]
        left = 5 - game["current_idx"]
        msg = await update.message.reply_text(
            f"✅ Фото для {nick} сохранено.\n\n"
            f"Пришли фото для {next_nick}\n"
            f"(осталось: {left})"
        )
    else:
        msg = await update.message.reply_text(
            "✅ Все 5 фото собраны.\n\n"
            "🥊 Напиши /go — и клетка закроется."
        )

    game["last_msg_id"] = msg.message_id
    game["chat_id"] = update.effective_chat.id


@only_me
async def cmd_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global game
    if not game["active"]:
        await update.message.reply_text("Сначала /cell @nick1 @nick2 @nick3 @nick4 @nick5")
        return

    if len(game["photos"]) < 5:
        left = 5 - len(game["photos"])
        await update.message.reply_text(f"Ещё не все фото. Осталось: {left}")
        return

    try:
        await update.message.delete()
    except Exception:
        pass

    if game.get("last_msg_id") and game.get("chat_id"):
        try:
            await ctx.bot.delete_message(
                chat_id=game["chat_id"],
                message_id=game["last_msg_id"]
            )
        except Exception:
            pass

    chat_id = update.effective_chat.id

    msg = await ctx.bot.send_message(
        chat_id=chat_id,
        text="⚡ Сейчас начнётся дикая заруба..."
    )
    await asyncio.sleep(1.8)

    await msg.edit_text("🥊 Решит только ЛАКИ ПАНЧ.")
    await asyncio.sleep(1.5)

    try:
        await msg.delete()
    except Exception:
        pass

    nicks = game["nicks"]
    photos = game["photos"]
    dice = roll_dice(nicks)
    winner_idx = dice.index(max(dice))
    winner = nicks[winner_idx]

    try:
        video_path = f"cell_{winner.lstrip('@')}.mp4"
        status_msg = await ctx.bot.send_message(
            chat_id=chat_id,
            text="🎬 Собираю видео..."
        )
        generate_video(photos, nicks, dice, winner_idx, video_path)
        try:
            await status_msg.delete()
        except Exception:
            pass
        await ctx.bot.send_video(
            chat_id=chat_id,
            video=open(video_path, "rb"),
            caption=f"🏆 КОФЕЙНЫЙ ЧЕМПИОН: {winner}",
            supports_streaming=True
        )
    except Exception as e:
        await ctx.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Видео не собралось: {e}"
        )

    state["history"].append({
        "nicks": nicks,
        "dice": dice,
        "winner": winner
    })
    save_state()

    game = {
        "active": False, "nicks": [], "photos": [],
        "current_idx": 0, "last_msg_id": None, "chat_id": None
    }


@only_me
async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not state["history"]:
        await update.message.reply_text("История пуста.")
        return
    text = "📜 История игр:\n\n"
    for i, h in enumerate(state["history"][-10:], 1):
        text += f"{i}. {h['winner']} (кубик {h['dice'][h['nicks'].index(h['winner'])]})\n"
    await update.message.reply_text(text)


@only_me
async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global state, game
    state = {"history": []}
    game = {
        "active": False, "nicks": [], "photos": [],
        "current_idx": 0, "last_msg_id": None, "chat_id": None
    }
    save_state()
    await update.message.reply_text("Сброшено.")


@only_me
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🥊 КЛЕТКА — битва за кофе\n\n"
        "/cell @nick1 @nick2 @nick3 @nick4 @nick5 — начать игру\n"
        "/go — запустить бой (после 5 фото)\n"
        "/history — история игр\n"
        "/reset — сброс\n"
    )


def main():
    load_state()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("cell", cmd_cell))
    app.add_handler(CommandHandler("go", cmd_go))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
