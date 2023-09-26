::

   # Install guest additions for Virtual Box
   sudo apt-get install virtualbox-guest-additions-iso

   # Install git, gitk and vim
   sudo apt install git
   sudo apt install gitk
   sudo apt install vim

   # Install visual studio code (via snap)
   sudo snap install --classic code

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
