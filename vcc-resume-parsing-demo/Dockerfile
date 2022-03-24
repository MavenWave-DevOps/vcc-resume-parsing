FROM python:3.7-slim

ENV STREAMLIT_SERVER_PORT 8000
ENV STREAMLIT_SERVER_HEADLESS True
ENV STREAMLIT_SERVER_BASE_URL_PATH /api/resume/demo
ENV IP_ADDRESS 0.0.0.0

COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app
COPY resume_parsing_demo .

ENTRYPOINT streamlit run resume_parsing.py -- --env=$ENDPOINT_ENV