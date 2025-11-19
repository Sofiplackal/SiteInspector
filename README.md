# SiteInspector

**SiteInspector** is a Python-based web crawler that inspects websites for spelling mistakes and broken links/images. It generates comprehensive reports in both JSON and text formats, making it easy to analyze the health of a website.

---

## Features

- Crawls internal pages of a website up to a configurable limit.
- Checks for spelling mistakes in visible text.
- Detects broken links and images.
- Respects `robots.txt` rules.
- Supports multithreading for faster crawling.
- Generates:
  - `crawl_report.json` – structured JSON report.
  - `crawl_summary.txt` – human-readable summary report.

---

## Requirements

- Python 3.8 or higher
- Libraries:
  - `requests`
  - `beautifulsoup4`
  - `pyspellchecker`
