from .schemas import CaseInfo

# 仅用于教育演示的高风险关键词筛查；不是临床分诊或诊断工具。
RED_FLAGS = {
    "胸痛伴呼吸困难": ["胸痛", "呼吸困难"],
    "严重呼吸困难": ["喘不过气", "呼吸困难严重", "无法呼吸"],
    "意识障碍": ["昏迷", "意识不清", "叫不醒"],
    "严重出血": ["大量出血", "止不住血"],
    "卒中相关表现": ["口角歪斜", "单侧肢体无力", "突然说话不清"],
}

def detect_red_flags(text: str) -> list[str]:
    found = []
    for label, keywords in RED_FLAGS.items():
        if label == "胸痛伴呼吸困难":
            if all(k in text for k in keywords):
                found.append(label)
        elif any(k in text for k in keywords):
            found.append(label)
    return found

def extract_case(text: str) -> CaseInfo:
    text = text.strip()
    if not text:
        raise ValueError("请输入症状或病情描述")
    flags = detect_red_flags(text)
    missing = ["症状开始时间与变化", "严重程度", "既往疾病与用药", "年龄及相关背景"]
    return CaseInfo(narrative=text, urgent_signs=flags, missing=missing)

def choose_route(case: CaseInfo) -> str:
    if case.urgent_signs:
        return "urgent"
    if len(case.narrative) > 180 or any(x in case.narrative for x in ("多种", "长期", "反复", "住院", "检查结果", "慢性病")):
        return "collaborative"
    return "simple"

def clarifying_questions(case: CaseInfo) -> list[str]:
    return [
        "症状从什么时候开始？是否突然出现或持续加重？",
        "具体部位、严重程度和伴随症状是什么？",
        "是否有既往疾病、正在服用的药物或过敏史？",
        "是否已经就医或做过检查？有哪些已知结果？",
    ]
