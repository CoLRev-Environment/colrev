incomplete_field
============================

Fields should not be incomplete.

Fields considered truncated if they have ``...`` at the end.
An author field is considered incomplete if first name is missing, which is indicated by a ``,`` at the end of the author name

+-----------------+
| Fields checked  |
+=================+
| title           |
+-----------------+
| journal         |
+-----------------+
| booktitle       |
+-----------------+
| author          |
+-----------------+
