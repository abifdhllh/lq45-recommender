#!/usr/bin/env python3
"""
Dashboard Streamlit untuk skrining LQ45 (data Yahoo Finance).
Jalankan: .venv/bin/streamlit run streamlit_app.py
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from constituents import LQ45_CODES
from recommender import run_with_meta

MAX_STOCKS = len(LQ45_CODES)
TZ_JAKARTA = ZoneInfo("Asia/Jakarta")

PERIOD_OPTIONS = {
    "1 bulan": "1mo",
    "3 bulan": "3mo",
    "6 bulan (default)": "6mo",
    "1 tahun": "1y",
    "2 tahun": "2y",
    "YTD": "ytd",
    "Maksimum": "max",
}

# Tooltip header kolom (ringkas). Detail ada di expander di bawah tabel.
_COL_HELP = {
    "code": "Kode saham di BEI (contoh: BBCA). Satu kode = satu emiten tercatat.",
    "score": (
        "Skor 0–100: peringkat relatif antar LQ45 menurut rumus (momentum, vol, Sharpe"
        ", + PE/ROE/dividen jika fundamental aktif). Bukan ramalan harga atau saran beli/jual."
    ),
    "last_price": (
        "Harga penutupan terakhir dari data Yahoo (IDR/lembar). Bukan harga real-time; "
        "bisa beda sedikit dengan aplikasi sekuritas Anda."
    ),
    "ret_1m_pct": (
        "Perubahan harga sekitar 1 bulan terakhir (%). Positif = naik, negatif = turun. "
        "Belum dipotong biaya broker/pajak."
    ),
    "ret_3m_pct": (
        "Perubahan harga sekitar 3 bulan terakhir (%). Untuk melihat tren sedikit lebih panjang."
    ),
    "vol_ann_pct": (
        "Volatilitas tahunan (diannualisasi) dari fluktuasi harian (%). Lebih besar = "
        "lebih loncat-loncat. Di skor, vol rendah sedikit diutamakan — bukan berarti vol tinggi selalu buruk."
    ),
    "sharpe_63d": (
        "Sharpe perkiraan ~63 hari perdagangan terakhir: imbal harian vs fluktuasi harian. "
        "Lebih tinggi = imbal relatif lebih besar dibanding 'noise'. Bisa negatif. Bukan Sharpe portofolio Anda."
    ),
    "trailing_pe": (
        "Trailing P/E: harga vs laba per saham kinerja yang sudah lewat (biasanya 12 bulan). "
        "Lebih kecil sering dianggap 'lebih murah' vs laba — tidak otomatis lebih baik. Kosong = data tidak ada."
    ),
    "forward_pe": (
        "Forward P/E memakai perkiraan laba ke depan (jika Yahoo punya). Bisa salah atau tidak update."
    ),
    "roe": (
        "Return on equity (biasanya desimal, mis. 0.15 ≈ 15%). Laba vs ekuitas pemegang saham. "
        "Bandingkan dengan utang, industri, dan laporan resmi."
    ),
    "div_pct": (
        "Perkiraan yield dividen tahunan (%) dari data Yahoo. Bukan jaminan dividen tahun depan sama."
    ),
    "error": (
        "Jika terisi, data emiten ini kurang/gagal diambil. Jangan dipakai untuk perbandingan "
        "sebelum dicek manual di sekuritas/IDX."
    ),
}


def _prepare_display_df(df: pd.DataFrame, fundamentals: bool) -> pd.DataFrame:
    out = df.copy()
    if fundamentals and "dividend_yield" in out.columns:
        out["div_pct"] = out["dividend_yield"].apply(
            lambda v: round(v * 100, 2) if pd.notna(v) else None
        )
        out = out.drop(columns=["dividend_yield"])
    return out


def _style_df(df: pd.DataFrame, *, dark_theme: bool = True) -> pd.io.formats.style.Styler:
    """Warnai return positif/negatif (hanya tampilan). Warna disesuaikan kontras light vs dark."""
    ret_cols = [c for c in ("ret_1m_pct", "ret_3m_pct") if c in df.columns]
    pos = "#4ade80" if dark_theme else "#1e8449"
    neg = "#f87171" if dark_theme else "#c0392b"

    def color_ret(v: float) -> str:
        if pd.isna(v):
            return ""
        if v > 0:
            return f"color: {pos}; font-weight: 600"
        if v < 0:
            return f"color: {neg}; font-weight: 600"
        return ""

    sty = df.style
    for c in ret_cols:
        sty = sty.map(color_ret, subset=[c])
    numeric_subset = [
        c
        for c in df.columns
        if c not in ("code", "error") and pd.api.types.is_numeric_dtype(df[c])
    ]
    if numeric_subset:
        sty = sty.format(na_rep="—", precision=4, subset=numeric_subset)
    return sty


def _friendly_fetch_error(exc: BaseException) -> str:
    raw = str(exc).strip()
    low = raw.lower()
    if "tidak ada data harga" in raw or "tidak ada data" in raw:
        return (
            "Tidak ada data harga yang terbaca dari Yahoo. Coba periode lain, periksa koneksi internet, "
            "atau coba lagi nanti."
        )
    if "gagal unduh" in low or "failed to download" in low or "timeout" in low:
        return (
            "Gagal mengunduh data dari Yahoo Finance (koneksi terputus, dibatasi, atau server sibuk). "
            "Tunggu sebentar lalu pakai **Refresh data**."
        )
    if "network" in low or "connection" in low or "ssl" in low:
        return "Masalah jaringan saat menghubungi Yahoo Finance. Periksa internet lalu coba lagi."
    return f"Tidak bisa memuat data: {raw}"


def _filter_by_code_query(df: pd.DataFrame, query: str) -> pd.DataFrame:
    q = (query or "").strip()
    if not q:
        return df
    tokens = [t for t in re.split(r"[\s,;]+", q.upper()) if t]
    if not tokens:
        return df
    codes = df["code"].astype(str).str.upper()
    mask = pd.Series(False, index=df.index)
    for t in tokens:
        mask |= codes.str.contains(t, regex=False, na=False)
    return df.loc[mask].copy()


@st.cache_data(ttl=120, show_spinner=False)
def _cached_full_run(use_fundamentals: bool, price_period: str) -> dict:
    """Satu snapshot penuh LQ45 + metadata; di-cache per parameter (bukan per top N)."""
    result = run_with_meta(
        use_fundamentals=use_fundamentals,
        price_period=price_period,
    )
    fetched_at = datetime.now(TZ_JAKARTA)
    pld = result.price_last_date
    pld_iso = None
    if pld is not None and not pd.isna(pld):
        pld_iso = pd.Timestamp(pld).isoformat()
    return {
        "table": result.table,
        "failed_download_codes": list(result.failed_download_codes),
        "price_last_date_iso": pld_iso,
        "fetched_at_iso": fetched_at.isoformat(),
    }


# Override ke tema terang bila user mematikan mode gelap (config default = dark).
_LIGHT_THEME_OVERRIDES = """
  .stApp, [data-testid="stAppViewContainer"], section.main {
    background-color: #ffffff !important;
    color: #31333f !important;
  }
  [data-testid="stSidebar"], section[data-testid="stSidebar"] {
    background-color: #f0f2f6 !important;
    border-right: 1px solid #e6e9ef !important;
  }
  [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] span, [data-testid="stSidebar"] p {
    color: #31333f !important;
  }
  div[data-testid="stHeader"] {
    background-color: #ffffff !important;
  }
  [data-testid="stMetric"] {
    background-color: #ffffff !important;
    border: 1px solid #e6e9ef !important;
    border-radius: 0.5rem !important;
    padding: 0.5rem !important;
  }
  [data-testid="stMetric"] label, [data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #31333f !important;
  }
  .stAlert, [data-testid="stAlertContentSuccess"], [data-testid="stAlertContentInfo"],
  [data-testid="stAlertContentWarning"] {
    color: #31333f !important;
  }
  div[data-testid="stExpander"] details summary { color: #31333f !important; }
  .stTextInput input, .stSelectbox div[data-baseweb="select"] {
    background-color: #ffffff !important;
    color: #31333f !important;
  }
"""


def _inject_theme_and_table_css(*, light_mode: bool) -> None:
    """Scroll horizontal untuk tabel (HP) + opsi override tema terang."""
    parts = [
        """
  div[data-testid="stDataFrame"] { overflow-x: auto !important; -webkit-overflow-scrolling: touch; }
  div[data-testid="stDataFrame"] > div { min-width: min(100%, 720px); }
"""
    ]
    if light_mode:
        parts.append(_LIGHT_THEME_OVERRIDES)
    st.markdown(
        "<style>" + "\n".join(parts) + "</style>",
        unsafe_allow_html=True,
    )


def _build_column_config(
    disp_cols: list[str],
) -> dict:
    col_conf: dict = {
        "code": st.column_config.TextColumn(
            "Kode",
            width="small",
            help=_COL_HELP["code"],
        ),
        "score": st.column_config.ProgressColumn(
            "Skor",
            help=_COL_HELP["score"],
            format="%.1f",
            min_value=0,
            max_value=100,
        ),
        "last_price": st.column_config.NumberColumn(
            "Harga",
            format="%.0f",
            help=_COL_HELP["last_price"],
        ),
        "ret_1m_pct": st.column_config.NumberColumn(
            "Ret 1m %",
            format="%.2f",
            help=_COL_HELP["ret_1m_pct"],
        ),
        "ret_3m_pct": st.column_config.NumberColumn(
            "Ret 3m %",
            format="%.2f",
            help=_COL_HELP["ret_3m_pct"],
        ),
        "vol_ann_pct": st.column_config.NumberColumn(
            "Vol tahunan %",
            format="%.2f",
            help=_COL_HELP["vol_ann_pct"],
        ),
        "sharpe_63d": st.column_config.NumberColumn(
            "Sharpe ~63d",
            format="%.4f",
            help=_COL_HELP["sharpe_63d"],
        ),
        "trailing_pe": st.column_config.NumberColumn(
            "PE trailing",
            format="%.2f",
            help=_COL_HELP["trailing_pe"],
        ),
        "forward_pe": st.column_config.NumberColumn(
            "PE forward",
            format="%.2f",
            help=_COL_HELP["forward_pe"],
        ),
        "roe": st.column_config.NumberColumn(
            "ROE",
            format="%.4f",
            help=_COL_HELP["roe"],
        ),
        "div_pct": st.column_config.NumberColumn(
            "Div yield %",
            format="%.2f",
            help=_COL_HELP["div_pct"],
        ),
        "error": st.column_config.TextColumn(
            "Error",
            width="medium",
            help=_COL_HELP["error"],
        ),
    }
    return {k: v for k, v in col_conf.items() if k in disp_cols}


def _compact_column_order(fundamentals: bool) -> list[str]:
    base = ["code", "score", "last_price", "ret_1m_pct", "ret_3m_pct"]
    if fundamentals:
        return base + ["trailing_pe", "forward_pe", "roe", "div_pct", "error"]
    return base + ["error"]


def main() -> None:
    st.set_page_config(
        page_title="Skrining LQ45",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    with st.sidebar:
        st.header("Tampilan")
        dark_mode = st.toggle(
            "Mode gelap",
            value=True,
            help="Default gelap (sesuai tema aplikasi). Matikan untuk tampilan terang.",
        )
        light_mode = not dark_mode
        st.divider()
        st.header("Pengaturan")
        view_mode = st.radio(
            "Tampilan baris",
            options=("top_n", "semua"),
            format_func=lambda x: "Top N (urut skor)" if x == "top_n" else f"Semua LQ45 ({MAX_STOCKS})",
            index=0,
        )
        top_n = 15
        if view_mode == "top_n":
            top_n = st.slider(
                "Jumlah teratas",
                min_value=5,
                max_value=MAX_STOCKS,
                value=min(15, MAX_STOCKS),
                step=1,
            )
        fundamentals = st.toggle(
            "Sertakan fundamental (PE, ROE, dividen — lebih lambat)",
            value=False,
        )
        compact = st.toggle(
            "Tampilan ringkas (cocok untuk layar kecil / HP)",
            value=False,
            help="Menyembunyikan vol, Sharpe, dan (tanpa fundamental) kolom PE/ROE/div.",
        )
        period_label = st.selectbox(
            "Periode data harga",
            options=list(PERIOD_OPTIONS.keys()),
            index=2,
        )
        price_period = PERIOD_OPTIONS[period_label]
        bypass_cache = st.button("Refresh data (abaikan cache 2 menit)")

    _inject_theme_and_table_css(light_mode=light_mode)

    st.title("Skrining LQ45")
    st.caption(
        "Ringkasan metrik dari Yahoo Finance — bukan saran investasi. "
        "Verifikasi ke emiten/IDX sebelum keputusan."
    )

    if bypass_cache:
        _cached_full_run.clear()

    with st.spinner("Mengunduh data dari Yahoo Finance…"):
        try:
            payload = _cached_full_run(
                use_fundamentals=fundamentals,
                price_period=price_period,
            )
        except Exception as e:
            st.error(_friendly_fetch_error(e))
            with st.expander("Detail teknis (untuk debug)"):
                st.exception(e)
            st.stop()

    df_full: pd.DataFrame = payload["table"]
    if view_mode == "top_n":
        df = df_full.iloc[: max(1, top_n)].copy()
    else:
        df = df_full.copy()

    fetched_at = datetime.fromisoformat(payload["fetched_at_iso"])
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=TZ_JAKARTA)

    pld_str = "—"
    if payload.get("price_last_date_iso"):
        pld = datetime.fromisoformat(payload["price_last_date_iso"])
        # Sama gaya tanggal dengan "Snapshot diambil" (tanpa jam — ini hanya tanggal penutupan harian)
        pld_str = pld.strftime("%d %b %Y")

    st.subheader("Status data")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            "Snapshot diambil",
            fetched_at.strftime("%d %b %Y, %H:%M"),
            help="Waktu server saat data ini di-cache (TTL 2 menit). Bukan harga real-time.",
        )
    with c2:
        st.metric(
            "Penutupan terakhir di data harga",
            pld_str,
            help="Tanggal bar terbaru dari seri historis Yahoo untuk unduhan ini (bukan jam transaksi live).",
        )
    with c3:
        st.metric("Sumber", "Yahoo Finance")
    st.caption(
        "Data IDX lewat Yahoo bisa **terlambat atau tidak lengkap**. "
        "Fundamental dari `info` Yahoo sering **perkiraan** — silang dengan laporan emiten bila putuskan investasi."
    )

    failed_codes = payload.get("failed_download_codes") or []
    if failed_codes:
        st.warning(
            "**Unduhan harga parsial:** seri untuk kode berikut tidak ikut di batch Yahoo — "
            + ", ".join(f"`{c}`" for c in failed_codes)
            + ". Metrik untuk kode itu bisa kosong atau diisi error; cek di sekuritas/IDX."
        )

    search_q = st.text_input(
        "Cari kode saham",
        placeholder="contoh: BBCA atau BBCA, BBRI",
        help="Pisahkan beberapa kode dengan koma/spasi. Kosong = tampilkan semua baris mode di atas.",
    )
    disp = _prepare_display_df(df, fundamentals=fundamentals)
    disp = _filter_by_code_query(disp, search_q)

    if disp.empty:
        st.info("Tidak ada baris yang cocok dengan pencarian. Kosongkan filter atau perbaiki kode.")
        st.stop()

    if "error" in disp.columns and disp["error"].isna().all():
        disp = disp.drop(columns=["error"])

    if compact:
        wanted = [c for c in _compact_column_order(fundamentals) if c in disp.columns]
        disp = disp[wanted]

    st.success(
        f"Tabel: **{len(disp)}** baris — periode unduhan harga `{price_period}` — skor relatif ke seluruh LQ45."
    )
    st.markdown(
        "**Tip:** hover **header kolom** (ⓘ) untuk pengingat singkat. Penjelasan lengkap di bagian bawah."
    )

    disp_cols = list(disp.columns)
    cfg = _build_column_config(disp_cols)

    row_h = min(720, max(120, 42 + len(disp) * 36))
    st.dataframe(
        _style_df(disp, dark_theme=not light_mode),
        column_config=cfg,
        use_container_width=True,
        hide_index=True,
        height=row_h,
    )

    with st.expander("Penjelasan kolom (baca saat lupa)", expanded=False):
        st.markdown(
            """
##### Selalu ada di tabel

**Kode**  
Kode saham di BEI (misalnya BBCA, BBRI). Satu kode = satu perusahaan tercatat.

**Skor**  
Angka 0–100: gabungan *peringkat* antar saham LQ45 menurut rumus program (momentum 1m/3m, volatilitas, Sharpe ~63 hari; jika *fundamental* aktif juga PE, ROE, dividen). Makin tinggi = makin “di atas” *relatif ke LQ45 lain*, bukan jaminan untung dan **bukan** saran beli/jual.

**Harga**  
Harga penutupan terakhir dari data Yahoo (rupiah per lembar). Bukan harga detik ini; bisa sedikit beda dengan aplikasi sekuritas. Harga per lembar saja tidak menjelaskan “murah/mahal” tanpa konteks laba/valuasi.

**Ret 1m %**  
Perubahan harga kira-kira **satu bulan** terakhir dalam persen. Positif = periode itu harga naik, negatif = turun. Ini *return* dari pergerakan harga, belum dipotong biaya transaksi/pajak.

**Ret 3m %**  
Sama konsepnya, untuk kira-kira **tiga bulan** terakhir — melihat tren sedikit lebih panjang.

**Vol tahunan %**  
Volatilitas yang diannualisasi dari fluktuasi harian (%). Angka besar = pergerakan lebih “gelisah”. Di skor, vol **rendah** sedikit diunggulkan; itu preferensi rumus, bukan kebenaran mutlak (banyak strategi justru cari vol tinggi).

**Sharpe ~63d**  
Perkiraan Sharpe dari ~63 hari perdagangan terakhir: membandingkan imbal hasil harian rata-rata dengan fluktuasi harian. Lebih tinggi = imbal relatif lebih besar dibanding “noise” (versi sederhana; bukan Sharpe portofolio pribadi Anda). Bisa negatif.

---

##### Hanya jika *Sertakan fundamental* di sidebar aktif

**PE trailing**  
P/E dari laba yang **sudah terjadi** (trailing). Angka lebih kecil sering dibaca “lebih murah vs laba”, tapi bisa juga karena ekspeksi buruk — cek laporan keuangan.

**PE forward**  
P/E memakai **perkiraan** laba ke depan (kalau Yahoo punya datanya). Sering tidak sempurna atau tidak update.

**ROE**  
Return on equity — seberapa besar laba dibanding ekuitas (biasanya ditampilkan sebagai desimal; bandingkan dengan konteks industri dan utang).

**Div yield %**  
Perkiraan yield dividen tahunan dari harga (%), dari Yahoo. Dividen masa depan bisa berubah atau dibatalkan.

---

##### Kolom Error (kalau muncul)

**Error**  
Kalau ada teks, data untuk baris itu **gagal atau tidak lengkap**. Jangan dipakai untuk membandingkan skor sebelum Anda cek manual di sekuritas/IDX.

---

*Ringkasan: baca tabel sebagai statistik kilat dari data publik, bukan rekomendasi investasi. Verifikasi ke emiten/IDX bila akan putuskan transaksi.*
            """
        )


if __name__ == "__main__":
    main()
