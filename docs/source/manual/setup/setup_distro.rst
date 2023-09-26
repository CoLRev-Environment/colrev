Install docker
--------------
If you are using a distro other than ubuntu, please replace "ubuntu" in the following links (urls) with your respective distro name
Other available distros:

- "centos"
- "debian"
- "fedora"
- "raspbian" aka Raspberry Pi OS
- "rhel" aka Red Hat Enterprise Linux
- "sles" aka SUSE Linux Enterprise Server
- "static"
- "ubuntu"

TODO: add a $mydistro variable into the script

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
