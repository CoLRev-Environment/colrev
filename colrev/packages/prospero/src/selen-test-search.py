from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.remote.webelement import WebElement

chrome_options = Options()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--headless')

service = Service(executable_path=r'/workspaces/colrev/colrev/packages/prospero/bin/chromedriver')
driver = webdriver.Chrome(options = chrome_options, service=service)
driver.get("https://www.crd.york.ac.uk/prospero/")
driver.implicitly_wait(5)
print(driver.title) #browser opened properly
assert "PROSPERO" in driver.title

search_bar = driver.find_element(By.ID, "txtSearch")
search_bar.clear()
search_bar.send_keys("inverted-T")
search_bar.send_keys(Keys.RETURN)
print(driver.current_url) #browser navigated to search results web page successfully

matches = driver.find_elements(By.XPATH, "//tr[@class='myDataTableRow']")

if not matches:  # This evaluates to True if the list is empty
    print("No elements found")
else:
    print(f"Found {len(matches)} elements")

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

registered_date = []
title =[]
review_status = []


registered_date_elem = None
title_elem = None
review_status_elem = None

#extract register date, title and review status of each paper from result list
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
