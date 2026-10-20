# MediCouncil 第一代（通用医疗协同决策教育原型）

> 本版本是最初的**通用医疗**方向，不是后续肿瘤 MDT 专用版。仅供教学/研究/虚构病例演示，不是经过临床验证的医疗产品。

## 已实现
- Streamlit 对话式症状输入；无需上传文献才能启动
- 简单症状澄清问题、有限关键词紧急风险筛查、简单/协作/紧急路由
- DeepSeek 与豆包独立调用（兼容 OpenAI Python SDK）
- PubMed E-utilities 检索并抓取论文摘要及真实 PMID 链接
- 双模型观点比较；基于检索摘要的有限证据核查（非真实指南全文验证）
- PDF 可提取文字解析、分块、逐块模型阅读、SQLite 分块结果缓存/断点续读
- SQLite 保存会诊报告；TXT 报告下载

## 尚未实现/局限
- 不是临床分诊系统，关键词筛查漏报风险很高；未识别风险不代表安全
- 未接入中国指南库、医学网站的授权全文、临床知识图谱
- 未实现严格的多专业动态 Agent 会诊；当前为规则路由+双模型独立分析+证据审查的基础版
- 证据核验是 LLM 对提供摘要的审查，**不保证医学正确性或指南时效性**
- PDF 无 OCR；复杂表格/图片可能丢失；分块阅读有截断上限，不能声称已阅读整篇
- 不支持 DICOM/原始影像分析、用户权限、生产级加密、审计、医院集成
- 真实病例不得在未经授权和合规保障时提交给第三方模型服务

## 安装
推荐 Python 3.10 或更新版本。

```bash
cd MediCouncil_Gen1
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`，填写：
- `DEEPSEEK_API_KEY`：DeepSeek 的密钥
- `DOUBAO_API_KEY`：火山方舟密钥
- `DOUBAO_MODEL`：火山方舟的**实际推理接入点 ID**，不是随意填写模型名称
- `NCBI_EMAIL`：可选，NCBI 推荐提供真实邮箱

请勿把 `.env` 上传到公开代码仓库。

## 运行
```bash
streamlit run app.py
```
浏览器通常访问 http://localhost:8501 。

## 测试
```bash
pytest -q
```

## 工作流
输入病例 → 关键词安全检查 → 简单/协作路由 → DeepSeek 独立分析 + 豆包独立分析 → PubMed 摘要检索（可选）→ 证据审查 → 分歧审查 → 报告保存。

## 关于模型访问
SDK 中使用 `from openai import OpenAI` 只是使用兼容的客户端库，不代表请求会发送给 OpenAI；实际目标由 `base_url` 指定。模型 API 的网络可达性取决于供应商、地区与网络环境。

## 安全
本原型可能向第三方模型发送你输入的文本；请仅使用虚构或合规脱敏的教学材料。急症症状应立即联系当地急救服务。不能依据原型结果自行诊断、停药或更改治疗。
