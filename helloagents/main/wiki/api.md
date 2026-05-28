# API 手册

## 概述
后端通过 `/api/v1` 提供模型信息、插件运行、mask 调整与 inpaint 修复接口。

## 认证方式
当前本地应用无认证机制。

---

## 接口列表

### 图像修复

#### POST /api/v1/inpaint
**描述:** 使用输入图片与 mask 执行图像修复。

#### POST /api/v1/run_plugin_gen_mask
**描述:** 调用支持 `gen_mask` 的插件生成前端可用 mask。

#### POST /api/v1/adjust_mask
**描述:** 对 mask 进行膨胀、腐蚀等调整。


### 水印检测插件

#### POST /api/v1/run_plugin_gen_mask
**描述:** 当 `name` 为 `WatermarkDetector` 时，根据水印检测策略生成 PNG mask。

**请求参数:**
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| name | string | 是 | 固定为 `WatermarkDetector` |
| image | string | 是 | base64 图片 |
| watermark_mode | string | 否 | `cv_ocr` / `vl_sam` / `combined`，默认 `cv_ocr` |
| watermark_prompt | string | 否 | 开放词汇检测提示词 |
| watermark_confidence | number | 否 | 置信度阈值，0-1 |
| watermark_dilate | number | 否 | mask 膨胀像素，0-256 |
| watermark_max_area_ratio | number | 否 | 候选区域最大面积比例，0-1 |

**响应:** PNG mask，255 表示需要修复区域。
