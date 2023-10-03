Windows: WSL2
===================================================

On Windows, CoLRev can be installed through the Windows Subsystem for Linux 2 (WSL2) with Ubuntu 22.04.3 LTS (`setup with “The one line install!” <https://ubuntu.com/tutorials/install-ubuntu-on-wsl2-on-windows-10#3-download-ubuntu>`__).

`Setup Docker for WSL2 <https://docs.docker.com/desktop/wsl>`__

Check availability of Virtualization in Task Manager

::

  Press "WIN + S", type "task" and start "Task Manager"
  Performance tab shows if Virtualization is activated

Install WSL2 via PowerShell

::

  Press "WIN + X" start "Windows PowerShell(Administrator)"
  Enter the following command:
  wsl --install -d ubuntu

Restart your machine

::

  Press "WIN + S", type "ubuntu" and start "Ubuntu"
  Setup a new user and assign a password

Windows: 10/11 via WSL2 with Ubuntu 22.04.3 LTS (`tutorial and setup with “The one line install!” <https://ubuntu.com/tutorials/install-ubuntu-on-wsl2-on-windows-10#3-download-ubuntu>`__)

Afterwards, follow Setup steps 1-2.

**TODO DOCKER**
