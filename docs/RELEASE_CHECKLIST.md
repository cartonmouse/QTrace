# 问迹 QTrace 发布收口清单

这份清单用于确认公开的 QTrace 仓库包含可运行代码、测试、文档和清晰边界。后续新 commit 和 push 仍然需要用户单独确认。

## 已完成

- [x] README 包含 Windows PowerShell 后端/前端启动命令；
- [x] README 说明 Stub 模式和 OpenAI-compatible 模式的差异；
- [x] README 明确真实长音频、说话人分离、时间戳、知识图谱和 WebSocket 不属于当前交付；
- [x] `.gitignore` 忽略 `data/`、SQLite、`.env`、前端依赖和构建产物；
- [x] API Key 不会出现在 `/api/settings` 返回值；
- [x] 所有用户级会话、画像、复习项、简历目录和 Agent 对话按 `user_id` 隔离；
- [x] 旧 SQLite 通过 settings、sessions、profiles 和 topic_profiles 迁移继续可用；
- [x] Stub 模式不联网，测试不依赖真实模型；
- [x] 后端测试、Python 编译、前端类型检查和生产构建全部通过；
- [x] 工程笔记已同步到 Obsidian，并完成 UTF-8 替换字符扫描。
- [x] GitHub 仓库 `cartonmouse/QTrace` 已创建并发布初始版本；问迹图标已接入 favicon 和 README。
- [x] Personal Agent 的受控 `create_learning_plan` 工具已通过用户隔离测试。

## 后续公开版本需要人工确认

- [ ] 检查 `git status`，确认没有真实简历、录音、API Key、运行数据库和临时账号数据；
- [ ] 选定公开仓库的 README 截图和演示账号策略；
- [ ] 决定是否公开参考项目链接、差异说明和学习边界；
- [x] 确认 GitHub 仓库名、可见性和默认分支；
- [x] 用户已明确授权初始版本和图标版本的提交、推送。

## 真实 LLM 联调前检查

- [x] 在本地模型设置中填写 API Base、Model 和 API Key；
- [x] 验证 Personal Agent 的规划调用和回答调用；
- [x] 验证专项动态出题的 JSON `questions` 数组；
- [x] 验证一次真实面试追问；
- [x] 验证真实复盘 JSON 和复盘会话写回；
- [x] API 失败时补充超时、网络错误、限流和 5xx 有界重试策略；
- [x] 联调过程中没有输出 API Key，也没有上传真实简历文件。
