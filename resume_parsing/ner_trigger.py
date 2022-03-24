import logging
import os

from fastapi import HTTPException, status
from google.cloud import aiplatform

logger = logging.getLogger()
logger.setLevel(level=logging.INFO)


PROJECT_ID = os.getenv("PROJECT_ID", "wi-vcc-dev-ml-254a")
LOCATION = os.getenv("LOCATION", "us-central1")


def get_endpoint(endpoint_name):
    try:
        endpoint_id = [
            x
            for x in aiplatform.Endpoint.list(project=PROJECT_ID, location=LOCATION)
            if x.display_name == endpoint_name
        ][0].name
        return endpoint_id
    except Exception as err:
        logger.error(
            f"Failed to find Vertex model endpoint [{endpoint_name}] in "
            f"project [{PROJECT_ID}] and location [{LOCATION}]"
        )
        logger.error(err)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to startup model service."
        )


# mock this and return corerct json
def predict_entities(resume, request=None):
    """Submits a document for entity extraction on Vertex AI.

    Args:
        resume (str): The text content from a resume.

    Returns:
        response.predictions (dict): The infrence
    """
    if hasattr(request.app.state, "endpoint_id"):
        logger.debug("Using saved endpoint id")
        endpoint_id = request.app.state.endpoint_id
    else:
        logger.debug("Hitting model endpoint")
        endpoint_id = get_endpoint(request.app.state.endpoint_name)
        request.app.state.endpoint_id = endpoint_id

    # if len(resume) > 9500:
    #     logger.warning(f"Truncating resume from {len(resume)} to 10k characters")
    #     resume = resume[:9500]

    endpoint = aiplatform.Endpoint(endpoint_id, project=PROJECT_ID, location=LOCATION)

    try:
        response = endpoint.predict(instances=[{"content": resume}], parameters={})
    except Exception as err:
        logger.error(err)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Failed to make call to parser model.",
        )
    return response.predictions[0]
