.. _Setup docker:

Setup part 1: Docker
------------------------

If you are using a distribution other than ubuntu, please replace "ubuntu" in the following links (urls) with your respective distribution name.

Other available distributions:

- "centos"
- "debian"
- "fedora"
- "raspbian" aka Raspberry Pi OS
- "rhel" aka Red Hat Enterprise Linux
- "sles" aka SUSE Linux Enterprise Server
- "static"
- "ubuntu"

::

   sudo apt install ca-certificates curl gnupg
   sudo install -m 0755 -d /etc/apt/keyrings
   # curl -fsSL https://download.docker.com/linux/"NameOfYourDistro"/gpg
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   sudo chmod a+r /etc/apt/keyrings/docker.gpg
   echo \
      # https://download.docker.com/linux/"NameOfYourDistro" \
     "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
     "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
     sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt update
   sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   sudo gpasswd -a $USER docker
   newgrp docker
   # reboot system to fully load docker
   reboot
