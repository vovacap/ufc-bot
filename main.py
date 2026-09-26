import random
import json
import os
import math
import wave
import struct
import subprocess
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TOKEN = "8625559038:AAG2kfcvIfm1SLBSZ_O2ovs2UPZdWQFTYy8"
MY_ID = 709900282

STATE_FILE = "minefield_state.json"
STEPS = 3
MINE_CHANCE = 0.30
IMG_W, IMG_H = 1080, 1080
VID_W, VID_H = 720, 720


# ---------- State ----------
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"history": []}


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


# ---------- Fonts ----------
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


# ---------- Drawing helpers ----------
def make_gradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        r = y / h
        color = (
            int(top[0] * (1 - r) + bottom[0] * r),
            int(top[1] * (1 - r) + bottom[1] * r),
            int(top[2] * (1 - r) + bottom[2] * r),
        )
        draw.line([(0, y), (w, y)], fill=color)
    return img


def draw_glow(draw, cx, cy, r, color, steps=5, intensity=0.4):
    for i in range(steps, 0, -1):
        gr = r + i * 6
        factor = (1 - i / steps) * intensity
        c = tuple(int(ch * factor) for ch in color)
        draw.ellipse([cx - gr, cy - gr, cx + gr, cy + gr], fill=c)


def draw_mark(draw, cx, cy, kind):
    if kind == "safe":
        draw_glow(draw, cx, cy, 26, (60, 220, 100))
        draw.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(40, 180, 80))
        draw.line([cx - 13, cy, cx - 3, cy + 12], fill=(255, 255, 255), width=6)
        draw.line([cx - 3, cy + 12, cx + 14, cy - 12], fill=(255, 255, 255), width=6)
    elif kind == "mine":
        draw_glow(draw, cx, cy, 30, (255, 60, 40), intensity=0.6)
        s = 24
        draw.line([cx - s, cy - s, cx + s, cy + s], fill=(255, 60, 60), width=10)
        draw.line([cx - s, cy + s, cx + s, cy - s], fill=(255, 60, 60), width=10)
    else:
        draw.line([cx - 22, cy, cx + 22, cy], fill=(60, 60, 70), width=5)


# ---------- Minefield image ----------
def generate_minefield_image(players, history, winner):
    img = make_gradient(IMG_W, IMG_H, (20, 15, 35), (5, 5, 8))
    draw = ImageDraw.Draw(img)

    # Прожекторы (мягкие световые пятна)
    for pos in [(150, 100), (930, 100), (540, 30)]:
        for r in range(200, 0, -20):
            factor = r / 200
            c = int(28 * (1 - factor) + 8)
            draw.ellipse(
                [pos[0] - r, pos[1] - r, pos[0] + r, pos[1] + r],
                fill=(c, c, c + 4)
            )

    # Заголовок
    font_title = get_font(78, bold=True)
    title = "МИННОЕ ПОЛЕ"
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2 + 3, 53), title, font=font_title, fill=(80, 20, 20))
    draw.text(((IMG_W - tw) // 2, 50), title, font=font_title, fill=(255, 70, 60))

    font_sub = get_font(34)
    sub = "3 бойца · 3 шага · 30% мины"
    bbox = draw.textbbox((0, 0), sub, font=font_sub)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2, 148), sub, font=font_sub, fill=(150, 150, 170))

    # Колонки
    col_w = IMG_W // 3
    cols_x = [col_w // 2, col_w + col_w // 2, 2 * col_w + col_w // 2]

    # Разделители
    for i in range(1, 3):
        draw.line([i * col_w, 215, i * col_w, IMG_H - 260],
                  fill=(45, 45, 60), width=2)

    # Ники сверху
    font_nick = get_font(42, bold=True)
    for i, p in enumerate(players):
        color = (255, 215, 0) if p == winner else (235, 235, 235)
        bbox = draw.textbbox((0, 0), p, font=font_nick)
        tw = bbox[2] - bbox[0]
        x = cols_x[i] - tw // 2
        y = 235
        if p == winner:
            draw.text((x + 2, y + 2), p, font=font_nick, fill=(80, 60, 0))
        draw.text((x, y), p, font=font_nick, fill=color)

    # Шаги
    font_step = get_font(36, bold=True)
    y_start = 360
    y_step = 165

    for s in range(1, STEPS + 1):
        y = y_start + (s - 1) * y_step
        label = f"ШАГ {s}"
        bbox = draw.textbbox((0, 0), label, font=font_step)
        tw = bbox[2] - bbox[0]
        draw.text(((IMG_W - tw) // 2, y - 60), label,
                  font=font_step, fill=(140, 140, 160))

    # Метки
    for i, p in enumerate(players):
        for s in range(1, STEPS + 1):
            y = y_start + (s - 1) * y_step
            kind = "out"
            for h in history:
                if h["step"] == s and p in h["result"]:
                    kind = h["result"][p]
                    break
            draw_mark(draw, cols_x[i], y, kind)

    # Панель победителя
    panel_y = IMG_H - 200
    draw.rectangle([40, panel_y, IMG_W - 40, panel_y + 130],
                   fill=(25, 20, 5), outline=(255, 215, 0), width=3)

    font_win_label = get_font(28)
    label = "ПОБЕДИТЕЛЬ"
    bbox = draw.textbbox((0, 0), label, font=font_win_label)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2, panel_y + 15), label,
              font=font_win_label, fill=(200, 180, 100))

    font_win = get_font(64, bold=True)
    bbox = draw.textbbox((0, 0), winner, font=font_win)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2 + 2, panel_y + 57), winner,
              font=font_win, fill=(120, 90, 0))
    draw.text(((IMG_W - tw) // 2, panel_y + 55), winner,
              font=font_win, fill=(255, 215, 0))

    # Виньетка (затемнение краёв)
    vignette = Image.new("L", (IMG_W, IMG_H), 0)
    vd = ImageDraw.Draw(vignette)
    for i in range(80):
        vd.rectangle([i, i, IMG_W - i, IMG_H - i], outline=int(i * 3))
    vignette = vignette.filter(ImageFilter.GaussianBlur(50))
    black = Image.new("RGB", (IMG_W, IMG_H), (0, 0, 0))
    img = Image.composite(black, img, vignette.point(lambda p: 255 - p))

    path = f"minefield_{winner.lstrip('@')}.png"
    img.save(path)
    return path


# ---------- Explosion ----------
def create_explosion_frame(frame_idx, total_frames):
    W, H = VID_W, VID_H
    img = Image.new("RGB", (W, H), (3, 3, 6))
    draw = ImageDraw.Draw(img)
    cx, cy = W // 2, H // 2

    p = frame_idx / (total_frames - 1)

    if p < 0.4:
        size = p / 0.4
    elif p < 0.65:
        size = 1.0
    else:
        size = max(0.0, 1.0 - (p - 0.65) / 0.35)

    if p < 0.5:
        bright = 1.0
    else:
        bright = max(0.0, 1.0 - (p - 0.5) / 0.5)

    max_r = int(W * 0.46 * size)

    if max_r > 0:
        for r in range(max_r, 0, -6):
            ratio = r / max_r
            if ratio > 0.78:
                base = (180, 25, 0)
            elif ratio > 0.55:
                base = (255, 70, 0)
            elif ratio > 0.30:
                base = (255, 170, 30)
            elif ratio > 0.12:
                base = (255, 230, 120)
            else:
                base = (255, 255, 220)
            color = tuple(int(c * bright) for c in base)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    if 0.15 < p < 0.92 and max_r > 0:
        rng = random.Random(frame_idx * 7 + 1)
        for _ in range(50):
            angle = rng.uniform(0, 2 * math.pi)
            speed = rng.uniform(0.4, 1.2)
            dist = speed * max_r * (1 + p * 0.7)
            px = cx + math.cos(angle) * dist
            py = cy + math.sin(angle) * dist
            if 0 <= px < W and 0 <= py < H:
                pr = rng.randint(2, 7)
                pc = rng.choice([
                    (255, 200, 50), (255, 100, 0),
                    (255, 60, 20), (255, 235, 180)
                ])
                pc = tuple(int(c * bright) for c in pc)
                draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=pc)

    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    return img


def generate_explosion_sound(path):
    sample_rate = 44100
    duration = 1.5
    n = int(sample_rate * duration)

    frames = []
    for i in range(n):
        t = i / sample_rate
        boom = math.sin(2 * math.pi * 55 * t) * math.exp(-4 * t)
        rumble = math.sin(2 * math.pi * 30 * t) * math.exp(-2.5 * t) * 0.6
        noise = random.uniform(-1, 1) * math.exp(-12 * t) * 0.7
        sizzle = random.uniform(-0.3, 0.3) * math.exp(-3 * t) * 0.4
        s = boom * 0.9 + rumble + noise + sizzle
        s = max(-1.0, min(1.0, s))
        frames.append(int(s * 32767))

    with wave.open(path, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        data = struct.pack('<' + 'h' * len(frames), *frames)
        w.writeframes(data)


def generate_explosion_video(output_path):
    total = 18
    fps = 12

    tmp = tempfile.mkdtemp()
    try:
        for i in range(total):
            frame = create_explosion_frame(i, total)
            frame.save(os.path.join(tmp, f"f_{i:04d}.png"))

        sound_path = os.path.join(tmp, "boom.wav")
        generate_explosion_sound(sound_path)

        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-framerate", str(fps),
            "-i", os.path.join(tmp, "f_%04d.png"),
            "-i", sound_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            output_path
        ], check=True, timeout=60)
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


# ---------- Game logic ----------
def play_minefield(players):
    progress = {p: 0 for p in players}
    history = []

    for step in range(1, STEPS + 1):
        step_result = {}
        for p in players:
            if progress[p] == step - 1:
                if random.random() < MINE_CHANCE:
                    step_result[p] = "mine"
                else:
                    step_result[p] = "safe"
                    progress[p] = step
            else:
                step_result[p] = "out"
        history.append({"step": step, "result": step_result})

    survivors = [p for p in players if progress[p] == STEPS]
    sd_step = STEPS + 1

    while len(survivors) > 1:
        sd_result = {}
        for p in players:
            if p in survivors:
                if random.random() < MINE_CHANCE:
                    sd_result[p] = "mine"
                    survivors.remove(p)
                else:
                    sd_result[p] = "safe"
                    progress[p] = sd_step
            else:
                sd_result[p] = "out"
        history.append({"step": sd_step, "result": sd_result})
        sd_step += 1

    if survivors:
        winner = survivors[0]
    else:
        max_prog = max(progress.values())
        furthest = [p for p in players if progress[p] == max_prog]
        winner = random.choice(furthest)

    return history, winner


def format_text(players, history, winner):
    lines = ["💣 МИННОЕ ПОЛЕ", ""]
    for h in history:
        step = h["step"]
        label = f"ШАГ {step}" if isinstance(step, int) and step <= STEPS else "СМЕРТЕЛЬНЫЙ"
        lines.append(f"— {label} —")
        for p in players:
            r = h["result"].get(p, "out")
            mark = "✅" if r == "safe" else ("💥" if r == "mine" else "—")
            lines.append(f"{mark} {p}")
        lines.append("")
    lines.append(f"🏆 Победитель: {winner}")
    return "\n".join(lines)


# ---------- Handlers ----------
@only_me
async def minefield(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global state

    args = ctx.args
    if len(args) != 3:
        await update.message.reply_text(
            "Формат: /minefield @nick1 @nick2 @nick3\n"
            "Нужно ровно 3 ника."
        )
        return

    players = args[:3]
    if len(set(players)) != 3:
        await update.message.reply_text("Ники должны быть разными.")
        return

    await update.message.reply_text("💣 Игра началась...")

    history, winner = play_minefield(players)
    text = format_text(players, history, winner)
    img_path = generate_minefield_image(players, history, winner)

    await update.message.reply_photo(
        photo=open(img_path, "rb"),
        caption=text
    )

    await update.message.reply_text("💥 Взрыв...")
    try:
        video_path = f"boom_{winner.lstrip('@')}.mp4"
        generate_explosion_video(video_path)
        await update.message.reply_video(
            video=open(video_path, "rb"),
            caption=f"🏆 {winner} выжил!",
            supports_streaming=True
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Видео не собралось: {e}")

    state["history"].append({"players": players, "winner": winner})
    save_state(state)


@only_me
async def history_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not state["history"]:
        await update.message.reply_text("История пуста.")
        return
    text = "📜 История игр:\n\n"
    for i, h in enumerate(state["history"][-10:], 1):
        players = ", ".join(h["players"])
        text += f"{i}. {players} → 🏆 {h['winner']}\n"
    await update.message.reply_text(text)


@only_me
async def reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global state
    state = {"history": []}
    save_state(state)
    await update.message.reply_text("История сброшена.")


@only_me
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 МИННОЕ ПОЛЕ\n\n"
        "/minefield @nick1 @nick2 @nick3 — игра\n"
        "/history — история\n"
        "/reset — сброс\n\n"
        "3 бойца · 3 шага · 30% мины"
    )


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("minefield", minefield))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_cmd))
    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
