
1. Workflow
==================================

This chapter will teach you how to use the CoLRev workflow.
Conducting a literature review is very challenging, requiring authors to keep track of individual papers, steps, and collaborative changes.
In CoLRev, you should only have to know the colrev status command and ...

Mention agreement on a shared data structure and steps of the literature review

.. The main purpose of the three-step workflow is to make your work easier.


.. figure:: ../../../figures/workflow.svg
   :width: 600
   :align: center
   :alt: Workflow cycle


CoLRev status
-------------------------------

The CoLRev status command serves as a starting point for all steps and helps to make CoLRev self-explanatory.
It consists of the following (as shown below):

- The **status section**, which provides an overview of the review project and reports the state of the records in the process

- The **instructions section**, which provides situational instructions on the next steps of the review project (highlighted in yellow), versioning and collaboration, and the local CoLRev environment

- The **checks section**, which checks consistency of file formats and structure


`colrev status` should provide all necessary instructions for your project.

.. code-block:: bash

   Status

    Metadata retrieval        7040 processed    [6198 curated]
    Metadata prescreen         814 included     [6226 prescreen excluded]
    PDF retrieval              814 prepared
    PDF screen                  49 included     [716 excluded]
    Data synthesis              49 synthesized

      Progress: |██████████████████▊    |82%

   Review project

     colrev dedupe

   Versioning and collaboration

     Up-to-date


   Checks

     ReviewManager.check_repo()  ...  Everything ok.
     ReviewManager.format()      ...  Everything ok.


CoLRev operation
-------------------------------

The status provides an overview of the six steps and corresponding operations.
The sequence of steps and operations as well as the corresponding state transitions of records are standardized across CoLRev projects.
Within this standardized structure, each operation can be configured.
Through the settings, it is possible to rely on the default configuration (the CoLRev reference implementation with reasonable parameters), to adapt selected parameters, to plug in CoLRev packages (community packages or custom built ones).

Step Problem formulation
   - Operation: init
Step Metadata retrieval
   - Operation: search
   - Operation: load
   - Operation: prep
   - Operation: dedupe
Step Metadata prescreen
   - Operation: prescreen
Step PDFs
   - Operation: pdf-get
   - Operation: pdf-prep
Step PDF screen
   - Operation: screen
Step Data
   - Operation: data

Operations can lead records to transition between states as illustrated in the following.

.. figure:: ../../../figures/steps_operations.svg
   :width: 800
   :alt: Overview of states


CoLRev validate
-------------------------------

After each step, check and validate the changes using

.. code-block:: bash

      colrev validate

TODO : include example of colrev validate

..
   Using git, you can validate the individual changes and the commit report for each version.
   Instructions on how to correct and trace errors are available in the guidelines for the respective step.

CoLRev also ensures that the git-diffs are readable:

TODO : update (e.g., colrev_origin, provenance fields)

.. code-block:: diff

   @inproceedings{BurtchWattalGhose2012,
      origin              = {scopus.bib/Burtch20123329},
   -  status              = {md_imported},
   +  status              = {md_prepared},
   -  metadata_source     = {ORIGINAL},
   +  metadata_source     = {CURATED},
   -  author              = {Burtch, G. and Wattal, S. and Ghose, A.},
   +  author              = {Burtch, Gordon and Ghose, Anindya and Wattal, Sunil},
   -  booktitle           = {International Conference on Information Systems, ICIS 2012},
   +  booktitle           = {International Conference on Information Systems},
   -  title               = {An Empirical Examination of Cultural Biases in Interpersonal Economic Exchange},
   +  title               = {An empirical examination of cultural biases in interpersonal economic exchange},
      year                = {2012},
      pages               = {3329--3346},
      volume              = {4},
      note                = {cited By 4},
   +  url                 = {http://aisel.aisnet.org/icis2012/proceedings/GlobalIssues/6},
   }

Note: you can also use a `git client of your choice <https://git-scm.com/downloads/guis>`_.

..
      A git commit report provides a higher-level overview of the repository's state:

      .. code-block:: diff

         Author: script:colrev prep main <>  2022-04-06 06:10:52
         Committer: Gerit Wagner <gerit.wagner@hec.ca>  2022-04-06 06:10:52
         Parent: 3ad86d73f7e04ee30b8687648b4dea140c526623 (Prepare records (exclusion)*)
         Child:  a7df1f2025e95419989e1d5b4a80223ddf099bc4 (Prepare records (medium_confidence)*)
         Branches: main, remotes/origin/main
         Follows:
         Precedes:

            Prepare records (high_confidence)*

            Report

            Command
            colrev prep \
                  --reprocess_state \
                  --debug_ids=NA \
                  --debug_file=NA \
                  --similarity=0.99
            On git repo with version 3ad86d73f7e04ee30b8687648b4dea140c526623

            Status

               Search           7661 retrieved    (0% curated)
               Metadata         7042 processed    (619 duplicates removed)
               Prescreen         577 included     (5807 excluded, 658 to prescreen)
               PDFs              577 prepared
               Screen             49 included     (528 excluded)
               Data                0 synthesized  (49 to synthesize)

            Properties for tree 170bae9a6651d86fc027d1196506452546b4a52f
            - Traceability of records          YES
            - Consistency (based on hooks)     YES
            - Completeness of iteration        NO
            To check tree_hash use             git log --pretty=raw -1
            To validate use                    colrev validate --properties
                                                --commit INSERT_COMMIT_HASH

            Software
            - colrev:               version 0.3.0+180.gc112ca4.dirty
            - colrev hooks:              version 0.3.0
            - Python:                    version 3.8.10
            - Git:                       version 2.25.1
            - Docker:                    version 20.10.7, build 20.10.7-0ubuntu5~20.04.2
            - colrev:                    version 0+untagged.20.g914a30b.dirty
                  * created with a modified version (not reproducible)

            Processing report

            Detailed report


            2022-04-06 12:08:30 [INFO] Dropped eissn field
            2022-04-06 12:08:30 [INFO] Dropped earlyaccessdate field

            ...
