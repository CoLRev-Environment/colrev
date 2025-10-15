Collaboration
==================================

Selecting software
-----------------------------------------------------

CoLRev aims to support a broad range of software packages and offer seamless integration across all steps of the process. For example, in the synthesis step, users may want to rely on purley open-source setups involving Pandoc and Zotero, or proprietary software including Word and Endnote. Although automation, transparency, and efficient collaboration is a typical strength of open-source tools, team consensus may favor other setups. When planning collaborative literature review projects, it is therefore important to agree on the software that should be used by the team.

Giving team members access
-----------------------------------------------------

- Explain how to invite collaborators (link from colrev init)
- Replace the following (git pull/push) by colrev pull/push, add clone
- Distinguish within/beyond project collaboration

Collaborative reviews based on a shared git repository (repositories can be hosted on `GitHub <https://docs.github.com/en/repositories/creating-and-managing-repositories/quickstart-for-repositories>`_ or other git hosting services)

Users can pull an existing one (with the url provided by the project manager):

.. code:: bash

	colrev pull https://github.com/u_name/repo_name.git


Coordinating different modes of collaboration
-----------------------------------------------------

The composition of human and algorithmic work can vary throughout the steps. It is at the reviewers discretion to complete operations manually or automatically.

The init/prescreen/screen/data tend to be the steps where humans take the lead. Machines should take the lead on the more mechanical tasks (running the search/load/prep/dedupe/pdf-get/pdf-prep).

- Start with collaboration between humans, between humans and machines/algorithms (need for validation/tracing/reset functionality, highlight that benchmarking "between-machines" is also important and supported)
- Explain how colrev/git support asynchronous (merge) and synchronous (example: data) collaboration
- Mention that colrev can facilitate collaboration between users with different areas of expertise
- Mention colrev merged
- TBD: planning who does what? notifying/coordinating?



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

- CoLRev relies on `colrev-hooks <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/hooks>`_ (`pre-commit hooks <https://pre-commit.com/>`_) to enforce consistent formatting across repositories.
- CoLRev uses collaboration instructions (part of ``colrev status``) to encourage users to share (git push) and integrate (git pull) changes often because keeping all repositories synchronized reduces the likelihood of merge conflicts.
- CoLRev recommends that all records should be *processed* before sharing them (git push) because the metadata preparation steps can involve sorting changes (when setting record IDs) and raise git commit merges when executed in parallel.

Thereby, CoLRev implements a conservative strategy to prevent merge conflicts per default.
This seems appropriate for most cases in which the search and preparation is completed individually and with high degrees of automation.
To override this rule, experts can use the configuration to set the SHARE_STAT_REQ to 'NONE'.

When a git merge conflict occurs, a git diff tool (e.g., `GitHub Desktop <https://github.com/apps/desktop>`_) can be useful to resolve the conflict.
It asks the user to resolve the issue (select what should be retained by modifying the file accordingly) and inserts merge conflict markers in the file to stop the merge process.
Using a diff tool, you can select which version should be retained.
