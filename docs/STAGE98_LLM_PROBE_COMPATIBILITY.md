# 阶段 98：LLM 连接探测兼容性

## 问题

专项训练已经可以调用用户填写的 OpenAI-compatible LLM，但模型设置页的“测试连接”返回“LLM 返回了空内容”。两条路径使用同一个 Provider，但连接探测额外把 `max_tokens` 限制为 1；部分带 reasoning 的模型可能在生成可见文本前就结束，因此被连接测试误判为失败。

## 实现

- `OpenAICompatibleProvider._chat()` 增加仅供探测使用的 `allow_empty` 边界，默认仍为 `False`。
- `probe()` 将短请求上限调整为 16，并允许合法 `choices[0].message` 中的空可见 `content` 作为“已收到模型响应”。
- 正常 `structured_chat()` 仍拒绝空内容，不会把专项训练的业务空回复伪装成成功。
- 没有改变 API Key 存储、返回或日志策略；本阶段只使用合成 Provider 响应回归，不调用真实 LLM。

## 验证

```text
python -m pytest -p no:cacheprovider -q tests/test_provider_resilience.py tests/test_llm_connection.py
10 passed
```

首次运行若未设置临时 `REBUILD_DB_PATH`，正式目录的只读 `data` 会导致应用导入阶段 SQLite 写入失败；这属于本地权限边界。回归使用阶段目录中的临时测试数据库，未触碰正式数据。

## 人工验收

使用已配置真实 LLM 的账号进入“设置 → LLM 服务”，点击“测试连接”：

1. 正常返回文本的模型应显示“连接正常”。
2. 专项训练已能工作的 reasoning/短输出模型不应再因为空可见 `content` 被误报为失败。
3. 仍无法访问、HTTP 非 2xx 或响应缺少 `choices/message` 时，应保留失败提示。

