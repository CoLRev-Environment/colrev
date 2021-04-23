FROM python:3.6
WORKDIR /opt/workdir

COPY requirements.txt ./

RUN apt-get update && pip install -U pip && pip install --no-cache-dir -r requirements.txt

