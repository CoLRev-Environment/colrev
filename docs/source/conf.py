import os
import sys
from datetime import datetime

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
author = "Gerit Wagner and Julian Prester"
copyright = f"{datetime.now().year}, {author}"

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

html_baseurl = "https://colrev-environment.github.io/colrev/"

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

html_theme = "sphinx_rtd_theme"
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

html_context = {
    "display_github": True,  # Integrate GitHub
    "github_user": "CoLRev-Environment",  # Username
    "github_repo": "colrev",  # Repo name
    "github_version": "main",  # Version
    "conf_py_path": "/docs/source/",  # Path in the checkout to the docs root
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


def skip_member(app, what, name, obj, skip, options):  # type: ignore
    # Define members to skip (including private and internal Pydantic members)
    excluded_members = [
        "model_computed_fields",
        "model_config",
        "model_extra",
        "model_fields",
        "model_fields_set",
        "construct",
        "copy",
        "dict",
        "from_orm",
        "json",
        "model_construct",
        "model_copy",
        "model_dump",
        "model_dump_json",
        "model_json_schema",
        "model_parametrized_name",
        "model_post_init",
        "model_rebuild",
        "model_validate",
        "model_validate_json",
        "model_validate_strings",
        "parse_file",
        "parse_obj",
        "parse_raw",
        "schema",
        "schema_json",
        "update_forward_refs",
        "validate",
    ]

    if name in excluded_members or name.startswith("_"):
        return True
    return skip


def setup(app):  # type: ignore
    app.connect("autodoc-skip-member", skip_member)
