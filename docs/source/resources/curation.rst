Curation
==================================

If you already completed a literature review project, it is very easy to set it up as a curation.
Make your repository available to the intended audience (publicly or within a team), and set the curation fields in the settings.
Suggest using a repository as a curation refers primarily to the data associated with individual papers (record level). It is always possible to clone/extend a colrev project or to include the sample in a new colrev project (show how this would be supported but state that this is not what we mean by *curation*).

This enables you to reuse record-level data within other local projects, within a research team, or across the research community.

.. also suggest the correction path via github (edit references.bib (?))

Literature reviews are much more efficient, accurate, and rich if you rely on curated community repositories (e.g., reuse of prepared metadata, duplicate matchings, PDF hashes).
Search available curations on `GitHub <https://github.com/topics/colrev-curation>`_, add curated repositories, and help create a reuse-index:

.. code-block:: bash

      colrev env --install https://github.com/u_name/repo_name
      colrev env --index

See :doc:`reuse of community-curated data </foundations/cep/cep001_framework>` for details.

..    This may become a separate chapter:
      Local review environments

      - Elements (include a figure and explanation):
      - feed repositories (update & distribute)
      - local topic repositories (e.g., zettelkasten) (often private)
      - paper projects (often shared)
      - Best practices for collaboration and sharing setups with students/colleagues
