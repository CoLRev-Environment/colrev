
1. Workflow
==================================


.. figure:: ../../../figures/workflow.svg
   :width: 400
   :align: center
   :alt: Workflow cycle


Status
-------------------------------

The CoLRev status command serves as a starting point for all steps and helps to make CoLRev self-explanatory.
It consists of the following (as shown in the screenshot below):

- A checks section, which validates data structures and formats
- A status section, which provides an overview of the review project
- An instructions section (next steps), which provides situational instructions on the next steps of the review project, versioning and collaboration, and the local CoLRev environment

`colrev status` should provide all necessary instructions for your project.

.. code::

   ________________________ Status _______________________________

   Search
      - Records retrieved     7661  *   6266 curated (81.81%)
   ______________________________________________________________
   | Metadata preparation
   |  - Records imported     7661
   |  - Records prepared     7661
   |                               *   1282 to deduplicate
   |  - Records processed    6377  ->     2 duplicates removed
   |_____________________________________________________________

   Prescreen
      - Prescreen size        6377
      - Included               578  ->  5799 records excluded
   ______________________________________________________________
   | PDF preparation
   |  - PDFs imported         578
   |  - PDFs prepared         578
   |_____________________________________________________________

   Screen
      - Screen size            578
      - Included                49  ->   529 records excluded
                                    -     11 : BC1_digital_technology
                                    -     73 : BC2_value_network
                                    -     36 : BC3_centralized_governance
                                    -    148 : BC4_contract
                                    -    264 : BC5_knowledge_work

   Data and synthesis
      - Total                   49
      - Synthesized              0  *     49 to synthesize
   _______________________________________________________________

   Progress: |███████████████▊       |69%


   ______________________ Next steps _____________________________

   Review project

     Deduplicate records  i.e., use
     colrev dedupe

   Versioning and collaboration

     Sharing requirement: processed
     Local changes not yet on the server
     Once you have committed your changes, upload them to the shared repository.
     git push


   Checks

     ReviewManager.check_repo()  ...  SUCCESS




Analyze changes
-------------------------

After each step, check and validate the changes using a git `client of your choice <https://git-scm.com/downloads/guis>`_:

.. code-block:: bash

      git status
      gitk
      colrev status

Using git, you can validate the individual changes and the commit report for each version.
Instructions on how to correct and trace errors are available in the guidelines for the respective step.

CoLRev also ensures that the git-diffs are readable:

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


A git commit report provides a higher-level overview of the repository's state:

.. code-block:: diff

    Author: script:colrev_core prep main <>  2022-04-06 06:10:52
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


        ________________________ Status _______________________________

        Search
        - Records retrieved     7661  *   6247 curated (83.46%)
        ______________________________________________________________
        | Metadata preparation
        |  - Records imported     7661
        |                               *    174 need preparation
        |  - Records prepared     7487
        |                               *   1108 to deduplicate
        |  - Records processed    6377  ->     2 duplicates removed
        |_____________________________________________________________

        Prescreen
        - Prescreen size        6377
        - Included               578  ->  5799 records excluded
        ______________________________________________________________
        | PDF preparation
        |  - PDFs imported         578
        |  - PDFs prepared         578
        |_____________________________________________________________

        Screen
        - Screen size            578
        - Included                49  ->   529 records excluded
                                        -     13 : BC1_digital_technology
                                        -    120 : BC2_value_network
                                        -     56 : BC3_centralized_governance
                                        -    255 : BC4_contract
                                        -    415 : BC5_knowledge_work

        Data and synthesis
        - Total                   49
        - Synthesized              0  *     49 to synthesize
        _______________________________________________________________


        Properties for tree 170bae9a6651d86fc027d1196506452546b4a52f
        - Traceability of records          YES
        - Consistency (based on hooks)     YES
        - Completeness of iteration        NO
        To check tree_hash use             git log --pretty=raw -1
        To validate use                    colrev validate --properties
                                            --commit INSERT_COMMIT_HASH

        Software
        - colrev_core:               version 0.3.0+180.gc112ca4.dirty
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
