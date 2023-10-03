Setup
====================================

This document describes the setup of a development environment for the CoLRev project.
Although we only support the systems listed in the compatibility section, useful hints for the setup on other machines can be contributed to this repository (issues or pull-requests).

The setup includes:

-  Python3, pip
-  git
-  Docker
-  CoLRev
-  Continuous integration (pre-commit hooks)
-  Visual Studio Code

**Operating systems**

CoLRev runs on **Linux** distributions and the step-by-step instructions apply to Linux systems.
They are tested for `Ubuntu 22.04.3 LTS <https://ubuntu.com/download/desktop>`__ and `Debian 11.7 “Bullseye” <https://www.debian.org/releases/bullseye/debian-installer/>`__.
Please note that current Non-LTS versions (22.10, 23.04, 23.10) of Ubuntu and Debian 12 “Bookworm” are not supported due to a change in the handling of the `pip package manager <https://itsfoss.com/install-pipx-ubuntu/>`__.
Support for newer Linux distributions is scheduled for April 2024 with the next LTS release of Ubuntu.

**Windows** and **MacOS** do not (yet) support all dependencies required by CoLRev.
The last sections of the setup explain how to setup CoLRev on Windows using the WSL2 and on macOS using a Virtual Machine.

.. toctree::
   :maxdepth: 3
   :caption: Installation instructions

   dev_setup/part_1_git_ssh
   dev_setup/part_2_colrev
   dev_setup/part_3_docker
   dev_setup/macos_vm
   dev_setup/windows_wsl2
