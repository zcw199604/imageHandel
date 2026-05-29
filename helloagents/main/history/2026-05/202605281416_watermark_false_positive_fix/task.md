# 任务清单: 水印检测误标人体区域修复

目录: `helloagents/main/plan/202605281416_watermark_false_positive_fix/`

---

## 并行子代理标注（可选）

启用条件: 写入范围不重叠且验证明确时可并行。

- 并行组 A: 任务 [1.1, 1.2, 1.3, 1.4]；允许写入: `iopaint/plugins/watermark_detector.py`, `iopaint/schema.py`；冲突域: 后端检测算法；验证: `pytest iopaint/tests/test_watermark_detector.py -q`
- 并行组 B: 任务 [2.1, 2.2]；允许写入: `iopaint/tests/test_watermark_detector.py`；冲突域: 测试样本与断言；验证: `pytest iopaint/tests/test_watermark_detector.py -q`
- 并行组 C: 任务 [3.1, 3.2]；允许写入: `web_app/src/lib/states.ts`, `web_app/src/components/Plugins.tsx`；冲突域: 前端默认参数与提示；验证: `npm --prefix web_app run build`
- 不可并行任务: [0.1, 4.1, 5A.1, 5A.4, 6.1, 6.2]；原因: 边界确认、安全检查、RED/GREEN顺序、文档同步和最终审计需串行执行

---

## 0. 方案边界确认
- [√] 0.1 确认本次修复目标是降低人物主体误检，优先主体安全，不追求复杂水印最高召回
- [√] 0.2 确认不新增大型模型依赖、不重写 inpaint 流程、不改插件 API 契约
- [√] 0.3 确认自动生成 mask 仍需用户预览/可编辑后再修复

## 1. 后端检测算法修复
- [√] 1.1 在 `iopaint/plugins/watermark_detector.py` 修改 `detect_vl_sam` 无真实后端时的降级策略，禁止使用泛化 Laplacian 显著性 fallback，验证 why.md#需求-水印检测不误伤人物主体-场景-Open-Vocabulary-后端不可用
- [√] 1.2 在 `iopaint/plugins/watermark_detector.py` 为连通域过滤增加填充率、bbox 面积、组件面积比例、中心区域约束和大块组件剔除，验证 why.md#需求-水印检测不误伤人物主体-场景-人物照片无水印，依赖任务1.1
- [√] 1.3 在 `iopaint/plugins/watermark_detector.py` 调整后处理顺序和膨胀逻辑，先过滤后小半径膨胀，并增加膨胀后总面积安全门禁，验证 why.md#需求-水印检测不误伤人物主体-场景-人物照片含文字Logo水印，依赖任务1.2
- [√] 1.4 在 `iopaint/schema.py` 和插件默认处理中收紧 `watermark_dilate`、`watermark_max_area_ratio` 默认值，验证默认请求不会生成过大 mask，依赖任务1.3

## 2. 后端回归测试
### 2A. TDD路径（强制）
- [√] 2A.1 RED: 在 `iopaint/tests/test_watermark_detector.py` 添加人物/类人体无水印负样本测试，要求 mask 面积低于安全阈值，确认当前实现失败
- [√] 2A.2 RED: 添加人物/类人体 + 文字水印测试，要求水印区域命中且人体主体区域低误检，确认当前实现失败或暴露边界
- [√] 2A.3 RED: 添加 `vl_sam` 无 backend 时不使用显著性人体边缘的测试，确认当前实现失败
- [√] 2A.4 GREEN: 以最小实现完成任务1，使 2A.1-2A.3 通过
- [√] 2A.5 REFACTOR: 在测试通过后整理候选评分 helper 和常量命名，保持行为不变

## 3. 前端默认参数与提示
- [√] 3.1 在 `web_app/src/lib/states.ts` 将 Watermark Detector 默认参数调整为保守值，例如 `watermarkDilate=4/6`、`watermarkMaxAreaRatio=0.1`，验证 npm 构建
- [√] 3.2 如当前提示不足，在 `web_app/src/components/Plugins.tsx` 增加或调整提示，强调“先预览 mask，确认后再修复”，验证 why.md#需求-自动-mask-预览安全-场景-自动识别后先预览再修复

## 4. 安全检查
- [√] 4.1 执行安全检查（无新增敏感信息、无模型权重提交、无外部服务调用、授权提示仍可见、自动检测不直接修改原图）

## 5. 验证
- [√] 5A.1 VERIFY: 运行 `pytest iopaint/tests/test_watermark_detector.py -q`
- [√] 5A.2 VERIFY: 运行 `npm --prefix web_app run build`
- [√] 5A.3 VERIFY: 手工验证人物无水印图、人物+文字/Logo 水印图、普通文字水印图的 mask 结果
- [-] 5A.4 VERIFY: 如需 Docker 验证，重新打包并启动本地服务，确认 `WatermarkDetector` 插件可用且默认参数生效
  > 备注: 本次修复未要求 Docker 重新验证；已完成后端单测与前端构建验证。

## 6. 文档与收尾
- [√] 6.1 更新 `helloagents/main/wiki/modules/backend-api.md`，记录水印检测主体安全优先、保守 fallback 和默认参数变化
- [√] 6.2 更新 `helloagents/main/wiki/modules/frontend-editor.md`，记录自动 mask 预览确认规范
- [√] 6.3 检查 `git status`，确认无缓存、模型权重、构建产物被提交


## 执行备注
- RED: 新增人物/类人体无水印、人物+角标水印、`vl_sam` 无后端降级测试后，当前实现出现 2 个失败用例，暴露角标识别和显著性 fallback 误检问题。
- GREEN: 调整后端检测为保守 fallback、组件形态过滤、膨胀面积门禁，并收紧默认参数后 `pytest iopaint/tests/test_watermark_detector.py -q` 通过。
- 前端: 默认水印检测参数改为 `watermarkDilate=6`、`watermarkMaxAreaRatio=0.1`，并强化预览 mask 提示。
- 验证: `pytest iopaint/tests/test_watermark_detector.py -q` 通过；`npm --prefix web_app run build` 通过，存在既有 Browserslist 与 chunk size 警告。

## 追加修复记录（2026-05-28 23:58 UTC）
- [√] 根据用户复现条件 `combined/both + 半透明文字 + 人物身上` 增加回归测试，覆盖人物身体上的半透明浅色文字水印，同时约束头部与身体外轮廓误检率。
- [√] 调整 `detect_cv_ocr`：新增局部背景差分弱文字候选，并将 contrast/light/low-sat-edge 三类线索先分别连通域过滤再合并，避免文字候选与人体轮廓先粘连后整体被拒绝。
- [√] 调整后处理：膨胀改为横向优先的小核，并在安全门禁中过滤小孤立人体边缘噪声，减少脸部/身体轮廓被扩张标记。
- [√] 验证：`pytest iopaint/tests/test_watermark_detector.py -q` 通过；`npm --prefix web_app run build` 通过（存在既有 Browserslist/chunk size 警告）。
