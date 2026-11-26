"""Growth-operations metrics computed from site-level data.

Definitions follow common SaaS usage:
    MRR             sum of live sites' monthly recurring revenue
    NRR (12m)       MRR today from sites that were live 12 months ago / their MRR then
    Gross churn     MRR lost to churned sites in the month / MRR at start of month
    Time to launch  days from signup to go-live, median per signup month
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from .generate import MONTHS, SEGMENTS, Site, generate, month_label


def mrr_by_segment(sites: list[Site]) -> dict[str, list[float]]:
    out = {seg: [0.0] * MONTHS for seg in SEGMENTS}
    for s in sites:
        for m, v in s.mrr_by_month.items():
            out[s.segment][m] += v
    return {k: [round(x) for x in v] for k, v in out.items()}


def nrr(sites: list[Site], month: int, lookback: int = 12) -> float | None:
    base_m = month - lookback
    if base_m < 0:
        return None
    cohort = [s for s in sites if base_m in s.mrr_by_month]
    if len(cohort) < 10:
        return None
    start = sum(s.mrr_by_month[base_m] for s in cohort)
    now = sum(s.mrr_by_month.get(month, 0.0) for s in cohort)
    return round(100 * now / start, 1) if start else None


def gross_churn_pct(sites: list[Site], month: int) -> float | None:
    if month == 0:
        return None
    start = sum(s.mrr_by_month.get(month - 1, 0.0) for s in sites)
    lost = sum(s.mrr_by_month.get(month - 1, 0.0) for s in sites if s.churn_month == month)
    return round(100 * lost / start, 2) if start else None


def launches_by_month(sites: list[Site]) -> dict[str, list[int]]:
    out = {seg: [0] * MONTHS for seg in SEGMENTS}
    for s in sites:
        if s.signup_month >= 0 and s.launch_month < MONTHS:   # new sites only, not the installed base
            out[s.segment][s.launch_month] += 1
    return out


def median_launch_days(sites: list[Site]) -> dict[str, list[float | None]]:
    """Median signup-to-launch days per segment and signup quarter (new sites only)."""
    out = {}
    for seg in SEGMENTS:
        by_q = defaultdict(list)
        for s in sites:
            if s.segment == seg and s.signup_month >= 0:
                by_q[s.signup_month // 3].append(s.launch_days)
        out[seg] = [round(statistics.median(by_q[q])) if by_q[q] else None for q in range(MONTHS // 3)]
    return out


def overall_median_launch(sites: list[Site], months: range) -> float:
    return statistics.median(s.launch_days for s in sites if s.signup_month in months)


def churn_reasons(sites: list[Site]) -> dict[str, int]:
    return dict(Counter(s.churn_reason for s in sites if s.churn_reason).most_common())


def cohort_retention(sites: list[Site], cohort_months: int = 12, horizon: int = 12) -> list[dict]:
    """Logo retention by launch-quarter cohort: share of sites still live N months after launch."""
    rows = []
    for q in range(0, cohort_months, 3):
        cohort = [s for s in sites if s.signup_month >= 0 and q <= s.launch_month < q + 3]
        if not cohort:
            continue
        cells = []
        for k in range(0, horizon + 1, 3):
            eligible = [s for s in cohort if s.launch_month + k < MONTHS]
            if not eligible:
                cells.append(None)
                continue
            alive = sum(1 for s in eligible if s.churn_month is None or s.churn_month > s.launch_month + k)
            cells.append(round(100 * alive / len(eligible), 1))
        rows.append({"cohort": f"{month_label(q)[:4]} Q{q // 3 + 1}", "sites": len(cohort), "retention": cells})
    return rows


def build(sites: list[Site]) -> dict:
    last = MONTHS - 1
    mrr = mrr_by_segment(sites)
    total_mrr = [sum(v[m] for v in mrr.values()) for m in range(MONTHS)]
    live_sites = sum(1 for s in sites if last in s.mrr_by_month)
    launch = median_launch_days(sites)
    launch_now = overall_median_launch(sites, range(last - 2, last + 1))
    launch_prior = overall_median_launch(sites, range(last - 14, last - 11))
    return {
        "months": [month_label(m) for m in range(MONTHS)],
        "segments": list(SEGMENTS),
        "kpis": {
            "arr": total_mrr[last] * 12,
            "arr_yoy_pct": round(100 * (total_mrr[last] / total_mrr[last - 12] - 1), 1),
            "nrr_pct": nrr(sites, last),
            "gross_churn_pct": gross_churn_pct(sites, last),
            "avg_gross_churn_12m_pct": round(statistics.mean(gross_churn_pct(sites, m) for m in range(last - 11, last + 1)), 2),
            "live_sites": live_sites,
            "median_launch_days": launch_now,
            "median_launch_days_prior_year": launch_prior,
        },
        "mrr_by_segment": mrr,
        "nrr_by_month": [nrr(sites, m) for m in range(MONTHS)],
        "gross_churn_by_month": [gross_churn_pct(sites, m) for m in range(MONTHS)],
        "launches_by_segment": launches_by_month(sites),
        "quarters": [f"{month_label(q * 3)[:4]} Q{q % 4 + 1}" for q in range(MONTHS // 3)],
        "median_launch_days_by_segment": launch,
        "churn_reasons": churn_reasons(sites),
        "cohort_retention": cohort_retention(sites),
    }


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "data" / "metrics.json"
    data = build(generate())
    out.write_text(json.dumps(data, indent=1))
    k = data["kpis"]
    print(f"ARR ${k['arr']:,.0f} (+{k['arr_yoy_pct']}% YoY) | NRR {k['nrr_pct']}% | "
          f"live sites {k['live_sites']} | launch {k['median_launch_days']}d")


if __name__ == "__main__":
    main()
