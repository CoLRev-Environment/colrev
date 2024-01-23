# Semantic Scholar

This class supports the search function for Semantic Scholar via an unofficial python client (link below).

## search

So far, only API search is implemented. Other search types such as MD search or TOC search might be implemented in the future. All search results are saved as a standardized dictionary in the colrev feed and a distinctive `data/search/records.bib` file, the filename of which contains the query for the search. 

### API search

The code for the API search is located in `colrev/ops/built_in/search_sources/semanticscholar_api.py`.

The API search is launched with the following command:

```
colrev search -a colrev.semanticscholar
```

Upon entering the command above with no additional parameters, a console interface opens up, in which the user is asked to enter the parameters and query for their search. 

#### API search: Interface

The code for interface is located in `colrev/ops/built_in/search_sources/semanticscholarui.py`. 

In the main menu, the user can decide whether they want to search for a single paper or author, or conduct a full keyword search. Authors can be searched for by their name or via their distinct SemanticScholar-ID, which the user is asked to enter into the console. Papers can be searched for by their title or a specific ID - SemanticScholarID, DOI, ArXiv etc. 

If the user opted for a full keyword search, they are asked to enter a series of search parameters: A query, a yearspan, fields of study, publication types etc. These parameters restrict the search within the SemanticScholar library to recieve more precise results. 

For all search parameters except the query, the user can press the `enter` key to leave them blank. The query then will not restrict the search in the respective parameters, resulting in an increasingly broad search and more returned papers. 

When asked about the different publication types, the user can select one or multiple values by navigating the list with `uparrow` and `downarrow` and selecting and unselecting with `rightarrow`. Pressing `enter` will confirm the choice.

Please note that some user entries require a specific format and will be validated by the UI. If the format is not satisfied, the user will be asked to make a different entry. Here are some examples:

```
S2Ids (Paper or author) --> A String of alphanumeric characters
yearspan                --> Specific format, e.g.: "2020", "2020-" (from 2020 until this year), "-2020", "2020-2023"
venues and studyfields  --> Multiple entries in csv format possible, e.g.: "Venue A,Venue B,Venue C"
API key                 --> A String of 40 alphanumeric characters
```

#### API search: API key for SemanticScholar

While it is not necessary to enter an API key to conduct a search in SemanticScholar, we highly recommend it. Without an API key, SemanticScholar only allows limited access attempts per minute. This might lead to the site being unavailable for a short time. An API key can be requested via the SemanticScholar API (link below). Once a valid API key was entered, it will be saved in the `SETTINGS` file. Subsequent searches of SematicScholar will now include this API key. Every time a new search is conducted, the user will have the opportunity to change or delete the stored API key via the user interface.

#### API search: Forming the url and running the search

A dictionary containing the entered search parameters is saved as the `search_params` attribute of the UI object that is defined in the search source class. Accessing this dictionary, the different parameters are now distingushed and passed on to the SemanticScholar client software (link below). The client then implements these parameters into a query url. By calling the url, the client accesses the SemanticScholar API and downloads the results from the website. These results are then passed back to the search source class as a dictionary, containing objects of the SemanticScholar-specific `Paper` type.

#### API search: Transforming the search results to standardized colrev resultfile

Via iteration, each item of the result dictionary is modified to satisfy the colrev resultfile standard established in the `colrev/constants.py` module. Items are transformed into dictionaries and the contained information is allocated to the respective colrev `Fields`, which serve as keys in the newly formed dictionary. After completing the allocation, all key-value pairs whose keys are not colrev fields, are deleted to complete the transformation.

Please note that, unfortunately, the format of SemanticScholar outputs does not produce sufficiently clear information to fill in every colrev field. Disparities, e.g. in the definition of publication types (== "ENTRYTYPES" in colrev), may lead to ambigous information about a paper, its type or its venue. To prevent misinformation, papers will be marked as `miscellaneaous`, if the publication type is not determinable. Other fields, especially regarding books, such as `EDITOR`, `EDITION` or `ADDRESS` are not supported at all by SemanticScholar and thus cannot be filled in. 

SemanticScholar also does not distinguish between forthcoming or retracted entries. Thus, entries unfortunately cannot be flagged as such in the result file. 

#### API search: Saving resultfile in records.bib and updating the feed

TO BE IMPLEMENTED

#### API search: Not yet supported features

So far, the `rerun` functionality, which enables the user to conduct a completely new run of an already conducted query, has been out of scope. It will be implemented in the future. 

## Links
[SemanticScholar](https://www.semanticscholar.org)
[License]
[SemanticScholarAPI] (https://www.semanticscholar.org/product/api/tutorial#searching-and-retrieving-paper-details)
[SemanticScholarAPIDocumentation] (https://api.semanticscholar.org/api-docs/)
[SemanticScholarPythonClient] (https://github.com/danielnsilva/semanticscholar)
