import argparse
import logging
import os

from scripts.pipeline import run_pdf_extraction
from scripts.utils import copy_to_input_dir, write_output_json


def setup_logger(level=logging.INFO):
    logger = logging.getLogger("extent-ai")
    if logger.hasHandlers():
        logger.setLevel(level)
        return logger

    logger.setLevel(level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = False
    logger.info("Logger initialized")
    return logger


logger = setup_logger(level=logging.DEBUG)


def main(
    file_path=None, company_name_page_index=None, financial_highlights_page_index=None
):
    if not file_path:
        parser = argparse.ArgumentParser(description="Extract data from PDF files")
        parser.add_argument(
            "--file_path",
            type=str,
            required=True,
            help="Path to the PDF file to process",
        )
        parser.add_argument(
            "--company_name_page_index",
            type=int,
            default=0,
            help="Page index to extract company name from (default: 0)",
        )
        parser.add_argument(
            "--financial_highlights_page_index",
            type=int,
            default=3,
            help="Page index to extract financial highlights from (default: 3)",
        )
        args = parser.parse_args()
        file_path = args.file_path
        company_name_page_index = args.company_name_page_index
        financial_highlights_page_index = args.financial_highlights_page_index

    logger.info(f"Starting extraction for file: {file_path}")
    # Copy file to input directory
    input_file_path = copy_to_input_dir(file_path)
    results = run_pdf_extraction(
        input_file_path,
        company_name_page_index=company_name_page_index,
        financial_highlights_page_index=financial_highlights_page_index,
    )

    if results:
        logger.info("Extraction completed successfully.")
        # Use the same name as input file (without extension) for output JSON
        base_name = os.path.splitext(os.path.basename(input_file_path))[0]
        output_filename = f"{base_name}.json"
        write_output_json(output_filename, results)
    else:
        logger.error("No results returned from extraction.")


if __name__ == "__main__":
    main()
