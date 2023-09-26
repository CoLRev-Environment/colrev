Update git credentials and setup SSH
------------------------------------

Before using the setup, please update your git credentials (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   sudo apt install git
   git config --global user.name "Lisa Smith"
   git config --global user.email "lisa.smith@stud.uni-bamberg.de"
   git config --global credential.helper store

Create a SSH key pair and register the public key at Github
(`steps <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent>`__).

Install CoLRev with the following commands (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

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

To test CoLRev in a demo project, run the following commands (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   cd ~/Desktop
   mkdir test
   cd test
   # Complete run to pull the Docker images, this may be time consuming
   colrev init --example
   # The status operation will guide you through the whole process
   colrev status
