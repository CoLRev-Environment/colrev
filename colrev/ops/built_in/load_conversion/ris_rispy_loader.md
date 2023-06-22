# RisRispyLoader

Supported File type: `ris`

## Supported fields:

| RIS      | Mapped to                        |
|:---------|:---------------------------------|
| T2       | journal                          |
| A1,A2,A3 | author, also used to generate ID |
| Y1,PY    | year, also used to generate ID   |
| SP,EP    | pages (SP--EP)                   |
| N2       | abstract                         |
| N1       | Note                             |
| T1,TI,T2 | Title                            |
| VL       | Volume                           |
| DO       | Doi                              |
| PB       | Publisher                        |
| IS       | Number                           |


For all reference types, Author is required.

| Type or Reference      | Mapped to                        | RIS Fields Required         |
|:-----------------------|:---------------------------------|:----------------------------|
| JOUR, JFULL            | article                          | A1/A2/A3/AU,T1/TI/T2        |
| CONF                   | inproceedings                    | IS,T2                       |
| THES                   | pdhthesis                        | VL,IS,T2,TI                 |
| CHAP                   | inbook                           | T2/TI                       |
| BOOK                   | book                             | VL,IS,T2/TI/T2              |

* Check Wiki for more details about available fields, right now only the fields
mentioned here are available.


## Links
* [rispy](https://pypi.org/project/rispy)
* [RIS File format](https://en.wikipedia.org/wiki/RIS_\(file_format\))
