"""src/graph/reference_parser.py — 조문 내 참조 관계 추출기"""
import re
from typing import List, Tuple, Optional

# 조 번호 패턴 (예: 12조, 12조의2)
# '조'가 먼저 나오고 그 뒤에 '의2' 등이 붙는 한국 법령 특유의 구조 반영
JO_PAT = r"(\d+조(?:의\d+)?)"

# 1. 일반적인 "제N조" 패턴
RE_INTERNAL = re.compile(rf"제{JO_PAT}")

# 2. "「법령명」 제N조" 패턴
RE_CROSS = re.compile(rf"「([^」]+)」\s*제{JO_PAT}")

# 3. "동법 제N조" 패턴
RE_SAME_LAW = re.compile(rf"동법\s*제{JO_PAT}")

class ReferenceParser:
    @staticmethod
    def extract_references(content: str, current_law: str) -> List[Tuple[str, str]]:
        """텍스트에서 (법령명, 조번호) 튜플 리스트를 추출한다."""
        refs = []
        
        # 1. 타법 참조 추출: 「주택법」 제49조
        for match in RE_CROSS.finditer(content):
            law_name = match.group(1).strip()
            art_num = f"제{match.group(2)}" # match.group(2)에 이미 '조'가 포함됨
            refs.append((law_name, art_num))
            
        # 2. 동법 참조 추출: 동법 제12조
        for match in RE_SAME_LAW.finditer(content):
            art_num = f"제{match.group(1)}"
            refs.append((current_law, art_num))
            
        # 3. 내부 참조 추출: 제12조
        for match in RE_INTERNAL.finditer(content):
            start = match.start()
            prefix = content[max(0, start-20):start]
            
            # 타법/동법 중복 제외 로직
            if "「" in prefix and "」" in prefix and prefix.rfind("「") < prefix.rfind("」"):
                 continue
            if "동법" in prefix[-5:]:
                 continue
                 
            art_num = f"제{match.group(1)}"
            refs.append((current_law, art_num))
            
        return list(dict.fromkeys(refs))
