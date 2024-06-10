Setup part 3: CoLRev
------------------------------------

Extend the $PATH environment variable enabling all pip packages to run correctly (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   # Add $HOME/.local/bin to the beginning of $PATH environment variable and make it persistent within ~/.bashrc
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> $HOME/.bashrc

::

   # Source the adjusted $PATH environment variable into the current terminal session with source
   # Or simply open a new terminal session to enable the new $PATH
   source ~/.bashrc

Install the following tools mandatory for CoLRev (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   # Install git, gitk and vim
   sudo apt install git
   sudo apt install gitk
   sudo apt install vim

::

   # Install visual studio code as snap package
   sudo snap install --classic code
   # If you are using Ubuntu with WSL2, please run the command "code" afterwards
   # It will add Visual Studio Code (aka VS Code Server for x64) to your Windows Start Menu with WSL2 compatibility
   # if you prefer to install a .deb package, please follow the official instructions: https://code.visualstudio.com/docs/setup/linux

::

   # install python and pip package manager
   sudo apt install python-is-python3
   sudo apt install python3-pip
.. these lines are obsolete/redundant, will get handled later by "$ pip install -e .[dev,docs]"
   python3 -m pip install --upgrade pip
   python3 -m pip install poetry
   python3 -m pip install --upgrade paramiko

.. note::
   In the following, we assume that the ``colrev`` directory and the ``test`` directory are located on the Desktop. If you have chosen a different location, please adjust the paths accordingly.

Clone and install CoLRev with the following commands (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   # Clone and install CoLRev on your Desktop
   # Make sure you have registered your SSH key on GitHub beforehand, see "Setup part 2: Git and SSH"
   mkdir -p ~/Desktop
   cd ~/Desktop
   git clone git@github.com:CoLRev-Environment/colrev.git
   cd ~/Desktop/colrev
   pip install -e .[dev,docs]
   pre-commit install

::

   # Run the pre-commit hooks
   pre-commit run --all

::

   # Run the tests separately (optional)
   pytest tests

::

   # Build the docs locally (optional)
   cd ~/Desktop/colrev/docs
   make html

Test CoLRev in a demo project with the following commands (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   # Create a test directory on Desktop and change directory into ~/Desktop/test
   mkdir ~/Desktop/test
   cd ~/Desktop/test

::

   # Complete run to pull the Docker images, this may be time consuming
   colrev init --example

::

   # The status operation will guide you through the whole process
   colrev status

Pull the newest changes from the main repository and update CoLRev with the following commands (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   # Switch to colrev directory. Path may differ, if colrev was setup elsewhere
   cd ~/Desktop/colrev

::

   # Pull the newest changes and apply the update
   git pull
   pip install -e .[dev,docs]
