import re
import os

def load_valid_ids(work_exp_path):
    """Parses workExperience.md to extract all valid IDs and their ground-truth sentences.
    Returns a dictionary: {ID: GroundTruthLine}
    """
    truth_map = {}
    if not os.path.exists(work_exp_path):
        return truth_map
    
    with open(work_exp_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Parse line by line to associate IDs with their content context
    lines = content.split('\n')
    pattern = re.compile(r"(ACC-\d+|MET-\d+|VOC-\d+)")
    
    for line in lines:
        matches = pattern.findall(line)
        for m in matches:
            # Preserve the FIRST occurrence of the ID as the Ground Truth source,
            # preventing subsequent example citations from overwriting definitions.
            if m not in truth_map:
                truth_map[m] = line.strip()
            
    return truth_map

def extract_numeric_tokens(text):
    """Extracts string segments containing digits (e.g., 40, 300, 25000)."""
    # Strip commas to normalize numbers (e.g., 40,000 -> 40000)
    normalized = text.replace(",", "")
    # Find all sequences of digits
    tokens = re.findall(r"\b\d+\b", normalized)
    return set(tokens)

def verify_content(content, truth_map):
    """
    Performs Fact-Bound Semantic Verification (FR-069).
    Verifies ID presence and ensures NO fabricated numeric metrics are injected.
    """
    # 1. Presence Verification
    pattern = re.compile(r"\[(ACC-\d+|MET-\d+|VOC-\d+)\]")
    found_ids = set(pattern.findall(content))
    
    if not found_ids:
        return {
            "success": False,
            "error": "No claim IDs found in content. Every bullet/paragraph must be anchored to a valid [ID].",
            "invalid_ids": [],
            "found_ids": []
        }
        
    # Check if all referenced IDs exist in ground truth
    invalid_ids = [fid for fid in found_ids if fid not in truth_map]
    if invalid_ids:
        return {
            "success": False,
            "error": f"Invalid/Non-existent IDs cited: {', '.join(invalid_ids)}",
            "invalid_ids": invalid_ids,
            "found_ids": list(found_ids)
        }

    # 2. Fact-Bound Metric Validation
    # Break content into logical sentences or bullet lines
    sentences = [s.strip() for s in re.split(r"\n|\. ", content) if s.strip()]
    
    for idx, s in enumerate(sentences):
        # Find all citations in THIS sentence
        citations = pattern.findall(s)
        if not citations:
            continue
            
        # Strip the citation brackets themselves (e.g., [MET-01]) from the text
        # to prevent matching '01' or '101' as fabricated numeric metrics.
        clean_s = pattern.sub(" ", s)
        
        # Extract numeric entities generated in this sentence
        gen_tokens = extract_numeric_tokens(clean_s)
        
        # Aggregate all truth lines for every citation referenced in this sentence.
        # This allows a single sentence to make multiple valid claims (e.g. MET-01 and MET-03) 
        # and verifies them against the combined set of allowed metrics.
        truth_segments = []
        all_truth_tokens = set()
        
        for cid in citations:
            truth_line = truth_map[cid]
            clean_truth_line = pattern.sub(" ", truth_line)
            truth_segments.append(clean_truth_line.lower().replace(",", ""))
            
            all_truth_tokens.update(extract_numeric_tokens(clean_truth_line))
            
        # Evaluate each generated numeric token against the combined context
        for token in gen_tokens:
            # Skip single digits that are extremely common (like 1, 2, 3) to avoid false negatives on list indices,
            # but rigorously gate multi-digit metrics, percentages, and scales.
            if len(token) <= 1 and token in "0123456789":
                continue
                
            # Check if this token is supported by ANY of the citation ground truths
            supported = False
            for norm_truth in truth_segments:
                if token in norm_truth:
                    supported = True
                    break
                    
            if not supported:
                # Secondary containment check on any single truth token
                supported = any(t.startswith(token) or token.startswith(t) for t in all_truth_tokens)
                
            if not supported:
                return {
                    "success": False,
                    "error": f"Factual Mismatch on {citations}: Sentence claims '{token}' which is not supported by the cited Ground Truths. Line: \"{s}\"",
                    "invalid_ids": [],
                    "found_ids": list(found_ids),
                    "hallucination": {
                        "citations": citations,
                        "failed_metric": token,
                        "sentence": s,
                        "ground_truths": [truth_map[c] for c in citations]
                    }
                }

    return {
        "success": True,
        "error": None,
        "invalid_ids": [],
        "found_ids": list(found_ids)
    }

def strip_ids(content):
    """Strips claim IDs from generated content so it can be compiled."""
    pattern = re.compile(r"\s*\[(ACC-\d+|MET-\d+|VOC-\d+)\]\s*")
    cleaned = pattern.sub(" ", content)
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned.strip()

if __name__ == "__main__":
    # Quick verification dry run
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exp_path = os.path.join(base_dir, "data", "workExperience.md")
    truth = load_valid_ids(exp_path)
    print(f"Loaded {len(truth)} truth mappings.")
    
    # Valid case test
    valid_txt = "Managed customer platform scaling to 25,000 users [MET-03] and protected $40,000,000 ARR [MET-01]."
    res = verify_content(valid_txt, truth)
    print(f"Test (Valid): {res['success']} | Error: {res['error']}")
    
    # Mismatch / Fabrication test
    invalid_txt = "Grew revenue to $50,000,000 ARR [MET-01]."
    res_inv = verify_content(invalid_txt, truth)
    print(f"Test (Invalid): {res_inv['success']} | Error: {res_inv['error']}")
