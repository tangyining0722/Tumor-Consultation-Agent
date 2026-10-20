import streamlit as st
import os
import json
import requests
import xml.etree.ElementTree as ET
import uuid
import re
import sqlite3
import base64
from datetime import datetime
from openai import OpenAI

# ================= 页面配置 =================
st.set_page_config(page_title="肿瘤 MDT 辅助决策系统", layout="wide")
st.title("肿瘤 MDT 辅助决策系统 (Clinical Agent)")
st.caption("面向临床医生的循证医学辅助工具。支持病历结构化、双模型对抗、实时文献核查。")

# ================= 数据库初始化 (记忆功能) =================
DB_FILE = "tumor_memory.db"
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS consultations
                 (id TEXT PRIMARY KEY, timestamp TEXT, initial_symptoms TEXT, final_report TEXT)''')
    conn.commit()
    conn.close()
init_db()

def save_to_memory(initial_symptoms, final_report):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO consultations VALUES (?, ?, ?, ?)",
                  (str(uuid.uuid4()), datetime.now().strftime("%Y-%m-%d %H:%M"), initial_symptoms, final_report))
        conn.commit()
        conn.close()
    except: pass

def get_history():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT timestamp, initial_symptoms FROM consultations ORDER BY timestamp DESC LIMIT 5")
        rows = c.fetchall()
        conn.close()
        return rows
    except: return []

# ================= 状态管理初始化 =================
if "messages" not in st.session_state: st.session_state.messages = []
if "report" not in st.session_state: st.session_state.report = ""
if "questions" not in st.session_state: st.session_state.questions = []
if "round" not in st.session_state: st.session_state.round = 0
if "pubmed_done" not in st.session_state: st.session_state.pubmed_done = False
if "asked_questions" not in st.session_state: st.session_state.asked_questions = []
if "model_info" not in st.session_state: st.session_state.model_info = ""
if "references_list" not in st.session_state: st.session_state.references_list = []
if "image_analysis" not in st.session_state: st.session_state.image_analysis = ""

def get_api_key(key_name):
    key = os.environ.get(key_name)
    if not key:
        try: key = st.secrets[key_name]
        except: pass
    return key

# ================= 底层 API 调用 =================
def call_llm(model_name, system_prompt, user_prompt, json_mode=False):
    try:
        if model_name == "deepseek":
            api_key = get_api_key("DEEPSEEK_API_KEY")
            if not api_key: return ""
            base_url = "https://api.deepseek.com/v1"
            model_id = "deepseek-chat"
        elif model_name == "doubao":
            api_key = get_api_key("DOUBAO_API_KEY")
            if not api_key: return ""
            base_url = "https://ark.cn-beijing.volces.com/api/v3"
            model_id = "ep-2024061112345-abcde" # ⚠️ 请替换为你真实的豆包 EP ID
        else: return ""

        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.2,
            response_format={"type": "json_object"} if json_mode else None
        )
        return response.choices[0].message.content
    except Exception: return ""

# ================= 【核心修改 1】面向医生的专业追问逻辑 =================
def generate_report_and_questions(messages_history, route_info, current_round):
    role_a = route_info["role_a_model"]
    role_b = route_info["role_b_model"]
    context = "\n".join([f"{'临床医生' if m['role']=='user' else 'AI辅助'}：{m['content']}" for m in messages_history])
    asked_questions_text = "、".join(st.session_state.asked_questions) if st.session_state.asked_questions else "无"

    ask_instructions = ""
    if current_round < 3:
        ask_instructions = f"""
        4. 追问机制：以主治医师的身份，向临床医生索要【缺失的关键临床参数】。提出最多3个追问。
        5. 绝对禁止重复提问：{asked_questions_text}
        6. 追问应聚焦于：TNM分期、ECOG评分、病理/免疫组化结果、基因突变状态、是否有肿瘤急症（如上腔静脉综合征、脊髓压迫）。
        7. 【极其重要】问题必须放在 JSON 的 `questions` 数组里，提供下拉或多选选项（如：ECOG评分 0/1/2/3/4），方便医生快速点选。
        """
    else:
        ask_instructions = "4. 已达到最大追问轮次，停止追问，直接输出基于现有数据的最终 MDT 报告。questions 数组必须为空 []。"

    # 重新定义主诊医生的 Prompt
    doctor_prompt = f"""
    你是一位顶级三甲医院的肿瘤内科主任。现在一位临床医生向你提交了患者的病历摘要：
    {context}

    请基于 CSCO / NCCN 最新指南，输出一份专业的 MDT 辅助决策报告（语言高度精炼、使用标准医学术语）：
    ## 一、 临床特征摘要
    （提炼患者的病理分型、分期、核心体征）
    
    ## 二、 诊疗缺口评估（重点！）
    （严格评估：目前缺少哪些数据导致无法制定下一步方案？如：缺乏PD-L1表达、缺乏脑部MRI排查转移等）
    
    ## 三、 下一步临床检查/检验建议（重点！）
    （明确建议医生开具哪些具体检查，如：建议行PET-CT、建议行NGS大Panel检测等）
    
    ## 四、 初步干预方向
    （在现有数据下，建议的干预方向，如：建议MDT讨论手术指征、建议先进行新辅助化疗等）

    {ask_instructions}
    请严格只输出标准 JSON 格式：{{"report": "...", "questions": [...]}}
    """
    doctor_response = call_llm(role_a, "你是一位肿瘤科主任。", doctor_prompt, json_mode=True)
    try:
        doctor_data = json.loads(doctor_response.strip().replace("```json", "").replace("```", ""))
    except: doctor_data = {}

    # 质控专家（双重审查）
    quality_prompt = f"""
    你是一位严苛的肿瘤 MDT 质控专家。请审查上述主诊报告。
    病历：{context}
    初诊报告：{doctor_data.get('report', '')}

    审查任务：
    1. 检查是否有违反 CSCO/NCCN 指南的表述。
    2. 检查是否遗漏了肿瘤急症排查。
    3. 输出最终修正版报告，保持（临床特征摘要、诊疗缺口、检查建议、初步干预方向）结构。

    {ask_instructions}
    请严格只输出标准 JSON 格式：{{"report": "...", "questions": [...]}}
    """
    quality_response = call_llm(role_b, "你是一位质控专家。", quality_prompt, json_mode=True)
    try:
        final_data = json.loads(quality_response.strip().replace("```json", "").replace("```", ""))
    except: final_data = doctor_data
        
    raw_questions = final_data.get("questions", [])
    cleaned_questions = []
    for idx, q in enumerate(raw_questions):
        if not isinstance(q, dict): continue
        q_text = q.get("text", f"缺失参数 {idx + 1}")
        if q_text in st.session_state.asked_questions: continue
        options = q.get("options", [])
        q_id = q.get("id") or f"q_{uuid.uuid4().hex[:8]}_{idx}"
        cleaned_questions.append({"id": q_id, "text": q_text, "options": options})
        st.session_state.asked_questions.append(q_text)

    return {"report": final_data.get("report", ""), "questions": cleaned_questions}

# ================= 【占位】路由与文献核查 (直接使用你原来的代码即可) =================
# evaluate_and_assign, verify_with_literature, search_pubmed, search_europepmc 保持你原来的代码不变
# 这里为了代码完整，我把之前的简易版放进来，你直接复制你原来有的就行
def evaluate_and_assign(messages_history):
    return {"complexity": "high", "role_a_model": "deepseek", "role_b_model": "doubao"}

def search_europepmc(query, max_results=3):
    try:
        safe_query = requests.utils.quote(query)
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={safe_query}&format=json&resultType=core&pageSize={max_results}"
        results = requests.get(url, timeout=10).json().get("resultList", {}).get("result", [])
        return [f"【Europe PMC】{item.get('title')}\n摘要：{item.get('abstractText', '')[:600]}..." for item in results if item.get('abstractText')]
    except: return []

def search_pubmed(query, max_results=3):
    try:
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmode=json&retmax={max_results}"
        id_list = requests.get(search_url, timeout=10).json().get("esearchresult", {}).get("idlist", [])
        if not id_list: return []
        fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={','.join(id_list)}&retmode=xml"
        root = ET.fromstring(requests.get(fetch_url, timeout=15).content)
        return [f"【PubMed】{a.find('.//ArticleTitle').text}\n摘要：{' '.join([t.text for t in a.findall('.//AbstractText') if t.text])[:600]}..." for a in root.findall(".//PubmedArticle")]
    except: return []

def verify_with_literature(report_content, role_b):
    english_terms = re.findall(r'[\(（]([A-Za-z\s\-]+)[\)）]', report_content)
    search_query = " AND ".join(english_terms[:2]) if english_terms else ""
    if not search_query: return report_content, ["未能提取到检索词。"]
    
    evidence_list = search_europepmc(search_query) + search_pubmed(search_query)
    if not evidence_list: return report_content, [f"未检索到相关文献。"]
    
    return report_content, evidence_list # 简化版，确保你运行通畅

# ================= 界面交互流程 =================
with st.sidebar:
    st.header("病历数据录入")
    if st.button("🔄 开始新病例"):
        st.session_state.messages = []
        st.session_state.report = ""
        st.session_state.questions = []
        st.session_state.round = 0
        st.session_state.pubmed_done = False
        st.session_state.asked_questions = []
        st.session_state.image_analysis = ""
        st.rerun()

    st.markdown("---")
    st.subheader("🧠 历史记录")
    for h in get_history():
        st.caption(f"🕒 {h[0]} | {h[1][:15]}...")

if not st.session_state.messages:
    st.info("请粘贴患者的电子病历（现病史、影像、病理、基因检测结果等）")
    initial_symptom = st.text_area("病历文本：", height=200, key="initial_input")
    
    if st.button("生成 MDT 辅助决策", type="primary"):
        combined_symptoms = initial_symptom
        st.session_state.messages.append({"role": "user", "content": combined_symptoms})
        with st.spinner("AI 正在调度双模型进行 MDT 推理..."):
            route_info = evaluate_and_assign(st.session_state.messages)
            result = generate_report_and_questions(st.session_state.messages, route_info, 0)
            st.session_state.report = result.get("report", "")
            st.session_state.questions = result.get("questions", [])
            st.session_state.messages.append({"role": "assistant", "content": json.dumps(result, ensure_ascii=False)})
            save_to_memory(combined_symptoms, st.session_state.report)
            st.rerun()

if st.session_state.report:
    st.markdown("### 📋 MDT 辅助决策报告")
    st.markdown(st.session_state.report)
    st.markdown("---")

# 【核心修改 2】将追问 UI 改成医生视角的“待补充参数”
if st.session_state.questions and st.session_state.round < 3:
    st.subheader(f"⚠️ 缺少关键临床参数，请主治医师补充（第 {st.session_state.round + 1} 轮）")
    with st.form(key=f"follow_up_form_{st.session_state.round}"):
        answers = {}
        for q in st.session_state.questions:
            q_text = q.get("text", "缺失参数")
            options = q.get("options", [])
            q_key = f"key_{q.get('id')}_{st.session_state.round}"
            if options:
                answers[q_text] = st.multiselect(q_text, options, key=q_key)
            else:
                answers[q_text] = st.text_input(q_text, key=q_key)
                
        submit_answers = st.form_submit_button("提交补充数据")
        
        if submit_answers:
            formatted_answers = "\n".join([f"【{k}】：{v}" for k, v in answers.items() if v])
            if formatted_answers:
                st.session_state.messages.append({"role": "user", "content": f"补充临床数据：\n{formatted_answers}"})
                st.session_state.round += 1
                with st.spinner("正在更新 MDT 决策方案..."):
                    route_info = evaluate_and_assign(st.session_state.messages)
                    result = generate_report_and_questions(st.session_state.messages, route_info, st.session_state.round)
                    st.session_state.report = result.get("report", "")
                    st.session_state.questions = result.get("questions", [])
                    st.session_state.messages.append({"role": "assistant", "content": json.dumps(result, ensure_ascii=False)})
                    st.rerun()
            else:
                st.warning("请至少填写一项参数。")

# （后续文献核查与下载逻辑保持不变，按你原版保留即可）