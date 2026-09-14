# WearSight Windows 離線部署包

此部署包適用於 Windows 10/11 Intel／AMD 電腦，包含 WearSight 刀具磨耗系統、DINOv2 模型快取、YOLO 權重、Dify 1.16.1 的現有設定與資料，以及 Ollama 與目前已下載的模型。PPT 與簡報產生檔未收錄。

## 目的電腦需求

- Windows 10/11 64 位元
- Docker Desktop（使用 WSL 2）
- 建議至少 16 GB RAM、35 GB 可用空間
- 若用隨身碟搬移，請使用 NTFS 或 exFAT；映像封存檔可能超過 FAT32 的 4 GB 限制

## 第一次安裝

1. 安裝並啟動 Docker Desktop，等待畫面顯示引擎已就緒。
2. 將整個部署包複製到目的電腦的本機磁碟。
3. 建議先執行 `Verify-Package.ps1`，確認搬移過程沒有損壞大型檔案。
4. 在 `Install-Offline.ps1` 上按右鍵，選擇「使用 PowerShell 執行」。
5. 若 Windows 阻擋本機腳本，可開啟 PowerShell，在部署包資料夾執行：

   `powershell -ExecutionPolicy Bypass -File .\Install-Offline.ps1`

6. 安裝完成後開啟：
   - WearSight：<http://localhost:8080>
   - Dify：<http://localhost:8081>

## 日後使用

- 啟動：執行 `Start.ps1`
- 停止：執行 `Stop.ps1`
- Docker Desktop 必須保持執行

Dify 的既有帳號、密碼、工作流和金鑰會隨資料一同移轉。部署包應視為敏感資料妥善保存，移轉後建議更改 Dify 登入密碼。目的電腦若已有同名 Docker 容器或正在使用 8000、8080、8081、8443、11434 連接埠，請先停止衝突的服務。

`backups/dify-postgres.dump` 是額外的資料庫備份；一般安裝會直接使用已封存的完整 Dify 資料，不需要手動匯入。
