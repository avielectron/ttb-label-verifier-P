# TTB Label Verifier

Checks alcoholic beverage label images against expected brand name, ABV%,
and presence of the U.S. government warning text — using a vision-capable
Claude model to read the label instead of a traditional OCR engine.

## Stack
- **Backend:** FastAPI (Python), calling the Anthropic API for vision-based
  label extraction
- **Frontend:** single static HTML page (`static/index.html`) — no build
  step, no framework
- **Deploy target:** Render (Python web service)

- ##Instructions
  Go to render.com, log in, click New → Web Service.
Connect your GitHub account if you haven't, and select the repo.
Render should auto-detect it as a Python service. If it gives you a Runtime/Language dropdown, confirm it's Python 3.

3. Set the two command fields
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT

4. Set environment variables
In the service's Environment tab, add:
ANTHROPIC_API_KEY → your key from console.anthropic.com
PYTHON_VERSION → 3.12.7 (belt-and-suspenders alongside the .python-version file already in the repo)

5. Deploy and watch the logs
Click Create Web Service (or Manual Deploy if it already exists).
Watch the log stream: you want to see pip install succeed, then Build successful, then Uvicorn print something like Uvicorn running on http://0.0.0.0:$PORT.
If it hangs on "No open ports detected" — check the Start Command didn't drift back to the local dev version (--reload, no --host/--port).

6. Verify it's actually live
Render gives you a URL like https://your-service-name.onrender.com.
Open it — you should see your Apple-styled UI, not an error page.
Do one real test: upload a label photo through "Check one label" and confirm you get a result back, not just that the page loads.

## Why vision instead of Tesseract/OCR
Traditional OCR engines segment the image into text regions first and then
recognize characters region-by-region. That works fine for uniform,
high-contrast text but struggles with stylized/display fonts, low-contrast
printing on textured backgrounds, and text that isn't in one clean, evenly
lit block. A vision-capable model reads the whole image holistically
instead, so font style and background texture don't trip it up the way
they trip up Tesseract.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY
```

Run it locally:
```bash
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 in your browser.

## Using it

**Check one label:** upload a label photo, optionally type in the brand/ABV
you expect, and get an instant pass/fail per field, with the photo shown
alongside the result.

**Check a batch:** upload a CSV of expected values and a zip of the label
images it refers to. Results render as a table directly on the page —
nothing to download.

CSV format (see `sample_data/sample_expected.csv`):

```csv
filename,expected_brand,expected_abv
wine1.jpeg,Resolution,14.9
wine2.jpeg,Some Other Brand,13.5
```

CSV/zip matching behavior:
- Column delimiter is auto-detected (comma, semicolon, or tab) — spreadsheet
  apps export CSVs with different delimiters depending on regional settings,
  so this isn't assumed to always be a comma.
- A CSV row's `filename` matches an image in the zip case-insensitively,
  and `.jpg`/`.jpeg` are treated as the same extension.
- Folders inside the zip are fine — only the filename has to match.
- macOS "Compress" zip metadata (`__MACOSX/`, `._resourcefork` files) is
  filtered out automatically.

## Edge case handling

Extraction always reports how many distinct labels it can see in the image
(`label_count`). Rather than guessing when something's ambiguous:
- **0 labels detected** (blurry/unreadable/no label) → flagged as
  "needs review", not silently marked pass or fail.
- **2+ labels detected** in one photo → also flagged as "needs review",
  since automatically guessing which label is "the" one is a worse failure
  mode than asking a human to look.
- **Exactly 1 label** → runs the normal brand/ABV/warning comparison.

## API endpoints

- `POST /verify-one` — form fields: `image` (file), `expected_brand` (text,
  optional), `expected_abv` (text, optional)
- `POST /verify` — form fields: `csv_file` (file), `images_zip` (file)
- `GET /health` — liveness check

## Deploying on Render

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment tab:** add `ANTHROPIC_API_KEY` with your key, and
  `PYTHON_VERSION` set to `3.12.7`

The repo also includes a `.python-version` file pinning Python 3.12.7 as a
second, redundant way of specifying the version (Render reads this file
directly; it does **not** support Heroku-style `runtime.txt`).

## Dependency version notes
- **pydantic pinned to `2.12.5`** — earlier versions don't have prebuilt
  wheels for newer Python releases, which forces pip to compile
  `pydantic-core` from source (via Rust/maturin), and that compile step
  fails on Render's build filesystem.
- **anthropic SDK pinned to `0.125.0`**, deliberately staying just before
  the `1.0.0` release (Aug 20, 2026), which is a breaking migration (moves
  its HTTP layer to a different library, drops some older APIs). `0.125.0`
  is new enough to avoid a `TypeError: ... got an unexpected keyword
  argument 'proxies'` crash that older `anthropic` versions hit against
  modern `httpx`, but old enough that `app/vision_client.py`'s
  `client.messages.create(...)` pattern still works unmodified.

## How this actually got built
reiterative approach spent the entire week testing 



## How this actually got built---

## How this actually got built
