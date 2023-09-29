.. _CoLRev Setup:

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

**Compatibility**

Windows: 10/11 via WSL2 with Ubuntu 22.04.3 LTS (`setup with “The one line install!” <https://ubuntu.com/tutorials/install-ubuntu-on-wsl2-on-windows-10#3-download-ubuntu>`__)

macOS: via Virtual Machine

Linux: `Ubuntu 22.04.3 LTS <https://ubuntu.com/download/desktop>`__ and `Debian 11.7 “Bullseye” <https://www.debian.org/releases/bullseye/debian-installer/>`__

Note: Current Non-LTS versions (22.10, 23.04, 23.10) of Ubuntu and Debian 12 “Bookworm” are not supported due to a change in the handling of the `pip package manager <https://itsfoss.com/install-pipx-ubuntu/>`__.
Support for newer Linux distributions is scheduled for April 2024 with the next LTS release of Ubuntu.

.. toctree::
   :maxdepth: 3
   :caption: Installations

   setup/setup_cli
   setup/setup_distro
   setup/setup_vm
   setup/setup_wsl2
