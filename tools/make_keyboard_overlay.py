"""
1:1 printable overlay for the 32-key instrument, two-row layout.

Geometry:
  lower row: 19 white keys, 20 mm wide x 50 mm long, no gaps -> 380 mm
  upper row: 13 black keys, 20 mm wide x 40 mm long, separate row above
             the white row, with 4 mm white gaps between them
  total depth: 50 + 40 = 90 mm

The sheet is split over two A4 PORTRAIT pages (210 x 297 mm). The keyboard
starts at x=10 mm on page 1; page 2 is shifted left by 180 mm, so the pages
overlap by 20 mm. The join at x=200 mm falls between A5 and B5 and in the
4 mm black-key gap after G#5, so no key is cut.

Outputs:
  pc/overlay/keyboard_overlay_clean.html / .svg
  pc/overlay/keyboard_overlay_labels.html / .svg

Print the HTML at A4 portrait, 100% / actual size, no scaling.
"""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "pc" / "overlay"

WHITE_W = 20
WHITE_L = 50
WHITE_COUNT = 19
WHITE_TOTAL = WHITE_COUNT * WHITE_W  # 380

BLACK_W = 20
BLACK_L = 40
BLACK_GAP = 4
BLACK_COUNT = 13
BLACK_TOTAL = BLACK_COUNT * BLACK_W + (BLACK_COUNT - 1) * BLACK_GAP  # 308
BLACK_START = (WHITE_TOTAL - BLACK_TOTAL) / 2  # 36
BLACK_STEP = BLACK_W + BLACK_GAP  # 24
WHITE_Y = BLACK_L  # 40
TOTAL_H = BLACK_L + WHITE_L  # 90

WHITE_NOTES = ["F4", "G4", "A4", "B4", "C5", "D5", "E5", "F5", "G5",
               "A5", "B5", "C6", "D6", "E6", "F6", "G6", "A6", "B6", "C7"]
WHITE_NUMS = [1, 3, 5, 7, 8, 10, 12, 13, 15, 17, 19, 20, 22, 24, 25, 27, 29, 31, 32]
BLACK_NOTES = ["F#4", "G#4", "A#4", "C#5", "D#5", "F#5", "G#5", "A#5",
               "C#6", "D#6", "F#6", "G#6", "A#6"]
BLACK_NUMS = [2, 4, 6, 9, 11, 14, 16, 18, 21, 23, 26, 28, 30]


def keyboard_svg(labels: bool) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WHITE_TOTAL}mm" height="{TOTAL_H}mm" '
        f'viewBox="0 0 {WHITE_TOTAL} {TOTAL_H}">'
    ]
    # Black row background + boundary, so the two rows read as separate banks.
    parts.append(
        f'<rect x="{BLACK_START}" y="0" width="{BLACK_TOTAL}" height="{BLACK_L}" '
        f'fill="none" stroke="#c7c2b6" stroke-width="0.25"/>'
    )
    parts.append(
        f'<line x1="0" y1="{WHITE_Y}" x2="{WHITE_TOTAL}" y2="{WHITE_Y}" '
        f'stroke="#b8b3a7" stroke-width="0.25"/>'
    )
    # White row.
    for i in range(WHITE_COUNT):
        x = i * WHITE_W
        parts.append(
            f'<rect x="{x}" y="{WHITE_Y}" width="{WHITE_W}" height="{WHITE_L}" '
            f'fill="#fcfbf7" stroke="#1a1a1a" stroke-width="0.25"/>'
        )
    # Black row, with white gaps.
    for i in range(BLACK_COUNT):
        x = BLACK_START + i * BLACK_STEP
        parts.append(
            f'<rect x="{x}" y="0" width="{BLACK_W}" height="{BLACK_L}" '
            f'fill="#101010" stroke="#000000" stroke-width="0.2"/>'
        )
    if labels:
        for i, note in enumerate(WHITE_NOTES):
            cx = i * WHITE_W + WHITE_W / 2
            parts.append(
                f'<text x="{cx}" y="83.1" text-anchor="middle" font-size="1.8" '
                f'font-family="Segoe UI, sans-serif" fill="#9a968c">{WHITE_NUMS[i]}</text>'
            )
            parts.append(
                f'<text x="{cx}" y="87.4" text-anchor="middle" font-size="2.7" '
                f'font-family="Segoe UI, sans-serif" fill="#4c4942">{note}</text>'
            )
        for i, (note, num) in enumerate(zip(BLACK_NOTES, BLACK_NUMS)):
            cx = BLACK_START + i * BLACK_STEP + BLACK_W / 2
            parts.append(
                f'<text x="{cx}" y="33.2" text-anchor="middle" font-size="1.7" '
                f'font-family="Segoe UI, sans-serif" fill="#d9d0be">{note}</text>'
            )
            parts.append(
                f'<text x="{cx}" y="37.4" text-anchor="middle" font-size="1.8" '
                f'font-family="Segoe UI, sans-serif" fill="#f0e8d8">{num}</text>'
            )
    # Outer cut edge around the whole 380 x 90 mm overlay.
    parts.append(
        f'<rect x="0.15" y="0.15" width="{WHITE_TOTAL - 0.3}" height="{TOTAL_H - 0.3}" '
        f'fill="none" stroke="#1a1a1a" stroke-width="0.3"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def ruler_svg() -> str:
    ticks = []
    for i in range(11):
        x = i * 10
        height = 3.2 if i % 5 == 0 else 1.8
        ticks.append(f'<line x1="{x}" y1="8" x2="{x}" y2="{8 - height}" stroke="#333" stroke-width="0.25"/>')
        if i % 5 == 0:
            if i == 0:
                tx, anchor = 0.4, "start"
            elif i == 10:
                tx, anchor = 99.6, "end"
            else:
                tx, anchor = x, "middle"
            ticks.append(
                f'<text x="{tx}" y="3.2" text-anchor="{anchor}" font-size="2.2" fill="#555">{i * 10}</text>'
            )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="8mm" viewBox="0 0 100 8">'
        '<line x1="0" y1="8" x2="100" y2="8" stroke="#333" stroke-width="0.3"/>'
        + "".join(ticks)
        + "</svg>"
    )


def cutouts_html() -> str:
    pieces = []
    # 7 in the first row, 6 in the second; 20 x 40 mm with 4 mm gaps.
    for row, count in ((0, 7), (1, 6)):
        total = count * 20 + (count - 1) * 4
        start = (210 - total) / 2
        for i in range(count):
            x = start + i * 24
            y = 194 + row * 46
            index = row * 7 + i + 1
            pieces.append(
                f'<div style="position:absolute;left:{x}mm;top:{y}mm;width:20mm;height:40mm;'
                f'background:#101010;border:0.3mm dashed #ffffff;box-sizing:border-box;'
                f'color:#d9cdb6;font-size:2.2mm;text-align:center;padding-top:34mm">{index}</div>'
            )
    return "".join(pieces)


def page(labels: bool) -> str:
    kb = keyboard_svg(labels)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>KeyBorad overlay — {'labels' if labels else 'clean'}</title>
<style>
  @page {{ size: A4 portrait; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: #fff; color: #1a1a1a;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; }}
  .page {{ position: relative; width: 210mm; height: 297mm; overflow: hidden;
    page-break-after: always; background: #fff; }}
  .page:last-child {{ page-break-after: auto; }}
  .kb {{ position: absolute; top: 80mm; width: {WHITE_TOTAL}mm; height: {TOTAL_H}mm; }}
  .kb1 {{ left: 10mm; }}
  .kb2 {{ left: -180mm; }}
  .h1 {{ position: absolute; left: 15mm; top: 15mm; font-size: 5.2mm; font-weight: 600;
    letter-spacing: .06em; }}
  .h2 {{ position: absolute; left: 15mm; top: 24mm; font-size: 2.6mm; color: #666; }}
  .h2b {{ left: 25mm; }}
  .hint {{ position: absolute; left: 15mm; top: 63mm; font-size: 2.4mm; color: #555; }}
  .seam {{ position: absolute; top: 69mm; font-size: 2.5mm; color: #8a5a1d;
    background: #fff7e8; border: 0.2mm solid #e3c48b; padding: 1.4mm 2.4mm; }}
  .seam1 {{ left: 140mm; }}
  .seam2 {{ left: 30mm; }}
  .mark {{ position: absolute; width: 6mm; height: 6mm; }}
  .mark::before, .mark::after {{ content: ""; position: absolute; background: #111; }}
  .mark::before {{ left: 2.9mm; top: 0; width: 0.25mm; height: 6mm; }}
  .mark::after {{ left: 0; top: 2.9mm; width: 6mm; height: 0.25mm; }}
  .alignline {{ position: absolute; top: 74mm; height: 102mm; border-left: 0.2mm dashed #999; }}
  .ruler {{ position: absolute; top: 42mm; }}
  .steps {{ position: absolute; left: 15mm; top: 186mm; width: 180mm; font-size: 2.35mm;
    line-height: 1.72; color: #444; }}
  .steps b {{ color: #111; }}
  .note {{ position: absolute; left: 15mm; top: 258mm; width: 180mm; font-size: 2.2mm;
    color: #666; line-height: 1.65; }}
  .cutlabel {{ position: absolute; left: 15mm; top: 183mm; font-size: 2.7mm; font-weight: 600; }}
  .foot {{ position: absolute; left: 15mm; bottom: 7mm; font-size: 2.0mm; color: #888; }}
</style>
</head>
<body>

<div class="page">
  <div class="h1">KeyBorad · 32 键面板 · 1:1</div>
  <div class="h2">第 1 / 2 张 · A4 竖向 210 × 297 mm · 实际大小 100%（不要选“适应页面”）</div>
  <div class="ruler" style="left:15mm">{ruler_svg()}</div>
  <div class="hint">用尺量上面这段应为 100 mm；不对就重打。</div>

  <div class="kb kb1">{kb}</div>

  <div class="alignline" style="left:200mm"></div>
  <div class="mark" style="left:197mm;top:74mm"></div>
  <div class="mark" style="left:197mm;top:170mm"></div>
  <div class="seam seam1">接缝：与第 2 张重叠 20 mm，对齐虚线</div>

  <div class="cutlabel">可选：黑色键帽片 20 × 40 mm × 13</div>
  <div style="position:absolute;left:15mm;top:188mm;font-size:2.1mm;color:#666">剪下后垫在对应黑键上，可获得 1–2 mm 高度。</div>
  {cutouts_html()}

  <div class="foot">第 1 张：裁左、上、下三边；右边是接缝，不要裁。第 2 张：保留左侧 20 mm 重叠区，只裁上、下、右三边。<br>
  接缝在 A5 / B5 之间，且落在 G#5 / A#5 的黑键白缝里。建议 100–150 g 哑光纸或薄 PVC；覆盖后请重新校准阈值。此图只含 32 个琴键。</div>
</div>

<div class="page">
  <div class="h1">KeyBorad · 32 键面板 · 1:1</div>
  <div class="h2 h2b">第 2 / 2 张 · A4 竖向 210 × 297 mm · 左侧 20 mm 重叠</div>
  <div class="ruler" style="left:100mm">{ruler_svg()}</div>
  <div class="hint">键盘部分：0–200 mm；右侧 10 mm 留白可裁掉。</div>

  <div class="kb kb2">{kb}</div>

  <div class="alignline" style="left:10mm"></div>
  <div class="mark" style="left:7mm;top:74mm"></div>
  <div class="mark" style="left:7mm;top:170mm"></div>
  <div class="seam seam2">← 重叠区 20 mm：对齐虚线 / 上下十字</div>

  <div class="steps">
    <b>拼接步骤</b><br>
    1. 两页都按 100% 打印，先用 100 mm 校准尺核对。<br>
    2. 第 1 张裁左、上、下；右边是接缝，不要裁。第 2 张保留左侧 20 mm，只裁上、下、右。<br>
    3. 把第 2 张左侧 20 mm 叠到第 1 张右侧，让虚线 + 上下十字重合。<br>
    4. 从背面胶带固定；接缝在 A5 / B5 之间，黑键白缝处。<br>
    5. 可选：把第 1 张下方的 13 个黑键片剪下，垫高 1–2 mm。<br>
    6. 覆盖后跑一次阈值校准（静置 / 悬停 / 逐键）。
  </div>

  <div class="note">
    尺寸：白键 20 × 50 mm × 19；黑键 20 × 40 mm × 13，白缝 4 mm；总宽 380 mm，总深 90 mm。<br>
    下排白键 19 个连续排列；上排黑键单独一排，居中放置，同组不再相接。<br>
    黑键排与白键排分开；黑键白缝宽度可改成 3–5 mm（改脚本里的 BLACK_GAP 后重新生成）。
  </div>

  <div class="foot">第 2 张 · 与第 1 张重叠 20 mm · 接缝对齐后从背面固定</div>
</div>

</body>
</html>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "keyboard_overlay_clean.html").write_text(page(False), encoding="utf-8")
    (OUT / "keyboard_overlay_labels.html").write_text(page(True), encoding="utf-8")
    (OUT / "keyboard_overlay_clean.svg").write_text(keyboard_svg(False), encoding="utf-8")
    (OUT / "keyboard_overlay_labels.svg").write_text(keyboard_svg(True), encoding="utf-8")
    for name in ("keyboard_overlay_clean.html", "keyboard_overlay_labels.html",
                 "keyboard_overlay_clean.svg", "keyboard_overlay_labels.svg"):
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
