.. |EXPERIMENTAL| image:: https://img.shields.io/badge/status-experimental-blue
   :height: 14pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |MATURING| image:: https://img.shields.io/badge/status-maturing-yellowgreen
   :height: 14pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |STABLE| image:: https://img.shields.io/badge/status-stable-brightgreen
   :height: 14pt
   :target: https://colrev-environment.github.io/colrev/dev_docs/dev_status.html
.. |VERSION| image:: /_static/svg/iconmonstr-product-10.svg
   :width: 15
   :alt: Version
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
colrev.osf
==========

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Peiyao Mao, Mingxin Jiang, Johannes Maximilian Diel, Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/osf>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |EXPERIMENTAL|
     - .. code-block::


         colrev search --add colrev.osf


Summary
-------

search
------

API search
^^^^^^^^^^

ℹ️ Restriction: API searches do not support complex queries yet.

Download search results and store in ``data/search/`` directory.

Data from the OSF open platform can be retrieved with the URL from the `https://www.osf.io/ <https://api.osf.io/v2/nodes/?filter>`_. Add the URL as follows:

.. code-block::

   colrev search --add colrev.osf -p "https://api.osf.io/v2/nodes/?filter[title]=reproducibility"

The retrieved data, including detailed project metadata and resources, is processed and made available for further actions within CoLRev, such as analysis or reporting.

It is not necessary to pass an API key as a parameter here. In order to keep the key secret, you will be prompted to enter it through user input if it is not already stored in the settings. The api key can be requested via the `OSF settings page <https://accounts.osf.io/login?service=https://osf.io/settings/tokens/>`_.

The search can be filtered by changing the filter parameter to one of the following parameters: title, id, type, category, year, description, tags, data_created. For each of these, change "filter[parameter]=value" in the URL.

.. code-block::

   colrev search --add colrev.osf -p "https://api.osf.io/v2/nodes/?filter[description]=machine%20learning"

Format of the search-history file (interactive API search):

.. code-block:: json

   {
       "search_string": "",
       "platform": "colrev.osf",
       "search_results_path": "data/search/osf_description.bib",
       "search_type": "API",
       "search_parameters": {
           "description": "fitbit"
       },
       "version": "0.1.0"
   }

Links
-----


* `OSF <https://osf.io/>`_
* `OSF_API <https://developer.osf.io/>`_
