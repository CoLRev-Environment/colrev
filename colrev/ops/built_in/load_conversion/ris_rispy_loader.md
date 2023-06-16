# RisRispyLoader

Supported File type: `ris`

## Supported fields:


| RIS      | Mapped to                        |
|:---------|:---------------------------------|
| T2       | journal                          |
| A1,A2,A3 | author, also used to generate ID |
| Y1,PY    | year, also used to generate ID   |
| SP,EP    | pages (SP--EP)                   |
| IS       | Number                           |
| N2       | abstract                         |
| N1       | Note                             |
| T1,TI    | Title                            |

* Check Wiki for more details about available fields, right now only the fields
mentioned here are available.

Following fields are taken just as it is:
"TI", "VL", "DO", "PB", "IS"

## Links
* [rispy](https://pypi.org/project/rispy)
* [RIS File format](https://en.wikipedia.org/wiki/RIS_\(file_format\))
