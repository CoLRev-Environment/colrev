#!/usr/bin/env python
"""Constants for CoLRev"""
# pylint: disable=too-few-public-methods
# pylint: disable=colrev-missed-constant-usage


class ENTRYTYPES:
    """Constants for record ENTRYTYPEs"""

    ARTICLE = "article"
    INPROCEEDINGS = "inproceedings"
    BOOK = "book"
    INBOOK = "inbook"
    PROCEEDINGS = "proceedings"

    INCOLLECTION = "incollection"
    PHDTHESIS = "phdthesis"
    THESIS = "thesis"
    MASTERSTHESIS = "masterthesis"
    BACHELORTHESIS = "bachelorthesis"
    TECHREPORT = "techreport"
    UNPUBLISHED = "unpublished"
    MISC = "misc"
    SOFTWARE = "software"
    ONLINE = "online"


class Fields:
    """Constant field names"""

    ID = "ID"
    ENTRYTYPE = "ENTRYTYPE"
    DOI = "doi"
    URL = "url"
    # TBD: no LINK field?
    ISSN = "issn"
    ISBN = "isbn"
    FULLTEXT = "fulltext"
    ABSTRACT = "abstract"
    KEYWORDS = "keywords"
    CITED_BY = "cited_by"
    FILE = "file"
    INSTITUTION = "institution"
    MONTH = "month"
    SERIES = "series"
    SCHOOL = "school"
    LANGUAGE = "language"

    MD_PROV = "colrev_masterdata_provenance"
    D_PROV = "colrev_data_provenance"
    ORIGIN = "colrev_origin"
    STATUS = "colrev_status"
    PDF_ID = "colrev_pdf_id"

    TEI_ID = "tei_id"

    TITLE = "title"
    AUTHOR = "author"
    YEAR = "year"
    JOURNAL = "journal"
    BOOKTITLE = "booktitle"
    CHAPTER = "chapter"
    PUBLISHER = "publisher"
    VOLUME = "volume"
    NUMBER = "number"
    PAGES = "pages"
    EDITOR = "editor"
    EDITION = "edition"
    ADDRESS = "address"

    SCREENING_CRITERIA = "screening_criteria"
    PRESCREEN_EXCLUSION = "prescreen_exclusion"

    COLREV_ID = "colrev_id"
    METADATA_SOURCE_REPOSITORY_PATHS = "metadata_source_repository_paths"
    LOCAL_CURATED_METADATA = "local_curated_metadata"
    GROBID_VERSION = "grobid-version"

    DBLP_KEY = "colrev.dblp.dblp_key"
    SEMANTIC_SCHOLAR_ID = "colrev.semantic_scholar.id"
    WEB_OF_SCIENCE_ID = "colrev.web_of_science.unique-id"
    PUBMED_ID = "colrev.pubmed.pubmedid"
    PMCID = "colrev.pubmed.pmcid"
    # https://www.nlm.nih.gov/bsd/mms/medlineelements.html#pmc
    EUROPE_PMC_ID = "colrev.europe_pmc.europe_pmc_id"


class FieldSet:
    """Constant field sets"""

    # """Keys of identifying fields considered for masterdata provenance"""
    PROVENANCE_KEYS = [
        Fields.MD_PROV,
        Fields.D_PROV,
        Fields.ORIGIN,
        Fields.STATUS,
        Fields.PDF_ID,
    ]

    IDENTIFYING_FIELD_KEYS = [
        Fields.TITLE,
        Fields.AUTHOR,
        Fields.YEAR,
        Fields.JOURNAL,
        Fields.BOOKTITLE,
        Fields.CHAPTER,
        Fields.PUBLISHER,
        Fields.VOLUME,
        Fields.NUMBER,
        Fields.PAGES,
        Fields.EDITOR,
    ]

    STANDARDIZED_FIELD_KEYS = (
        IDENTIFYING_FIELD_KEYS
        + PROVENANCE_KEYS
        + [
            Fields.ID,
            Fields.ENTRYTYPE,
            Fields.DOI,
            Fields.URL,
            Fields.ISSN,
            Fields.ISBN,
            Fields.FULLTEXT,
            Fields.ABSTRACT,
            Fields.KEYWORDS,
            Fields.CITED_BY,
            Fields.FILE,
            Fields.INSTITUTION,
            Fields.MONTH,
            Fields.SERIES,
            Fields.LANGUAGE,
        ]
    )
    """Standardized field keys"""

    TIME_VARIANT_FIELDS = [Fields.CITED_BY]


class FieldValues:
    """Constant field values"""

    UNKNOWN = "UNKNOWN"
    FORTHCOMING = "forthcoming"
    RETRACTED = "retracted"
    CURATED = "CURATED"


class DefectCodes:
    """Constant defect codes"""

    MISSING = "missing"
    NOT_MISSING = "not-missing"
    RECORD_NOT_IN_TOC = "record-not-in-toc"
    INCONSISTENT_WITH_ENTRYTYPE = "inconsistent-with-entrytype"
    CONTAINER_TITLE_ABBREVIATED = "container-title-abbreviated"
    DOI_NOT_MATCHING_PATTERN = "doi-not-matching-pattern"
    ERRONEOUS_SYMBOL_IN_FIELD = "erroneous-symbol-in-field"
    ERRONEOUS_TERM_IN_FIELD = "erroneous-term-in-field"
    ERRONEOUS_TITLE_FIELD = "erroneous-title-field"
    HTML_TAGS = "html-tags"
    IDENTICAL_VALUES_BETWEEN_TITLE_AND_CONTAINER = (
        "identical-values-between-title-and-container"
    )
    INCOMPLETE_FIELD = "incomplete-field"
    INCONSISTENT_CONTENT = "inconsistent-content"
    INCONSISTENT_WITH_DOI_METADATA = "inconsistent-with-doi-metadata"
    INCONSISTENT_WITH_URL_METADATA = "inconsistent-with-url-metadata"
    ISBN_NOT_MATCHING_PATTERN = "isbn-not-matching-pattern"
    LANGUAGE_FORMAT_ERROR = "language-format-error"
    LANGUAGE_UNKNOWN = "language-unknown"
    MOSTLY_ALL_CAPS = "mostly-all-caps"
    NAME_ABBREVIATED = "name-abbreviated"
    NAME_FORMAT_SEPARTORS = "name-format-separators"
    NAME_FORMAT_TITLES = "name-format-titles"
    NAME_PARTICLES = "name-particles"
    PAGE_RANGE = "page-range"
    PUBMED_ID_NOT_MATCHING_PATTERN = "pubmedid-not-matching-pattern"
    THESIS_WITH_MULTIPLE_AUTHORS = "thesis-with-multiple-authors"
    YEAR_FORMAT = "year-format"


class Operations:
    """Constant operation strings"""

    SEARCH = "search"
    LOAD = "load"
    PREP = "prep"
    PREP_MAN = "prep_man"
    DEDUPE = "dedupe"
    PRESCREEN = "prescreen"
    PDF_GET = "pdf_get"
    PDF_GET_MAN = "pdf_get_man"
    PDF_PREP = "pdf_prep"
    PDF_PREP_MAN = "pdf_prep_man"
    SCREEN = "screen"
    DATA = "data"


class ExitCodes:
    """Exit codes"""

    SUCCESS = 0
    FAIL = 1


class Colors:
    """Colors for CLI printing"""

    RED = "\033[91m"
    GREEN = "\033[92m"
    ORANGE = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"
