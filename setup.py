#!/usr/bin/env python
from setuptools import find_packages
from setuptools import setup

import versioneer

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('CHANGELOG.md') as changelog_file:
    changelog = changelog_file.read()

requirements = ['Click>=7.0',
                'ansiwrap==0.8.4',
                'bibtexparser==1.2.0',
                'dictdiffer==0.8.1',
                'fuzzywuzzy==0.18.0',
                'GitPython==3.1.18',
                'langdetect==1.0.9',
                'nameparser==1.0.6',
                'nltk==3.6.2',
                'numpy==1.21.2',
                'pandas==1.2.5',
                'pdfminer==20191125',
                'pdfminer.six==20201018',
                'pre-commit==2.15.0',
                'pytest==6.2.4',
                'python_Levenshtein==0.12.2',
                'PyYAML==5.4.1',
                'requests==2.22.0',
                'tqdm==4.61.1',
                'ujson==4.0.2',
                'wordsegment==1.3.1', ]

test_requirements = ['pytest>=3',
                     'attrs>=19.2.0',
                     'packaging>=21.0']


entry_points = \
    [
        'process=review_template.cli:process',
        'status=review_template.cli:status',
        'initialize=review_template.cli:initialize',
        'complete_manual=review_template.cli:complete_manual',
        'cleanse_manual=review_template.cli:cleanse_manual',
        'process_duplicates_manual=review_template.cli:proc_duplicates_manual',
        'pre_screen=review_template.cli:pre_screen',
        'screen=review_template.cli:screen',
        'acquire_pdfs=review_template.cli:acquire_pdfs',
        'validate_pdfs=review_template.cli:validate_pdfs',
        'backward_search=review_template.cli:backward_search',
        'data=review_template.cli:data',
        'validate_changes=review_template.cli:validate_changes',
        'sample_profile=review_template.cli:sample_profile',
        'trace_hash_id=review_template.cli:trace_hash_id',
        'trace_search_result=review_template.cli:trace_search_result',
        'trace_entry=review_template.cli:trace_entry',
    ]

setup(
    name='review_template',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    python_requires='>=3.6',
    description='Template for git-based literature reviews',
    long_description=readme + '\n\n' + changelog,
    long_description_content_type='text/markdown',
    url='https://github.com/geritwagner/review_template',
    author='Gerit Wagner',
    author_email='gerit.wagner@hec.ca',
    license='MIT license',
    py_modules=['review_template'],
    test_suite='tests',
    tests_require=test_requirements,
    include_package_data=True,
    package_data={
        '': ['template*'],
    },
    packages=find_packages(include=['review_template', 'review_template.*']),
    keywords='review_template',
    zip_safe=False,
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Topic :: Scientific/Engineering',
        'Operating System :: OS Independent',
    ],
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'review_template=review_template.cli:main',
        ],
        'review_template.entry_points': entry_points,
    },
    project_urls={
        'Bug Reports': 'https://github.com/geritwagner/review_template/issues',
        'Source': 'https://github.com/geritwagner/review_template',
    },
)
