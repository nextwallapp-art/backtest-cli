from __future__ import annotations

import argparse
from pathlib import Path

from .data import download_prices
from .engine import run_backtest
from .metrics import format_table
from .strategies import (
    GEM,
    GTAA5,
    HAA,
    VAA,
    AcceleratingDualMomentum,
    AllWeather,
    BuyAndHold,
    DualMomentum,
    GoldenButterfly,
    InverseVolatility,
    Ivy5,
    PermanentPortfolio,
    SixtyForty,
    SmaCross,
    Strategy,
    VolTarget,
)

# Orden canónico de la biblioteca: de más pasiva a más táctica.
STRATEGY_NAMES = [
    "buyhold",
    "60/40",
    "permanent",
    "allweather",
    "butterfly",
    "ivy",
    "riskparity",
    "voltarget",
    "sma",
    "gtaa5",
    "dualmom",
    "gem",
    "adm",
    "vaa",
    "haa",
]


def _parse_tickers(raw: str) -> list[str]:
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
    if not tickers:
        raise SystemExit("Indica al menos un ticker.")
    return tickers


def _build_strategy(name: str, args: argparse.Namespace) -> Strategy:
    custom = _parse_tickers(args.tickers) if args.tickers else None

    if name == "buyhold":
        return BuyAndHold(ticker=custom[0] if custom else "SPY")
    if name == "60/40":
        return SixtyForty()
    if name == "permanent":
        return PermanentPortfolio()
    if name == "allweather":
        return AllWeather()
    if name == "butterfly":
        return GoldenButterfly()
    if name == "ivy":
        return Ivy5()
    if name == "riskparity":
        return InverseVolatility(universe=custom)
    if name == "voltarget":
        return VolTarget(
            ticker=custom[0] if custom else "SPY",
            target_vol=args.target_vol,
        )
    if name == "sma":
        return SmaCross(fast=args.fast, slow=args.slow, ticker=custom[0] if custom else "SPY")
    if name == "gtaa5":
        return GTAA5(universe=custom)
    if name == "dualmom":
        if custom and len(custom) >= 2:
            return DualMomentum(risk=custom[:-1], defensive=custom[-1], lookback=args.lookback)
        return DualMomentum(lookback=args.lookback)
    if name == "gem":
        return GEM()
    if name == "adm":
        return AcceleratingDualMomentum()
    if name == "vaa":
        return VAA()
    if name == "haa":
        return HAA(
            offensive=_parse_tickers(args.offensive),
            defensive=_parse_tickers(args.defensive),
            canary=args.canary,
            top_n=args.top_n,
        )
    raise SystemExit(f"Estrategia desconocida: {name}. Usa `backtest list`.")


def _disclaimer(prices, measure_from, fee_bps) -> None:
    start = measure_from or prices.index[0].date()
    print()
    print(f"Medido: {start} → {prices.index[-1].date()}  |  fee {fee_bps} bps")
    print("No es una recomendación de inversión. Solo simulación histórica.")


def cmd_run(args: argparse.Namespace) -> None:
    strategy = _build_strategy(args.strategy, args)
    tickers = list(strategy.default_tickers)
    bench_ticker = tickers[0]
    if bench_ticker != "SPY" and "SPY" not in tickers:
        pass  # el benchmark es el primer ticker del universo de la estrategia

    prices = download_prices(tickers, start=args.start, end=args.end)
    result = run_backtest(
        prices,
        strategy,
        capital=args.capital,
        fee_bps=args.fee_bps,
        measure_from=args.measure_from,
    )
    rows = {result.strategy_name: result.metrics}
    equities = {result.strategy_name: result.equity}

    if args.strategy != "buyhold":
        bench = run_backtest(
            prices,
            BuyAndHold(ticker=bench_ticker),
            capital=args.capital,
            fee_bps=args.fee_bps,
            measure_from=args.measure_from,
        )
        label = f"bh:{bench_ticker}"
        rows[label] = bench.metrics
        equities[label] = bench.equity

    print()
    print(format_table(rows))
    print(f"\nEstrategia: {strategy.cite}")
    print(f"Tickers: {', '.join(tickers)}")
    _disclaimer(prices, args.measure_from, args.fee_bps)

    if args.plot:
        _save_plot(equities, args.plot, result.strategy_name)


def cmd_compare(args: argparse.Namespace) -> None:
    names = (
        STRATEGY_NAMES
        if args.strategies.strip().lower() == "all"
        else [n.strip().lower() for n in args.strategies.split(",") if n.strip()]
    )
    unknown = [n for n in names if n not in STRATEGY_NAMES]
    if unknown:
        raise SystemExit(f"Estrategias desconocidas: {', '.join(unknown)}. Usa `backtest list`.")

    strategies = [_build_strategy(n, args) for n in names]

    union: list[str] = []
    for strat in strategies:
        for t in strat.default_tickers:
            if t not in union:
                union.append(t)

    prices = download_prices(union, start=args.start, end=args.end)

    rows = {}
    equities = {}
    for strat in strategies:
        result = run_backtest(
            prices,
            strat,
            capital=args.capital,
            fee_bps=args.fee_bps,
            measure_from=args.measure_from,
        )
        rows[result.strategy_name] = result.metrics
        equities[result.strategy_name] = result.equity

    print()
    print(format_table(rows))
    print(f"\nUniverso común: {', '.join(union)}")
    print(
        "Nota: el periodo empieza cuando existe el ETF más joven del universo común."
    )
    _disclaimer(prices, args.measure_from, args.fee_bps)

    if args.plot:
        _save_plot(equities, args.plot, "Equity curves")


def cmd_list(args: argparse.Namespace) -> None:
    print()
    print("Biblioteca de estrategias (todas con reglas publicadas):\n")
    for name in STRATEGY_NAMES:
        strat = _build_strategy(name, args)
        tickers = ", ".join(strat.default_tickers)
        print(f"  {name:<11} {strat.cite}")
        print(f"  {'':<11} universo: {tickers}\n")
    print("Uso: backtest run --strategy <nombre> | backtest compare --strategies all")


def _save_plot(equities: dict, path: str, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(path)
    for name, eq in equities.items():
        eq.plot(label=name)
    plt.legend()
    plt.title(title)
    plt.ylabel("Equity ($)")
    plt.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=120)
    plt.close()
    print(f"Gráfico: {out}")


def _add_common(sp: argparse.ArgumentParser) -> None:
    sp.add_argument(
        "--tickers",
        default=None,
        help="Anula el universo por defecto (solo estrategias que lo admiten).",
    )
    sp.add_argument("--start", default="2007-06-01")
    sp.add_argument("--end", default=None)
    sp.add_argument("--capital", type=float, default=10_000)
    sp.add_argument(
        "--fee-bps",
        type=float,
        default=10.0,
        help="Comisión en bps sobre el notional rotado (10 = 0,10%).",
    )
    sp.add_argument("--fast", type=int, default=50)
    sp.add_argument("--slow", type=int, default=200)
    sp.add_argument("--lookback", type=int, default=252)
    sp.add_argument("--target-vol", type=float, default=0.10, help="(voltarget)")
    sp.add_argument(
        "--offensive",
        default="SPY,IWM,EFA,EEM,VNQ,DBC,IEF,TLT",
        help="(haa) Universo ofensivo del paper.",
    )
    sp.add_argument("--defensive", default="BIL,IEF", help="(haa)")
    sp.add_argument("--canary", default="TIP", help="(haa)")
    sp.add_argument("--top-n", type=int, default=4, help="(haa)")
    sp.add_argument("--plot", default=None, help="Ruta PNG para la curva de equity.")
    sp.add_argument(
        "--measure-from",
        default=None,
        help="Las métricas empiezan aquí; el histórico anterior solo alimenta señales (warmup).",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="backtest",
        description="Biblioteca open source de estrategias publicadas, backtesteadas en tu terminal.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Ejecuta una estrategia contra su benchmark")
    _add_common(run)
    run.add_argument("--strategy", choices=STRATEGY_NAMES, default="buyhold")
    run.set_defaults(func=cmd_run)

    compare = sub.add_parser("compare", help="Enfrenta varias estrategias (o todas)")
    _add_common(compare)
    compare.add_argument(
        "--strategies",
        default="all",
        help="Lista separada por comas, o 'all' (por defecto).",
    )
    compare.set_defaults(func=cmd_compare)

    lst = sub.add_parser("list", help="Muestra la biblioteca con sus fuentes")
    _add_common(lst)
    lst.set_defaults(func=cmd_list)
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
