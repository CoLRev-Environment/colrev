#! /usr/bin/env python
"""SearchSource: Prospero"""
import zope.interface
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
from colrev.constants import SearchType
from colrev.constants import SearchSourceHeuristicStatus
from colrev.settings import SearchSource
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.remote.webelement import WebElement
from pydantic import Field
import json
from pathlib import Path
from colrev.ops.search import Search


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

    @classmethod
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

    def load(self, filename: Path) -> dict:
        """
        Load search results from a Prospero result file.

        Args:
            filename (Path): The path to the results JSON file.

        Returns:
            dict: A dictionary containing the loaded search results.
        """
        try:
            # Ensure the file exists before attempting to load it
            if not filename.is_file():
                raise FileNotFoundError(f"File not found: {filename}")

            # Read and parse the file
            with open(filename, "r", encoding="utf-8") as file:
                data = json.load(file)

            # Validate the structure of the loaded data (if needed)
            if not isinstance(data, dict):
                raise ValueError("Invalid file format: Expected a JSON object")

            # Return the parsed data
            return data
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
            # Log and handle errors gracefully
            print(f"Error loading file {filename}: {e}")
            return {}


if __name__ == "__main__":
    # Mock a Search operation
    class MockSearchOperation:
        def get_unique_filename(self, file_path_string: str) -> str:
            return f"{file_path_string}.json"

        def add_source_and_search(self, search_source):
            print(f"Search source added: {search_source}")

    # Create a test case for add_endpoint()
    search_op = MockSearchOperation()
    params = "url=https://www.crd.york.ac.uk/prospero/?search=cancer"

    # Call add_endpoint
    try:
        endpoint = ProsperoSearchSource.add_endpoint(search_op, params)
        print(f"Generated Search Source: {endpoint}")
    except ValueError as e:
        print(f"Error in add_endpoint: {e}")
     # Test the load method
    try:
        prospero_source = ProsperoSearchSource()
        filename = Path("colrev/packages/prospero/bin/prospero_results.json")
        loaded_data = prospero_source.load(filename)
        print(f"Loaded Data: {loaded_data}")
    except Exception as e:
        print(f"Error in load: {e}")

    
    def search(self, rerun: bool) -> None:

        """Run a search on Prospero"""

        service = Service(executable_path=r'/workspaces/colrev/colrev/packages/prospero/bin/chromedriver')
        driver = webdriver.Chrome(options = chrome_options, service=service)
        driver.get("https://www.crd.york.ac.uk/prospero/")
        driver.implicitly_wait(5)
        print(driver.title) #browser opened properly
        assert "PROSPERO" in driver.title

        search_bar = driver.find_element(By.ID, "txtSearch")
        search_bar.clear()
        search_bar.send_keys("inverted-T") #TODO: keyword input from user
        search_bar.send_keys(Keys.RETURN)
        print(driver.current_url) #browser navigated to search results web page successfully

        matches = driver.find_elements(By.XPATH, "//tr[@class='myDataTableRow']")

        #validate that matches are not empty
        if not matches:  # This evaluates to True if the list is empty
            print("No elements found")
        else:
            print(f"Found {len(matches)} elements")

        #TODO: handle stale element exception
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

        #create empty array for articles' data
        registered_date = []
        title =[]
        review_status = []


        registered_date_elem = None
        title_elem = None
        review_status_elem = None

        #extract register date, title and review status of each paper into arrays
        for match in matches:
            if retry_find_elem(match,'./td[2]'):
                registered_date.append(match.find_element(By.XPATH, './td[2]').text)
            else:
                registered_date_elem = match.find_element(By.XPATH, './td[2]')
                registered_date.append(registered_date_elem.text)
            if retry_find_elem(match,'./td[3]'):
                title.append(match.find_element(By.XPATH, './td[3]').text)    
            else:
                title_elem = match.find_element(By.XPATH, './td[3]')
                title.append(title_elem.text)
            if retry_find_elem(match, '.td[5]'):
                review_status.append(match.find_element(By.XPATH, './td[5]').text)
            else:
                review_status_elem = match.find_element(By.XPATH, './td[5]')
                review_status.append(review_status_elem.text)
    
        print(registered_date)
        print(title)
        print(review_status)

        #assert "No results found." not in driver.page_source
        driver.close()