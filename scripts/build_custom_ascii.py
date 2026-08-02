#!/usr/bin/env python3
import os
import numpy as np
from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
IMG_PATH = r"C:\Users\Prateek Raiger\.gemini\antigravity-ide\brain\77e72203-1a73-4cc2-85ae-4acc27331651\media__1785657612538.png"

def main():
    img = Image.open(IMG_PATH).convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.6)

    RAMP = " .`:-=+*cs#%@"
    COLS = 90
    ROW_RATIO = 0.48
    CHAR_W = 7.74
    LINE_H = 15
    FONT_SIZE = 12.9
    ROW_DELAY = 0.09

    w, h = img.size
    rows = int(COLS * (h / w) * ROW_RATIO)
    img = img.resize((COLS, rows), Image.Resampling.LANCZOS)
    px = np.array(img)

    lines = []
    n = len(RAMP)
    for r in range(rows):
        line = "".join(RAMP[min(n - 1, int((1.0 - px[r, c] / 255.0) ** 1.5 * n))] for c in range(COLS)).rstrip()
        lines.append(line)

    pad = 14
    width = int(COLS * CHAR_W + pad * 2)
    height = len(lines) * LINE_H + pad * 2

    FAMILY = "JBMono,ui-monospace,SFMono-Regular,Menlo,Consolas,&apos;Liberation Mono&apos;,monospace"
    FG_LIGHT = "#6e7681"
    FG_DARK = "#c9d1d9"

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="{FAMILY}">',
         f'<style>.a{{fill:{FG_LIGHT}}}@media(prefers-color-scheme:dark){{.a{{fill:{FG_DARK}}}}}</style>']

    for i, line in enumerate(lines):
        y = pad + i * LINE_H
        begin = f"{i * ROW_DELAY:.2f}s"
        end = f"{(i + 1) * ROW_DELAY:.2f}s"
        w_px = max(len(line), 1) * CHAR_W
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        p.append(f'<clipPath id="c{i}"><rect x="{pad}" y="{y}" height="{LINE_H}" width="0"><animate attributeName="width" from="0" to="{w_px:.1f}" begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/></clipPath>')
        p.append(f'<g clip-path="url(#c{i})"><text xml:space="preserve" x="{pad}" y="{y + 11.2:.1f}" class="a" font-size="{FONT_SIZE}">{safe}</text></g>')
        p.append(f'<rect y="{y + 1}" width="6" height="12" class="a" opacity="0"><animate attributeName="x" from="{pad}" to="{pad + w_px:.1f}" begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/><set attributeName="opacity" to="0.8" begin="{begin}"/><set attributeName="opacity" to="0" begin="{end}"/></rect>')

    p.append("</svg>")
    svg_out = "".join(p)

    out_path = os.path.join(REPO_ROOT, "ascii.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg_out)
    print(f"Generated custom ascii.svg at {out_path} from user avatar!")

if __name__ == "__main__":
    main()
