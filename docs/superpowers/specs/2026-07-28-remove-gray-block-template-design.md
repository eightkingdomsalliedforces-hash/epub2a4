# 移除封面灰色色塊設計

日期：2026-07-28

## 問題

「上下色塊」模板會建立 `template-front-top-block` 與
`template-back-bottom-block`。編輯畫布不繪製 shape 元素，因此使用者在編輯時
看不到灰塊；PNG、PDF 與 DOCX 輸出會繪製它們，造成輸出結果突然多出兩個
`#E2E2E2` 灰塊。

## 核准行為

- 完整移除「上下色塊」模板，不再提供於初始模板與編輯器模板選單。
- 共用模板目錄與模板 builder 不再公開或產生 `top_bottom_blocks`。
- 建立或更新任何封面專案時，清除舊專案遺留的
  `template-front-top-block` 與 `template-back-bottom-block`。
- 舊 `.cover.json` 仍可載入；重新建立／更新模板後不再預覽或輸出灰塊。
- 其他自訂 shape、裁切線、出版社封底、書脊及圖片元素不受影響。

## 相容性

若舊專案的 `background.active_template` 是 `top_bottom_blocks`，載入時改用
`minimal_text`，並清除兩個舊色塊。這是有意的相容性遷移，不保留已移除的
視覺效果。

## 測試

- 模板清單及 Desktop 兩個模板選單不含 `top_bottom_blocks`。
- 舊專案經相容性遷移後，兩個元素皆不存在。
- PNG 預覽、PDF 與 DOCX 的回歸測試確認灰塊不會再次輸出。
- 完整 Python 與 Desktop 測試維持通過。
