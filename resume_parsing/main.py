import logging
import os

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer
from gcsfs import GCSFileSystem

# from jose import JWTError, jwt
from pydantic import BaseModel

from resume_parsing import (
    custom_parser,
    doc_extractor,
    onet_similarity,
)  # , ner_trigger
from resume_parsing import ner_trigger_patch as ner_trigger
import onet_similarity_patch as onet_similarity
from resume_parsing.utils import to_xml
from utils import to_xml

app = FastAPI()

logger = logging.getLogger()
logger.setLevel(level=logging.INFO)

fs = GCSFileSystem(timeout=1)

# bearer = HTTPBearer()
# SECRET_KEY = os.getenv("JCW_APP")
# ALGORITHM = "HS256"

STAGING_PATH = os.getenv("STAGING_PATH", "gs://wi_test_bucket/tests")
ENDPOINT_NAME = os.getenv("ENDPOINT_NAME", "resume_parsing_qa_09_03_2021")


class ResumeFile(BaseModel):
    file: str
    fileExtension: str


class ParsedFields(BaseModel):
    xml: str

    class Config:
        schema_extra = {
            "example": {
                "xml": """<?xml version="1.0" standalone="yes"?>
  <ResumeData xmlns="http://tempuri.org/ResumeData.xsd">
    <CUST_RSUM></CUST_RSUM>
    <RSUM_EDUC_HIST></RSUM_EDUC_HIST>
    <RSUM_WORK_HIST></RSUM_WORK_HIST>
    <RSUM_WORK_HIST></RSUM_WORK_HIST>
  </ResumeData>"""
            }
        }


@app.get("/api/resumes/healthcheck")
async def health():
    return Response(status_code=200)


# @app.on_event("startup")
# async def app_startup():
#     app.state.endpoint_name = ENDPOINT_NAME
#     app.state.onet = onet_similarity.get_onet()
#     app.state.embed = onet_similarity.get_embed()


# async def authenticate(token: str = Depends(bearer)):  # noqa: B008
# async def authenticate(token: str = Depends(bearer)):  # noqa: B008
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload
#     except JWTError:
#         raise credentials_exception


@app.post(
    "/api/resumes/",
    response_model=ParsedFields,
    # dependencies=[Depends(authenticate)],
)
def root(file: ResumeFile, request: Request):
    """Extracts a resume document for text processing.

    .doc/.docx files are extracted using Textract
    .pdf files are extracted using Google's Cloud Vision API

    A message is added to a downstream Pub/Sub topic with the request_id
    to wait for completion.

    Args:
        file (str): A base64-encoded string containing the file.
        fileExtension (str): The file extension of the resume. Expected to be one of:
            .pdf, .doc, .docx

    Returns:
        ExtractionRequest:
            xml: An XML element containing the parsed fields
    """
    text = doc_extractor.process_by_filetype(file.file, file.fileExtension)
    entities = ner_trigger.predict_entities(text, request=request)
    # entities = ner_trigger.predict_entities(text, request=request)
    parsed_results = custom_parser.parse(entities, text)
    final_results = onet_similarity.recommend_onet(
        parsed_results, request=request
    )  # add placeholder dictionary key
    return {"xml": to_xml(final_results)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)