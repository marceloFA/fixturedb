# Setup and Requirements

## Prerequisites

- Python 3.11+
- Git (must be on `PATH`)
- A GitHub personal access token (free, no special scopes needed)

## Installation

```bash
git clone https://github.com/marcelofa/fixture-corpus.git
cd fixture-corpus

pip install -r requirements.txt

cp .env.example .env
# Open .env and set GITHUB_TOKEN=<your token>
# Get a token at: https://github.com/settings/tokens

python pipeline.py init
```

## Dependencies

| Package         | Purpose |
|-----------------|---------|
| `pydriller`     | Repository traversal and git metadata |
| `tree-sitter` + language bindings | AST parsing for fixture detection (all 6 languages) |
| `lizard`        | Cyclomatic complexity metrics and parameter count |
| `complexipy`    | SonarQube-standard cognitive complexity for Python (fast, Rust-based) |
| `requests`      | GitHub Search API client |
| `python-dotenv` | `.env` file loading |
| `pandas`        | CSV export and validation sample generation |
| `tqdm`          | Progress bars |
| `gitpython`     | Git operations in the cloner |
