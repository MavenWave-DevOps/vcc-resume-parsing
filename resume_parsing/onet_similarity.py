# import logging
# import os
# from typing import List

# import numpy as np
# import pandas as pd
# import tensorflow_hub as hub
# from fastapi import Request
# from gcsfs import GCSFileSystem

# logger = logging.getLogger()
# logger.setLevel(level=logging.INFO)


# fs = GCSFileSystem(timeout=1)

# STAGING_PATH = os.getenv("STAGING_PATH", "gs://wi-vcc-dev-ml-o-net/db_25_0_excel")


# def get_onet():
#     return pd.read_excel(f"{STAGING_PATH}/Occupation Data.xlsx")


# def get_embed():
#     model_path = (
#         os.environ.get("TFHUB_CACHE_DIR")
#         or "https://tfhub.dev/google/universal-sentence-encoder/4"  # noqa: W503
#     )
#     return hub.load(model_path)


# def recommend_onet(parsed_results: dict, request: Request = None) -> dict:
#     """Recomends O*NET labels.

#     Args:
#         parsed_results (dict): The parsed results.

#     Returns:
#         dict: Parsed results with O*NET recommendations inserted.
#     """
#     jobs = parsed_results["ResumeData"]["RSUM_WORK_HIST"]
#     recs = find_closest_onet_categories(jobs=jobs, request=request, top_n=1)
#     parsed_results["ResumeData"]["RSUM_WORK_HIST"] = [
#         {
#             **orig,
#             **{"ONET_CD": match[0]["SOC"]},
#         }
#         for orig, match in zip(parsed_results["ResumeData"]["RSUM_WORK_HIST"], recs)
#     ]

#     return parsed_results


# def find_closest_onet_categories(
#     jobs, top_n: int = 1, request: Request = None
# ) -> List[List[dict]]:
#     """Find the N closest categories for each job position.

#     Batch method to find similar recommendations based on
#     both job titles and descriptions.

#     Args:
#         jobs (dict): The dictionary of job data
#         top_n (int): The number of positions to return per job position

#     Returns:
#         List[List[dict]]: Recommendations for each job position
#     """
#     if len(jobs) == 0:
#         return []

#     if request:
#         onet = request.app.state.onet
#         embed = request.app.state.embed
#     else:
#         onet = get_onet()
#         embed = get_embed()
#     titles = [
#         x["POSN_NAM"] if x.get("POSN_NAM", None) is not None else "" for x in jobs
#     ]

#     # titles = [x["POSN_NAM"] if x["POSN_NAM"] is not None else "" for x in jobs]
#     descriptions = [
#         x["RESP_TXT"] if x.get("RESP_TXT", None) is not None else "" for x in jobs
#     ]

#     embeddings = embed(titles + descriptions)
#     title_embed = embeddings[: len(titles)]
#     descrip_embed = embeddings[len(titles) :]

#     onet_title_embed = embed(onet["Title"].to_list())
#     onet_descrip_embed = embed(onet["Description"].to_list())
#     # Scores are normalized per resume; this should probably be fixed
#     # so that we can set thresholds for filtering recommendations
#     title_score = np.inner(title_embed, onet_title_embed) / (
#         np.linalg.norm(title_embed) * np.linalg.norm(onet_title_embed)
#     )
#     title_score = (title_score - np.min(title_score)) / (
#         np.max(title_score) - np.min(title_score)
#     )
#     descrip_score = np.inner(descrip_embed, onet_descrip_embed) / (
#         np.linalg.norm(descrip_embed) * np.linalg.norm(onet_descrip_embed)
#     )
#     descrip_score = (descrip_score - np.min(descrip_score)) / (
#         np.max(descrip_score) - np.min(descrip_score)
#     )
#     similarity_score = np.divide(
#         2 * title_score * descrip_score, title_score + descrip_score
#     )

#     idx = (-similarity_score).argsort()[:, :top_n]
#     recs = [
#         [
#             {
#                 "SOC": onet.iloc[i]["O*NET-SOC Code"],
#                 "Similarity": similarity_score[p, i],
#             }
#             for i in title
#         ]
#         for p, title in enumerate(idx)
#     ]
#     return recs
