## Summary

The unpaywall package provides legal and open access PDF retrieval for cross-disciplinary research. With access to over 30,000,000 scholarly articles, it offers a convenient way to retrieve PDF documents from the [Unpaywall](https://unpaywall.org/) API.

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

## search
So far, only API search is implemented. Other search types such as MD search or TOC search might be implemented in the future.

### API search
Download search results and store in `data/search/` directory. A search on the Unpaywall API can be performed as follows.

#### Add enpoint and enter search query
You can add the endpoint without parameters as follows.
```
colrev search --add colrev.unpaywall
```
Afterwards you get enter the keywords as follows. The title must contain all keywords to be matched.

#### API search: Query format
The user can enter one single term or use the boolean  `AND`, `OR` , `NOT` for a specified search. Following conditions have to be followed:
- The boolean operators `AND`, `OR` , `NOT` must be written in capital letters
- Search terms must be enclosed in double quotes `""`
- The boolean operators `AND`, `OR` , `NOT` must be seperated from the search term with a whitespace `" "`

##### Examples
- A single search term: `"thermometry"`
- Two terms with AND: `"cell" AND "thermometry"`
- Two terms with OR: `"cell" OR "thermometry"`
- Negation of a term: `"cell" - "thermometry"`

#### Adding Endpoint with URL

To add an endpoint with a specific URL from the Unpaywall Article Search tool:

1. Copy the URL: Visit [Unpaywall Article Search tool](https://unpaywall.org/articles) and enter the keywords as described in the Query format section. Then click on "view in API" and copy the URL.

2. Use colrev command: Use the following command to add the endpoint with the copied URL:

   ```
   colrev search --add colrev.unpaywall -p "https://api.unpaywall.org/v2/search?query=YOUR_SEARCH_TERMS_HERE&is_oa=true&email=YOUR_EMAIL_HERE"
   ```

   ##### Example
   ```
    colrev search --add colrev.unpaywall -p "https://api.unpaywall.org/v2/search?query=cell%20thermometry&is_oa=true&email=unpaywall_01@example.com"
    ```

##### Unpaywall Query Parameters

- `is_oa:` (Optional) A boolean value indicating whether the returned records should be Open Access or not.
- `query:` (Required) The text to search for. The title must contain all search terms to be matched. 
- `email:` Your email address to access the API. If the email address is manually specified in the URL, this email will be saved in the registry.


#### E-Mail

By default, the email address used in the git configuration is added to the unpaywall requests (pdf-get, search).

If you would like to use a different email address, use the following command.

```
colrev settings --update-global=packages.pdf_get.colrev.unpaywall.email=<email_address>
```

## Links

- [REST API](https://unpaywall.org/products/api)
