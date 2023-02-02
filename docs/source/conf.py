import os
import sys

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
copyright = "2022, Gerit Wagner and Julian Prester"
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
    "sphinxcontrib-bibtex",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_click",
    "m2r2",
    "sphinxcontrib.datatemplates",
    "sphinx_collapse",
]

source_suffix = [".rst", ".md"]

m2r_parse_relative_links = True

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

bibtex_bibfiles = ["references.bib"]

# -- Options for HTML output -------------------------------------------------

# html_theme = "alabaster"

# Readthedocs theme
# on_rtd is whether on readthedocs.org,
# this line of code grabbed from docs.readthedocs.org...
on_rtd = os.environ.get("READTHEDOCS", None) == "True"
if not on_rtd:  # only import and set the theme if we're building docs locally
    import sphinx_rtd_theme

    html_theme = "sphinx_rtd_theme"
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
html_css_files = ["custom.css"]  # Override some CSS settings

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
# html_logo = "logo_small.png"
html_favicon = "favicon.png"

html_context = {
    "display_github": True,  # Integrate GitHub
    "github_user": "geritwagner",  # Username
    "github_repo": "colrev",  # Repo name
    "github_version": "master",  # Version
    "conf_py_path": "docs/source/",  # Path in the checkout to the docs root
}
