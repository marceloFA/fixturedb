# Limitations and Threats to Validity

## Sampling bias

The corpus is drawn from repositories with ≥ 100 GitHub stars. Popular,
actively maintained projects may exhibit higher test discipline than typical
open-source software. This is a known limitation in empirical software
engineering studies (Hamster study by Pan et al., 2025) which also used
star-based sampling to ensure sufficient test coverage. To mitigate this bias
and improve generalizability, the dataset records `star_tier` (`core` for ≥500
stars, `extended` for 100–499) and we recommend stratifying all analyses by tier.
This allows researchers to study both popular and emerging projects separately.

## Go language exclusion

Go repositories are excluded from the FixtureDB dataset due to unvalidated heuristic-based detection. The Go helper detector relies on pattern matching (non-test functions called from ≥2 test functions) without formal validation. Rather than publish unvalidated data, Go is not included (this exclusion avoids ~2.5% of data). All included languages (Python, Java, JavaScript, TypeScript) use syntax-based detection with high confidence (~95%+).

## Snapshot corpus

Each repository is captured at a single commit. The dataset does not support
longitudinal analyses of fixture evolution.

## Language coverage

This dataset covers four languages (Python, Java, JavaScript, TypeScript) with syntax-based detection across all. Ruby (RSpec), Kotlin, Scala, Rust, and Go are not included.

## Mock detection completeness

Mock detection uses regular expressions over source text. Framework versions
or unusual coding styles may produce false negatives. The `raw_source`
column is included in the SQLite file specifically so that researchers can
re-run or improve detection against the original fixture text.
