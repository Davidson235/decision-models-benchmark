"""Twenty vision tasks arranged as a difficulty ladder (5 levels x 4 tasks).

Every image is generated from code, so the ground truth is exact by
construction: there is no annotation step that could drift.

Design note after the first run: pixel-acuity stressors (3 px misalignment,
JPEG noise) turned out to be either invisible to every model or free for every
model. The revision below moves the difficulty of levels 4-5 from "see smaller"
to "reason over what you see": arithmetic against a printed total, aggregate
comparison of bars, a ratio between two panels, counting in a dense grid, and a
logical bug in code that is not the highlighted line.
"""
from __future__ import annotations

import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 560, 400
FONT_PATHS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
]
FONT_MONO = [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf"]


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    for path in (FONT_MONO if mono else FONT_PATHS):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def canvas(bg="white") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), bg)
    return img, ImageDraw.Draw(img)


def _circle(d, cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def degrade(img: Image.Image, quality: int = 55) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    px = img.load()
    rng = random.Random(20261023)
    for _ in range(7000):
        x, y = rng.randrange(W), rng.randrange(H)
        r, g, b = px[x, y]
        n = rng.randint(-14, 14)
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    return img


# --------------------------------------------------------------------- level 1
def v01():
    img, d = canvas()
    _circle(d, W // 2, H // 2, 110, (210, 25, 35))
    return img


def v02():
    img, d = canvas()
    _circle(d, 170, 200, 80, "black")
    _circle(d, 390, 200, 80, "black")
    return img


def v03():
    img, d = canvas()
    d.rectangle([180, 100, 380, 300], fill="black")
    return img


def v04():
    img, d = canvas()
    d.polygon([(400, 90), (480, 310), (320, 310)], fill=(30, 90, 200))
    d.line([(280, 0), (280, H)], fill=(200, 200, 200), width=2)
    return img


# --------------------------------------------------------------------- level 2
def v05():
    img, d = canvas()
    d.text((W // 2, H // 2), "742", font=font(120), fill="black", anchor="mm")
    return img


def v06():
    img, d = canvas()
    d.rectangle([60, 150, 220, 250], fill=(90, 90, 90))
    d.rectangle([300, 150, 500, 250], fill=(90, 90, 90))
    return img


def v07():
    img, d = canvas()
    d.line([(200, 210), (260, 280)], fill=(20, 150, 60), width=26)
    d.line([(260, 280), (380, 130)], fill=(20, 150, 60), width=26)
    return img


def v08():
    img, d = canvas("#f7f7f7")
    d.rectangle([120, 60, 440, 340], fill="white", outline=(180, 180, 180), width=2)
    d.text((280, 110), "ORDER 7712", font=font(26), fill=(40, 40, 40), anchor="mm")
    d.text((280, 200), "PAID", font=font(64), fill=(20, 140, 60), anchor="mm")
    d.text((280, 300), "total 1 990 RUB", font=font(22), fill=(60, 60, 60), anchor="mm")
    return img


# --------------------------------------------------------------------- level 3
def v09():
    """Only ~8 px of the button's right edge is outside the viewport."""
    img, d = canvas()
    d.rectangle([16, 150, 544, 232], fill=(238, 238, 238), outline=(210, 210, 210))
    d.rectangle([300, 162, 568, 220], fill=(40, 110, 220))
    d.text((430, 191), "Продолжить", font=font(22), fill="white", anchor="mm")
    d.line([(546, 0), (546, H)], fill=(120, 120, 120), width=2)
    return img


def v10():
    """Two badges overlap each other by 8 px; the title itself fits."""
    img, d = canvas()
    d.text((40, 118), "Куртка зимняя", font=font(34), fill=(30, 30, 30), anchor="lm")
    d.rectangle([330, 96, 420, 142], fill=(220, 40, 40))
    d.text((375, 119), "-40%", font=font(24), fill="white", anchor="mm")
    d.rectangle([412, 96, 500, 142], fill=(30, 80, 180))
    d.text((456, 119), "ХИТ", font=font(24), fill="white", anchor="mm")
    return img


def v11():
    """A form where one label is duplicated: 'Поле 2' appears twice."""
    img, d = canvas()
    labels = ["Поле 1", "Поле 2", "Поле 2"]
    for i, label in enumerate(labels):
        y = 90 + i * 90
        d.text((44, y - 22), label, font=font(17), fill=(80, 80, 80))
        d.rectangle([44, y, 516, y + 46], outline=(130, 130, 130), width=2)
    return img


def v12():
    """Five fields, three of them filled."""
    img, d = canvas()
    rows = [("Имя", "Анна"), ("Email", "anna@mail.ru"), ("Телефон", ""),
            ("Город", ""), ("Комментарий", "домофон 12")]
    for i, (label, value) in enumerate(rows):
        y = 60 + i * 66
        d.text((40, y - 18), label, font=font(15), fill=(90, 90, 90))
        d.rectangle([40, y, 520, y + 40], outline=(140, 140, 140), width=2)
        if value:
            d.text((52, y + 20), value, font=font(19), fill=(20, 20, 20), anchor="lm")
    return img


# --------------------------------------------------------------------- level 4
ITEMS = [("Кофе", 1250), ("Круассан", 740), ("Сок", 310), ("Доставка", 0),
         ("Сервисный сбор", 120), ("Упаковка", 90), ("Скидка", -192)]
ITEMS_SUM = sum(p for _, p in ITEMS)          # 2318
PRINTED_TOTAL = 4318                           # deliberately wrong by 2 000


def v13():
    """A receipt whose printed total does not match the sum of its items."""
    img, d = canvas("white")
    d.text((26, 22), "ЧЕК  № 0042", font=font(20), fill="black")
    y = 64
    for name, price in ITEMS:
        d.text((26, y), name, font=font(16), fill=(45, 45, 45))
        d.text((534, y), f"{price:,}".replace(",", " "), font=font(16),
               fill=(45, 45, 45), anchor="ra")
        y += 34
    d.line([(26, y + 4), (534, y + 4)], fill=(120, 120, 120), width=2)
    d.text((26, y + 16), "ИТОГО", font=font(22), fill="black")
    d.text((534, y + 14), f"{PRINTED_TOTAL:,}".replace(",", " "), font=font(26),
           fill="black", anchor="ra")
    return img


BAR_HEIGHTS = {"A": 120, "B": 190, "C": 300, "D": 90, "E": 296, "F": 150}


def v14():
    """A table with two section headers among nine data rows."""
    img, d = canvas()
    d.rectangle([20, 16, 540, 46], fill=(228, 233, 245))
    d.text((34, 31), "ID", font=font(15), fill="black", anchor="lm")
    d.text((250, 31), "Статус", font=font(15), fill="black", anchor="lm")
    y = 46
    rows = [("section", "Октябрь"), ("data", "1001 ok"), ("data", "1002 ok"),
            ("data", "1003 error"), ("data", "1004 ok"), ("section", "Ноябрь"),
            ("data", "1005 pending"), ("data", "1006 ok"), ("data", "1007 ok"),
            ("data", "1008 error"), ("data", "1009 ok")]
    for kind, text in rows:
        size = 30 if kind == "section" else 26
        if kind == "section":
            d.rectangle([20, y, 540, y + size], fill=(242, 244, 248))
            d.text((34, y + size // 2), text, font=font(14), fill=(70, 70, 90), anchor="lm")
        else:
            d.line([(20, y), (540, y)], fill=(205, 205, 205), width=1)
            d.text((34, y + size // 2), text, font=font(14), fill=(45, 45, 45), anchor="lm")
        y += size
    return img


def v15():
    """Six bars; the question needs four of them added up, not one compared."""
    img, d = canvas()
    x = 40
    for label, h in BAR_HEIGHTS.items():
        d.rectangle([x, 340 - h, x + 56, 340], fill=(74, 112, 196))
        d.text((x + 28, 358), label, font=font(20), fill="black", anchor="mm")
        x += 84
    d.line([(24, 340), (536, 340)], fill=(120, 120, 120), width=2)
    return img


def v16():
    """Two panels: p95 before and after. The answer is a ratio, not a value."""
    img, d = canvas()
    for i, (title, value, color) in enumerate(
            (("ДО", "8.1 s", (200, 60, 60)), ("ПОСЛЕ", "2.4 s", (30, 150, 80)))):
        x = 30 + i * 265
        d.rectangle([x, 60, x + 235, 320], fill="#f4f6f8", outline=(200, 200, 200), width=2)
        d.text((x + 117, 100), title, font=font(22), fill=(90, 90, 90), anchor="mm")
        d.text((x + 117, 190), "p95", font=font(18), fill=(110, 110, 110), anchor="mm")
        d.text((x + 117, 245), value, font=font(44), fill=color, anchor="mm")
    d.text((280, 350), "до / после оптимизации", font=font(18), fill=(110, 110, 110), anchor="mm")
    return img


# --------------------------------------------------------------------- level 5
RED_CELLS = {"B1", "C4", "D2", "E5", "F1", "A6", "E2"}
ORANGE_CELLS = {"C2", "A4", "F5"}


def v17():
    """Six-by-six grid with seven red and three orange tiles: count the red ones."""
    img, d = canvas()
    cols, rows = "ABCDEF", 6
    for ci, col in enumerate(cols):
        for ri in range(rows):
            x = 34 + ci * 84
            y = 20 + ri * 62
            cell = f"{col}{ri + 1}"
            fill = (168, 168, 168)
            if cell in RED_CELLS:
                fill = (214, 28, 38)
            elif cell in ORANGE_CELLS:
                fill = (232, 140, 24)
            d.rectangle([x, y, x + 72, y + 50], fill=fill)
            d.text((x + 36, y + 25), cell, font=font(12), fill=(245, 245, 245), anchor="mm")
    return img


# Tight gold box for the red dot in v18: centre (0.28W, 0.72H), radius 18 px.
V18_BOX = {"left": 0.248, "right": 0.312, "top": 0.675, "bottom": 0.765}


def v18():
    """One small red dot among grey and orange decoys, on a degraded frame."""
    img, d = canvas("#f4f4f4")
    d.rectangle([30, 30, 250, 160], outline=(150, 150, 150), width=3)
    _circle(d, 120, 100, 26, (168, 168, 168))
    _circle(d, 380, 90, 24, (232, 140, 24))
    _circle(d, int(0.28 * W), int(0.72 * H), 18, (214, 28, 38))
    _circle(d, 430, 300, 30, (168, 168, 168))
    _circle(d, 90, 330, 20, (232, 140, 24))
    return degrade(img, quality=60)


CODE_LINES = [
    "if (!cart.items.length) return null;",       # 13
    "const total = cart.items.reduce(sum, 0);",   # 14
    "await pay(total, { retry: 3 });",            # 15  <- decorative highlight
    "const receipt = await getReceipt(order.id);",  # 16
    "if (!receipt) throw new Error('no receipt');",  # 17
    "logger.info('paid', receipt.id);",           # 18
    "await mail.send(receipt, user);",            # 19
    "if (mail.ok) retryLater();",                 # 20  <- inverted condition
    "return receipt.id;",                          # 21
]
BUG_LINE = 20


def v19():
    """Code where the highlighted line is a decoy and the bug is elsewhere."""
    img, d = canvas("#0f1419")
    d.text((18, 12), "checkout.ts — edited", font=font(13, mono=True), fill=(150, 170, 190))
    y = 44
    for i, text in enumerate(CODE_LINES):
        if i == 2:
            d.rectangle([10, y - 4, 550, y + 18], fill=(58, 40, 12))
        d.text((16, y), f"{13 + i}", font=font(12, mono=True), fill=(110, 130, 150))
        d.text((56, y), text, font=font(13, mono=True), fill=(220, 232, 242))
        y += 26
    return degrade(img, quality=65)


def v20():
    """Cross-modal conflict: the stamp says REJECTED while the text says approved."""
    img, d = canvas("#fafafa")
    d.rectangle([110, 60, 450, 340], fill="white", outline=(190, 190, 190), width=2)
    d.text((280, 110), "АКТ ПРИЁМКИ № 4", font=font(20), fill=(50, 50, 50), anchor="mm")
    d.text((280, 200), "REJECTED", font=font(46), fill=(200, 30, 40), anchor="mm")
    d.text((280, 300), "подпись: Иванов", font=font(16), fill=(110, 110, 110), anchor="mm")
    return img.rotate(-2, fillcolor="#fafafa")


TASKS_V = [
    # ---------------------------------------------------------------- level 1
    dict(id="V1-01", level=1, render=v01, family="vision_color",
         questions={"q": dict(type="choice", instructions="Какого цвета объект в центре?",
                              criteria={"red": "красный", "blue": "синий",
                                        "green": "зелёный", "yellow": "жёлтый"})},
         gold={"q": "red"}),
    dict(id="V1-02", level=1, render=v02, family="vision_count",
         questions={"q": dict(type="choice", instructions="Сколько кругов на изображении?",
                              criteria={"1": "один", "2": "два", "3": "три", "4": "четыре"})},
         gold={"q": "2"}),
    dict(id="V1-03", level=1, render=v03, family="vision_shape",
         questions={"q": dict(type="noul", instructions="На изображении есть закрашенный квадрат?",
                              criteria={"true": "Да, чёрный квадрат",
                                        "false": "Нет квадрата или он не закрашен"})},
         gold={"q": True}),
    dict(id="V1-04", level=1, render=v04, family="vision_position",
         questions={"q": dict(type="choice", instructions="В какой половине находится треугольник?",
                              criteria={"left": "слева", "right": "справа"})},
         gold={"q": "right"}),
    # ---------------------------------------------------------------- level 2
    dict(id="V2-05", level=2, render=v05, family="vision_text",
         questions={"q": dict(type="choice", instructions="Какое число написано?",
                              criteria={"724": "724", "742": "742", "472": "472"})},
         gold={"q": "742"}),
    dict(id="V2-06", level=2, render=v06, family="vision_compare",
         questions={"q": dict(type="choice", instructions="Какой прямоугольник шире?",
                              criteria={"left": "левый", "right": "правый"})},
         gold={"q": "right"}),
    dict(id="V2-07", level=2, render=v07, family="vision_symbol",
         questions={"q": dict(type="noul", instructions="На изображении галочка (check mark)?",
                              criteria={"true": "Да, галочка",
                                        "false": "Нет, другой символ"})},
         gold={"q": True}),
    dict(id="V2-08", level=2, render=v08, family="vision_stamp",
         questions={"q": dict(type="choice", instructions="Какой статус заказа?",
                              criteria={"paid": "оплачен", "due": "ожидает оплаты",
                                        "void": "аннулирован"})},
         gold={"q": "paid"}),
    # ---------------------------------------------------------------- level 3
    dict(id="V3-09", level=3, render=v09, family="vision_layout",
         questions={"q": dict(type="noul", instructions="Кнопка выходит за правый край экрана?",
                              criteria={"true": "Да, часть кнопки за границей",
                                        "false": "Нет, кнопка целиком внутри"})},
         gold={"q": True}),
    dict(id="V3-10", level=3, render=v10, family="vision_layout",
         questions={"q": dict(type="choice", instructions="Какой дефект вёрстки виден?",
                              criteria={"overlap": "Элементы перекрываются",
                                        "overflow": "Контент выходит за контейнер",
                                        "contrast": "Недостаточный контраст"})},
         gold={"q": "overlap"}),
    dict(id="V3-11", level=3, render=v11, family="vision_text",
         questions={"q": dict(type="noul", instructions="Все подписи полей уникальны?",
                              criteria={"true": "Да, каждая подпись встречается один раз",
                                        "false": "Нет, есть повтор"})},
         gold={"q": False}),
    dict(id="V3-12", level=3, render=v12, family="vision_count",
         questions={"q": dict(type="choice", instructions="Сколько полей заполнено?",
                              criteria={"2": "два", "3": "три", "4": "четыре", "5": "пять"})},
         gold={"q": "3"}),
    # ---------------------------------------------------------------- level 4
    dict(id="V4-13", level=4, render=v13, family="vision_arithmetic",
         questions={"q": dict(type="noul",
                              instructions="Напечатанный итог совпадает с суммой позиций?",
                              criteria={"true": "Да, сходится",
                                        "false": "Нет, итог отличается от суммы"})},
         gold={"q": False}),
    dict(id="V4-15", level=4, render=v15, family="vision_aggregate",
         questions={"q": dict(type="noul",
                              instructions="Сумма C и E больше суммы A и B?",
                              criteria={"true": "Да, C+E больше",
                                        "false": "Нет, A+B больше или равно"})},
         gold={"q": True}),
    dict(id="V4-16", level=4, render=v16, family="vision_ratio",
         questions={"q": dict(type="choice",
                              instructions="Во сколько раз снизился p95 после оптимизации?",
                              criteria={"20": "примерно в 2 раза", "34": "примерно в 3.4 раза",
                                        "40": "примерно в 4 раза", "81": "примерно в 8 раз"})},
         gold={"q": "34"}),
    dict(id="V4-14", level=4, render=v14, family="vision_table",
         questions={"q": dict(type="choice",
                              instructions="Сколько строк с данными (не заголовков и не разделов)?",
                              criteria={"7": "7", "8": "8", "9": "9", "11": "11"})},
         gold={"q": "9"}),
    # ---------------------------------------------------------------- level 5
    dict(id="V5-17", level=5, render=v17, family="vision_count",
         questions={"q": dict(type="choice", instructions="Сколько красных клеток в сетке?",
                              criteria={"5": "5", "6": "6", "7": "7", "8": "8"})},
         gold={"q": "7"}),
    dict(id="V5-18", level=5, render=v18, family="vision_box",
         questions={"q": dict(type="box", instructions="Найди красную точку.")},
         gold={"q": V18_BOX}, box_only=True),
    dict(id="V5-19", level=5, render=v19, family="vision_code",
         questions={"q": dict(type="choice",
                              instructions="На какой строке логическая ошибка в условии?",
                              criteria={"15": "15", "18": "18", "20": "20", "21": "21"})},
         gold={"q": "20"}),
    dict(id="V5-20", level=5, render=v20, family="vision_ocr",
         questions={"q": dict(type="noul", instructions="Согласно штампу документ принят?",
                              criteria={"true": "Да, принят",
                                        "false": "Нет, отклонён"})},
         gold={"q": False}),
]

LEVEL_TITLES = {
    1: "L1 крупный объект",
    2: "L2 текст/счёт",
    3: "L3 вёрстка и подписи",
    4: "L4 арифметика и сравнение",
    5: "L5 плотная сцена",
}


def render_png(task: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{task['id']}.png"
    if not path.exists():
        img = task["render"]()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        path.write_bytes(buf.getvalue())
    return path
