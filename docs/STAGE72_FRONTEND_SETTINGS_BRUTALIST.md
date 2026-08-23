# 阶段 72：模型设置工业化前端收口

## 目标

阶段 71 已经把本地语义 Embedding 接入后端和设置页，但实际操作中暴露出一个直接影响验收的问题：LLM 和 Embedding 共用同一组 `busy/message/error` 状态。点击 Embedding 保存失败时，错误会显示在 LLM 面板；保存成功也没有说明“保存配置”和“真正调用模型”之间的区别。

本阶段只优化“模型设置”这一块操作面，不改变业务路由、API 协议、Provider 选择和资料处理边界。

## 实现内容

### 1. 两条配置链路各自可观察

`SettingsPage` 将状态拆成两组：

- LLM：`llmBusy`、`llmMessage`、`llmError`；
- Embedding：`embeddingBusy`、`embeddingMessage`、`embeddingError`。

因此一次保存只锁定对应按钮，反馈也只出现在对应面板。错误使用 `role="alert"`，成功状态使用 `role="status"` 和 `aria-live="polite"`，方便人工验收和辅助技术读取。

### 2. 错误信息保留可定位字段

`frontend/src/api.ts` 新增 `formatApiErrorDetail`：

- 继续直接显示后端返回的安全字符串 detail；
- 将 FastAPI 校验错误数组格式化为“字段位置 + 错误信息”；
- 只读取 `loc` 和 `msg` 等结构化字段，不打印请求体，不打印 API Key；
- 未识别的错误仍回退为“请求失败”。

这让本地模型目录不存在、请求字段不合法等问题可以在页面直接定位，而不是统一变成无上下文的“请求失败”。

### 3. 工业瑞士印刷视觉方向

按照 `industrial-brutalist-ui` 选择浅色 Swiss Industrial Print，而不是黑色 CRT 终端：

- 米白纸张背景、碳黑文字、单一警示红；
- 设置页使用硬边 2px 分区、直角面板、结构化边框和技术标签；
- 状态使用等宽字体并保留 `configured / missing` 等可读值；
- 输入框和主按钮在设置页内统一直角、清晰 focus outline；
- 不引入渐变、阴影、半透明装饰或新依赖；
- 用媒体查询适配窄屏，并在 reduced-motion 下关闭过渡。

这次是局部作用域改造，样式集中在 `.settings-page` 下，不重写训练、画像、Agent 等既有页面，降低视觉改造对业务回归的影响。

### 4. 把验收路径写进界面

LLM 面板明确显示：

```text
保存配置 => 个人 Agent => 发送合成问题 => 查看返回结果
```

Embedding 面板明确显示：

```text
保存目录 => 重建索引 => 个人文档库检索 => 查看证据
```

这两个路径强调：保存设置只代表配置持久化，不等于已经发生一次模型调用或已经重建旧文档索引。

## 回归证据

暂存工程通过：

```text
npm run typecheck       PASS
npm run build           PASS
python scripts/frontend_route_preflight.py  PASS
pytest tests/test_frontend_route_preflight.py -q  11 passed
```

新增 `REQUIRED_SETTINGS_FEEDBACK_MARKERS`，检查设置页的独立反馈状态、工业化容器、结构化错误格式化函数和错误/成功样式。全量 Python 回归会在本阶段同步到正式工程后再执行。

本阶段没有读取或输出 API Key，没有读取真实简历、个人文档或浏览器存储，没有调用外部 API，没有删除文件、部署或提交推送 GitHub。

## 浏览器验收边界

本次可以打开本地前端并确认服务返回登录页，但当前自动化浏览器会话没有可复用的已登录标签。按照安全边界，没有在浏览器里输入密码、创建账号或读取 localStorage，因此本阶段没有把“登录后的视觉人工验收”宣称为已完成。

用户后续可用合成账号验收以下项目：

1. 进入“模型设置”，确认两个面板都是硬边工业分区；
2. 在 Embedding 面板填入不存在的目录，确认错误显示在 Embedding 面板内，并包含可定位的错误信息；
3. 填入真实本地模型目录并保存，确认 Embedding 面板显示保存反馈；
4. 进入个人文档库重建索引，确认本地模型链路的结果；
5. 在 LLM 面板保存配置后进入个人 Agent，用合成问题验证真实调用，不能只以“已配置”作为调用成功证据。

## 面试讲法

> 我先处理的是配置页的可观察性，而不是重新设计所有页面。原来 LLM 和 Embedding 共用反馈状态，导致 Embedding 失败会显示在 LLM 区域，用户也无法区分“配置保存成功”和“模型实际调用成功”。我把两条状态链拆开，并让后端结构化校验错误在前端保留字段位置。视觉上采用浅色工业瑞士印刷方向，用硬边网格和单一警示色强化操作分区；样式只作用于设置页，避免破坏训练主链。最后用 typecheck、生产构建和源码契约回归证明改造没有破坏已有路由，登录后视觉验收仍单独保留给合成账号人工彩排。

## 下一步

- 完成正式工程全量 Python 回归和运行态检查；
- 同步 README、CONTEXT、LEARNING_LOG 和 Obsidian 阶段总结；
- 用户回来后按本阶段清单验收登录后的设置页；
- 继续处理下一项独立的前端体验问题，优先保持现有功能不变。
