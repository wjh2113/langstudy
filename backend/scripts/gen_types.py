"""Generate the frontend's TypeScript API types from the backend's OpenAPI document.

    cd backend && python scripts/gen_types.py      # writes frontend/src/api/types.gen.ts

Run it after changing app/schemas.py so the frontend can't drift from the backend
(the frontend build's type check then flags every place that needs updating).
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GATEWAY_API_KEY", "")

OUT = ROOT.parent / "frontend" / "src" / "api" / "types.gen.ts"


def ts_type(schema: dict) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[1].replace("-", "")
    if "const" in schema:
        return json.dumps(schema["const"], ensure_ascii=False)
    if "enum" in schema:
        return " | ".join(json.dumps(v, ensure_ascii=False) for v in schema["enum"])
    for key in ("anyOf", "oneOf"):
        if key in schema:
            parts = []
            for s in schema[key]:
                t = ts_type(s)
                if t not in parts:
                    parts.append(t)
            return " | ".join(parts)
    t = schema.get("type")
    if t == "string":
        return "string"
    if t in ("integer", "number"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "null":
        return "null"
    if t == "array":
        inner = ts_type(schema.get("items", {}))
        return f"({inner})[]" if "|" in inner else f"{inner}[]"
    if t == "object" or "properties" in schema or "additionalProperties" in schema:
        if "properties" in schema:
            return inline_object(schema)
        extra = schema.get("additionalProperties")
        value = ts_type(extra) if isinstance(extra, dict) and extra else "unknown"
        return f"Record<string, {value}>"
    return "unknown"


def inline_object(schema: dict, indent: str = "") -> str:
    required = set(schema.get("required", []))
    lines = ["{"]
    for name, prop in schema.get("properties", {}).items():
        doc = prop.get("description")
        if doc:
            lines.append(f"{indent}  /** {doc} */")
        opt = "" if name in required else "?"
        lines.append(f"{indent}  {name}{opt}: {ts_type(prop)}")
    lines.append(indent + "}")
    return "\n".join(lines)


def main():
    from app.main import app

    spec = app.openapi()
    out = [
        "// Generated from the backend's OpenAPI document by backend/scripts/gen_types.py.",
        "// Do not edit by hand: change backend/app/schemas.py and re-run the script.",
        "/* eslint-disable */",
        "",
    ]
    for name, schema in sorted(spec["components"]["schemas"].items()):
        if name in ("HTTPValidationError", "ValidationError") or name.startswith("Body_"):
            continue
        ident = name.replace("-", "")
        doc = schema.get("description")
        if doc:
            out.append("/** " + doc.strip().replace("\n", " ") + " */")
        if schema.get("type") == "object" or "properties" in schema:
            out.append(f"export interface {ident} {inline_object(schema)}")
        else:
            out.append(f"export type {ident} = {ts_type(schema)}")
        out.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT.parent)} ({len(spec['components']['schemas'])} schemas)")


if __name__ == "__main__":
    main()
