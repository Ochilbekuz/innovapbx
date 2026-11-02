"""Oʻzbek apostrofi uchun mini-shrift.

IBM Plex'da U+02BB (ʻ) va U+02BC (ʼ) «spacing modifier» sifatida 600 birlik enli —
«Qoʻngʻiroq» soʻzida harflar orasida teshik paydo boʻladi. Bu skript Plex'ning
oʻz tirnoq glifini (U+2018 ‘ → ʻ, U+2019 ’ → ʼ, en 270 atrofida) olib, faqat shu
ikki belgidan iborat woff2 yasaydi. CSS'da u unicode-range U+02BB-02BC bilan
asosiy shriftdan oldin turadi — qolgan matn Plex'da qoladi.

OFL: Plex nomi (Reserved Font Name) ishlatilmaydi — oila nomi «Innova Apostrof».
Ishga tushirish: python3 scripts/build-apostrof.py  (fonttools + brotli kerak)
"""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools import subset

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "node_modules" / "@fontsource"
OUT = ROOT / "src" / "styles" / "fonts"
JOBS = [
    ("ibm-plex-sans", "Innova Apostrof", w) for w in (400, 500, 600)
] + [("ibm-plex-sans-condensed", "Innova Apostrof Condensed", w) for w in (500, 600)]
MAP = {0x02BB: 0x2018, 0x02BC: 0x2019}


def build(pkg: str, family: str, weight: int) -> Path:
    font = TTFont(SRC / pkg / "files" / f"{pkg}-latin-{weight}-normal.woff2")
    for table in font["cmap"].tables:
        if table.isUnicode():
            for dst, src in MAP.items():
                if src in table.cmap:
                    table.cmap[dst] = table.cmap[src]
    opts = subset.Options()
    opts.layout_features = []
    opts.name_IDs = ["*"]
    opts.flavor = "woff2"
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=list(MAP))
    sub.subset(font)
    style = f"{family} {weight}"
    for rec in font["name"].names:
        if rec.nameID in (1, 16):
            rec.string = family
        elif rec.nameID in (3, 4):
            rec.string = style
        elif rec.nameID == 6:
            rec.string = style.replace(" ", "")
    out = OUT / f"{family.lower().replace(' ', '-')}-{weight}.woff2"
    font.flavor = "woff2"
    font.save(out)
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for job in JOBS:
        p = build(*job)
        print(p.name, p.stat().st_size, "bayt")
