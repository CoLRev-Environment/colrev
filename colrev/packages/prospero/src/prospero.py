#!/usr/bin/env python
from __future__ import annotations

import logging
import os
import time
import typing
from pathlib import Path

import bibtexparser
import zope.interface
from pydantic import Field
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import colrev.loader.load_utils
import colrev.ops.load
import colrev.ops.search_api_feed
import colrev.package_manager.interfaces
import colrev.package_manager.package_settings
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.ops.search import Search
from colrev.packages.prospero.src.get_record_info import get_record_info
from colrev.review_manager import ReviewManager
from colrev.settings import SearchSource


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
class ProsperoSearchSource:
    """Prospero Search Source for retrieving protocol data"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.prospero"
    source_identifier = "url"
    search_types = [SearchType.API]
    heuristic_status = SearchSourceHeuristicStatus.supported
    ci_supported: bool = Field(default=True)
    db_url = "https://www.crd.york.ac.uk/prospero/"

    def __init__(
        self,
        *,
        source_operation: typing.Optional[colrev.process.operation.Operation] = None,
        settings: typing.Optional[dict] = None,
    ):
        print(settings)
        """Initialize the ProsperoSearchSource plugin."""
        if source_operation and settings:
            self.search_source = self.settings_class(**settings)
            self.review_manager = source_operation.review_manager
            self.operation = source_operation
            self.logger = self.review_manager.logger
        else:
            self.search_source = None
            self.review_manager = None
            self.logger = None
        self.search_word = None

    @classmethod
    def add_endpoint(cls, operation: Search, params: str) -> SearchSource:
        """Adds Prospero as a search source endpoint based on user-provided parameters."""
        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {"url": params}
            else:
                for item in params.split(";"):
                    if "=" in item:
                        key, value = item.split("=", 1)
                        params_dict[key] = value
                    else:
                        raise ValueError(f"Invalid parameter format: {item}")

        # Generate a unique .bib filename (like other CoLRev endpoints do)
        filename = operation.get_unique_filename(file_path_string="prospero_results")

        search_source = SearchSource(
            endpoint=cls.endpoint,
            filename=filename,
            search_type=SearchType.API,
            search_parameters=params_dict,
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

    """"
    @classmethod
    def heuristic(cls, filename: Path) -> dict:
        ""\"Source heuristic for Prospero""/"

        data = None

        try:
            reader = open(filename)
        except:
            print("Unable to open file. Please make sure the file path is correct!")
        try:
            data = reader.read()
        except:
            print("Unable to read exported data!")

        # TODO: reformat corresponding to BibTex file
        # assuming Prospero exports a .txt file
        result = {"confidence_level": 0.1}
        link_occurrences = data.count(
            "http://www.crd.york.ac.uk/PROSPERO/display_record.asp?"
        )
        entries = data.count("Record #")
        prospero_occurrences = data.count("DBN:   PROSPERO")

        if (
            link_occurrences == entries
        ):  # counts if number of entries match the number of times website was linked
            return result.update({"confidence_level": 1.0})

        if prospero_occurrences == entries:
            return result.update({"confidence_level": 1.0})

        return result """

    def get_search_word(self) -> str:
        """Get the search query from settings or prompt the user."""
        if self.search_word is not None:
            return self.search_word

        if self.search_source and hasattr(self.search_source, "search_parameters"):
            self.search_word = self.search_source.search_parameters.get(
                "query", "cancer1"
            )
            if self.logger:
                self.logger.debug(
                    f"Using query from search_parameters: {self.search_word}"
                )
        else:
            # fallback to standalone
            user_input = input("Enter your search query (default: cancer1): ").strip()
            self.search_word = user_input if user_input else "cancer1"
            if self.logger:
                self.logger.debug(
                    f"Using fallback user-input query: {self.search_word}"
                )

        return self.search_word

    def _load_existing_records(self, bib_path: Path) -> dict[str, dict]:
        """Load existing Prospero .bib records into a dictionary: ID -> record fields."""
        existing_records = {}
        if bib_path.is_file():
            with open(bib_path, encoding="utf8") as bib_file:
                bib_database = bibtexparser.load(bib_file)
            for entry in bib_database.entries:
                if Fields.ID in entry:
                    existing_records[entry[Fields.ID]] = entry
        return existing_records

    def _merge_new_results(
        self,
        existing_records: dict[str, dict],
        new_records: list[dict],
    ) -> None:
        """Compare new results with existing records; only update changed data."""
        for new_rec in new_records:
            record_id = new_rec.get(Fields.ID, None)
            if not record_id:
                continue
            if record_id in existing_records:
                # Compare and update existing record only if fields changed
                existing_rec = existing_records[record_id]
                changed = False
                for k, v in new_rec.items():
                    if k == Fields.ID:
                        continue
                    if existing_rec.get(k, "") != v:
                        existing_rec[k] = v
                        changed = True
                if changed and self.logger:
                    self.logger.info(f"Updated record: {record_id}")
            else:
                # Add new record
                existing_records[record_id] = new_rec
                if self.logger:
                    self.logger.info(f"Added new record: {record_id}")

    def search(self, rerun: bool) -> None:
        """Scrape Prospero using Selenium, save .bib file with results."""

        # Array declaration for all necessary information on found records
        record_id_array = []
        registered_date_array = []
        title_array = []
        review_status_array = []
        authors_array = []
        language_array =[]

        logger = logging.getLogger()

        """prospero_feed = self.search_source.get_api_feed(
            review_manager = self.review_manager,
            source_identifier = self.source_identifier,
            update_only =(not rerun)
        )"""

        if self.logger:
            self.logger.info("Starting ProsperoSearchSource search...")
        print("Starting ProsperoSearchSource search...")  # Debug statement

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

        try:
            driver.get("https://www.crd.york.ac.uk/prospero/")
            driver.implicitly_wait(5)
            assert "PROSPERO" in driver.title

            search_word = self.get_search_word()
            print(f"Using query: {search_word}")  # Debug statement
            if self.logger:
                self.logger.info(f"Prospero search with query: {search_word}")

            search_bar = driver.find_element(By.ID, "txtSearch")
            search_bar.clear()
            search_bar.send_keys(search_word)
            search_bar.send_keys(Keys.RETURN)

            original_search_window = driver.current_window_handle

            # Wait for results or no results
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
                return

            # Retrieve number of records found
            hit_count = int(
                driver.find_element(By.XPATH, "//div[@id='hitcountleft']/span[1]").text
            )
            print(f"Found {hit_count} record(s) for {search_word}")
            if self.logger:
                self.logger.info(f"Found {hit_count} record(s) for '{search_word}'.")

            # Calculate number of result pages manually to loop through 
            page_count = None
            if hit_count == 0:
                print("No results found for this query.")
                if self.logger:
                    self.logger.info("No records found.")
                return
            elif hit_count < 51:
                page_count = 1
            else:
                page_count = hit_count // 50

            start_index = 1
            while start_index <= page_count:

                table_of_matches = driver.find_element(
                    By.XPATH, "//table[@id='myDataTable']"
                )
                records = table_of_matches.find_elements(
                    By.XPATH, ".//tr[@class='myDataTableRow']"
                )
                # Remove header row if present
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

                # Collect record IDs, authors and language
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
                        page_increment= start_index-1
                    )
                except StaleElementReferenceException:
                    logger.error(
                        "Failed loading results: StaleElementReferenceException"
                    )
                print(f"Current window handle: {driver.window_handles}")

                # Clicking on "next" element to go to next page
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

            #  Start saving to BibTeX file
            bib_entries = []
            for record_id, registered_date, title, language, authors, status in zip(
                record_id_array, registered_date_array, title_array, language_array, authors_array, review_status_array
            ):
                entry = {
                    "ENTRYTYPE": "misc",
                    "ID": record_id,
                    "title": title,
                    "author": authors,
                    "published": f"Prospero Registration ID {record_id}",
                    "year": registered_date,
                    "language": language,
                    "note": f"Status: {status}",
                }
                bib_entries.append(entry)
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

    """def run_api_search(self, *, prospero_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool,) -> None:
        if rerun:
            self.review_manager.logger.info(
                "Performing a search of the full history (may take time)"
            )
        for records in self.new_records:
            try:
                if "" == records.get(
                    Fields.AUTHOR, ""
                ) and "" == records.get(Fields.TITLE, ""):
                    continue
                prep_record = colrev.record.record_prep.PrepRecord(records)
                prospero_feed.add_update_record(prep_record)

            except colrev_exceptions.NotFeedIdentifiableException:
                continue
        prospero_feed.save()"""

    def prep_link_md(self, prep_operation, record, save_feed=True, timeout=10):
        """Record-level metadata enrichment from Prospero, given a record ID."""
        record_id = record.get("ID")
        if not record_id:
            print("No ID provided in record, cannot link masterdata.")
            if self.logger:
                self.logger.warning("No ID in record for prep_link_md.")
            return record

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
            return record

        detailed_url = f"https://www.crd.york.ac.uk/prospero/display_record.php?RecordID={record_id}"
        try:
            driver.get(detailed_url)
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@id='documentfields']")
                )
            )

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//h1[text()='Language']")
                    )
                )
                language_paragraph = driver.find_element(
                    By.XPATH, "//h1[text()='Language']/following-sibling::p[1]"
                )
                record["language"] = language_paragraph.text.strip()
            except (TimeoutException, NoSuchElementException):
                record["language"] = "N/A"

            try:
                authors_div = driver.find_element(By.ID, "documenttitlesauthor")
                authors_text = authors_div.text.strip()
                record["authors"] = authors_text if authors_text else "N/A"
            except NoSuchElementException:
                record["authors"] = "N/A"

            print(
                f"Masterdata linked for ID {record_id}: Language={record['language']}, Authors={record['authors']}"
            )  # Debug
            if self.logger:
                self.logger.info(
                    f"Prospero masterdata linked for record {record_id}: "
                    f"Lang={record['language']}, Authors={record['authors']}"
                )

            if save_feed:
                print(
                    "Record updated. Would be saved to feed or further data structure."
                )
                if self.logger:
                    self.logger.debug(
                        "Record updated, feed saving not implemented here."
                    )

        except TimeoutException:
            print(f"Timeout while linking masterdata for ID {record_id}")
            if self.logger:
                self.logger.warning(f"Timeout for prep_link_md ID {record_id}")
        finally:
            driver.quit()

        return record

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

    @property
    def search_types(self):
        return self.__class__.search_types

    """
    @property
    def settings_class(self):
        ####return self.__class__.settings_class

        """

    @property
    def source_identifier(self):
        return self.__class__.source_identifier


if __name__ == "__main__":
    print("Running ProsperoSearchSource in standalone mode...")

    # Minimal mock usage
    import sys
    import logging
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
