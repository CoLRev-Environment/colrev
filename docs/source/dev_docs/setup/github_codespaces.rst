Install GitHub Codespaces
-------------------------
A short introduction video into GitHub Codespaces: `How to use GitHub Codespaces for Coding and Data Science <https://www.youtube.com/watch?v=kvJf8s18Vr4>`__

Prerequisites for web-based usage:

- GitHub Account
- Firefox or Chromium-based Browser

Setup `Codespaces here <https://github.com/features/codespaces>`__:

- Click: Get started for free
- Click: New codespace
- Click: Select a repository
- Enter: colrev
- Select: ColRev-Environment/colrev
- Leave the rest on default settings (Branch: main; Region: Europe West; Machine type 2-core)
- Uncheck "Auto-delete codespace" in "..." menu
- Let "GitHub Codespaces configuration" do some initial setup (happens automatically)

While on "@username ➜ /workspaces/colrev (main) $" the installation of CoLRev in editable mode and pre-commit hooks are started automatically. This may take several minutes to complete.

[Optional, recommended] For local usage also required:

- Install Visual Studio Code available for Windows, Linux and macOS (`download <https://code.visualstudio.com/download>`__)
- `Short intro <https://www.youtube.com/watch?v=u9ZQpKGTog4>`__ to "Git Graph" extension for VSCode (only for local installation of VSCode, web-based view does not work/stays blank)

[Optional, recommended] Update your git credentials:

::

   git config --global user.name "Lisa Smith"
   git config --global user.email "lisa.smith@stud.uni-bamberg.de"
   git config --global credential.helper store

[Optional] Add additional repos to current workspace and Git Graph:

::

   # In local VSCode setup click on "File" (top left menu)-> "Add Folder To Workspace..." -> enter absolute path to git repository
   # The newly added repo will be visible in Git Graph "Repo" drop-down menu
   # If the workspace settings is not saved, newly added repositories will not persist in Git Graph

[Optional] Navigation in the terminal, open and edit text files:

::

   # navigate with
   ls
   cd
   # open any text files directly in VSCode
   code mytextfile.txt
   # or in the terminal window with nano or vim
   nano mytextfile2.txt
   vim mytextfile3.txt

[Optional, diagnostics] Check if everything is setup correctly:

::

   # check if $PATH variable is correctly setup
   echo $PATH | grep :/home/codespace/.local/bin:
   # print effective user name
   whoami
   # print system information (kernel and distro version)
   uname -a
   # check docker functionality with docker-image "hello-world"
   docker run hello-world
   # print the git user name, user email and credential helper
   git config user.name
   git config user.email
   git config credential.helper

[Optional] Create a SSH key pair and register the public key at Github
(`steps <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent>`__).
