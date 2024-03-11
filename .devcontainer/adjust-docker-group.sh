#!/bin/bash
# Adjust the Docker group ID to match the host's Docker socket group ID, then execute the original command.
SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)
groupmod -g $SOCKET_GID docker

docker pull pandoc/latex:3.1
docker pull lfoppiano/grobid:0.7.3

exec "$@"
