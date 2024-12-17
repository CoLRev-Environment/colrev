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

def record_info(driver: WebDriver,
                records: WebElement, 
                record_ids : [], # type: ignore
                registered_dates_array: [], # type: ignore
                titles_array: [], # type: ignore
                review_status_array: [], # type: ignore
                original_search_window: str) -> None:

    for i, row in enumerate(records):
        tds = row.find_elements(By.XPATH, "./td")

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

    for x, record_id in enumerate(record_ids):

        detail_url = f"https://www.crd.york.ac.uk/prospero/display_record.php?RecordID={record_id}"
        driver.switch_to.new_window('tab')
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
        finally:
            assert len(driver.window_handles) > 1
            driver.close()
            driver.switch_to.window(original_search_window)
            print(driver.window_handles)
        language_array.append(language_details)
        authors_array.append(authors_details)
        print(f"Row {x}: {titles_array[x]}, Language: {language_details}, Authors: {authors_details}", flush=True)
           