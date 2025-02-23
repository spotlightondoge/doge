from playwright.sync_api import sync_playwright
import pandas as pd
from bs4 import BeautifulSoup
import numpy as np  # Import for handling NaN values
import asyncio
from playwright.async_api import async_playwright

MAX_WORKERS = 10

# Load the CSV containing doge data
input_csv = "contracts.csv"  # Change this to your actual CSV filename
df_urls = pd.read_csv(input_csv, encoding="utf-8")

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
csv_name = "full_contracts_dataset.csv"
df_final.to_csv(csv_name, index=False)

print(f"Scraped data saved to {csv_name}")