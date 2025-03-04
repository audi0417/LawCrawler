# LawCrawler (法律法規爬蟲工具)

一個用於爬取台灣法律法規的專業工具，支援中央法規及地方法規（台北市、台中市）。持續更新中


## 功能特色

- 多源爬取：支援中央法規、台北市法規及台中市法規
- 高效並行：使用 ThreadPoolExecutor 實現多線程爬取
- 異常處理：完善的重試機制和日誌記錄
- 結構化存儲：以 JSON 格式保存所有法規數據
- 用戶友好：帶有進度條顯示，清晰展示爬取進度

## 支援來源

| 來源 | 網址 | 狀態 |
|------|------|------|
| 中央法規 | https://law.moj.gov.tw/ | ✅ 支援 |
| 台北市法規 | https://www.laws.taipei.gov.tw/Law | ✅ 支援 |
| 新北市法規 | https://web.law.ntpc.gov.tw/ | ✅ 支援 |
| 桃園市法規 | https://law.tycg.gov.tw/ | ✅ 支援 |
| 台中市法規 | https://law.taichung.gov.tw/ | ✅ 支援 |

## 安裝

### 前置需求

- Python 3.8+
- pip 套件管理工具

### 步驟

1. 克隆儲存庫

```bash
git clone https://github.com/yourusername/LawCrawler.git
cd LawCrawler
```

2. 安裝依賴套件

```bash
pip install -r requirements.txt
```

## 使用方法

### 爬取中央法規

```bash
python 中央法規.py
```

### 爬取台北市法規

```bash
python 台北市法規.py
```

### 爬取台中市法規

```bash
python 台中市法規.py
```

## 輸出格式

所有爬取的法規都會以 JSON 格式保存，基本結構如下：

```json
{
  "LawName": "法規名稱",
  "LawCategory": "法規分類",
  "LawModifiedDate": "最後修改日期",
  "LawArticles": [
    {
      "ArticleNo": "條號",
      "ArticleContent": "條文內容"
    }
  ],
  "LawURL": "原始網址"
}
```

## 實現細節

### 共通特性

- 使用 `requests` 進行網頁請求
- 使用 `BeautifulSoup` 解析 HTML 結構
- 使用 `concurrent.futures` 實現多線程爬取
- 實現指數退避重試機制，處理網路不穩定情況
- 隨機延遲請求，降低對目標伺服器的壓力

### 中央法規爬蟲

- 通過遞歸解析法規分類樹形結構
- 支援多頁面爬取與分類關聯

### 台北市法規爬蟲

- 通過分頁機制批量獲取法規列表
- 分別爬取法規基本信息和具體條文內容

### 台中市法規爬蟲

- 識別法規狀態，避免爬取已廢除法規
- 支援法規章節結構保存

## 效能調優

- 使用連接池重用 HTTP 連接
- 批量處理 URL，減少記憶體佔用
- 進度條顯示，實時監控爬取進度

## 常見問題

**Q: 爬取過程中遇到 HTTP 錯誤怎麼辦？**  
A: 程式已內建重試機制，會自動重試失敗的請求。如果問題持續存在，請檢查日誌文件了解詳情。

**Q: 如何調整爬取速度？**  
A: 您可以調整代碼中的 `time.sleep()` 參數和 `max_workers` 參數來控制爬取速度。

**Q: 法規數據多久更新一次？**  
A: 本工具不會自動更新數據，需手動執行以獲取最新法規。建議定期執行以保持數據最新。

## 貢獻指南

歡迎提交 Pull Request 或建立 Issue！

1. Fork 此倉庫
2. 創建您的功能分支：`git checkout -b feature/amazing-feature`
3. 提交您的更改：`git commit -m 'Add some amazing feature'`
4. 推送到分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

## 免責聲明

本工具僅供研究和學習使用。請尊重各法規網站的使用條款，不要過度頻繁地訪問這些網站。用戶須自行承擔使用本工具的法律責任。

## 授權

本專案採用 MIT 授權 - 詳情請參閱 [LICENSE](LICENSE) 文件

## 作者

**陳楷融** - [GitHub Profile](https://github.com/audi0417)

如果您覺得這個專案有幫助，請給它一個 ⭐️！

## 更新日誌

- **v1.0.0** (2025-02-28)
  - 初始版本發布
  - 支援中央法規、台北市法規和台中市法規爬取

---

Made with ❤️ in Taiwan
