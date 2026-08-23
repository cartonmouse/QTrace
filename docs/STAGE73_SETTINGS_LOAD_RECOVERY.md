# 阶段 73：模型设置加载恢复

## 背景

阶段 72 已经修复保存动作的反馈归属，但设置页初始化请求仍然没有 catch。`/api/settings` 失败时页面会一直停留在“正在读取模型设置…”，用户无法区分后端未启动、认证过期和接口异常，也没有重试入口。

## 实现

`SettingsPage` 现在把初始化请求拆成三态：

```text
loading
  -> success: 渲染模型设置
  -> failure: 显示错误详情 + 重新读取模型设置
```

具体变化：

- 新增 `loading`、`loadError` 和 `loadKey` 状态；
- 读取请求失败时保留 `ApiError` 的安全 message，不显示请求体或密钥；
- 重试只增加 `loadKey`，重新读取同一个 `/settings` 接口，不保存配置、不创建索引、不调用模型；
- 用 `active` 标记忽略组件卸载后的旧请求结果，避免路由切换后旧响应覆盖新状态；
- loading 使用 `role="status"`，错误使用 `role="alert"`；
- 错误卡沿用工业瑞士印刷方向，硬边、警示红、无圆角和无额外依赖。

## 与本地模型启用的关系

本阶段没有把“页面读取成功”误说成本地模型推理成功。模型设置页的证据层级仍然是：

1. `/settings` 成功返回，说明当前配置可读；
2. 点击保存后面板显示保存反馈，说明配置写入成功；
3. 个人文档库显式重建索引，才会真正触发本地 Embedding Provider；
4. 文档检索返回证据，才能证明该模型参与了检索链路。

这种分层可以区分“设置接口正常”“配置持久化成功”和“模型实际加载/检索成功”。

## 验收证据

暂存工程通过：

```text
npm run typecheck       PASS
npm run build           PASS
python scripts/frontend_route_preflight.py  PASS
pytest tests/test_frontend_route_preflight.py -q  12 passed
```

新增源码契约覆盖 `loadKey`、`重新读取模型设置` 和 `settings-load-card`。后续同步正式工程后重新运行全量回归和本地运行态 smoke。

本阶段只使用合成源码夹具，没有读取或输出 API Key、真实简历、个人文档或浏览器存储，没有调用外部 API、删除文件、部署或提交推送 GitHub。

## 面试讲法

> 我在配置保存反馈之后又补了一层初始化恢复。之前 `/settings` 读取失败时页面会永久 loading，用户无法判断是服务没启动还是请求失败。我把它拆成 loading、success、failure 三态，失败时保留安全错误信息并提供无副作用重试；用 active 标记避免卸载后的旧请求污染状态。对于本地 Embedding，我仍然区分配置可读、配置已保存、重建索引和检索命中四层证据，没有把页面显示“已配置”夸大成模型推理成功。

## 未完成边界

- 登录后的浏览器视觉验收仍需用户使用合成账号完成；
- 本阶段没有自动执行真实 LLM 或本地模型请求；
- 正式工程全量回归、构建和运行态 smoke 需在同步后再次执行。
