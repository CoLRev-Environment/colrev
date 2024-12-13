from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.remote.webelement import WebElement
import zope.interface
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
from colrev.constants import SearchType
from colrev.constants import SearchSourceHeuristicStatus
from colrev.settings import SearchSource
from colrev.ops.search import Search
from pydantic import Field
import json
from pathlib import Path

chrome_options = Options()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--headless')

@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
class ProsperoSearchSource:
    """Prospero Search Source for retrieving protocol data"""

    # Default settings and attributes for the source
    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.prospero"
    source_identifier = "url"
    search_types = [SearchType.API]
    heuristic_status = SearchSourceHeuristicStatus.supported
    ci_supported: bool = Field(default=True)
    db_url = "https://www.crd.york.ac.uk/prospero/"

     
    def add_endpoint(
        cls,
        operation: Search,
        params: str,
    ) -> SearchSource:
        """Adds Prospero as a search source endpoint"""

        # Parse parameters into a dictionary
        params_dict = {}
        if params:
            if params.startswith("http"):  # Handle URL-based parameters
                params_dict = {"url": params}
            else:  # Handle key-value parameter strings
                for item in params.split(";"):
                    if "=" in item:
                        key, value = item.split("=", 1)  # Only split on the first '='
                        params_dict[key] = value
                    else:
                        raise ValueError(f"Invalid parameter format: {item}")

        # Generate a unique filename for storing Prospero search results
        # Keep the filename local to the prospero directory but simulate the required prefix
        filename = f"data/search/{operation.get_unique_filename(file_path_string='prospero_results')}"

        # Create the SearchSource object
        search_source = SearchSource(
            endpoint=cls.endpoint,
            filename=filename,
            search_type=SearchType.API,
            search_parameters=params_dict,
            comment="Search source for Prospero protocols",
        )

        # Register the search source
        operation.add_source_and_search(search_source)
        return search_source
    
    def search(self, rerun: bool) -> None:

        driver = webdriver.Chrome(options = chrome_options)
        driver.get("https://www.crd.york.ac.uk/prospero/")
        driver.implicitly_wait(5)
        print(driver.title) #browser opened properly
        assert "PROSPERO" in driver.title

        search_bar = driver.find_element(By.ID, "txtSearch")
        search_bar.clear()
        print("Enter search string:")
        search_string_input = input()
        search_bar.send_keys(search_string_input)
        search_bar.send_keys(Keys.RETURN)
        print(driver.current_url) #browser navigated to search results web page successfully

        matches = driver.find_element(By.XPATH, "//table[@id='myDataTable']")
        matches1 = matches.find_elements(By.XPATH, "//tr[@class='myDataTableRow']")
        matches1.pop(0)
        print(matches1)
        
        if not matches1:  # This evaluates to True if the list is empty
            print("No elements found")
        else:
            print(f"Found {len(matches1)} element(s)")

        def retry_find_elem(web_elem: WebElement, byXpath: str) -> bool:
            result = False
            attempts = 0
            while(attempts < 3):
                try:
                    web_elem.find_element(By.XPATH, byXpath)
                    result = True
                except StaleElementReferenceException:
                    attempts += 1
            return result

        registered_date = None
        title = None
        review_status = None

        registered_dates_array = []
        titles_array = []
        review_status_array = []

        matches1 = WebDriverWait(driver, 10).until(
    EC.presence_of_all_elements_located((By.XPATH, "//table[@id='myDataTable']//tr[@class='myDataTableRow']"))
)
        for row in matches1:
            try:
                registered_date = row.find_element(By.XPATH, "./td[2]").text
                registered_dates_array.append(registered_date)
                title = row.find_element(By.XPATH, "./td[3]").text
                titles_array.append(title)
                review_status = row.find_element(By.XPATH, "./td[5]").text
                review_status_array.append(review_status)
            except Exception as e:
                print(f"Error extracting content for a row: {e}")


        print("Registered Dates:")
        for date in registered_dates_array:
            print(date)

        print("Titles: ")
        for titles in titles_array:
            print(titles)

        print("Review status: ")
        for review in review_status_array:
            print(review)

        #assert "No results found." not in driver.page_source
        driver.close()
    search(self=1,rerun=bool)
