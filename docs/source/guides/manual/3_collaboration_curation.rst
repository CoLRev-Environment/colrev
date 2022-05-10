
3. Collaboration and Curation
==================================


.. _Collaboration:

Collaboration
-------------------------

Collaborative reviews based on a shared git repository (repositories can be hosted on `GitHub <https://docs.github.com/en/get-started/quickstart/create-a-repo>`_ or other git hosting services)

TODO : replace by colrev pull/push

.. code-block:: bash

      # To connect to the remote repository (update the url)
      git remote add origin https://github.com/u_name/repo_name.git
      git branch -M main
      git push -u origin main

      # To submit your local changes to the shared repository
      git push

      # To retrieve changes from co-authors
      git pull

      # Inspect the changes in a git client, such as gitk
      gitk

      # Merge conflicts: resolve manually or using a merge tool
      git add filename.ext
      git commit -m 'resolve'


Merging different versions of the same repository is challenging, but git uses powerful heuristics and successfully merges different versions (branches) automatically in most cases.
This allows us to work on a review project in a distributed and asynchronous manner.

In some situations, it is impossible to define (automated) rules to decide which change is the right one for the merged version.
For example, two researchers may change the title field of the same record.
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

When a git merge conflict occurs, a git diff tool (e.g., `Github client <https://desktop.github.com/>`_) can be useful to resolve the conflict.
It asks the user to resolve the issue (select what should be retained by modifying the file accordingly) and inserts merge conflict markers in the file to stop the merge process.
Using a diff tool, you can select which version should be retained.

.. _Curated repositories:

Curation
---------------------------------------------

Literature reviews are much more efficient, accurate, and rich if you rely on curated community repositories (e.g., reuse of prepared metadata, duplicate matchings, PDF hashes).
Search available curations on `GitHub <https://github.com/topics/colrev-curation>`_, add curated repositories, and help create a reuse-index:

.. code-block:: bash

      colrev env --install https://github.com/u_name/repo_name
      colrev env --index

See `reuse of community-curated data <../technical_documentation/colrev.html#reuse>`_ for details.
