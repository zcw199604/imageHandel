# 项目技术约定

---

## 技术栈
- **后端:** Python / FastAPI / OpenCV / PyTorch / PIL
- **前端:** TypeScript / React / Vite
- **模型能力:** IOPaint inpaint 模型、插件式图像/Mask 生成能力

---

## 开发约定
- **代码规范:** 保持原 IOPaint 项目风格，后端使用类型标注和模块化插件，前端使用现有 Zustand 状态与组件结构。
- **命名约定:** Python 使用 snake_case；TypeScript 使用 camelCase/PascalCase。

---

## 错误与日志
- **策略:** 后端 FastAPI 统一异常处理中返回 JSON 错误；插件初始化失败需给出明确日志。
- **日志:** 后端复用 loguru。

---

## 测试与流程
- **测试:** 后端优先使用 pytest；前端至少通过构建或类型检查。
- **提交:** 使用清晰动词短语描述功能变更。
