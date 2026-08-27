import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.csv_utils import CsvFormatError, parse_expected_csv
from app.verifier import assess, error_result
from app.vision_client import VisionExtractionError, extract_label_fields

app = FastAPI(title="TTB Label Verifier")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _normalize_lookup_name(name: str) -> str:
    """
    Normalizes a filename for matching between the CSV and the zip:
    lowercase, and treat .jpeg/.jpg as the same extension (Preview, Photos,
    and other tools disagree on which one to export, and people type
    ".jpg" out of habit regardless of what's actually on disk).
    """
    p = Path(name)
    ext = p.suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    return (p.stem.lower() + ext)


def _is_junk_zip_entry(name: str) -> bool:
    """
    Filters out macOS zip metadata noise: __MACOSX/ folders and the
    AppleDouble resource-fork files it creates (._actualfilename). These
    aren't real images and shouldn't be treated as candidates for matching.
    """
    parts = Path(name).parts
    if any(part == "__MACOSX" for part in parts):
        return True
    if Path(name).name.startswith("._"):
        return True
    return False


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/verify-one")
async def verify_one(
    image: UploadFile = File(...),
    expected_brand: str = Form(""),
    expected_abv: str = Form(""),
):
    """Quick single-image check — handy for testing without a CSV/zip."""
    image_bytes = await image.read()
    try:
        extracted = extract_label_fields(image_bytes, image.filename or "upload.jpg")
    except VisionExtractionError as e:
        raise HTTPException(status_code=502, detail=str(e))

    expected_row = {
        "filename": image.filename or "upload.jpg",
        "expected_brand": expected_brand.strip() or None,
        "expected_abv": float(expected_abv) if expected_abv.strip() else None,
    }
    result = assess(expected_row, extracted)
    return JSONResponse(result)


@app.post("/verify")
async def verify_batch(
    csv_file: UploadFile = File(...),
    images_zip: UploadFile = File(...),
):
    """
    Batch check: a CSV of expected values (filename,expected_brand,expected_abv)
    plus a zip of the label images it refers to. Returns one result row per
    CSV entry.
    """
    csv_bytes = await csv_file.read()
    try:
        expected_rows = parse_expected_csv(csv_bytes)
    except CsvFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))

    zip_bytes = await images_zip.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="images_zip is not a valid zip file.")

    # map normalized basename -> actual name in the zip, so lookups are
    # case-insensitive, tolerant of .jpg/.jpeg, ignore folder prefixes, and
    # skip macOS metadata junk (__MACOSX/, ._resourcefork files)
    zip_index = {}
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        if _is_junk_zip_entry(name):
            continue
        zip_index[_normalize_lookup_name(Path(name).name)] = name

    results = []
    for expected_row in expected_rows:
        lookup_key = _normalize_lookup_name(expected_row["filename"])
        zip_entry = zip_index.get(lookup_key)

        if zip_entry is None:
            results.append(
                error_result(
                    expected_row,
                    f"No file named '{expected_row['filename']}' found in the uploaded zip.",
                )
            )
            continue

        image_bytes = zf.read(zip_entry)
        try:
            extracted = extract_label_fields(image_bytes, expected_row["filename"])
        except VisionExtractionError as e:
            results.append(error_result(expected_row, str(e)))
            continue

        results.append(assess(expected_row, extracted))

    return JSONResponse({"results": results})


@app.get("/health")
def health():
    return {"status": "ok"}
