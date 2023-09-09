inconsistent_with_entrytype
===========================

Record content should match with entity type content

+--------------+-----------------------------------------+
|Container     | allowed fields                          |
+==============+=========================================+
|article       | booktitle                               |
+--------------+-----------------------------------------+
|inproceedings | issue,number,journal                    |
+--------------+-----------------------------------------+
|incollection  |                                         |
+--------------+-----------------------------------------+
|inbook        | journal                                 |
+--------------+-----------------------------------------+
|book          | volume,issue,number,journal             |
+--------------+-----------------------------------------+
|phdthesis     | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|masterthesis  | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|techreport    | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|unpublished   | volume,issue,number,journal,booktitle   |
+--------------+-----------------------------------------+
|online        | journal,booktitle                       |
+--------------+-----------------------------------------+
|misc          | journal,booktitle                       |
+--------------+-----------------------------------------+
