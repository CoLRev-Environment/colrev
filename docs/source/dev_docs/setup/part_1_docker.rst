Setup part 1: Docker
------------------------

.. note::
   - If you are running Windows please perform the steps in :doc:`"Windows 10/11: WSL2" </dev_docs/setup/windows_wsl2>`
   - If you are running macOS, please refer to the instructions in :doc:`"Install GitHub Codespaces" </dev_docs/setup/github_codespaces>`
   - If you are using a distribution other than Ubuntu (e.g. Debian, Linux Mint, Kali Linux etc.), please refer to the official install instructions of the Docker Engine (`Install Docker Engine <https://docs.docker.com/engine/install/>`__)

Install **Docker Engine for Ubuntu** with the following commands (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   sudo apt install ca-certificates curl gnupg
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   sudo chmod a+r /etc/apt/keyrings/docker.gpg
   echo \
     "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
     "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
     sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt update
   sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   sudo gpasswd -a $USER docker
   newgrp docker

Please reboot your system afterwards to fully activate docker:

::

   # This command immediately reboots the system, please save any open files beforehand
   sudo reboot
