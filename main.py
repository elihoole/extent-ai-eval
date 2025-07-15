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


def main(file_path=None):
    if not file_path:
        file_path = input("Enter the path to the PDF file: ")

    logger.info(f"Starting extraction for file: {file_path}")
    # Copy file to input directory
    input_file_path = copy_to_input_dir(file_path)
    results = run_pdf_extraction(input_file_path)

    if results:
        logger.info("Extraction completed successfully.")
        # Use the same name as input file (without extension) for output JSON
        base_name = os.path.splitext(os.path.basename(input_file_path))[0]
        output_filename = f"{base_name}.json"
        write_output_json(output_filename, results)
    else:
        logger.error("No results returned from extraction.")


if __name__ == "__main__":
    main(file_path="financial_statement (1).pdf")
