# Open Science Framework(OSF) Search Source

### API search

ℹ️ Restriction: API searches do not support complex queries yet.

Download search results and store in `data/search/` directory.

Data from the OSF open platform can be retrieved with the URL from the [https://www.osf.io/](https://api.osf.io/v2/nodes/?filter). Add the URL as follows:

----------------------------------------------------------------------------------------------
colrev search --add colrev.osf -p "https://api.osf.io/v2/nodes/?filter[title]=reproducibility"
----------------------------------------------------------------------------------------------

The search can be filtered by changing the filter parameter to one of the following parameters:
------
title
id
type
category
year
ia_url
description
tags
date_created
-------

The keyword you want the search source to filter it by should replace "reproducibility" in the given example.

## Links

- [REST API](https://developer.osf.io/)
