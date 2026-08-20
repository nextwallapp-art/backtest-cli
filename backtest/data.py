from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


def download_prices(
    tickers: list[str],
    start: str,
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Descarga precios de cierre ajustados. Una columna por ticker."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{'-'.join(tickers)}_{start}_{end or 'today'}.csv"
    cache_file = CACHE_DIR / key

    if use_cache and cache_file.exists():
        prices = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        return prices.sort_index()

    raw = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if raw.empty:
        raise RuntimeError(
            f"No se pudieron descargar datos para {tickers}. "
            "Comprueba tickers y conexión."
        )

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            prices = raw["Close"].copy()
        else:
            prices = raw.xs("Close", axis=1, level=0)
    else:
        prices = raw[["Close"]].copy()
        prices.columns = tickers[:1]

    prices = prices.dropna(how="all").ffill().dropna(how="any")
    if prices.empty:
        raise RuntimeError("La serie de precios quedó vacía tras limpiar huecos.")

    if isinstance(prices, pd.Series):
        prices = prices.to_frame(name=tickers[0])

    prices.columns = [str(c) for c in prices.columns]
    ordered = [t for t in tickers if t in prices.columns]
    missing = [t for t in tickers if t not in prices.columns]
    if missing:
        raise RuntimeError(f"Sin datos para: {', '.join(missing)}")
    prices = prices[ordered]
    prices.to_csv(cache_file)
    return prices.sort_index()
