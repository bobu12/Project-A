"""Monte-Carlo competition simulator.

Answers the real question - "should I increase lot size / capital to hit 18x?" -
quantitatively, using the REAL backtested trade distribution rather than hope.

Method:
  * Express each backtested trade as an R-multiple = pnl / risk_$ (how many
    risk-units it won or lost). This is the strategy's true outcome shape.
  * A "competition" = `n_trades` trades. Each trade risks fraction `f` of
    CURRENT equity, so equity *= (1 + f * R). This compounds, exactly like
    sizing up your lots.
  * Run many competitions per `f` and measure: P(ever reach 18x) and
    P(blow up, i.e. equity <= 20% of start), plus the median outcome.

The point it makes: increasing `f` (bigger lots) raises P(18x) AND P(ruin)
together. If mean(R) <= 0, the distribution drifts to ruin - size cannot fix a
missing edge. Capital cancels out entirely (everything is a multiple of start).
"""
import numpy as np


def r_multiples(trades):
    """Convert Trade objects to R-multiples (pnl / risk)."""
    return np.array([t.pnl / t.risk_usd for t in trades if t.risk_usd > 0])


def simulate(r_samples, f, n_trades, target_mult=18.0, ruin_mult=0.2,
             n_sims=20000, seed=0):
    rng = np.random.default_rng(seed)
    reached = ruined = 0
    finals = np.empty(n_sims)
    n = len(r_samples)
    for s in range(n_sims):
        eq = 1.0
        peak = 1.0
        draws = r_samples[rng.integers(0, n, n_trades)]
        for R in draws:
            eq *= (1.0 + f * R)
            if eq <= 0:
                eq = 0.0
                break
            peak = max(peak, eq)
        finals[s] = eq
        if peak >= target_mult:
            reached += 1
        if eq <= ruin_mult:
            ruined += 1
    return {
        "risk_per_trade_%": round(100 * f, 1),
        "P(reach 18x)_%": round(100 * reached / n_sims, 2),
        "P(blow up)_%": round(100 * ruined / n_sims, 2),
        "median_final_x": round(float(np.median(finals)), 2),
    }


def sweep(r_samples, n_trades, f_grid=None, **kw):
    if f_grid is None:
        f_grid = [0.01, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50]
    return [simulate(r_samples, f, n_trades, **kw) for f in f_grid]
