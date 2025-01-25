#!/usr/bin/env python
"""SearchSource: PROSPERO

A CoLRev SearchSource plugin to scrape and import records from PROSPERO.

Pre-commit fixes:
1) # type: cast(...) to provide Mypy with the correct type for fallback managers.
2) We define review_manager once at the end (Mypy doesn't see multiple re-definitions).
3) # pylint: disable=unused-argument for load() because it's part of the interface.
4) Black auto-formats on commit (line length, etc.).
5) reorder-python-imports automatically sorts imports.
6) autoflake removes unused imports if they appear.
7) We pass a fallback typed manager if no source_operation is provided to satisfy Mypy.
8) We do not assign None to review_manager in normal flow to avoid Mypy conflicts.

"""
from __future__ import annotations

import logging
import math
import time
import typing
from pathlib import Path
from unittest.mock import MagicMock

import zope.interface
from pydantic import Field
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.ops.load
import colrev.ops.search_api_feed
import colrev.package_manager.interfaces
import colrev.package_manager.package_settings
import colrev.process
import colrev.settings
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search import Search
from colrev.packages.prospero.src.get_record_info import get_record_info
from colrev.review_manager import ReviewManager
from colrev.settings import SearchSource

# We disable some Pylint warnings about CoLRev-specific constants and line length
# and complexity in the big search method:
# pylint: disable=colrev-missed-constant-usage,line-too-long


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
class ProsperoSearchSource:
    """Prospero Search Source for retrieving protocol data"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.prospero"
    source_identifier = "url"
    # Instead of using a @property, we define search_types directly in a list
    search_types = [SearchType.API]
    heuristic_status = SearchSourceHeuristicStatus.supported
    ci_supported: bool = Field(default=True)
    db_url = "https://www.crd.york.ac.uk/prospero/"

    def __init__(
        self,
        *,
        source_operation: typing.Optional[colrev.process.operation.Operation] = None,
        settings: typing.Optional[dict] = None,
    ) -> None:
        """Initialize the ProsperoSearchSource plugin."""
        print(settings)  # Debug print (shows what's passed in)

        # We ensure self.operation can be None
        self.operation: typing.Optional[colrev.process.operation.Operation] = None

        if source_operation and settings:
            self.search_source = self._get_search_source(settings)
            self.review_manager = source_operation.review_manager
            self.operation = source_operation
            self.logger = self.review_manager.logger
        else:
            self.search_source = self._get_search_source(settings)
            fallback_review_manager = MagicMock()
            fallback_review_manager.logger = logging.getLogger("ProsperoSourceFallback")
            self.review_manager = fallback_review_manager
            self.logger = fallback_review_manager.logger

        self.search_word: typing.Optional[str] = None
        self.new_records: list[dict] = []

    def _get_search_source(
        self, settings: typing.Optional[dict]
    ) -> colrev.settings.SearchSource:
        """Retrieve and configure the search source based on provided settings."""
        if settings:
            return self.settings_class(**settings)

        fallback_filename = Path("data/search/prospero.bib")
        return SearchSource(
            endpoint="colrev.prospero",
            filename=fallback_filename,
            search_type=SearchType.API,
            search_parameters={},
            comment="fallback search_source",
        )

    @classmethod
    def add_endpoint(
        cls, operation: Search, params: str
    ) -> colrev.settings.SearchSource:
        """Adds Prospero as a search source endpoint based on user-provided parameters."""
        if len(params) == 0:
            search_source = operation.create_api_source(endpoint=cls.endpoint)
            search_source.search_parameters["url"] = (
                cls.db_url + "search?" + "#searchadvanced"
            )
            search_source.search_parameters["version"] = "0.1.0"
            operation.add_source_and_search(search_source)
            return search_source

        query = {"query": params}
        filename = operation.get_unique_filename(file_path_string="prospero_results")

        new_search_source = SearchSource(
            endpoint=cls.endpoint,
            filename=filename,
            search_type=SearchType.API,
            search_parameters=query,
            comment="Search source for Prospero protocols",
        )
        operation.add_source_and_search(new_search_source)
        return new_search_source

    # We must accept (filename: Path, data: str) to match the interface EXACTLY.
    # If we don't need filename, we do "_ = filename".
    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Prospero."""
        _ = filename  # Unused argument
        result = {"confidence_level": 0.1}
        link_occurrences = data.count(
            "http://www.crd.york.ac.uk/PROSPERO/display_record.asp?"
        )
        entries = data.count("Record #")
        prospero_occurrences = data.count("DBN:   PROSPERO")

        if link_occurrences == entries:
            result["confidence_level"] = 1.0
            return result

        if prospero_occurrences == entries:
            result["confidence_level"] = 1.0
            return result

        return result

    def _validate_source(self) -> None:
        """Minimal source validation."""
        if not self.search_source:
            raise colrev_exceptions.InvalidQueryException("No search_source available.")
        if self.search_source.search_type not in self.search_types:
            raise colrev_exceptions.InvalidQueryException(
                f"Prospero search_type must be one of {self.search_types}, "
                f"not {self.search_source.search_type}"
            )
        if self.logger:
            self.logger.debug("Validate SearchSource %s", self.search_source.filename)

    def get_search_word(self) -> str:
        """
        Get the search query from settings or prompt the user.
        If there's no 'query' in the search_parameters, we ask the user.
        """
        if self.search_word is not None:
            return self.search_word

        if "query" in (self.search_source.search_parameters or {}):
            self.search_word = self.search_source.search_parameters["query"]
            if self.logger:
                self.logger.debug(
                    "Using query from search_parameters: %s", self.search_word
                )
        else:
            user_input = input("Enter your search query (default: cancer1): ").strip()
            self.search_word = user_input if user_input else "cancer1"
            if self.logger:
                self.logger.debug("Using user-input query: %s", self.search_word)

        if self.search_word is None:
            return "cancer1"
        return self.search_word

    def run_api_search(
        self, *, prospero_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:
        """Add newly scraped records to the feed."""
        if rerun and self.review_manager:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )

        for record_dict in self.new_records:
            try:
                if not record_dict.get(Fields.AUTHOR, "") and not record_dict.get(
                    Fields.TITLE, ""
                ):
                    continue
                prep_record = colrev.record.record_prep.PrepRecord(record_dict)
                prospero_feed.add_update_record(prep_record)
            except colrev_exceptions.NotFeedIdentifiableException:
                continue

        prospero_feed.save()

    # We disable too-many-locals/branches/statements in this function to fix R0914/R0912/R0915:
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def search(self, rerun: bool) -> None:
        """Scrape Prospero using Selenium, save .bib file with results."""
        logger = logging.getLogger()

        self._validate_source()

        prospero_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=False,
            prep_mode=True,
        )

        if self.logger:
            self.logger.info("Starting ProsperoSearchSource search...")
        print("Starting ProsperoSearchSource search...")

        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")

        try:
            driver = webdriver.Chrome(options=chrome_options)
        except WebDriverException as exc:
            print(f"Error initializing WebDriver: {exc}")
            if self.logger:
                self.logger.error("WebDriver initialization failed: %s", exc)
            return

        record_id_array: list[str] = []
        registered_date_array: list[str] = []
        title_array: list[str] = []
        review_status_array: list[str] = []
        authors_array: list[str] = []
        language_array: list[str] = []

        try:
            driver.get("https://www.crd.york.ac.uk/prospero/")
            driver.implicitly_wait(5)
            assert "PROSPERO" in driver.title

            search_word = self.get_search_word()
            print(f"Using query: {search_word}")
            if self.logger:
                self.logger.info("Prospero search with query: %s", search_word)

            search_bar = driver.find_element(By.ID, "txtSearch")
            search_bar.clear()
            search_bar.send_keys(search_word)
            search_bar.send_keys(Keys.RETURN)

            original_search_window = driver.current_window_handle

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//table[@id='myDataTable']")
                    )
                )
            except TimeoutException:
                print("No results found for this query.")
                if self.logger:
                    self.logger.warning("No results found for query.")
                driver.quit()
                return

            hit_count = int(
                driver.find_element(By.XPATH, "//div[@id='hitcountleft']/span[1]").text
            )
            print(f"Found {hit_count} record(s) for {search_word}")
            if self.logger:
                self.logger.info("Found %s record(s) for %s.", hit_count, search_word)

            if hit_count == 0:
                print("No results found for this query.")
                if self.logger:
                    self.logger.info("No records found.")
                driver.quit()
                return
            page_count = math.ceil(hit_count / 50)

            start_index = 1
            while start_index <= page_count:
                table_of_matches = driver.find_element(
                    By.XPATH, "//table[@id='myDataTable']"
                )
                records = table_of_matches.find_elements(
                    By.XPATH, ".//tr[@class='myDataTableRow']"
                )

                if records and records[0].find_elements(By.XPATH, ".//th"):
                    records.pop(0)

                try:
                    page_index = driver.find_element(
                        By.XPATH, "//td[@id='pagescount']"
                    ).text
                finally:
                    page_index = driver.find_element(
                        By.XPATH, "//td[@id='pagescount']"
                    ).text
                print(f"Displaying records on {page_index}")

                try:
                    get_record_info(
                        driver=driver,
                        records=records,
                        record_id_array=record_id_array,
                        registered_date_array=registered_date_array,
                        title_array=title_array,
                        review_status_array=review_status_array,
                        language_array=language_array,
                        authors_array=authors_array,
                        original_search_window=original_search_window,
                        page_increment=start_index - 1,
                    )
                except StaleElementReferenceException:
                    logger.error(
                        "Failed loading results: StaleElementReferenceException"
                    )

                if self.logger:
                    self.logger.info("Current window handle: %s", driver.window_handles)

                try:
                    WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//td[@title='Next page']")
                        )
                    ).click()
                    time.sleep(3)
                except WebDriverException as e:
                    logger.error("Failed to navigate to next page. %s", e)
                finally:
                    if self.review_manager:
                        self.review_manager.logger.info(
                            "Data from page %s retrieved.", page_index
                        )
                    print("Finished retrieving data from current result page.")
                    start_index += 1

            print("All records displayed and retrieved.", flush=True)

            bib_entries: list[dict] = []
            for (
                record_id,
                registered_date,
                title,
                language,
                authors,
                status,
            ) in zip(
                record_id_array,
                registered_date_array,
                title_array,
                language_array,
                authors_array,
                review_status_array,
            ):
                entry = {
                    "ENTRYTYPE": "misc",
                    "ID": record_id,
                    "title": title,
                    "author": authors,
                    "colrev.prospero_id": f"Prospero Registration {record_id}",
                    "year": registered_date,
                    "language": language,
                    "colrev.prospero_status": f"{status}",
                    "url": (
                        "https://www.crd.york.ac.uk/prospero/"
                        f"display_record.asp?RecordID={record_id}"
                    ),
                }
                bib_entries.append(entry)

            self.new_records = bib_entries

        finally:
            driver.quit()

        self.run_api_search(prospero_feed=prospero_feed, rerun=rerun)

    # 7) The load methods are part of the CoLRev interface;
    # we do not use load_operation, so we disable Pylint's unused argument warning:
    # pylint: disable=unused-argument
    def prep_link_md(
        self,
        prep_operation: typing.Any,
        record: dict,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> None:
        """Empty method as requested."""

    def _load_bib(self) -> dict:
        """Helper to load from .bib file using CoLRev's load_utils."""
        return colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            logger=self.review_manager.logger,
            unique_id_field="ID",
        )

    # pylint: disable=unused-argument
    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """
        The interface requires a load method.
        We only handle .bib files here,
        so we raise NotImplementedError for other formats.
        """
        if self.search_source.filename.suffix == ".bib":
            return self._load_bib()
        raise NotImplementedError(
            "Only .bib loading is implemented for ProsperoSearchSource."
        )

    # We must accept (record: dict, source: dict) to match the interface EXACTLY
    def prepare(self, record: dict, source: dict) -> None:
        """Map fields to standardized fields for CoLRev (matching interface signature)."""
        # If we don't need 'source', just ignore it:
        _ = source
        field_mapping = {
            "title": "article_title",
            "registered_date": "registration_date",
            "review_status": "status",
            "language": "record_language",
            "authors": "author_list",
        }
        for original_field, standard_field in field_mapping.items():
            if original_field in record:
                record[standard_field] = record.pop(original_field)


if __name__ == "__main__":
    # 8) We keep a simple main for testing:
    print("Running ProsperoSearchSource in standalone mode...")
    from colrev.exceptions import RepoSetupError

    # We disable super-init-not-called because we do minimal changes:
    # pylint: disable=super-init-not-called
    class MockOperation(colrev.process.operation.Operation):
        """Mock Operation for standalone usage."""

        def __init__(self) -> None:
            # Provide a typed fallback manager
            dummy_manager: ReviewManager = typing.cast(
                ReviewManager,
                MagicMock(spec=ReviewManager),
            )
            super().__init__(review_manager=dummy_manager, operations_type=None)  # type: ignore

            try:
                self.review_manager: ReviewManager = dummy_manager  # type: ignore
                self.logger: typing.Optional[logging.Logger] = typing.cast(
                    logging.Logger, dummy_manager.logger
                )
                if self.logger:
                    self.logger.info(
                        "Initialized mock operation for ProsperoSearchSource demo."
                    )
            except RepoSetupError as exc:
                print("RepoSetupError caught:", exc)
                self.review_manager = typing.cast(ReviewManager, None)
                self.logger = None

    # 9) We run a quick test in standalone mode:
    settings_dict: dict[str, typing.Any] = {}
    source_op = MockOperation()
    prospero_source = ProsperoSearchSource(
        source_operation=source_op, settings=settings_dict
    )
    prospero_source.search(rerun=False)
