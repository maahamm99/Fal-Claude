"""Build the Kynd hook variations and body rough cuts from the winning ad.

Usage: python3 build.py <source.mp4> <out_dir>

Every shot is re-cut from the source ad; captions are rendered with Pillow and
overlaid with ffmpeg. See ../../copy/kynd-underarm-serum-variations-2026-10-24/
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
    vf = f"setpts=(PTS-STARTPTS)/{speed}"
    if freeze:
        vf += f",tpad=stop_mode=clone:stop_duration={freeze}"
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
    """Concatenate source audio ranges into one AAC track."""
    out = tmp("m4a")
    args = []
    for s, e in ranges:
        args += ["-ss", f"{s}", "-t", f"{e - s}", "-i", SRC]
    n = len(ranges)
    fc = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    run(args + ["-filter_complex", fc, "-map", "[a]", "-c:a", "aac", "-b:a", "128k", out])
    return out


def assemble(segments, out, audio=None):
    lst = tmp("txt")
    with open(lst, "w") as f:
        for path, _ in segments:
            f.write(f"file '{path}'\n")
    total = sum(d for _, d in segments)
    video = tmp("mp4")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])
    if audio is None:
        args = ["-i", video, "-f", "lavfi", "-t", f"{total}", "-i", "anullsrc=r=44100:cl=stereo"]
    else:
        args = ["-i", video, "-i", audio]
    run(args + ["-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                "-t", f"{total:.3f}", "-movflags", "+faststart", out])
    print(f"{out}: {total:.1f}s")


END = 54.98

# --- hooks (finished ads: new hook + original body and audio) ----------------

def hook_a():
    segs = [
        clip(6.25, 7.5, [caption("Sleeveless pehenna chor diya tha…", "white", 820)]),
        clip(3.5, 5.1, [caption("…bas 14 din pehle tak 😌", "white", 860)]),
        clip(2.2, 3.4, [caption("Ye raaz hai 👇", "white", 860)]),
    ]
    hook_len = sum(d for _, d in segs)
    segs.append(clip(8.0, END))  # resume at "Lekin 2nd week se" → Day 14/21/27
    audio = audio_from([(0, hook_len), (8.0, END)])
    assemble(segs, f"{OUT}/hook-A-sleeveless.mp4", audio)


def hook_b():
    x = red_x()
    segs = [
        clip(12.0, 12.6, [(x, 0.6, 1.2), (caption("RUKO ✋", "pink", 820), 0.6, 1.2)], freeze=0.6),
        clip(12.9, 14.9, [caption("Dark underarms ki asal wajah ye hai", "white", 820)]),
        clip(3.5, 5.1, [caption("…aur ye deo ya lemon se theek nahi hoti", "white", 820)]),
    ]
    hook_len = sum(d for _, d in segs)
    # Body without the original shaving segment (10.5–15.6), since the hook already covers it.
    segs += [clip(5.2, 10.5), clip(15.6, END)]
    audio = audio_from([(0, hook_len), (5.2, 10.5), (15.6, END)])
    assemble(segs, f"{OUT}/hook-B-asal-wajah.mp4", audio)


def hook_c():
    sticker = comment_sticker("Ye sach mein kaam karta hai ya sirf ad hai? 🙄")
    segs = [
        clip(3.5, 5.1, [sticker]),
        clip(0.0, 1.0, [caption("Khud dekh lo 👀", "label", 960, min_w=520)]),  # box covers burned-in caption
        grid([6.6, 8.6, 9.9, 10.38], 2.0, [caption("Day 1 → Day 27", "label", 618)]),
    ]
    hook_len = sum(d for _, d in segs)
    segs.append(clip(5.2, END))
    audio = audio_from([(0, hook_len), (5.2, END)])
    assemble(segs, f"{OUT}/hook-C-comment-reply.mp4", audio)


# --- bodies (silent rough cuts: VO shown as subtitles, new shots tagged) -----

def vo(text):
    return caption("VO: " + text, "vo")


def tag(text):
    return caption("NEW SHOT: " + text, "tag")


ROUGH = None  # set in main


def body_1():
    segs = [
        clip(0.0, 5.2),  # original hook
        clip(3.5, 5.1, [ROUGH, tag("creator to camera, 3 fingers up"),
                        caption("3 galtiyan jo underarms dark karti hain", "white", 820),
                        vo("Ye 3 galtiyan hum sab karte hain…")], speed=0.5),
        clip(12.0, 15.6, [ROUGH, caption("1. Dry shaving 🪒", "white", 820),
                          vo("Pehli — baghair kuch lagaye shaving. Har baar skin chhilti hai aur dark hoti jati hai.")]),
        clip(15.6, 17.0, [ROUGH, tag("tight top rubbing underarm"), caption("2. Friction", "white", 820),
                          vo("Doosri — tight kapre aur garmi mein rubbing.")], speed=0.5),
        clip(31.0, 33.0, [ROUGH, tag("sweat close-up, deo sprayed after shave"),
                          caption("3. Pasina + harsh deo", "white", 820),
                          vo("Teesri — pasina aur shave ke foran baad harsh deo.")], speed=0.75),
        clip(17.0, 22.5, [ROUGH, caption("Kynd Bright Booster", "pink", 120),
                          vo("Is liye maine Kynd Bright Booster shuru kiya — kojic, glycolic aur lactic acid.")]),
        clip(2.2, 3.4, [ROUGH, caption("Raat ko, shower ke baad", "white", 820),
                        vo("Bas raat ko shower ke baad lagati hoon. [VERIFY directions]")], speed=0.4),
        clip(6.25, 7.25, [ROUGH, caption("Day 1", "label", 860), vo("Aur ye mera result hai.")]),
        clip(8.3, 10.6, [ROUGH, vo("Aur ye mera result hai.")]),
        clip(25.5, 28.0, [ROUGH, caption("Bad smell bhi nai ati 🌸", "white", 820),
                          vo("Plus fragrance itni achi hai ke poora din fresh.")]),
        clip(43.0, 51.8, [ROUGH, vo("Pasand na aye to 100 din mein paise wapis. Link neeche hai.")]),
        clip(52.0, END),
    ]
    assemble(segs, f"{OUT}/body-1-3-galtiyan-ROUGH.mp4")


def body_2():
    segs = [
        clip(0.0, 5.2),  # original hook
        card(1.6, [ROUGH, tag("lemon / aloo / baking soda with X stamps"),
                   (caption("Lemon ❌", "pink", 440), 0.0, 1.6), (caption("Aloo ❌", "pink", 560), 0.5, 1.6),
                   (caption("Baking soda ❌", "pink", 680), 1.0, 1.6),
                   vo("Lemon, aloo, baking soda — sab try kar liya tha.")]),
        clip(6.25, 7.5, [ROUGH, caption("Kuch farq nahi para 😩", "white", 820),
                        vo("Kuch farq nahi para, ulta jalan ho jati thi.")], speed=0.6),
        clip(12.0, 15.6, [ROUGH, caption("Masla upar nahi, andar hai", "white", 820),
                          vo("Kyun ke masla sirf rang ka nahi — shaving se skin andar se damage hoti hai.")]),
        clip(51.0, 51.9, [ROUGH, vo("Regular products sirf smell chupate hain.")], freeze=1.6),
        clip(17.0, 21.0, [ROUGH, vo("Kynd mein kojic, glycolic aur lactic acid hai jo dark spots brighten karte hain.")]),
        card(1.0, [ROUGH, caption("Kitne din?", "pink")]),
        clip(8.3, 10.6, [ROUGH, vo("2 hafte se farq nazar aana shuru.")]),
        card(1.0, [ROUGH, caption("Sirf underarms?", "pink")]),
        clip(31.0, 35.0, [ROUGH, vo("Neck aur bikini line pe bhi.")]),
        card(1.0, [ROUGH, caption("Smell?", "pink")]),
        clip(25.5, 28.0, [ROUGH, caption("Bad smell nai ati 🌸", "white", 820), vo("Poora din fresh.")]),
        clip(40.0, 42.5, [ROUGH]),
        clip(48.0, 51.0, [ROUGH, caption("Kaam na kare? Poore paise wapis.", "white", 560),
                          vo("Aur agar kaam na kare? 100 din mein poore paise wapis. Risk zero.")]),
        clip(52.0, END),
    ]
    assemble(segs, f"{OUT}/body-2-sab-try-kar-liya-ROUGH.mp4")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    ROUGH = caption("ROUGH CUT · VO to record", "tag", 1228)
    for fn in (hook_a, hook_b, hook_c, body_1, body_2):
        fn()
