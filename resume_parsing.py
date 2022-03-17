import json
import logging

import streamlit as st

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def run():
    st.title("Mock Demo - Resume Parsing")
    file = st.file_uploader("Upload resume")

    if file is not None:
        if file.name in [
            "ResumeParserTest1.docx",
            "ResumeParserTest2.docx",
            "ResumeParserTest3.docx",
        ]:
            if file.name == "ResumeParserTest1.docx":
                json_file = json.load(open("ResumeParserTest1.json", "r"))

            elif file.name == "ResumeParserTest2.docx":
                json_file = json.load(open("ResumeParserTest2.json", "r"))

            elif file.name == "ResumeParserTest3.docx":
                json_file = json.load(open("ResumeParserTest3.json", "r"))
            st.subheader("Parsed Resume")

            st.json(json_file)

        else:
            st.error(f"> :exclamation: {file.name} is not a valid document")


if __name__ == "__main__":
    run()