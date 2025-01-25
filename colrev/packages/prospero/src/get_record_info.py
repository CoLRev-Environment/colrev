"""
Module providing get_record_info() to extract record details from Prospero results pages.
"""
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# Disable rules for too-many-args/locals/positional-args/statements
# since we want minimal changes here
# pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments,too-many-statements
def get_record_info(
    driver: WebDriver,
    records: WebElement,
    record_id_array: list[str],
    registered_date_array: list[str],
    title_array: list[str],
    review_status_array: list[str],
    language_array: list[str],
    authors_array: list[str],
    original_search_window: str,
    page_increment: int,
) -> None:
    """
    Extract record details from Prospero search-result elements and populate various arrays.

    :param driver: Selenium WebDriver instance.
    :param records: A WebElement representing rows of records on the page.
    :param record_id_array: Collects extracted record IDs.
    :param registered_date_array: Collects registration dates.
    :param title_array: Collects record titles.
    :param review_status_array: Collects review statuses.
    :param language_array: Collects extracted languages.
    :param authors_array: Collects extracted authors.
    :param original_search_window: Window handle of the original search page.
    :param page_increment: Current page increment, used in output printing.
    :return: None (modifies the provided arrays in-place).
    """

    record_id_array_pro_page: list[str] = []

    # Extract basic info: record ID, registration date, review status
    for _, record in enumerate(records):
        tds = record.find_elements(By.XPATH, "./td")

        registered_date = tds[1].text.strip().split("/")[-1]
        review_status = tds[4].text.strip()

        registered_date_array.append(registered_date)
        review_status_array.append(review_status)

        checkbox = tds[0].find_element(By.XPATH, ".//input[@type='checkbox']")
        record_id = checkbox.get_attribute("data-checkid")
        record_id_array_pro_page.append(record_id)

    record_id_array.extend(record_id_array_pro_page)
    # For each record in this page, open its detail page in a new tab,
    # extract language, authors, and title, then close the tab.
    for x, record_id in enumerate(record_id_array_pro_page, start=1):
        detail_url = f"https://www.crd.york.ac.uk/prospero/display_record.php?RecordID={record_id}"
        driver.switch_to.new_window("tab")
        driver.get(detail_url)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@id='documentfields']")
                )
            )
            # Extract language
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//h1[text()='Language']")
                    )
                )
                language_paragraph = driver.find_element(
                    By.XPATH, "//h1[text()='Language']/following-sibling::p[1]"
                )
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

            # Extract title
            try:
                title_div = driver.find_element(By.ID, "documenttitlestitle")
                title_text = title_div.text.strip()
                title_details = title_text if title_text else "N/A"
            except NoSuchElementException:
                title_details = "N/A"

        except TimeoutException:
            language_details = "N/A"
            authors_details = "N/A"
            title_details = "N/A"

        finally:
            # Close the detail tab and switch back to the original search page
            assert len(driver.window_handles) > 1
            driver.close()
            driver.switch_to.window(original_search_window)

        language_array.append(language_details)
        authors_array.append(authors_details)
        title_array.append(title_details)

        print(
            f"Record {x + page_increment * 50}: [ID: {record_id}] {title_details}",
            flush=True,
        )
