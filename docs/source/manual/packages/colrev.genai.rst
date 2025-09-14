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
colrev.genai
============

|VERSION| Version: 0.1.0

|MAINTAINER| Maintainer: Julian Prester, Gerit Wagner

|LICENSE| License: MIT

|GIT_REPO| Repository: `CoLRev-Environment/colrev <https://github.com/CoLRev-Environment/colrev/tree/main/colrev/packages/genai>`_

.. list-table::
   :header-rows: 1
   :widths: 20 30 80

   * - Endpoint
     - Status
     - Add
   * - prescreen
     - |EXPERIMENTAL|
     - .. code-block::


         colrev prescreen --add colrev.genai

   * - screen
     - |EXPERIMENTAL|
     - .. code-block::


         colrev screen --add colrev.genai

   * - data
     - |EXPERIMENTAL|
     - .. code-block::


         colrev data --add colrev.genai


Summary
-------

Installation
------------

To install the dependencies of ``colrev.genai``\ , run

.. code-block::

   pip install colrev[colrev.genai]

To set the open-AI key, run

.. code-block::

   export OPENAI_API_KEY="your_api_key_here"

prescreen
---------

Note: This document is currently under development. It will contain the following elements.


* description
* example

.. code-block::

   colrev prescreen --add colrev.genai

screen
------

Note: This document is currently under development. It will contain the following elements.


* description
* example

.. code-block::

   colrev screen --add colrev.genai

References
----------

Syriani, E., David, I., and Kumar, G. 2023. “Assessing the Ability of ChatGPT to Screen Articles for Systematic Reviews,” arXiv. (https://doi.org/10.48550/ARXIV.2307.06464).

Castillo-Segura, P., Alario-Hoyos, C., Kloos, C. D., and Fernández Panadero, C. 2023. “Leveraging the Potential of Generative AI to Accelerate Systematic Literature Reviews: An Example in the Area of Educational Technology,” in 2023 World Engineering Education Forum - Global Engineering Deans Council (WEEF-GEDC), pp. 1–8. (https://doi.org/10.1109/WEEF-GEDC59520.2023.10344098).
