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
        logging.FileHandler('kaohsiung_laws_crawler.log'),
        logging.StreamHandler()
    ]
)

def get_session():
    """建立一個具有重試機制的請求會話"""
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

def get_all_laws_url(session, base_url="https://outlaw.kcg.gov.tw"):
    """獲取所有法規的URL"""
    try:
        # 直接使用"全部"法規的URL
        all_laws_url = urljoin(base_url, "LawResultList.aspx?NLawTypeID=all&GroupID=&CategoryID=1%2c01%2c02%2c03%2c04%2c05%2c06%2c07%2c08%2c09%2c10%2c11%2c12%2c13%2c14%2c15%2c16%2c17%2c18%2c19%2c20%2c21%2c22%2c23%2c24%2c25%2c26%2c27%2c28%2c29%2c30%2c31%2c33%2c34%2c35%2c36%2c32%2cb01%2cb02%2cb03%2cb04%2cb05%2cb06%2cb07%2cb08%2cb09%2cb10%2cb11%2cb12%2c&KW=&name=1&content=1&StartDate=&EndDate=&LNumber=&now=1&fei=1")
        
        response = session.get(all_laws_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 從頁面獲取總法規數
        page_info = soup.select_one(".pageinfo")
        total_laws = 0
        if page_info:
            info_text = page_info.text
            if "共" in info_text and "筆" in info_text:
                try:
                    total_laws = int(info_text.split("共")[1].split("筆")[0].strip())
                    logging.info(f"Total laws: {total_laws}")
                except:
                    logging.warning("Could not parse total law count")
        
        return all_laws_url, total_laws
    except Exception as e:
        logging.error(f"Error getting all laws URL: {e}")
        return None, 0

def get_law_links_from_page(session, url, base_url="https://outlaw.kcg.gov.tw"):
    """從單一頁面獲取所有法規連結"""
    try:
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        law_links = []
        
        # 獲取當前頁面的所有法規連結
        rows = soup.select("table.table-hover tr")
        for row in rows:
            # 跳過已廢止的法規
            if row.select_one(".label-fei"):
                continue
            
            link = row.select_one("a[href*='LawContent.aspx']")
            if link and link.get('href'):
                full_url = urljoin(base_url, link['href'])
                date_td = row.select_one("td:nth-of-type(2)")
                date = date_td.text.strip() if date_td else ""
                
                law_links.append({
                    'url': full_url,
                    'name': link.text.strip(),
                    'date': date
                })
        
        # 查找下一頁連結
        next_page = soup.select_one("a#ctl00_cp_content_rptList_ctl11_PagerButtom_hlNext")
        next_page_url = None
        if next_page and 'disabled' not in next_page.get('class', []) and next_page.get('href'):
            next_page_url = urljoin(base_url, next_page['href'])
        
        return law_links, next_page_url
    except Exception as e:
        logging.error(f"Error getting laws from page {url}: {e}")
        return [], None

def get_all_law_links(session, start_url, base_url="https://law.tycg.gov.tw/", total_laws=0):
    """抓取所有頁面的法規連結"""
    all_links = []
    current_url = start_url
    page = 1
    
    with tqdm(total=total_laws, desc="Finding laws") as pbar:
        while current_url:
            links, next_url = get_law_links_from_page(session, current_url, base_url)
            all_links.extend(links)
            
            # 更新進度條
            pbar.update(len(links))
            pbar.set_description(f"Finding laws (Page {page})")
            
            if not next_url:
                break
                
            current_url = next_url
            page += 1
            time.sleep(random.uniform(0.5, 1.5))  # 避免請求過快
    
    logging.info(f"Found total {len(all_links)} laws from {page} pages")
    return all_links

def get_law_content(law_info, session):
    """解析單一法規內容頁面"""
    try:
        time.sleep(random.uniform(0.5, 1))
        response = session.get(law_info['url'])
        soup = BeautifulSoup(response.text, 'html.parser')
        
        law_data = {
            "LawName": law_info['name'],
            "LawURL": law_info['url'],
            "LawDate": law_info.get('date', ''),
            "LawType": "",
            "LawCategory": "",
            "LawPublishDate": "",
            "LawModifiedDate": "",
            "LawArticles": []
        }
        
        # 獲取法規基本資訊
        info_table = soup.select_one("table.table-bordered")
        if info_table:
            for row in info_table.select("tr"):
                th = row.select_one("th")
                td = row.select_one("td")
                if not th or not td:
                    continue
                
                field_name = th.text.strip()
                field_value = td.text.strip()
                
                if "法規名稱" in field_name:
                    law_data["LawName"] = field_value
                elif "法規體系" in field_name:
                    law_data["LawCategory"] = field_value
                elif "公發布日" in field_name:
                    law_data["LawPublishDate"] = field_value
                elif "修正日期" in field_name:
                    law_data["LawModifiedDate"] = field_value
                elif "發文字號" in field_name:
                    law_data["LawNumber"] = field_value
        
        # 獲取法規條文內容
        law_content_table = soup.select_one("table.tab-law")
        
        # 如果找到標準的法規表格，從表格解析條文
        if law_content_table:
            for row in law_content_table.select("tr"):
                cols = row.select("td")
                if len(cols) >= 2:
                    article_number = cols[0].text.strip()
                    article_content = cols[1].text.strip()
                    
                    if article_content:
                        law_data["LawArticles"].append({
                            "ArticleNumber": article_number,
                            "ArticleContent": article_content
                        })
                elif len(cols) == 1 and "章" in cols[0].text:
                    # 這是章節標題
                    chapter_title = cols[0].text.strip()
                    law_data["LawArticles"].append({
                        "ArticleNumber": "章節",
                        "ArticleContent": chapter_title
                    })
        
        # 如果沒有找到條文表格，嘗試從其他地方獲取內容
        if not law_data["LawArticles"]:
            # 檢查是否有 div.law-reg-content.law-article 或 div#divLawContent08
            content_div = soup.select_one(".law-reg-content.law-article") or soup.select_one("div[id*='divLawContent']")
            
            if content_div:
                # 分析 span 標籤中的文本
                articles = []
                current_article = None
                current_content = []
                
                # 使用更有針對性的選擇器來處理法規條文
                spans = content_div.select("span")
                for span in spans:
                    text = span.get_text(strip=True)
                    if not text:
                        continue
                    
                    # 檢查是否是條文標題（使用正則表達式匹配「第X條」格式）
                    import re
                    article_match = re.match(r'^第\s*([一二三四五六七八九十百千]+|\d+)\s*條', text)
                    
                    if article_match:
                        # 如果已經有收集的條文，先儲存起來
                        if current_article and current_content:
                            articles.append({
                                "ArticleNumber": current_article,
                                "ArticleContent": " ".join(current_content)
                            })
                        
                        # 開始收集新的條文
                        current_article = text.split("　")[0]  # 取得條號部分
                        # 移除條號部分，只保留條文內容
                        content_text = text[len(current_article):].strip()
                        if content_text:
                            current_content = [content_text]
                        else:
                            current_content = []
                    else:
                        # 繼續收集當前條文的內容
                        if current_article:
                            current_content.append(text)
                
                # 別忘了最後一個條文
                if current_article and current_content:
                    articles.append({
                        "ArticleNumber": current_article,
                        "ArticleContent": " ".join(current_content)
                    })
                
                # 如果成功解析出條文
                if articles:
                    law_data["LawArticles"] = articles
                else:
                    # 如果無法按條解析，就整個文本作為一個條目
                    law_data["LawArticles"].append({
                        "ArticleNumber": "",
                        "ArticleContent": content_div.get_text(strip=True)
                    })
        
        return law_data
    except Exception as e:
        logging.error(f"Error processing law {law_info['name']}: {e}")
        return None

def save_json(data, filename):
    """儲存法規資料為JSON檔案"""
    os.makedirs('kaohsiung_law_jsons', exist_ok=True)
    # 處理檔名中可能有的特殊字元
    safe_filename = "".join([c for c in filename if c.isalnum() or c in ' _-']).strip()
    if not safe_filename:
        safe_filename = f"law_{hash(filename) % 10000}"
    
    filepath = os.path.join('kaohsiung_law_jsons', f"{safe_filename}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filepath

def main():
    base_url = "https://outlaw.kcg.gov.tw"
    session = get_session()
    
    # 獲取所有法規的URL和總數
    all_laws_url, total_laws = get_all_laws_url(session, base_url)
    if not all_laws_url:
        logging.error("Could not get all laws URL")
        return
    
    # 獲取所有法規連結
    all_law_links = get_all_law_links(session, all_laws_url, base_url, total_laws)
    
    # 處理所有法規內容
    with tqdm(total=len(all_law_links), desc="Processing laws") as pbar:
        successful_count = 0
        failed_count = 0
        
        # 分批處理，每次5個法規
        for i in range(0, len(all_law_links), 5):
            batch = all_law_links[i:i+5]
            
            # 使用多線程處理每一批
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(get_law_content, law_info, session): law_info for law_info in batch}
                
                for future in concurrent.futures.as_completed(futures):
                    law_info = futures[future]
                    try:
                        law_data = future.result()
                        if law_data:
                            filename = law_data['LawName']
                            filepath = save_json(law_data, filename)
                            logging.info(f"Saved law: {filename}")
                            successful_count += 1
                        else:
                            failed_count += 1
                            logging.warning(f"Failed to process: {law_info['name']}")
                    except Exception as e:
                        failed_count += 1
                        logging.error(f"Exception processing {law_info['name']}: {e}")
                    
                    pbar.update(1)
            
            # 批次處理完成後稍等，避免請求過快
            time.sleep(random.uniform(1, 2))
    
    logging.info(f"Completed! Successfully processed {successful_count} laws, failed: {failed_count}")

if __name__ == "__main__":
    main()