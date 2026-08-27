"""
Parses the expected-values CSV that gets uploaded alongside the zip of label
images. Expected columns (header row required):

    filename,expected_brand,expected_abv

- filename must match (case-insensitively) a file inside the uploaded zip.
- expected_abv should be a plain number like 14.9 (no % sign needed, but a
  trailing % is tolerated and stripped).
- Delimiter is auto-detected (comma, semicolon, or tab) rather than assumed,
  since spreadsheet apps (Excel/Numbers/Sheets) export CSVs with different
  delimiters depending on regional settings — a semicolon-delimited export
  is a very common real-world case, not an edge case.
"""

import csv
import io


class CsvFormatError(Exception):
    pass


REQUIRED_COLUMNS = {"filename", "expected_brand", "expected_abv"}


def _detect_dialect(text: str) -> csv.Dialect:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        # Sniffer gives up on very short/simple samples sometimes even when
        # comma is clearly right — fall back to the standard comma dialect
        # rather than failing outright.
        return csv.excel


def parse_expected_csv(csv_bytes: bytes) -> list[dict]:
    text = csv_bytes.decode("utf-8-sig")  # handles Excel's BOM-prefixed CSVs
    dialect = _detect_dialect(text)
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    if reader.fieldnames is None:
        raise CsvFormatError("CSV file appears to be empty.")

    header = {h.strip().lower() for h in reader.fieldnames}
    missing = REQUIRED_COLUMNS - header
    if missing:
        detected_delim = repr(dialect.delimiter)
        raise CsvFormatError(
            f"CSV is missing required column(s): {', '.join(sorted(missing))}. "
            f"Required columns: {', '.join(sorted(REQUIRED_COLUMNS))}. "
            f"Detected column delimiter was {detected_delim} — if that's wrong for "
            f"your file, re-save it as a plain comma-separated .csv."
        )

    rows = []
    for i, raw_row in enumerate(reader, start=2):  # row 1 is the header
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items()}
        if not row.get("filename"):
            continue  # skip blank lines

        abv_raw = row["expected_abv"].rstrip("%").strip()
        try:
            expected_abv = float(abv_raw) if abv_raw else None
        except ValueError:
            raise CsvFormatError(
                f"Row {i}: expected_abv value '{row['expected_abv']}' is not a number."
            )

        rows.append(
            {
                "filename": row["filename"],
                "expected_brand": row.get("expected_brand") or None,
                "expected_abv": expected_abv,
            }
        )

    if not rows:
        raise CsvFormatError("CSV had a header but no data rows.")

    return rows
