# Dify 與 ROI 分析 API

Web UI 目前直接呼叫 FastAPI。Dify 作為另一個入口，沿用同一分析 API；本次程式更新不會自動修改 Dify 內已發布的工作流。

```text
Start（image_url、question）
  → HTTP POST /api/analyze（只傳 image_url，避免重複呼叫 LLM）
  → Code（讀取後端結果，不重算狀態）
  → question 是否為空？
      空白 → 結果模板 → End
      有問題 → HTTP POST /api/assistant（analysis_id、question）→ End
```

## 分析節點

URL：`http://host.docker.internal:8000/api/analyze`

JSON body：
```json
{"image_url":"由 Start 的變數選擇器插入圖片網址","mode":"dinov2_roi"}
```

圖片也可使用 multipart 的 `image` 上傳欄位。`mode` 可省略以採用系統設定（目前為 DINOv2 ROI）；DINOv3 尚未取得權重時會回傳 503，不會改用 CLIP。測試基準可明確指定 `clip_roi` 或 `clip_full`。

將 HTTP 的 body 傳入 [status-policy.js](status-policy.js) 的 `body`。狀態、覆核原因與建議全部由 FastAPI 提供。刪除舊有 Dify Code 中的 0.5 / 0.85 / 20 / 80 等判斷，避免設定不同步。Code 輸出涉及 null 的欄位請設定為可接受 null，或改只使用 `wear_display` 與 `result_json` 文字欄位。

## 問答節點（建議）

URL：`http://host.docker.internal:8000/api/assistant`

```json
{"analysis_id":"由分析節點輸出的 analysis_id","question":"由 Start 的 question"}
```

只傳編號和問題，後端會讀取完整分析快照。人工覆核狀態由系統直接說明；其他狀態可呼叫 Ollama，失敗則回傳同一份系統建議。

如果保留既有 Ollama Expert 節點，請採用 [ollama-system-prompt.md](ollama-system-prompt.md)，輸入 `result_json` 與 `question`。人工覆核分支應直接輸出 API 的原因與建議，避免 LLM 覆寫判定。LLM 文字只能作補充，End 仍需保留 API 的原始狀態。

## 相容性與輸出

- API 保留 `predicted_rate`（0–1）、`predicted_wear_percent`、`wear_std`、`wear_std_percent`、`top_k` 與圖片網址。
- 不再回傳原本由相似度裁切成的 `confidence`；它不是磨耗率可靠度。使用 `detection_confidence` 或 `average_similarity`，並標示其正確意義。
- 沒有 ROI 或少於五筆案例時，磨耗率為 `null`。模板不可把 null 轉為 0%。
- 檢索資訊在 `retrieval`：model、image_source、mode、k、actual_k、weighting、top_k、index_signature。
- `status`、`status_label`、`reasons`、`assessment`、`thresholds` 為同一份後端判定。
- 每次分析保存完整快照。Dify 不需重複建立分析紀錄。
- 圖片網址為 `/api/results/...`，Dify 端需接上可存取的 API 主機網址。

## 驗證清單

1. 不帶 question 分析，End 顯示原始結果，沒有重複 LLM 呼叫。
2. 帶 question，以相同 analysis_id 取得回答。
3. 沒有刀具 ROI 時，顯示「無法估算／人工覆核」。
4. DINOv3 缺權重時，HTTP 錯誤分支顯示 503 原因。
5. 修改 FastAPI 設定後，下一次分析和 Dify 顯示的 thresholds 一致。
