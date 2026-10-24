"""Build the Kynd hook and body variations from the winning ad.

Usage: python3 build.py <source.mp4> <out_dir> [hook_a hook_b hook_c body_1 body_2]

Every shot is re-cut from the source ad; captions and motion graphics are
rendered with Pillow and overlaid with ffmpeg. New VO lines are Urdu TTS
(Google Translate voice), cached in .tts_cache/, and each scene is timed to
its line. See ../../copy/kynd-underarm-serum-variations-2026-10-24/
for the scripts these edits follow.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 720, 1280, 30
LILAC = "0xEBD7FE"
PINK = (236, 46, 140)
FONT = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FONT_REG = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

SRC = sys.argv[1]
OUT = sys.argv[2]
TMP = tempfile.mkdtemp(prefix="kynd_")
_n = [0]


def tmp(ext):
    _n[0] += 1
    return os.path.join(TMP, f"{_n[0]:03d}.{ext}")


def run(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


# --- caption rendering -------------------------------------------------------

def _is_emoji(ch):
    return ord(ch) >= 0x2190 and ch not in "→…·"


def _runs(text):
    runs, cur, cur_e = [], "", None
    for ch in text:
        e = _is_emoji(ch)
        if cur and e != cur_e:
            runs.append((cur, cur_e))
            cur = ""
        cur, cur_e = cur + ch, e
    if cur:
        runs.append((cur, cur_e))
    return runs


def _draw_line(img, text, cx, y, size, fill, stroke, stroke_w, font_path):
    font = ImageFont.truetype(font_path, size)
    efont = ImageFont.truetype(EMOJI, 109)
    escale = size / 109 * 1.05
    parts = []
    for seg, is_e in _runs(text):
        if is_e:
            for ch in seg:
                if ch == "️":
                    continue
                g = Image.new("RGBA", (140, 140))
                ImageDraw.Draw(g).text((0, 0), ch, font=efont, embedded_color=True)
                g = g.crop(g.getbbox() or (0, 0, 1, 1))
                g = g.resize((max(1, int(g.width * escale)), max(1, int(g.height * escale))))
                parts.append(("img", g, g.width + 4))
        else:
            parts.append(("txt", seg, int(font.getlength(seg))))
    total = sum(p[2] for p in parts)
    x = cx - total // 2
    d = ImageDraw.Draw(img)
    for kind, val, w in parts:
        if kind == "txt":
            d.text((x, y), val, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=stroke)
        else:
            img.alpha_composite(val, (x + 2, y + (size - val.height) // 2 + 4))
        x += w
    return total


def _wrap(text, size, max_w, font_path):
    font = ImageFont.truetype(font_path, size)
    lines, cur = [], ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if font.getlength(trial) > max_w and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    return lines


def caption(text, style="white", y=None, min_w=0):
    """Render a full-frame transparent PNG with one caption block."""
    img = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(img)
    if style == "white":       # white bold, black outline (original's caption style)
        size, fill, stroke, sw, font, y = 46, "white", "black", 5, FONT, y or 860
    elif style == "pink":      # pink kinetic card text
        size, fill, stroke, sw, font, y = 54, PINK, "white", 5, FONT, y or 560
    elif style == "label":     # black on white box (FROM THIS… / TO THIS…)
        size, fill, stroke, sw, font, y = 40, "black", None, 0, FONT, y or 900
    elif style == "vo":        # rough-cut VO subtitle bar
        size, fill, stroke, sw, font, y = 26, "white", None, 0, FONT_REG, y or 1120
    elif style == "tag":       # rough-cut "new shot needed" tag
        size, fill, stroke, sw, font, y = 24, "black", None, 0, FONT, y or 40
    lines = _wrap(text, size, W - 90, font)
    lh = int(size * 1.25)
    if style in ("label", "vo", "tag"):
        pad = 12
        widths = [ImageFont.truetype(font, size).getlength(l) for l in lines]
        bw = max(int(max(widths)) + pad * 2, min_w)
        bh = lh * len(lines) + pad * 2
        bg = {"label": (255, 255, 255, 255), "vo": (0, 0, 0, 170), "tag": (255, 214, 0, 255)}[style]
        d.rounded_rectangle([W // 2 - bw // 2, y - pad, W // 2 + bw // 2, y - pad + bh], 10, fill=bg)
    for i, line in enumerate(lines):
        _draw_line(img, line, W // 2, y + i * lh, size, fill, stroke, sw, font)
    path = tmp("png")
    img.save(path)
    return path


def comment_sticker(text, user="@username"):
    """TikTok/Reels style 'reply to comment' sticker. Swap in a real comment before launch."""
    img = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(img)
    f_small = ImageFont.truetype(FONT_REG, 22)
    lines = _wrap(text, 32, 520, FONT)
    bw, bh = 580, 70 + 42 * len(lines)
    x0, y0 = (W - bw) // 2, 250
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], 22, fill="white")
    d.polygon([(x0 + 60, y0 + bh), (x0 + 90, y0 + bh), (x0 + 60, y0 + bh + 26)], fill="white")
    d.ellipse([x0 + 22, y0 + 18, x0 + 52, y0 + 48], fill=(200, 160, 230))
    d.text((x0 + 62, y0 + 20), f"Reply to {user}'s comment", font=f_small, fill=(110, 110, 110))
    for i, line in enumerate(lines):
        _draw_line(img, line, W // 2, y0 + 60 + i * 42, 32, "black", None, 0, FONT)
    path = tmp("png")
    img.save(path)
    return path


def red_x():
    img = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(img)
    c, r, w = (W // 2, 560), 170, 34
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=(230, 30, 40), width=w)
    k = int(r * 0.55)
    d.line([c[0] - k, c[1] - k, c[0] + k, c[1] + k], fill=(230, 30, 40), width=w)
    d.line([c[0] - k, c[1] + k, c[0] + k, c[1] - k], fill=(230, 30, 40), width=w)
    path = tmp("png")
    img.save(path)
    return path


# --- video segments ----------------------------------------------------------

def _finish(base_filter, inputs, overlays, out, dur):
    """overlays: list of (png, t0, t1) relative to segment start."""
    args = list(inputs)
    chain = f"[0:v]{base_filter},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[v0]"
    last = "v0"
    for i, (png, t0, t1) in enumerate(overlays):
        args += ["-loop", "1", "-t", f"{dur:.3f}", "-i", png]
        idx = len([a for a in args if a == "-i"]) - 1
        nxt = f"v{i + 1}"
        chain += f";[{last}][{idx}:v]overlay=0:0:enable='between(t,{t0},{t1})'[{nxt}]"
        last = nxt
    args += ["-filter_complex", chain, "-map", f"[{last}]", "-t", f"{dur:.3f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-an", out]
    run(args)


def clip(start, end, overlays=(), speed=1.0, freeze=0.0):
    """Cut [start, end) of the source; optional slow-down and end freeze."""
    dur = (end - start) / speed + freeze
    vf = f"setpts=(PTS-STARTPTS)/{speed:.4f}"
    if freeze >= 0.01:
        vf += f",tpad=stop_mode=clone:stop_duration={freeze:.3f}"
    out = tmp("mp4")
    _finish(vf, ["-ss", f"{start}", "-t", f"{end - start + 0.1}", "-i", SRC],
            [(p, 0, dur) if isinstance(p, str) else p for p in overlays], out, dur)
    return out, dur


def card(dur, overlays=()):
    """Plain lilac text card, like the original's kinetic text cards."""
    out = tmp("mp4")
    _finish("null", ["-f", "lavfi", "-t", f"{dur}", "-i", f"color=c={LILAC}:s={W}x{H}:r={FPS}"],
            [(p, 0, dur) if isinstance(p, str) else p for p in overlays], out, dur)
    return out, dur


def grid(starts, length, overlays=()):
    """2x2 grid of short clips (progression split screen)."""
    out = tmp("mp4")
    args = []
    for s in starts:
        args += ["-ss", f"{s}", "-t", "0.2", "-i", SRC]
    # Each tile is a held frame, so no tile runs into the next shot.
    fc = ";".join(f"[{i}:v]setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={length},scale={W // 2}:{H // 2}:force_original_aspect_ratio=increase,"
                  f"crop={W // 2}:{H // 2},setsar=1[g{i}]" for i in range(4))
    fc += ";[g0][g1][g2][g3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[gx]"
    tmpgrid = tmp("mp4")
    run(args + ["-filter_complex", fc, "-map", "[gx]", "-t", f"{length}", "-c:v", "libx264",
                "-crf", "18", "-pix_fmt", "yuv420p", "-an", tmpgrid])
    _finish("null", ["-i", tmpgrid], [(p, 0, length) if isinstance(p, str) else p for p in overlays],
            out, length)
    return out, length


def audio_from(ranges):
    """Concatenate source audio ranges into one track."""
    out = tmp("wav")
    args = []
    for s, e in ranges:
        args += ["-ss", f"{s}", "-t", f"{e - s}", "-i", SRC]
    n = len(ranges)
    fc = "".join(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo[a{i}];" for i in range(n))
    fc += "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    run(args + ["-filter_complex", fc, "-map", "[a]", out])
    return out


# --- voiceover ---------------------------------------------------------------

TTS_LANG = "ur"
TTS_TEMPO = 1.12  # Google's voice reads slowly; speed it up slightly
TTS_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tts_cache")


def voice(text):
    """Urdu TTS for one line → (wav path, duration). Cached by text."""
    import hashlib
    import urllib.parse
    import urllib.request
    os.makedirs(TTS_CACHE, exist_ok=True)
    key = hashlib.sha1(f"{TTS_LANG}|{TTS_TEMPO}|{text}".encode()).hexdigest()[:16]
    wav = os.path.join(TTS_CACHE, key + ".wav")
    if not os.path.exists(wav):
        mp3 = tmp("mp3")
        q = urllib.parse.urlencode(dict(ie="UTF-8", client="gtx", tl=TTS_LANG, q=text))
        with urllib.request.urlopen("https://translate.googleapis.com/translate_tts?" + q, timeout=30) as r:
            open(mp3, "wb").write(r.read())
        # trim leading/trailing silence, speed up, louden
        run(["-i", mp3, "-af",
             "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
             "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
             f"atempo={TTS_TEMPO},loudnorm=I=-14:TP=-1.5,aresample=44100",
             "-ac", "2", wav])
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav]))
    return wav, dur


# --- scenes: one VO line, visuals stretched or trimmed to fit it -------------

GAP = 0.25  # breath after each line


def scene(parts, say=None, overlays=(), min_dur=0.0, max_slow=0.5):
    """parts: list of (start, end) source ranges played back to back.

    The scene lasts as long as its VO line (or the source length with no VO).
    Too much footage → each part is trimmed proportionally; too little → it is
    slowed down (no slower than max_slow) and the last frame is held.
    Returns a list of segments (path, dur, vo_wav_or_None, vo_offset).
    """
    base = sum(e - s for s, e in parts)
    wav, vdur = voice(say) if say else (None, 0.0)
    need = max(vdur + GAP, min_dur) if say else max(base, min_dur)
    segs = []
    if need <= base:
        k = need / base
        for s, e in parts:
            p, d = clip(s, s + (e - s) * k, overlays)
            segs.append([p, d])
    else:
        speed = max(base / need, max_slow)
        hold = round(max(need - base / speed, 0.0), 3)
        for i, (s, e) in enumerate(parts):
            p, d = clip(s, e, overlays, speed=speed, freeze=hold if i == len(parts) - 1 else 0.0)
            segs.append([p, d])
    out = [(p, d, None, 0) for p, d in segs]
    out[0] = (out[0][0], out[0][1], wav, 0)
    return out


def gfx(say, overlays, min_dur=1.2):
    """Lilac motion-graphics card timed to its VO line."""
    wav, vdur = voice(say) if say else (None, 0.0)
    dur = max(vdur + GAP, min_dur)
    ov = []
    for o in overlays:
        if isinstance(o, str):
            ov.append((o, 0, dur))
        else:  # (png, fraction_in) → appears at that fraction of the line
            ov.append((o[0], round(o[1] * dur, 2), dur))
    p, d = card(dur, ov)
    return [(p, d, wav, 0)]


def emoji_png(chars, size=230, y=520, gap=40):
    """Large emoji row on a transparent full frame."""
    efont = ImageFont.truetype(EMOJI, 109)
    glyphs = []
    for ch in chars:
        g = Image.new("RGBA", (140, 140))
        ImageDraw.Draw(g).text((0, 0), ch, font=efont, embedded_color=True)
        g = g.crop(g.getbbox()).resize((size, size), Image.LANCZOS)
        glyphs.append(g)
    img = Image.new("RGBA", (W, H))
    total = len(glyphs) * size + (len(glyphs) - 1) * gap
    x = (W - total) // 2
    for g in glyphs:
        img.alpha_composite(g, (x, y))
        x += size + gap
    path = tmp("png")
    img.save(path)
    return path


def stamp_x(cx, cy, r=70):
    img = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(img)
    d.line([cx - r, cy - r, cx + r, cy + r], fill=(230, 30, 40), width=22)
    d.line([cx - r, cy + r, cx + r, cy - r], fill=(230, 30, 40), width=22)
    path = tmp("png")
    img.save(path)
    return path


def _dur(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]))


def vo_track(segs):
    """VO lines laid over their segments, padded with silence to each segment's length."""
    args, chain = [], ""
    for i, (_, dur, wav, _) in enumerate(segs):
        if wav:
            args += ["-i", wav]
        else:
            args += ["-f", "lavfi", "-t", f"{dur}", "-i", "anullsrc=r=44100:cl=stereo"]
        chain += f"[{i}:a]apad,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS[s{i}];"
    chain += "".join(f"[s{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=0:a=1[a]"
    out = tmp("wav")
    run(args + ["-filter_complex", chain, "-map", "[a]", out])
    return out


def render(parts, out):
    """parts: ("vo", segs) uses the new VO; ("orig", segs, ranges) keeps the source audio."""
    segs, audios = [], []
    for part in parts:
        segs += part[1]
        audios.append(vo_track(part[1]) if part[0] == "vo" else audio_from(part[2]))
    lst = tmp("txt")
    with open(lst, "w") as f:
        for path, *_ in segs:
            f.write(f"file '{path}'\n")
    video = tmp("mp4")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])
    audio = tmp("wav")
    args = sum((["-i", a] for a in audios), [])
    run(args + ["-filter_complex", "".join(f"[{i}:a]" for i in range(len(audios)))
                + f"concat=n={len(audios)}:v=0:a=1[a]", "-map", "[a]", audio])
    vdur = _dur(video)
    run(["-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
         "-b:a", "160k", "-t", f"{vdur:.3f}", "-movflags", "+faststart", out])
    print(f"{out}: {vdur:.1f}s")


def raw(path_dur):
    p, d = path_dur
    return [(p, d, None, 0)]


END = 54.98

# --- hooks: new hook with its own VO, then the original body and audio -------

def hook_a():
    segs = scene([(6.25, 7.5)], "میں نے سلیولیس پہننا ہی چھوڑ دیا تھا",
                 [caption("Sleeveless pehenna chor diya tha…", "white", 820)])
    segs += scene([(3.5, 5.1)], "بس چودہ دن پہلے تک",
                  [caption("…bas 14 din pehle tak 😌", "white", 860)])
    segs += scene([(2.2, 3.4)], "اور یہ ہے میرا راز",
                  [caption("Ye raaz hai 👇", "white", 860)])
    # resume at "Lekin 2nd week se" → Day 14/21/27
    render([("vo", segs), ("orig", raw(clip(8.0, END)), [(8.0, END)])], f"{OUT}/hook-A-sleeveless.mp4")


def hook_b():
    x = red_x()
    segs = scene([(12.0, 12.6)], "رکو!", [(x, 0.0, 9), (caption("RUKO ✋", "pink", 820), 0.0, 9)],
                 min_dur=1.0)
    segs += scene([(12.9, 14.9)], "انڈر آرمز کے ڈارک ہونے کی اصل وجہ یہ ہے",
                  [caption("Dark underarms ki asal wajah ye hai", "white", 820)])
    segs += scene([(3.5, 5.1)], "اور یہ ڈیو یا لیموں سے ٹھیک نہیں ہوتی",
                  [caption("…aur ye deo ya lemon se theek nahi hoti", "white", 820)])
    # Body without the original shaving segment (10.5–15.6), since the hook covers it.
    body = raw(clip(5.2, 10.5)) + raw(clip(15.6, END))
    render([("vo", segs), ("orig", body, [(5.2, 10.5), (15.6, END)])], f"{OUT}/hook-B-asal-wajah.mp4")


def hook_c():
    sticker = comment_sticker("Ye sach mein kaam karta hai ya sirf ad hai? 🙄")
    segs = scene([(3.5, 5.1)], "یہ سچ میں کام کرتا ہے یا صرف ایڈ ہے؟", [sticker])
    segs += scene([(0.0, 1.0)], "خود دیکھ لو",
                  [caption("Khud dekh lo 👀", "label", 960, min_w=520)])  # box covers burned-in caption
    wav, vdur = voice("پہلے دن سے ستائیسویں دن تک")
    p, d = grid([6.6, 8.6, 9.9, 10.38], round(vdur + GAP + 0.6, 2), [caption("Day 1 → Day 27", "label", 618)])
    segs += [(p, d, wav, 0)]
    render([("vo", segs), ("orig", raw(clip(5.2, END)), [(5.2, END)])], f"{OUT}/hook-C-comment-reply.mp4")


# --- bodies: new edit with full Urdu VO (original hook kept at the front) ----

def body_1():
    segs = []
    segs += scene([(3.5, 5.1), (2.2, 3.4)], "یہ تین غلطیاں ہم سب کرتے ہیں جو انڈر آرمز کو ڈارک کرتی ہیں",
                  [caption("3 galtiyan jo underarms dark karti hain", "white", 820)])
    segs += scene([(12.0, 12.6), (12.9, 15.5)],
                  "پہلی، بغیر کچھ لگائے شیونگ۔ ہر بار سکن چھلتی ہے اور ڈارک ہوتی جاتی ہے",
                  [caption("1. Dry shaving 🪒", "white", 820)])
    segs += gfx("دوسری، ٹائٹ کپڑے اور گرمی میں رگڑ",
                [emoji_png("👕🔥"), caption("2. Friction", "pink", 860)])
    segs += gfx("تیسری، پسینہ اور شیو کے فوراً بعد ہارش ڈیو",
                [emoji_png("💦🧴"), caption("3. Pasina + harsh deo", "pink", 860)])
    segs += scene([(17.0, 22.5)],
                  "اسی لیے میں نے کائنڈ برائٹ بوسٹر لگانا شروع کیا۔ اس میں کوجک، گلائکولک اور لیکٹک ایسڈ ہے",
                  [caption("Kynd Bright Booster", "pink", 120)])
    segs += scene([(2.2, 3.4), (15.6, 16.9)], "بس رات کو شاور کے بعد لگاتی ہوں",
                  [caption("Raat ko, shower ke baad", "white", 820)])
    segs += scene([(6.25, 7.4), (8.3, 10.5)], "اور یہ ہے میرا رزلٹ، پہلے دن سے ستائیسویں دن تک")
    segs += scene([(25.5, 28.0), (29.0, 29.9)], "خوشبو اتنی اچھی کہ پورا دن فریش، بد بو بالکل نہیں آتی",
                  [caption("Bad smell bhi nai ati 🌸", "white", 820)])
    segs += scene([(43.0, 51.8)], "ہزار سے زیادہ کسٹمرز اسے استعمال کر رہے ہیں۔ اور پسند نہ آئے تو سو دن میں پیسے واپس")
    segs += scene([(52.0, END)], "ابھی آرڈر کریں، لنک نیچے ہے")
    render([("orig", raw(clip(0.0, 5.2)), [(0.0, 5.2)]), ("vo", segs)], f"{OUT}/body-1-3-galtiyan.mp4")


def body_2():
    lemon, aloo, soda = emoji_png("🍋", 200, 300), emoji_png("🥔", 200, 560), emoji_png("🧂", 200, 820)
    segs = gfx("لیموں، آلو، بیکنگ سوڈا، سب ٹرائی کر لیا تھا",
               [lemon, (stamp_x(W // 2, 400), 0.2), (aloo, 0.25), (stamp_x(W // 2, 660), 0.45),
                (soda, 0.5), (stamp_x(W // 2, 920), 0.7)], min_dur=2.4)
    segs += scene([(6.25, 7.5), (37.0, 37.9)], "کچھ فرق نہیں پڑا، الٹا جلن ہو جاتی تھی",
                  [caption("Kuch farq nahi para 😩", "white", 820)])
    segs += scene([(12.0, 12.6), (12.9, 15.5)],
                  "کیونکہ مسئلہ صرف رنگ کا نہیں۔ شیونگ سے سکن اندر سے ڈیمج ہوتی ہے",
                  [caption("Masla upar nahi, andar hai", "white", 820)])
    segs += scene([(51.0, 51.9)], "ریگولر پروڈکٹس صرف بو چھپاتی ہیں")
    segs += scene([(17.0, 21.5)], "کائنڈ میں کوجک، گلائکولک اور لیکٹک ایسڈ ہے، جو ڈارک سپاٹس کو برائٹ کرتے ہیں")
    segs += gfx("کتنے دن؟", [caption("Kitne din?", "pink")], min_dur=1.0)
    segs += scene([(8.3, 10.5)], "دو ہفتوں سے فرق نظر آنا شروع ہو جاتا ہے")
    segs += gfx("صرف انڈر آرمز؟", [caption("Sirf underarms?", "pink")], min_dur=1.0)
    segs += scene([(31.0, 35.0)], "نہیں، گردن اور بکنی لائن پر بھی")
    segs += gfx("اور بو؟", [caption("Smell?", "pink")], min_dur=1.0)
    segs += scene([(25.5, 28.0)], "پورا دن فریش", [caption("Bad smell nai ati 🌸", "white", 820)])
    segs += scene([(40.0, 42.5)], "فرق خود دیکھ لیں")
    segs += scene([(48.0, 51.0)], "اور اگر کام نہ کرے؟ سو دن میں پورے پیسے واپس، کوئی رسک نہیں",
                  [caption("Kaam na kare? Poore paise wapis.", "white", 560)])
    segs += scene([(52.0, END)], "ابھی آرڈر کریں")
    render([("orig", raw(clip(0.0, 5.2)), [(0.0, 5.2)]), ("vo", segs)], f"{OUT}/body-2-sab-try-kar-liya.mp4")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[3:] or ["hook_a", "hook_b", "hook_c", "body_1", "body_2"]
    for name in only:
        globals()[name]()
