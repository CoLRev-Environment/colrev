from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException,StaleElementReferenceException
import logging
import time
from colrev.packages.prospero.src.extract_from_each_article import get_record_info
#from bibtexparser.bibdatabase import BibDatabase
#from bibtexparser.bwriter import BibTexWriter
import zope.interface
import colrev.package_manager.interfaces
import colrev.package_manager.package_settings
from colrev.constants import SearchType
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
            user_input = input("Enter search term (default: cancer1): ").strip()
            self.search_word = user_input if user_input else "cancer1"
        return self.search_word

    def search(self, rerun: bool) -> None:

        record_id_array = []
        registered_date_array = []
        title_array = []
        review_status_array = []

        logger = logging.getLogger()

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

            original_search_window = driver.current_window_handle
            
            # Wait for results or no results
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//table[@id='myDataTable']"))
                )
            except TimeoutException:
                print("No results found for this query.")
                return

            # Determine number of results found 
            hit_count = int(driver.find_element(By.XPATH, "//div[@id='hitcountleft']/span[1]").text)
            print(f"Found {hit_count} element(s) for {search_word}")
            
            # Calculate number of result pages manually to loop through since no indicator for last page 
            page_count = None
            if hit_count == 0:
                print("No results found for this query.")
                return
            elif hit_count < 51:
                page_count = 1
            else:
                page_count = hit_count // 50

            start_index = 1
            while start_index <= page_count:

                table_of_matches = driver.find_element(By.XPATH, "//table[@id='myDataTable']")
                records = table_of_matches.find_elements(By.XPATH, ".//tr[@class='myDataTableRow']")
                # Remove header row if present
                if records and records[0].find_elements(By.XPATH, ".//th"):
                    records.pop(0)
                
                try:
                    page_index = driver.find_element(By.XPATH, "//td[@id='pagescount']").text
                finally: 
                    page_index = driver.find_element(By.XPATH, "//td[@id='pagescount']").text
                print(f"Displaying records on {page_index}")

                # collect record IDs and basic info
                try: 
                    get_record_info(driver,
                                    records,
                                    record_id_array,
                                    registered_date_array,
                                    title_array,
                                    review_status_array,
                                    original_search_window)
                except StaleElementReferenceException:
                    logger.error("Failed loading results: StaleElementReferenceException")
                print(f"Current window handle: {driver.window_handles}")

                #click to next page
                try:
                    WebDriverWait(driver,3).until(
                    EC.element_to_be_clickable((By.XPATH, "//td[@title='Next page']"))
                ).click()
                    time.sleep(3)
                except:
                    print("I cannot do this anymore omg the driver is not clicking on the next fucking button.")
                finally:
                    start_index+= 1
                    print(f"Finished retrieving data from current result page. Moving on to next page...")
            
            print("All records displayed and retrieved.", flush=True)
        
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
