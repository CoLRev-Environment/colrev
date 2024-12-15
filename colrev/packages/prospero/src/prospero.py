from pathlib import Path
import bibtexparser
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
from colrev.constants import Fields, SearchType
from colrev.constants import SearchSourceHeuristicStatus
from colrev.settings import SearchSource
from colrev.ops.search import Search

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

    # def __init__(self):

    @classmethod
    def add_endpoint(cls, operation: Search, params: str) -> SearchSource:
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

        filename = f"data/search/{operation.get_unique_filename(file_path_string='prospero_results')}"
        search_source = SearchSource(
            endpoint=cls.endpoint,
            filename=filename,
            search_type=SearchType.API,
            search_parameters=params_dict,
            comment="Search source for Prospero protocols",
        )
        operation.add_source_and_search(search_source)
        return search_source

    # @classmethod
    # def heuristic

    def get_search_word(self):
        if hasattr(self, 'search_word') and self.search_word is not None:
            return self.search_word
        try:
            self.search_word = self.settings.search_parameters.get("query", "cancer1")
        except AttributeError:
            user_input = input("Enter your search query (default: cancer1): ").strip()
            self.search_word = user_input if user_input else "cancer1"
        return self.search_word

    def search(self, rerun: bool) -> None:
        print("Starting search method...", flush=True)
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--remote-debugging-port=9222')

        driver = webdriver.Chrome(options=chrome_options)

        try:
            # Navigate to Prospero homepage and search
            driver.get("https://www.crd.york.ac.uk/prospero/")
            driver.implicitly_wait(5)
            assert "PROSPERO" in driver.title

            search_word = self.get_search_word()
            search_bar = driver.find_element(By.ID, "txtSearch")
            search_bar.clear()
            search_bar.send_keys(search_word)
            search_bar.send_keys(Keys.RETURN)

            # Wait for results or no results
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//table[@id='myDataTable']"))
                )
            except TimeoutException:
                print("No results found for this query.")
                return

            matches = driver.find_element(By.XPATH, "//table[@id='myDataTable']")
            rows = matches.find_elements(By.XPATH, ".//tr[@class='myDataTableRow']")
            # Remove header row if present
            if rows and rows[0].find_elements(By.XPATH, ".//th"):
                rows.pop(0)

            total_rows = len(rows)
            if total_rows == 0:
                print("No results found for this query.")
                return

            print(f"Found {total_rows} element(s)")

            # collect record IDs and basic info
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

                checkbox = tds[0].find_element(By.XPATH, ".//input[@type='checkbox']")
                record_id = checkbox.get_attribute("data-checkid")
                record_ids.append(record_id)

            # for each record, load detail page and extract authors/language
            language_array = []
            authors_array = []
            for i, record_id in enumerate(record_ids):
                if record_id is None:
                    # Already handled these as N/A
                    language_array.append("N/A")
                    authors_array.append("N/A")
                    continue

                detail_url = f"https://www.crd.york.ac.uk/prospero/display_record.php?RecordID={record_id}"
                driver.get(detail_url)

                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//div[@id='documentfields']"))
                    )
                    # Extract language
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, "//h1[text()='Language']"))
                        )
                        language_paragraph = driver.find_element(By.XPATH, "//h1[text()='Language']/following-sibling::p[1]")
                        language_details = language_paragraph.text.strip()
                    except (TimeoutException, NoSuchElementException):
                        language_details = "N/A"

                    # Extract authors
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
                print(f"Row {i}: {titles_array[i]}, Language: {language_details}, Authors: {authors_details}", flush=True)

            # Print summary
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
            
            max_len= max(len(registered_dates_array),len(authors_array),len(titles_array),len(review_status_array),len(language_array))
            records_bib = []
            for record in range(max_len): 
                test_rec = {
                    Fields.TITLE: titles_array[record],
                    Fields.AUTHOR: authors_array[record],
                    Fields.DOI: registered_dates_array[record],
                    Fields.JOURNAL: "PROSPERO",
                    Fields.LANGUAGE: language_array[record],
                    Fields.STATUS: review_status_array[record],
                    Fields.ID: "ID"+record_ids[record],                  
                    Fields.ENTRYTYPE: "article",
                }
                records_bib=[*records_bib,test_rec]
        
            bib_database = bibtexparser.bibdatabase.BibDatabase()
            bib_database.entries = records_bib
            with open("prospero.bib", 'w') as bibfile:
                bibtexparser.dump(bib_database, bibfile)

            print("Done.", flush=True)

        finally:
            driver.quit()

    def prep_link_md(self, prep_operation, record, save_feed=True, timeout=10):
        """Given a record with ID, fetch authors and language from Prospero."""
        record_id = record.get('ID')
        if not record_id:
            print("No ID provided in record, cannot link masterdata.")
            return record

        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--remote-debugging-port=9222')

        driver = webdriver.Chrome(options=chrome_options)
        detail_url = f"https://www.crd.york.ac.uk/prospero/display_record.php?RecordID={record_id}"
        try:
            driver.get(detail_url)
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='documentfields']"))
            )

            # Extract language
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//h1[text()='Language']"))
                )
                language_paragraph = driver.find_element(By.XPATH, "//h1[text()='Language']/following-sibling::p[1]")
                record['language'] = language_paragraph.text.strip()
            except (TimeoutException, NoSuchElementException):
                record['language'] = "N/A"

            # Extract authors
            try:
                authors_div = driver.find_element(By.ID, "documenttitlesauthor")
                authors_text = authors_div.text.strip()
                record['authors'] = authors_text if authors_text else "N/A"
            except NoSuchElementException:
                record['authors'] = "N/A"

            print(f"Masterdata linked for ID {record_id}: Language={record['language']}, Authors={record['authors']}")

            if save_feed:
                print("Record updated and would be saved to feed.")
        except TimeoutException:
            print(f"Timeout while linking masterdata for ID {record_id}")
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

    # def load(self, load_operation) -> 
    def _load_bib(self) -> dict: 
        records = colrev.loader.load_utils.load(
            filename = self.search_source.filename,
            logger = self.review_manager.logger,
            unique_id_field = "ID",
        )
        return records
    
    @classmethod
    def load(self,load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            return self._load_bib()
        
        raise NotImplementedError

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
    prospero_source = ProsperoSearchSource()
    prospero_source.search(rerun=False)
