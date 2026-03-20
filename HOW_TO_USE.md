# On your machine:
cp .env.example .env
# edit .env, paste your token from github.com/settings/tokens

# Smoke test with 10 Python repos
python pipeline.py run --language python --max 10

# Check what was collected
python pipeline.py stats

# When happy with the smoke test, run the full collection
python pipeline.py run --max 200

The recommended order once you have data is: run → classify → validate --sample 50 → fill the CSV manually → validate --compute <file> → export --version 1.0. That last step gives you the zip file to upload to Zenodo.