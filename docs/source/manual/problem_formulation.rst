Step 1: Problem formulation
==================================

Literature reviews begin with the problem formulation step in which reviewers **specify the objective, the review type, and the plans for how the review team will conduct the review**.
This step may be informal and evolve throughout the review process, or be more formal.

..
   does not involve any records, but it can be updated throughout the process (e.g., after an exploratory search was completed)

Literature review guidelines emphasize the **pluralism of review types and methods**, suggesting that the objectives and the review types, as well as the subsequent choices, should be selected carefully to ensure methodological coherence.
To accomplish this, it is recommended to familiarize with the different genres and types of reviews:

.. list-table::
    :widths: 40 60
    :align: left
    :header-rows: 1

    * - Genre of review
      - Review types
    * - Describing
      - :doc:`Descriptive review <packages/colrev.descriptive_review>`, :doc:`Narrative review <packages/colrev.narrative_review>`
    * - Understanding
      - :doc:`Scoping review <packages/colrev.scoping_review>`, :doc:`Critical review <packages/colrev.critical_review>`
    * - Explaining
      - :doc:`Theoretical review <packages/colrev.theoretical_review>`, Realist review
    * - Testing
      - :doc:`Qualitative systematic review <packages/colrev.qualitative_systematic_review>`, :doc:`Meta-analysis <packages/colrev.meta_analysis>`, :doc:`Umbrella review <packages/colrev.umbrella>`

..
   (**TODO: link to resources/classifications/ideally a database overview**).

Once the initial objectives and review type are specified, the CoLRev project can be initialized using the ``colrev init`` operation and shared with the team.

In most cases, activities related to the problem formulation step will continue after initializing the repository.
The specification of plans for the review project may lead to the development of a **review protocol**.
As a best practice recommendation, we suggest to keep notes on the review objective, review type etc. in the ``data/paper.md`` file.
This document may also serve as the review protocol and evolve into the final review manuscript.
Review protocols often involve the following:

- Refining the review objectives and the characteristics of the review
- Defining focal concepts of the review
- Identifying prior (related) reviews to justify the need for a new review paper, inform methodological choices, such as the search terms and databases to be covered, and add their samples to the review project
- Developing a search strategy and testing it
- Specifying screening criteria
- Anticipating extected results and potential limitations

..
   - working hypothesis: differences between review types primarily manifest in the data stage (in the other steps, it is mostly a question of parameters)
   - Indicate that different forms of `data <2_6_data/data.html>`data analysis are activated by the selected review types  (per default)

.. dropdown:: References and resources

    **Classifications of literature review types**

    Paré, G., Trudel, M. C., Jaana, M., & Kitsiou, S. (2015). Synthesizing information systems knowledge: A typology of literature reviews. *Information & Management*, 52(2), 183-199. `link <https://www.sciencedirect.com/science/article/abs/pii/S0378720614001116>`_

    Schryen, G., Wagner, G., Benlian, A., & Paré, G. (2020). A knowledge development perspective on literature reviews: Validation of a new typology in the IS field. *Communications of the Association for Information Systems*, 46(1), 7. `link <https://aisel.aisnet.org/cais/vol46/iss1/7/>`__

    **Additional tools**

    Guidance on selecting an appropriate review type is provided by the `RightReview <https://rightreview.knowledgetranslation.net/>`_ tool.

.. toctree::
   :maxdepth: 1
   :caption: Operations

   problem_formulation/init
