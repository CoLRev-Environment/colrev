#!/usr/bin/env python
from __future__ import annotations

import logging
import math
import os
import time
import typing
from pathlib import Path
from unittest.mock import MagicMock

import bibtexparser
import zope.interface
from pydantic import Field
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
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
import colrev.settings
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search import Search
from colrev.packages.prospero.src.get_record_info import get_record_info
from colrev.review_manager import ReviewManager
from colrev.settings import SearchType

# Minimal fallback imports for a standalone run if no operation is passed


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
class ProsperoSearchSource:
    """Prospero Search Source for retrieving protocol data"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.prospero"
    source_identifier = "url"
    # <CHANGED> Instead of using a @property, we define search_types directly in a list
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
        print(settings)  # Debug print (shows what's passed in)
        """Initialize the ProsperoSearchSource plugin."""
        if source_operation and settings:
            # <CHANGED> We now retrieve the search_source via a helper method
            self.search_source = self._get_search_source(settings)
            self.review_manager = source_operation.review_manager
            self.operation = source_operation
            self.logger = self.review_manager.logger
        else:
            # <CHANGED> Fallback logic if no operation/settings are provided
            self.search_source = self._get_search_source(settings)
            fallback_review_manager = MagicMock()
            fallback_review_manager.logger = logging.getLogger("ProsperoSourceFallback")
            self.review_manager = fallback_review_manager
            self.operation = None
            self.logger = fallback_review_manager.logger

        self.search_word = None
        self.new_records: list[dict] = []

    def _get_search_source(
        self, settings: typing.Optional[dict]
    ) -> colrev.settings.SearchSource:
        """Retrieve and configure the search source based on provided settings."""
        if settings:
            return self.settings_class(**settings)
        else:
            # <CHANGED> Provide a minimal fallback if no settings were provided
            from colrev.settings import SearchSource

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
                cls.db_url
                + "search?"
                + "#searchadvanced"
                + search_source.search_parameters.pop("query", "").replace(" ", "+")
            )
            search_source.search_parameters["version"] = "0.1.0"
            operation.add_source_and_search(search_source)

            return search_source
        else:
            if Fields.URL in params:
                query = {"url": params[Fields.URL]}
            else: 
                query = params
            
        # Generate a unique .bib filename
        filename = operation.get_unique_filename(file_path_string="prospero_results")

        search_source = colrev.settings.SearchSource(
            endpoint=cls.endpoint,
            filename=filename,
            search_type=SearchType.API,
            search_parameters=query,
            comment="Search source for Prospero protocols",
        )
        operation.add_source_and_search(search_source)
        return search_source

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Prospero"""
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
            self.logger.debug(f"Validate SearchSource {self.search_source.filename}")

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
                    f"Using query from search_parameters: {self.search_word}"
                )
        else:
            user_input = input("Enter your search query (default: cancer1): ").strip()
            self.search_word = user_input if user_input else "cancer1"
            if self.logger:
                self.logger.debug(f"Using user-input query: {self.search_word}")

        return self.search_word

    def run_api_search(
        self,
        *,
        prospero_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
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

    def search(self, rerun: bool) -> None:
        """Scrape Prospero using Selenium, save .bib file with results."""
        logger = logging.getLogger()

        # <CHANGED> We now validate the search_source
        self._validate_source()

        # <CHANGED> We retrieve (or create) the feed in prep_mode
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
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            if self.logger:
                self.logger.error(f"WebDriver initialization failed: {e}")
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
                self.logger.info(f"Prospero search with query: {search_word}")

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
                self.logger.info(f"Found {hit_count} record(s) for '{search_word}'.")

            if hit_count == 0:
                print("No results found for this query.")
                if self.logger:
                    self.logger.info("No records found.")
                driver.quit()
                return
            else:
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
                        driver,
                        records,
                        record_id_array,
                        registered_date_array,
                        title_array,
                        review_status_array,
                        language_array,
                        authors_array,
                        original_search_window,
                        page_increment=start_index - 1,
                    )
                except StaleElementReferenceException:
                    logger.error(
                        "Failed loading results: StaleElementReferenceException"
                    )

                print(f"Current window handle: {driver.window_handles}")

                try:
                    WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//td[@title='Next page']")
                        )
                    ).click()
                    time.sleep(3)
                except:
                    logger.error("Failed to navigate to next page.")
                finally:
                    start_index += 1
                    print("Finished retrieving data from current result page.")

            print("All records displayed and retrieved.", flush=True)

            bib_entries = []
            for record_id, registered_date, title, language, authors, status in zip(
                record_id_array,
                registered_date_array,
                title_array,
                language_array,
                authors_array,
                review_status_array,
            ):
                # <CHANGED> We replaced "published" with "colrev.prospero_id" (namespaced)
                # and "note" with "colrev.status" so they won't get dropped at load time
                entry = {
                    "ENTRYTYPE": "misc",
                    "ID": record_id,
                    "title": title,
                    "author": authors,
                    "colrev.prospero_id": f"Prospero Registration {record_id}",
                    "year": registered_date,
                    "language": language,
                    "colrev.prospero_status": f"{status}",
                }
                bib_entries.append(entry)

            self.new_records = bib_entries

            bib_database = bibtexparser.bibdatabase.BibDatabase()
            bib_database.entries = bib_entries
            os.makedirs("data/search/", exist_ok=True)
            with open(
                "data/search/prospero_results.bib", "w", encoding="utf8"
            ) as bibfile:
                bibtexparser.dump(bib_database, bibfile)
            if self.logger:
                self.logger.info(
                    "Saved Prospero search results to data/search/prospero_results.bib"
                )
            print("BibTeX file saved to data/search/prospero_results.bib")

        finally:
            driver.quit()

        # <CHANGED> We call run_api_search after scraping, adding the records to the feed
        self.run_api_search(prospero_feed=prospero_feed, rerun=rerun)

    def prep_link_md(self, prep_operation, record, save_feed=True, timeout=10):
        """Empty method as requested."""

    def prepare(self, record, source):
        """Map fields to standardized fields."""
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

    def _load_bib(self) -> dict:
        records = colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            logger=self.review_manager.logger,
            unique_id_field="ID",
        )
        return records

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        if self.search_source.filename.suffix == ".bib":
            return self._load_bib()
        raise NotImplementedError(
            "Only .bib loading is implemented for ProsperoSearchSource."
        )

    @property
    def heuristic_status(self) -> SearchSourceHeuristicStatus:
        return self.__class__.heuristic_status


if __name__ == "__main__":
    print("Running ProsperoSearchSource in standalone mode...")

    import sys
    from unittest.mock import MagicMock
    from colrev.review_manager import ReviewManager
    from colrev.exceptions import RepoSetupError

    class MockOperation(colrev.process.operation.Operation):
        def __init__(self):
            try:
                self.review_manager = MagicMock(spec=ReviewManager)
                self.review_manager.logger = logging.getLogger(
                    "ProsperoSearchSourceMock"
                )
                self.review_manager.logger.setLevel(logging.DEBUG)
                handler = logging.StreamHandler(sys.stdout)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                handler.setFormatter(formatter)
                self.review_manager.logger.addHandler(handler)
                self.logger = self.review_manager.logger
                self.review_manager.logger.info(
                    "Initialized mock operation for ProsperoSearchSource demo."
                )
            except RepoSetupError as exc:
                print("RepoSetupError caught: ", exc)
                self.review_manager = None
                self.logger = None

    source_op = MockOperation()

    settings_dict = {}
    prospero_source = ProsperoSearchSource(
        source_operation=source_op, settings=settings_dict
    )
    prospero_source.search(rerun=False)
