#! /usr/bin/env python
"""Package init."""
from __future__ import annotations

import inspect
import os
import subprocess
from datetime import datetime
from importlib import import_module
from pathlib import Path

import git
import inquirer
import zope.interface.interface

from colrev.constants import Colors

INTERFACE_MAP = {
    "review_type": "ReviewTypeInterface",
    "search_source": "SearchSourceInterface",
    "prep": "PrepInterface",
    "prep_man": "PrepManInterface",
    "dedupe": "DedupeInterface",
    "prescreen": "PrescreenInterface",
    "pdf_get": "PDFGetInterface",
    "pdf_get_man": "PDFGetManInterface",
    "pdf_prep": "PDFPrepInterface",
    "pdf_prep_man": "PDFPrepManInterface",
    "screen": "ScreenInterface",
    "data": "DataInterface",
}


def _get_default_author() -> dict:
    try:
        name = (
            subprocess.check_output(["git", "config", "--global", "user.name"])
            .decode()
            .strip()
        )
        email = (
            subprocess.check_output(["git", "config", "--global", "user.email"])
            .decode()
            .strip()
        )
        return {"name": name, "email": email}
    except subprocess.CalledProcessError:
        return {}


DEFAULT_AUTHOR = _get_default_author()


# Function to create the pyproject.toml file
def _create_pyproject_toml(data: dict) -> None:
    plugins = "\n".join(
        [
            f'{plugin} = "colrev.packages.genai.src.{module}:{klass}"'
            for plugin, module, klass in zip(
                data["plugins"], data["modules"], data["classes"]
            )
        ]
    )

    content = f"""
[tool.poetry]
name = "{data['name']}"
description = "{data['description']}"
version = "{data['version']}"
license = "{data['license']}"
authors = ["{data['author']['name']} <{data['author']['email']}>"]
repository = "{data['repository']}"

[[tool.poetry.packages]]
include = "src"

[tool.poetry.dependencies]
python = ">=3.9, <4"

[tool.colrev]
colrev_doc_description = "{data['doc_description']}"
colrev_doc_link = "docs/README.md"
search_types = []

[tool.poetry.plugins.colrev]
{plugins}

[build-system]
requires = ["poetry-core>=1.0.0", "cython<3.0"]
build-backend = "poetry.core.masonry.api"
"""
    with open("pyproject.toml", "w", encoding="utf-8") as f:
        f.write(content.strip())


def _create_git_repo() -> None:
    repo_path = os.getcwd()
    repo = git.Repo.init(repo_path)
    repo.git.add(all=True)
    repo.index.commit("Initial commit")


def _create_built_in_package() -> bool:
    questions = [
        inquirer.List(
            "package_type",
            message="Select the package type",
            choices=["Standalone", "Built-in"],
        )
    ]
    data = inquirer.prompt(questions)
    return data["package_type"] == "Built-in"


def _get_package_data(default_package_name: str, built_in: bool) -> dict:
    default_package_name_str = ""
    if default_package_name:
        default_package_name_str = (
            f" [{Colors.GREEN}{default_package_name}{Colors.END}]"
        )

    default_author_str = (
        f"[{Colors.GREEN}{DEFAULT_AUTHOR['name']} "
        + f"<{DEFAULT_AUTHOR['email']}>{Colors.END}]"
    )
    questions = [
        inquirer.Text(
            "name",
            message=f"Enter the package name, e.g., colrev.genai{default_package_name_str}",
        ),
        inquirer.Text("description", message="Enter the package description"),
        inquirer.Text(
            "doc_description",
            message="Enter short description string for the CoLRev docs list",
        ),
        inquirer.Text(
            "version",
            message=f"Enter the package version number [{Colors.GREEN}0.1.0{Colors.END}]",
        ),
        inquirer.Text(
            "license",
            message=f"Enter the package license [{Colors.GREEN}MIT{Colors.END}]",
        ),
        inquirer.Text(
            "author",
            message=f"Enter the author name {default_author_str}",
        ),
    ]
    if not built_in:
        questions.append(
            inquirer.Text("repository", message="Enter the URL of the repository"),
        )

    questions.append(
        inquirer.Checkbox(
            "plugins",
            message="Select the plugin types",
            choices=list(INTERFACE_MAP.keys()),
        )
    )

    package_data = inquirer.prompt(questions)

    if built_in:
        package_data["repository"] = (
            f"https://github.com/CoLRev-Environment/colrev/tree/"
            f"main/colrev/packages/{package_data['name']}"
        )

    if not package_data["version"]:
        package_data["version"] = "0.1.0"
    if not package_data["license"]:
        package_data["license"] = "MIT"
    if not package_data["author"]:
        # pylint: disable=colrev-missed-constant-usage
        package_data["author"] = DEFAULT_AUTHOR
    if not package_data["name"]:
        package_data["name"] = default_package_name
    if not package_data["repository"]:
        package_data["repository"] = "TODO"

    package_data["doc_description"] = "TODO"
    # package_data['author'] = [author.strip() for author in package_data['author'].split(',')]

    plugin_questions = []
    for plugin in package_data["plugins"]:
        plugin_questions.extend(
            [
                inquirer.Text(
                    f"module_{plugin}", message=f"Enter the module name for {plugin}"
                ),
                inquirer.Text(
                    f"class_{plugin}", message=f"Enter the class name for {plugin}"
                ),
            ]
        )

    plugin_data = inquirer.prompt(plugin_questions)

    package_data["modules"] = [
        plugin_data[f"module_{plugin}"] for plugin in package_data["plugins"]
    ]
    package_data["classes"] = [
        plugin_data[f"class_{plugin}"] for plugin in package_data["plugins"]
    ]
    return package_data


def _generate_method_signatures(module_path: str, class_name: str) -> list:
    module = import_module(module_path)
    interface_class = getattr(module, class_name)
    members = inspect.getmembers(interface_class)

    interface_class_attrs = next(
        (member for member in members if member[0] == "_InterfaceClass__attrs"), None
    )
    if interface_class_attrs:
        attrs_dict = interface_class_attrs[1]

        method_signatures = []

        for name, attr in attrs_dict.items():
            if isinstance(attr, zope.interface.interface.Attribute) and not isinstance(
                attr, zope.interface.interface.Method
            ):
                method_signatures.append(f"   {name} = '' #TODO\n")
        method_signatures.append("\n")

        method_signatures.append("   def __init__(self) -> None:\n")
        method_signatures.append("      pass\n\n")

        for name, attr in attrs_dict.items():
            if isinstance(attr, zope.interface.interface.Method):
                method_signatures.append(
                    f"   def {name}{attr.getSignatureString()}:\n"
                    f'      """{attr.getDoc()}"""\n      # TODO\n\n'
                )

        return method_signatures

    return ["Attribute '_InterfaceClass__attrs' not found."]


def _create_module_files(package_data: dict) -> None:

    os.makedirs("src", exist_ok=True)

    for plugin, module, class_name in zip(
        package_data["plugins"], package_data["modules"], package_data["classes"]
    ):
        file_path = os.path.join("src", f"{module}.py")
        interface = INTERFACE_MAP[plugin]

        module_path = "colrev.package_manager.interfaces"
        method_signatures = _generate_method_signatures(module_path, interface)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(
                f'''#! /usr/bin/env python
"""{interface}: {class_name}"""

from zope.interface import implementer
from colrev.package_manager.interfaces import {interface}

@implementer({interface})
class {class_name}:

'''
            )
            for signature in method_signatures:
                f.write(signature)


def _create_src_init(package_data: dict) -> None:

    with open("src/__init__.py", "w", encoding="utf-8") as f:
        f.write(
            f'''"""Package for {package_data['name']}."""

    __author__ = "{package_data['author']['name']}"
    __email__ = "{package_data['author']['email']}"'''
        )


def _create_docs_readme() -> None:

    Path("docs").mkdir()

    with open("docs/README.md", "w", encoding="utf-8") as f:
        f.write("""# TODO : Docs""")


def _create_readme(package_data: dict) -> None:
    print(f"TODO : take infos from {package_data}")

    with open("README.md", "w", encoding="utf-8") as f:
        f.write("""# TODO : README""")


def _create_license_file(package_data: dict) -> None:

    license_file_path = "LICENSE"
    license_text = _get_license_text(package_data)
    with open(license_file_path, "w", encoding="utf-8") as f:
        f.write(license_text)


def _get_license_text(package_data: dict) -> str:
    license_name = package_data["license"]

    current_year = datetime.now().year
    license_texts = {
        "MIT": f"""MIT License

        Copyright (c) [{current_year}] [{package_data['author']['name']}]

        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.""",
        # Add more license texts for other licenses if needed
    }

    license_text = license_texts.get(license_name, "")

    return license_text


def _create_pre_commit_hooks() -> None:

    pre_commit_hooks = """
repos:
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
    -   id: trailing-whitespace
    -   id: end-of-file-fixer
        exclude: bib$|txt$|ris$|enl$|xml$
    -   id: check-docstring-first
    -   id: check-json
    -   id: check-yaml
    -   id: check-toml
    -   id: debug-statements
    -   id: name-tests-test
-   repo: https://github.com/psf/black-pre-commit-mirror
    rev: 24.4.2
    hooks:
      - id: black
        language_version: python3
-   repo: https://github.com/PyCQA/autoflake
    rev: v2.3.1
    hooks:
    -   id: autoflake
-   repo: https://github.com/PyCQA/flake8
    rev: 7.1.0
    hooks:
    -   id: flake8
        additional_dependencies: [flake8-typing-imports==1.12.0]
        args: ['--max-line-length=110', '--extend-ignore=E203,TYP006']
-   repo: https://github.com/asottile/reorder-python-imports
    rev: v3.13.0
    hooks:
    -   id: reorder-python-imports
        args: [--py3-plus]
-   repo: https://github.com/asottile/pyupgrade
    rev: v3.16.0
    hooks:
    -   id: pyupgrade
        args: [--py36-plus, --keep-runtime-typing]
-   repo: https://github.com/pre-commit/mirrors-mypy
    rev: 'v1.11.0'
    hooks:
    -   id: mypy
        args: [--disallow-untyped-defs, --disallow-incomplete-defs, --disallow-untyped-calls]
        additional_dependencies: [types-toml]
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.5.4
  hooks:
    - id: ruff # runs faster than pylint
      args: [--fix, --exit-non-zero-on-fix]
- repo: local
  hooks:
    - id: pylint
      name: pylint
      entry: pylint
      language: system
      types: [python]
      files: colrev
      args:
        [
          "-rn", # Only display messages
          "-sn", # Don't display the score
        ]
"""
    with open(".pre-commit-config.yaml", "w", encoding="utf-8") as f:
        f.write(pre_commit_hooks)


def main() -> None:
    """Main function to create a CoLRev package."""

    built_in = _create_built_in_package()
    if built_in:

        packages_dir = Path(__file__).resolve().parent.parent / "packages"
        print(packages_dir)
        default_package_name = "NONE"

    else:

        current_dir = Path.cwd()
        if any(Path(current_dir).iterdir()):
            print(
                "The current directory is not empty. Please select an empty directory."
            )
            return

        default_package_name = current_dir.name

    package_data = _get_package_data(default_package_name, built_in)

    _create_pyproject_toml(package_data)
    _create_module_files(package_data)
    _create_src_init(package_data)
    _create_readme(package_data)
    _create_license_file(package_data)
    _create_pre_commit_hooks()
    _create_docs_readme()
    _create_git_repo()

    # tests
    # gh-actions: pypi-publishing setup
