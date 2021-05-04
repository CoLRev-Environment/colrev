#! /usr/bin/env python
# -*- coding: utf-8 -*-


import os
import time
from time import gmtime, strftime
import pandas as pd
import requests
import subprocess
from tqdm import tqdm


GROBID_URL = 'http://localhost:8070'

def start_grobid():
    try:
        r = requests.get(GROBID_URL + '/api/isalive')
        if r.text == 'true':
            return True
    except:
        print('Starting grobid service...')
        subprocess.Popen(['docker run -t --rm -m "4g" -p 8070:8070 -p 8071:8071 lfoppiano/grobid:0.6.2'], 
                         shell=True,
                         stdin=None,
                         stdout=open(os.devnull, 'wb'), 
                         stderr=None, close_fds=True)
        pass

    i = 0
    while True:
        i += 1
        time.sleep(1)
        try:
            r = requests.get(GROBID_URL + '/api/isalive')
            if r.text == 'true':
                print('Grobid service alive.')
                return True
        except:
            pass
        if i > 30:
            break
    return False

def grobid_transformation(pdf):
    
    print(pdf)
    tei_filename = pdf.replace('.pdf','.tei.xml').replace('data/pdf/', 'data/search/backward/')
    if os.path.exists(tei_filename):
        print('file already transformed: ' + tei_filename)
        return
    #TODO: possibly using docker-compose?    
    if not start_grobid():
        print('Cannot start Docker/Grobid')
        return

    options = {'consolidateHeader': '0', 'consolidateCitations': '1'}
    r = requests.post(GROBID_URL + '/api/processFulltextDocument', 
                      files=dict(input=open(pdf, 'rb')), 
                      data=options)
    f = open(tei_filename, "w")
    f.write(r.text)
    f.close()

    return

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Backward search - Grobid transformation')

    print('requires local Grobid image (docker pull lfoppiano/grobid:0.6.2)')
    
    backward_search_file = 'data/search/backward_search_pdfs.csv'
    assert os.path.exists(backward_search_file)

    pdfs = pd.read_csv(backward_search_file)

    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    for pdf in tqdm(pdfs['filenames'].tolist()):
        grobid_transformation(pdf)
    print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
