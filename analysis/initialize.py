#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import git
from git import Actor

if __name__ == "__main__":

    print('')
    print('')    
    
    print('Initialize review repository')

    assert not os.path.exists('data')
    os.mkdir('data')
    r = git.Repo.init('data')
    os.chdir('data')
    os.mkdir('search')
    
    f = open("search/search_details.csv", "w")
    f.write('"filename","number_records","iteration","date_start","date_completion","source_url","search_parameters","responsible","comment"')
    f.close()
    
    
    project_title = input('Project title: ')
    
    with open('../template/readme.md', 'r') as file :
      filedata = file.read()
    
    filedata = filedata.replace('{{project_title}}', project_title)
    
    with open('readme.md', 'w') as file:
      file.write(filedata)
    
    r.index.add(['readme.md', 'search/search_details.csv'])

#    committer_name = input('Please provide your git-committer name')
#    committer_email = input('Please provide your git-committer email')
    # TBD: store them in a config.py?? there may be further cases in which it is useful to have access to the committer name/email
#    committer = Actor(committer_name, committer_email)
#    r.index.commit("initial commit", committer = committer)