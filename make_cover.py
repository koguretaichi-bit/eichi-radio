"""番組のカバー画像(正方形)を生成する。Spotify/Apple用に1500x1500のJPG。
日本語フォントはWindows標準を自動選択。お好みで docs/cover.jpg を差し替え可。"""
import os
from PIL import Image, ImageDraw, ImageFont

W = 1500
TITLE = "アイディアの\nアウフヘーベン"
SUB = "ニュース×古典で、信頼を築く"

# 背景: 紺のグラデーション風（単色2層）
img = Image.new("RGB", (W, W), (18, 24, 38))
draw = ImageDraw.Draw(img)
for y in range(W):
    t = y / W
    r = int(18 + t * 18)
    g = int(24 + t * 26)
    b = int(38 + t * 50)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# 罫線アクセント
draw.rectangle([60, 60, W - 60, W - 60], outline=(210, 180, 110), width=6)


def find_font(size):
    candidates = [
        r"C:\Windows\Fonts\YuGothB.ttc",
        r"C:\Windows\Fonts\meiryob.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


title_font = find_font(150)
sub_font = find_font(58)


def draw_center(text, font, y, fill):
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center", spacing=20)
    w = bbox[2] - bbox[0]
    draw.multiline_text(((W - w) / 2, y), text, font=font, fill=fill, align="center", spacing=20)


draw_center(TITLE, title_font, 470, (245, 245, 245))
draw_center(SUB, sub_font, 980, (210, 180, 110))

out = os.path.join("docs", "cover.jpg")
img.save(out, "JPEG", quality=90)
print("wrote", out, img.size)
