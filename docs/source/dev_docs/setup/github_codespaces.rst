Install GitHub Codespaces for web-based programming
---------------------------------------------------
Prerequisites for web-based usage:

- GitHub Account
- Firefox or Chromium-based Browser

Setup `Codespaces here <https://github.com/features/codespaces>`__
                                                           
- Click: Get started for free
- Click: New codespace
- Click: Select a repository
- Enter: colrev
- Select: ColRev-Environment/colrev
- Select: Machine type 4-core
- Leave the rest on default settings (Branch: main, Region: Europe West)
- Uncheck "Auto-delete codespace" in "..." menu
- Let "GitHub Codespaces configuration" do some initial setup (happens automatically)
                                                             
While on "@username ➜ /workspaces/colrev (main) $" run the following commands:

Setup the CoLRev development environment:

::

   pip install -e .[dev,docs]
   # if the command above terminates with a warning append "--break-system-packages" and rerun the command:
   # pip install -e .[dev,docs] --break-system-packages
   pre-commit run --all

[Optional, recommended] For local usage also required:

- Install Visual Studio Code available for Windows, Linux and macOS (`download <https://code.visualstudio.com/download>`__)
- `Short intro <https://www.youtube.com/watch?v=u9ZQpKGTog4>`__ to "Git Graph" extension for VSCode (only for local installation of VSCode, web-based view does not work/stays blank)

[Optional] Update your git credentials:

::

   git config --global user.name "Lisa Smith"
   git config --global user.email "lisa.smith@stud.uni-bamberg.de"
   git config --global credential.helper store

[Optional] Navigation in the terminal, open and edit text files:

::

   # navigate with
   ls
   cd
   # open any text files with
   code mytextfile.txt

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
