import logging

import PyPDF2

from scripts.extract_with_llm import extract_from_image
from scripts.file_handler import read_pdf
from scripts.utils import pil_image_to_base64

logger = logging.getLogger("extent-ai")


def run_pdf_extraction(
    file_path, company_name_page_index=0, financial_highlights_page_index=3
):
    """Extract text from PDF by converting pages to images and using OCR extraction"""
    # Convert PDF to list of PIL Images

    logger.debug(f"Converting PDF to images: {file_path}")

    company_name = get_company_name_from_pdf(file_path, company_name_page_index)
    financial_highlights = extract_financial_highlights_from_pdf(
        file_path, financial_highlights_page_index
    )

    # Add company name to the financial highlights metadata
    if company_name:
        financial_highlights.metadata["company_name"] = company_name

    return financial_highlights


def extract_financial_highlights_from_pdf(file_path, financial_highlights_page_index=3):
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


def get_company_name_from_pdf(file_path, company_name_page_index=0):
    """
    # First page of the PDF is assumed to contain the company name.
    :param file_path: Path to the PDF file.
    :return: Company name extracted from page index 0, using PyPDF2.
    """
    if not file_path or not isinstance(file_path, str):
        return None
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            if len(reader.pages) > 0:
                first_page = reader.pages[company_name_page_index]
                text = first_page.extract_text()
                if text:
                    # Assuming the company name is the first line of text
                    company_name = text.strip()
                    logger.info(f"Extracted company name: {company_name}")
                    return company_name
    except Exception as e:
        logging.error(f"Error reading PDF file: {e}")
    return None
