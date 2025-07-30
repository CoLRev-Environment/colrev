# Extend the specified Python image
FROM mcr.microsoft.com/vscode/devcontainers/python:3.12-bullseye

# Install Docker CLI
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && apt-get install -y docker-ce-cli

# Add and setup the vscode user, attempt to handle Docker group dynamically
ARG DOCKER_GROUP_GID=800 # Provide a default GID to use if not passed as build arg
RUN groupadd -g $DOCKER_GROUP_GID docker || true # Ignore if group already exists
RUN useradd -m vscode -G docker || usermod -aG docker vscode # Add vscode user or append to docker group

COPY .bash_aliases /home/vscode/.bash_aliases

# Copy and adjust permissions for the startup script
COPY dockerfile_entrypoint.sh /usr/local/bin/dockerfile_entrypoint.sh
RUN chmod +x /usr/local/bin/dockerfile_entrypoint.sh

# Install colrev from the Git repository
# RUN pip install "colrev[dev] @ git+https://github.com/CoLRev-Environment/colrev"
# RUN pip install -e .[dev,docs]
# COPY . /workspaces/colrev
# WORKDIR /workspaces/colrev
# RUN pip install -e .[dev]
# RUN pre-commit run --all

# Use the dockerfile_entrypoint.sh script as an entry point to adjust the docker group ID at runtime
ENTRYPOINT ["/usr/local/bin/dockerfile_entrypoint.sh"]

# Specify the default command, if any, or override with your own command
CMD ["bash"]
