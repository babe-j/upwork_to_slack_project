import json
import csv
import asyncio
from playwright.async_api import async_playwright
from urllib.parse import urljoin
import os 
import logging 
from cookies import cookies

logging.basicConfig(level=logging.INFO)

target_url = 'https://www.upwork.com/nx/search/jobs/'
cookies_path = r"/mnt/c/Users/user/upwork_to_slack_project/upwork_to_slack/Cookies/cookies.json"


def save_to_csv(data:list, first_time:bool):
    mode = 'w' if first_time else 'a'
    with open("upwork_jobs.csv", mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        if first_time: 
            writer.writeheader()
        writer.writerows(data)

def get_cookies(path:str):
    if not os.path.exists(path):
        logging.info("Cookies file not found.")
        return []
    with open(path, 'r') as f:
        cookies = json.load(f)
        logging.info('getting cookies...')
        return cookies.get('cookies')
    
async def ensure_cookies():
    """Ensure the cookies file exists by generating it if missing."""
    if not os.path.exists(cookies_path):
        logging.info("Creating cookies file...")
        await cookies(target_url)
         
async def scrape_upwork(path:str, max_retries: int = 1):
    try:
        await ensure_cookies()
        async with async_playwright() as p:
            retries = 1
            while retries <= max_retries:
                try:
                    browser = browser = await p.chromium.launch(channel="chrome", headless=False)
                    context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36")
                
                    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    context.set_default_timeout(180000)
                    await context.add_cookies(get_cookies(cookies_path))
   
                    page = await context.new_page()
                    response = await page.goto(target_url, timeout=100000)
                    status = response.status if response else None
                    if not response or not response.ok:           
                        if status == 403:
                            if retries > max_retries:
                               return
                            logging.info(f"{status} response! Atempt {retries} of {max_retries} ")
                            await asyncio.sleep(5)
                            await browser.close()
                            await cookies(target_url)
                            retries +=1
                            continue 
                        else:
                            logging.error(f"Non-200 response: {status if response else 'No response'}")
                            return
                        
                    logging.info(f"loaded page successfully {status}.")
                            
                except Exception as e:
                    await browser.close()
                    logging.error(f"GOTO failed: {e}") 
                    return

            
            logging.info("waiting until site is stable")
            await page.wait_for_load_state('domcontentloaded')
            try:
                # Adjust the selector based on the actual button text or CSS selector
                await page.click("text='Accept All'", timeout=5000)
                logging.info("Cookies accepted.")
            except:
                logging.info("No cookie banner found or already accepted.")

            logging.info("waiting for selector....")
            await page.wait_for_selector('article.job-tile.cursor-pointer', state='visible')
        
            first_time = True           
            page_number = 1 
            
            while True:
                try:
                    print(f"scraping page {page_number}")
                    await page.wait_for_load_state('domcontentloaded')
                    await page.wait_for_selector('article.job-tile.cursor-pointer', state='visible')
                    job_selector = await page.query_selector_all('article.job-tile.cursor-pointer')
                    if not job_selector:
                        logging.info("No jobs found on the page.")
                        break
                    for tag in job_selector:
                        try:
                            date_posted_element = await tag.query_selector_all('span[data-v-6e74a038]')
                            job_title_el = await tag.query_selector('a.air3-link')                        
                            job_type_el = await tag.query_selector('li[data-test="job-type-label"]')
                            experiecnce_label_el = await tag.query_selector('li[data-test="experience-level"] strong')
                            duration_element = await tag.query_selector_all('li[data-test="duration-label"] strong')
                            price_element = await tag.query_selector_all('li[data-test="is-fixed-price"] strong')
                            url_el = await tag.query_selector('a.air3-link')
                            tags_el = await tag.query_selector_all('div.air3-token-wrap')

                            date_posted = [await date.inner_text() for date in date_posted_element or []][-1] if date_posted_element else None 
                            job_title = await job_title_el.inner_text() if job_title_el else None 
                            job_type = await job_type_el.inner_text() if job_type_el else None 
                            experience = await experiecnce_label_el.inner_text() if experiecnce_label_el else None 
                            duration = [await dur.inner_text() for dur in duration_element or []][-1] if duration_element else None 
                            price =  [await pr.inner_text() for pr in price_element or []][-1] if price_element else None 
                            link = await url_el.get_attribute('href') if url_el else None 
                            tags = ','.join([await tg.inner_text() for tg in tags_el or []]) if tags_el else None

                            base_url = 'https://www.upwork.com/'
                            upwork_jobs = [{
                                'Title': job_title,
                                'ExperienceLevel': experience,  
                                'DatePosted': date_posted, 
                                'JobType' : job_type,
                                'Duration' : duration,
                                'Price' : price,
                                'JobLink': urljoin(base_url, link),
                                'Tags': tags 
                            }]
                            
                            save_to_csv(upwork_jobs, first_time)
                            first_time = False
                        
                        except Exception as e:
                            logging.info(f"Error extracting product: {e} in {page_number}")
                            continue
                
                    next_page = page.locator('button[data-test="next-page"]')
                    if await next_page.count() == 0:
                        logging.info("No next button found. Possibly last page.")
                        break
                    
                    try:
                        await next_page.scroll_into_view_if_needed()
                        await next_page.click()
                        await page.wait_for_selector('article.job-tile.cursor-pointer', state='attached')
                        page_number += 1
                    except:
                        logging.info(f"Failed to click next page")
                        break
                
                except Exception as e:
                    print(f"Error on page {page_number}: {e}")
                    page_number += 1
                    continue

                await browser.close()
                await context.close()
                
    except Exception as e:
        logging.info(f"Error: {e}")
            
asyncio.run(scrape_upwork(cookies_path, max_retries=2)) 