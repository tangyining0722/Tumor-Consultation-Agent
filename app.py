import streamlit as st
import os
import json
import requests
import xml.etree.ElementTree as ET
import uuid
import re
import sqlite3
import base64
import time
from datetime import datetime
from openai import OpenAI

# ================= 页面配置 =================
st.set_page_config(page_title="肿瘤 MDT 辅助决策系统", layout="wide")
st.title("肿瘤 MDT 辅助决策系统 (Clinical Agent)")
st.caption("面向临床医生的循证医学辅助工具。支持影像双通道分析、双模型对抗、实时文献核查。")

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
if "image_analysis" not in st.session_state: st.session_state.image_analysis = ""
if "references_list" not in st.session_state: st.session_state.references_list = []

def get_api_key(key_name):
    key = os.environ.get(key_name)
    if not key:
        try: key = st.secrets[key_name]
        except: pass
    return key

# ================= 底层 API 调用 =================
def call_llm(model_name, system_prompt, user_prompt, json_mode=False, image_base64=None):
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
            model_id = "ep-2024061112345-abcde" # ⚠️ 请务必替换为你真实的豆包 EP ID
        else: return ""

        client = OpenAI(api_key=api_key, base_url=base_url)
        
        # 多模态请求
        if image_base64 and model_name == "doubao":
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]}
            ]
        else:
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        response = client.chat.completions.create(
            model=model_id, messages=messages, temperature=0.2,
            response_format={"type": "json_object"} if json_mode else None
        )
        return response.choices[0].message.content
    except Exception: return ""

# ================= 影像分析双通道 =================
def analyze_image(image_bytes):
    """双通道影像分析：通道A调用本地/云端专业API，通道B用多模态大模型兜底"""
    base64_img = base64.b64encode(image_bytes).decode('utf-8')
    
    # 【通道 A】：预留你同学包（TumorImagingAgent）的 API 接口
    IMAGING_API_URL = os.environ.get("IMAGING_API_URL") 
    if IMAGING_API_URL:
        try:
            st.toast("正在调用本地专业影像分割模型...", icon="🧠")
            res = requests.post(f"{IMAGING_API_URL}/analyze", json={"image": base64_img, "tumor_type": "general"}, timeout=120)
            return res.json().get("report", "影像 API 返回为空")
        except Exception as e:
            st.warning(f"专业影像API调用失败: {e}，将切换至大模型读图。")

    # 【通道 B】：使用豆包多模态大模型直接读图（确保在 Render 能跑通）
    st.toast("正在使用多模态大模型提取影像特征...", icon="👁️")
    prompt = """
    你是一位顶级影像科/病理科专家。请详细阅读这张医学图像，提取以下关键信息：
    1. 图像类型（如CT/X光/病理切片）；
    2. 主要病灶位置与大小（如最大长径、体积）；
    3. 形态特征（如边界、密度、毛刺征等）；
    4. 影像学初步印象（如高度怀疑恶性）。
    请用专业术语输出纯文本描述。
    """
    res = call_llm("doubao", "你是专业的医学影像分析专家。", prompt, json_mode=False, image_base64=base64_img)
    if not res:
        return "【影像学分析】未能识别图像内容（请检查豆包视觉模型EP ID是否配置正确）。"
    
    return f"【大模型影像特征提取】\n{res}"

# ================= 文献检索模块 =================
def search_europepmc(query, max_results=3):
    try:
        safe_query = requests.utils.quote(query)
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={safe_query}&format=json&resultType=core&pageSize={max_results}"
        res = requests.get(url, timeout=10)
        results = res.json().get("resultList", {}).get("result", [])
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

# ================= 核心逻辑：双模型对抗与 MDT 追问 =================
def generate_report_and_questions(messages_history, current_round):
    context = "\n".join([f"{'医生' if m['role']=='user' else 'AI'}：{m['content']}" for m in messages_history])
    asked_questions_text = "、".join(st.session_state.asked_questions) if st.session_state.asked_questions else "无"

    ask_instructions = ""
    if current_round < 3:
        ask_instructions = f"""
        4. 追问机制：向临床医生索要【缺失的关键临床参数】。最多3个。
        5. 绝对禁止重复提问：{asked_questions_text}
        6. 追问应聚焦于：TNM分期、ECOG评分、病理/基因结果、是否有肿瘤急症。
        7. 【极其重要】问题必须放在 JSON 的 `questions` 数组里，提供多选选项。
        """
    else:
        ask_instructions = "4. 达到最大追问轮次，停止追问，questions 数组为空 []。"

    # 主诊医生
    doctor_prompt = f"""
    你是一位顶级肿瘤内科主任。基于以下病历及影像特征：
    {context}

    请输出 MDT 辅助决策报告（高度精炼）：
    ## 一、 临床特征摘要
    ## 二、 诊疗缺口评估
    ## 三、 下一步临床检查建议
    ## 四、 初步干预方向

    {ask_instructions}
    只输出 JSON 格式：{{"report": "...", "questions": [...]}}
    """
    doc_res = call_llm("deepseek", "你是一位肿瘤科主任。", doctor_prompt, json_mode=True)
    try: doc_data = json.loads(doc_res.strip().replace("```json", "").replace("```", ""))
    except: doc_data = {}

    # 质控专家（审查）
    quality_prompt = f"""
    你是一位严苛的肿瘤 MDT 质控专家。审查以下报告：
    {doc_data.get('report', '')}
    检查是否违反指南、遗漏急症排查，并输出修正后的最终报告。
    {ask_instructions}
    只输出 JSON 格式：{{"report": "...", "questions": [...]}}
    """
    qual_res = call_llm("doubao", "你是一位质控专家。", quality_prompt, json_mode=True)
    try: final_data = json.loads(qual_res.strip().replace("```json", "").replace("```", ""))
    except: final_data = doc_data
        
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

def verify_with_literature(report_content):
    english_terms = re.findall(r'[\(（]([A-Za-z\s\-]+)[\)）]', report_content)
    search_query = " AND ".join(english_terms[:2]) if english_terms else "Lung Cancer"
    
    st.toast(f"正在同时检索 Europe PMC 与 PubMed: {search_query}", icon="🔍")
    return search_europepmc(search_query) + search_pubmed(search_query)

# ================= 界面交互流程 =================
with st.sidebar:
    st.header("病历数据录入")
    uploaded_file = st.file_uploader("上传医学影像 (JPG/PNG)", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="已上传影像", use_column_width=True)
        if st.button("🔍 提取影像特征"):
            with st.spinner("正在分析影像..."):
                st.session_state.image_analysis = analyze_image(uploaded_file.getvalue())
                st.success("影像特征提取成功！已注入上下文。")

    if st.button("🔄 开始新病例"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    st.markdown("---")
    st.subheader("🧠 历史记录")
    for h in get_history(): st.caption(f"🕒 {h[0]} | {h[1][:15]}...")

if not st.session_state.messages:
    st.info("请粘贴患者的电子病历")
    initial_symptom = st.text_area("病历文本：", height=200)
    
    if st.button("生成 MDT 辅助决策", type="primary"):
        combined_symptoms = initial_symptom
        if st.session_state.image_analysis:
            combined_symptoms += f"\n\n{st.session_state.image_analysis}"

        st.session_state.messages.append({"role": "user", "content": combined_symptoms})
        with st.spinner("双模型对抗推理中..."):
            result = generate_report_and_questions(st.session_state.messages, 0)
            st.session_state.report = result.get("report", "")
            st.session_state.questions = result.get("questions", [])
            st.session_state.messages.append({"role": "assistant", "content": json.dumps(result, ensure_ascii=False)})
            save_to_memory(combined_symptoms, st.session_state.report)
            st.rerun()

if st.session_state.report:
    st.markdown("### 📋 MDT 辅助决策报告")
    st.markdown(st.session_state.report)
    st.markdown("---")

if st.session_state.questions and st.session_state.round < 3:
    st.subheader(f"⚠️ 缺少关键参数，请补充（第 {st.session_state.round + 1} 轮）")
    with st.form(key=f"form_{st.session_state.round}"):
        answers = {}
        for q in st.session_state.questions:
            q_text, options = q.get("text", ""), q.get("options", [])
            q_key = f"key_{q.get('id')}_{st.session_state.round}"
            answers[q_text] = st.multiselect(q_text, options, key=q_key) if options else st.text_input(q_text, key=q_key)
                
        if st.form_submit_button("提交补充数据"):
            formatted = "\n".join([f"【{k}】：{v}" for k, v in answers.items() if v])
            if formatted:
                st.session_state.messages.append({"role": "user", "content": f"补充数据：\n{formatted}"})
                st.session_state.round += 1
                with st.spinner("正在更新 MDT 方案..."):
                    result = generate_report_and_questions(st.session_state.messages, st.session_state.round)
                    st.session_state.report = result.get("report", "")
                    st.session_state.questions = result.get("questions", [])
                    st.session_state.messages.append({"role": "assistant", "content": json.dumps(result, ensure_ascii=False)})
                    st.rerun()

if (st.session_state.round >= 3 or not st.session_state.questions) and st.session_state.report and not st.session_state.pubmed_done:
    st.session_state.pubmed_done = True
    with st.spinner("正在调用双库进行循证核查..."):
        st.session_state.references_list = verify_with_literature(st.session_state.report)
        st.rerun()

if st.session_state.pubmed_done and "references_list" in st.session_state:
    st.markdown("### 📚 参考文献（实时循证核对）")
    for ref in st.session_state.references_list:
        st.markdown(f"- {ref}")