#pip install selenium webdriver-manager pandas
#may need to run webdriver-manager install as administrator

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time

# Set up the Selenium WebDriver with Chrome
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run in headless mode (no browser UI)
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")

driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

# Navigate to the page with the JavaScript-rendered table
url = "https://www.doge.gov/savings"
driver.get(url)

# Optional: Wait for the page to fully load
wait = WebDriverWait(driver, 10)

# Repeatedly click the "Show More" button until all content is loaded

# Click "Savings" button to view by claimed saved instead of TCV
try:
    savings_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Savings']")))
    savings_button.click()
except:
    print("Unable to click Savings button.")

# Click both "see more" buttons on the table in order to show all rows.
while True:
    try:
        # Locate and click the "Show More" button
        show_more_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//td[text()='see more']")))
        show_more_button.click()
        print("I click...")
        time.sleep(5)  # Wait for new data to load
    except Exception as e:
        print("No more 'see more' buttons found or error occurred:", e)
        break

# Now extract the table data after all elements are loaded
doge_desc_list = list()

tables = driver.find_elements(By.TAG_NAME, "table")

table_dfs = []  # To store data from all tables

for index, table in enumerate(tables):
    rows = table.find_elements(By.TAG_NAME, "tr")
    table_data = []
    for rowdex, row in enumerate(rows[1:]):
        if index == 0:
            # DOGE Site requires clicking each entry to get the full descriptions
            # TODO stop using xpath. will need maintainence if site changes.
            print("Clicking buttons...")
            try:
                time.sleep(0.25)
                row.click()

                # Wait for the modal to be visible
                modal = wait.until(EC.visibility_of_element_located((By.XPATH, "/html/body/div/main/div/div/div[6]/div/div")))


                # Extract paragraph text
                paragraph = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div/main/div/div/div[6]/div/div/div/div[2]/p[2]")))
                doge_desc = paragraph.text


                # Click the close button
                # /html/body/div/main/div/div/div[6]/div/div/div/div[3]/button[2]
                try:
                    close_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div/main/div/div/div[6]/div/div/div/div[3]/button[2]")))
                    close_button.click()
                except:
                    # Don't laugh it works ok?
                    try:
                        close_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div/main/div/div/div[6]/div/div/div/div[3]/button"))) # If contract isn't available, there's no button to view contract.
                        close_button.click()
                    
                    except:
                        print("Cannot close modal! Giving up!")
                        driver.quit()
                print("Clicked the button...")

                # Wait for the modal to disappear before continuing
                wait.until(EC.invisibility_of_element(modal))
                
            except Exception as e:
                doge_desc = "error"
                print(e)
                print("Failed to get doge description")

        else:
            doge_desc = ""

        cells = row.find_elements(By.TAG_NAME, "td")
        row_data = []
        for cell in cells:
            # Check if the cell contains an anchor tag
            if len(cell.find_elements(By.TAG_NAME, "a")) > 0:
                text = cell.find_element(By.TAG_NAME, "a").get_attribute("href")
            else:
                text = cell.text.strip()  # Extract text
            row_data.append(text)
        row_data.append(doge_desc)
        table_data.append(row_data)
    
    table_dfs.append(pd.DataFrame(table_data))

contracts = table_dfs[0]
contracts.drop(columns=[1], inplace=True) # Remove partial description
contracts.columns = ["Doge Agency", "Doge Upload Date", "Contract URL", "Doge Value", "Doge Desc"]
contracts.to_csv("contracts.csv", index=False)

real_estate = table_dfs[1] # Remove ghost
real_estate.drop(columns=[4], inplace=True)
real_estate.columns = ["Main Agency", "Location", "Sqare Feet", "Doge Value"]
real_estate.to_csv("real_estate.csv", index=False)

driver.quit()