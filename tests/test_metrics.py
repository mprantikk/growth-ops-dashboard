import json
from pathlib import Path

from pipeline.generate import MONTHS, Site, generate
from pipeline.metrics import build, cohort_retention, gross_churn_pct, nrr


def _site(sid, mrr, churn=None, seg="SMB", launch=0, signup=0):
    s = Site(sid, seg, signup, 20, launch, churn_month=churn)
    s.mrr_by_month = dict(mrr)
    return s


def test_nrr_counts_expansion_and_churn_from_base_cohort_only():
    base = [_site(i, {0: 100, 12: 110}) for i in range(9)]          # +10% each
    churned = _site(99, {0: 100}, churn=5)                            # lost entirely
    newbie = _site(100, {12: 5000}, launch=12, signup=11)             # must be ignored
    # cohort at month 0 = 10 sites, MRR 1000; at month 12 = 9 * 110 = 990
    assert nrr(base + [churned, newbie], 12) == 99.0


def test_nrr_needs_a_full_lookback_and_a_real_cohort():
    assert nrr([_site(1, {0: 100, 12: 100})], 5) is None
    assert nrr([_site(1, {0: 100, 12: 100})], 12) is None   # cohort under 10 sites


def test_gross_churn_is_lost_mrr_over_starting_mrr():
    sites = [_site(1, {0: 300, 1: 300}), _site(2, {0: 100}, churn=1)]
    assert gross_churn_pct(sites, 1) == 25.0
    assert gross_churn_pct(sites, 0) is None


def test_cohort_retention_month_zero_counts_everyone_alive():
    sites = [_site(i, {m: 1 for m in range(MONTHS)}) for i in range(4)] + [_site(9, {0: 1, 1: 1}, churn=2)]
    row = cohort_retention(sites, cohort_months=3)[0]
    assert row["sites"] == 5
    assert row["retention"][0] == 100.0
    assert row["retention"][1] == 80.0


def test_build_output_is_complete_and_consistent():
    data = build(generate())
    assert len(data["months"]) == MONTHS
    for seg in data["segments"]:
        assert len(data["mrr_by_segment"][seg]) == MONTHS
    total_last = sum(v[-1] for v in data["mrr_by_segment"].values())
    assert data["kpis"]["arr"] == total_last * 12
    assert data["kpis"]["median_launch_days"] < data["kpis"]["median_launch_days_prior_year"]


def test_committed_json_matches_pipeline():
    committed = json.loads((Path(__file__).parent.parent / "data" / "metrics.json").read_text())
    assert committed == json.loads(json.dumps(build(generate())))
