# 阶段 80：个人文档 PDF 与 Markdown 文件导入

## 用户问题

个人文档库原本已经支持手工保存 Markdown 文本，也已经有文本型 PDF 的后端解析和前端 PDF 入口，但 Markdown 文件还不能直接选择导入。这个阶段把两种文件统一接到个人文档记忆链路。

## 实现结果

- `backend/document_import.py` 保留 `pypdf` 文本层解析，并新增 `.md` 与 `.markdown` 文件的 UTF-8 解码，支持 UTF-8 BOM，拒绝路径型文件名、空文件、错误扩展名和非 UTF-8 文本。
- `/api/agent/documents/upload` 根据文件扩展名选择 PDF 或 Markdown 解析，解析结果仍调用 `PersonalDocumentService.add_document`，因此继续复用用户隔离、正文指纹去重、版本创建、分块和 Embedding。
- 前端个人文档库增加独立的“导入 Markdown”入口；“导入 PDF”继续保留。两者都显示处理中、成功、重复导入和失败提示。
- 导入后不会直接把文件本体放入文档目录，只保存解析后的正文、版本快照和检索 chunks；切换 Embedding 后仍需用户显式点击“重建索引”。

## 数据流

```text
本地文件选择
  -> multipart 上传到本机 FastAPI
  -> PDF 提取文本层 / Markdown UTF-8 解码
  -> PersonalDocumentService 规范化、指纹、分块、Embedding
  -> SQLite 保存当前版本和 chunks
  -> 个人文档检索 / Personal Agent 只读工具
```

## 约束与边界

- PDF 只支持有文字层的文档，扫描 PDF 没有 OCR 能力，页面会明确提示失败。
- Markdown 只接受 `.md`、`.markdown` 和 UTF-8 编码，保留 Markdown 原文，不在导入阶段转换成 HTML。
- 单个文件上传上限为 20 MB，入库文本上限为 100,000 字，过长内容会按统一规则截断并写入标记。
- 解析器不调用外部服务，不读取 API Key，不读取其他用户资料；真正的 Embedding 是否联网仍由用户模型设置和显式重建索引决定。

## 验证证据

- 合成 PDF/Markdown 导入专项回归：`5 passed`。
- 前端 typecheck、production build 和 `frontend_route_preflight.py`：通过。
- 前端契约回归：`14 passed`。
- 全量 Python 合成回归：`111 passed`。
- 回归使用全新合成 SQLite、合成文件内容和项目范围临时目录，没有触碰真实简历、真实个人文档或日常数据库。

## 面试讲解要点

1. 为什么 PDF 和 Markdown 不直接存文件路径？因为路径不可移植，也会把运行环境暴露给检索层；系统只持久化经过校验的正文和版本快照。
2. 为什么 Markdown 不经过 LLM 解析？Markdown 本身已经是可检索文本，直接保留原文更稳定、更便于引用和复现。
3. 为什么扫描 PDF 暂不支持？当前依赖 `pypdf` 的文本层提取；OCR 会引入额外模型、耗时和准确率验证，应作为独立阶段。
4. 为什么导入后仍要重建索引？导入只负责建立当前 Embedding 下的 chunks；切换模型后向量空间可能变化，必须显式重建，不能混用旧向量。

