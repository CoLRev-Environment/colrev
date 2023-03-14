

.. _Problem formulation:

Step 1: Problem formulation
==================================

Literature reviews begin with the problem formulation step in which reviewers **specify the objective, the review type, and the plans for how the review team will conduct the review**.
This step may be informal and evolve throughout the review process, or be more formal.

..
   does not involve any records, but it can be updated throughout the process (e.g., after an exploratory search was completed)

Literature review guidelines emphasize that the objectives and the review types, as well as the subsequent choices, should be methodologically coherent.
It is therefore recommended to familiarize with the different types of review. Exemplary classifications cover the following:

- Narrative review
- Descriptive review
- Scoping review
- Critical review
- Meta-analysis
- Qualitative systematic review
- Umbrella review
- Realist review
- Theoretical review

..
   (**TODO: link to resources/classifications/ideally a database overview**).

Guidance on selecting an appropriate review type is provided by the `RightReview <https://rightreview.knowledgetranslation.net/>`_ tool.

It can also be useful to check prior (related) reviews. This can help to justify the need for a new review paper and it can inform several decisions, such as the search terms and databases to be covered.

Once the initial objectives and review type are specified, the CoLRev project can be initialized using the ``colrev init`` operation.

In most cases, activities related to the problem formulation step will continue after initializing the repository.
The specification of plans for the review project may lead to the development of a review protocol.
As a best practice recommendation, we suggest to keep notes on he review objective etc. in the ``data/paper.md`` file.
This document may also serve as the review protocol and evolve into the final review manuscript.
Review protocols often involve the following:

- Sharing the repository with your team (see `instructions <collaboration.html>`_).
- Refining the review objectives and the characteristics of the review.
- Defining focal concepts of the review.
- Developing a search strategy and testing it.
- If prior reviews were found, make plans to add their samples to the review project.

..
   - working hypothesis: differences between review types primarily manifest in the data stage (in the other steps, it is mostly a question of parameters)
   - Indicate that different forms of `data <2_6_data/data.html>`data analysis are activated by the selected review types  (per default)
   - mention settings (but do not display complete settings.json, which is too long?)

.. collapse:: References

   **Classifications of literature review types**

   Paré, G., Trudel, M. C., Jaana, M., & Kitsiou, S. (2015). Synthesizing information systems knowledge: A typology of literature reviews. Information & Management, 52(2), 183-199. `link <https://www.sciencedirect.com/science/article/abs/pii/S0378720614001116>`_

.. toctree::
   :maxdepth: 3
   :caption: Operations

   problem_formulation/init
