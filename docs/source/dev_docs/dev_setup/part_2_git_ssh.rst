Setup part 2: Git and SSH
-------------------------------------------

Before installing and using CoLRev, please update your git credentials (using the shell / ``Ctrl``\ +\ ``Alt``\ +\ ``T``):

::

   sudo apt install git
   git config --global user.name "Lisa Smith"
   git config --global user.email "lisa.smith@stud.uni-bamberg.de"
   git config --global credential.helper store

Create a SSH key pair and register the public key at Github
(`steps <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent>`__).
