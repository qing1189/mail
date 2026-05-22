"""结果查询 API"""
import csv
import io
import os
import sys
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

router = APIRouter(prefix="/api/results", tags=["results"])

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "../..", "Results")


def _read_file_lines(filepath: str) -> list[str]:
    """读取文件行"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


@router.get("")
async def get_results(
    type: str = Query("email", description="类型: email 或 token"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="搜索关键词"),
):
    """获取结果列表"""
    if type == "token":
        filepath = os.path.join(RESULTS_DIR, "outlook_token.txt")
    else:
        filepath = os.path.join(RESULTS_DIR, "unlogged_email.txt")
        if not os.path.exists(filepath):
            filepath = os.path.join(RESULTS_DIR, "logged_email.txt")

    lines = _read_file_lines(filepath)

    # 搜索过滤
    if search:
        lines = [l for l in lines if search.lower() in l.lower()]

    # 分页
    total = len(lines)
    start = (page - 1) * size
    end = start + size
    items = lines[start:end]

    return {
        "code": 0,
        "data": {
            "total": total,
            "page": page,
            "size": size,
            "items": items,
        },
    }


@router.get("/export")
async def export_results(
    type: str = Query("email", description="类型: email 或 token"),
    format: str = Query("txt", description="格式: txt 或 csv"),
):
    """导出结果"""
    if type == "token":
        filepath = os.path.join(RESULTS_DIR, "outlook_token.txt")
    else:
        filepath = os.path.join(RESULTS_DIR, "unlogged_email.txt")
        if not os.path.exists(filepath):
            filepath = os.path.join(RESULTS_DIR, "logged_email.txt")

    lines = _read_file_lines(filepath)

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["账号", "密码", "Client ID", "Refresh Token"])
        for line in lines:
            parts = line.split("----")
            writer.writerow(parts)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={type}_results.csv"},
        )
    else:
        content = "\n".join(lines)
        return StreamingResponse(
            iter([content]),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={type}_results.txt"},
        )


@router.get("/stats")
async def get_result_stats():
    """获取结果统计"""
    email_lines = _read_file_lines(os.path.join(RESULTS_DIR, "unlogged_email.txt"))
    if not email_lines:
        email_lines = _read_file_lines(os.path.join(RESULTS_DIR, "logged_email.txt"))
    token_lines = _read_file_lines(os.path.join(RESULTS_DIR, "outlook_token.txt"))

    return {
        "code": 0,
        "data": {
            "email_count": len(email_lines),
            "token_count": len(token_lines),
        },
    }


@router.delete("")
async def clear_results(type: str = Query("email", description="类型: email 或 token")):
    """清空结果"""
    if type == "token":
        filepath = os.path.join(RESULTS_DIR, "outlook_token.txt")
    else:
        filepath = os.path.join(RESULTS_DIR, "unlogged_email.txt")
        if not os.path.exists(filepath):
            filepath = os.path.join(RESULTS_DIR, "logged_email.txt")

    if os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("")

    return {"code": 0, "message": f"已清空 {type} 结果"}
