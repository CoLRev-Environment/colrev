## Issue description


## Expected behavior


## Actual behavior


## Steps to reproduce the problem (copy of the commit message report)

Report

    Command
        run prepare.py
        On git version x

    Software
       - colrev_core:               version x
       - pre-commit hooks:          version x
       - Python:                    version x
       - Git:                       version x
       - Docker:                    version x

    Certified properties for tree x
       - Traceability of records          YES/NO?
       - Consistency (based on hooks)     YES/NO?
       - Completeness of iteration        YES/NO?
       To check tree_hash use             git log --pretty=raw -1
       To validate use                    colrev_core validate --properties --commit INSERT_COMMIT_HASH

    Status
     | Search
     |  - Records retrieved          x
     |  - Records imported           x
     |  - Records prepared           x
     |  - Records processed          x  ->     x duplicates removed
     |
     | Pre-screen
     |  - Prescreen size             x
     |  - Included                   x  ->     x records excluded
     |
     | PDFs
     |  - PDFs need retrieval        x
     |  - PDFs retrieved             x
     |  - PDFs prepared              x
     |
     | Screen
     |  - Screen size                x
     |  - Included                   x  ->     x records excluded
     |
     | Data and synthesis
     |  - Total                      x
     |  - Synthesized                x

    Processing report

        2021-11-02 21:13:37 [INFO] Prepare
        2021-11-02 21:13:37 [INFO] Batch size: 2000
        2021-11-02 21:13:37 [INFO] Prepare WebsterWatson2002:
        ....
