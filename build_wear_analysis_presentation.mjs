import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/user/Downloads/project0528";
const SKILL_DIR = "C:/Users/user/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations";
const RUNTIME_PYTHON = "C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const TMP_DIR = path.join(workspaceDir, ".ppt-build");
const FINAL_PPTX = path.join(workspaceDir, "reports", "tool_wear_analysis_system_report_7slides_ui_examples.pptx");

const { resolvePresentationFont, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);

await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });

const font = resolvePresentationFont({ availableFonts: ["Microsoft JhengHei", "Noto Sans CJK TC", "Arial"] });
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

const C = {
  navy: "#102B46",
  blue: "#235D91",
  sky: "#EAF2F8",
  mist: "#F5F7F9",
  ink: "#17212B",
  gray: "#667085",
  amber: "#F0A500",
  white: "#FFFFFF",
  line: "#C9D4DF",
  soft: "#DDE7F0",
};

function box(slide, x, y, w, h, fill = "none", line = { fill: "none", width: 0 }, radius = undefined) {
  return slide.shapes.add({ geometry: "roundRect", position: { left: x, top: y, width: w, height: h }, fill, line, borderRadius: radius });
}

function text(slide, value, x, y, w, h, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    typeface: font,
    fontSize: opts.size ?? 20,
    bold: opts.bold ?? false,
    color: opts.color ?? C.ink,
    align: opts.align ?? "left",
    verticalAlignment: opts.verticalAlignment ?? "top",
    autoFit: "shrinkText",
  };
  return shape;
}

function addTitle(slide, title, number) {
  text(slide, title, 72, 48, 920, 52, { size: 32, bold: true, color: C.navy });
  text(slide, String(number).padStart(2, "0"), 1130, 52, 74, 36, { size: 18, bold: true, color: C.blue, align: "right" });
  const line = slide.shapes.add({ geometry: "line", position: { left: 72, top: 112, width: 1136, height: 0 }, fill: "none", line: { fill: C.line, width: 1 } });
  return line;
}

function addBulletList(slide, items, x, y, w, size = 19, color = C.ink, spacing = 50) {
  items.forEach((item, index) => {
    text(slide, "•", x, y + index * spacing, 18, 28, { size, bold: true, color: C.amber });
    text(slide, item, x + 24, y + index * spacing, w - 24, 34, { size, color });
  });
}

async function addPhoto(slide, source, x, y, w, h, alt) {
  const blob = await fs.readFile(path.join(workspaceDir, source));
  slide.images.add({ blob, contentType: "image/jpeg", alt, fit: "cover", position: { left: x, top: y, width: w, height: h }, geometry: "roundRect", borderRadius: "rounded-xl" });
}

async function addScreenshot(slide, source, x, y, w, h, alt) {
  const blob = await fs.readFile(source);
  slide.images.add({ blob, contentType: "image/png", alt, fit: "contain", position: { left: x, top: y, width: w, height: h }, geometry: "roundRect", borderRadius: "rounded-xl" });
}

function processBlock(slide, label, sub, x, y, w, h, accent = C.blue) {
  box(slide, x, y, w, h, C.white, { fill: C.line, width: 1 }, "rounded-xl");
  box(slide, x, y, 8, h, accent, { fill: accent, width: 0 }, "rounded-xl");
  text(slide, label, x + 24, y + 20, w - 38, 30, { size: 21, bold: true, color: C.navy });
  text(slide, sub, x + 24, y + 56, w - 38, h - 64, { size: 15.5, color: C.gray });
}

// Slide 1
{
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  await addPhoto(slide, "sample_uploads/wear_percent_samples/20260824_110424.jpg", 742, 0, 538, 720, "刀具磨耗案例照片");
  box(slide, 696, 0, 70, 720, "#FFFFFF/72", { fill: "none", width: 0 });
  text(slide, "車刀磨耗分析系統", 80, 190, 620, 82, { size: 47, bold: true, color: C.navy });
  text(slide, "YOLO 偵測、Dify 工作流與 Ollama 回答整合", 84, 290, 570, 38, { size: 21, color: C.gray });
  box(slide, 84, 375, 104, 8, C.amber, { fill: C.amber, width: 0 }, "rounded-xl");
  text(slide, "專題進度簡報", 84, 412, 300, 30, { size: 17, color: C.gray });
  text(slide, "2026 年 9 月", 84, 610, 260, 26, { size: 15, color: C.gray });
  slide.speakerNotes.textFrame.setText("本簡報根據目前專案實作與 Dify 測試結果整理。圖片為專案資料庫案例。" );
}

// Slide 2
{
  const slide = deck.slides.add();
  slide.background.fill = C.mist;
  addTitle(slide, "專題目標與目前範圍", 2);
  text(slide, "目標", 86, 160, 160, 44, { size: 24, bold: true, color: C.blue });
  text(slide, "讓使用者上傳車刀圖片後，取得可閱讀的偵測結果與問題說明。", 86, 214, 495, 78, { size: 26, bold: true, color: C.navy });
  processBlock(slide, "輸入", "車刀圖片\n使用者問題為選填", 690, 160, 420, 112, C.blue);
  processBlock(slide, "輸出", "框選圖、刀具類別、偵測信心度\n有問題時另提供文字回答", 690, 302, 420, 138, C.amber);
  text(slide, "本階段完成項目", 86, 360, 260, 34, { size: 22, bold: true, color: C.navy });
  addBulletList(slide, [
    "YOLO 產生刀具框選圖與偵測信心度",
    "Dify 呼叫 FastAPI 並依問題是否存在分流",
    "Ollama 依 API 結果輸出繁體中文說明",
  ], 86, 414, 520, 19, C.ink, 55);
  text(slide, "目前的磨耗率僅作為示意資料，尚未能代表正式模型預測。", 86, 604, 990, 30, { size: 18, bold: true, color: "#9A5A00" });
  slide.speakerNotes.textFrame.setText("本階段的重點是先建立可運行的影像分析與問答工作流。" );
}

// Slide 3
{
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "分析系統 UI 展示", 3);
  await addScreenshot(slide, "C:/Users/user/AppData/Local/Temp/codex-clipboard-96cdcc2b-9d0f-4ba7-b5d1-3e9aa19bb9d0.png", 60, 150, 820, 500, "車刀磨耗分析系統介面");
  text(slide, "使用者操作", 930, 170, 230, 32, { size: 23, bold: true, color: C.navy });
  addBulletList(slide, [
    "上傳車刀圖片",
    "查看原圖與 YOLO 框選圖",
    "查看 Top 5 參考案例",
    "讀取系統分析摘要",
  ], 930, 230, 250, 18, C.ink, 54);
  text(slide, "畫面會同時保留原始圖片與結果圖片，方便進行人工複核。", 930, 500, 250, 56, { size: 17, color: C.gray });
  slide.speakerNotes.textFrame.setText("本頁為實際前端 UI 截圖，展示上傳、框選圖與 Top 5 案例呈現方式。" );
}

// Slide 4
{
  const slide = deck.slides.add();
  slide.background.fill = C.mist;
  addTitle(slide, "分析範例", 4);
  await addPhoto(slide, "sample_uploads/wear_percent_samples/20260825_103207.jpg", 78, 156, 500, 386, "車刀案例照片");
  text(slide, "範例輸出", 650, 166, 320, 34, { size: 25, bold: true, color: C.navy });
  addBulletList(slide, [
    "YOLO 框選刀具位置",
    "顯示偵測信心度與類別",
    "列出 Top 5 相似案例供比對",
  ], 650, 226, 450, 20, C.ink, 55);
  box(slide, 650, 407, 460, 122, "#FFF7E8", { fill: "#EBCB91", width: 1 }, "rounded-xl");
  text(slide, "範例解讀", 680, 430, 180, 28, { size: 20, bold: true, color: "#915A00" });
  text(slide, "偵測信心度僅代表框選可信度。磨耗率需以案例標籤、相似案例與誤差驗證後，才能作為正式判斷依據。", 680, 466, 390, 52, { size: 17, color: C.ink });
  slide.speakerNotes.textFrame.setText("本頁使用專案刀具案例照片說明一次分析流程，避免將偵測信心度誤解為磨耗率。" );
}

// Slide 5
{
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "Dify 工作流 UI 展示", 5);
  await addScreenshot(slide, "C:/Users/user/AppData/Local/Temp/codex-clipboard-40a30ca1-c6d2-4b71-b83e-a357e7a84880.png", 70, 145, 640, 250, "Dify 工作流畫面");
  text(slide, "已完成的流程", 78, 425, 300, 36, { size: 24, bold: true, color: C.navy });
  const nodes = [
    ["開始", "question\nimage_url", C.blue],
    ["車刀圖片分析 API", "POST /api/analyze", C.amber],
    ["條件分支", "question 不為空", C.blue],
    ["Ollama Expert", "qwen2.5:1.5b", C.amber],
    ["結果輸出", "LLM text 或 API body", C.blue],
  ];
  nodes.forEach((node, i) => {
    const x = 74 + i * 228;
    processBlock(slide, node[0], node[1], x, 497, 190, 100, node[2]);
    if (i < nodes.length - 1) {
      slide.shapes.add({ geometry: "rightArrow", position: { left: x + 195, top: 529, width: 24, height: 32 }, fill: C.soft, line: { fill: C.line, width: 1 } });
    }
  });
  text(slide, "實際 Dify 畫面已建立 HTTP API、條件分支與輸出節點。", 760, 185, 380, 65, { size: 20, bold: true, color: C.navy });
  text(slide, "有問題時進入 Ollama Expert；無問題時直接回傳 API 分析結果。", 760, 277, 380, 60, { size: 18, color: C.gray });
  slide.speakerNotes.textFrame.setText("Dify 已完成 HTTP API、條件分支、Ollama Expert 和輸出節點串接，並已成功發布。" );
}

// Slide 6
{
  const slide = deck.slides.add();
  slide.background.fill = C.mist;
  addTitle(slide, "整合測試結果", 6);
  const results = [
    ["FastAPI 串接", "成功", "Dify 已能呼叫本機 /api/analyze"],
    ["輸入格式", "成功", "圖片網址模式已排除先前的 400 錯誤"],
    ["條件分流", "成功", "question 為空時直接輸出，否則進入 LLM"],
    ["Ollama 回答", "成功", "本機 qwen2.5:1.5b 已回傳繁中回答"],
  ];
  results.forEach((row, i) => {
    const y = 168 + i * 98;
    box(slide, 100, y, 1080, 74, C.white, { fill: C.line, width: 1 }, "rounded-xl");
    text(slide, row[0], 132, y + 21, 210, 28, { size: 20, bold: true, color: C.navy });
    text(slide, row[1], 420, y + 21, 110, 28, { size: 18, bold: true, color: "#19734A", align: "center" });
    text(slide, row[2], 570, y + 21, 565, 32, { size: 17, color: C.gray });
  });
  text(slide, "測試結論：Dify → FastAPI → YOLO → Dify → Ollama 的工作流已可運行。", 100, 592, 1080, 40, { size: 24, bold: true, color: C.navy, align: "center" });
  slide.speakerNotes.textFrame.setText("測試使用本機 Dify、FastAPI 與 Ollama，確認完整問題回答分支可正常執行。" );
}

// Slide 7
{
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  await addPhoto(slide, "sample_uploads/wear_percent_samples/20260901_111426.jpg", 760, 0, 520, 720, "刀具案例照片");
  box(slide, 720, 0, 80, 720, "#FFFFFF/76", { fill: "none", width: 0 });
  text(slide, "下一步工作", 80, 80, 560, 58, { size: 38, bold: true, color: C.navy });
  const next = [
    ["1", "建立案例資料庫", "整理圖片與已知磨耗標籤"],
    ["2", "Top 5 相似案例", "使用 CLIP 或 DINOv2 檢索相似圖片"],
    ["3", "磨耗率驗證", "以 weighted kNN、MAE 與 RMSE 評估結果"],
  ];
  next.forEach((row, i) => {
    const y = 205 + i * 126;
    text(slide, row[0], 86, y, 42, 42, { size: 31, bold: true, color: C.amber });
    text(slide, row[1], 150, y + 2, 470, 32, { size: 22, bold: true, color: C.navy });
    text(slide, row[2], 150, y + 44, 470, 28, { size: 17, color: C.gray });
  });
  text(slide, "結論：系統已具備影像偵測與專家問答骨架，下一階段聚焦於讓磨耗率具備可量化的驗證結果。", 84, 608, 570, 56, { size: 18, color: C.gray });
  slide.speakerNotes.textFrame.setText("下一階段將從實際磨耗標籤出發，驗證圖片相似案例能否可靠地估算磨耗率。圖片為專案資料庫案例。" );
}

const candidatePath = path.join(workspaceDir, ".codex-finalizer", "candidate_tool_wear_7slides_ui_examples.pptx");
await fs.mkdir(path.dirname(candidatePath), { recursive: true });
await (await PresentationFile.exportPptx(deck)).save(candidatePath);

const result = await finalizePresentation({
  explicitTotalSlideCount: 7,
  requiredNativeTableOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit"],
  fontPolicy: { basis: "design", families: [font], scriptFonts: { ea: font } },
  verifyArtifactToolImport: true,
  receiptPath: path.join(workspaceDir, ".codex-finalizer", "tool_wear_analysis_system_report_7slides_ui_examples.validation.json"),
});
console.log(JSON.stringify(result, null, 2));
