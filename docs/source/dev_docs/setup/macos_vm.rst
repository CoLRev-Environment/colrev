MacOS: VirtualBox
===========================


A fully installed VirtualBox image is available `here <https://gigamove.rwth-aachen.de/en/download/a0dc5c130b24636165a5772921ebff40>`__.
If the link has expired, please contact `Gerit Wagner <mailto:gerit.wagner@uni-bamberg.de>`__.

-  VirtualBox: `Version 7.0.12 <https://www.virtualbox.org/wiki/Downloads>`__ (no unattended installation)
-  Distro ISO: `Ubuntu 22.04.3 LTS <https://ubuntu.com/download/desktop>`__

After unpacking the VirtualBox Image, add the ``colrev_dev.vbox`` file in VirtualBox. Start the machine, and log in (user ``ubuntu``, password ``ubuntu``). Please execute the steps described in the file ``colrev_final_setup_steps.md`` on the desktop.

To avoid performance issues, the following settings are recommended and are already preset for this image:

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

Install the guest additions (if missing) for a better integration between host and guest system:

::

   Open a Terminal and run the following command:
   sudo apt-get install virtualbox-guest-additions-iso

   Activate copy-paste between the VM (guest) and your OS (host):
   Devices > Shared Clipboard > Bidirectional

**Setup your own virtual machine from scratch**

If you want to setup your own virtual machine from scratch, please contiue with the :doc:`setup </dev_docs/setup/part_1_docker>`.
