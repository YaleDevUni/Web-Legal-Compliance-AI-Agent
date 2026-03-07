"""tests/input/test_file_loader.py — 파일 로더 TDD (tmp_path 픽스처)

테스트 전략:
- pytest 내장 tmp_path 픽스처로 임시 파일 생성 → 테스트 후 자동 삭제
- 지원 확장자: .py .html .htm .js .css .ts .txt
- 미지원 확장자 (.xlsx 등) → ValueError("지원하지 않는")
- 존재하지 않는 경로 → FileNotFoundError
"""
import pytest


class TestFileLoader:
    def test_load_python_file(self, tmp_path):
        """.py 파일을 UTF-8로 읽어 문자열 그대로 반환"""
        from input.file_loader import load_file
        f = tmp_path / "app.py"
        f.write_text("print('hello')", encoding="utf-8")
        result = load_file(str(f))
        assert result == "print('hello')"

    def test_load_html_file(self, tmp_path):
        """.html 파일 로드 — 한글 포함 텍스트 반환 확인"""
        from input.file_loader import load_file
        f = tmp_path / "index.html"
        f.write_text("<html><body>개인정보처리방침</body></html>", encoding="utf-8")
        result = load_file(str(f))
        assert "개인정보처리방침" in result

    def test_load_js_file(self, tmp_path):
        """.js 파일 로드"""
        from input.file_loader import load_file
        f = tmp_path / "main.js"
        f.write_text("const a = 1;", encoding="utf-8")
        assert load_file(str(f)) == "const a = 1;"

    def test_load_css_file(self, tmp_path):
        """.css 파일 로드"""
        from input.file_loader import load_file
        f = tmp_path / "style.css"
        f.write_text("body { color: red; }", encoding="utf-8")
        assert load_file(str(f)) == "body { color: red; }"

    def test_nonexistent_path_raises(self):
        """존재하지 않는 경로 → FileNotFoundError 발생"""
        from input.file_loader import load_file
        with pytest.raises(FileNotFoundError):
            load_file("/nonexistent/path/file.py")

    def test_unsupported_extension_raises(self, tmp_path):
        """미지원 확장자 (.xlsx) → ValueError("지원하지 않는") 발생"""
        from input.file_loader import load_file
        f = tmp_path / "data.xlsx"
        f.write_bytes(b"binary")
        with pytest.raises(ValueError, match="지원하지 않는"):
            load_file(str(f))
