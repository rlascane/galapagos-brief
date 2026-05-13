"""
fetch_market_data.py -- Busca dados historicos via yfinance.
Gera build/market_YYYY-MM-DD.json com series YTD para cada ativo.
Roda antes de generate_brief.py no workflow.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

TZ_BR = ZoneInfo("America/Sao_Paulo")

TICKERS = [
    {"ticker": "^BVSP",    "name": "Ibovespa",  "unit": "pts",     "decimals": 0},
    {"ticker": "BRL=X",    "name": "USD/BRL",   "unit": "R$",      "decimals": 4},
    {"ticker": "^GSPC",    "name": "S&P 500",   "unit": "pts",     "decimals": 0},
    {"ticker": "^IXIC",    "name": "Nasdaq",    "unit": "pts",     "decimals": 0},
    {"ticker": "EURUSD=X", "name": "EUR/USD",   "unit": "USD",     "decimals": 4},
    {"ticker": "GC=F",     "name": "Ouro",      "unit": "US$/oz",  "decimals": 0},
    {"ticker": "BZ=F",     "name": "Brent",     "unit": "US$/bbl", "decimals": 2},
]


def fetch_one(info: dict, start: date, end: date) -> dict | None:
    try:
        hist = yf.Ticker(info["ticker"]).history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
        )
    except Exception as e:
        print(f"    erro ao buscar {info['ticker']}: {e}", file=sys.stderr)
        return None

    if hist.empty:
        return None

    closes = hist["Close"].dropna()
    if len(closes) < 2:
        return None

    dates = [d.strftime("%Y-%m-%d") for d in closes.index]
    values = closes.tolist()
    base = values[0]

    # Serie YTD indexada em % a partir de 1 jan
    pct_series = [round((v / base - 1) * 100, 3) for v in values]

    current = values[-1]
    ytd_pct = pct_series[-1]

    # MTD: primeiro fechamento do mes atual
    today = end - timedelta(days=1)
    mtd_base_idx = next(
        (i for i, d in enumerate(closes.index)
         if d.month == today.month and d.year == today.year),
        None,
    )
    if mtd_base_idx is not None and mtd_base_idx > 0:
        mtd_pct = round((current / values[mtd_base_idx - 1] - 1) * 100, 2)
    elif mtd_base_idx == 0:
        mtd_pct = round(ytd_pct, 2)
    else:
        mtd_pct = None

    # 5D
    n = min(5, len(values) - 1)
    five_d_pct = round((values[-1] / values[-(n + 1)] - 1) * 100, 2) if n > 0 else None

    dec = info["decimals"]
    return {
        "ticker":      info["ticker"],
        "name":        info["name"],
        "unit":        info["unit"],
        "decimals":    dec,
        "current":     round(current, dec),
        "ytd_pct":     round(ytd_pct, 2),
        "mtd_pct":     mtd_pct,
        "five_d_pct":  five_d_pct,
        "dates":       dates,
        "pct_series":  pct_series,
    }


def main() -> int:
    now_br = datetime.now(TZ_BR)
    today = now_br.date()
    year_start = date(today.year, 1, 1)
    fetch_end = today + timedelta(days=1)  # inclui hoje

    print(f"[fetch_market_data] YTD {year_start} -> {today}")

    assets = []
    for info in TICKERS:
        print(f"  {info['ticker']:12s}", end=" ")
        data = fetch_one(info, year_start, fetch_end)
        if data:
            assets.append(data)
            mtd = f"{data['mtd_pct']:+.1f}% MTD" if data["mtd_pct"] is not None else ""
            print(f"{data['current']}  YTD {data['ytd_pct']:+.1f}%  {mtd}")
        else:
            print("sem dados")

    if not assets:
        print("AVISO: nenhum dado disponivel. Continuando sem graficos.", file=sys.stderr)
        # Nao falha o workflow -- graficos sao opcionais
        assets = []

    out_dir = Path(__file__).resolve().parent.parent / "build"
    out_dir.mkdir(exist_ok=True)
    date_iso = today.strftime("%Y-%m-%d")
    out_file = out_dir / f"market_{date_iso}.json"
    out_file.write_text(
        json.dumps({"date_iso": date_iso, "assets": assets}, ensure_ascii=False, indent=2)
    )
    print(f"[fetch_market_data] {len(assets)} ativos salvos em {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
