Windows 10/11: WSL2
===================================================

On Windows 10/11, CoLRev can be installed through the Windows Subsystem for Linux 2 (WSL2) with Ubuntu 22.04.

Check availability of virtualization capabilities in Task Manager:

::

  Press "WIN + S", type "task" and start "Task Manager"

  Performance tab shows if "Virtualization" is activated

Install WSL2 and Ubuntu 22.04 via PowerShell:

::

  Press "WIN + X", in the menu click on "Windows PowerShell(Administrator)"

  Enter the following command:
  wsl --install -d Ubuntu-22.04

Restart your machine and and launch Ubuntu:

::

  Press "WIN + S", type "ubuntu" and start "Ubuntu"

  Add a new user and assign a password

  Update the package sources list and update all the packages presently installed:
  sudo apt update && sudo apt upgrade

  Create the default folder for ssh keys:
  mkdir ~/.ssh

  Create the "Desktop" folder as workspace:
  mkdir ~/Desktop

  Exit ubuntu and install Docker in the next step:
  exit

Now install Docker as a prerequisite to run CoLRev following the official install guide: `Docker Desktop WSL 2 backend on Windows <https://docs.docker.com/desktop/features/wsl/>`__.

Afterwards, follow the steps in :doc:`"Setup part 2: Git and SSH" </dev_docs/setup/part_2_git_ssh>` and :doc:`"Setup part 3: CoLRev" </dev_docs/setup/part_3_colrev>`.

**Important**: To use the WSL command line, you have to run `wsl` in the Windows command prompt or PowerShell (see `explanation <https://devblogs.microsoft.com/commandline/a-guide-to-invoking-wsl/>`__).

Further guides and tutorials how to setup and configure WSL2 can be found directly in the `official Ubuntu WSL documentation at Canonical. <https://documentation.ubuntu.com/wsl/latest/guides/install-ubuntu-wsl2/>`__
