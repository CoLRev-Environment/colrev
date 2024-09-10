#!/usr/bin/env python
"""Testing docker manager"""
import os
from pathlib import Path

import docker

import colrev.env.docker_manager


def continue_test() -> bool:
    """Skip test if running inside CI"""
    return not any(
        "true" == os.getenv(x)
        for x in ["GITHUB_ACTIONS", "CIRCLECI", "TRAVIS", "GITLAB_CI"]
    )


def test_build_docker_image(tmp_path) -> None:  # type: ignore
    def remove_docker_image(image_name: str) -> None:
        client = docker.from_env()
        try:
            client.images.remove(image_name)
            print(f"Image '{image_name}' removed successfully.")
        except docker.errors.ImageNotFound:
            print(f"Image '{image_name}' not found.")

    def remove_docker_container(container_name: str) -> None:
        client = docker.from_env()
        containers = client.containers.list(
            all=True, filters={"ancestor": container_name}
        )
        for container in containers:
            container.remove()

    # Do not run on macOS (GH-Actions) as Docker is not available
    if os.getenv("RUNNER_OS") == "macOS":
        return

    remove_docker_container("hello-world:latest")
    remove_docker_image("hello-world:latest")
    colrev.env.docker_manager.DockerManager.build_docker_image(
        imagename="hello-world:latest"
    )
    remove_docker_container("hello-world:latest")
    remove_docker_image("hello-world:latest")

    # Docker not available on Windows (GH-Actions)
    if not continue_test():
        return

    # Create a simple Dockerfile
    dockerfile_content = """
    FROM python:3.9
    WORKDIR /app
    COPY . /app
    """

    # Save the Dockerfile
    dockerfile_path = tmp_path / Path("Dockerfile")
    with open(dockerfile_path, "w") as file:
        file.write(dockerfile_content)

    # Build the Docker image
    colrev.env.docker_manager.DockerManager.build_docker_image(
        imagename="testimage:latest", dockerfile=dockerfile_path
    )
    remove_docker_container("testimage:latest")
    remove_docker_image("testimage:latest")
