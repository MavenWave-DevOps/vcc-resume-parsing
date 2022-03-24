import asyncio
import io
import json  # noqa: F401
import logging
import os  # noqa: F401
import pathlib
import re
import tempfile
import time
from base64 import b64decode  # noqa: F401
from typing import List

import fitz
import proto
import textract
from fastapi import FastAPI, HTTPException, status
from google.cloud import vision  # noqa: F401

# from resume_parsing import utils  # noqa: I202, F401
import utils  # noqa: I202, F401

app = FastAPI()
logger = logging.getLogger()
logger.setLevel(level=logging.INFO)
loop = asyncio.get_event_loop()
STAGING_PATH = os.getenv("STAGING_PATH", "gs://wi_test_bucket/tests")


def process_by_filetype(file: str, file_extension: str) -> str:
    """Route processing based on the extension string.

    Args:
        document_path (str): A GCS URI containing the document.

    Raises:
        HTTPException: HTTP 400 if the file extension is not supported

    Returns:
        str: Path to the extracted text file
    """
    if re.match(r".*\.doc[x]?$", file_extension, re.IGNORECASE):
        result = process_word(file, file_extension)
    elif re.match(r".*\.pdf[x]?$", file_extension, re.IGNORECASE):
        result = process_pdf(file, file_extension)
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Document type not supported. Must provide a .doc/.docx/.pdf file.",
        )

    return result


def process_word(file: str, file_extension: str) -> str:
    """Process a Microsoft Word document.

    Attempts to extract a Microsoft Word document. Also handles RTF format.

    Args:
        document_path (str): A GCS URI containing the document.

    Returns:
        str: Path to the extracted text file
    """
    logging.debug("Processing as a Word document")

    t = time.time()
    with tempfile.TemporaryDirectory() as dirpath:
        tempf = pathlib.Path(dirpath) / f"local{file_extension}"
        with open(tempf, "wb") as f:
            f.write(b64decode(file))
            logger.debug(f"Time to write: {time.time() - t}s")
        text = extract_word(tempf, file_extension)

    return text


def extract_word(filepath: str, ext: str) -> str:
    "Try to extract a word document, with handling for RTFs."
    try:
        t = time.time()
        text = textract.process(filepath, extension=ext).decode("utf-8")
        logger.debug(f"Time to extract: {time.time() - t}s")
        return text
    except textract.exceptions.ShellError:
        try:
            t = time.time()
            text = textract.process(filepath, extension="rtf").decode("utf-8")
            logger.debug(f"Time to extract: {time.time() - t}s")
            return text
        except Exception as err:
            logging.error(err)
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not read document.")
    except Exception as err:
        logging.error(err)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not read document.")


def process_pdf(file: str, file_extension: str) -> str:
    """Call the GCP Cloud Vision API to extract text from a PDF document."""
    logging.debug("Processing as a PDF")

    t = time.time()
    content = b64decode(file)
    with io.BytesIO(content) as b:
        try:
            pdf = fitz.open(filename="x.pdf", stream=b)
        except RuntimeError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid PDF file")
        page_count = pdf.page_count
        logger.debug(page_count)
        logger.debug(f"Time to get page count: {time.time() - t}s")

        # Attempt direct extraction
        full_text = "\n".join([page.getText() for page in pdf])

        if len(full_text.strip()) > 0:
            return full_text

    client = vision.ImageAnnotatorClient()
    tasks = asyncio.gather(
        *[
            sync_detect_document(content, batch, client=client)
            for batch in utils.batch_pages(page_count)
        ]
    )
    results = loop.run_until_complete(tasks)
    full_text = " ".join(
        [
            y["fullTextAnnotation"]["text"]
            for b in results
            for x in json.loads(proto.Message.to_json(b))["responses"]
            for y in x["responses"]
        ]
    )
    return full_text


async def sync_detect_document(content, page_batch: List[int], client=None):
    """Synchronous call to Vision API.

    Args:
        content: Byte stream of the file.
        page_batch (List[int]): A list of page numbers to detect on
            e.g. [1,2,3,4,5]. Max len = 5.
        client: The Vision API ImageAnnotatorClient

    Returns:
        BatchAnnotateFilesResponse
    """
    if not client:
        client = vision.ImageAnnotatorClient()

    mime_type = "application/pdf"
    input_config = {"mime_type": mime_type, "content": content}
    features = [{"type_": vision.Feature.Type.DOCUMENT_TEXT_DETECTION}]
    request = [
        {"input_config": input_config, "features": features, "pages": page_batch}
    ]
    return client.batch_annotate_files(requests=request)
