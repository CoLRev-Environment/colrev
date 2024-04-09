#! /usr/bin/env python
"""Manages Docker"""
from __future__ import annotations

import typing
from pathlib import Path

import docker
from docker.errors import DockerException

import colrev.exceptions as colrev_exceptions
from colrev.constants import Colors


class DockerManager:
    """The DockerManager manages everything related to Docker
    (e.g. building images, running containers)"""

    @classmethod
    def build_docker_image(
        cls, *, imagename: str, dockerfile: typing.Optional[Path] = None
    ) -> None:
        """Build a docker image"""

        try:
            client = docker.from_env()
            repo_tags = [t for image in client.images.list() for t in image.tags]

            if imagename not in repo_tags:
                if dockerfile:
                    print(f"Building {imagename} Docker image ...")
                    dockerfile.resolve()
                    client.images.build(
                        path=str(dockerfile.parent).replace("\\", "/"),
                        tag=f"{imagename}:latest",
                    )

                else:
                    print(f"Pulling {imagename} Docker image...")
                    client.images.pull(imagename)
        except DockerException as exc:  # pragma: no cover
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="docker",
                detailed_trace=f"Docker service not available ({exc}). "
                + "Please install/start Docker.",
            ) from exc

    @classmethod
    def check_docker_installed(cls) -> None:  # pragma: no cover
        """Check whether Docker is installed"""

        try:
            client = docker.from_env()
            _ = client.version()
        except docker.errors.DockerException as exc:
            if "PermissionError" in exc.args[0]:
                raise colrev_exceptions.DependencyConfigurationError(
                    "Docker: Permission error. Run "
                    f"{Colors.ORANGE}sudo gpasswd -a $USER docker && "
                    f"newgrp docker{Colors.END}"
                )
            raise colrev_exceptions.MissingDependencyError("Docker")
