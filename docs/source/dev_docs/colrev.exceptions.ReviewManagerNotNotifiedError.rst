colrev.exceptions.ReviewManagerNotNotifiedError
===============================================

.. currentmodule:: colrev.exceptions

.. autoexception:: ReviewManagerNotNotifiedError

   ``Dataset.load_records_dict()`` refuses to return data until the review
   manager knows which operation is about to run. It expects the
   :class:`~colrev.review_manager.ReviewManager` to have its
   ``notified_next_operation`` flag set, otherwise it raises this exception.
   Creating an operation immediately calls :meth:`Operation.notify()
   <colrev.operation.Operation.notify>` which sets that flag and runs the
   operation's precondition checks. In other words, you do *not* need to call
   ``notify()`` manually; instantiating the desired operation is enough.

   The notification gate exists to prevent two classes of errors:

   * **Dirty working tree issues** –
     :meth:`Operation.check_precondition()
     <colrev.operation.Operation.check_precondition>` ensures the repository is
     clean before state-changing work begins. It raises
     :class:`~colrev.exceptions.UnstagedGitChangesError` when modifications are
     unstaged and :class:`~colrev.exceptions.CleanRepoRequiredError` when tracked
     files outside the ignore list would be overwritten. By forcing dataset
     access to go through an operation, these safeguards always execute before
     records are read or written.
   * **Process-order violations** – the same precondition routine verifies that
     the requested operation is valid given each record's current status. It can
     raise :class:`~colrev.exceptions.ProcessOrderViolation` if earlier steps are
     missing or :class:`~colrev.exceptions.NoRecordsError` if work other than
     loading is attempted before any records exist. Requiring notification makes
     sure these workflow errors are caught instead of letting scripts bypass the
     process model.

   ``ReviewManagerNotNotifiedError`` therefore ensures that every dataset access
   is routed through an operation, keeping the repository cleanliness and
   process-order checks in place.
