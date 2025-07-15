import logging

import pdf2image


def read_pdf(file_path):
    """
    Reads a PDF file and returns a list of page images

    :param file_path: Path to the PDF file.
    :return: list of page images or None if the file cannot be read.
    """
    logger = logging.getLogger("extent-ai")
    # first check if the file exists
    if (
        not file_path
        or not isinstance(file_path, str)
        or not file_path.endswith(".pdf")
    ):
        logger.error("Invalid file path provided.")
        return None
    try:
        images = pdf2image.convert_from_path(file_path)
        logger.info(f"Successfully read {len(images)} pages from the PDF.")
        return images
    except Exception as e:
        logger.error(f"Failed to read PDF file: {e}")
        return None


if __name__ == "__main__":
    doc_path = (
        "/home/elihoole/Documents/personal-work/extent-ai/financial_statement (1).pdf"
    )
    images = read_pdf(doc_path)
    if images:
        print(f"Extracted {len(images)} pages from the PDF.")
    else:
        print("Failed to read the PDF file.")
