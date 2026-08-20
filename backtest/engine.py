from __future__ import annotations

import pandas as pd

from .metrics import summarize
from .strategies import Strategy


class BacktestResult:
    def __init__(
        self,
        strategy_name: str,
        equity: pd.Series,
        weights: pd.DataFrame,
        n_trades: int,
        fees_paid: float,
    ):
        self.strategy_name = strategy_name
        self.equity = equity
        self.weights = weights
        self.n_trades = n_trades
        self.fees_paid = fees_paid
        self.metrics = summarize(equity, n_trades, fees_paid)


def run_backtest(
    prices: pd.DataFrame,
    strategy: Strategy,
    capital: float = 10_000.0,
    fee_bps: float = 10.0,
    measure_from: str | None = None,
) -> BacktestResult:
    """Simula la estrategia.

    `fee_bps`: comisión en puntos básicos sobre el notional rotado
    (10 = 0,10% por cada lado de la operación).
    `measure_from`: las señales usan todo el histórico, pero las métricas
    y la curva de equity empiezan en esta fecha (útil para warmup y
    tests fuera de muestra).
    """
    weights = (
        strategy.weights(prices)
        .reindex(index=prices.index, columns=prices.columns)
        .fillna(0.0)
    )
    asset_rets = prices.pct_change().fillna(0.0)

    # Turnover real: lo que se opera es la diferencia entre los pesos
    # elegidos hoy y los pesos que la cartera de ayer tendría hoy por sí
    # sola (deriva de mercado). La deriva pasiva no paga comisión.
    prev = weights.shift(1)
    growth = 1.0 + (prev * asset_rets).sum(axis=1)
    drifted = prev.mul(1.0 + asset_rets).div(growth.where(growth > 0, 1.0), axis=0)
    turnover = (weights - drifted).abs().sum(axis=1).fillna(0.0)
    # primer día: entrar cuenta como turnover
    turnover.iloc[0] = weights.iloc[0].abs().sum()
    fee_rate = fee_bps / 10_000.0
    fee = turnover * fee_rate

    port_rets = (weights.shift(1).fillna(0.0) * asset_rets).sum(axis=1) - fee

    if measure_from is not None:
        cutoff = pd.Timestamp(measure_from)
        mask = port_rets.index >= cutoff
        if not mask.any():
            raise ValueError(f"measure_from {measure_from} deja la serie vacía")
        port_rets = port_rets[mask]
        turnover = turnover[mask]
        fee = fee[mask]

    equity = capital * (1 + port_rets).cumprod()
    n_trades = int((turnover > 1e-9).sum())
    fees_paid = float((fee * equity.shift(1).fillna(capital)).sum())

    return BacktestResult(
        strategy_name=strategy.name,
        equity=equity,
        weights=weights,
        n_trades=n_trades,
        fees_paid=fees_paid,
    )
