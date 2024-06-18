.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt
   :target: https://colrev.readthedocs.io/en/latest/dev_docs/dev_status.html
.. |GIT_REPO| image:: /_static/svg/iconmonstr-code-fork-1.svg
   :width: 15
   :alt: Git repository
.. |LICENSE| image:: /_static/svg/iconmonstr-copyright-2.svg
   :width: 15
   :alt: Licencse
.. |MAINTAINER| image:: /_static/svg/iconmonstr-user-29.svg
   :width: 20
   :alt: Maintainer
.. |DOCUMENTATION| image:: /_static/svg/iconmonstr-book-17.svg
   :width: 15
   :alt: Documentation
colrev.synergy_datasets
=======================

Package
--------------------

|MAINTAINER| Maintainer: Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/synergy_datasets>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |MATURING|
     - .. code-block::


         colrev search --add colrev.synergy_datasets


Summary
-------

search
------

API search
^^^^^^^^^^


.. raw:: html

   <!-- Download search results and store in `data/search/` directory. API-access not yet available. -->



Navigate to the `SYNERGY Datasets <https://github.com/asreview/synergy-dataset>`_ and copy the name of the directory and csv file (in the datasets directory).
For example, the dataset under ``Howard_2016/Wassenaar_2017_ids.csv`` can be added as follows:

.. code-block::

   colrev search --add colrev.synergy_datasets -p dataset=Howard_2016/Wassenaar_2017_ids.csv

Note: some datasets are "broken". For example, the `Nagtegaal_2019 <https://github.com/asreview/synergy-dataset/blob/master/datasets/Nagtegaal_2019/Nagtegaal_2019_ids.csv>`_ dataset is a broken csv file and does not have any ids (doi/pubmedid/openalex_id).

The percentage of records with missing meatadata (no ids) is shown upon ``colrev search``.

Links
-----


* `SYNERGY Datasets <https://github.com/asreview/synergy-dataset>`_
