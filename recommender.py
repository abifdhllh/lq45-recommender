#!/usr/bin/env python3
"""
Skrining saham LQ45 memakai data Yahoo Finance (yfinance).
Menghitung skor gabungan dari metrik teknikal (harga) dan opsional fundamental.

Penggunaan:
  .venv/bin/python recommender.py --top 10
  .venv/bin/python recommender.py --top 15 --fundamentals --json

Ini BUKAN saran investasi berizin — hanya alat kuantitatif berbasis data publik.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from constituents import LQ45_CODES, yahoo_symbols


@dataclass(frozen=True)
class RunResult:
    """Hasil skrining penuh (semua kode LQ45), sudah diurut skor."""

    table: pd.DataFrame
    failed_download_codes: list[str]
    price_last_date: pd.Timestamp | None


def _failed_symbols_to_codes(symbols: list[str]) -> list[str]:
    return sorted({s.replace(".JK", "").strip() for s in symbols if s})


def _panel_last_date(panel: pd.DataFrame) -> pd.Timestamp | None:
    if panel is None or panel.empty:
        return None
    idx = panel.index
    if not isinstance(idx, pd.DatetimeIndex) or len(idx) == 0:
        return None
    return pd.Timestamp(idx.max())


def run_with_meta(
    use_fundamentals: bool,
    price_period: str,
) -> RunResult:
    """
    Jalankan pipeline skrining untuk seluruh LQ45; kembalikan tabel penuh + metadata data harga.
    """
    panel, failed_dl = fetch_price_panel(period=price_period)
    failed_codes = _failed_symbols_to_codes(failed_dl)
    price_last = _panel_last_date(panel)

    fund = None
    if use_fundamentals:
        fund = fetch_fundamentals_parallel(LQ45_CODES)

    df = build_metrics(panel, fund)
    df = add_composite_score(df, use_fundamentals=use_fundamentals)
    if failed_dl:
        sys.stderr.write(f"Peringatan: unduhan parsial gagal untuk: {failed_dl}\n")
    return RunResult(
        table=df,
        failed_download_codes=failed_codes,
        price_last_date=price_last,
    )


def _to_float(v: Any) -> float:
    if v is None:
        return np.nan
    try:
        x = float(v)
        return x if not np.isnan(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _sanitize_pe(v: Any) -> float:
    """Yahoo kadang mengembalikan PE tidak masuk akal; buang outlier."""
    x = _to_float(v)
    if np.isnan(x) or x <= 0 or x > 500:
        return np.nan
    return x


def _sanitize_div_yield(v: Any) -> float:
    """Normalisasi ke desimal (0.05 = 5%). Jika > 1, anggap persen."""
    x = _to_float(v)
    if np.isnan(x) or x < 0:
        return np.nan
    if x > 1.0:
        x = x / 100.0
    if x > 0.35:
        return np.nan
    return x


def _safe_pct_return(series: pd.Series) -> float | None:
    if series is None or len(series) < 2:
        return None
    clean = series.dropna()
    if len(clean) < 2:
        return None
    a, b = float(clean.iloc[0]), float(clean.iloc[-1])
    if a == 0:
        return None
    return (b / a - 1.0) * 100.0


def _annualized_vol(daily_returns: pd.Series) -> float | None:
    if daily_returns is None or len(daily_returns) < 10:
        return None
    std = float(daily_returns.std())
    if std == 0 or np.isnan(std):
        return None
    return std * np.sqrt(252) * 100.0


def _sharpe(daily_returns: pd.Series) -> float | None:
    if daily_returns is None or len(daily_returns) < 20:
        return None
    mu = float(daily_returns.mean())
    sd = float(daily_returns.std())
    if sd == 0 or np.isnan(sd):
        return None
    return (mu / sd) * np.sqrt(252)


def fetch_price_panel(period: str = "6mo") -> tuple[pd.DataFrame, list[str]]:
    """Unduh harga penutupan untuk semua simbol; kembalikan wide DataFrame + daftar gagal."""
    symbols = yahoo_symbols()
    failed: list[str] = []
    try:
        raw = yf.download(
            symbols,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
    except Exception as e:
        raise RuntimeError(f"Gagal unduh harga batch: {e}") from e

    closes: dict[str, pd.Series] = {}
    if len(symbols) == 1:
        sym = symbols[0]
        if "Close" in raw.columns:
            closes[sym.replace(".JK", "")] = raw["Close"]
        else:
            failed.append(sym)
    else:
        for sym in symbols:
            code = sym.replace(".JK", "")
            try:
                if sym in raw.columns.get_level_values(0):
                    s = raw[sym]["Close"]
                else:
                    s = raw["Close"][sym]
                closes[code] = s
            except Exception:
                failed.append(sym)

    if not closes:
        raise RuntimeError("Tidak ada data harga yang terbaca.")
    panel = pd.DataFrame(closes)
    return panel, failed


def _one_ticker_info(code: str) -> tuple[str, dict[str, Any], str | None]:
    sym = f"{code}.JK"
    err = None
    data: dict[str, Any] = {}
    try:
        t = yf.Ticker(sym)
        inf = t.info or {}
        if not inf:
            err = "info kosong"
        data["trailing_pe"] = _sanitize_pe(inf.get("trailingPE"))
        data["forward_pe"] = _sanitize_pe(inf.get("forwardPE"))
        data["roe"] = inf.get("returnOnEquity")
        data["dividend_yield"] = _sanitize_div_yield(inf.get("dividendYield"))
        data["debt_to_equity"] = inf.get("debtToEquity")
        data["market_cap"] = inf.get("marketCap")
        fi = getattr(t, "fast_info", None)
        if hasattr(fi, "get"):
            if data.get("market_cap") is None:
                data["market_cap"] = fi.get("market_cap")
            if "last_price" not in data:
                data["last_price"] = fi.get("last_price") or fi.get("lastPrice")
    except Exception as e:
        err = str(e)
    return code, data, err


def fetch_fundamentals_parallel(
    codes: list[str], max_workers: int = 6, pause_s: float = 0.12
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_one_ticker_info, c): c for c in codes}
        for fut in as_completed(futs):
            code, data, err = fut.result()
            data["_err"] = err
            out[code] = data
            time.sleep(pause_s)
    return out


def _empty_metric_row(code: str, error: str) -> dict[str, Any]:
    return {
        "code": code,
        "error": error,
        "last_price": np.nan,
        "ret_1m_pct": np.nan,
        "ret_3m_pct": np.nan,
        "vol_ann_pct": np.nan,
        "sharpe_63d": np.nan,
        "trailing_pe": np.nan,
        "forward_pe": np.nan,
        "roe": np.nan,
        "dividend_yield": np.nan,
        "debt_to_equity": np.nan,
        "market_cap": np.nan,
    }


def build_metrics(
    panel: pd.DataFrame, fund: dict[str, dict[str, Any]] | None
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for code in LQ45_CODES:
        if code not in panel.columns:
            rows.append(_empty_metric_row(code, "tidak ada seri harga"))
            continue
        s = panel[code].dropna()
        if len(s) < 30:
            rows.append(_empty_metric_row(code, "data harga terlalu pendek"))
            continue

        last = float(s.iloc[-1])
        r1 = _safe_pct_return(s.iloc[-22:]) if len(s) >= 22 else None
        r3 = _safe_pct_return(s.iloc[-66:]) if len(s) >= 66 else _safe_pct_return(s)

        dr = s.pct_change().dropna()
        vol = _annualized_vol(dr.iloc[-20:]) if len(dr) >= 20 else _annualized_vol(dr)
        sharpe = _sharpe(dr.iloc[-63:]) if len(dr) >= 63 else _sharpe(dr)

        row: dict[str, Any] = {
            "code": code,
            "error": None,
            "last_price": last,
            "ret_1m_pct": r1,
            "ret_3m_pct": r3,
            "vol_ann_pct": vol,
            "sharpe_63d": sharpe,
            "trailing_pe": np.nan,
            "forward_pe": np.nan,
            "roe": np.nan,
            "dividend_yield": np.nan,
            "debt_to_equity": np.nan,
            "market_cap": np.nan,
        }
        if fund and code in fund:
            fd = fund[code]
            for k, src in (
                ("trailing_pe", "trailing_pe"),
                ("forward_pe", "forward_pe"),
                ("roe", "roe"),
                ("dividend_yield", "dividend_yield"),
                ("debt_to_equity", "debt_to_equity"),
                ("market_cap", "market_cap"),
            ):
                row[k] = _to_float(fd.get(src))
            lp = fd.get("last_price")
            if lp is not None and not (isinstance(lp, float) and np.isnan(lp)):
                row["last_price"] = _to_float(lp)
        rows.append(row)

    return pd.DataFrame(rows)


def _pct_rank(series: pd.Series, higher_is_better: bool) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    valid = s.notna()
    out = pd.Series(np.nan, index=s.index, dtype=float)
    if valid.sum() < 2:
        return out
    r = s[valid].rank(pct=True)
    if higher_is_better:
        out.loc[valid] = r * 100.0
    else:
        out.loc[valid] = (1.0 - r) * 100.0
    return out


def add_composite_score(
    df: pd.DataFrame,
    use_fundamentals: bool,
    w_mom1: float = 0.2,
    w_mom3: float = 0.25,
    w_vol: float = 0.15,
    w_sharpe: float = 0.2,
    w_pe: float = 0.1,
    w_roe: float = 0.1,
    w_div: float = 0.1,
) -> pd.DataFrame:
    """Skor 0–100: rata-rata tertimbang dari persentil lintas emiten."""
    out = df.copy()
    ok = out["error"].isna() if "error" in out.columns else pd.Series(True, index=out.index)
    pe_col = out["forward_pe"].where(out["forward_pe"].notna(), out["trailing_pe"])

    parts: list[tuple[pd.Series, float]] = [
        (_pct_rank(out["ret_1m_pct"].where(ok), True), w_mom1),
        (_pct_rank(out["ret_3m_pct"].where(ok), True), w_mom3),
        (_pct_rank(out["vol_ann_pct"].where(ok), False), w_vol),
        (_pct_rank(out["sharpe_63d"].where(ok), True), w_sharpe),
    ]
    if use_fundamentals:
        pe_for_rank = pe_col.astype(float)
        bad_pe = (pe_for_rank <= 0) | pe_for_rank.isna()
        pe_rank = _pct_rank(pe_for_rank.where(ok).mask(bad_pe), False)
        parts.extend(
            [
                (pe_rank, w_pe),
                (_pct_rank(out["roe"].where(ok).astype(float), True), w_roe),
                (_pct_rank(out["dividend_yield"].where(ok).astype(float), True), w_div),
            ]
        )

    total_w = sum(w for _, w in parts)
    score = pd.Series(np.nan, index=out.index, dtype=float)
    mask_ok = ok.to_numpy()
    sub = pd.Series(0.0, index=out.index)
    for ser, w in parts:
        sub = sub + ser.fillna(50.0) * (w / total_w)
    score.loc[mask_ok] = sub.loc[mask_ok]
    out["score"] = score
    return out.sort_values("score", ascending=False, na_position="last")


def run(
    top: int,
    use_fundamentals: bool,
    price_period: str,
) -> pd.DataFrame:
    r = run_with_meta(use_fundamentals=use_fundamentals, price_period=price_period)
    n = max(1, min(top, len(r.table)))
    return r.table.iloc[:n].copy()


def main() -> None:
    p = argparse.ArgumentParser(description="Skor & ranking LQ45 dari Yahoo Finance")
    p.add_argument("--top", type=int, default=10, help="Jumlah baris teratas")
    p.add_argument(
        "--fundamentals",
        action="store_true",
        help="Ambil PE/ROE/dividen (lebih lambat, banyak request ke Yahoo)",
    )
    p.add_argument(
        "--period",
        default="6mo",
        help="Periode unduh harga yfinance (default: 6mo)",
    )
    p.add_argument("--json", action="store_true", help="Keluaran JSON ke stdout")
    args = p.parse_args()

    try:
        df = run(
            top=max(1, args.top),
            use_fundamentals=args.fundamentals,
            price_period=args.period,
        )
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)

    cols = [
        "code",
        "score",
        "error",
        "last_price",
        "ret_1m_pct",
        "ret_3m_pct",
        "vol_ann_pct",
        "sharpe_63d",
    ]
    if args.fundamentals:
        cols.extend(["trailing_pe", "forward_pe", "roe", "dividend_yield"])
    show = df[[c for c in cols if c in df.columns]]

    if args.json:
        records = []
        for _, r in show.iterrows():
            rec = {k: (None if pd.isna(v) else v) for k, v in r.items()}
            if args.fundamentals and rec.get("dividend_yield") is not None:
                rec["dividend_yield_pct"] = round(rec["dividend_yield"] * 100, 2)
            records.append(rec)
        print(json.dumps(records, indent=2))
    else:
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 180)
        disp = show.copy()
        if args.fundamentals and "dividend_yield" in disp.columns:
            disp["div_pct"] = disp["dividend_yield"].apply(
                lambda v: np.nan if pd.isna(v) else v * 100.0
            )
            disp = disp.drop(columns=["dividend_yield"])
        print(disp.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
        print(
            "\nCatatan: skor = kombinasi persentil momentum, volatilitas (lebih rendah lebih baik), "
            "Sharpe 63 hari terakhir"
            + (" + PE/ROE/dividen bila --fundamentals." if args.fundamentals else "."),
        )
        if args.fundamentals:
            print(
                "Kolom div_pct = perkiraan yield dividen tahunan (%) dari Yahoo; data bisa salah/tunda."
            )
        print("Data dari Yahoo Finance; verifikasi ke emiten/IDX sebelum keputusan investasi.")


if __name__ == "__main__":
    main()
