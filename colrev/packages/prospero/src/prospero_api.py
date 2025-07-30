#!/usr/bin/env python
"""Module emulating an API for Prospero results pages."""
import logging
import math
import time
import typing

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class PROSPEROAPI:
    """PROSPERO API class to extract records from Prospero."""

    URL_PREFIX = "https://www.crd.york.ac.uk/prospero/display_record.php?RecordID="

    def __init__(self, search_word: str, logger: logging.Logger) -> None:

        self.search_word = search_word

        self.logger = logger

        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except WebDriverException as exc:
            self.logger.error(f"Error initializing WebDriver: {exc}")

        self.nr_pages = 0
        self.current_page_index = 1
        self.page_index_displayed = 0
        self.original_search_window = None

    def _navigate_to_search_page(self) -> None:
        self.driver.get("https://www.crd.york.ac.uk/prospero/")
        self.driver.implicitly_wait(5)
        assert "PROSPERO" in self.driver.title

        search_bar = self.driver.find_element(By.ID, "txtSearch")
        search_bar.clear()
        search_bar.send_keys(self.search_word)
        search_bar.send_keys(Keys.RETURN)

        self.original_search_window = self.driver.current_window_handle

        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//table[@id='myDataTable']"))
            )
        except TimeoutException as exc:
            self.logger.info("No results found for this query.")
            self.driver.quit()
            raise TimeoutException from exc

        hit_count = int(
            self.driver.find_element(By.XPATH, "//div[@id='hitcountleft']/span[1]").text
        )
        self.logger.info(f"Found {hit_count} record(s) for {self.search_word}")

        if hit_count == 0:
            self.logger.info("No results found for this query.")
            self.driver.quit()
            return
        self.nr_pages = math.ceil(hit_count / 50)

    def _set_page_index_displayed(self) -> None:
        try:
            self.page_index_displayed = self.driver.find_element(
                By.XPATH, "//td[@id='pagescount']"
            ).text
        finally:
            self.page_index_displayed = self.driver.find_element(
                By.XPATH, "//td[@id='pagescount']"
            ).text
        self.logger.info(f"Records from {self.page_index_displayed}")

    def _navigate_to_next_page(self) -> None:
        try:
            WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//td[@title='Next page']"))
            ).click()
            time.sleep(3)
        except WebDriverException as e:
            self.logger.error("Failed to navigate to next page. %s", e)
        finally:
            self.logger.debug("Data from page %s retrieved.", self.page_index_displayed)
            self.logger.debug("Finished retrieving data from current result page.")
        self.current_page_index += 1

    def _get_records_from_page(self) -> typing.List[WebElement]:

        table_of_matches = self.driver.find_element(
            By.XPATH, "//table[@id='myDataTable']"
        )
        records = table_of_matches.find_elements(
            By.XPATH, ".//tr[@class='myDataTableRow']"
        )

        if records and records[0].find_elements(By.XPATH, ".//th"):
            records.pop(0)
        return records

    def _format_author(self, author_string: str) -> str:
        """Convert authors to colrev format"""
        particles = {"de", "del", "la", "van", "von", "der", "di", "da", "le"}

        if author_string.startswith("{{") and author_string.endswith("}}"):
            return author_string

        formatted_list = []
        for author in author_string.split(","):

            parts = author.split()
            if len(parts) < 2:
                formatted_list.append(author)

            last_name = parts[-1]

            first_names = " ".join(parts[:-1])

            if len(parts) > 2 and parts[-2].lower() in particles:
                last_name = f"{{{' '.join(parts[-2:])}}}"
                first_names = " ".join(parts[:-2])

            formatted_list.append(f"{last_name}, {first_names}")
        return " and ".join(formatted_list)

    def _parse_record(self, record: WebElement) -> dict:
        tds = record.find_elements(By.XPATH, "./td")

        record_id = (
            tds[0]
            .find_element(By.XPATH, ".//input[@type='checkbox']")
            .get_attribute("data-checkid")
        )
        registered_date = tds[1].text.strip().split("/")[-1]
        review_status = tds[4].text.strip()

        detail_url = f"{self.URL_PREFIX}{record_id}"
        record_dict = {
            Fields.ENTRYTYPE: "misc",
            Fields.ID: record_id,
            Fields.PROSPERO_ID: record_id,
            Fields.AUTHOR: "N/A",
            Fields.TITLE: "N/A",
            "colrev.prospero.registered_date": registered_date,
            "colrev.prospero.status": f"{review_status}",
            Fields.URL: detail_url,
            "note": f"PROSPERO registration number: {record_id}",
            "howpublished": f"\\url{{{detail_url}}}",
        }

        self.driver.switch_to.new_window("tab")
        self.driver.get(detail_url)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@id='documentfields']")
                )
            )

            # Extract language
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//h1[text()='Language']")
                    )
                )
                language_paragraph = self.driver.find_element(
                    By.XPATH, "//h1[text()='Language']/following-sibling::p[1]"
                )
                record_dict[Fields.LANGUAGE] = language_paragraph.text.strip().replace(
                    "English", "eng"
                )
            except (TimeoutException, NoSuchElementException):
                pass

            # Extract authors
            try:
                authors_div = self.driver.find_element(By.ID, "documenttitlesauthor")
                record_dict[Fields.AUTHOR] = (
                    self._format_author(authors_div.text.strip()) or "N/A"
                )
            except NoSuchElementException:
                pass

            # Extract title
            try:
                title_div = self.driver.find_element(By.ID, "documenttitlestitle")
                record_dict[Fields.TITLE] = title_div.text.strip() or "N/A"
            except NoSuchElementException:
                pass

        except TimeoutException:
            pass

        finally:
            # Close the detail tab and switch back to the original search page
            assert len(self.driver.window_handles) > 1
            self.driver.close()
            self.driver.switch_to.window(self.original_search_window)

        return record_dict

    def get_next_record(self) -> typing.Iterator[dict]:
        """Extract record details from Prospero and yield them as dictionaries."""

        try:
            self._navigate_to_search_page()

            while self.current_page_index <= self.nr_pages:

                self._set_page_index_displayed()

                for record in self._get_records_from_page():
                    yield self._parse_record(record)

                self._navigate_to_next_page()

            self.logger.info("All records displayed and retrieved.")

        finally:
            self.driver.quit()
