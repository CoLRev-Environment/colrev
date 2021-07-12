#! /usr/bin/env python
import csv
import hashlib
import sys

import requests
import utils

if __name__ == '__main__':

    print('')
    print('')

    print('Renew hash_id function')
    print('')

    input('IMPORTANT: remove BIB_DETAILS from entry_hash_function.py in the next version!')

    input('TODO: dont add duplicates to hash_function_pipeline_commit_id.csv')
    with open('analysis/entry_hash_function.py') as file:
        hash_of_hash_function = hashlib.sha256(
            file.read().encode('utf-8')).hexdigest()
        # print(hash_of_hash_function)
        # NOTE: requests not yet working because pipeline-validation-hooks
        # is not yet publicly available.
#        r = requests.get('https://raw.githubusercontent.com/geritwagner/pipeline-validation-hooks/main/pipeline_validation_hooks/entry_hash_function.py')
#        print(hashlib.sha256(r.text.encode('utf-8')).hexdigest())
    print('Replace temporary fix once pipeline-validation-hooks is public:')
    with open('/home/gerit/ownCloud/projects/WAITING_LRTemplate/pipeline-validation-hooks/pipeline_validation_hooks/entry_hash_function.py') as file2:
        hash_of_hash_function_pipeline = hashlib.sha256(
            file2.read().encode('utf-8')).hexdigest()
        # print(hash_of_hash_function_pipeline)
    if not hash_of_hash_function_pipeline == hash_of_hash_function:
        print('Error: hash functions not matching!')
        sys.exit(0)
        # latest commit id
        # https://api.github.com/repos/geritwagner/enlit/commits/master

    # TODO: get commit_id of https://github.com/geritwagner/pipeline-validation-hooks
    commit_id = input(
        'please enter latest commit ID of pipeline-validation-hooks repository:')

    fields = [hash_of_hash_function, commit_id]
    with open('analysis/hash_function_pipeline_commit_id.csv', 'a') as f:
        writer = csv.writer(f)
#        writer.writerow(['hash_of_hash_function', 'commit_id'])
        writer.writerow(fields)

    input('TODO manually: update commit_id in /home/gerit/ownCloud/projects/WAITING_LRTemplate/review-template/template/.pre-commit-config.yaml')

    # implement checks of up-to-date hash_function in all scripts
    # Note: this should work reliably even if changes are force-pushed (because the IDs would change!)
