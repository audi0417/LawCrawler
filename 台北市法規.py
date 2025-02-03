from bs4 import BeautifulSoup
import concurrent.futures
import requests
import json
import os
from urllib.parse import urljoin
from tqdm import tqdm
import logging
import random
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re 

logging.basicConfig(
   level=logging.INFO,
   format='%(asctime)s - %(levelname)s - %(message)s',
   handlers=[
       logging.FileHandler('taipei_laws_crawler.log'),
       logging.StreamHandler()
   ]
)

HEADERS = {
   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
   'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
}

def get_session():
   session = requests.Session()
   retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
   adapter = HTTPAdapter(max_retries=retry)
   session.mount('http://', adapter)
   session.mount('https://', adapter)
   session.headers.update(HEADERS)
   return session

def get_total_pages(session):
   try:
       response = session.get("https://www.laws.taipei.gov.tw/Law/LawCategory/LawCategoryResult?categoryid=001&page=1")
       soup = BeautifulSoup(response.text, 'html.parser')
       total_pages = int(soup.select_one("div.paging-counts em:nth-of-type(2)").text)
       logging.info(f"Total pages: {total_pages}")
       return total_pages
   except Exception as e:
       logging.error(f"Error getting total pages: {e}")
       return 0

def get_law_urls(session):
   urls = []
   total_pages = get_total_pages(session)
   
   with tqdm(total=total_pages, desc="Collecting URLs") as pbar:
       for page in range(1, total_pages + 1):
           try:
               time.sleep(random.uniform(1, 2))
               response = session.get(f"https://www.laws.taipei.gov.tw/Law/LawCategory/LawCategoryResult?categoryid=001&page={page}")
               soup = BeautifulSoup(response.text, 'html.parser')
               
               for link in soup.select("table.table-tab td a"):
                   if 'href' in link.attrs:
                       law_url = urljoin("https://www.laws.taipei.gov.tw", link['href'])
                       urls.append(law_url)
               pbar.update(1)
           except Exception as e:
               logging.error(f"Error on page {page}: {e}")
   
   logging.info(f"Found {len(urls)} law URLs")
   return urls

def get_law_json(url, session):
   try:
       fl_code = url.split('/FL')[1].split('?')[0]
       info_url = f"https://www.laws.taipei.gov.tw/Law/LawSearch/LawInformation/FL{fl_code}"
       content_url = f"https://www.laws.taipei.gov.tw/Law/LawSearch/LawArticleContent/FL{fl_code}"
       
       response = session.get(info_url)
       soup = BeautifulSoup(response.text, 'html.parser')
       
       law_data = {
           "LawName": soup.select_one("div.col-input a.law-link").text.strip() if soup.select_one("div.col-input a.law-link") else "",
           "LawModifiedDate": soup.select_one("div.col-label:contains('修正日期') + div.col-input dfn").text.strip() if soup.select_one("div.col-label:contains('修正日期') + div.col-input dfn") else "",
           "LawArticles": [],
           "LawURL": content_url
       }
       
       time.sleep(random.uniform(1, 2))
       response = session.get(content_url)
       soup = BeautifulSoup(response.text, 'html.parser')
       
       articles = soup.select("ul.law.law-content li")
       chapter = ""
       
       for article in articles:
           # 處理章節標題
           if article.select_one("div.law-articlepre") is None and article.text.strip():
               chapter = article.text.strip()
               continue
               
           content_div = article.select_one("div.law-articlepre")
           if content_div:
               content = content_div.text.strip()
               
               # 檢查是否為點號形式(如 "一、") 或條號形式(如 "第1條")
               if re.match(r'^[一二三四五六七八九十]+、', content):
                   number = content.split('、')[0] + '、'
                   content = content[len(number):].strip()
               else:
                   number_div = article.select_one("div.col-no")
                   number = number_div.text.strip() if number_div else ""
               
               if content:
                   law_data["LawArticles"].append({
                       "Chapter": chapter,
                       "ArticleNo": number,
                       "ArticleContent": content
                   })
       
       if not law_data["LawName"]:
           logging.error(f"No law name found for URL: {content_url}")
           return None
           
       return law_data
   except Exception as e:
       logging.error(f"Failed URL: {url}")
       logging.error(f"Error: {str(e)}")
       return None

def save_json(data, filename):
   os.makedirs('taipei_law_jsons', exist_ok=True)
   filepath = os.path.join('taipei_law_jsons', filename)
   with open(filepath, 'w', encoding='utf-8') as f:
       json.dump(data, f, ensure_ascii=False, indent=2)

def main():
   session = get_session()
   law_urls = get_law_urls(session)
   
   if not law_urls:
       logging.error("No law URLs found")
       return
       
   processed_count = 0
   with tqdm(total=len(law_urls), desc="Processing Laws") as pbar:
       for i in range(0, len(law_urls), 20):
           batch = law_urls[i:i+20]
           with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
               futures = [executor.submit(get_law_json, url, session) for url in batch]
               
               for future in concurrent.futures.as_completed(futures):
                   try:
                       law_data = future.result()
                       if law_data and law_data["LawName"]:
                           filename = f"{law_data['LawName']}.json"
                           save_json(law_data, filename)
                           processed_count += 1
                   except Exception as e:
                       logging.error(f"Error processing law: {e}")
                   pbar.update(1)
   
   logging.info(f"Completed! Successfully processed {processed_count} out of {len(law_urls)} laws")

if __name__ == "__main__":
   main()