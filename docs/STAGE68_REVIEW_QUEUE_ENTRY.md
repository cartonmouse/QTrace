# 阶段 68：画像待复习项直达训练

## 发现的问题

画像页已经展示了 SM-2 到期队列、领域和薄弱点，但每一行只是信息展示，没有直接进入专项训练的入口。用户需要记住主题后再手动切换页面，画像到训练的闭环被人为打断。

## 实现

画像页的每个待复习项现在有“立即复习”入口：

```text
ProfilePage 的 due_reviews
    -> buildDueReviewPath(point, topic)
    -> /topic-drill?topic=<topic>&focus=<point>
    -> TopicDrillPage 读取 topic/focus
    -> POST /interview/start(mode=topic_drill, topic, focus)
```

- `buildDueReviewPath` 总是保留待复习点作为 `focus`；有领域时同时带上 `topic`，没有领域的通用表达仍可进入专项训练并由页面选择当前可用主题；
- 复用已有 `TopicDrillPage` 的 query 参数和后端 `focus` 字段，不新增数据库表、不复制 SM-2 逻辑，也不绕过后端用户鉴权；
- 入口使用已有 `text-link` 样式，保持画像页现有布局和移动端换行规则。

## 预检与回归

`scripts/frontend_route_preflight.py` 新增 `REQUIRED_REVIEW_FLOW_MARKERS`，只读检查待复习队列标题、路径构造、主题参数、focus 参数和“立即复习”入口。`tests/test_frontend_route_preflight.py` 新增缺失入口回归；前端 typecheck/build 验证 TypeScript 路由参数和 JSX 结构。

这个静态检查不证明用户点击后的 HTTP 请求成功；后端已有的主题校验、SM-2 到期读取和训练 session 审计仍是运行时证据。

## 面试讲解

可以这样回答“画像如何真正影响训练”：

> 画像页的 SM-2 到期项不是只读报表。用户点击某个待复习点后，前端把主题和复习点作为 query 参数带到专项训练页，训练页再把它们作为 `topic` 和 `focus` 传给后端。后端继续按当前用户校验主题并调用个性化出题链路，所以画像数据最终成为下一场训练的输入，而不是停留在展示层。

## 边界

- 没有读取或输出 API Key，没有读取或上传真实简历、个人文档或数据库内容。
- 没有调用外部 API、输入密码、部署、删除文件或提交推送 GitHub。
- 本阶段只补充画像到专项训练的前端入口，不改变 SM-2 算法、出题策略、Agent 计划或后端权限边界。
