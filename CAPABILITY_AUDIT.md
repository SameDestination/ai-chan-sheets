# ChatGPT Pro / Codex 生图能力审计

审计日期：2026-10-27。以下结论区分实际观察、官方文档与尚未验证的事项。

| 检查项 | 实际结果 |
| --- | --- |
| Codex 通过 ChatGPT 登录 | 是。官方 CLI `codex.cmd login status` 在可访问用户配置的执行环境返回 `Logged in using ChatGPT`。受限沙箱中的同一诊断因无法找到主目录而失败，不能据此断言未登录。 |
| API-key 模式 | 该 CLI 登录诊断显示 ChatGPT 模式；本应用完全没有 API-key 生图适配器，也不读取密钥或 OAuth 凭据。此结果不等于独立验证本会话每项工具的计费来源。 |
| 会话内置 image_gen 暴露 | 是。当前 Codex 会话的真实工具 schema 提供生成、参考文件输入、编辑及透明背景能力。工具暴露不是成功调用证据。 |
| 订阅计费和包含额度 | 尚未验证当前图像请求可使用的包含额度；没有取得当前权威额度快照，也没有实际图像请求的计费回执。 |
| 返回真实生成文件 | 否；本次安装没有发起生图。 |
| 真实参考条件验证 | 否；未发起生图。 |
| 独立程序调用订阅生图 | 尚未验证，没有可复现的端到端证据。本应用使用模式 B。 |
| 实际执行报告的图像模型 | `unreported`。官方功能文档目前描述内置模型为 `gpt-image-2`；这不是本次执行结果。 |
| 本次真实调用 | 图像 0 次；订阅视觉/规划 0 次。确定性测试图不计为真实生成。 |

当前状态为 `SUBSCRIPTION_IMAGE_GENERATION_NOT_AUTOMATABLE`。本地项目管理、审阅、版本选择、合成、独立验证与导出可以在本会话结束后独立运行。会话内生图与独立程序自动化均未因安装而变成已验证。

## 官方资料与边界

- [官方 imagegen skill](https://github.com/openai/skills/blob/main/skills/.system/imagegen/SKILL.md)：内置工具路径不需要 `OPENAI_API_KEY`；API-key CLI 是另一条路径。本项目不使用该回退路径。安装的本地 skill 与此边界一致。
- [Codex / ChatGPT 图像功能](https://learn.chatgpt.com/docs/image-generation)：描述交互会话和真实参考图片输入。其对程序化图像生成的 API 建议不在本项目授权范围内。
- [Codex 价格和用量](https://learn.chatgpt.com/docs/pricing)：图像生成消耗通用包含额度；包含额度耗尽后可能使用购买的积分。当前余量与重置时间需在官方用量界面或交互 CLI `/status` 核实。不能将 Pro 理解为不限量。
- [官方用量页面](https://chatgpt.com/codex/settings/usage)：由用户在已登录的官方客户端检查。本应用不抓取浏览器会话、cookies 或登录 token。
- [SIWC preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)：ChatGPT plan token-sharing preview 明确不支持 image generation。可以输入图片或使用文本推理不等于可以借 OAuth 调用图像端点。
- [Codex app-server](https://learn.chatgpt.com/docs/app-server)：记录了 `account/read` 和 `account/rateLimits/read` 等只读接口。通用 RPC、SDK、CLI 的存在不证明无头会话能调用同一内置图像工具。
- [ChatGPT 与 API 分开计费](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)：本应用不请求、配置或使用普通 API 计费。
- 用户提供的 `https://developers.openai.com/docs/pricing` 当前指向 API 价格页；不能把它当作本机 Pro 剩余额度的证明。

## 模式 B 的精确操作

1. 导入实际参考原图，记录来源、角色、哈希和需要的独立裁剪。完成角色分析与清单，明确批准版本化快照。
2. 在已经通过 ChatGPT 登录的官方客户端核实本次包含额度、重置时间及是否可能使用额外积分。无法确认时停止；禁止购买积分或使用 API 回退。
3. 在本地 UI 安排任务并恢复队列。填写本次真实计费/额度证据，只授权一个请求，导出该项完整交接说明。
4. 将说明及真实参考图片交给交互 Codex。由该代理检查参考并调用当前会话内置 `image_gen` 一次；不要假设 `codex exec` 会提供该工具。工具不支持强制尺寸/质量时将其作为意图，记录实际结果。
5. 从工具实际报告的真实文件位置复制选定输出，通常位于 `$CODEX_HOME/generated_images/...`。不能编造输出位置，也不能假设工具接受任意输出路径参数。
6. 在 UI 以 `codex_builtin` 导入，记录原始来源、真实模型（未报告则 `unreported`）、参考哈希、尺寸与计费证据。工具未暴露时改用官方 ChatGPT Images 手工生成并明确选择 `manual_chatgpt_import`。
7. 人工逐项检查角色、左右、解剖、衣物、符号、单对象和背景；接受实际尺寸差异后批准、明确选择版本，再制作画板。成功导入或像素相等都不代表艺术批准。
8. 限额、认证错误或结果未知时暂停。已提交后超时必须核对输出或明确决定重试；不能自动切换账号、后端、模型或消耗购买的积分。

完整 22 图批次没有授权启动。该应用不调用普通 Image/Responses API、提取 OAuth、使用非官方后端、订阅代理或浏览器 cookies。测试夹具不能用于声称 `SUBSCRIPTION-IMAGEGEN-VERIFIED`、`STANDALONE-AUTOMATION-VERIFIED` 或 `ARTWORK-APPROVED`。
