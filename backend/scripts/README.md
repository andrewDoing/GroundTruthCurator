# Scripts

This folder contains helper scripts used during development and data ops.

## KB CSV import workflow

Use these two scripts to prepare and import a KB CSV into the Ground Truth Curator API.

1) Clean the CSV (drops Japanese descriptions and rows with non-empty "Added question?"):

```bash
uv run python scripts/clean_kb_csv.py \
  --input 'scripts/AI_Generated_Questions_500_v1_0820-1545_dataset(Sheet1).csv' \
  --output /tmp/kb_cleaned.csv
```

2) Import the cleaned CSV (prefix CS to `article`, build KB article URLs, POST in batches):

```bash
uv run python scripts/import_kb_csv.py \
  --input /tmp/kb_cleaned.csv \
  --base-url http://localhost:8000 \
  --api-prefix /v1 \
  --dataset kb \
  --kb-base-url https://example.com \
  --approve \
  --batch-size 200
```

Authentication:
- Bearer token header:

```bash
uv run python scripts/import_kb_csv.py --input /tmp/kb_cleaned.csv \
  --base-url http://localhost:8000 --api-prefix /v1 --dataset kb --kb-base-url https://example.com --approve \
  --bearer-token '<your_token_here>'
```

- Dev convenience header (used when AUTH_MODE=dev):

```bash
uv run python scripts/import_kb_csv.py --input /tmp/kb_cleaned.csv \
  --base-url http://localhost:8000 --api-prefix /v1 --dataset kb --kb-base-url https://example.com --approve \
  --user-id importer
```

Dry-run (no POSTs; preview first 3 payloads):

```bash
uv run python scripts/import_kb_csv.py --input /tmp/kb_cleaned.csv --dry-run
```

Notes:
- Cleaning detects Japanese using a Unicode-range heuristic (Hiragana/Katakana/Kanji) in `description` and removes such rows; also removes rows where "Added question?" is non-empty.
- Import normalizes the `article` field to start with `CS` and constructs references like `https://example.com/support/article/CS32540` using `--kb-base-url`. It uses `generated_question` (fallback: `description`) as the synthetic question and posts to `/v1/ground-truths` in batches.
- API errors are printed per batch, plus a final deduplicated summary.
