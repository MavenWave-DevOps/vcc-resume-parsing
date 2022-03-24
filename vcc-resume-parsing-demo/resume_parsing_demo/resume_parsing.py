import argparse
import base64
import json
import logging
import xml.dom.minidom
import os

import requests
import streamlit as st

logger = logging.getLogger()
logger.setLevel(logging.INFO)

IP_ADDRESS = os.getenv("IP_ADDRESS", "127.0.0.1")


def run(args):
    st.title("Mock Demo - Resume Parsing")
    st.markdown(
        "> Note: This front-end is a temporary mockup created only for "
        "demonstration purposes. It will not be developed into a final "
        "product."
    )

    file = st.file_uploader("Upload Resume")
    if file is not None:
        file_details = {
            "Filename": file.name,
            "FileType": file.type,
            "FileSize": file.size,
        }
        st.write(file_details)
        extension = "." + file.name.split(".")[-1]

        with file as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        logger.info(f"Hitting endpoint https://{IP_ADDRESS}:8000/api/resumes/")
        response = requests.post(
            f"http://{IP_ADDRESS}:8000/api/resumes/",
            data=json.dumps({"file": b64, "fileExtension": extension}),
        )
        if response.status_code == 200:
            print(response.text)
            data = json.loads(response.content.decode())
            xmlstr = xml.dom.minidom.parseString(data.get("xml", ""))
            st.markdown("```\n" + xmlstr.toprettyxml() + "\n```")
        elif response.status_code == 500:
            st.markdown(
                f"> :exclamation: An unhandled exception occurred for\n {response.status_code}: {response.text}"
            )
        else:
            st.markdown(
                f"> :exclamation: A known exception occurred\n {response.status_code}: {response.text}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="dev")
    args, _ = parser.parse_known_args()
    run(args)
