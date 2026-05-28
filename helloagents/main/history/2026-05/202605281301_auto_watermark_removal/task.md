# 任务清单: 自动水印识别与去除

目录: `helloagents/main/plan/202605281301_auto_watermark_removal/`

---

## 并行子代理标注（可选）

启用条件: 可并行任务必须写入范围不重叠并可独立验证。

- 并行组 A: 任务 [1.1, 1.2, 1.3]；允许写入: `iopaint/plugins/watermark_detector.py`, `iopaint/plugins/__init__.py`, `iopaint/schema.py`；冲突域: 后端插件注册；验证: `pytest iopaint/tests/test_watermark_detector.py`
- 并行组 B: 任务 [2.1, 2.2]；允许写入: `web_app/src/lib/api.ts`, `web_app/src/lib/states.ts`, `web_app/src/components/*`；冲突域: 前端状态与 UI；验证: `npm --prefix web_app run build`
- 不可并行任务: [0.1, 3.1, 4.1, 5A.4, 6.1]；原因: 边界确认、安全检查、文档同步和最终验证需在集成后执行

---

## 0. 方案边界确认
- [√] 0.1 确认本次任务仅覆盖 why.md 的范围内切片，范围外内容不进入实现
- [√] 0.2 确认 how.md 的设计边界完整，尤其是模块职责、接口契约、数据边界和依赖边界
- [√] 0.3 大型项目确认最小改动策略: 不做无关重构、目录搬迁、依赖升级或公共API重命名

---

## 1. 后端自动水印检测插件
- [√] 1.1 在 `iopaint/schema.py` 扩展 `RunPluginRequest` 的可选水印检测参数，验证 why.md#需求-自动水印检测策略选择-场景-选择方案1识别文字或简单水印
- [√] 1.2 新增 `iopaint/plugins/watermark_detector.py`，实现方案1 CV/OCR mask 检测与后处理，验证 why.md#需求-自动水印检测策略选择-场景-选择方案1识别文字或简单水印，依赖任务1.1
- [√] 1.3 在 `iopaint/plugins/watermark_detector.py` 中实现方案2开放词汇检测/分割适配层、懒加载和不可用降级，验证 why.md#需求-自动水印检测策略选择-场景-选择方案2识别非固定复杂水印，依赖任务1.1
- [√] 1.4 在 `iopaint/plugins/watermark_detector.py` 中实现 `combined` 叠加检测、mask 合并、面积限制、膨胀/闭运算，验证 why.md#需求-自动水印检测策略选择-场景-选择叠加检测提升召回率，依赖任务1.2和1.3
- [√] 1.5 在 `iopaint/plugins/__init__.py` 与相关配置中注册水印检测插件，确保基础服务未安装方案2依赖时仍可启动，依赖任务1.4

## 2. 前端策略选择与自动画笔接入
- [√] 2.1 在 `web_app/src/lib/api.ts` 增加水印检测参数传递，验证 why.md#需求-自动水印检测策略选择-场景-选择叠加检测提升召回率
- [√] 2.2 在 `web_app/src/lib/states.ts` 增加自动识别水印动作，将返回 mask 注入 `extraMasks` 或现有临时 mask 流程，验证 why.md#需求-自动去除水印-场景-识别后预览再去除，依赖任务2.1
- [√] 2.3 在相关编辑器/插件组件中新增“自动识别水印”入口、策略选择、加载状态、错误提示和授权使用提示，验证 why.md#需求-自动水印检测策略选择-场景-选择方案2识别非固定复杂水印，依赖任务2.2

## 3. 安全检查
- [√] 3.1 执行安全检查（按G9: 输入尺寸限制、参数范围校验、方案2依赖降级、版权授权提示、无敏感信息写入），依赖任务1和任务2

## 4. 文档更新
- [√] 4.1 更新 `helloagents/main/wiki/modules/backend-api.md`、`helloagents/main/wiki/modules/frontend-editor.md`、`helloagents/main/wiki/api.md`、`helloagents/main/wiki/arch.md`，记录水印检测插件、参数与 ADR，依赖任务3.1
- [√] 4.2 如新增依赖，更新 `requirements*.txt` 或安装说明，并记录版本、兼容性和可选启用方式，依赖任务1.3

## 5. 测试

### 5A. TDD路径（适用）
- [√] 5A.1 RED: 添加后端测试 `iopaint/tests/test_watermark_detector.py`，覆盖模式参数解析、方案1合成图 mask、combined 合并逻辑，确认实现前失败
- [√] 5A.2 GREEN: 以最小生产实现让 RED 测试通过，依赖任务5A.1和任务1
- [√] 5A.3 REFACTOR: 在测试保持通过的前提下整理插件内部策略接口和后处理函数，依赖任务5A.2
- [√] 5A.4 VERIFY: 运行 `pytest iopaint/tests/test_watermark_detector.py`、必要的现有后端测试和 `npm --prefix web_app run build`，记录结果，依赖任务5A.3和任务2

### 5B. TDD-EXEMPT路径（部分适用）
- [-] 5B.1 TDD-EXEMPT: 真实开放词汇/SAM 模型效果评估，原因: 模型下载和 GPU 环境不可稳定复现；替代验证: 使用 mock 自动测试 + 手工图片验证 + 明确依赖不可用降级

## 6. 提交前收尾
- [√] 6.1 检查 `git status`，确认无无关文件、无模型权重/缓存被提交
- [√] 6.2 提交代码并推送，提交信息建议: `Add automatic watermark detection and removal`


## 执行备注
- RED 证据: `pytest iopaint/tests/test_watermark_detector.py -q` 初次因环境缺少 OpenCV/libGL 与 loguru/torch 依赖无法收集；补齐轻量测试依赖并隔离重插件导入后进入 GREEN。
- GREEN/VERIFY: `pytest iopaint/tests/test_watermark_detector.py -q` 通过；`npm --prefix web_app run build` 通过。
- 方案2真实模型评估按 TDD-EXEMPT 处理，本次实现可注入 backend 与 CV fallback，不提交模型权重。
