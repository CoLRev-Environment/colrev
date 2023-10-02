.. _Setup WSL2:

Windows 10/11: WSL2
===================================================

On Windows 10/11, CoLRev can be installed through the Windows Subsystem for Linux 2 (WSL2) with Ubuntu 22.04.3 LTS (`setup with “The one line install!” <https://ubuntu.com/tutorials/install-ubuntu-on-wsl2-on-windows-10#3-download-ubuntu>`__).

Additionally, Docker must also be installed as a prerequisite to run CoLRev (`Setup Docker for WSL2 <https://docs.docker.com/desktop/wsl>`__).

Check availability of virtualization capabilities in Task Manager:

::

  Press "WIN + S", type "task" and start "Task Manager"
  Performance tab shows if "Virtualization" is activated

Install WSL2 via PowerShell:

::

  Press "WIN + X", in the menu click on "Windows PowerShell(Administrator)"
  Enter the following command:
  wsl --install -d ubuntu

Restart your machine and setup a new user:

::

  Press "WIN + S", type "ubuntu" and start "Ubuntu"
  Setup a new user and assign a password

Afterwards, follow the steps in :ref:`"Setup part 2: Git and SS" <part_2_git_ssh>`.
