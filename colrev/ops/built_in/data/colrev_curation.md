# Data: Enter DataEndpoint

Note: This document is currently under development. It will contain the following elements.

- description
- example


## Masterdata restrictions

Masterdata restrictions are useful to specify field requirements related to the ENTRYTYPE, the journal name, and the required fields (volume/number).
They can be set as follows:

```
"data_package_endpoints": [
    {
        "endpoint": "colrev.colrev_curation",
        ...
        "masterdata_restrictions": {
            "1985": {
                "ENTRYTYPE": "article",
                "volume": true,
                "number": true,
                "journal": "Decision Support Systems"
            },
            "2013": {
                "ENTRYTYPE": "article",
                "volume": true,
                "journal": "Decision Support Systems"
            },
            "2014": {
                "ENTRYTYPE": "article",
                "volume": true,
                "number": false,
                "journal": "Decision Support Systems"
            }
        },
        ...
    }

```

## Links
