# Running the Pipeline

## Full run (recommended)

```bash
# All languages, full targets (~4,000 repos searched, ~2,400 expected to survive)
python pipeline.py run

# Single language, full target
python pipeline.py run --language python

# Smoke test with a small batch
python pipeline.py run --language python --max 20
```

The `run` command executes all phases in order: init → search → clone → extract → classify.

## Running phases independently

```bash
# Phase 1: discover repos (writes to DB, no cloning yet)
python pipeline.py search --language java --max 1000

# Phase 2: clone a batch of discovered repos
python pipeline.py clone --language java --batch 50

# Phase 3: extract fixtures from all cloned repos
python pipeline.py extract --language java

# Phase 4: assign domain labels
python pipeline.py classify

# Check current counts
python pipeline.py stats
```

Running phases independently is useful for incremental collection — you can
run `clone` and `extract` in a loop, processing repos in batches without
re-running the search phase.

## Validation (for the paper's precision/recall numbers)

```bash
# Step 1: generate a stratified sample (50 fixtures per language)
python pipeline.py validate --sample 50

# Step 2: open validation/sample_<timestamp>.csv
# For each row, read 'raw_source' and set 'is_true_fixture' to 1 or 0

# Step 3: compute precision
python pipeline.py validate --compute validation/sample_<timestamp>.csv
```

## Export (Zenodo deposit)

```bash
python pipeline.py export --version 1.0
# Produces: export/fixturedb_v1.0_<date>.zip
```
