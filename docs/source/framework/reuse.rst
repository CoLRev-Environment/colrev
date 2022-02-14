
Reuse
==================================

Reuse of community-curated data is a built-in feature of CoLRev, aimed at saving efforts across projects as well as increasing accuracy and richness of the process.
Per default, every CoLRev repository that is registered locally makes its data accessible to all other local repositories.
This means that all general operations (e.g., preparing metadata or linking PDFs) are completed automatically once indexed.
Of course, reuse is the most powerful when sharing curated content (such as reviews, topic or journal-related repositories) within teams or publicly.

CoLRev builds on a comprehensive vision of reusing community-curated data, as illustrated in the figure.
This includes

- assigning shared IDs in the load process
- curated record metadata in the preparation process
- data on duplicate/non-duplicate relationships
- urls and local paths for PDFs
- fingerprints (hashes) to identify and verify PDFs
- any other label or data associated with the curated records

.. figure:: ../../figures/reuse.svg
   :width: 700
   :alt: Reuse of community-curated data

The colrev_cml_assistant extension provides an environment supporting researchers in curating shared repositories based on crowdsourcing and machine-learning.
