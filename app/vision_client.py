"""
Reads a wine/spirits label image and extracts the fields TTB verification
needs, using Claude's vision capability instead of a traditional OCR engine
(Tesseract, etc).

Why vision instead of OCR: label text is often stylized (small caps, serif
display fonts, low-contrast printing on textured backgrounds) which trips up
character-recognition engines. A vision-capable model reads the label
holistically the way a person would, so it isn't thrown off by font choice
or background texture the way Tesseract is.
"""

import base64
import json
import mimetypes

import anthropic

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

EXTRACTION_PROMPT = """You are looking at a photo that is supposed to show one alcoholic beverage label (wine, beer, or spirits).

First, count how many distinct beverage labels are clearly visible in the photo.
Then read the label(s) carefully, including small print.

Return ONLY a JSON object (no markdown fences, no commentary) with exactly these keys:

{
  "label_count": <integer - how many distinct labels you can see. 0 if none/unreadable.>,
  "brand": "<the brand/product name as printed on the (single, primary) label, or null if not visible or not applicable>",
  "abv_percent": <the alcohol-by-volume percentage as a number, e.g. 14.9, or null if not visible or not applicable>,
  "has_government_warning": <true if the label contains the U.S. Surgeon General government warning text, false otherwise>,
  "government_warning_text": "<the government warning text if present, else null>",
  "raw_text": "<all text visible in the photo, transcribed as best you can>"
}

Important: only fill in brand/abv_percent/has_government_warning/government_warning_text
when label_count is exactly 1. If label_count is 0 (no readable label) or 2+ (multiple
labels), set those four fields to null/false and just fill in label_count and raw_text.

Return ONLY the JSON object, nothing else."""


class VisionExtractionError(Exception):
    pass


def _guess_media_type(filename: str) -> str:
    media_type, _ = mimetypes.guess_type(filename)
    if media_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
        # default to jpeg if we can't tell; Claude will still usually decode it
        media_type = "image/jpeg"
    return media_type


def extract_label_fields(image_bytes: bytes, filename: str) -> dict:
    """
    Sends one label image to Claude and returns the parsed extraction dict.
    Raises VisionExtractionError on any failure (missing key, bad response, etc).
    """
    if not ANTHROPIC_API_KEY:
        raise VisionExtractionError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file."
        )

    media_type = _guess_media_type(filename)
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = _client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_image,
                            },
                        },
                        {"type": "text", "text": EXTRACTION_PROMPT},
                    ],
                }
            ],
        )
    except anthropic.APIError as e:
        raise VisionExtractionError(f"Anthropic API error: {e}") from e

    text_parts = [block.text for block in response.content if block.type == "text"]
    raw_text = "\n".join(text_parts).strip()

    # Strip markdown code fences if the model added them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise VisionExtractionError(
            f"Could not parse model response as JSON: {e}\nRaw response: {raw_text[:500]}"
        ) from e

    parsed.setdefault("label_count", 1 if parsed.get("brand") else 0)
    parsed.setdefault("brand", None)
    parsed.setdefault("abv_percent", None)
    parsed.setdefault("has_government_warning", False)
    parsed.setdefault("government_warning_text", None)
    parsed.setdefault("raw_text", "")
    return parsed
