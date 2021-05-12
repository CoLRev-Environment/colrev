FROM python:3.6

COPY requirements.txt ./

RUN apt-get update && apt-get install -y libxml2-dev zlibc python3-lxml \
&& pip install -U pip && pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /usr/data
RUN chown -R root:root /usr/data

WORKDIR /opt/workdir
COPY . /opt/workdir
