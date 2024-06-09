import os
import sys

import sphinx_rtd_theme

try:
    from colrev import __version__ as colrev_version
except Exception:
    colrev_version = ""

# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# Problems with imports? Could try `export PYTHONPATH=$PYTHONPATH:`pwd``
# from root project dir...

sys.path.insert(
    0, os.path.abspath("../../colrev")
)  # Source code dir relative to this file
sys.path.insert(
    0, os.path.abspath("../../colrev")
)  # Source code dir relative to this file

# -- Project information -----------------------------------------------------

project = "CoLRev"
copyright = "2023, Gerit Wagner and Julian Prester"
author = "Gerit Wagner and Julian Prester"

# The full version, including alpha/beta/rc tags
release = colrev_version

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_click",
    "sphinxcontrib.datatemplates",
    "sphinx_collapse",
    "repoze.sphinx.autointerface",
    "sphinx_design",
    "sphinx_copybutton",
]


autosummary_generate = True  # Turn on sphinx.ext.autosummary
autoclass_content = "both"  # Add __init__ doc (ie. params) to class summaries
html_show_sourcelink = (
    False  # Remove 'view source code' from top of page (for html, not python)
)
autodoc_inherit_docstrings = True  # If no docstring, inherit from base class
set_type_checking_flag = True  # Enable 'expensive' imports for sphinx_autodoc_typehints
add_module_names = False  # Remove namespaces from class/method signatures

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# -- Options for HTML output -------------------------------------------------

# html_theme = "alabaster"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
# html_logo = "logo_small.png"
html_favicon = "favicon.png"
html_css_files = [
    "css/asciinema-player.css",
    "css/custom.css",
    "css/jquery.dataTables.min.css",
]

html_js_files = [
    "js/asciinema-player.min.js",
    "js/jquery-3.5.1.js",
    "js/jquery.dataTables.min.js",
    "js/main.js",
]

# Readthedocs theme
# on_rtd is whether on readthedocs.org,
# this line of code grabbed from docs.readthedocs.org...
on_rtd = os.environ.get("READTHEDOCS", None) == "True"
# if not on_rtd:  # only import and set the theme if we're building docs locally

html_theme = "sphinx_rtd_theme"
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

html_context = {
    "display_github": True,  # Integrate GitHub
    "github_user": "CoLRev-Environment",  # Username
    "github_repo": "colrev",  # Repo name
    "github_version": "master",  # Version
    "conf_py_path": "docs/source/",  # Path in the checkout to the docs root
    "meta_http_equiv": True,  # for asciinema
    "html5_doctype": True,  # for asciinema
}

linkcheck_ignore = [
    r"http://bibutils.refbase.org/|"
    + r"https://www.sciencedirect.com/.*"
    + r"|https://www.tandfonline.com.*"
    + r"|https://onlinelibrary.wiley.com"
    + r"|https://www.webofknowledge.com"
    + r"|https://ieeexploreapi.ieee.org"
    + r"|https://ieeexplore.ieee.org"
    + r"|http://www.scopus.com"
]
