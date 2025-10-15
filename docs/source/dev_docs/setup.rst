Setup
====================================

This document describes the setup of a development environment for the CoLRev project.
Although we only support the systems listed in the table below, useful hints for the setup on other machines can be contributed to this repository (`create an issue <https://github.com/CoLRev-Environment/colrev/issues>`_).

**Supported operating systems and setup methods:**

 ============  ============ ====== ===================
  OS/Setup      Native       WSL2   GitHub Codespaces
 ============  ============ ====== ===================
 Ubuntu 22.04    yes        no     yes
  Win 10/11      no         yes    yes
    macOS        no         no     yes
 ============  ============ ====== ===================

**The setup also includes:**

-  Docker
-  git
-  Visual Studio Code
-  Python3, pip
-  CoLRev
-  Continuous integration (pre-commit hooks)

For best performance and user experience, it is recommended to run CoLRev natively on a machine with Ubuntu 22.04 installed.

CoLRev runs natively on **Linux** distributions and the step-by-step instructions apply to Linux systems.
They are tested for `Ubuntu 22.04 “Jammy” <https://releases.ubuntu.com/jammy/>`__ and `Debian 11.7 “Bullseye” <https://www.debian.org/releases/bullseye/debian-installer/index.en.html>`__.
Please note that newer versions of Ubuntu (22.10, 23.04, 23.10, 24.04) and Debian 12 “Bookworm” are not supported due to a change in the handling of the `pip package manager <https://itsfoss.com/install-pipx-ubuntu/>`__.

Windows machines can run CoLRev via WSL2 with Ubuntu 22.04 installed.
Using Ubuntu 22.04 via WSL2 does not provide the default GNOME Desktop Environment (GNOME DE).
Applications with a GUI such as gitk or VSCode can be run via commands using the CLI provided.

For MacOS, we recommend using GitHub Codespaces.

.. toctree::
   :maxdepth: 3
   :caption: Installation instructions

   setup/part_1_docker
   setup/part_2_git_ssh
   setup/part_3_colrev
   setup/windows_wsl2
   setup/github_codespaces
