import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from json_repair import repair_json
from pydantic import BaseModel, Field

logger = logging.getLogger("extent-ai")
load_dotenv()


class FinancialMetric(BaseModel):
    """Individual financial metric with current year, previous year, and change percentage"""

    metric: str = Field(description="Name of the financial metric")
    value_2025: Optional[float] = Field(
        description="Value for the current report year (2025)"
    )
    value_2024: Optional[float] = Field(
        description="Value for the previous year (2024)"
    )
    change_percent: Optional[float] = Field(
        description="Percentage change from previous year"
    )


class FinancialHighlights(BaseModel):
    """Response schema for OCR extraction of financial highlights"""

    report_year: int = Field(description="The year of the financial report")
    metrics: List[FinancialMetric] = Field(
        description="List of all financial metrics extracted from the highlights table"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the extraction"
    )


def setup_gemini():
    system_prompt = get_system_prompt()
    model = os.getenv("GEMINI_MODEL")
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return client, model, system_prompt


def get_system_prompt() -> str:
    prompt_path = os.getenv("PROMPT_PATH")
    if not prompt_path:
        raise ValueError("PROMPT_PATH environment variable is not set")

    with open(prompt_path, "r") as f:
        extraction_prompt = f.read()
        return extraction_prompt


def get_token_counts(gemini_response):
    # Get token usage metrics if available (Keep this part)
    token_counts = {}
    if hasattr(gemini_response, "usage_metadata"):
        token_counts = {
            "input_tokens": getattr(
                gemini_response.usage_metadata, "prompt_token_count", 0
            ),
            "output_tokens": getattr(
                gemini_response.usage_metadata, "candidates_token_count", 0
            ),
            "total_tokens": getattr(
                gemini_response.usage_metadata, "total_token_count", 0
            ),
        }

        logger.debug(
            f"Token Usage - Input: {token_counts['input_tokens']}, "
            f"Output: {token_counts['output_tokens']}, "
            f"Total: {token_counts['total_tokens']}"
        )
    return token_counts


def extract_from_image(base64_image, max_tries=3, retry_delay=2) -> FinancialHighlights:
    """
    Extract structured information from an image using Google's Gemini model

    Args:
        base64_image: Base64 encoded image string
        max_tries: Maximum number of extraction attempts
        retry_delay: Initial delay between retry attempts in seconds

    Returns:
        PageResponse object containing the extracted data
    """
    last_exception = None

    for attempt in range(1, max_tries + 1):
        try:
            logger.info(f"Extraction attempt {attempt}/{max_tries}")

            client, model, system_prompt = setup_gemini()

            # Call Gemini API requesting JSON output
            response = client.models.generate_content(
                model=model,
                contents=[
                    system_prompt,
                    # Ensure base64_image is bytes, not string:
                    types.Part.from_bytes(data=base64_image, mime_type="image/jpeg"),
                ],
                config={
                    "response_mime_type": "application/json",
                },
            )

            # Parse the response
            try:
                json_data = repair_json(response.text)

                # Validate with Pydantic model
                financial_highlights = FinancialHighlights.model_validate(
                    json.loads(json_data)
                )

                financial_highlights.metadata["token_usage"] = get_token_counts(
                    response
                )
                # Successfully processed, return the result
                return financial_highlights

            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON response: {e}")
                logger.error(f"Raw response: {response.text}")
                raise
            except Exception as e:
                logger.error(f"Error parsing or validating response: {e}")
                logger.error(f"Raw response: {response.text}")
                raise

        except Exception as e:
            last_exception = e
            logger.error(
                f"Error during extraction (attempt {attempt}/{max_tries}): {e}"
            )

            if attempt < max_tries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                # Increase delay for next retry (exponential backoff)
                retry_delay *= 2
            else:
                logger.error(f"Failed after {max_tries} attempts")
                raise last_exception
