from __future__ import annotations
from typing import List, Dict
from schemas.diff import SectionDiff, LogicChange

class SemanticAnalyzer:
    """Detects logical changes by comparing semantic fields directly."""
    
    def analyze(self, old_sections: Dict[str, List[str]], new_sections: Dict[str, List[str]], section_diffs: List[SectionDiff]) -> List[LogicChange]:
        logic_changes = []
        
        for section_diff in section_diffs:
            if section_diff.status in ["equal"]:
                continue
                
            key = section_diff.name
            old_val = "\n".join(old_sections.get(key, [])).strip()
            new_val = "\n".join(new_sections.get(key, [])).strip()
            
            if not old_val or not new_val:
                continue

            # 1. Detect hours changes
            hours_keys = {
                'ore_curs': 'Lecture hours',
                'ore_laborator': 'Lab hours',
                'ore_seminar': 'Seminar hours',
                'ore_proiect': 'Project hours'
            }
            if key in hours_keys:
                if old_val != new_val:
                    logic_changes.append(LogicChange(
                        type="HOURS_CHANGED",
                        section=key,
                        description=f"{hours_keys[key]} changed from {old_val} to {new_val}",
                        severity="HIGH",
                        old_value=old_val,
                        new_value=new_val
                    ))
            
            # 2. Detect ECTS changes
            if key in ['credite_ects', 'credite']:
                if old_val != new_val:
                    logic_changes.append(LogicChange(
                        type="ECTS_CHANGED",
                        section=key,
                        description=f"ECTS credits changed from {old_val} to {new_val}",
                        severity="HIGH",
                        old_value=old_val,
                        new_value=new_val
                    ))
            
            # 3. Detect evaluation changes
            if 'evaluare' in key or 'procent' in key:
                if old_val != new_val:
                    logic_changes.append(LogicChange(
                        type="EVALUATION_CHANGED",
                        section=key,
                        description=f"{key.replace('_', ' ').capitalize()} changed from {old_val} to {new_val}",
                        severity="MEDIUM",
                        old_value=old_val,
                        new_value=new_val
                    ))

        return logic_changes
