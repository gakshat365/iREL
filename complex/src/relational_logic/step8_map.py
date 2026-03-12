import os
import json
import csv
import re
from collections import defaultdict
import math

def calculate_refd(concepts, tokenized_transcripts):
    """
    Computes Reference Distance (RefD) for all concept pairs.
    Returns a dict: {(A, B): score}
    """
    refd_scores = {}
    
    for i in range(len(concepts)):
        for j in range(len(concepts)):
            if i == j: continue
            
            c_a = concepts[i]
            c_b = concepts[j]
            
            # Simple check if c_a and c_b consist of multiple tokens, we search for the phrase
            c_a_toks = len(c_a.split())
            c_b_toks = len(c_b.split())
            
            distances = []
            
            for toks in tokenized_transcripts:
               # Find indices of c_a
               a_indices = []
               b_indices = []
               
               str_text = " " + " ".join(toks) + " "
               
               # Fast find
               for m in re.finditer(r'\b' + re.escape(c_a) + r'\b', str_text):
                   # approximate token index
                   a_indices.append(len(str_text[:m.start()].split()))
                   
               for m in re.finditer(r'\b' + re.escape(c_b) + r'\b', str_text):
                   b_indices.append(len(str_text[:m.start()].split()))
                   
               min_dist = float('inf')
               for a_idx in a_indices:
                   for b_idx in b_indices:
                       if b_idx > a_idx:
                           dist = b_idx - a_idx
                           if dist < min_dist:
                               min_dist = dist
               
               if min_dist != float('inf'):
                   distances.append(min_dist)
                   
            if distances:
                mean_dist = sum(distances) / len(distances)
                if mean_dist > 50: # Threshold of 50 tokens
                    consistency = len(distances) / len(tokenized_transcripts)
                    # Normalize score between 0 and 1
                    # 1.0 consistency means it appeared in all 5 videos with A before B
                    score = min(consistency * 1.5, 1.0)
                    refd_scores[(c_a, c_b)] = score
                    
    return refd_scores

def extract_discourse_signals(c_a, c_b, text):
    """
    Extracts discourse markers matching specific rules between concept A and concept B within a text window.
    """
    signals = []
    
    # Escape concepts for regex
    ea = re.escape(c_a)
    eb = re.escape(c_b)
    
    # 1. Sequential Cues
    seq_patterns = [
        rf'pehle.*?\b{ea}\b.*?phir.*?\b{eb}\b',
        rf'before.*?\b{eb}\b.*?\b{ea}\b',
        rf'\b{ea}\b.*?uske baad.*?\b{eb}\b',
        rf'ab hum.*?\b{eb}\b.*?dekhenge' # Contextual: if A was just discussed
    ]
    # 2. Causal Cues
    causal_patterns = [
        rf'\b{ea}\b.*?ki wajah se.*?\b{eb}\b',
        rf'\b{ea}\b.*?happens because of.*?\b{eb}\b',
        rf'\b{eb}\b.*?ke liye.*?\b{ea}\b.*?zaroori hai',
        rf'because of.*?\b{ea}\b.*?\b{eb}\b'
    ]
    # 3. Reformulation 
    ref_patterns = [
        rf'\b{ea}\b.*?is essentially.*?\b{eb}\b',
        rf'\b{ea}\b.*?matlab.*?\b{eb}\b',
        rf'\b{ea}\b.*?ko.*?\b{eb}\b.*?kehte hain'
    ]
    # 4. Assumed Knowledge
    assume_patterns = [
        rf'as we know.*?\b{ea}\b',
        rf'\b{ea}\b.*?toh pata hi hai'
    ]
    
    # For A to B direct edges (sequential/causal) A -> B
    for p in seq_patterns:
        if re.search(p, text, re.IGNORECASE):
            signals.append("sequential")
    for p in causal_patterns:
        if re.search(p, text, re.IGNORECASE):
            signals.append("causal")
            
    # For Reformulation, they are sameAs or alias, so we might want to capture to refine the graph
    for p in ref_patterns:
        if re.search(p, text, re.IGNORECASE):
            signals.append("reformulation")
            
    # Assumed knowledge implies A is a prerequisite for current topic.
    for p in assume_patterns:
        if re.search(p, text, re.IGNORECASE):
            signals.append("assumed_knowledge")
            
    return signals

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    interim_dir = os.path.join(root_dir, 'data', 'interim')
    metadata_file = os.path.join(root_dir, 'data', 'raw', 'metadata.json')
    
    concepts_file = os.path.join(interim_dir, 'concepts.json')
    
    if not os.path.exists(concepts_file):
        print("concepts.json not found. Run step 7 first.")
        return
        
    with open(concepts_file, 'r', encoding='utf-8') as f:
        concepts_data = json.load(f)
        
    # Extract just the canonical concept strings
    concepts = [c['concept'] for c in concepts_data]
    print(f"Loaded {len(concepts)} concepts for mapping.")
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    tokenized_transcripts = []
    full_texts = []
    
    for video in metadata:
        vid = video['video_id']
        txt_path = os.path.join(interim_dir, f'v5_ready_data_{vid}.txt')
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines()]
                tokenized_transcripts.append(" ".join(lines).split())
                full_texts.append(" ".join(lines))
                
    print("Calculating Reference Distance (RefD)...")
    refd_scores = calculate_refd(concepts, tokenized_transcripts)
    print(f"Found {len(refd_scores)} potential RefD edges.")
    
    edges = []
    
    print("Extracting Discourse Markers and Combining Evidence...")
    for i in range(len(concepts)):
        for j in range(len(concepts)):
            if i == j: continue
            
            c_a = concepts[i]
            c_b = concepts[j]
            
            # Combine 5-sentence sliding window for signals across all transcripts
            signals_found = []
            evidences = []
            
            for text in full_texts:
                sentences = text.split('.') # approximate since we stripped punctuation, but line breaks were removed.
                # Actually v5_ready_data is one sentence per line. Let's rebuild the lines.
            
            for vid_text_lines in [t.split(' ') for t in full_texts]:
                # Sliding window of 5 sentences = roughly window of 100 words in our normalized format
                idx = 0
                while idx < len(vid_text_lines):
                    window = " ".join(vid_text_lines[idx:idx+100])
                    # If both concepts exist in window, look for signals
                    if c_a in window and c_b in window:
                        found = extract_discourse_signals(c_a, c_b, window)
                        if found:
                            signals_found.extend(found)
                            evidences.append(window.strip())
                    idx += 50 # Advance half window
                    
            dm_score = min(len(signals_found) * 0.5, 1.0)
            
            refd = refd_scores.get((c_a, c_b), 0.0)
            
            if refd > 0 or dm_score > 0:
                # Combined metric
                confidence = (0.4 * refd) + (0.6 * dm_score)
                
                if confidence >= 0.2:
                    signal_type = signals_found[0] if signals_found else "positional_refd"
                    evidence_str = evidences[0] if evidences else "Positional offset evidence across corpus."
                    
                    edges.append({
                        "source": c_a,
                        "target": c_b,
                        "confidence": round(confidence, 3),
                        "signal_type": signal_type,
                        "evidence": evidence_str
                    })
                    
    out_csv = os.path.join(interim_dir, 'flow_edges.csv')
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["source", "target", "confidence", "signal_type", "evidence"])
        writer.writeheader()
        for e in edges:
            writer.writerow(e)
            
    print(f"Successfully generated {len(edges)} prerequisite edges.")
    print(f"Saved to {out_csv}")
    print("Done! Subtask 8 completed.")

if __name__ == '__main__':
    main()
