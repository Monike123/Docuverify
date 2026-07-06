import re

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def find_company_email(company_name: str) -> str | None:
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        try:
            query = f"{company_name} official contact email HR"
            driver.get(f"https://www.google.com/search?q={query.replace(' ', '+')}")
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True)
            emails = EMAIL_RE.findall(text)
            for email in emails:
                domain = email.split("@")[-1].lower()
                if domain not in {"google.com", "gmail.com", "youtube.com"}:
                    return email
        finally:
            driver.quit()
    except Exception:
        return None
    return None
