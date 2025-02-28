#pip install selenium webdriver-manager pandas
#may need to run webdriver-manager install as administrator

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import numpy as np  # Import for handling NaN values
import asyncio
from playwright.async_api import async_playwright
import time

#### SCRAPE DOGE ####

MAX_WORKERS = 10
# Set up the Selenium WebDriver with Chrome
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run in headless mode (no browser UI)
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
timestamp = str(int(time.time()))
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
        print(f"{rowdex}: {row.find_elements(By.TAG_NAME, 'td')[1].text}")
        if index == 0:
            # DOGE Site requires clicking each entry to get the full descriptions
            # TODO stop using xpath. will need maintainence if site changes.
            print("Clicking buttons...")
            try:
                time.sleep(0.50)
                row.click()

                # Wait for the modal to be visible
                modal = wait.until(EC.visibility_of_element_located((By.XPATH, "/html/body/div/main/div/div/div[6]/div/div")))


                # Extract paragraph text
                paragraph = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div/main/div/div/div[6]/div/div/div/div[2]/p[2]")))
                doge_desc = paragraph.text


                # Click the close button
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

real_estate = table_dfs[1] # Remove ghost
real_estate.drop(columns=[4], inplace=True)
real_estate.columns = ["Main Agency", "Location", "Sqare Feet", "Doge Value"]
real_estate.to_csv("real_estate.csv", index=False)
real_estate.to_csv(f"datasets/DOGE/real_estate{timestamp}.csv", index=False)
driver.quit()


#### SCRAPE FPDS CONTRACTS ####




# Load the CSV containing doge data
df_urls = contracts

# Convert URLs to strings and strip spaces/newlines
df_urls["Contract URL"] = df_urls["Contract URL"].astype(str).str.strip()

# Replace "nan" and other invalid placeholders with an empty string
df_urls["Contract URL"] = df_urls["Contract URL"].replace(["nan", "SEE FPDS", "N/A", "TBD", "", " "], np.nan)

# Create a boolean column to mark valid URLs
df_urls["Valid URL"] = df_urls["Contract URL"].notna()  # `True` if it's a valid URL

# Keep a copy of the full dataset (including invalid URLs)
df_full = df_urls.copy()

# Filter out only valid URLs for scraping
df_valid_urls = df_urls[df_urls["Valid URL"]]

# Debugging: Print filtered count
print(f"Total records: {len(df_urls)} | Valid URLs to scrape: {len(df_valid_urls)}")

async def scrape_contract(browser, url):
    input_data = {"Contract URL": url}
    page = await browser.new_page()

    try:
        await page.goto(url, wait_until="networkidle")  # Adjust timeout if needed
        
        # Await these calls
        text_inputs = await page.query_selector_all("input[type='text'][readonly]")
        text_areas = await page.query_selector_all("textarea")
        display_texts = await page.query_selector_all(".displayText")
        select_inputs = await page.query_selector_all("select")

        # Extract readonly text input values
        for input_field in text_inputs:
            name = await input_field.get_attribute("name")
            value = await input_field.get_attribute("value")
            input_data[name] = value  # Store form field data

        for textarea_field in text_areas:
            name = await textarea_field.get_attribute("name")
            value = await textarea_field.input_value()
            input_data[name] = value
        
        for display_text_field in display_texts:
            name = await display_text_field.get_attribute("id")
            value = await display_text_field.inner_text()
            input_data[name] = value

        # Extract selected option values from dropdowns
        for select_field in select_inputs:
            name = await select_field.get_attribute("name")
            selected_option = await select_field.query_selector("option[selected]")
            if selected_option:
                value = await selected_option.inner_text()
                input_data[name] = value
        
        print(f"✅ {url}")
        return input_data

    except Exception as e:
        print(f"❌ {url} | Error: {e}")
        return input_data  # Skip invalid URLs gracefully

    finally:
        await page.close()

async def process_urls(url_list):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(MAX_WORKERS)  # Adjust concurrency limit

        async def bound_scrape(url):
            async with semaphore:
                return await scrape_contract(browser, url)

        tasks = [bound_scrape(row["Contract URL"]) for _, row in url_list.iterrows()]
        results = await asyncio.gather(*tasks)

        await browser.close()
        return [r for r in results if r is not None]

# Run the async scraper
all_data = asyncio.run(process_urls(df_valid_urls))

df_scraped = pd.DataFrame(all_data)

# Merge scraped data back into full dataset (including rows with invalid URLs)
df_final = df_full.merge(df_scraped, on=["Contract URL"], how="left")

# Save final results

csv_name = f"datasets/DOGE/full_contracts_dataset_{timestamp}.csv"
df_final.to_csv("test.csv", index=False)
df_final.to_csv(csv_name, index=False)

print(f"Scraped data saved to {csv_name}")