#!/usr/bin/env python
"""Constants for CoLRev"""
# pylint: disable=too-few-public-methods
# pylint: disable=colrev-missed-constant-usage
import typing
from enum import Enum
from pathlib import Path


class Filepaths:
    """Filepaths for CoLRev"""

    # Environment-specific paths
    LOCAL_ENVIRONMENT_DIR = Path.home().joinpath("colrev")
    CURATIONS_PATH = LOCAL_ENVIRONMENT_DIR.joinpath("curated_metadata")

    LOCAL_INDEX_SQLITE_FILE = LOCAL_ENVIRONMENT_DIR / Path("sqlite_index.db")
    TEI_INDEX_DIR = LOCAL_ENVIRONMENT_DIR / Path(".tei_index/")

    REGISTRY_FILE = LOCAL_ENVIRONMENT_DIR.joinpath(Path("registry.json"))

    PREP_REQUESTS_CACHE_FILE = LOCAL_ENVIRONMENT_DIR / Path("prep_requests_cache")


class FileSets:
    """File sets for CoLRev"""

    DEFAULT_GIT_IGNORE_ITEMS = [
        ".history",
        ".colrev",
        "__pycache__",
        "*.bib.sav",
        "venv",
        ".corrections",
        ".report.log",
        "output",
        "data/pdfs",
        "data/dedupe",
        "data/prep",
        "data/pdf_get_man/missing_pdf_files.csv",
        "data/.tei/",
        "data/prep_man/records_prep_man.bib",
        "data/data/sample_references.bib",
        ".DS_Store",
    ]
    DEPRECATED_GIT_IGNORE_ITEMS = [
        "missing_pdf_files.csv",
        "manual_cleansing_statistics.csv",
        ".references_learned_settings",
        "pdfs",
        ".tei",
        "data.csv",
        "requests_cache.sqlite",
    ]


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
    CONFERENCE = "conference"

    @classmethod
    def get_all(cls) -> list:
        """Get all ENTRYTYPES"""
        return [
            cls.ARTICLE,
            cls.INPROCEEDINGS,
            cls.BOOK,
            cls.INBOOK,
            cls.PROCEEDINGS,
            cls.INCOLLECTION,
            cls.PHDTHESIS,
            cls.MASTERSTHESIS,
            cls.BACHELORTHESIS,
            cls.TECHREPORT,
            cls.UNPUBLISHED,
            cls.MISC,
            cls.SOFTWARE,
            cls.ONLINE,
            cls.CONFERENCE,
        ]


class Fields:
    """Constant field names"""

    ID = "ID"
    ENTRYTYPE = "ENTRYTYPE"

    MD_PROV = "colrev_masterdata_provenance"
    D_PROV = "colrev_data_provenance"
    ORIGIN = "colrev_origin"
    STATUS = "colrev_status"
    PDF_ID = "colrev_pdf_id"

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
    INSTITUTION = "institution"
    MONTH = "month"
    SERIES = "series"
    SCHOOL = "school"
    LANGUAGE = "language"
    DATE = "date"
    FILE = "file"
    DOI = "doi"
    URL = "url"
    # TBD: no LINK field?
    ISSN = "issn"
    ISBN = "isbn"
    FULLTEXT = "fulltext"
    ABSTRACT = "abstract"
    KEYWORDS = "keywords"

    CONTAINER_TITLE = "container_title"

    SCREENING_CRITERIA = "screening_criteria"
    PRESCREEN_EXCLUSION = "prescreen_exclusion"
    RETRACTED = "retracted"

    # References and citations
    # First-level references (backward) and citations (forward) can be stored in the record.

    # CITED_BY refers to forward citations
    # (as extracted from GoogleScholar cited_by for example)
    # Note : rename to CITED_BY_COUNT and use CITED_BY for a list of citing papers?
    CITED_BY = "cited_by"

    # REFERENCES is a list containing a dictionary for each reference in the bibliography
    # each reference can have the same fields as constants.Fields
    # specific additional fields are TEI_ID and NR_INTEXT_CITATIONS
    REFERENCES = "references"
    TEI_ID = "tei_id"
    NR_INTEXT_CITATIONS = "nr_intext_citations"

    TEXT_FROM_PDF = "text_from_pdf"
    NR_PAGES_IN_FILE = "nr_pages_in_file"

    COLREV_ID = "colrev_id"
    CURATION_ID = "curation_ID"
    METADATA_SOURCE_REPOSITORY_PATHS = "metadata_source_repository_paths"
    GROBID_VERSION = "grobid-version"

    DBLP_KEY = "colrev.dblp.dblp_key"
    SEMANTIC_SCHOLAR_ID = "colrev.semantic_scholar.id"
    WEB_OF_SCIENCE_ID = "colrev.web_of_science.unique-id"
    PUBMED_ID = "colrev.pubmed.pubmedid"
    PMCID = "colrev.pubmed.pmcid"
    # https://www.nlm.nih.gov/bsd/mms/medlineelements.html#pmc
    EUROPE_PMC_ID = "colrev.europe_pmc.europe_pmc_id"


class LocalIndexFields:
    """Fields used in the local index"""

    ID = "id"
    CITATION_KEY = "citation_key"
    BIBTEX = "bibtex"
    TEI = "tei"
    DBLP_KEY = "dblp_key"
    TOC_KEY = "toc_key"


class FieldValues:
    """Constant field values"""

    UNKNOWN = "UNKNOWN"
    FORTHCOMING = "forthcoming"
    RETRACTED = "retracted"
    CURATED = "CURATED"
    ANONYMOUS = "Anonymous"


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
        Fields.INSTITUTION,
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
            Fields.MONTH,
            Fields.SERIES,
            Fields.LANGUAGE,
            Fields.DATE,
            Fields.SCHOOL,
            Fields.ADDRESS,
            Fields.RETRACTED,
            Fields.CURATION_ID,
            Fields.DBLP_KEY,
            Fields.SEMANTIC_SCHOLAR_ID,
            Fields.WEB_OF_SCIENCE_ID,
            Fields.PUBMED_ID,
            Fields.PMCID,
        ]
    )
    """Standardized field keys"""

    TIME_VARIANT_FIELDS = [Fields.CITED_BY]

    # Fields that are stored as lists (items separated by newlines)
    LIST_FIELDS = [Fields.ORIGIN]

    MASTERDATA = IDENTIFYING_FIELD_KEYS + [FieldValues.CURATED]
    NO_PROVENANCE = PROVENANCE_KEYS + [
        Fields.ID,
        Fields.ENTRYTYPE,
        Fields.COLREV_ID,
        Fields.METADATA_SOURCE_REPOSITORY_PATHS,
    ]


class RecordState(Enum):
    """The possible RecordStates stored in the colrev_status field
    (corresponding to the ProcessModel)"""

    # pylint: disable=invalid-name

    # without the md_retrieved state, we could not display the load transition
    md_retrieved = 1
    """Record is retrieved and stored in the ./search directory"""
    md_imported = 2
    """Record is imported into the RECORDS_FILE"""
    md_needs_manual_preparation = 3
    """Record requires manual preparation
    (colrev_masterdata_provenance provides hints)"""
    md_prepared = 4
    """Record is prepared (no missing or incomplete fields, inconsistencies checked)"""
    md_processed = 5
    """Record has been checked for duplicate associations
    with any record in RecordState md_processed or later"""
    rev_prescreen_excluded = 6
    """Record was excluded in the prescreen (based on titles/abstracts)"""
    rev_prescreen_included = 7
    """Record was included in the prescreen (based on titles/abstracts)"""
    pdf_needs_manual_retrieval = 8
    """Record marked for manual PDF retrieval"""
    pdf_imported = 9
    """PDF imported and marked for preparation"""
    pdf_not_available = 10
    """PDF is not available"""
    pdf_needs_manual_preparation = 11
    """PDF marked for manual preparation"""
    pdf_prepared = 12
    """PDF prepared"""
    rev_excluded = 13
    """Record excluded in screen (full-text)"""
    rev_included = 14
    """Record included in screen (full-text)"""
    rev_synthesized = 15
    """Record synthesized"""
    # Note : TBD: rev_coded

    def __str__(self) -> str:
        return f"{self.name}"

    def __lt__(self, other) -> bool:  # type: ignore
        if self.__class__ == RecordState and other.__class__ == RecordState:
            return self.value < other.value
        raise NotImplementedError

    @classmethod
    def get_states_requiring_file(cls) -> list:
        """Get the states that require a file"""
        return [
            RecordState.pdf_imported,
            RecordState.pdf_needs_manual_preparation,
            RecordState.pdf_prepared,
            RecordState.rev_excluded,
            RecordState.rev_included,
            RecordState.rev_synthesized,
        ]

    @classmethod
    def get_non_processed_states(cls) -> list:
        """Get the states that correspond to not-yet-processed"""
        return [
            RecordState.md_retrieved,
            RecordState.md_imported,
            RecordState.md_prepared,
            RecordState.md_needs_manual_preparation,
        ]

    @classmethod
    def get_post_x_states(cls, *, state: "RecordState") -> typing.Set["RecordState"]:
        """Get the states after state x (passed as a parameter)"""
        # pylint: disable=too-many-return-statements
        if state == RecordState.md_prepared:
            return {
                RecordState.md_prepared,
                RecordState.md_processed,
                RecordState.rev_prescreen_included,
                RecordState.rev_prescreen_excluded,
                RecordState.pdf_needs_manual_retrieval,
                RecordState.pdf_imported,
                RecordState.pdf_not_available,
                RecordState.pdf_needs_manual_preparation,
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }
        if state == RecordState.md_processed:
            return {
                RecordState.md_processed,
                RecordState.rev_prescreen_included,
                RecordState.rev_prescreen_excluded,
                RecordState.pdf_needs_manual_retrieval,
                RecordState.pdf_imported,
                RecordState.pdf_not_available,
                RecordState.pdf_needs_manual_preparation,
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }
        if state == RecordState.rev_prescreen_included:
            return {
                RecordState.rev_prescreen_included,
                RecordState.rev_prescreen_excluded,
                RecordState.pdf_needs_manual_retrieval,
                RecordState.pdf_imported,
                RecordState.pdf_not_available,
                RecordState.pdf_needs_manual_preparation,
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }
        if state == RecordState.pdf_imported:
            return {
                RecordState.pdf_imported,
                RecordState.pdf_needs_manual_preparation,
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }
        if state == RecordState.pdf_prepared:
            return {
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }
        if state == RecordState.rev_included:
            return {
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            }
        if state == RecordState.rev_synthesized:
            return {RecordState.rev_synthesized}

        raise ValueError(f"state {state}")


class DefectCodes:
    """Constant defect codes"""

    MISSING = "missing"
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


class PDFDefectCodes:
    """Constant PDF defect codes"""

    NO_TEXT_IN_PDF = "no-text-in-pdf"
    PDF_INCOMPLETE = "pdf-incomplete"
    AUTHOR_NOT_IN_PDF = "author-not-in-pdf"
    TITLE_NOT_IN_PDF = "title-not-in-pdf"
    COVERPAGE_INCLUDED = "coverpage-included"
    LAST_PAGE_APPENDED = "last-page-appended"


class OperationsType(Enum):
    """Operation types correspond to the main state transitions (see ProcessModel)"""

    # pylint: disable=invalid-name

    search = "search"
    load = "load"
    prep = "prep"
    prep_man = "prep_man"
    dedupe = "dedupe"
    prescreen = "prescreen"
    pdf_get = "pdf_get"
    pdf_get_man = "pdf_get_man"
    pdf_prep = "pdf_prep"
    pdf_prep_man = "pdf_prep_man"
    screen = "screen"
    data = "data"

    format = "format"
    check = "check"

    def __str__(self) -> str:
        return f"{self.name}"

    @classmethod
    def get_manual_extra_operations(cls) -> list:
        """Get the manual operations that require extra manual steps"""
        return [
            OperationsType.pdf_prep_man,
            OperationsType.pdf_get_man,
            OperationsType.prep_man,
        ]


class IDPattern(Enum):
    """The pattern for generating record IDs"""

    # pylint: disable=invalid-name
    first_author_year = "first_author_year"
    three_authors_year = "three_authors_year"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_


class SearchType(Enum):
    """Type of search source"""

    API = "API"  # Keyword-searches
    DB = "DB"  # search-results-file with search query
    TOC = "TOC"
    BACKWARD_SEARCH = "BACKWARD_SEARCH"
    FORWARD_SEARCH = "FORWARD_SEARCH"
    FILES = "FILES"  # Replaces PDFS
    OTHER = "OTHER"
    MD = "MD"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_

    def __str__(self) -> str:
        return f"{self.name}"


class SearchSourceHeuristicStatus(Enum):
    """Status of the SearchSource heuristic"""

    # pylint: disable=invalid-name
    na = "not_applicable"
    oni = "output_not_identifiable"
    supported = "supported"
    todo = "to_be_implemented"

    def __str__(self) -> str:
        return f"{self.name}"  # pragma: no cover


class PDFPathType(Enum):
    """Policy for handling PDFs (create symlinks or copy files)"""

    # pylint: disable=invalid-name
    symlink = "symlink"
    copy = "copy"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_


class ScreenCriterionType(Enum):
    """Type of screening criterion"""

    # pylint: disable=invalid-name
    inclusion_criterion = "inclusion_criterion"
    exclusion_criterion = "exclusion_criterion"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_

    def __str__(self) -> str:
        return self.name


class ShareStatReq(Enum):
    """Record status requirements for sharing"""

    # pylint: disable=invalid-name
    none = "none"
    processed = "processed"
    screened = "screened"
    completed = "completed"

    @classmethod
    def get_options(cls) -> typing.List[str]:
        """Get the options"""
        # pylint: disable=no-member
        return cls._member_names_


# pylint: disable=colrev-missed-constant-usage
class EndpointType(Enum):
    """An enum for the types of PackageEndpoints"""

    # pylint: disable=C0103
    review_type = "review_type"
    """Endpoint for review types"""
    search_source = "search_source"
    """Endpoint for search sources"""
    prep = "prep"
    """Endpoint for prep"""
    prep_man = "prep_man"
    """Endpoint for prep-man"""
    dedupe = "dedupe"
    """Endpoint for dedupe"""
    prescreen = "prescreen"
    """Endpoint for prescreen"""
    pdf_get = "pdf_get"
    """Endpoint for pdf-get"""
    pdf_get_man = "pdf_get_man"
    """Endpoint for pdf-get-man"""
    pdf_prep = "pdf_prep"
    """Endpoint for pdf-prep"""
    pdf_prep_man = "pdf_prep_man"
    """Endpoint for pdf-prep-man"""
    screen = "screen"
    """Endpoint for screen"""
    data = "data"
    """Endpoint for data"""


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
