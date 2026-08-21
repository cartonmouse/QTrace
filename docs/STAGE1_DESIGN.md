# Stage 1 设计说明：认证、配置门禁与面试状态机

## 为什么从这条链开始

参考项目的所有智能入口都依赖三个基础条件：知道当前用户是谁、知道该用户能否调用模型、知道一轮训练的状态保存在哪里。因此第一阶段只做一个竖切片：

```text
注册/登录 -> provider 门禁 -> 开始面试 -> 逐轮回答 -> 结束复盘 -> 历史/画像
```

## 模块边界

```text
frontend/src/api.ts        统一 HTTP 和类型
frontend/src/App.tsx       路由、登录态、页面交互
backend/main.py            HTTP 编排和鉴权依赖
backend/security.py        密码哈希和签名 token
backend/store.py           SQLite 持久化
backend/provider.py        模型能力边界（当前为 StubProvider）
backend/interview.py       显式阶段状态机
```

## 数据流

1. 注册时建立用户、默认设置、空画像。
2. 登录时签发带 `sub`/`exp` 的签名 token。
3. 每个受保护请求从 Bearer token 得到 user id，再用 `user_id` 查询数据。
4. 未配置 provider 时，面试启动返回 `provider_not_configured`。
5. 启用 stub 后，开始面试会把第一条面试官消息和初始状态写入 SQLite。
6. 每次回答由 `InterviewEngine` 追加用户消息、判断阶段是否切换、生成下一问，再整体落盘。
7. 结束时 provider 生成结构化 review，store 更新会话和画像。

## 与真实模型的替换点

`InterviewEngine` 只依赖 `InterviewProvider` 协议；后续新增 `OpenAICompatibleProvider` 时，面试流程和路由不应改动。这个 seam 是本阶段最重要的架构学习点。

