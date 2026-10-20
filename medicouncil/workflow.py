from .schemas import ConsultationResult, ModelOpinion
from .triage import extract_case, choose_route, clarifying_questions
from .llm import LLMClient
from .pubmed import search_pubmed
from .config import settings


def run_consultation(user_input: str, pubmed_query: str = "", use_pubmed: bool = True, providers: list[str] | None = None) -> ConsultationResult:
    case=extract_case(user_input)
    route=choose_route(case)
    questions=clarifying_questions(case)
    warnings=["仅用于教育与研究演示，不提供诊断、处方或替代医生的会诊结论。", "高风险症状筛查仅为有限关键词规则，未命中不能排除急症。"]
    if case.urgent_signs:
        warnings.insert(0,"检测到可能的紧急风险信号，请及时联系当地急救服务或立即就医；系统不进行延误就医的诊断分析。")
        return ConsultationResult(case=case,route=route,questions=questions,opinions=[],evidence=[],evidence_review="紧急情形暂停自动会诊。",disagreement_review="未执行。",report="请立即寻求线下紧急医疗评估。",warnings=warnings)

    providers=providers if providers is not None else ["deepseek","doubao"]
    opinions=[]
    for provider in providers:
        try:
            client=LLMClient(provider)
            prompt=("病例原始描述："+case.narrative+"\n请独立分析：1已知事实 2需要追问的信息 3可供临床医生考虑的鉴别方向及不确定性 4需要及时就医的警示信号。不要做确定诊断，不要开药。")
            opinions.append(ModelOpinion(provider=provider,content=client.ask(prompt)))
        except Exception as e:
            opinions.append(ModelOpinion(provider=provider,content="",error=str(e)))
            warnings.append(f"{provider} 调用失败；结果不完整。")
    evidence=[]
    if use_pubmed and pubmed_query.strip():
        try:
            evidence=search_pubmed(pubmed_query,settings.ncbi_email)
        except Exception as e:
            warnings.append(f"PubMed 检索失败：{e}")
    elif use_pubmed:
        warnings.append("未填写英文 PubMed 检索词；未执行证据检索。")

    good=[x for x in opinions if not x.error]
    source_text="\n".join(f"PMID {x.pmid}: {x.title}\n摘要：{x.abstract[:1100]}" for x in evidence)
    evidence_review="未完成证据核验：没有可用的检索结果。"
    disagreement_review="无法完成双模型分歧审查。"
    report="已收集病例信息，等待模型分析。"
    if good:
        reviewer=next((x for x in good if x.provider=="doubao"),good[0])
        try:
            client=LLMClient(reviewer.provider)
            evidence_review=client.ask("请对以下AI观点进行证据核查。仅可引用提供的PubMed摘要；没有摘要或不足以支持时写'证据不足'。不允许声称已核验完整指南或全文。\n观点：\n"+"\n".join(x.content[:2200] for x in good)+"\n证据：\n"+(source_text or "未提供可核验来源"),max_tokens=1100)
        except Exception as e:
            warnings.append(f"证据复核模型失败：{e}")
        if len(good)>1:
            try:
                client=LLMClient("doubao" if any(x.provider=="doubao" for x in good) else good[0].provider)
                disagreement_review=client.ask("比较以下独立分析：列出共同点、实质分歧、缺少的临床事实、应进一步验证的问题。不得用多数投票代替证据。\n"+"\n".join(f"{x.provider}: {x.content[:2800]}" for x in good),max_tokens=950)
            except Exception as e:
                warnings.append(f"分歧审查失败：{e}")
        report=("【病例原始描述】\n"+case.narrative+"\n\n【待补信息】\n"+"；".join(case.missing)+"\n\n【模型意见（未经医生审核）】\n"+"\n".join(f"{x.provider}: {x.content}" for x in good)+"\n\n【证据核查】\n"+evidence_review+"\n\n【分歧审查】\n"+disagreement_review+"\n\n【结论边界】\n仅为会诊准备材料；不能据此自诊或调整治疗。")
    return ConsultationResult(case=case,route=route,questions=questions,opinions=opinions,evidence=evidence,evidence_review=evidence_review,disagreement_review=disagreement_review,report=report,warnings=warnings)
