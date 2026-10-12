# scrapers/jd_scraper.py
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
            excluded_tags=["nav", "footer", "header", "script", "style", "aside", "form"]
        )

    async def _crawl(self, url: str) -> str:
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=url, config=self.run_config)
            if not result.success:
                raise RuntimeError(f"Failed to crawl URL: {url}. Error: {result.error_message}")
            return result.html

    def _clean_html(self, raw_html: str) -> str:
        """Strips leftover boilerplate, cookie notices, and layout artifacts."""
        soup = BeautifulSoup(raw_html, "html.parser")

        # Strip remaining non-content tags
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "button"]):
            element.decompose()

        # Prioritize job content wrappers if identifiable
        content_selectors = [
            {"id": re.compile(r"(job-description|job-details|content|posting-description)", re.I)},
            {"class_": re.compile(r"(job-description|job-details|description|posting-content)", re.I)},
            {"role": "main"},
            "article",
            "main"
        ]

        target_container = None
        for selector in content_selectors:
            if isinstance(selector, dict):
                target_container = soup.find(**selector)
            else:
                target_container = soup.find(selector)
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