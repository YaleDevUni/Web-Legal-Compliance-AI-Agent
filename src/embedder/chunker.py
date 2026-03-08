"""src/embedder/chunker.py — 법령 조항 및 판례 텍스트 청킹"""
from typing import List, Dict, Any, Union
from core.models import LawArticle, CaseArticle
import re

def chunk_article(article: LawArticle) -> List[Dict[str, Any]]:
    """LawArticle을 조/항/호 계층 기반으로 청킹한다."""
    base_metadata = {
        "article_id": article.article_id,
        "law_name": article.law_name,
        "article_number": article.article_number,
        "sha256": article.sha256,
        "url": str(article.url),
        "updated_at": article.updated_at.isoformat(),
        "full_content": article.content,
        "doc_type": "law",
    }
    
    lines = [line.strip() for line in article.content.split("\n") if line.strip()]
    chunks = []
    
    # 조문 제목 (첫 줄)
    title = lines[0] if lines else article.article_number
    
    current_para = "" # 항 (①, ② ...)
    current_subpara = "" # 호 (1., 2. ...)
    
    for line in lines:
        # 항 번호 추출 시도 (예: ①, ②, ③ ...)
        para_match = re.match(r"^([①-⑳])", line)
        if para_match:
            current_para = para_match.group(1)
            current_subpara = "" # 새 항이 시작되면 호 초기화
            
        # 호 번호 추출 시도 (예: 1., 2., 10. ...)
        subpara_match = re.match(r"^(\d+\.)", line)
        if subpara_match:
            current_subpara = subpara_match.group(1)

        metadata = base_metadata.copy()
        metadata.update({
            "paragraph": current_para,
            "subparagraph": current_subpara,
        })
        
        # 청크 텍스트 구성: "법령명 제N조 [제목]\n[현재라인]"
        chunk_text = f"{article.law_name} {article.article_number} {title}\n{line}"
        chunks.append({"text": chunk_text, "metadata": metadata})
        
    # 내용이 없는 경우 처리
    if not chunks:
        chunks.append({
            "text": f"{article.law_name} {article.article_number}\n{article.content}",
            "metadata": base_metadata
        })
        
    return chunks

def chunk_case(case: CaseArticle) -> List[Dict[str, Any]]:
    """CaseArticle을 판시사항/판결요지 단위로 청킹한다."""
    base_metadata = {
        "case_id": case.case_id,
        "case_number": case.case_number,
        "case_name": case.case_name,
        "court": case.court,
        "decision_date": case.decision_date.isoformat(),
        "sha256": case.sha256,
        "url": str(case.url),
        "doc_type": "case",
    }
    
    chunks = []
    
    # 1. 판시사항 청킹
    if case.ruling_summary:
        summary_lines = [l.strip() for l in case.ruling_summary.split("<br/>") if l.strip()]
        for line in summary_lines:
            # HTML 태그 제거 (간단히)
            clean_line = re.sub(r"<[^>]+>", "", line).strip()
            if not clean_line: continue
            
            chunks.append({
                "text": f"[{case.case_number} 판시사항]\n{clean_line}",
                "metadata": {**base_metadata, "section": "summary"}
            })
            
    # 2. 판결요지 청킹
    if case.ruling_text:
        text_lines = [l.strip() for l in case.ruling_text.split("<br/>") if l.strip()]
        for line in text_lines:
            clean_line = re.sub(r"<[^>]+>", "", line).strip()
            if not clean_line: continue
            
            chunks.append({
                "text": f"[{case.case_number} 판결요지]\n{clean_line}",
                "metadata": {**base_metadata, "section": "ruling"}
            })
            
    # 내용이 전혀 없는 경우
    if not chunks:
        chunks.append({
            "text": f"[{case.case_number}] {case.case_name}",
            "metadata": base_metadata
        })
        
    return chunks
