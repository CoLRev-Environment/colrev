FROM rocker/tidyverse
## Work-around to make Docker Hub use the Dockerfile
## from https://github.com/rocker-org/rocker-versioned/tree/master/rstudio
WORKDIR /home/rstudio

RUN apt-get update && apt-get install -y \
    python3-pip
RUN apt-get install -y --no-install-recommends latexmk\
  	texlive-lang-japanese \
  	texlive-luatex \
  	texlive-xetex \
  	texlive-pictures \
  	texlive-fonts-extra \
    texlive-fonts-recommended

RUN sudo pip3 install bibtexparser pandas citeproc-py xlsxwriter unidecode gensim bs4 fuzzywuzzy

RUN install2.r irr rms moments ineq polycor robustHD e1071 forecast Cairo extrafont tikzDevice showtext bib2df devEMF plyr xtable

RUN apt-key adv --keyserver hkp://keys.gnupg.net --recv-keys 7638D0442B90D010
RUN apt-key adv --keyserver hkp://keys.gnupg.net --recv-keys 04EE7237B7D453EC
RUN apt-key adv --keyserver hkp://keys.gnupg.net --recv-keys 9D6D8F6BC857C906

# ---------
# MS CORE FONTS
# ---------
# RUN echo "deb http://httpredir.debian.org/debian jessie main contrib" > /etc/apt/sources.list \
#    && echo "deb http://security.debian.org/ jessie/updates main contrib" >> /etc/apt/sources.list \    && echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections \
RUN echo "deb http://cloudfront.debian.net/debian jessie main contrib" > /etc/apt/sources.list \
    && echo "deb http://cloudfront.debian.net/debian-security jessie/updates main contrib" >> /etc/apt/sources.list \    && echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections \
    && apt-get update \
    && apt-get install -y ttf-mscorefonts-installer \
    && apt-get clean \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN R -e "devtools::install_github('ropensci/bib2df')"
