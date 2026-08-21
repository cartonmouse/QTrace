# 阶段 5：专项掌握度与长期画像

## 目标

让专项训练结果真正改变下一轮训练的输入：

```text
topic_drill 完成
  -> 保存 session review
  -> 更新全局 profile
  -> 更新 user_id + topic 的掌握度
  -> 画像页显示领域进度和薄弱点
  -> 领域历史接口支持继续复盘
```

## 数据模型

新增 SQLite 表 `topic_profiles`：

| 字段 | 含义 |
| --- | --- |
| `user_id + topic` | 一个用户在一个训练领域的唯一记录 |
| `attempts` | 完成的专项训练次数 |
| `mastery_score` | 历次平均得分，范围 0—10 |
| `last_score` | 最近一轮得分 |
| `weak_points_json` | 这个领域累计的薄弱点 |
| `updated_at` | 最近一次写回时间 |

全局 `profiles` 仍然保留，用于跨领域的总体掌握度和薄弱点；`topic_profiles` 解决的是“我在 RAG 和 Agent 上分别练得怎么样”。

## 写回时机

只有第一次生成复盘时才写回画像：

```python
had_review = bool(state["review"])
engine.finish(state)
if not had_review:
    store.update_profile_after_review(..., topic=state["topic"])
```

这样重复打开复盘页不会重复增加训练次数，也不会让掌握度被重复计算。

当前掌握度使用透明的累计平均分，适合学习和调试。参考项目使用更复杂的长期画像、薄弱点生命周期和 SM-2 调度；后续可以在不改变接口的前提下替换算法。

## 接口

- `GET /api/profile`：全局画像，同时返回 `topic_mastery`
- `GET /api/profile/topics`：领域掌握度列表
- `GET /api/profile/topic/{topic}/history`：指定领域的训练历史

## 面试追问卡

### 1. 为什么要区分全局画像和领域画像？

“回答结构不清”可能是跨领域的表达问题，而“RAG 的 chunk 策略理解不足”只属于某个知识领域。分层存储可以避免把所有问题混成一张弱点列表。

### 2. 为什么不能每次打开复盘都更新掌握度？

复盘页面读取是幂等操作，更新必须绑定“首次完成复盘”这个状态转移，否则刷新页面会虚增训练次数。

### 3. 为什么当前使用平均分？

平均分容易解释、容易测试，适合第一版验证数据链路。生产系统可以加入时间衰减、题目难度、覆盖度和间隔复习，但要先建立可观测的评估数据。

### 4. 这个掌握度能直接证明能力提升吗？

不能。它是训练内部指标，不等同于真实面试表现。要验证有效性，需要固定题集、盲评、一致的评分标准和一段时间的对照数据。

## 验收命令

```powershell
cd D:\3BUPT\mark'workshop\techsnowsong\rebuild\backend
python -m pytest -q

cd ..\frontend
npm run typecheck
npm run build
```
