from typing import Dict, List
from schemas.extraction import ExtractedDocument

def to_sections(doc: ExtractedDocument) -> Dict[str, List[str]]:
    """Convert a structured ExtractedDocument into sections for diffing."""
    sections = {}
    
    # 1. Map simple fields
    for field in doc.fields:
        key = field.key
        val = field.value
        
        lines = []
        if isinstance(val, list):
            lines = [str(x) for x in val]
        elif isinstance(val, str):
            lines = val.split("\n")
        elif val is not None:
            lines = [str(val)]
            
        sections[key] = [line.strip() for line in lines if line.strip()]
        
    # 2. Map tables
    for table in doc.tables:
        key = table.name
        lines = []
        if table.headers:
            lines.append(" | ".join(str(h) for h in table.headers))
        for row in table.rows:
            lines.append(" | ".join(str(c) for c in row))
        sections[key] = lines
        
    return sections
