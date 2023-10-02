.. _Setup VM:

MacOS: VirtualBox
===========================

A fully installed VirtualBox image is available `here <https://gigamove.rwth-aachen.de/de/download/29146e80c3ec3e691e35b4866e9573c9>`__.
If the link has expired, please contact `Gerit Wagner <mailto:gerit.wagner@uni-bamberg.de>`__.

-  VirtualBox: `Version 7.0.10 <https://www.virtualbox.org/wiki/Downloads>`__ (no unattended installation)
-  Distro ISO: `Ubuntu 22.04.3 LTS <https://ubuntu.com/download/desktop>`__

After unpacking the VirtualBox Image, open the ``colrev_dev.vbox`` file in `VirtualBox <https://www.virtualbox.org/>`__.
To avoid performance issues, the following settings are recommended:

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

Start the machine, and log in (pre-built VM image: user ``ubuntu`` with password ``ubuntu``).

Install the guest additions for a better integration between host and guest system:

::

   Open a Terminal an run the following command:
   sudo apt-get install virtualbox-guest-additions-iso

   To activate copy-paste between the VM and your OS:
   Devices > Shared Clipboard > Bidirectional

Afterwards, please update git and SSH setup_cli.

**Setup your own virtual machine from scratch**

If you want to setup your own virtual machine from scratch, please contiue with the steps in the setup_distro section.
