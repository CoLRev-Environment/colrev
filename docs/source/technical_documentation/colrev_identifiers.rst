
Document Identifiers
====================================

Core architecture and design of identifiers for source documents

**Version** 0.1

**Status** preliminary

..
   - TODO: explain how variations of journals/abbreviations are handled
   - TODO: describe how the properties (e.g., erroneous merges) were evaluated
   - TODO: explicitly mention that the same source document may have multiple metadata representations and identifiers - the data storage and retrieval processes should ensure that identifiers pointing to the same source document are resolved (based on manually verified links)
   Maybe refer to decentralized source identifiers?

Contents:

- :any:`definitions`
- :any:`design_goals`
- :any:`identifier_scheme`
- :any:`methods`
- :any:`appendix_resources`

.. _definitions:

Definitions
---------------

- TODO: identifier
- TODO: source document/associated metadata/content

.. _design_goals:

Design goals
------------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Goal
     - Description
   * - Decentralization
     - Enable the creation of identifiers without requiring centralized organizations and infrastructure, i.e., single points of failure which may have a limited life time.
   * - Control
     - Control of identifier creation, its associated metadata and content is distributed. Everyone can create identifiers, i.e., make metadata available under the specified protocol. As a result, this enables a shift from centrally controlled creation and publication of metadata and content associated with source documents by individuals towards distributed models in which the research community can take more active roles in curating, selecting, and reusing source documents.
   * - Universality
     - Enable the creation of identifiers for all source documents assuming that its metadata is complete.
   * - Interoperability
     - Enable an efficient conversion between centralized identifiers (such as DOIs) to CoLRev identifiers and vice versa if such identifiers exists for the source document.
   * - Authentication
     - Provide authentication of sources and authors/creators supports the evaluation of source trustworthiness upon retrieval.
   * - Verification
     - Enable the verification of associated metadata based on the identifier without requiring interactions with a centralized endpoint.
   * - Discoverability
     - Enable the discovery of the source documents and associated metadata/contents through a protocol and distributed resources without relying on centralized infrastructure. The protocol ensures that source documents can be discovered across public databases but also in non-public repositories, such as repositories shared by a reseach team or local resources.
   * - Efficiency
     - Storage and network requirements should be minimized, especially considering the volume of source documents and the multitude of metadata representations.

..
   design: two source documents should only be assigned distinct identifiers if there are non-trivial differences in the associate metadata.

   robust:

   not cryptographically verified

   When metadata for a given source document is incomplete, metadata completion may be required before creating an identifier.

.. _identifier_scheme:

Identifier scheme
------------------

ABNF definition:

.. code-block:: bash

   colrev1       = "colrev1:" source-type
   source-type   = article / inproceedings / book / inbook / thesis / misc / techreport / unpublished
   article       = "a/" journal "/" year "/" volume "/" number "/" authors "/" title
   inproceedings = "ip/" booktitle "/" year "/" authors "/" title
   book          = "b/" authors "/" year "/" title
   inbook        = "ib/" chapter "/" title "/" year "/" authors
   thesis        = "t/" title "/" year "/" authors
   misc          = "m/" title "/" year "/" authors "/" howpublished
   techreport    = "tr/" title "/" year "/" authors "/" howpublished
   unpublished   = "tr/" title "/" year "/" authors "/" howpublished

   journal       = *alpha
   year          = 1*4DIGIT
   volume        = *(alpha / DIGIT)
   number        = *(alpha / DIGIT)
   title         = 1*(alpha / DIGIT / "-")
   authors       = *(alpha / "-")
   booktitle     = *(alpha / DIGIT / "-")
   chapter       = 1*(alpha / DIGIT / "-")
   howpublished  = 1*(alpha / DIGIT / "-")

Notes

- Fields like journal, year, volume correspond to BibTex fields or equivalent fields in other formats.
- The rule "alpha" means lower case ASCII letters. Non-ASCII letters in a field are replaced by the corresponding lower-level ASCII letter (e.g., é is replaced by e) or by a space otherwise.
- Remaining spaces are replaced by "-".
- Cases in which metadata for different source documents is identical can be resolved in the retrieval process

Examples:

.. code-block:: bash

   colrev1:a/mis-quarterly/2003/27/1/weber-r/editor-s-comments
   colrev1:ip/international-conference-on-information-systems/2019/jin-q-animesh-a-pinsonneault-a/when-popularity-meets-position
   colrev1:b/popper-c/1934/the-logic-of-scientific-discovery

.. _methods:

Methods
----------

Create

- Check the completeness condition

Note: The identifier is defined by the process, i.e., in many cases, providing the metadata is enough and identifiers may not be persisted. Especially when using identifiers non-persistently for within and across repository operations, this makes it superfluous to change persisted identifiers when the identification scheme is updated.

Retrieve

- Retrieval from distributed service endpoints, which can be selected and simulated locally
- A service endpoint receives a query (colrev1 identifier) and parses its resources (including associated duplicate representations)
- Resources can be local/shared team/public downloaded/public linked
- If the identifier is is discovered as a duplicate representation of the main record in a given resource, the service endpoint resolves it accordingly.

.. _appendix_resources:

Appendix: Resources
-----------------------

`ISO 26324:2012(en), Information and documentation — Digital object identifier system <https://www.iso.org/obp/ui/#iso:std:iso:26324:ed-1:v1:en>`_

`W3C, Decentralized Identifiers (DIDs) v1.0 <https://www.w3.org/TR/did-core/>`_

`Silvio PeroniSilvio Peroni, David Shotton, Open Citation Identifier <https://figshare.com/articles/journal_contribution/Open_Citation_Identifier_Definition/7127816>`_
