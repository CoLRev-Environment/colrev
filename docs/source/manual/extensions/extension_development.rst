
Extension development
==================================

Guidelines on extension development and a few examples are summarized below.

Developing CoLRev extensions in Python/R is easy. Instructions and examples are provided below.

**Recommendations**:

- Get paths (as shown in :program:`colrev settings`) from REVIEW_MANAGER.paths
- Use the logger (report vs tool/extension)
    - colrev_report logger: log info that are helpful to examine and validate the process, including links to the docs where instructions for tracing and fixing errors are available
    - extension logger: log info on the progress. The output should be relatively short and allow users to see the progress and judge whether any errors occurred

- `Add <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>`_ the ```colrev-extension``` `topic tag on GitHub <https://github.com/topics/colrev-extension>`_ to allow others to find and use your work


TODO : add infos on the process for registering CoLRev extensions

..
   TDOO : Extensions of CoLRev are available on `GitHub <https://github.com/topics/colrev-extension>`_.
