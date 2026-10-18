import asyncio
import re
from typing import Optional
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig


class JDScraper:
    """
    Asynchronously crawls dynamic job postings using Crawl4AI 
    and sanitizes HTML content with BeautifulSoup.
    """

    def __init__(self):
        # Headless browser configuration for modern ATS platforms
        self.browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )
        self.run_config = CrawlerRunConfig(
            word_count_threshold=10,
            delay_before_return_html=2.0,
            excluded_tags=["nav", "footer", "header", "script", "style", "aside", "form"]
        )

    async def _crawl(self, url: str) -> str:
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=url, config=self.run_config)
            if not result.success:
                raise RuntimeError(f"Failed to crawl URL: {url}. Error: {result.error_message}")
            return result.html

    def _extract_from_ld_json(self, soup: BeautifulSoup) -> Optional[str]:
        """Extracts structured JobPosting schema if available (standard for major ATS platforms)."""
        import json
        import html
        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string.strip())
                candidates = []
                if isinstance(data, list):
                    candidates.extend(data)
                elif isinstance(data, dict):
                    if "@graph" in data and isinstance(data["@graph"], list):
                        candidates.extend(data["@graph"])
                    else:
                        candidates.append(data)

                for item in candidates:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        desc = item.get("description", "")
                        if desc:
                            desc_soup = BeautifulSoup(html.unescape(desc), "html.parser")
                            text = desc_soup.get_text(separator="\n")
                            cleaned = "\n".join(l.strip() for l in text.splitlines() if l.strip())
                            if len(cleaned) >= 100:
                                title = item.get("title", "")
                                org = item.get("hiringOrganization", {}).get("name", "") if isinstance(item.get("hiringOrganization"), dict) else ""
                                header = f"{title} - {org}\n\n" if title else ""
                                return header + cleaned
            except Exception:
                continue
        return None

    def _clean_html(self, raw_html: str) -> str:
        """Strips leftover boilerplate, cookie notices, and layout artifacts."""
        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. First attempt to extract structured JobPosting JSON-LD before stripping tags
        ld_text = self._extract_from_ld_json(soup)
        if ld_text:
            return ld_text

        # 2. Strip non-content tags for DOM extraction fallback
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "button"]):
            element.decompose()

        # 3. Prioritize job content wrappers that actually contain substantial content
        content_selectors = [
            {"id": re.compile(r"(job-description|job-details|content|posting-description)", re.I)},
            {"class_": re.compile(r"(job-description|job-details|description|posting-content)", re.I)},
            {"role": "main"},
            "article",
            "main"
        ]

        target_container = None
        for selector in content_selectors:
            candidates = soup.find_all(**selector) if isinstance(selector, dict) else soup.find_all(selector)
            for cand in candidates:
                cand_text = cand.get_text(strip=True)
                if len(cand_text) >= 100:
                    target_container = cand
                    break
            if target_container:
                break

        body_soup = target_container if target_container else (soup.body or soup)
        
        # Extract text and normalize excess whitespace
        raw_text = body_soup.get_text(separator="\n")
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        return "\n".join(lines)

    async def scrape_async(self, url: str) -> str:
        """Asynchronously scrapes and sanitizes a job posting."""
        raw_html = await self._crawl(url)
        cleaned_text = self._clean_html(raw_html)
        if len(cleaned_text) < 100:
            raise ValueError("Scraped job description is too short or empty. The site might require authentication.")
        return cleaned_text

    def scrape(self, url: str) -> str:
        """Synchronous wrapper for CLI workflows."""
        return asyncio.run(self.scrape_async(url))