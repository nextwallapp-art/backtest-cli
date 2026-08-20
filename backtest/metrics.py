from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0 or equity.iloc[0] <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def annual_vol(returns: pd.Series) -> float:
    if returns.std(ddof=0) == 0:
        return 0.0
    return float(returns.std(ddof=0) * np.sqrt(TRADING_DAYS))


def sharpe(returns: pd.Series, rf: float = 0.0) -> float:
    excess = returns - rf / TRADING_DAYS
    vol = annual_vol(excess)
    if vol == 0:
        return 0.0
    return float(excess.mean() * TRADING_DAYS / vol)


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1
    return float(dd.min())


def summarize(equity: pd.Series, n_trades: int, fees_paid: float) -> dict[str, float | int]:
    rets = equity.pct_change().dropna()
    return {
        "CAGR": cagr(equity),
        "Vol": annual_vol(rets),
        "Sharpe": sharpe(rets),
        "MaxDD": max_drawdown(equity),
        "Trades": n_trades,
        "Fees": fees_paid,
        "Final": float(equity.iloc[-1]),
    }


def format_table(rows: dict[str, dict[str, float | int]]) -> str:
    headers = ["Strategy", "CAGR", "Vol", "Sharpe", "MaxDD", "Trades", "Fees", "Final $"]
    lines = ["  ".join(f"{h:>10}" for h in headers)]
    lines.append("-" * len(lines[0]))
    for name, m in rows.items():
        lines.append(
            "  ".join(
                [
                    f"{name:>10.10}",
                    f"{m['CAGR']:>10.1%}",
                    f"{m['Vol']:>10.1%}",
                    f"{m['Sharpe']:>10.2f}",
                    f"{m['MaxDD']:>10.1%}",
                    f"{int(m['Trades']):>10d}",
                    f"{m['Fees']:>10.2f}",
                    f"{m['Final']:>10.2f}",
                ]
            )
        )
    return "\n".join(lines)
