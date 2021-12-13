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
    "debug=colrev_core.cli:debug",
]

setup(
    name="colrev_core",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    python_requires=">=3.6",
    description="Template for git-based literature reviews",
    long_description=readme + "\n\n" + changelog,
    long_description_content_type="text/markdown",
    url="https://github.com/geritwagner/colrev_core",
    author="Gerit Wagner",
    author_email="gerit.wagner@hec.ca",
    license="MIT license",
    py_modules=["colrev_core"],
    test_suite="tests",
    tests_require=test_requirements,
    include_package_data=True,
    package_data={
        "colrev_core": [
            "template/*",
            "template/.*",
        ],
    },
    packages=find_packages(include=["colrev_core", "colrev_core.*"]),
    keywords="colrev_core",
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
            "colrev_core=colrev_core.cli:main",
        ],
        "colrev_core.entry_points": entry_points,
    },
    project_urls={
        "Bug Reports": "https://github.com/geritwagner/colrev_core/issues",
        "Source": "https://github.com/geritwagner/colrev_core",
    },
)
