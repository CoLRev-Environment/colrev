CoLRev development environment setup
====================================

This document describes the setup of a development environment for the
CoLRev project. Although we only support the systems listed in the
compatibility section, useful hints for the setup on other machines can
be contributed to this repository (issues or pull-requests).

The setup includes: 

-  Python3, pip 
-  git 
-  Docker 
-  CoLRev 
-  Continuous integration (pre-commit hooks) 
-  Visual Studio Code

Compatibility
-------------

Windows: 10/11 via WSL2 with Ubuntu 22.04.3 LTS (`setup with “The one
line
install!” <https://ubuntu.com/tutorials/install-ubuntu-on-wsl2-on-windows-10#3-download-ubuntu>`__)

macOS: via Virtual Machine

Linux: `Ubuntu 22.04.3 LTS <https://ubuntu.com/download/desktop>`__ and
`Debian 11.7
“Bullseye” <https://www.debian.org/releases/bullseye/debian-installer/>`__

Note: Current Non-LTS versions (22.10, 23.04, 23.10) of Ubuntu and
Debian 12 “Bookworm” are not supported due to a change in the handling
of the `pip package
manager <https://itsfoss.com/install-pipx-ubuntu/>`__. Support for newer
Linux distributions is scheduled for April 2024 with the next LTS
release of Ubuntu.

CoLRev Demo via Virtual Machine
-------------------------------

A fully installed VirtualBox image is available
`here <https://gigamove.rwth-aachen.de/de/download/29146e80c3ec3e691e35b4866e9573c9>`__.
If the link has expired, please contact `Gerit
Wagner <mailto:gerit.wagner@uni-bamberg.de>`__.

After unpacking the VirtualBox Image, open the ``colrev_dev.vbox`` file
in `VirtualBox <https://www.virtualbox.org/>`__. To avoid performance
issues, the following settings are recommended:

::

   Set Acceleration manually to KVM, if not already set by default:
   Settings > System > Acceleration > Paravirtualization Interface > KVM

   Allocate at least 4096 MB of system memory to your guest system (Ubuntu recommended requirements):
   Settings > System > Motherboard > set the slider "Base Memory" to 4096 MB or higher (stay within green margin)

   Allocate at least 2 CPU cores to your guest system (Ubuntu recommended requirements):
   Settings > System > Processor > set the slider "Processors" to 2 CPUs (stay within green margin)

   Allocate 128 MB of video memory to your guest system:
   Settings > Display > Screen > set the slider "Video Memory" to 128 MB

   If you encounter any graphical glitches or errors, consider turning off 3D acceleration temporarily:
   Settings > Display > Screen > uncheck "Enabale 3D Acceleration"

Start the machine, and log in (account: ``ubuntu``, password:
``ubuntu``).

Install the guest additions for a better integration between host and
guest system

::

   Open a Terminal an run the following command:
   sudo apt-get install virtualbox-guest-additions-iso

   To activate copy-paste between the VM and your OS:
   Devices > Shared Clipboard > Bidirectional

Update git credentials and setup SSH
------------------------------------

Before using the setup, please update your git credentials (using the
shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``) and pull the latest version of
CoLRev:

::

   git config --global user.name "Lisa Smith"
   git config --global user.email "lisa.smith@stud.uni-bamberg.de"
   git config --global credential.helper store
   cd ~/Desktop/colrev
   git pull

Create an SSH key pair and register the public key at Github
(`steps <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent>`__).

To test colrev, open a Terminal (``Ctrl``\ +\ ``Alt``\ +\ ``T``),
navigate to an empty directory, and run:

::

   colrev init

Installation log
----------------

-  Image: `Ubuntu 22.04.3 LTS <https://ubuntu.com/download/desktop>`__
-  VirtualBox: `Version
   7.0.10 <https://www.virtualbox.org/wiki/Downloads>`__ (no unattended
   installation)
-  Account:

   -  Username: ubuntu
   -  Password: ubuntu

::

   # Install guest additions for Virtual Box
   sudo apt-get install virtualbox-guest-additions-iso

   # Install git, gitk and vim
   sudo apt install git
   sudo apt install gitk
   sudo apt install vim

   # Install visual studio code (via snap)
   sudo snap install --classic code

   # Install docker
   # If you are using a distro other than ubuntu, please replace "ubuntu" in the following links (urls) with your respective distro name
   # Other available distros: "centos", "debian", "fedora", "raspbian" aka Raspberry Pi OS, "rhel" aka Red Hat Enterprise Linux, "sles" aka SUSE Linux Enterprise Server, "static", "ubuntu"
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

   sudo apt install python-is-python3
   sudo apt install python3-pip
   python3 -m pip install --upgrade pip
   python3 -m pip install poetry pytest-mock pylint pytest pre-commit
   python3 -m pip install --upgrade paramiko

   # Clone and install CoLRev on your Desktop
   # Make sure you have registered your SSH key on GitHub beforehand
   cd ~/Desktop
   git clone git@github.com:geritwagner/dev-setup.git
   git clone git@github.com:CoLRev-Environment/colrev.git
   cd colrev
   pip install -e .
   poetry install --with dev
   pre-commit install
   pre-commit run --all

   # Create a testfolder and try out CoLRev
   # Complete run to pull the Docker images, this may be time consuming
   # The status operation will guide you through the whole process
   cd ~/Desktop
   mkdir test
   cd test
   colrev init --example
   colrev status
