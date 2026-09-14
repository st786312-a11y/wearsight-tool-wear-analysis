// Dify Code node input: body (HTTP Analyze body string or parsed object).
// Do not recalculate policy thresholds here. FastAPI owns the decision.
function main({ body }) {
  const result = typeof body === 'string' ? JSON.parse(body) : body;
  if (!result || !['manual_review','continue','replace_or_stop'].includes(result.status) || !Array.isArray(result.reasons)) {
    throw new Error('分析 API 未提供完整狀態，請檢查 HTTP 節點是否成功。');
  }
  return {
    analysis_id: result.analysis_id,
    predicted_wear_percent: result.predicted_wear_percent,
    wear_display: Number.isFinite(result.predicted_wear_percent) ? result.predicted_wear_percent.toFixed(1) + '%' : '無法估算',
    wear_std_percent: result.wear_std_percent,
    status: result.status,
    status_label: result.status_label,
    reason: result.reasons.join(' '),
    annotated_image_url: result.annotated_image_url || '',
    roi_image_url: result.roi_image_url || '',
    model: result.retrieval.model,
    image_source: result.retrieval.image_source,
    result_json: JSON.stringify(result),
  };
}
