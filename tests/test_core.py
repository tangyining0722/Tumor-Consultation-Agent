from medicouncil.triage import extract_case,choose_route,detect_red_flags
from medicouncil.reader import chunk_text

def test_missing_image_does_not_block():
    case=extract_case("最近三天肚子痛，尚未检查")
    assert choose_route(case) in ("simple","collaborative")
    assert not case.urgent_signs

def test_urgent_route():
    case=extract_case("胸痛而且呼吸困难")
    assert choose_route(case)=="urgent"

def test_chunking():
    pieces=chunk_text("1234567890",size=5,overlap=2)
    assert pieces==["12345","45678","7890"]

def test_nonempty():
    try: extract_case("  ")
    except ValueError: pass
    else: assert False
