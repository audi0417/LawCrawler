from bs4.element import Tag
from bs4 import BeautifulSoup
import concurrent.futures
import requests
import json
import os
from urllib.parse import urljoin
from tqdm import tqdm
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import logging
import random

logging.basicConfig(
   level=logging.INFO,
   format='%(asctime)s - %(levelname)s - %(message)s',
   handlers=[
       logging.FileHandler('crawler.log'),
       logging.StreamHandler()
   ]
)

HEADERS = {
   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
   'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
   'Connection': 'keep-alive'
}

def get_session():
   session = requests.Session()
   retry = Retry(
       total=3,
       backoff_factor=0.5,
       status_forcelist=[500, 502, 503, 504]
   )
   adapter = HTTPAdapter(max_retries=retry)
   session.mount('http://', adapter)
   session.mount('https://', adapter)
   session.headers.update(HEADERS)
   return session

def get_category_links(session):
   base_url = "https://law.moj.gov.tw/Law/"
   try:
       response = session.get(base_url + "LawSearchLaw.aspx")
       soup = BeautifulSoup(response.text, 'html.parser')
       
       links = []
       def parse_tree(element):
           if element.name == 'a':
               if 'LawSearchLaw.aspx?TY=' in element.get('href', ''): 
                   href = urljoin(base_url, element['href'])
                   if 'fei=1' not in href:
                       links.append(href)
               elif 'javascript:void(0)' in element.get('href', ''):
                   next_ul = element.find_next('ul')
                   if next_ul:
                       parse_tree(next_ul)
                       
           for child in element.children:
               if isinstance(child, Tag):
                   parse_tree(child)
       
       tree = soup.find('ul', id='tree')
       parse_tree(tree)
       
       total_laws = sum(int(span.text) for span in soup.select('span.badge') if span.text.isdigit())
       logging.info(f"Found {len(links)} category links, estimated {total_laws} laws")
       
       return links, total_laws
   except Exception as e:
       logging.error(f"Error getting category links: {e}")
       return [], 0

def get_law_links(category_url, session):
   try:
       time.sleep(random.uniform(1, 2))
       response = session.get(category_url)
       soup = BeautifulSoup(response.text, 'html.parser')
       
       links = []
       table = soup.find('table', {'class': 'table table-hover tab-list tab-central'})
       if table:
           for a in table.find_all('a', href=re.compile(r'LawAll\.aspx\?PCODE=')):
               href = urljoin("https://law.moj.gov.tw", a['href'])
               links.append(href)
       return links
   except Exception as e:
       logging.error(f"Error getting law links from {category_url}: {e}")
       return []

def get_law_json(url, session):
   try:
       time.sleep(random.uniform(1, 2))
       response = session.get(url, timeout=10)
       soup = BeautifulSoup(response.text, 'html.parser')
       
       modified_date_elem = (
           soup.select_one("#trLNNDate td") or 
           soup.select_one("#trLNODate td") or
           soup.select_one(".table-title tr:contains('修正日期') td")
       )
       
       law_data = {
           "LawName": soup.select_one("#hlLawName").text.strip(),
           "LawCategory": soup.select_one(".table tr:nth-child(3) td").text.strip(), 
           "LawModifiedDate": ''.join(filter(str.isdigit, modified_date_elem.text)) if modified_date_elem else "",
           "LawHistories": "",
           "LawArticles": [],
           "LawURL": url
       }
       
       rows = soup.select('.row')
       for row in rows:
           article_no = row.select_one('.col-no a')
           article = row.select_one('.law-article')
           if article_no and article:
               law_data["LawArticles"].append({
                   "ArticleNo": f"{law_data['LawName']}, {article_no.text.strip()}",
                   "ArticleContent": article.text.strip()
               })
       return law_data
       
   except Exception as e:
       logging.error(f"Failed URL: {url}")
       return None

def save_json(data, filename):
   os.makedirs('law_jsons', exist_ok=True)
   filepath = os.path.join('law_jsons', filename)
   with open(filepath, 'w', encoding='utf-8') as f:
       json.dump(data, f, ensure_ascii=False, indent=2)

def main():
   session = get_session()
   category_links, total_laws = get_category_links(session)
   
   if not category_links:
       logging.error("No category links found")
       return
       
   all_law_urls = []
   with tqdm(total=len(category_links), desc="Collecting law URLs") as pbar:
       for category_url in category_links:
           urls = get_law_links(category_url, session)
           all_law_urls.extend(urls)
           pbar.update(1)
   
   logging.info(f"Found {len(all_law_urls)} total law URLs")
   
   with tqdm(total=len(all_law_urls), desc="Processing Laws") as pbar:
       for i in range(0, len(all_law_urls), 20):
           batch = all_law_urls[i:i+20]
           with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
               futures = [executor.submit(get_law_json, url, session) for url in batch]
               
               for future in concurrent.futures.as_completed(futures):
                   law_data = future.result()
                   if law_data:
                       filename = f"{law_data['LawName']}.json"
                       save_json(law_data, filename)
                   pbar.update(1)
                   
   logging.info(f"Completed! Processed {len(all_law_urls)} laws")
