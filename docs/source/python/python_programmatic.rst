Python (programmatic)
==================================

Programmatic use of CoLRev in other Python applications is supported. The following code block illustrates the required steps.

.. code-block:: python

    import colrev.review_manager

    # Initialize the ReviewManager
    review_manager = colrev.review_manager.ReviewManager()

    # Get an operation and notify the ReviewManager
    prep_operation = review_manager.get_prep_operation()

    # Load the records and apply changes
    records = review_manager.dataset.load_records_dict()
    for record in records.values():
        ...

    # Save the changes, add them to git, and create commit
    review_manager.dataset.save_records_dict(records)
    review_manager.dataset.create_commit(msg="Pre-screening (package/script X")

It is also possible to use CoLRev utility methods to load and save different bibliography formats:

.. code-block:: python

    from pathlib import Path
    from colrev.writer.write_utils import write_file
    from colrev.loader.load_utils import load

    records_dict = load(filename=Path("filename.bib"))

    # modify records_dict

    write_file(records_dict=records_dict, filename=Path("filename.bib"))


PDF: text and tei

.. code-block:: python

    record = colrev.record.record_pdf.PDFRecord(record_dict)
    record.set_text_from_pdf()
    input(record[Fields.TEXT_FROM_PDF])

    import colrev.env.tei_parser
    

    tei = colrev.env.tei_parser.TEIParser(
        pdf_path=pdf_path,
        tei_path=tei_path,
    )

TODO : record matching, OCR, use of packages, quality model, local_index

TODO: show the "simple" example with review_manager and the "complex" exmaple without (load records dict, etc.) in comments