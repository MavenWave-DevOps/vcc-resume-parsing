FROM tiangolo/uvicorn-gunicorn-fastapi:python3.7

ENV PORT 8000
ENV STAGING_PATH gs://wi-vcc-dev-ml-o-net/db_25_0_excel
ENV TFHUB_CACHE_DIR /root/.cache/tfhub_modules
ENV ENDPOINT_NAME resume_parsing_qa_09_03_2021
ENV PROJECT_ID wi-vcc-dev-ml-254a
ENV LOCATION us-central1
ENV MAX_WORKERS 1
ENV JCW_APP SecretKey-5E753756-0676-4335-955D-9CA8EBFF89A2-4VCC

EXPOSE 8000

RUN apt-get update && apt-get install -y antiword unrtf
RUN apt-get install -y git # Workaround for textract

COPY gunicorn_conf.py /app/gunicorn_conf.py

COPY resume_parsing/requirements.txt .
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app/resume_parsing
COPY resume_parsing/* .
