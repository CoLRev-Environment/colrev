Setup part 3: CoLRev
------------------------------------

Install CoLRev with the following commands (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   # Install git, gitk and vim
   sudo apt install git
   sudo apt install gitk
   sudo apt install vim

   # Install visual studio code (via snap)
   sudo snap install --classic code

   # Add $HOME/.local/bin to PATH and load it into the current terminal session with source
   echo 'export PATH="$PATH:$HOME/.local/bin"' >> $HOME/.bashrc
   source ~/.bashrc

   sudo apt install python-is-python3
   sudo apt install python3-pip
   python3 -m pip install --upgrade pip
   python3 -m pip install poetry
   python3 -m pip install --upgrade paramiko

   # Clone and install CoLRev on your Desktop
   # Make sure you have registered your SSH key on GitHub beforehand
   cd ~/Desktop
   git clone git@github.com:CoLRev-Environment/colrev.git
   cd colrev
   pip install -e .[dev,docs]
   pre-commit install

   # Run the pre-commit hooks
   pre-commit run --all

   # Run the tests separately (optional)
   pytest tests

   # Build the docs locally (optional)
   cd docs
   make html

Test CoLRev in a demo project with the following commands (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   cd ~/Desktop
   mkdir test
   cd test
   # Complete run to pull the Docker images, this may be time consuming
   colrev init --example
   # The status operation will guide you through the whole process
   colrev status

Pull the newest changes from the main repository and update CoLRev with the following commands (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   # switch to colrev directory. Path may differ, if colrev was setup elsewhere
   cd ~/Desktop/colrev
   # pull the newest changes and apply the update
   git pull
   pip install -e .[dev,docs]
   
