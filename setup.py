#!/usr/bin/env python
from setuptools import find_packages
from setuptools import setup

import versioneer

with open("README.md") as readme_file:
    readme = readme_file.read()

with open("CHANGELOG.md") as changelog_file:
    changelog = changelog_file.read()

requirements = [
    "ansiwrap==0.8.4",
    "bashplotlib==0.6.5",
    "bibtexparser==1.2.0",
    "Click==8.0.1",
    "click_completion==0.5.2",
    "dictdiffer==0.8.1",
    "docker_py==1.10.6",
    "docker==2.1.0",
    "GitPython==3.1.24",
    "langdetect==1.0.9",
    "nameparser==1.0.6",
    "pandas==1.2.5",
    "pdfminer.six==20211012",
    "PyYAML==6.0",
    "requests==2.22.0",
    "thefuzz==0.19.0",
    "tqdm==4.61.1",
    "transitions==0.8.10",
]
# 'configparser>=5.0'


# Note: docker and docker-py seem to be similar/identical?!
# https://pypi.org/project/docker-py/
# https://pypi.org/project/docker/

test_requirements = ["pytest>=3", "attrs>=19.2.0", "packaging>=21.0"]


entry_points = [
    "process=review_template.cli:process",
    "status=review_template.cli:status",
    "init=review_template.cli:init",
    "load=review_template.cli:load",
    "prepare=review_template.cli:prepare",
    "dedupe=review_template.cli:dedupe",
    "prep_man=review_template.cli:prep_man",
    "dedupe_man=review_template.cli:dedupe_man",
    "prescreen=review_template.cli:prescreen",
    "screen=review_template.cli:screen",
    "pdf_get=review_template.cli:pdf_get",
    "pdf_prep=review_template.cli:pdf_prepare",
    "pdf_prep_man=review_template.cli:pdf_prep_man",
    "pdf_get_man=review_template.cli:pdf_get_man",
    "data=review_template.cli:data",
    "validate=review_template.cli:validate",
    "paper=review_template.cli:paper",
    "trace=review_template.cli:trace",
    "debug=review_template.cli:debug",
]

setup(
    name="review_template",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    python_requires=">=3.6",
    description="Template for git-based literature reviews",
    long_description=readme + "\n\n" + changelog,
    long_description_content_type="text/markdown",
    url="https://github.com/geritwagner/review_template",
    author="Gerit Wagner",
    author_email="gerit.wagner@hec.ca",
    license="MIT license",
    py_modules=["review_template"],
    test_suite="tests",
    tests_require=test_requirements,
    include_package_data=True,
    package_data={
        "review_template": [
            "review_template/template/paper.md",
            "review_template/template/readme.md",
            "review_template/template/.gitattributes",
            "review_template/template/.pre-commit-config.yaml",
        ],
    },
    packages=find_packages(include=["review_template", "review_template.*"]),
    keywords="review_template",
    zip_safe=False,
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Topic :: Scientific/Engineering",
        "Operating System :: OS Independent",
    ],
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "review_template=review_template.cli:main",
        ],
        "review_template.entry_points": entry_points,
    },
    project_urls={
        "Bug Reports": "https://github.com/geritwagner/review_template/issues",
        "Source": "https://github.com/geritwagner/review_template",
    },
)
