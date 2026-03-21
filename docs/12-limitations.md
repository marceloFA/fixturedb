# Limitations and Threats to Validity

## Sampling bias

The corpus is drawn from repositories with ≥ 100 GitHub stars. Popular,
actively maintained projects may exhibit higher test discipline than typical
open-source software. A prior study from our institution (Coelho et al.,
MSR 2020) shows that star-based sampling over-represents JavaScript projects
and web frameworks; this is why `star_tier` is recorded and why we recommend
stratifying analyses by tier.

## Go heuristic precision

The `go_helper` detector is heuristic-based. TODO: insert false-positive rate
from manual validation once completed.

## Snapshot corpus

Each repository is captured at a single commit. The dataset does not support
longitudinal analyses of fixture evolution.

## Language coverage

This release covers five language variants. Ruby (RSpec), C# (NUnit/xUnit),
and Rust (built-in test module) are not included.

## Mock detection completeness

Mock detection uses regular expressions over source text. Framework versions
or unusual coding styles may produce false negatives. The `raw_source`
column is included in the SQLite file specifically so that researchers can
re-run or improve detection against the original fixture text.
