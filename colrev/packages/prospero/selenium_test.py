import os  # Add this import
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

# Use the path to ChromeDriver in $HOME/bin
service = Service("/workspaces/colrev/colrev/packages/prospero/bin/chromedriver")
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run without opening a browser
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=service, options=options)

driver.get("https://www.google.com")
print(driver.title)

driver.quit()

