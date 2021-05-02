FROM pandoc/ubuntu-latex:latest
RUN tlmgr update --self
RUN tlmgr install gitinfo2
RUN tlmgr install xstring

RUN apt-get update && apt-get install -y python3-pip && pip3 install pantable
