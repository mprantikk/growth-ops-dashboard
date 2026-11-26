"""Synthetic event data for a B2B healthtech platform (seeded, reproducible).

Produces one row per customer site with its segment, signup and launch dates,
starting MRR, monthly MRR changes and churn date (if any).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

SEGMENTS = {
    # name: (new sites per month, base MRR, monthly churn prob, median launch days, expansion prob)
    "Enterprise": (2, 9000, 0.004, 62, 0.10),
    "Mid-market": (5, 3200, 0.010, 41, 0.08),
    "SMB": (11, 900, 0.025, 24, 0.05),
}
INSTALLED_BASE = {"Enterprise": 30, "Mid-market": 70, "SMB": 160}  # live sites on day one
CHURN_REASONS = ["Budget cut", "Switched vendor", "Practice closed", "Low adoption", "Merged / acquired"]
START = date(2024, 1, 1)
MONTHS = 24


@dataclass
class Site:
    site_id: int
    segment: str
    signup_month: int          # 0-based month index; -1 = installed base
    launch_days: int
    launch_month: int
    mrr_by_month: dict[int, float] = field(default_factory=dict)
    churn_month: int | None = None
    churn_reason: str | None = None


def month_label(i: int) -> str:
    y, m = divmod(START.month - 1 + i, 12)
    return f"{START.year + y}-{m + 1:02d}"


def generate(seed: int = 2026) -> list[Site]:
    rng = random.Random(seed)
    sites: list[Site] = []
    sid = 0

    def simulate(site: Site, mrr: float, churn_p: float, exp_p: float, slow: bool) -> None:
        for m in range(site.launch_month, MONTHS):
            if rng.random() < churn_p * (2.0 if slow else 1.0):
                site.churn_month = m
                site.churn_reason = rng.choice(CHURN_REASONS)
                return
            if rng.random() < exp_p:
                mrr *= rng.uniform(1.05, 1.25)   # expansion: more providers / modules
            elif rng.random() < 0.02:
                mrr *= rng.uniform(0.8, 0.95)    # contraction
            site.mrr_by_month[m] = round(mrr, 2)

    # customers already live when the period starts (launched before Jan 2024)
    for seg, n in INSTALLED_BASE.items():
        _, base, churn_p, launch_med, exp_p = SEGMENTS[seg]
        for _ in range(n):
            sid += 1
            site = Site(sid, seg, -1, int(rng.gauss(launch_med, launch_med * 0.25)), 0)
            simulate(site, base * rng.uniform(0.7, 1.6), churn_p, exp_p, False)
            sites.append(site)

    for month in range(MONTHS):
        growth = 1 + month * 0.03  # sales capacity grows over time
        for seg, (new, base, churn_p, launch_med, exp_p) in SEGMENTS.items():
            for _ in range(max(0, round(rng.gauss(new * growth, new ** 0.5)))):
                sid += 1
                # onboarding gets faster as the launch playbook matures
                days = max(7, int(rng.gauss(launch_med * (1 - month * 0.018), launch_med * 0.2)))
                launch = month + (days + 15) // 30
                site = Site(sid, seg, month, days, launch)
                slow = days > launch_med * 1.3
                simulate(site, base * rng.uniform(0.7, 1.4), churn_p, exp_p, slow)
                sites.append(site)
    return sites
