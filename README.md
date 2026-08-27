# TTB Label Verifier

Checks alcoholic beverage label images against expected brand name, ABV%,
and presence of the U.S. government warning text — using a vision-capable
Claude model to read the label instead of a traditional OCR engine.

## Why vision instead of Tesseract/OCR

Traditional OCR engines segment the image into text regions first and then
recognize characters region-by-region. That works fine for uniform,
high-contrast text but struggles with:
- stylized/display fonts (script, small caps, serif display faces)
- low-contrast printing on textured or colored backgrounds
- text that isn't in one clean, evenly-lit block

A vision-capable model reads the whole image holistically, the way a person
would, so font style and background texture don't trip it up the way they
trip up Tesseract.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY (get one at https://console.anthropic.com/)
```

Run it:

```bash
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 in your browser.

## Using it

**Quick check (single image):** upload one label photo, optionally type in
the brand/ABV you expect, and get an instant pass/fail per field.

**Batch check (CSV + zip):** upload a CSV of expected values and a zip of
the label images it refers to. A CSV row's `filename` must match (by
basename, case-insensitively) a file inside the zip — folders inside the
zip are fine, only the filename has to match.

CSV format (see `sample_data/sample_expected.csv`):

```csv
filename,expected_brand,expected_abv
wine1.jpg,Resolution,14.9
wine2.jpg,Some Other Brand,13.5
```

Results render as a table directly in the page — nothing to download.

## Dependency version notes

- **anthropic SDK is pinned to `0.125.0`**, deliberately staying just before
  the `1.0.0` release (Aug 20, 2026), which is a breaking migration (moves
  its HTTP layer to a different library, drops some older APIs). `0.125.0`
  is new enough to avoid the `TypeError: ... got an unexpected keyword
  argument 'proxies'` crash that older `anthropic` versions hit against
  modern `httpx`, but old enough that the code in `app/vision_client.py`
  (which uses the standard `client.messages.create(...)` pattern) still
  works unmodified. If you want to move to SDK v1.0+ later, expect to
  revisit `app/vision_client.py` against Anthropic's migration guide first.

## If the build fails with a pydantic-core / maturin / Rust error

That means pip is trying to *compile* `pydantic-core` from source instead of
downloading a prebuilt wheel — it happens when the Python version in use is
newer than what that package version has wheels for. `requirements.txt`
already pins a pydantic version with 3.14 wheels, so this shouldn't recur,
but if you ever see this error again after bumping a dependency: check
whether a **build cache** is the culprit before re-diagnosing from scratch.
Render (and similar platforms) can reuse a cached environment from a prior
failed build. On Render: dashboard → your service → Manual Deploy →
"Clear build cache & deploy".

## Deploying on Render

The repo includes a `.python-version` file pinning Python 3.12.7 — this is
the file Render actually reads (it does **not** support Heroku-style
`runtime.txt`, despite that being a common suggestion elsewhere). Without a
pin, Render defaults to its latest Python, and if that's newer than what
`pydantic-core` has a prebuilt wheel for, the build fails trying to compile
it from source (Rust/maturin), which doesn't work on Render's build
filesystem.

Belt-and-suspenders: also add a `PYTHON_VERSION` environment variable set
to `3.12.7` in the Render dashboard's Environment tab — either method
works alone, but setting both means you're covered if Render changes which
one it prioritizes.

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment tab:** add `ANTHROPIC_API_KEY` with your key, and
  `PYTHON_VERSION` set to `3.12.7`

## API endpoints

- `POST /verify-one` — form fields: `image` (file), `expected_brand` (text,
  optional), `expected_abv` (text, optional)
- `POST /verify` — form fields: `csv_file` (file), `images_zip` (file)
- `GET /health` — liveness check

## Notes / things you'll likely want to tune

- **Model id**: `.env.example` pins a model id. Anthropic model ids are
  versioned and get deprecated — check https://docs.claude.com for the
  current one before you deploy this anywhere long-lived.
- **Brand matching**: `app/verifier.py` does substring + fuzzy matching
  (85% similarity threshold) so minor punctuation/spacing differences don't
  fail a check that's obviously correct. Tighten `ABV_TOLERANCE` or the
  fuzzy threshold if you want stricter matching.
- **Rate limits / cost**: batch verification calls the Anthropic API once
  per image, sequentially. For large batches you may want to add
  concurrency (e.g. `asyncio.gather` with a semaphore) and watch your API
  rate limits.
- **Government warning check**: right now it's a simple boolean from the
  model. If you need to verify the *exact* legally-required wording (not
  just "a warning is present"), compare `government_warning_text` against
  the canonical TTB text with the same fuzzy-match approach used for brand.
