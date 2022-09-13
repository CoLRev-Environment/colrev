#! /usr/bin/env python
from __future__ import annotations

import importlib
import json
import sys
import typing
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import zope.interface
from zope.interface.verify import verifyObject

import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record


class PackageType(Enum):
    # pylint: disable=C0103
    load_conversion = "load_conversion"
    search_source = "search_source"
    prep = "prep"
    prep_man = "prep_man"
    dedupe = "dedupe"
    prescreen = "prescreen"
    pdf_get = "pdf_get"
    pdf_get_man = "pdf_get_man"
    pdf_prep = "pdf_prep"
    pdf_prep_man = "pdf_prep_man"
    screen = "screen"
    data = "data"


class SearchSourcePackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")
    source_identifier = zope.interface.Attribute("""Source identifier for provenance""")
    source_identifier_search = zope.interface.Attribute(
        """Source identifier for search (corretions?)"""
    )

    search_mode = zope.interface.Attribute("""Mode""")

    # pylint: disable=no-self-argument
    def run_search(search_operation) -> None:
        pass

    # pylint: disable=no-self-argument
    def heuristic(filename, data):
        pass

    def load_fixes(load_operation, source, records):
        """SearchSource-specific fixes to ensure that load_records (from .bib) works"""

    def prepare(record):
        pass


class LoadConversionPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class
    """Interface for packages that load records from different filetypes"""

    settings_class = zope.interface.Attribute("""Class for the package settings""")
    supported_extensions = zope.interface.Attribute("""List of supported extensions""")

    # pylint: disable=no-self-argument
    def load(load_operation, source):
        pass


class PrepPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")
    source_correction_hint = zope.interface.Attribute(
        """Hint on how to correct metadata at source"""
    )

    always_apply_changes = zope.interface.Attribute(
        """Flag indicating whether changes should always be applied
        (even if the colrev_status does not transition to md_prepared)"""
    )

    # pylint: disable=no-self-argument
    def prepare(prep_operation, prep_record):
        pass


class PrepManPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def prepare_manual(prep_man_operation, records):
        pass


class DedupePackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def run_dedupe(dedupe_operation):
        pass


class PrescreenPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def run_prescreen(prescreen_operation, records: dict, split: list) -> dict:
        pass


class PDFGetPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def get_pdf(pdf_get_operation, record):
        return record


class PDFGetManPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def get_man_pdf(pdf_get_man_operation, records):
        return records


class PDFPrepPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=unused-argument
    # pylint: disable=no-self-argument
    def prep_pdf(pdf_prep_operation, record, pad) -> dict:
        return record.data


class PDFPrepManPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def prep_man_pdf(pdf_prep_man_operation, records):
        return records


class ScreenPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    def run_screen(screen_operation, records: dict, split: list) -> dict:
        pass


class DataPackageInterface(
    zope.interface.Interface
):  # pylint: disable=inherit-non-class

    settings_class = zope.interface.Attribute("""Class for the package settings""")

    # pylint: disable=no-self-argument
    # pylint: disable=no-method-argument
    def get_default_setup() -> dict:  # type: ignore
        return {}

    def update_data(
        data_operation, records: dict, synthesized_record_status_matrix: dict
    ) -> None:
        pass

    def update_record_status_matrix(
        data_operation, synthesized_record_status_matrix, endpoint_identifier
    ) -> None:
        pass


@dataclass
class DefaultSettings:
    name: str


@dataclass
class DefaultSourceSettings:
    # pylint: disable=duplicate-code
    # pylint: disable=too-many-instance-attributes
    name: str
    filename: Path
    search_type: colrev.settings.SearchType
    source_name: str
    source_identifier: str
    search_parameters: dict
    load_conversion_script: dict
    comment: typing.Optional[str]


class PackageManager:

    endpoint_overview = [
        {
            "package_type": PackageType.load_conversion,
            "import_name": LoadConversionPackageInterface,
            "custom_class": "CustomLoad",
            "operation_name": "load_operation",
        },
        {
            "package_type": PackageType.search_source,
            "import_name": SearchSourcePackageInterface,
            "custom_class": "CustomSearchSource",
            "operation_name": "source_operation",
        },
        {
            "package_type": PackageType.prep,
            "import_name": PrepPackageInterface,
            "custom_class": "CustomPrep",
            "operation_name": "prep_operation",
        },
        {
            "package_type": PackageType.prep_man,
            "import_name": PrepManPackageInterface,
            "custom_class": "CustomPrepMan",
            "operation_name": "prep_man_operation",
        },
        {
            "package_type": PackageType.dedupe,
            "import_name": DedupePackageInterface,
            "custom_class": "CustomDedupe",
            "operation_name": "dedupe_operation",
        },
        {
            "package_type": PackageType.prescreen,
            "import_name": PrescreenPackageInterface,
            "custom_class": "CustomPrescreen",
            "operation_name": "prescreen_operation",
        },
        {
            "package_type": PackageType.pdf_get,
            "import_name": PDFGetPackageInterface,
            "custom_class": "CustomPDFGet",
            "operation_name": "pdf_get_operation",
        },
        {
            "package_type": PackageType.pdf_get_man,
            "import_name": PDFGetManPackageInterface,
            "custom_class": "CustomPDFGetMan",
            "operation_name": "pdf_get_man_operation",
        },
        {
            "package_type": PackageType.pdf_prep,
            "import_name": PDFPrepPackageInterface,
            "custom_class": "CustomPDFPrep",
            "operation_name": "pdf_prep_operation",
        },
        {
            "package_type": PackageType.pdf_prep_man,
            "import_name": PDFPrepManPackageInterface,
            "custom_class": "CustomPDFPrepMan",
            "operation_name": "pdf_prep_man_operation",
        },
        {
            "package_type": PackageType.screen,
            "import_name": ScreenPackageInterface,
            "custom_class": "CustomScreen",
            "operation_name": "screen_operation",
        },
        {
            "package_type": PackageType.data,
            "import_name": DataPackageInterface,
            "custom_class": "CustomData",
            "operation_name": "data_operation",
        },
    ]

    package: typing.Dict[str, typing.Dict[str, typing.Dict]]

    def __init__(
        self,
    ) -> None:

        self.packages = self.load_package_index()
        self.__flag_installed_packages()

    def load_package_index(self):

        # TODO : the list of packages should be curated
        # (like CRAN: packages that meet *minimum* requirements)
        # We should not load any package that matches the colrev* on PyPI
        # (security/quality issues...)

        # We can start by using/updating the following dictionary/json-file.
        # At some point, we may decide to move it to a separate repo/index.

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/packages.json")
        )
        if not filedata:
            raise colrev_exceptions.CoLRevException(
                "Package index not available (colrev/template/packages.json)"
            )

        package_dict = json.loads(filedata.decode("utf-8"))

        packages = {}
        for key, value in package_dict.items():
            packages[PackageType[key]] = value
            for package_identifier, package_path in value.items():
                assert " " not in package_identifier
                assert " " not in package_path
                assert package_identifier.islower()

        # TODO : testing: validate the structure of packages.json
        # and whether all endpoints are available

        # Note : parsing to a dataclass may not have many advantages
        # because the discover_packages and load_packages access the
        # packages through strings anyway

        return packages

    def __flag_installed_packages(self) -> None:
        for package_type, package in self.packages.items():
            for package_identifier, discovered_package in package.items():
                try:
                    self.load_package_endpoint(
                        package_type=package_type, package_identifier=package_identifier
                    )
                    discovered_package["installed"] = True
                except (AttributeError, ModuleNotFoundError):
                    discovered_package["installed"] = False

    def get_package_details(
        self, *, package_type: PackageType, package_identifier
    ) -> dict:
        package_identifier = package_identifier.lower()
        package_details = {"name": package_identifier}
        package_class = self.load_package_endpoint(
            package_type=package_type, package_identifier=package_identifier
        )
        package_details["description"] = package_class.__doc__
        package_details["parameters"] = {}
        settings_class = getattr(package_class, "settings_class", None)
        if settings_class is None:
            msg = f"{package_identifier} could not be loaded"
            raise colrev_exceptions.ServiceNotAvailableException(msg)

        if "DefaultSettings" == settings_class.__name__ or not settings_class:
            return package_details

        for parameter in [
            i for i in settings_class.__annotations__.keys() if i[:1] != "_"
        ]:

            # default value: determined from class.__dict__
            # merging_non_dup_threshold: float= 0.7
            if parameter in settings_class.__dict__:
                package_details["parameters"][parameter][
                    "default"
                ] = settings_class.__dict__[parameter]

            # not required: determined from typing annotation
            # variable_name: typing.Optional[str]
            package_details["parameters"][parameter] = {"required": True}

            # "type":
            # determined from typing annotation
            if parameter in settings_class.__annotations__:
                type_annotation = settings_class.__annotations__[parameter]
                if "typing.Optional" in type_annotation:
                    package_details["parameters"][parameter]["required"] = False

                if "typing.Optional[int]" == type_annotation:
                    type_annotation = "int"
                if "typing.Optional[float]" == type_annotation:
                    type_annotation = "float"
                if "typing.Optional[bool]" == type_annotation:
                    # TODO : required=False for boolean?!
                    type_annotation = "bool"
                # typing.Optional[list] : multiple_selection?
                package_details["parameters"][parameter]["type"] = type_annotation

            # tooltip, min, max, options: determined from settings_class._details dict
            # Note : tooltips are not in docstrings because
            # attribute docstrings are not supported (https://peps.python.org/pep-0224/)
            # pylint: disable=protected-access
            if parameter in settings_class._details:
                if "tooltip" in settings_class._details[parameter]:
                    package_details["parameters"][parameter][
                        "tooltip"
                    ] = settings_class._details[parameter]["tooltip"]

                if "min" in settings_class._details[parameter]:
                    package_details["parameters"][parameter][
                        "min"
                    ] = settings_class._details[parameter]["min"]

                if "max" in settings_class._details[parameter]:
                    package_details["parameters"][parameter][
                        "max"
                    ] = settings_class._details[parameter]["max"]

                if "options" in settings_class._details[parameter]:
                    package_details["parameters"][parameter][
                        "options"
                    ] = settings_class._details[parameter]["options"]

        # TODO apply validation when parsing settings during package init (based on _details)

        # TODO (later) : package version?

        return package_details

    def discover_packages(
        self, *, package_type: PackageType, installed_only: bool = False
    ) -> typing.Dict:

        discovered_packages = self.packages[package_type]
        for package_identifier, package in discovered_packages.items():
            if installed_only and not package["installed"]:
                continue
            package_class = self.load_package_endpoint(
                package_type=package_type, package_identifier=package_identifier
            )
            discovered_packages[package_identifier] = package
            discovered_packages[package_identifier][
                "description"
            ] = package_class.__doc__
            discovered_packages[package_identifier]["installed"] = package["installed"]

        return discovered_packages

    def load_package_endpoint(
        self, *, package_type: PackageType, package_identifier: str
    ):
        package_identifier = package_identifier.lower()
        package_str = self.packages[package_type][package_identifier]["endpoint"]
        package_module = package_str.rsplit(".", 1)[0]
        package_class = package_str.rsplit(".", 1)[-1]
        imported_package = importlib.import_module(package_module)
        package_class = getattr(imported_package, package_class)
        return package_class

    def load_packages(
        self,
        *,
        package_type: PackageType,
        selected_packages: list,
        process: colrev.process.Process,
        ignore_not_available: bool = False,
        instantiate_objects=True,
    ) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
        # pylint: disable=import-outside-toplevel
        # pylint: disable=unnecessary-dict-index-lookup
        # Note : when iterating over packages_dict.items(),
        # changes to the values (or del k) would not persist

        # TODO : generally change from process.type to package_type
        # (each process can involve different endpoints)

        # avoid changes in the config
        selected_packages = deepcopy(selected_packages)
        packages_dict: typing.Dict = {}
        for selected_package in selected_packages:

            # quick fix:
            if "endpoint" not in selected_package:
                selected_package["endpoint"] = selected_package["source_name"]

            package_identifier = selected_package["endpoint"].lower()
            packages_dict[package_identifier] = {}

            packages_dict[package_identifier]["settings"] = selected_package
            # 1. Load built-in packages
            # if package_identifier in cls.packages[process.type]
            if package_identifier in self.packages[package_type]:
                if not self.packages[package_type][package_identifier]["installed"]:
                    print(f"Cannot load {package_identifier} (not installed)")
                    continue

                if self.packages[package_type][package_identifier]["installed"]:
                    packages_dict[package_identifier][
                        "endpoint"
                    ] = self.load_package_endpoint(
                        package_type=package_type, package_identifier=package_identifier
                    )

            # 2. Load module packages
            # TODO : test the module prep_scripts
            elif not Path(package_identifier + ".py").is_file():
                try:
                    packages_dict[package_identifier]["settings"] = selected_package
                    packages_dict[package_identifier][
                        "endpoint"
                    ] = importlib.import_module(package_identifier)
                    packages_dict[package_identifier]["custom_flag"] = True
                except ModuleNotFoundError as exc:
                    if ignore_not_available:
                        del packages_dict[package_identifier]
                        continue
                    raise colrev_exceptions.MissingDependencyError(
                        "Dependency " + f"{package_identifier} not found. "
                        "Please install it\n  pip install "
                        f"{package_type} {package_identifier}"
                    ) from exc

            # 3. Load custom packages in the directory
            elif Path(package_identifier + ".py").is_file():
                sys.path.append(".")  # to import custom packages from the project dir
                packages_dict[package_identifier]["settings"] = selected_package
                packages_dict[package_identifier]["endpoint"] = importlib.import_module(
                    package_identifier, "."
                )
                packages_dict[package_identifier]["custom_flag"] = True
            else:
                print(f"Could not load {selected_package}")
                continue

            packages_dict[package_identifier]["settings"]["name"] = packages_dict[
                package_identifier
            ]["settings"]["endpoint"]
            del packages_dict[package_identifier]["settings"]["endpoint"]

        try:
            package_details = next(
                item
                for item in self.endpoint_overview
                if item["package_type"] == package_type
            )
        except StopIteration as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"package_type {package_type} not available"
            ) from exc

        broken_packages = []
        for k, val in packages_dict.items():
            if "custom_flag" in val:
                try:
                    packages_dict[k]["endpoint"] = getattr(  # type: ignore
                        val["endpoint"], package_details["custom_class"]
                    )
                    del packages_dict[k]["custom_flag"]
                except AttributeError:
                    # Note : these may also be (package name) conflicts
                    broken_packages.append(k)

        for k in broken_packages:
            print(f"Skipping broken package ({k})")
            packages_dict.pop(k, None)

        endpoint_class = package_details["import_name"]  # type: ignore
        for package_identifier, package_class in packages_dict.items():
            params = {
                package_details["operation_name"]: process,
                "settings": package_class["settings"],
            }
            if "search_source" == package_type:
                del params["check_operation"]

            if instantiate_objects:
                packages_dict[package_identifier] = package_class["endpoint"](**params)
                verifyObject(endpoint_class, packages_dict[package_identifier])
            else:
                packages_dict[package_identifier] = package_class["endpoint"]

        return packages_dict


if __name__ == "__main__":
    pass
