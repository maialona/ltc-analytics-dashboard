# 長照機構數據分析儀表板 (Long-Term Care Agency Analytics Dashboard)

這是一個使用 Streamlit 構建的數據分析應用程式，用於分析長照機構的經營績效、個案使用率及成長動能。

## 功能特色
- **機構總覽**：關鍵績效指標 (KPI)、額度使用率趨勢、營收機會分析。
- **雙月比較**：分析兩個月份之間的營收與個案數變化。
- **服務狀態**：監控個案服務狀態（服務中、暫停、結案）的分佈與趨勢。
- **異常警示**：自動偵測低使用率個案並提供改善建議。
- **自動化洞察**：AI 生成的月報摘要，提供營收動能與異常比例分析。

## 如何在本機執行

1. 安裝套件：
   ```bash
   pip install -r requirements.txt
   ```

2. 執行應用程式：
   ```bash
   streamlit run app.py
   ```

## 如何部署 (Deployment)

最簡單的部署方式是使用 **Streamlit Community Cloud**。

### 步驟 1：準備 GitHub
1. 在 GitHub 上建立一個新的儲存庫 (Repository)。
2. 將此專案的所有檔案 (包含 `app.py`, `requirements.txt`, `data/` 資料夾) 上傳或 Push 到該儲存庫。
   * **注意**：如果您的資料 `data/` 包含敏感個資，請勿上傳到公開 (Public) 的 GitHub 儲存庫。建議使用 Private Repo 或將資料去識別化。

### 步驟 2：連接 Streamlit Cloud
1. 前往 [Streamlit Community Cloud](https://streamlit.io/cloud)。
2. 使用 GitHub 帳號登入。
3. 點擊 **"New app"**。
4. 選擇您剛建立的 GitHub Repository。
5. 設定主要檔案路徑 (Main file path) 為 `app.py`。
6. 點擊 **"Deploy!"**。

### 其他平台
您也可以部署到 Docker 容器或其他支援 Python 的平台 (如 Render, Railway, Heroku)。

**Docker 指令範例：**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
```
