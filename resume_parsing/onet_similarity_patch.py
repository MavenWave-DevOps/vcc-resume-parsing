import logging
import os
from typing import List

import numpy as np
import pandas as pd

# import tensorflow_hub as hub
from fastapi import Request
import numpy as np

# from gcsfs import GCSFileSystem

logger = logging.getLogger()
logger.setLevel(level=logging.INFO)


# fs = GCSFileSystem(timeout=1)


def recommend_onet(parsed_results: dict, request: Request = None) -> dict:
    """Recomends O*NET labels.

    Args:
        parsed_results (dict): The parsed results.

    Returns:
        dict: Parsed results with O*NET recommendations inserted.
    """
    # jobs = parsed_results["ResumeData"]["RSUM_WORK_HIST"]
    # recs = find_closest_onet_categories(jobs=jobs, request=request, top_n=1)
    recs = [i for i in parsed_results["ResumeData"]["RSUM_WORK_HIST"]]
    parsed_results["ResumeData"]["RSUM_WORK_HIST"] = [
        {
            **orig,
            **{"ONET_CD": np.round(1252.00, 2)},
        }
        for orig, match in zip(parsed_results["ResumeData"]["RSUM_WORK_HIST"], recs)
    ]

    return parsed_results