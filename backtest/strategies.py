"""Biblioteca de estrategias publicadas.

Cada estrategia es una clase con:
- `name`: identificador en la CLI.
- `cite`: fuente publicada (paper, libro o web de referencia).
- `default_tickers`: universo de ETFs que necesita.
- `weights()`: para cada día, qué fracción del capital va a cada ticker.

Convención temporal: los pesos del día t se aplican a los retornos del
día t+1 (lo hace el motor), así que decidir con el cierre de t no es
lookahead. Las señales mensuales se calculan el último día de mercado
de cada mes, como en los papers originales.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

import pandas as pd


# ---------------------------------------------------------------------------
# utilidades comunes
# ---------------------------------------------------------------------------

def _month_end_mask(index: pd.DatetimeIndex) -> pd.Series:
    """True en el último día de mercado de cada mes."""
    months = pd.Series(index.month, index=index)
    years = pd.Series(index.year, index=index)
    mask = (months != months.shift(-1)) | (years != years.shift(-1))
    mask.iloc[-1] = True
    return mask


def _require(prices: pd.DataFrame, tickers: list[str], name: str) -> None:
    missing = [t for t in tickers if t not in prices.columns]
    if missing:
        raise ValueError(f"{name}: faltan tickers {', '.join(missing)}")


def _hold_with_drift(prices: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Convierte pesos objetivo (solo en fechas de rebalanceo) en pesos diarios.

    Entre rebalanceos la cartera NO se retoca: los pesos derivan con el
    mercado, como en una cuenta real. La parte no invertida es efectivo
    (retorno 0). Esto evita el error clásico de asumir rebalanceo diario
    gratuito.
    """
    rets = prices.pct_change().fillna(0.0)
    w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    current = pd.Series(0.0, index=prices.columns)
    target_dates = set(targets.index)

    for i, ts in enumerate(prices.index):
        if i > 0:
            r = rets.iloc[i]
            growth = 1.0 + float((current * r).sum())
            if growth > 0:
                current = current * (1.0 + r) / growth
        if ts in target_dates:
            row = targets.loc[ts]
            if not bool(row.isna().any()):
                current = row.astype(float).copy()
        w.iloc[i] = current

    return w


def _monthly_closes(prices: pd.DataFrame) -> pd.DataFrame:
    """Cierres del último día de mercado de cada mes."""
    return prices.loc[prices.index[_month_end_mask(prices.index)]]


# ---------------------------------------------------------------------------
# base
# ---------------------------------------------------------------------------

class Strategy(ABC):
    """Implementa `weights()` y ya tienes un algoritmo nuevo.

    Debe devolver un DataFrame con el mismo índice que `prices` y una
    columna por ticker. Cada fila suma ~1 (o menos si hay efectivo).
    Las columnas que la estrategia no use pueden quedarse a 0: el motor
    reindexa contra el universo descargado.
    """

    name: str = "strategy"
    cite: str = ""
    default_tickers: list[str] = ["SPY"]

    @abstractmethod
    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# benchmarks y carteras estáticas
# ---------------------------------------------------------------------------

class BuyAndHold(Strategy):
    """Compras un ticker y no tocas. El rival a batir."""

    name = "buyhold"
    cite = "Benchmark clásico (Bogle, 'Common Sense on Mutual Funds', 1999)"

    def __init__(self, ticker: str = "SPY"):
        self.ticker = ticker.upper()
        self.default_tickers = [self.ticker]

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, [self.ticker], self.name)
        w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        w[self.ticker] = 1.0
        return w


class StaticAllocation(Strategy):
    """Cartera fija rebalanceada cada fin de mes, con deriva entre medias."""

    allocation: dict[str, float] = {}

    def __init__(self) -> None:
        self.default_tickers = list(self.allocation)

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, self.default_tickers, self.name)
        dates = prices.index[_month_end_mask(prices.index)]
        first = prices.index[0]
        if first not in dates:
            dates = dates.insert(0, first)
        targets = pd.DataFrame(0.0, index=dates, columns=prices.columns)
        for ticker, weight in self.allocation.items():
            targets[ticker] = weight
        return _hold_with_drift(prices, targets)


class SixtyForty(StaticAllocation):
    """60% acciones USA / 40% bonos agregados."""

    name = "60/40"
    cite = "Cartera balanceada clásica (Markowitz 1952; estándar de la industria)"
    allocation = {"SPY": 0.60, "AGG": 0.40}


class PermanentPortfolio(StaticAllocation):
    """25% acciones, 25% bonos largos, 25% oro, 25% efectivo."""

    name = "permanent"
    cite = "Harry Browne, 'Fail-Safe Investing' (1999)"
    allocation = {"SPY": 0.25, "TLT": 0.25, "GLD": 0.25, "SHY": 0.25}


class AllWeather(StaticAllocation):
    """Aproximación pública de la cartera All Weather de Bridgewater."""

    name = "allweather"
    cite = "Ray Dalio, vía Tony Robbins 'Money: Master the Game' (2014)"
    allocation = {"SPY": 0.30, "TLT": 0.40, "IEF": 0.15, "GLD": 0.075, "DBC": 0.075}


class GoldenButterfly(StaticAllocation):
    """20% × 5: grandes, small value, bonos largos, bonos cortos, oro."""

    name = "butterfly"
    cite = "Tyler, PortfolioCharts.com 'Golden Butterfly' (2016)"
    allocation = {"SPY": 0.20, "IWN": 0.20, "TLT": 0.20, "SHY": 0.20, "GLD": 0.20}


class Ivy5(StaticAllocation):
    """20% × 5 clases de activo globales, sin timing (versión pasiva)."""

    name = "ivy"
    cite = "Faber & Richardson, 'The Ivy Portfolio' (2009)"
    allocation = {"SPY": 0.20, "EFA": 0.20, "IEF": 0.20, "VNQ": 0.20, "DBC": 0.20}


# ---------------------------------------------------------------------------
# riesgo gestionado
# ---------------------------------------------------------------------------

class InverseVolatility(Strategy):
    """Risk parity simple: cada activo pesa 1/volatilidad (sin apalancar).

    Versión sin apalancamiento del principio de paridad de riesgo.
    """

    name = "riskparity"
    cite = "Asness, Frazzini & Pedersen, 'Leverage Aversion and Risk Parity', FAJ (2012)"

    def __init__(self, universe: list[str] | None = None, vol_window: int = 63):
        self.universe = universe or ["SPY", "TLT", "GLD", "DBC"]
        self.vol_window = vol_window
        self.default_tickers = list(self.universe)

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, self.universe, self.name)
        sub = prices[self.universe]
        vol = sub.pct_change().rolling(self.vol_window).std()

        dates = prices.index[_month_end_mask(prices.index)]
        rows = {}
        for ts in dates:
            v = vol.loc[ts]
            if bool(v.isna().any()) or bool((v <= 0).any()):
                continue
            inv = 1.0 / v
            alloc = pd.Series(0.0, index=prices.columns)
            alloc[self.universe] = inv / inv.sum()
            rows[ts] = alloc
        if not rows:
            raise ValueError(f"{self.name}: histórico insuficiente para la volatilidad")
        targets = pd.DataFrame(rows).T.reindex(columns=prices.columns).fillna(0.0)
        return _hold_with_drift(prices, targets)


class VolTarget(Strategy):
    """Gestión de volatilidad: exposición = vol objetivo / vol realizada.

    Si el mercado se agita, reduces posición; si está tranquilo, la subes
    (sin apalancar: tope 100%). El resto queda en efectivo.
    """

    name = "voltarget"
    cite = "Moreira & Muir, 'Volatility-Managed Portfolios', Journal of Finance (2017)"

    def __init__(
        self,
        ticker: str = "SPY",
        target_vol: float = 0.10,
        window: int = 21,
        cap: float = 1.0,
    ):
        self.ticker = ticker.upper()
        self.target_vol = target_vol
        self.window = window
        self.cap = cap
        self.default_tickers = [self.ticker]

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, [self.ticker], self.name)
        rets = prices[self.ticker].pct_change()
        realized = rets.rolling(self.window).std() * math.sqrt(252)

        dates = prices.index[_month_end_mask(prices.index)]
        rows = {}
        for ts in dates:
            rv = realized.loc[ts]
            if pd.isna(rv) or rv <= 0:
                continue
            alloc = pd.Series(0.0, index=prices.columns)
            alloc[self.ticker] = min(self.cap, self.target_vol / rv)
            rows[ts] = alloc
        if not rows:
            raise ValueError(f"{self.name}: histórico insuficiente")
        targets = pd.DataFrame(rows).T.reindex(columns=prices.columns).fillna(0.0)
        return _hold_with_drift(prices, targets)


# ---------------------------------------------------------------------------
# seguimiento de tendencia / momentum
# ---------------------------------------------------------------------------

class SmaCross(Strategy):
    """Largo si la SMA rápida > SMA lenta (días); si no, efectivo."""

    name = "sma"
    cite = "Regla clásica de tendencia; variante diaria de Faber (2007)"

    def __init__(self, fast: int = 50, slow: int = 200, ticker: str = "SPY"):
        if fast >= slow:
            raise ValueError("fast debe ser menor que slow")
        self.fast = fast
        self.slow = slow
        self.ticker = ticker.upper()
        self.name = f"sma{fast}/{slow}"
        self.default_tickers = [self.ticker]

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, [self.ticker], self.name)
        series = prices[self.ticker]
        signal = (series.rolling(self.fast).mean() > series.rolling(self.slow).mean())
        w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        w[self.ticker] = signal.astype(float)
        return w


class GTAA5(Strategy):
    """Faber GTAA-5: cada activo dentro si cierra sobre su SMA de 10 meses.

    5 clases de activo, 20% cada una; la que está bajo su media se queda
    en efectivo ese mes.
    """

    name = "gtaa5"
    cite = "Faber, 'A Quantitative Approach to Tactical Asset Allocation', JWM (2007), SSRN 962461"

    def __init__(self, universe: list[str] | None = None, sma_months: int = 10):
        self.universe = universe or ["SPY", "EFA", "IEF", "VNQ", "DBC"]
        self.sma_months = sma_months
        self.default_tickers = list(self.universe)

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, self.universe, self.name)
        monthly = _monthly_closes(prices)[self.universe]
        sma = monthly.rolling(self.sma_months).mean()
        share = 1.0 / len(self.universe)

        rows = {}
        for ts in monthly.index:
            if bool(sma.loc[ts].isna().any()):
                continue
            above = monthly.loc[ts] > sma.loc[ts]
            alloc = pd.Series(0.0, index=prices.columns)
            for asset in self.universe:
                if bool(above[asset]):
                    alloc[asset] = share
            rows[ts] = alloc
        if not rows:
            raise ValueError(f"{self.name}: histórico insuficiente para la SMA de 10 meses")
        targets = pd.DataFrame(rows).T.reindex(columns=prices.columns).fillna(0.0)
        return _hold_with_drift(prices, targets)


class DualMomentum(Strategy):
    """Momentum dual simplificado: mejor activo de riesgo a 12 meses o defensivo."""

    name = "dualmom"
    cite = "Antonacci, 'Risk Premia Harvesting Through Dual Momentum', JMS (2013), simplificado"

    def __init__(
        self,
        risk: list[str] | None = None,
        defensive: str = "BIL",
        lookback: int = 252,
    ):
        self.risk = risk or ["SPY", "EEM", "TLT"]
        self.defensive = defensive.upper()
        self.lookback = lookback
        self.default_tickers = list(dict.fromkeys(self.risk + [self.defensive]))

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, self.default_tickers, self.name)
        mom = prices[self.risk].pct_change(self.lookback)
        rebalance = _month_end_mask(prices.index)

        w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        current = pd.Series(0.0, index=prices.columns)
        current[self.defensive] = 1.0

        for i in range(len(prices.index)):
            row = mom.iloc[i]
            if bool(rebalance.iloc[i]) and not bool(row.isna().any()):
                best = row.idxmax()
                current = pd.Series(0.0, index=prices.columns)
                if row[best] > 0:
                    current[best] = 1.0
                else:
                    current[self.defensive] = 1.0
            w.iloc[i] = current

        return w


class GEM(Strategy):
    """Global Equities Momentum (Antonacci).

    Cada mes: si el retorno a 12 meses de SPY supera al de las letras
    (BIL), invierte en el mejor entre SPY y EFA; si no, en bonos (AGG).
    """

    name = "gem"
    cite = "Antonacci, 'Dual Momentum Investing' (McGraw-Hill, 2014)"

    def __init__(
        self,
        us: str = "SPY",
        intl: str = "EFA",
        bonds: str = "AGG",
        tbill: str = "BIL",
        lookback_months: int = 12,
    ):
        self.us, self.intl, self.bonds, self.tbill = us, intl, bonds, tbill
        self.lookback = lookback_months
        self.default_tickers = [us, intl, bonds, tbill]

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, self.default_tickers, self.name)
        monthly = _monthly_closes(prices)[self.default_tickers]
        mom = monthly.pct_change(self.lookback)

        rows = {}
        for ts in monthly.index:
            row = mom.loc[ts]
            if bool(row.isna().any()):
                continue
            alloc = pd.Series(0.0, index=prices.columns)
            if row[self.us] > row[self.tbill]:
                winner = self.us if row[self.us] >= row[self.intl] else self.intl
                alloc[winner] = 1.0
            else:
                alloc[self.bonds] = 1.0
            rows[ts] = alloc
        if not rows:
            raise ValueError(f"{self.name}: histórico insuficiente (12 meses)")
        targets = pd.DataFrame(rows).T.reindex(columns=prices.columns).fillna(0.0)
        return _hold_with_drift(prices, targets)


class AcceleratingDualMomentum(Strategy):
    """ADM: momentum acelerado (1+3+6 meses) entre SPY y small caps
    internacionales; si ambos van mal, bonos largos.
    """

    name = "adm"
    cite = "EngineeredPortfolio.com, 'Accelerating Dual Momentum' (2018)"

    def __init__(self, us: str = "SPY", intl: str = "SCZ", defensive: str = "TLT"):
        self.us, self.intl, self.defensive = us, intl, defensive
        self.default_tickers = [us, intl, defensive]

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, self.default_tickers, self.name)
        monthly = _monthly_closes(prices)[[self.us, self.intl]]
        score = sum(monthly.pct_change(k) for k in (1, 3, 6))

        rows = {}
        for ts in monthly.index:
            row = score.loc[ts]
            if bool(row.isna().any()):
                continue
            alloc = pd.Series(0.0, index=prices.columns)
            best = row.idxmax()
            alloc[best if row[best] > 0 else self.defensive] = 1.0
            rows[ts] = alloc
        if not rows:
            raise ValueError(f"{self.name}: histórico insuficiente (6 meses)")
        targets = pd.DataFrame(rows).T.reindex(columns=prices.columns).fillna(0.0)
        return _hold_with_drift(prices, targets)


def _score_13612w(monthly: pd.DataFrame) -> pd.DataFrame:
    """Momentum 13612W de Keller: media ponderada (12, 4, 2, 1) de los
    retornos a 1, 3, 6 y 12 meses."""
    return (
        12 * monthly.pct_change(1)
        + 4 * monthly.pct_change(3)
        + 2 * monthly.pct_change(6)
        + 1 * monthly.pct_change(12)
    )


class VAA(Strategy):
    """Vigilant Asset Allocation G4 (Keller & Keuning 2017).

    Momentum 13612W. Si LOS CUATRO ofensivos son positivos, 100% al mejor
    ofensivo; si uno solo falla, 100% al mejor defensivo. Muy nervioso a
    propósito: es el detector de humo más sensible de la familia Keller.
    """

    name = "vaa"
    cite = "Keller & Keuning, 'Breadth Momentum and VAA', SSRN 3002624 (2017)"

    def __init__(
        self,
        offensive: list[str] | None = None,
        defensive: list[str] | None = None,
    ):
        self.offensive = offensive or ["SPY", "EFA", "EEM", "AGG"]
        self.defensive = defensive or ["LQD", "IEF", "SHY"]
        self.default_tickers = list(dict.fromkeys(self.offensive + self.defensive))

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, self.default_tickers, self.name)
        monthly = _monthly_closes(prices)[self.default_tickers]
        score = _score_13612w(monthly)

        rows = {}
        for ts in monthly.index:
            row = score.loc[ts]
            if bool(row.isna().any()):
                continue
            alloc = pd.Series(0.0, index=prices.columns)
            off = row[self.offensive]
            if bool((off > 0).all()):
                alloc[off.idxmax()] = 1.0
            else:
                alloc[row[self.defensive].idxmax()] = 1.0
            rows[ts] = alloc
        if not rows:
            raise ValueError(f"{self.name}: histórico insuficiente (12 meses)")
        targets = pd.DataFrame(rows).T.reindex(columns=prices.columns).fillna(0.0)
        return _hold_with_drift(prices, targets)


class HAA(Strategy):
    """Hybrid Asset Allocation (Keller & Keuning, SSRN 4346906, feb 2023).

    Reglas exactas del paper, cada último día de mes:
    1. Momentum "13612U" de cada activo: media de los retornos totales
       a 1, 3, 6 y 12 meses.
    2. Canario (TIP): si su momentum es <= 0, el 100% va al mejor activo
       defensivo (BIL o IEF, el de mayor momentum).
    3. Si el canario es positivo: top 4 de los 8 ofensivos por momentum,
       25% cada uno; los que tengan momentum <= 0 se sustituyen por el
       mejor defensivo.
    4. Se mantiene hasta el siguiente fin de mes.
    """

    name = "haa"
    cite = "Keller & Keuning, 'Hybrid Asset Allocation', SSRN 4346906 (2023)"

    def __init__(
        self,
        offensive: list[str] | None = None,
        defensive: list[str] | None = None,
        canary: str = "TIP",
        top_n: int = 4,
    ):
        self.offensive = offensive or ["SPY", "IWM", "EFA", "EEM", "VNQ", "DBC", "IEF", "TLT"]
        self.defensive = defensive or ["BIL", "IEF"]
        self.canary = canary.upper()
        self.top_n = top_n
        if len(self.offensive) < top_n:
            raise ValueError(f"HAA necesita al menos {top_n} activos ofensivos")
        self.default_tickers = list(
            dict.fromkeys(self.offensive + self.defensive + [self.canary])
        )

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        _require(prices, self.default_tickers, self.name)
        monthly = _monthly_closes(prices)[self.default_tickers]
        # 13612U: media (sin ponderar) de retornos a 1, 3, 6 y 12 meses
        mom = sum(monthly.pct_change(k) for k in (1, 3, 6, 12)) / 4.0

        rows = {}
        for ts in monthly.index:
            row = mom.loc[ts]
            if bool(row.isna().any()):
                continue
            rows[ts] = self._allocate(row, prices.columns)
        if not rows:
            raise ValueError(f"{self.name}: histórico insuficiente (12 meses)")
        targets = pd.DataFrame(rows).T.reindex(columns=prices.columns).fillna(0.0)
        return _hold_with_drift(prices, targets)

    def _allocate(self, mom_row: pd.Series, columns: pd.Index) -> pd.Series:
        alloc = pd.Series(0.0, index=columns)
        best_def = mom_row[self.defensive].idxmax()

        if mom_row[self.canary] <= 0:
            alloc[best_def] = 1.0
            return alloc

        top = mom_row[self.offensive].nlargest(self.top_n).index
        share = 1.0 / self.top_n
        for asset in top:
            target = asset if mom_row[asset] > 0 else best_def
            alloc[target] += share
        return alloc
