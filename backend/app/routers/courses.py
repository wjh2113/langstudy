"""Upload a worksheet and turn it into a course pack. Text extraction is local."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from .. import db, jobs
from ..coursepack import classify, save_course
from ..deps import bad, current_user
from ..languages import get_language
from ..materials import ExtractError, extract
from ..schemas import JobRef

router = APIRouter(prefix="/api", tags=["courses"])


@router.post("/courses", response_model=JobRef)
async def api_create_course(
    file: list[UploadFile] | None = File(None),
    text: str = Form(""),
    language: str = Form("en"),
    level: str = Form("intermediate"),
    user: dict = Depends(current_user),
):
    """Extract text locally, then one model call classifies it. Poll /api/jobs/{jobId}."""
    try:
        get_language(language)
    except ValueError as e:
        bad(e)
    # 一次可以选多个课件，文字拼在一起再归类。
    uploads = file if isinstance(file, list) else []
    chunks: list[str] = []
    names: list[str] = []
    for item in uploads:
        if item is None or not item.filename:
            continue
        data = await item.read()
        if not data:
            continue
        source_name = Path(item.filename).name
        try:
            chunks.append(f"--- {source_name} ---\n{extract(source_name, data)}")
        except ExtractError as e:
            bad(f"{source_name}：{e}" if len(uploads) > 1 else e)
        names.append(source_name)
    source = "\n\n".join(chunks).strip()
    source_name = "、".join(names)[:120]
    if text.strip():
        pasted = text.strip()[:40000]
        source = f"{source}\n\n{pasted}".strip() if source else pasted
        source_name = source_name or "粘贴的文字"
    if len(source) > 40000:
        source = source[:40000]
    if len(source) < 40:
        bad("请上传 PDF、PPTX、DOCX，或粘贴一段课件文字")

    def work():
        packed = classify(source)
        return save_course(user["id"], language, level, source_name, source, packed)

    return {"jobId": jobs.submit("course", user, work)}


@router.get("/courses/{cid}")
def api_course(cid: str, user: dict = Depends(current_user)):
    course = db.get_course(cid)
    if not course or course["userId"] != user["id"]:
        bad("课程包不存在", 404)
    course.pop("userId", None)
    return course
