"""tests/input/test_file_loader.py — 파일 로더 TDD (tmp_path 픽스처)

테스트 전략:
- pytest 내장 tmp_path 픽스처로 임시 파일 생성 → 테스트 후 자동 삭제
- 지원 확장자: .py .html .htm .js .css .ts .txt
- 미지원 확장자 (.xlsx 등) → ValueError("지원하지 않는")
- 존재하지 않는 경로 → FileNotFoundError
- load_zip: ZIP 파일에서 소스 파일만 추출, 불필요 경로/파일 필터링
"""
import io
import zipfile

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


def _make_zip(files: dict[str, str]) -> bytes:
    """파일명 → 내용 딕셔너리로 ZIP bytes 생성."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


class TestLoadZip:
    def test_keeps_source_files(self):
        """소스 파일(.py, .html, .js 등)은 결과에 포함된다."""
        from input.file_loader import load_zip
        data = _make_zip({
            "src/app.py": "print('hello')",
            "src/index.html": "<html></html>",
        })
        result = load_zip(data)
        assert "print('hello')" in result
        assert "<html></html>" in result

    def test_filters_node_modules(self):
        """node_modules/ 경로는 제거된다."""
        from input.file_loader import load_zip
        data = _make_zip({
            "src/app.py": "real code",
            "node_modules/lodash/index.js": "library code",
        })
        result = load_zip(data)
        assert "real code" in result
        assert "library code" not in result

    def test_filters_git_directory(self):
        """.git/ 경로는 제거된다."""
        from input.file_loader import load_zip
        data = _make_zip({
            "src/app.py": "real code",
            ".git/config": "git config",
        })
        result = load_zip(data)
        assert "git config" not in result

    def test_filters_build_directories(self):
        """dist/, build/, .next/, __pycache__/ 경로는 제거된다."""
        from input.file_loader import load_zip
        data = _make_zip({
            "src/app.py": "real code",
            "dist/bundle.js": "minified",
            "build/index.html": "built",
            ".next/server.js": "next",
            "__pycache__/app.cpython.pyc": "bytecode",
        })
        result = load_zip(data)
        assert "real code" in result
        assert "minified" not in result
        assert "built" not in result
        assert "next" not in result
        assert "bytecode" not in result

    def test_filters_minified_files(self):
        """*.min.js, *.min.css 파일은 제거된다."""
        from input.file_loader import load_zip
        data = _make_zip({
            "src/app.js": "real js",
            "static/vendor.min.js": "minified js",
            "static/style.min.css": "minified css",
        })
        result = load_zip(data)
        assert "real js" in result
        assert "minified js" not in result
        assert "minified css" not in result

    def test_filters_large_files(self):
        """단일 파일이 크기 제한(100KB)을 초과하면 제거된다."""
        from input.file_loader import load_zip
        big_content = "x" * (101 * 1024)
        data = _make_zip({
            "src/app.py": "small file",
            "src/big.js": big_content,
        })
        result = load_zip(data)
        assert "small file" in result
        assert big_content[:100] not in result

    def test_filters_unsupported_extensions(self):
        """지원하지 않는 확장자(.png, .lock, .json 등)는 제거된다."""
        from input.file_loader import load_zip
        data = _make_zip({
            "src/app.py": "python code",
            "logo.png": b"\x89PNG".decode("latin-1"),
            "package-lock.json": "{}",
            "yarn.lock": "lockfile",
        })
        result = load_zip(data)
        assert "python code" in result
        assert "lockfile" not in result

    def test_includes_file_path_header(self):
        """결과에 각 파일 경로가 헤더로 포함된다."""
        from input.file_loader import load_zip
        data = _make_zip({"src/app.py": "print('hello')"})
        result = load_zip(data)
        assert "src/app.py" in result

    def test_empty_zip_returns_empty_string(self):
        """유효 파일이 없는 ZIP은 빈 문자열을 반환한다."""
        from input.file_loader import load_zip
        data = _make_zip({"node_modules/x.js": "ignored"})
        result = load_zip(data)
        assert result == ""

    def test_invalid_zip_raises(self):
        """유효하지 않은 ZIP 데이터는 ValueError를 발생시킨다."""
        from input.file_loader import load_zip
        with pytest.raises(ValueError, match="유효하지 않은 ZIP"):
            load_zip(b"not a zip file")
