# Dify 與 WearSight 網頁連接

可直接在 Dify 匯入 [車刀磨耗分析工作流.yml](車刀磨耗分析工作流.yml)。工作流接受 `image_url` 與 `question`，先呼叫 WearSight 分析 API，再由 Ollama `phi4:latest` 說明後端產生的結果。

```text
WearSight 網頁 → POST /api/assistant
  → WearSight 後端（保護 Dify API 金鑰）
  → Dify /v1/workflows/run
  → HTTP POST WearSight /api/analyze
  → Ollama Expert → expert_answer
```

## Dify 設定

1. 匯入並發布 `車刀磨耗分析工作流.yml`。
2. Ollama Base URL 設為 `http://host.docker.internal:11434`，模型選 `phi4:latest`。
3. Dify HTTP 節點使用 `http://host.docker.internal:8000/api/analyze`。
4. 在 Dify「訪問 API」建立 Service API 金鑰。
5. 複製 `.env.example` 為 `.env`，填入 `DIFY_API_KEY`。金鑰不可提交到 Git。
6. 若 Dify 使用預設主機 80 連接埠，保留 `DIFY_API_URL=http://host.docker.internal/v1`；本機使用其他連接埠時一併修改。

Dify 的 SSRF Proxy 必須允許 Docker 主機位址。先在 Dify `docker/.env` 設定：

```text
SSRF_PROXY_ALLOW_PRIVATE_DOMAINS=host.docker.internal
SSRF_PROXY_ALLOW_PRIVATE_IPS=<host.docker.internal 解析出的 IPv4>/32
```

然後重新建立 `ssrf_proxy` 容器。只加入實際解析出的單一 `/32` 位址，不要開放整個私人網段。

## API 行為

- 網頁上傳圖片後，後端保存原圖與完整分析快照；Dify 金鑰只存在後端環境變數。
- Dify 的 JSON 分析請求只產生可重現的檢測結果，不在 `/api/analyze` 內再次呼叫 Dify，避免遞迴。
- Dify 無法連線時，問答會退回本機 Ollama；人工覆核結果至少保留後端的原因與建議。
- 狀態、磨耗率、Top-5 與處置建議由 FastAPI 決定，LLM 只負責說明。

首頁左下角顯示「Dify 已連線」後，完成一次圖片分析並使用「Dify 檢測結果問答」。成功回覆的來源會標示 `Dify / Ollama`。
