
import concurrent.futures
import requests
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tqdm import tqdm
import logging
import random
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
   level=logging.INFO,
   format='%(asctime)s - %(levelname)s - %(message)s',
   handlers=[
       logging.FileHandler('ntpc_laws_crawler.log'),
       logging.StreamHandler()
   ]
)

def get_session():
   session = requests.Session()
   retry = Retry(total=3, backoff_factor=0.5)
   adapter = HTTPAdapter(max_retries=retry)
   session.mount('http://', adapter)
   session.mount('https://', adapter)
   session.headers.update({
       'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
   })
   return session

def get_law_links_from_category(session, category_url, base_url="https://web.law.ntpc.gov.tw/"):
   laws = []
   try:
       response = session.get(category_url)
       soup = BeautifulSoup(response.text, 'html.parser')
       
       # 從表格中找到所有法規連結
       for link in soup.select("table.tab-list a[href*='FLAWDAT01.aspx']"):
           if not link.find_previous("img", src="/images/fei.gif"):
               href = link.get('href', '')
               lncode = href.split('lncode=')[1]  # 直接從href取得lncode
               fcode = lncode.replace('1C', 'C')  # 轉換成fcode格式
               title = link.text.strip()
               
               laws.append({
                   'title': title,
                   'fcode': fcode
               })
               
       time.sleep(0.5)
       return laws
   except Exception as e:
       logging.error(f"抓取類別頁面 {category_url} 時發生錯誤: {e}")
       return []

def try_get_content(url, law_info, session):
   try:
       response = session.get(url)
       soup = BeautifulSoup(response.text, 'html.parser')
       
       # 檢查是否包含法規內容
       if not soup.select("table.tab-law01 tr") and not soup.select("table.tab-law tr"):
           return None
           
       law_data = {
           "LawName": law_info['title'],
           "LastModified": "",
           "Articles": []
       }

       header = soup.select_one("#cph_content_lawheader_law")
       if header:
           date_text = header.text.split('(')[1].split(')')[0].strip()
           law_data["LastModified"] = date_text

       # 嘗試兩種可能的table class
       articles = soup.select("table.tab-law01 tr") or soup.select("table.tab-law tr")
       for row in articles:
           num = row.select_one(".col-th")
           content = row.select_one(".col-td pre")
           if num and content:
               law_data["Articles"].append({
                   "Number": num.text.strip(),
                   "Content": content.text.strip()
               })

       return law_data if law_data["Articles"] else None
       
   except Exception as e:
       logging.error(f"處理法規 {law_info['title']} 內容時發生錯誤: {e}")
       return None

def get_law_content(law_info, session):
   # 先嘗試0202
   url = f"https://web.law.ntpc.gov.tw/Scripts/FLAWDAT0202.aspx?fcode={law_info['fcode']}"
   content = try_get_content(url, law_info, session)
   
   # 若0202失敗則嘗試0201
   if not content:
       url = f"https://web.law.ntpc.gov.tw/Scripts/FLAWDAT0201.aspx?fcode={law_info['fcode']}"
       content = try_get_content(url, law_info, session)
       
   return content
   
def main():
   session = get_session()
   base_url = "https://web.law.ntpc.gov.tw/Level.aspx"

   # 獲取類別列表
   response = session.get(base_url)
   soup = BeautifulSoup(response.text, 'html.parser')
   categories = []
   for link in soup.select("ul.level a[href*='Query2.aspx?no=C']"):
       href = link.get('href', '')
       full_url = urljoin(base_url, href)
       categories.append(full_url)

   # 獲取所有法規連結
   all_laws = []
   for cat_url in tqdm(categories, desc="正在抓取類別"):
       laws = get_law_links_from_category(session, cat_url)
       all_laws.extend(laws)
       
   logging.info(f"成功取得 {len(all_laws)} 個法規代碼")
   
   # 處理法規內容
   os.makedirs('ntpc_law_jsons', exist_ok=True)
   with tqdm(total=len(all_laws), desc="正在處理法規內容") as pbar:
       with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
           for i in range(0, len(all_laws), 10):
               batch = all_laws[i:i+10]
               futures = [executor.submit(get_law_content, law, session) for law in batch]
               
               for future in concurrent.futures.as_completed(futures):
                   if law_data := future.result():
                       filename = f"{law_data['LawName']}.json"
                       filepath = os.path.join('ntpc_law_jsons', filename)
                       with open(filepath, 'w', encoding='utf-8') as f:
                           json.dump(law_data, f, ensure_ascii=False, indent=2)
                   pbar.update(1)

if __name__ == "__main__":
   main()