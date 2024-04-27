# Unpaywall

This package supports retrieval of PDF documents from the [unpaywall](https://unpaywall.org/) API, which provides access to over 40,000,000 free scholarly articles.

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

By default, the email address used in the git configuration is added to the unpaywall requests.

If you would like to use a different email address, use the following command

```
colrev settings --update-global=packages.pdf_get.colrev.unpaywall.email=<email_address>
```

## Links

- [REST API](https://unpaywall.org/products/api)
