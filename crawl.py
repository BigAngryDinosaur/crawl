import asyncio
from typing import List
from xml.etree import ElementTree

from crawl4ai import (AsyncWebCrawler, BrowserConfig, CacheMode,
                      CrawlerMonitor, CrawlerRunConfig,
                      DefaultMarkdownGenerator, DisplayMode,
                      PruningContentFilter, RateLimiter)
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher
from crawl4ai.models import CrawlResult
from crawl4ai.utils import requests


async def crawl(urls: List[str]):
    config = BrowserConfig(headless=False)
    prune_filter = PruningContentFilter(threshold_type="dynamic")
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, markdown_generator=md_generator
    )

    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=50.0,
        rate_limiter=RateLimiter(base_delay=(1.0, 2.0), max_delay=10.0, max_retries=2),
        monitor=CrawlerMonitor(max_visible_rows=50, display_mode=DisplayMode.DETAILED),
    )

    async with AsyncWebCrawler(config=config) as crawler:
        result = await crawler.arun_many(urls, config=run_config, dispatcher=dispatcher)
        return result


def get_sitemap_urls() -> List[str]:
    sitemap_url = ""

    try:
        response = requests.get(sitemap_url)
        response.raise_for_status()

        root = ElementTree.fromstring(response.content)

        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text for loc in root.findall(".//ns:loc", namespace) if loc.text]
        return urls

    except Exception as e:
        print(f"Error fetching urls: {e}")
        return []


async def process_result(url: str, text: str):
    pass


async def main():
    urls = []
    if not urls:
        print("Failed to fetch URLs")
        return
    results = await crawl(urls)
    for result in results:
        if result.success:
            await process_result(result.url, result.markdown_v2.raw_markdown)
        else:
            print(f"Failed to Crawl: {result.url}")


if __name__ == "__main__":
    asyncio.run(main())
