missing_field
============================

Should contain required fields for each ENTRYTYPE. Following are the required fields for each possible ENTRYTYPE

**TODO** : mention "not_missing" flag (integrate with general False-Positive flags? - e.g., IGNORE:missing, IGNORE:all-caps)

See: inconsistent-field

+----------------+----------------------------------------------+
| ENTRYTYPE      | Required fields                              |
+================+==============================================+
| article        | author, title, journal, year, volume, number |
+----------------+----------------------------------------------+
| inproceedings  | author, title, booktitle, year               |
+----------------+----------------------------------------------+
| incollection   | author, title, booktitle, publisher, year    |
+----------------+----------------------------------------------+
| inbook         | author, title, chapter, publisher, year      |
+----------------+----------------------------------------------+
| proceedings    | booktitle, editor, year                      |
+----------------+----------------------------------------------+
| conference     | booktitle, editor, year                      |
+----------------+----------------------------------------------+
| book           | author, title, publisher, year               |
+----------------+----------------------------------------------+
| phdthesis      | author, title, school, year                  |
+----------------+----------------------------------------------+
| bachelorthesis | author, title, school, year                  |
+----------------+----------------------------------------------+
| thesis         | author, title, school, year                  |
+----------------+----------------------------------------------+
| masterthesis   | author, title, school, year                  |
+----------------+----------------------------------------------+
| techreport     | author, title, institution, year             |
+----------------+----------------------------------------------+
| unpublished    | title, author, year                          |
+----------------+----------------------------------------------+
| misc           | author, title, year                          |
+----------------+----------------------------------------------+
| software       | author, title, url                           |
+----------------+----------------------------------------------+
| online         | author, title, url                           |
+----------------+----------------------------------------------+
| other          | author, title, year                          |
+----------------+----------------------------------------------+
