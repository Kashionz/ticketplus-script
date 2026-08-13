"""Attach to an existing Chrome at 127.0.0.1:9222 and print page state."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

TEST_URL = "https://ticketplus.com.tw/activity/4b47b5360d42451f65704664c40b1c72"


def main() -> None:
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=options)
    print("ATTACHED")
    print("title:", driver.title)
    print("url:", driver.current_url)
    if "ticketplus.com.tw" not in (driver.current_url or ""):
        driver.get(TEST_URL)
        print("navigated:", driver.current_url)
        print("title:", driver.title)
    cookies = driver.get_cookies()
    logged_in = any(
        c.get("name") == "user" and "account" in (c.get("value") or "") for c in cookies
    )
    print("logged_in:", logged_in)
    print("tabs:", len(driver.window_handles))


if __name__ == "__main__":
    main()
