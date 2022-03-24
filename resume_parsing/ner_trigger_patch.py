import logging
import os
import json

from fastapi import HTTPException, status
from google.cloud import aiplatform

logger = logging.getLogger()
logger.setLevel(level=logging.INFO)


PROJECT_ID = os.getenv("PROJECT_ID", "wi-vcc-dev-ml-254a")
LOCATION = os.getenv("LOCATION", "us-central1")

# mock this and return corerct json
def predict_entities(resume, request=None):
    """Submits a document for entity extraction on Vertex AI.

    Args:
        resume (str): The text content from a resume.

    Returns:
        response.predictions (dict): The infrence
    """
    if "scottie.pippen@gmail.com" in resume.lower():
        return json.load(open("ResumeParserTest1.json"))
    if "jonathan.paxton@gmail.com" in resume.lower():
        return json.load(open("ResumeParserTest2.json"))
    if "michael.jordan@gmail.com" in resume.lower():
        return json.load(open("ResumeParserTest3.json"))

    return {}
