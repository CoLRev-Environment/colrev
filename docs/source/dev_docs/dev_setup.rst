.. _CoLRev Setup:

Setup
====================================

This document describes the setup of a development environment for the CoLRev project.
Although we only support the systems listed in the table below, useful hints for the setup on other machines can be contributed to this repository (issues or pull-requests).

**Supported operating systems and setup methods:**

 =========== ============ ====== ============
  OS/Setup    Native       WSL2   VirtualBox
 =========== ============ ====== ============
    Linux        yes        no     yes
  Win 10/11      no         yes    yes
    macOS        no         no     yes
 =========== ============ ====== ============

**The setup also includes:**

-  Docker
-  git
-  Visual Studio Code
-  Python3, pip
-  CoLRev
-  Continuous integration (pre-commit hooks)

For best performance and user experience, it is best to run CoLRev natively on Linux or via WSL2 on Windows. For testing purposes or macOS, using the pre-configured virtual machine on VirtualBox is feasible, but performance is highly dependent on powerful hardware.

CoLRev runs natively on **Linux** distributions and the step-by-step instructions apply to Linux systems.
They are tested for `Ubuntu 22.04.3 LTS <https://ubuntu.com/download/desktop>`__ and `Debian 11.7 “Bullseye” <https://www.debian.org/releases/bullseye/debian-installer/>`__.
Please note that current Non-LTS versions (22.10, 23.04, 23.10) of Ubuntu and Debian 12 “Bookworm” are not supported due to a change in the handling of the `pip package manager <https://itsfoss.com/install-pipx-ubuntu/>`__.
Support for newer Linux distributions is scheduled for April 2024 with the next LTS release of Ubuntu.

**Windows** and **MacOS** do not (yet) support all dependencies required by CoLRev.
The last sections of the setup explain how to setup CoLRev on Windows using the WSL2 and on macOS using a Virtual Machine.


.. toctree::
   :maxdepth: 3
   :caption: Installation instructions

   dev_setup/part_1_docker
   dev_setup/part_2_git_ssh
   dev_setup/part_3_colrev
   dev_setup/macos_vm
   dev_setup/windows_wsl2
