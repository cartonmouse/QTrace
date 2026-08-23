# 阶段 97：首登模型配置可暂时跳过

## 目标

保留首次模型配置界面和真实 LLM/Embedding 的必填字段，同时允许没有 API Key 的访客先进入 QTrace，稍后从“模型设置”补齐配置。

## 实现

- `Onboarding.jsx` 在 LLM 和 Embedding 两步的底部都增加“暂时跳过，稍后在设置中填写”按钮；原有连接测试、保存和错误提示不变；
- `AuthContext` 增加按账号隔离的跳过标记：跳过后刷新页面不会立即重新弹出引导，退出登录时清除该账号标记；
- 没有放宽后端 Provider Gate。未配置模型时，专项训练、Agent 等依赖模型的接口仍会返回“请先配置 LLM 或启用本地演示模型”，避免 Stub/未配置状态被伪装成真实 LLM 可用；
- 跳过后可以进入画像、设置等页面，用户可在“模型设置”中配置真实 LLM、Demo Embedding 或本地 Embedding。

## 本地验证

- `npm run typecheck --prefix frontend` 通过；
- `npm test --prefix frontend`：3 passed；
- `npm run build --prefix frontend`：Vite 生产构建通过，3809 个模块转换成功；
- 没有读取或输出 API Key、真实简历或个人文档；没有调用 VPS、GitHub 或外部 LLM API。

## 同步边界

本阶段只修改本地正式工程，未提交、未推送 GitHub，也未重建或重启腾讯云 VPS。只有用户明确要求时，才执行后续同步。
