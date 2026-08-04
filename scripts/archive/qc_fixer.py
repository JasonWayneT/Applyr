# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import os
import re
from pathlib import Path

subs_dir = Path(r'c:\Users\Jason\Desktop\Jason\Resource\CodeProjects\JobAgent\submissions')

cision_fallback_bullet = "* Replaced reactive planning with a rigorous, PTO-adjusted capacity model based on workday-hours per engineer, using T-shirt sizing with uncertainty bands to manage resource allocations across stability, compliance, and planned roadmap items."

for company_dir in subs_dir.iterdir():
    if not company_dir.is_dir() or company_dir.name.startswith('.'):
        continue
    
    resume_path = company_dir / 'Resume.md'
    cl_path = company_dir / 'CoverLetter.md'
    
    if not resume_path.exists() or not cl_path.exists():
        continue
        
    with open(resume_path, 'r', encoding='utf-8') as f:
        resume_content = f.read()
        
    with open(cl_path, 'r', encoding='utf-8') as f:
        cl_content = f.read()

    # 1. Fix Cover Letter formatting anomalies
    cl_content = cl_content.replace(' ,  ', ', ')
    cl_content = cl_content.replace(' ,', ',')
    cl_content = cl_content.replace('(.', '.')
    cl_content = re.sub(r'\s+,', ',', cl_content)
    
    # 2. Fix Resume formatting anomalies
    resume_content = resume_content.replace(' ,  ', ', ')
    resume_content = resume_content.replace(' ,', ',')
    resume_content = resume_content.replace('(.', '.')
    resume_content = re.sub(r'\s+,', ',', resume_content)
    
    # 3. Strip Title variants
    resume_content = re.sub(r'### Product Manager \(.*?\) \| Cision', '### Product Manager | Cision', resume_content)
    
    # 4. Enforce bullet counts
    # We want Cision to have 4, Sterkly 3, Zero 2
    sections = re.split(r'(\n###\s+)', resume_content)
    # sections[0] is everything before the first ###
    # sections[1] is \n###\s+
    # sections[2] is the first job (e.g. Cision)
    
    new_sections = []
    
    # We rebuild the resume
    i = 0
    while i < len(sections):
        if i == 0 or i % 2 != 0:
            new_sections.append(sections[i])
            i += 1
            continue
            
        sec = sections[i]
        lines = sec.split('\n')
        header = lines[0].lower()
        
        # Extract bullets
        bullet_indices = [idx for idx, l in enumerate(lines) if l.strip().startswith('* ') or l.strip().startswith('- ')]
        
        if 'cision' in header:
            if len(bullet_indices) < 4:
                # Add a bullet at the end of the bullets list
                last_bullet_idx = bullet_indices[-1] if bullet_indices else len(lines)-1
                lines.insert(last_bullet_idx + 1, cision_fallback_bullet)
        elif 'sterkly' in header:
            # ensure 3 bullets
            while len(bullet_indices) > 3:
                del lines[bullet_indices[-1]]
                bullet_indices.pop()
        elif 'zero to sixty' in header:
            # ensure 2 bullets
            while len(bullet_indices) > 2:
                del lines[bullet_indices[-1]]
                bullet_indices.pop()
        
        new_sections.append('\n'.join(lines))
        i += 1

    resume_content = "".join(new_sections)

    # 5. Summary cut-off fix (if ends with a hanging parenthesis or similar)
    # Just a simple regex to fix common cutoffs
    resume_content = re.sub(r'\(\.\s*$', '.', resume_content, flags=re.MULTILINE)
    
    with open(resume_path, 'w', encoding='utf-8') as f:
        f.write(resume_content)
        
    with open(cl_path, 'w', encoding='utf-8') as f:
        f.write(cl_content)

print("QC Fixes applied to all directories.")
