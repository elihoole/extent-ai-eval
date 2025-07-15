import logging

from scripts.extract import extract_from_image
from scripts.file_handler import read_pdf
from scripts.utils import pil_image_to_base64

logger = logging.getLogger("extent-ai")


def run_pdf_extraction(file_path, financial_highlights_page_index=3):
    """Extract text from PDF by converting pages to images and using OCR extraction"""
    # Convert PDF to list of PIL Images
    logger.debug(f"Converting PDF to images: {file_path}")
    page_images = read_pdf(file_path)
    logger.debug(f"Number of pages in PDF: {len(page_images)}")

    if not page_images:
        logger.error("No pages extracted from the PDF.")
        return []

    financial_highlights_page_image = page_images[financial_highlights_page_index]
    logger.debug(
        f"Extracting financial highlights from page index: {financial_highlights_page_index}"
    )
    base64_image = pil_image_to_base64(financial_highlights_page_image)
    results = extract_from_image(base64_image)
    return results
