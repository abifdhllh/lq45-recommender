"""
Konstituen indeks LQ45 periode Feb–Apr 2026 (sumber: pengumuman BEI / media).
Perbarui daftar ini saat ada rebalancing resmi.
Ticker Yahoo Finance untuk IDX: KODE.JK
"""

LQ45_CODES = [
    "AADI",
    "ADMR",
    "ADRO",
    "AKRA",
    "AMMN",
    "AMRT",
    "ANTM",
    "ASII",
    "BBCA",
    "BBNI",
    "BBRI",
    "BBTN",
    "BMRI",
    "BREN",
    "BRPT",
    "BUMI",
    "CPIN",
    "CTRA",
    "DSSA",
    "EMTK",
    "EXCL",
    "GOTO",
    "HEAL",
    "ICBP",
    "INCO",
    "INDF",
    "INKP",
    "ISAT",
    "ITMG",
    "JPFA",
    "KLBF",
    "MAPI",
    "MBMA",
    "MDKA",
    "MEDC",
    "NCKL",
    "PGAS",
    "PGEO",
    "PTBA",
    "SCMA",
    "SMGR",
    "TLKM",
    "TOWR",
    "UNTR",
    "UNVR",
]

def yahoo_symbols():
    return [f"{c}.JK" for c in LQ45_CODES]
