#!/usr/bin/env python
from __future__ import annotations
import typing
from pathlib import Path
import bibtexparser
import colrev.ops.search_api_feed
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter
import zope.interface
import colrev.ops.load
import colrev.package_manager.interfaces
import colrev.package_manager.package_settings
from colrev.constants import Fields, SearchType, SearchSourceHeuristicStatus
from colrev.settings import SearchSource
from colrev.ops.search import Search
import colrev.loader.load_utils
from colrev.review_manager import ReviewManager
from pydantic import Field

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
    def heuristic(cls, filename: Path, data:str) -> dict:
        return {}

    def get_search_word(self) -> str:
        """Get the search query from settings or prompt the user."""
        if self.search_word is not None:
            return self.search_word

        if self.search_source and hasattr(self.search_source, "search_parameters"):
            self.search_word = self.search_source.search_parameters.get("query", "cancer1")
            if self.logger:
                self.logger.debug(f"Using query from search_parameters: {self.search_word}")
        else:
            # fallback to standalone
            user_input = input("Enter your search query (default: cancer1): ").strip()
            self.search_word = user_input if user_input else "cancer1"
            if self.logger:
                self.logger.debug(f"Using fallback user-input query: {self.search_word}")

        return self.search_word

    def _load_existing_records(self, bib_path: Path) -> dict[str, dict]:
        """Load existing Prospero .bib records into a dictionary: ID -> record fields."""
        existing_records = {}
        if bib_path.is_file():
            with open(bib_path, "r", encoding="utf8") as bib_file:
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
        if self.logger:
            self.logger.info("Starting ProsperoSearchSource search method...")
        print("Starting ProsperoSearchSource search method...")  # Debug statement

        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--remote-debugging-port=9222')

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

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//table[@id='myDataTable']"))
                )
            except TimeoutException:
                print("No results found for this query.")
                if self.logger:
                    self.logger.warning("No results found for query.")
                return

            matches = driver.find_element(By.XPATH, "//table[@id='myDataTable']")
            rows = matches.find_elements(By.XPATH, ".//tr[@class='myDataTableRow']")
            # Remove header row if present
            if rows and rows[0].find_elements(By.XPATH, ".//th"):
                rows.pop(0)

            total_rows = len(rows)
            if total_rows == 0:
                print("No results found for this query.")
                if self.logger:
                    self.logger.info("No rows found.")
                return

            print(f"Found {total_rows} element(s)")  # Debug statement
            if self.logger:
                self.logger.info(f"Found {total_rows} elements in Prospero results.")

            # 1) Collect record IDs and metadata
            record_ids = []
            registered_dates_array = []
            titles_array = []
            review_status_array = []

            for i, row in enumerate(rows):
                tds = row.find_elements(By.XPATH, "./td")
                if len(tds) < 5:
                    print(f"Row {i} does not have enough columns.")
                    registered_dates_array.append("N/A")
                    titles_array.append("N/A")
                    review_status_array.append("N/A")
                    record_ids.append(None)
                    continue

                registered_date = tds[1].text.strip()
                title = tds[2].text.strip()
                review_status = tds[4].text.strip()

                registered_dates_array.append(registered_date)
                titles_array.append(title)
                review_status_array.append(review_status)

                # Attempt to retrieve the record ID
                try:
                    checkbox = tds[0].find_element(By.XPATH, ".//input[@type='checkbox']")
                    record_id = checkbox.get_attribute("data-checkid")  # data-checkid
                except NoSuchElementException:
                    record_id = None
                record_ids.append(record_id)

            # Extract authors & language
            language_array = []
            authors_array = []

            for i, record_id in enumerate(record_ids):
                if not record_id:
                    language_array.append("N/A")
                    authors_array.append("N/A")
                    continue

                detail_url = f"https://www.crd.york.ac.uk/prospero/display_record.php?RecordID={record_id}"
                driver.get(detail_url)

                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//div[@id='documentfields']"))
                    )
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, "//h1[text()='Language']"))
                        )
                        language_paragraph = driver.find_element(By.XPATH, "//h1[text()='Language']/following-sibling::p[1]")
                        language_details = language_paragraph.text.strip()
                    except (TimeoutException, NoSuchElementException):
                        language_details = "N/A"

                    try:
                        authors_div = driver.find_element(By.ID, "documenttitlesauthor")
                        authors_text = authors_div.text.strip()
                        authors_details = authors_text if authors_text else "N/A"
                    except NoSuchElementException:
                        authors_details = "N/A"

                except TimeoutException:
                    language_details = "N/A"
                    authors_details = "N/A"

                language_array.append(language_details)
                authors_array.append(authors_details)

                print(f"Row {i}: {titles_array[i]}, Language: {language_details}, Authors: {authors_details}")  # Debug
                if self.logger:
                    self.logger.info(
                        f"Prospero record row {i}: Title={titles_array[i]}, Language={language_details}, Authors={authors_details}"
                    )

            # Print collected data
            print("Registered Dates:")
            for d in registered_dates_array:
                print(d)
            print("Titles:")
            for t in titles_array:
                print(t)
            print("Review status:")
            for r in review_status_array:
                print(r)
            print("Language Details:")
            for l in language_array:
                print(l)
            print("Authors:")
            for a in authors_array:
                print(a)

            # Merge new records
            max_len = max(
                len(registered_dates_array),
                len(authors_array),
                len(titles_array),
                len(review_status_array),
                len(language_array),
            )
            new_records = []
            for idx in range(max_len):
                rec_id = record_ids[idx] if record_ids[idx] else f"no_id_{idx}"
                bib_entry = {
                    Fields.ENTRYTYPE: "article",
                    Fields.ID: "ID" + str(rec_id),
                    Fields.TITLE: titles_array[idx],
                    Fields.AUTHOR: authors_array[idx],
                    Fields.DOI: registered_dates_array[idx],
                    Fields.JOURNAL: "PROSPERO",
                    Fields.LANGUAGE: language_array[idx],
                    Fields.STATUS: review_status_array[idx],
                }
                new_records.append(bib_entry)

            # Save to Bib
            output_path = Path("data/search/records.bib")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            existing_records = self._load_existing_records(output_path)

            self._merge_new_results(existing_records, new_records)

            bib_db = BibDatabase()
            bib_db.entries = list(existing_records.values())

            with open(output_path, 'w', encoding='utf8') as bibfile:
                writer = BibTexWriter()
                bibfile.write(writer.write(bib_db))

            if output_path.exists():
                print(f"Results saved/updated to {output_path}")  # Debug statement
                if self.logger:
                    self.logger.info(f"Prospero results saved/updated to {output_path}")
            else:
                print("Failed to save the BibTeX file.")
                if self.logger:
                    self.logger.warning("Failed to save the BibTeX file to disk.")

        finally:
            driver.quit()

    def run_api_search(self, *, prospero_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool,) -> None:
        if rerun:
            self.review_manager.logger.info()
        

    def prep_link_md(self, prep_operation, record, save_feed=True, timeout=10):
        """Record-level metadata enrichment from Prospero, given a record ID."""
        record_id = record.get('ID')
        if not record_id:
            print("No ID provided in record, cannot link masterdata.")
            if self.logger:
                self.logger.warning("No ID in record for prep_link_md.")
            return record

        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--remote-debugging-port=9222')

        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            if self.logger:
                self.logger.error(f"WebDriver initialization failed: {e}")
            return record

        detail_url = f"https://www.crd.york.ac.uk/prospero/display_record.php?RecordID={record_id}"
        try:
            driver.get(detail_url)
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='documentfields']"))
            )

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//h1[text()='Language']"))
                )
                language_paragraph = driver.find_element(By.XPATH, "//h1[text()='Language']/following-sibling::p[1]")
                record['language'] = language_paragraph.text.strip()
            except (TimeoutException, NoSuchElementException):
                record['language'] = "N/A"

            try:
                authors_div = driver.find_element(By.ID, "documenttitlesauthor")
                authors_text = authors_div.text.strip()
                record['authors'] = authors_text if authors_text else "N/A"
            except NoSuchElementException:
                record['authors'] = "N/A"

            print(f"Masterdata linked for ID {record_id}: Language={record['language']}, Authors={record['authors']}")  # Debug
            if self.logger:
                self.logger.info(
                    f"Prospero masterdata linked for record {record_id}: "
                    f"Lang={record['language']}, Authors={record['authors']}"
                )

            if save_feed:
                print("Record updated. Would be saved to feed or further data structure.")
                if self.logger:
                    self.logger.debug("Record updated, feed saving not implemented here.")

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
            'title': 'article_title',
            'registered_date': 'registration_date',
            'review_status': 'status',
            'language': 'record_language',
            'authors': 'author_list',
        }
        for original_field, standard_field in field_mapping.items():
            if original_field in record:
                record[standard_field] = record.pop(original_field)

    def _load_bib(self) -> dict: 
        records = colrev.loader.load_utils.load(
            filename = self.search_source.filename,
            logger = self.review_manager.logger,
            unique_id_field = "ID",
        )
        return records

    def load(self,load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            return self._load_bib()
        raise NotImplementedError("Only .bib loading is implemented for ProsperoSearchSource.")

    @property
    def heuristic_status(self) -> SearchSourceHeuristicStatus:
        return self.__class__.heuristic_status

    @property
    def search_types(self):
        return self.__class__.search_types

    @property
    def settings_class(self):
        return self.__class__.settings_class

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
                self.review_manager.logger = logging.getLogger("ProsperoSearchSourceMock")
                self.review_manager.logger.setLevel(logging.DEBUG)
                handler = logging.StreamHandler(sys.stdout)
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.review_manager.logger.addHandler(handler)
                self.logger = self.review_manager.logger
                self.review_manager.logger.info("Initialized mock operation for ProsperoSearchSource demo.")
            except RepoSetupError as exc:
                print("RepoSetupError caught: ", exc)

                self.review_manager = None
                self.logger = None

    source_op = MockOperation()
    
    settings_dict = {}
    
    prospero_source = ProsperoSearchSource(source_operation=source_op, settings=settings_dict)
    
    prospero_source.search(rerun=False)
