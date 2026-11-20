from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree

from pypdf import PdfReader


class FileExtractionError(Exception):
    pass


def extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages).strip()
        except Exception as exc:
            raise FileExtractionError("PDF文本读取失败，请确认文件没有损坏") from exc
    if suffix == ".docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            return "\n".join(node.text or "" for node in root.iter() if node.tag.endswith("}t")).strip()
        except Exception as exc:
            raise FileExtractionError("Word文档读取失败，请确认文件是标准 .docx 格式") from exc
    if suffix in {".txt", ".csv"}:
        return content.decode("utf-8-sig", errors="replace").strip()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        raise FileExtractionError("当前环境未安装图片 OCR 引擎。请先上传 PDF 或 Word，图片阅卷将在配置 OCR 后启用。")
    raise FileExtractionError("仅支持 PDF、Word、TXT 或图片文件")
