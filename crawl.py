import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerMonitor, CrawlerRunConfig, DefaultMarkdownGenerator, DisplayMode, PruningContentFilter, RateLimiter, SemaphoreDispatcher
from crawl4ai.utils import requests
from xml.etree import ElementTree

async def crawl(urls):
    config = BrowserConfig(headless=False)
    prune_filter = PruningContentFilter(threshold_type="dynamic")
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, 
        markdown_generator=md_generator
    )
    
    dispatcher = SemaphoreDispatcher(
        semaphore_count=5,
        rate_limiter=RateLimiter(
            base_delay=(0.5, 1.0),
            max_delay=10.0
        ),
        monitor=CrawlerMonitor(
            max_visible_rows=10,
            display_mode=DisplayMode.DETAILED
        )
    )

    async with AsyncWebCrawler(config=config) as crawler:
        result = await crawler.arun_many(
            urls,
            config=run_config,
            dispatcher=dispatcher
        )
        return result


def get_urls():
    root_url = "https://ai.pydantic.dev/"
    response = requests.get(root_url)
    response.raise_for_status()
    
    root = ElementTree.fromstring(response.content)
    
    urls = [link.get("href") for link in root.findall(".//div[@class='markdown-body']//a")]
    return urls


async def main():
    #urls = get_urls()
    urls = ["https://ai.pydantic.dev/"]
    if not urls:
        print("Failed to fetch URLs")
        return
    result = await crawl(urls)
    for result in result:
        if result.success:
            if result.markdown_v2.fit_markdown:
                print(result.markdown_v2.fit_markdown)
        else:
            print("Error:", result.error_message)

if __name__ == "__main__":
    asyncio.run(main())