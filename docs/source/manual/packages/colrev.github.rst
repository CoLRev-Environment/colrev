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
colrev.github
=============

Package
--------------------

|MAINTAINER| Maintainer: Kolja Rinne, Philipp Kasimir, Chris Vierath, Karl Schnickmann

|LICENSE| License: MIT

|DOCUMENTATION| `Documentation <README.md>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - search_source
     - |EXPERIMENTAL|
     - .. code-block::


         colrev search --add colrev.github

   * - prep
     - |EXPERIMENTAL|
     - .. code-block::


         colrev prep --add colrev.github


Summary
-------

`GitHub <https://github.com/>`_ hosts repositories for code, datasets, and documentation.

search
------

API search
^^^^^^^^^^

ℹ️ Restriction: API searches require an GitHub access token to retrieve all the relevant meta data.

In your GitHub account, a classic `personal access tokens <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens>`_ can be created. It is not necessary to select any scopes.

Keywords are entered after the search command is executed. The user can chose to search repositories by title, readme files, or both.

.. code-block::

   colrev search --add colrev.github

prep
----

GitHub can be used to provide meta data for linking and updating existing records.

.. code-block::

   colrev prep --add colrev.github
