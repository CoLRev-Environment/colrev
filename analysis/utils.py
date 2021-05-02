#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import re

def robust_append(string_to_hash, to_append):
    
    to_append = to_append.replace('\n', ' ').rstrip().lstrip()
    to_append = re.sub('\s+',' ', to_append)
    to_append = to_append.lower()
    
    string_to_hash = string_to_hash + to_append
    
    return string_to_hash

def create_hash(entry):
    string_to_hash = robust_append('', entry.get("author", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("author", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("title", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("journal", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("booktitle", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("year", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("volume", ""))
    string_to_hash = robust_append(string_to_hash, entry.get("issue", ""))

    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()