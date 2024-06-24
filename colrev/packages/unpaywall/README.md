## Summary

The unpaywall package provides legal and open access PDF retrieval for cross-disciplinary research. With access to over 30,000,000 scholarly articles, it offers a convenient way to retrieve PDF documents from the [Unpaywall](https://unpaywall.org/) API.

This package supports retrieval of PDF documents from the [unpaywall](https://unpaywall.org/) API, which provides access to over 40,000,000 free scholarly articles.

### E-Mail

By default, the email address used in the git configuration is added to the unpaywall requests.

If you would like to use a different email address, use the following command

```
colrev settings --update-global=packages.pdf_get.colrev.unpaywall.email=<email_address>
```

## pdf-get

<!--
Note: This document is currently under development. It will contain the following elements.

- description
- example
-->

The unpaywall package is activated by default.
If it is not yet activated, run

```
colrev pdf-get -a colrev.unpaywall
```

## search
So far, only API search is implemented. Other search types such as MD search or TOC search might be implemented in the future.

### API search
Download search results and store in `data/search/` directory.
A search on the Unpaywall API can be performed as follows:
```
colrev search --add colrev.unpaywall -p "https://api.unpaywall.org/v2/search?query=cell%20thermometry&is_oa=true&email=unpaywall_01@example.com"
```
If the email address is manually specified in the URL as a replacement for unpaywall_01@example.com, it will be stored under the following path:

```
packages.pdf_get.colrev.unpaywall.email=<email_address>
```


## Links

- [REST API](https://unpaywall.org/products/api)
