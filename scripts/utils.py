import base64
import io
import json
import logging
import os
import re
import shutil
import uuid

from dotenv import load_dotenv
from pydantic import BaseModel

logger = logging.getLogger("extent-ai")
load_dotenv()


def get_file_path_to_save(pdf_file_path: str):
    name, ext = os.path.splitext(os.path.basename(pdf_file_path))
    uuid_str = str(uuid.uuid4())[:8]
    file_name_to_save = (
        re.sub(r"[^a-zA-Z0-9]+", "_", name).lower() + f"_{uuid_str}" + ext
    )
    logger.info(f"File name to save: {file_name_to_save}")
    return file_name_to_save


def copy_to_input_dir(file_path: str):
    input_dir = os.getenv("INPUT_DIR", "input")
    os.makedirs(input_dir, exist_ok=True)
    input_file_path = os.path.join(input_dir, get_file_path_to_save(file_path))

    if not os.path.exists(input_file_path):
        shutil.copy2(file_path, input_file_path)
        logger.info(f"Copied file to input directory: {input_file_path}")
    else:
        logger.warning(f"File already exists in input directory: {input_file_path}")

    return input_file_path


def pil_image_to_base64(pil_image):
    """Convert a PIL Image to base64 string"""
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def write_output_json(file_path, data):
    """Write data to a JSON file"""
    if not file_path.endswith(".json"):
        raise ValueError("File path must end with .json")

    output_dir = os.getenv("OUTPUT_DIR", "output")
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, file_path)

    # Convert Pydantic models to dictionaries
    if isinstance(data, BaseModel):
        data = data.model_dump()

    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
    logger.info(f"Data written to {file_path}")
