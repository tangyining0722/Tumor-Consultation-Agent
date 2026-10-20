import streamlit as st
from medicouncil.workflow import run_consultation
from medicouncil.reader import extract_pdf_text
from medicouncil.reading_workflow import read_document
from medicouncil.store import save_consultation

st.set_page_config(page_title="MediCouncil 第一代", page_icon="🩺", layout="wide")
st.title("MediCouncil · 第一代")
st.caption("通用医疗协同决策教育原型｜DeepSeek + 豆包｜PubMed｜长文献分块")
st.warning("仅用于教学、研究和模拟病例。非医疗器械，不可替代医生。出现急症症状请及时线下就医。请勿上传含可识别身份信息的真实患者资料。")

tab1,tab2=st.tabs(["对话式病例会诊", "文献阅读与双模型比对"])
with tab1:
    st.subheader("您有什么身体不舒服的吗？")
    case=st.text_area("请用自己的话描述症状、病程和已知检查结果",height=170,placeholder="例如：最近两周反复腹痛，饭后更明显……")
    query=st.text_input("PubMed 英文检索词（可选；例如 abdominal pain differential diagnosis）")
    use_pubmed=st.checkbox("检索 PubMed 摘要",value=True)
    if st.button("开始辅助分析",type="primary"):
        if not case.strip(): st.error("请先输入病例描述。")
        else:
            with st.spinner("正在分析，可能需要几十秒……"):
                try:
                    result=run_consultation(case,query,use_pubmed)
                    st.session_state["result"]=result
                    st.session_state["case_id"]=save_consultation(case,result)
                except Exception as e: st.error(f"流程执行失败：{e}")
    if "result" in st.session_state:
        r=st.session_state["result"]
        st.info("会诊路径："+r.route+"；记录编号："+str(st.session_state.get("case_id","-")))
        for warning in r.warnings: st.warning(warning)
        st.subheader("建议追问")
        for q in r.questions: st.write("• "+q)
        st.subheader("双模型独立分析")
        cols=st.columns(2)
        for i, provider in enumerate(["deepseek","doubao"]):
            with cols[i]:
                st.markdown("**"+provider+"**")
                match=next((x for x in r.opinions if x.provider==provider),None)
                if match: st.error(match.error) if match.error else st.write(match.content)
                else: st.caption("未调用")
        st.subheader("PubMed 检索结果（摘要，不等于全文）")
        for item in r.evidence:
            st.markdown(f"[{item.title}]({item.url}) · PMID {item.pmid}")
            st.caption(item.abstract[:650] or "该记录没有可用摘要")
        st.subheader("证据核查")
        st.write(r.evidence_review)
        st.subheader("分歧审查")
        st.write(r.disagreement_review)
        st.download_button("下载辅助报告 TXT",r.report,file_name="medicouncil_report.txt",mime="text/plain")
with tab2:
    st.write("上传不含患者身份信息、允许使用的可提取文本 PDF。扫描件需另行 OCR。")
    pdf=st.file_uploader("上传医学文献 PDF",type=["pdf"])
    max_chunks=st.slider("每个模型最多读取多少片段",1,20,6)
    if pdf is not None:
        if pdf.size > 12*1024*1024:
            st.error("演示版限制 PDF 不超过 12 MB")
        else:
            try:
                text,warnings=extract_pdf_text(pdf.getvalue())
                for warning in warnings: st.warning(warning)
                st.caption(f"提取文字 {len(text)} 字符。注意：长文处理需要逐块阅读，可能产生 API 费用。")
                if text and st.button("DeepSeek + 豆包逐块阅读"):
                    with st.spinner("逐块阅读并保存进度中……"):
                        output=read_document(text,["deepseek","doubao"],max_chunks=max_chunks)
                        st.session_state["reading_output"]=output
            except Exception as e: st.error(str(e))
    if "reading_output" in st.session_state:
        for provider,data in st.session_state["reading_output"].items():
            with st.expander(provider+"（已处理 "+str(data["chunks_processed"])+" 段）",expanded=False):
                st.warning(data["warning"])
                for summary in data["summaries"]: st.write(summary)
