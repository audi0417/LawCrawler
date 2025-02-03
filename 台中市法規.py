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

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('taichung_laws_crawler.log'),
        logging.StreamHandler()
    ]
)

def get_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    })
    return session

def get_categories(session, base_url="https://law.taichung.gov.tw/LawCategoryMain.aspx"):
    """獲取所有法規類別連結"""
    try:
        response = session.get(base_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        category_links = []
        
        # 找出所有類別連結
        for link in soup.select("a[href*='LawCategoryMain.aspx?CategoryID=']"):
            href = link.get('href', '')
            if href and 'CategoryID=' in href:
                full_url = urljoin(base_url, href)
                category_links.append(full_url)
        
        logging.info(f"Found {len(category_links)} categories")
        return category_links
        
    except Exception as e:
        logging.error(f"Error getting categories: {e}")
        return []

def get_law_links_from_page(session, base_url, category_url):
    """從單一類別頁面獲取所有法規連結"""
    all_links = []
    page = 1
    
    while True:
        url = f"{category_url}&page={page}" if '?' in category_url else f"{category_url}?page={page}"
        
        try:
            response = session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            rows = soup.select("table.table-hover tr")
            if not rows:
                break
                
            for row in rows:
                # 跳過已廢除的法規
                if row.select_one("span.label-fei"):
                    continue
                    
                link = row.select_one("a[href*='LawContent.aspx']")
                if link and link.get('href'):
                    full_url = urljoin(base_url, link['href'])
                    all_links.append(full_url)
            
            # 檢查是否有下一頁
            next_page = soup.select_one("a[href*='page={}']".format(page + 1))
            if not next_page:
                break
                
            page += 1
            time.sleep(random.uniform(1, 2))
            
        except Exception as e:
            logging.error(f"Error getting laws from page {page}: {e}")
            break
            
    return all_links

def get_law_content(url, session):
    """解析單一法規內容"""
    try:
        time.sleep(random.uniform(0.5, 1))
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 基本資料表格
        info_table = soup.select_one("table.table-bordered")
        
        law_data = {
            "LawName": "",
            "LawCategory": "",
            "LawModifiedDate": "",
            "LawArticles": [],
            "LawURL": url
        }
        
        if info_table:
            # 取得基本資料
            rows = info_table.select("tr")
            for row in rows:
                th = row.select_one("th")
                td = row.select_one("td")
                if not th or not td:
                    continue
                    
                th_text = th.text.strip()
                td_text = td.text.strip()
                
                if "法規名稱" in th_text:
                    law_data["LawName"] = td_text
                elif "法規體系" in th_text:
                    law_data["LawCategory"] = td_text
                elif "公發布日" in th_text:
                    law_data["LawModifiedDate"] = td_text
        
        # 取得法規內容
        content_table = soup.select_one("table.tab-law")
        if content_table:
            for row in content_table.select("tr"):
                td = row.select_one("td:nth-of-type(2)")
                if td:
                    content = td.text.strip()
                    if content:
                        law_data["LawArticles"].append({
                            "ArticleContent": content
                        })
        
        return law_data
    except Exception as e:
        logging.error(f"Error processing URL {url}: {e}")
        return None

def save_json(data, filename):
    """儲存法規資料為JSON檔案"""
    os.makedirs('taichung_law_jsons', exist_ok=True)
    filepath = os.path.join('taichung_law_jsons', filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    base_url = "https://law.taichung.gov.tw/LawCategoryMain.aspx"
    session = get_session()
    
    # 獲取所有類別連結
    category_links = get_categories(session)
    if not category_links:
        logging.error("No category links found")
        return
        
    # 獲取所有法規連結
    all_law_links = []
    for category_url in tqdm(category_links, desc="Getting category laws"):
        links = get_law_links_from_page(session, base_url, category_url)
        all_law_links.extend(links)
    
    logging.info(f"Found {len(all_law_links)} total law URLs")
    
    # 處理所有法規內容
    with tqdm(total=len(all_law_links), desc="Processing Laws") as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for i in range(0, len(all_law_links), 20):
                batch = all_law_links[i:i+20]
                futures = [executor.submit(get_law_content, url, session) for url in batch]
                
                for future in concurrent.futures.as_completed(futures):
                    if law_data := future.result():
                        filename = f"{law_data['LawName']}.json"
                        save_json(law_data, filename)
                    pbar.update(1)

if __name__ == "__main__":
    main()