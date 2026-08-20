# backtest-cli

Biblioteca **open source** de 15 estrategias de inversión publicadas (papers y libros), implementadas fielmente en un mismo motor y backtesteadas en la terminal, con comisiones y sin maquillaje.

No es un asesor, no opera en ningún broker, no te dice qué comprar. Simula reglas sobre datos históricos y enseña números: rentabilidad, volatilidad, peor caída, comisiones.

```bash
python -m backtest list                      # la biblioteca y sus fuentes
python -m backtest run --strategy haa        # una estrategia vs su benchmark
python -m backtest compare --strategies all  # las 15 enfrentadas
```

## Por qué existe

Las colecciones serias de estrategias (Quantpedia, Allocate Smartly) son de pago y de código cerrado. Los motores open source (backtrader, vectorbt) vienen vacíos. Este repo junta las dos cosas: **estrategias famosas, con su cita, en código que cualquiera puede leer, ejecutar y auditar gratis**.

La pregunta que responde: *si yo hubiera seguido esta regla, con costes, ¿qué habría pasado frente a no hacer nada?*

## Requisitos

- Python 3.9+

```bash
cd backtest-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## La biblioteca (15 estrategias)

Cada una usa su universo de ETFs por defecto (el de su fuente) y decide el último día de mercado de cada mes, sin lookahead. Las carteras multi-activo se rebalancean mensualmente y **derivan** entre rebalanceos, como una cuenta real.

| Nombre | Idea en una frase | Fuente |
|---|---|---|
| `buyhold` | Compra SPY y no toques. El rival a batir. | Bogle (1999) |
| `60/40` | 60% acciones / 40% bonos, rebalanceo mensual | Clásico de la industria |
| `permanent` | 25% acciones, bonos largos, oro y efectivo | Harry Browne, *Fail-Safe Investing* (1999) |
| `allweather` | 30/40/15/7.5/7.5 acciones-bonos-oro-materias | Dalio vía Robbins, *Money* (2014) |
| `butterfly` | 20% × 5: grandes, small value, TLT, SHY, oro | PortfolioCharts, *Golden Butterfly* (2016) |
| `ivy` | 20% × 5 clases de activo globales, pasivo | Faber & Richardson, *The Ivy Portfolio* (2009) |
| `riskparity` | Cada activo pesa 1/volatilidad (sin apalancar) | Asness, Frazzini & Pedersen, FAJ (2012) |
| `voltarget` | Exposición = vol objetivo / vol realizada | Moreira & Muir, *Journal of Finance* (2017) |
| `sma` | Largo si SMA50 > SMA200; si no, efectivo | Regla de tendencia clásica |
| `gtaa5` | Cada activo dentro solo sobre su SMA 10 meses | Faber, JWM (2007), SSRN 962461 |
| `dualmom` | Mejor activo a 12m o refugio | Antonacci, JMS (2013), simplificado |
| `gem` | SPY vs EFA por momentum; si no hay, bonos | Antonacci, *Dual Momentum Investing* (2014) |
| `adm` | Momentum acelerado (1+3+6m) SPY vs SCZ | EngineeredPortfolio (2018) |
| `vaa` | Si un solo ofensivo falla, todo a defensivo | Keller & Keuning, SSRN 3002624 (2017) |
| `haa` | Dual momentum + canario de inflación (TIP) | Keller & Keuning, SSRN 4346906 (2023) |

`python -m backtest list` imprime esto mismo con los universos exactos.

## Resultados medidos (no prometidos)

Datos reales de ETFs, 10 bps de comisión por rotación, señales con warmup previo.

**2009–2026** (`compare --strategies all --start 2007-06-01 --measure-from 2009-01-05`):

| Estrategia | CAGR | Sharpe | Peor caída |
|---|---|---|---|
| buyhold SPY | **14.7%** | 0.86 | −33.7% |
| adm | 11.4% | 0.74 | −37.8% |
| haa | 10.1% | **0.91** | **−15.0%** |
| voltarget | 9.9% | 0.91 | −19.3% |
| 60/40 | 9.9% | 0.94 | −21.6% |
| sma50/200 | 9.7% | 0.72 | −33.7% |
| butterfly | 8.2% | 0.95 | −19.4% |
| gem | 8.1% | 0.57 | −33.7% |
| ivy | 8.2% | 0.68 | −26.2% |
| riskparity | 7.4% | 0.83 | −20.6% |
| permanent | 7.1% | 0.99 | −18.8% |
| dualmom | 6.7% | 0.46 | −30.2% |
| allweather | 6.6% | 0.83 | −23.7% |
| vaa | 5.7% | 0.50 | −22.3% |
| gtaa5 | 5.2% | 0.68 | −13.1% |

**2022, el año en que acciones y bonos cayeron a la vez:**

| Estrategia | 2022 |
|---|---|
| haa | **+3.0%** (la única en positivo) |
| gtaa5 | −6.3% |
| sma50/200 | −9.0% |
| buyhold SPY | −18.8% |
| adm | **−31.7%** |

Las dos lecciones que salen de la tabla, y que ningún vendedor de cursos te cuenta:

1. **En un mercado alcista de 17 años, nada batió a comprar y no tocar.** Todas las estrategias "listas" ganaron menos que SPY. Lo que compran a cambio es sufrir menos: HAA cayó −15% donde SPY cayó −34% (y −47% si incluyes 2008).
2. **La protección no es gratis ni universal.** ADM ganaba 11%/año a largo plazo y aun así se dejó un −32% en 2022. VAA, célebre en 2017, lleva una década floja. Publicarse sienta mal a las estrategias.

## Uso

```bash
# una estrategia contra su benchmark, con warmup separado de la medición
python -m backtest run --strategy haa --start 2007-06-01 --measure-from 2008-07-01

# test fuera de muestra: qué hizo HAA DESPUÉS de publicarse (feb 2023)
python -m backtest run --strategy haa --start 2022-01-01 --measure-from 2023-03-01

# enfrentar solo algunas
python -m backtest compare --strategies buyhold,60/40,haa,gtaa5 --start 2007-06-01 --measure-from 2009-01-05

# gráfico de curvas de equity
python -m backtest compare --strategies all --start 2007-06-01 --measure-from 2009-01-05 --plot equity.png
```

| Flag | Qué es |
|---|---|
| `--measure-from` | Las métricas empiezan aquí; lo anterior solo alimenta señales (warmup). Clave para tests fuera de muestra. |
| `--fee-bps` | Comisión en puntos básicos sobre lo rotado (10 = 0,10%). La deriva pasiva no paga. |
| `--capital` | Capital inicial (por defecto 10.000). |
| `--tickers` | Anula el universo por defecto en las estrategias que lo admiten (`buyhold`, `sma`, `dualmom`, `riskparity`, `gtaa5`, `voltarget`). |
| `--plot` | PNG de las curvas de equity. |

## Cómo añadir tu estrategia (la nº 16)

Abre `backtest/strategies.py`. Una estrategia es una clase que responde: *para cada día, ¿qué fracción del capital va a cada ticker?*

```python
class MiEstrategia(Strategy):
    name = "mia"
    cite = "Tu hipótesis, tu nombre, 2026"
    default_tickers = ["SPY", "TLT"]

    def weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        w["SPY"] = 0.5
        w["TLT"] = 0.5
        return w
```

Regístrala en `backtest/cli.py` (`STRATEGY_NAMES` y `_build_strategy`) y ya se backtestea con comisiones, benchmark y métricas gratis. Los helpers `_monthly_closes()` y `_hold_with_drift()` te dan señales mensuales y rebalanceo realista sin escribirlos de nuevo.

## Qué significan las métricas

- **CAGR** — rentabilidad anualizada.
- **Vol** — volatilidad anual.
- **Sharpe** — rentabilidad por unidad de riesgo (más alto, mejor *en el histórico*).
- **MaxDD** — peor caída desde un máximo. La cifra que duele.
- **Trades / Fees** — cuántas veces operas de verdad y qué te cuesta. El rebalanceo cuenta; la deriva pasiva no.

## Fidelidad del motor

- Los pesos del día t se aplican a los retornos de t+1: decidir con el cierre no es lookahead.
- Señales mensuales el último día de mercado del mes, como en los papers.
- Entre rebalanceos la cartera deriva con el mercado; la comisión se cobra solo sobre lo que de verdad se opera (diferencia contra los pesos derivados).
- Precios ajustados por dividendos y splits (auto-adjust de Yahoo).

## Limitaciones (léelas)

- Datos de Yahoo Finance: gratis, con huecos y sin calidad institucional. Los papers usan índices extendidos desde 1970; aquí mandan las fechas de creación de los ETFs (el periodo común empieza en 2008-2009).
- Sin slippage adicional ni impuestos.
- Un backtest se puede sobreajustar. La defensa aquí: reglas ajenas y publicadas (no optimizadas contra estos datos) y `--measure-from` para mirar qué pasó después de cada publicación.
- Esto **no es una recomendación de inversión**.

## Estructura

```text
backtest/
  data.py         descarga y cache de precios
  engine.py       simulación, comisiones, deriva
  metrics.py      CAGR, Sharpe, drawdown
  strategies.py   ← la biblioteca (15 estrategias con citas)
  cli.py          run / compare / list
```
