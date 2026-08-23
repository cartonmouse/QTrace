# Stage23：PDF 文档导入个人记忆

## 目标

让用户可以把项目说明、技术方案、复盘材料等文本型 PDF 导入 Personal Agent 的个人文档库。导入后的 PDF 不再是独立的“附件”，而是和手工输入的文本/Markdown 一样，经过文本抽取、分块、Embedding 和用户隔离检索。

本阶段复用已有的 PDF 解析能力，不引入 OCR、真实外部 Embedding 或向量数据库，也不把真实用户文件发送到外部服务。

## 领域模型

```text
PDF upload
  -> local validation
  -> text extraction
  -> PersonalDocument(source_type=pdf)
  -> DocumentChunk[]
  -> local deterministic embedding
```

- `DocumentImport` 负责文件名、大小、PDF 文件头和 `pypdf` 解析；
- `PersonalDocument` 负责用户拥有的长期资料及其来源类型；
- `DocumentChunk` 负责可检索的有序文档块；
- `EmbeddingProvider` 负责把文档块转换成可比较的向量；
- Agent 只读取检索证据，不直接写入导入结果。

## 关键接口

```text
POST /api/agent/documents/upload
  multipart/form-data: file=<pdf>
  -> PersonalDocumentView

GET /api/agent/documents
  -> 当前用户的文档元数据

GET /api/agent/documents/search?q=...
  -> Top-K 文档块和来源信息
```

简历上传和个人文档上传共同调用 `backend/document_import.py` 的 PDF 校验与文本抽取函数。简历继续使用较小的文本上限并保存到简历目录；个人 PDF 以 `source_type="pdf"` 写入个人文档表和文档块表。

## 数据流

```text
浏览器选择 PDF
  -> FormData 上传到后端
  -> 校验扩展名、路径、大小和 %PDF- 文件头
  -> pypdf 从内存字节流提取文本
  -> 没有文本层则返回“暂不支持 OCR”
  -> 文件名 stem 作为文档标题
  -> 清理、分块、生成本地确定性向量
  -> personal_documents + document_chunks 持久化
  -> Agent search_personal_documents 读取证据
```

## 错误边界

1. 文件名不能为空，不能包含路径，且必须以 `.pdf` 结尾；
2. 文件最大 20 MB；只检查 PDF 文件头不足以替代解析，损坏 PDF 仍会被拒绝；
3. 文本型 PDF 可以导入，扫描件或纯图片 PDF 因没有文本层而拒绝；本阶段不实现 OCR；
4. 文本抽取结果仍受个人文档 100,000 字上限约束，过长内容会被截断并带有明确标记；
5. 解析失败发生在持久化之前，不会产生空文档，也不会覆盖已有简历；
6. 所有文档列表、检索和 Agent 工具都按 `user_id` 隔离。

## 为什么抽出共享导入模块

如果简历和个人文档各自复制一份 `pypdf` 逻辑，文件大小限制、错误提示和文本清理会逐渐不一致。共享模块只负责“合法 PDF 字节 -> 文本”，上层模块分别决定保存位置、文本上限和业务来源类型。这是一个较窄的 seam：以后接入 OCR 或其他文档格式时，可以替换导入层，不需要改 Personal Agent 的检索协议。

## 当前取舍

- 先支持文本型 PDF，保证本地可运行和错误可解释；
- 不把 PDF 原始二进制写入个人文档库，当前只保存抽取后的文本和向量；
- 不在导入时调用 LLM，Embedding 仍是本地确定性 baseline；
- 不做文件版本、去重、删除和 OCR，避免在个人记忆主链稳定前扩展过多状态。

## 面试追问卡

### 为什么 PDF 导入后不直接把整个文件发给 LLM？

LLM 接口通常需要文本上下文，PDF 二进制本身不能直接作为可检索证据。先在后端抽取文本，再分块和检索，可以控制上下文长度，也能让 Agent 返回来源标题和文档块序号。

### 为什么简历解析和个人文档解析要共用模块？

两者对 PDF 的基础校验和文本提取相同，但业务保存位置和文本上限不同。共享底层导入模块可以避免重复逻辑，上层通过参数保留各自的业务边界。

### 扫描版 PDF 为什么导入失败？

当前使用 `pypdf` 提取文本层，没有 OCR。扫描版通常只有图片，没有可抽取的文字；系统明确返回失败，而不是创建一个空文档或假装检索成功。以后可以在导入层增加可选 OCR Provider。

### 导入 PDF 后什么时候调用 LLM？

导入阶段不调用 LLM。文档保存时只做本地文本处理和确定性向量；用户向 Personal Agent 提问时，Agent 先决定是否调用检索工具，检索到的证据再作为上下文交给回答模型。

### 如果未来换成真实 Embedding，需要改哪些地方？

只需实现 `EmbeddingProvider` 的真实适配器，并决定是否重新生成已有文档块向量；文档导入、分块、检索接口和 Agent 工具协议可以保持不变。

## 验证

- 共享 PDF 导入器可提取合成文本 PDF，并拒绝错误扩展名；
- PDF 上传后来源类型为 `pdf`，文档标题取文件名 stem；
- 导入文档可通过 `/api/agent/documents/search` 检索；
- 无文本层 PDF 返回可理解错误；
- 旧简历上传、个人文档隔离和 Agent 只读证据链路回归测试通过；
- 前端提供 PDF 导入入口，并明确提示扫描件暂不支持 OCR。
