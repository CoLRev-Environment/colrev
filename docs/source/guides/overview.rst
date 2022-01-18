
Overview
==================================

Conducting a full literature review should be as simple as running the following commands:

.. code-block:: bash

      # Initialize the project
      colrev init

      # Store search results in the search directory
      # Example:
      wget -p search https://bit.ly/33IZDnT
      wget -p search https://bit.ly/3qAbk9D

      # Load the seach results
      colrev load

      # Prepare the metadata
      colrev prep

      # Identify and merge duplicates
      colrev dedupe

      # Conduct a prescreen
      colrev prescreen

      # Get the PDFs for included papers
      colrev pdf-get

      # Prepare the PDFs
      colrev pdf-prep

      # Conduct a screen (using specific criteria)
      colrev screen

      # Complete the data analysis/synthesis
      colrev data

      # Build the paper
      colrev paper


Details and options for each step are provided in the guidelines section (on the left).
After each step, check and validate the changes using git status, gitk, and colrev status:

.. code-block:: bash

      git status
      gitk
      colrev status


Collaborative reviews based on a shared git repository (repositories can be hosted at `Github <https://docs.github.com/en/get-started/quickstart/create-a-repo>`_ or other git hosting services)

.. code-block:: bash

      # To connect to the remote repository (update the url)
      git remote add origin https://github.com/username/repository_name.git
      git branch -M main
      git push -u origin main

      # To submit the state of your local CoLRev repository to the shared repository
      git push

      # To retrieve changes from coauthors
      git pull

      # Inspect the changes in a git client, such as gitk
      gitk

      # Merge conflicts: resolve manually or using a merge tool
      git add filename.ext
      git commit -m 'resolve'


Merging different versions of the same repository is challenging, but git uses powerful heutistics and successfully merges different versions (branches) most of the time.
This allows us to work on review project in distributed and asynchronous settings.

In some situations, it is impossible to define (automated) rules to decide which change is the right one for the merged version.
For example, two researchers could change the title field of the same record.
In those cases, git raises a **merge conflict**.
This means, git does not arbitrarily decide which change is discarded and which change is retained for the merged commit.
It asks the user to decide.

While **git merge conflicts** are useful (they prevent errors), they should be anticipated and prevented as far as possible because their resolution requires manual effort.
CoLRev implements the following measures to avoid merge conflicts:

- CoLRev relies on `colrev-hooks <https://github.com/geritwagner/colrev-hooks>`_ (`pre-commit hooks <https://pre-commit.com/>`_) to enforce consistent formatting across repositories
- CoLRev uses collaboration instructions (part of :program:`colrev status`) to encourage users to share (git push) and integrate (git pull) changes often because keeping all repositories synchronized reduces the likelihood of merge conflicts
- CoLRev recommends that all records should be *processed* before sharing them (git push) because the metadata preparation steps can involve sorting changes (when setting record IDs) and raise git commit merges when executed in parallel.

Thereby, CoLRev implements a conservative strategy to prevent merge conflicts per default.
This seems appropriate for most cases in which the search and preparation is completed individually and with high degrees of automation.
To override this rule, experts can use the configuration to set the SHARE_STAT_REQ to 'NONE'.

When a git merge conflict occurs, a git diff tool (e.g., `Github client <https://github.blog/2018-11-14-github-desktop-1-5/#merge-conflict-resolution>`_) can be useful to resolve the conflict.
It asks the user to resolve the issue (select what should be retained by modifying the file accordingly) and inserts merge conflict markers in the file and stopping the merge process.
Using a diff tool, you can select the versions to be retained.
