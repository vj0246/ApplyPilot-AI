"""
job_service.py
---------------
Scrapes job description text out of a URL. Worth knowing up front: this is
best-effort. Every job board renders differently and some actively don't
want to be scraped. If a URL fails, pasting the JD text directly always
works — that's the real fallback, not more scraping cleverness.
"""
import re
import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# pretending to be a normal Chrome browser — without this a bunch of
# sites (greenhouse especially) just return a near-empty page or a 403
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# found by opening a few real postings per platform and checking devtools —
# will break whenever these companies redesign, that's just how scraping is
SELECTORS = {
    "greenhouse.io":    ["div#content", "div.job__description"],
    "lever.co":         ["div.content", "div[data-qa='job-description']"],
    "ashbyhq.com":      ["div.ashby-job-posting-brief-description"],
    "linkedin.com":     ["div.description__text", "div.show-more-less-html"],
    "indeed.com":       ["div#jobDescriptionText"],
    "workday.com":      ["div[data-automation-id='job-description']"],
    "smartrecruiters":  ["div.job-description"],
}

GENERIC = [
    "div.job-description", "div#job-description",
    "div[class*='jobDescription']", "div[class*='job-desc']",
    "article.job", "section.description", "main", "article",
]


async def fetch_from_url(url: str) -> Optional[str]:
    """
    Known troublemakers: LinkedIn often shows a login wall instead of the
    posting. Workday renders the description client-side via JS, which
    httpx can't execute, so those basically never work without something
    like Playwright. Indeed rate-limits hard, especially from cloud IPs.
    """
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning(f"Job URL returned HTTP {resp.status_code}: {url}")
                return None
            return _extract(resp.text, url)
    except httpx.TimeoutException:
        log.warning(f"Timeout fetching: {url}")
        return None
    except Exception as e:
        log.warning(f"Error fetching {url}: {e}")
        return None


def _extract(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
        tag.decompose()

    for domain, sels in SELECTORS.items():
        if domain in url:
            for sel in sels:
                el = soup.select_one(sel)
                if el:
                    t = el.get_text("\n", strip=True)
                    if len(t) > 200:
                        return _clean(t[:8000])

    for sel in GENERIC:
        el = soup.select_one(sel)
        if el:
            t = el.get_text("\n", strip=True)
            if len(t) > 200:
                return _clean(t[:8000])

    body = soup.find("body")
    if body:
        return _clean(body.get_text("\n", strip=True)[:8000])
    return ""


def _clean(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_platform(url: str) -> str:
    url = url.lower()
    mapping = {
        "greenhouse.io": "greenhouse", "lever.co": "lever", "ashbyhq.com": "ashby",
        "linkedin.com": "linkedin", "indeed.com": "indeed", "workday.com": "workday",
        "smartrecruiters.com": "smartrecruiters", "jobvite.com": "jobvite",
        "taleo.net": "taleo", "icims.com": "icims",
    }
    for domain, name in mapping.items():
        if domain in url:
            return name
    return "other"
