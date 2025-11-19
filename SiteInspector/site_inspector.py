import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from spellchecker import SpellChecker
import concurrent.futures
import urllib.robotparser
import re
import json
import threading
import time

# ----------------------------
# Initialization
# ----------------------------
visited = set()
visited_lock = threading.Lock()
spell = SpellChecker()
crawl_count = 0
crawl_count_lock = threading.Lock()

# ----------------------------
# Helper functions
# ----------------------------
def is_internal_link(base_url, link):
    parsed_base = urlparse(base_url).netloc
    parsed_link = urlparse(link).netloc
    return parsed_link == "" or parsed_link == parsed_base

def get_visible_text(soup):
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    text = soup.get_text(separator=" ")
    return " ".join(text.split())

def check_spelling(text):
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    misspelled = spell.unknown(words)
    corrections = {word: spell.correction(word) for word in misspelled}
    return corrections

def check_broken_links(soup, base_url):
    broken = []
    for tag in soup.find_all(["a", "img"]):
        attr = "href" if tag.name == "a" else "src"
        url = tag.get(attr)
        if not url:
            continue
        full_url = urljoin(base_url, url)
        if full_url.startswith("javascript:"):  # skip JS links
            continue
        try:
            r = requests.head(full_url, timeout=5, allow_redirects=True)
            if r.status_code >= 400:
                broken.append(full_url)
        except:
            broken.append(full_url)
    return broken

def can_fetch_url(url, rp):
    try:
        return rp.can_fetch("*", url)
    except:
        return True

# ----------------------------
# Process a single page
# ----------------------------
def process_page(url, base_url, rp, max_pages):
    global crawl_count
    result = {"spelling_issues": {}, "broken_links": []}
    new_links = []

    with crawl_count_lock:
        if crawl_count >= max_pages:
            return None, []  # stop processing further

    try:
        if not can_fetch_url(url, rp):
            return result, []

        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # Spell checking
        text = get_visible_text(soup)
        result["spelling_issues"] = check_spelling(text)

        # Broken links/images
        result["broken_links"] = check_broken_links(soup, url)

        # Internal links to crawl
        for link_tag in soup.find_all("a", href=True):
            full_url = urljoin(url, link_tag["href"])
            if is_internal_link(base_url, full_url):
                with visited_lock:
                    if full_url not in visited:
                        new_links.append(full_url)

        # ----------------------------
        # Thread-safe dynamic progress
        # ----------------------------
        with crawl_count_lock:
            crawl_count += 1
            current_count = crawl_count

        print(f"Crawled ({current_count}/{max_pages}): {url}")

    except Exception as e:
        print(f"Error crawling {url}: {e}")

    return result, new_links

# ----------------------------
# Crawl website
# ----------------------------
def crawl(base_url, max_pages=50, max_workers=5):
    report = {}
    to_visit = [base_url]

    # Robots.txt
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(urljoin(base_url, "/robots.txt"))
    try:
        rp.read()
    except:
        pass

    while to_visit and crawl_count < max_pages:
        futures = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            while to_visit and len(futures) < max_workers and crawl_count < max_pages:
                url = to_visit.pop(0)
                with visited_lock:
                    if url in visited:
                        continue
                    visited.add(url)
                future = executor.submit(process_page, url, base_url, rp, max_pages)
                futures[future] = url

            for future in concurrent.futures.as_completed(futures):
                page_result, new_links = future.result()
                future_url = futures[future]
                if page_result is not None:
                    report[future_url] = page_result

                    # Add new links safely
                    with visited_lock:
                        for link in new_links:
                            if link not in visited and len(visited) + len(to_visit) < max_pages:
                                to_visit.append(link)

        time.sleep(0.2)  # polite crawling

    return report

# ----------------------------
# Export reports
# ----------------------------
def export_report(summary, txt_file="crawl_summary.txt", json_file="crawl_report.json"):
    # JSON report
    with open(json_file, "w", encoding="utf-8") as f_json:
        json.dump(summary, f_json, indent=4)

    # Text report
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("=== Summary Report ===\n\n")

        # Spelling issues
        f.write("Page URLs with spelling issues:\n")
        found = False
        for page, issues in summary.items():
            if issues["spelling_issues"]:
                f.write(f" - {page}\n")
                found = True
        if not found:
            f.write(" None\n")

        # Misspelled words with suggestions
        f.write("\nMisspelled words (with suggestions):\n")
        found = False
        for page, issues in summary.items():
            if issues["spelling_issues"]:
                for word, correction in issues["spelling_issues"].items():
                    f.write(f" - {word} (suggestion: {correction})\n")
                found = True
        if not found:
            f.write(" None\n")

        # Broken links/images
        f.write("\nPage URLs with broken links/images:\n")
        found = False
        for page, issues in summary.items():
            if issues["broken_links"]:
                f.write(f" - {page}\n")
                for link in issues["broken_links"]:
                    f.write(f"    * {link}\n")
                found = True
        if not found:
            f.write(" None\n")

        # Crawl summary
        total_pages = len(summary)
        total_spelling = sum(len(issues["spelling_issues"]) for issues in summary.values())
        total_broken = sum(len(issues["broken_links"]) for issues in summary.values())
        f.write("\n=== Crawl Summary ===\n")
        f.write(f"Total Pages Crawled: {total_pages}\n")
        f.write(f"Total Spelling Mistakes: {total_spelling}\n")
        f.write(f"Total Broken Links/Images: {total_broken}\n")

# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    website = "https://books.toscrape.com/"  # Replace with your target site
    print(f"Starting crawl on {website}...\n")
    summary = crawl(website, max_pages=5, max_workers=5)
    export_report(summary)
    print("\nCrawl completed.")
    print("Reports generated: 'crawl_summary.txt' and 'crawl_report.json'")