#!/usr/bin/env python
from setuptools import find_packages
from setuptools import setup

import versioneer

with open("README.md") as readme_file:
    readme = readme_file.read()

with open("CHANGELOG.md") as changelog_file:
    changelog = changelog_file.read()

requirements = [
    "alphabet_detector==0.0.7",
    "ansiwrap==0.8.4",
    "bashplotlib==0.6.5",
    "bibtexparser==1.2.0",
    "beautifulsoup4==4.10.0",
    "Click==8.0.4",
    "click_completion==0.5.2",
    "crossrefapi==1.5.0",
    "cx_Freeze==6.10",
    "daff==1.3.46",
    "dictdiffer==0.8.1",
    "docker==5.0.3",
    "GitPython==3.1.24",
    "ImageHash==4.2.0",
    "lingua-language-detector==1.0.1",
    "lxml==4.5.0",
    "nameparser==1.0.6",
    "opensearch-py==1.1.0",
    "pandas==1.2.5",
    "pdfminer.six==20211012",
    "pdf2image==1.16.0",
    "pathos==0.2.8",
    "pandasql==0.7.3",
    "PyPDF2==1.26.0",
    "PyYAML==6.0",
    "p_tqdm==1.3.3",
    "pybtex==0.24.0",
    "requests==2.27.1",
    "requests-cache==0.9.3",
    "thefuzz==0.19.0",
    "tqdm==4.61.1",
    "transitions==0.8.10",
    "timeout_decorator==0.5.0",
    "zope.interface==5.4.0",
]
# 'configparser>=5.0'


test_requirements = ["pytest>=3", "attrs>=19.2.0", "packaging>=21.0"]


entry_points = [
    "debug=colrev_core.cli:debug",
]

setup(
    name="colrev_core",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    python_requires=">=3.6",
    description="Core engine for CoLRev (colaborative literature reviews)",
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
            "lexicon/*",
            "lexicon/.*",
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
