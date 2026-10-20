from openai import OpenAI
from .config import settings

SYSTEM = """你是医学教育与临床会诊准备辅助系统中的AI。不能替代医生诊断或处方。
只根据输入资料分析，区分事实、推测、未知；不可捏造检验结果、指南、PMID或引文。
遇到急症信号应提示及时线下急救/就医。所有建议均需临床人员复核。"""

class LLMClient:
    def __init__(self, provider: str):
        if provider == "deepseek":
            key, base, model = settings.deepseek_key, settings.deepseek_base, settings.deepseek_model
        elif provider == "doubao":
            key, base, model = settings.doubao_key, settings.doubao_base, settings.doubao_model
            if model == "YOUR_ARK_ENDPOINT_ID":
                raise ValueError("请先在 .env 中配置 DOUBAO_MODEL 为实际 Ark 推理接入点 ID")
        else:
            raise ValueError(f"未知模型: {provider}")
        if not key:
            raise ValueError(f"未配置 {provider} API Key")
        self.provider = provider
        self.model = model
        self.client = OpenAI(api_key=key, base_url=base, timeout=65.0, max_retries=1)

    def ask(self, prompt: str, system: str = SYSTEM, max_tokens: int = 1300) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
            temperature=0.2, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or "(模型未返回内容)"
