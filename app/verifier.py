"""
Compares what the vision model extracted from a label image against the
expected values from the CSV, and produces a pass/fail verdict per field.

Edge cases (no readable label, or more than one label in the frame) are
deliberately NOT auto-resolved — they're flagged for a human to look at
instead. See "needs_review" below.
"""

import difflib

ABV_TOLERANCE = 0.1  # allow +/- 0.1% for rounding differences


def _brand_matches(expected: str | None, actual: str | None) -> bool:
    if expected is None:
        return True  # nothing to check
    if actual is None:
        return False
    e = expected.strip().lower()
    a = actual.strip().lower()
    if e in a or a in e:
        return True
    # fuzzy fallback for OCR/formatting drift (e.g. punctuation, spacing)
    ratio = difflib.SequenceMatcher(None, e, a).ratio()
    return ratio >= 0.85


def _abv_matches(expected: float | None, actual: float | None) -> bool:
    if expected is None:
        return True
    if actual is None:
        return False
    return abs(expected - actual) <= ABV_TOLERANCE


def _base_result(expected_row: dict) -> dict:
    """Shared skeleton so every result dict (pass, fail, or needs_review) has
    the same keys — keeps the frontend table rendering simple."""
    return {
        "filename": expected_row["filename"],
        "expected_brand": expected_row["expected_brand"],
        "extracted_brand": None,
        "brand_match": False,
        "expected_abv": expected_row["expected_abv"],
        "extracted_abv": None,
        "abv_match": False,
        "government_warning_present": False,
        "overall_pass": False,
        "needs_review": False,
        "review_reason": None,
        "raw_text": None,
        "error": None,
    }


def assess(expected_row: dict, extracted: dict) -> dict:
    """
    expected_row: {filename, expected_brand, expected_abv}
    extracted: output of vision_client.extract_label_fields (always includes
    "label_count" now)
    Returns a result dict ready to hand back to the frontend table.
    """
    result = _base_result(expected_row)
    result["raw_text"] = extracted.get("raw_text")

    label_count = extracted.get("label_count", 0)

    if label_count == 0:
        result["needs_review"] = True
        result["review_reason"] = "No readable label detected in this image — needs a human look."
        return result

    if label_count > 1:
        result["needs_review"] = True
        result["review_reason"] = (
            f"{label_count} distinct labels detected in one image — "
            "can't reliably match this to a single expected result automatically."
        )
        return result

    # exactly one label — normal comparison path
    brand_ok = _brand_matches(expected_row["expected_brand"], extracted.get("brand"))
    abv_ok = _abv_matches(expected_row["expected_abv"], extracted.get("abv_percent"))
    warning_ok = bool(extracted.get("has_government_warning"))

    result["extracted_brand"] = extracted.get("brand")
    result["brand_match"] = brand_ok
    result["extracted_abv"] = extracted.get("abv_percent")
    result["abv_match"] = abv_ok
    result["government_warning_present"] = warning_ok
    result["overall_pass"] = brand_ok and abv_ok and warning_ok
    return result


def error_result(expected_row: dict, error_message: str) -> dict:
    result = _base_result(expected_row)
    result["needs_review"] = True
    result["review_reason"] = "Request failed — see error."
    result["error"] = error_message
    return result
