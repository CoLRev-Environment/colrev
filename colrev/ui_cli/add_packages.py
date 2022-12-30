#!/usr/bin/env python3
"""Scripts to add packages using the cli."""
from __future__ import annotations

from pathlib import Path

import requests

import colrev.env.package_manager


def add_data(
    *,
    data_operation: colrev.ops.data.Data,
    review_manager: colrev.review_manager.ReviewManager,
    add: str,
) -> None:
    """Add a data package_endpoint"""

    package_manager = review_manager.get_package_manager()
    available_data_endpoints = package_manager.discover_packages(
        package_type=colrev.env.package_manager.PackageEndpointType.data
    )

    if add in available_data_endpoints:
        package_endpoints = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.data,
            selected_packages=[{"endpoint": add}],
            operation=data_operation,
        )
        endpoint = package_endpoints[add]

        default_endpoint_conf = endpoint.get_default_setup()  # type: ignore

        if "colrev_built_in.manuscript" == add:
            if "y" == input("Select a custom word template (y/n)?"):

                template_name = input(
                    'Please copy the word template to " \
                "the project directory and enter the filename.'
                )
                default_endpoint_conf["word_template"] = template_name
            else:
                print("Adding APA as a default")

            if "y" == input("Select a custom citation stlye (y/n)?"):
                print(
                    "Citation stlyes are available at: \n"
                    "https://github.com/citation-style-language/styles"
                )
                csl_link = input("Please select a citation style and provide the link.")
                ret = requests.get(csl_link, allow_redirects=True, timeout=30)
                with open(Path(csl_link).name, "wb") as file:
                    file.write(ret.content)
                default_endpoint_conf["csl_style"] = Path(csl_link).name
            else:
                print("Adding APA as a default")

            data_operation.review_manager.dataset.add_changes(
                path=default_endpoint_conf["csl_style"]
            )
            data_operation.review_manager.dataset.add_changes(
                path=default_endpoint_conf["word_template"]
            )

        data_operation.add_data_endpoint(data_endpoint=default_endpoint_conf)
        data_operation.review_manager.create_commit(
            msg="Add data endpoint",
            script_call="colrev data",
        )

        # Note : reload updated settings
        review_manager = colrev.review_manager.ReviewManager(force_mode=True)
        data_operation = colrev.ops.data.Data(review_manager=review_manager)
    else:
        print("Data format not available")

    data_ret = data_operation.main()
    if data_ret["ask_to_commit"]:
        if "y" == input("Create commit (y/n)?"):
            review_manager.create_commit(msg="Data and synthesis", manual_author=True)


if __name__ == "__main__":
    pass
