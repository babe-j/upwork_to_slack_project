
import json
import nodriver as uc
import asyncio
# import pyautogui as pag
from functools import partial
import logging
import asyncio.base_subprocess
import os 

# Patch asyncio's BaseSubprocessTransport.close to avoid "Event loop is closed" errors
# when subprocesses are cleaned up after the event loop shuts down
asyncio.base_subprocess._old_close = asyncio.base_subprocess.BaseSubprocessTransport.close

cookies_path = os.path.join("Cookies", "cookies.json")

def silent_close(self):
    try:
        asyncio.base_subprocess._old_close(self)  # Call original close
    except RuntimeError as e:
        # Suppress only the specific 'Event loop is closed' error
        if 'Event loop is closed' not in str(e):
            raise e

asyncio.base_subprocess.BaseSubprocessTransport.close = silent_close

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# screenshot_path = r"C:\Users\user\scrapy_project2\jobs\Himalayas and Upwork\Screenshot.png"

def clean_same_site(same_site_raw):
    if not same_site_raw:
        return "Lax"
    s = str(same_site_raw).strip().lower()

    if "strict" in s:
        return "Strict"
    elif "lax" in s:
        return "Lax"
    elif "none" in s:
        return "None"
    else:
        return "Lax"

# async def wait_for_cloudflare(path:str):
#     loop = asyncio.get_event_loop()
#     logging.info("Waiting for CloudFlare image to be detected...")  

    # try:
        # Run PyAutoGUI locateOnScreen in executor to avoid blocking async loop
    #     location = await loop.run_in_executor(
    #         None,
    #         partial(pag.locateOnScreen, path, grayscale=True, confidence=0.8)
    #     )
    #     if location:
    #         # If image found, calculate its center and click it
    #         main_x, main_y = pag.center(location)
    #         await loop.run_in_executor(None, partial(pag.click, main_x, main_y))
    #         logging.info("Cloudflare image found and clicked.")
    #         return True
    # except pag.PyAutoGUIException:
    #     logging.info("Cloudflare image not found. Proceeding anyway.")
    #     return True       
    # except Exception as e:
    #     logging.info(f"Error: {e}")
    #     return False
        
    
async def cookies(path:str):
    browser=None
    try:
        browser = await uc.start(options=["--headless", "--disable-gpu"])   
        page = await browser.get(path)
        await asyncio.sleep(40)
        
        # output = await wait_for_cloudflare(screenshot_path)
        # if output is False:
        #     logging.error("Could not locate image, will try to get cookies regardless...")
        #     return
        # await asyncio.sleep(20)
        origin = await page.evaluate("window.location.origin")
        cookies_list = await browser.cookies.get_all()

        # Transform cookie objects into dictionaries with consistent fields
        cookies_result = [{
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "expires": cookie.expires,
            "httpOnly": cookie.http_only,
            "secure": cookie.secure,
            "sameSite": clean_same_site(cookie.same_site)
        } for cookie in cookies_list]

        # Retrieve and format local storage items from the page
        local_storage_items = await page.get_local_storage()
        local_storage = [
            {"name": key, "value": value} for key, value in local_storage_items.items()
        ]

        data = {
            "cookies": cookies_result,
            "origins": [
                {
                    "origin": origin,
                    "local_storage": local_storage
                }
            ]
        }

        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    except Exception as e:
        logging.error(f"A critical error occurred in the main process: {e}", exc_info=True)
        return
    finally:
        if browser:
            try:
                browser.stop()
                logging.info("Browser closed successfully.")
            except Exception as e:
                logging.warning(f"Error while closing browser: {e}", exc_info=True)
                return
    
