Linters
====================================

CoLRev includes custom plugins for pylint, which is useful to write high-qualiy code. Currently, `colrev-direct-status-assign` and `colrev-missed-constant-usage` are implemented.

If the linters emit error messages for code that is correct, you can ignore the messages for a particular line of code::

   # pylint: disable=colrev-direct-status-assign
   record_dict["colrev_status"] = RecordState.md_prepared


colrev-direct-status-assign
----------------------------------

The `colrev_status` should not be assigned directly using the `record_dict` dictionary. Instead, the `set_status()` method of `Record` should be used.

**Problematic code**::

   record_dict["colrev_status"] = RecordState.md_prepared


**Correct code**::

   import colrev.record.record
   from colrev.constants import RecordState

   record = colrev.record.record.Record(record_dict)
   record.set_statue(target_state = RecordState.md_prepared)



colrev-missed-constant-usage
----------------------------------

The use of global `CoLRev constants <https://github.com/CoLRev-Environment/colrev/blob/main/colrev/constants.py>`_ is encouraged.

**Problematic code**::

   record_dict["ENTRYTYPE"] = "Article"

**Correct code**::

   from colrev.constants import Fields
   from colrev.constants import ENTRYTYPES

   record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
