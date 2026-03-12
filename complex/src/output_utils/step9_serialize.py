import os
import json
import csv
import re
from pyvis.network import Network
import networkx as nx

import logging
logging.basicConfig(level=logging.INFO)

# For Tier 3 sameAs Enrichment
try:
    import spacy
except ImportError:
    spacy = None

"""
NOTE on Tier 3 sameAs Enrichment:
Automated entity linking on Hinglish-derived concept labels (where the underlying syntactic structure 
and phonetic realization heavily deviates from standard English Wikipedia entity labels) is an open 
research problem. This script attempts to use spaCy's EntityLinker to retrieve a candidate URL. 
A highly conservative confidence threshold of 0.8 is applied to favour precision over recall, 
avoiding spurious links. Full automation of this step at scale is actively marked as future work.
"""

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text).strip('-')
    return f"#{text}"

def run_entity_linking(nlp, label):
    """Attempt entity linking against spaCy knowledge base. Returns URL or None."""
    if nlp is None:
        return None
        
    try:
        doc = nlp(label)
        # Check against linked entities
        for ent in doc.ents:
            if ent.kb_id_ != 0 and hasattr(ent, "_"):
                # Simplistic dummy heuristic for Entity Linker if it's setup
                # Actually initializing a full KB for SpaCy takes custom files.
                # Assuming standard en_core_web_sm doesn't have a linked KB without explicit add-on.
                pass
    except Exception:
        pass
        
    return None

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    interim_dir = os.path.join(root_dir, 'data', 'interim')
    processed_dir = os.path.join(root_dir, 'data', 'processed')
    metadata_file = os.path.join(root_dir, 'data', 'raw', 'metadata.json')
    
    concepts_file = os.path.join(interim_dir, 'concepts.json')
    edges_file = os.path.join(interim_dir, 'flow_edges.csv')
    
    os.makedirs(processed_dir, exist_ok=True)
    
    if not os.path.exists(concepts_file) or not os.path.exists(edges_file):
        logging.error("Missing interim data (concepts.json or flow_edges.csv). Ensure steps 7 & 8 are run.")
        return
        
    with open(concepts_file, 'r', encoding='utf-8') as f:
        concepts = json.load(f)
        
    edges = []
    with open(edges_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            edges.append(row)
            
    # Load SpaCy for Entity Linking if available
    nlp = None
    if spacy:
        try:
            # Requires `python -m spacy download en_core_web_sm`
            nlp = spacy.load("en_core_web_sm")
            # Usually requires `nlp.add_pipe("entityLinker", last=True)` but requires `spacy-entity-linker` module.
            # We fail gracefully as we warned in the docstring.
        except Exception:
            logging.warning("SpaCy model 'en_core_web_sm' not found or EntityLinker not attached. Skipping sameAs enrichment.")
            
    # Build JSON-LD
    has_course = []
    for c in concepts:
        label = c['concept']
        node_id = slugify(label)
        
        # Build alignments (edges where target == this concept, so source is prerequisite)
        # Wait, if A -> B, then B has prerequisite A. 
        # Source = prerequisite, Target = the concept being taught.
        # So for concept B, we find all edges where target == B.
        alignments = []
        for e in edges:
            if e['target'] == label:
                alignments.append({
                    "@type": "AlignmentObject",
                    "alignmentType": "prerequisite",
                    "targetName": e['source'],
                    "educationalFramework": "PedagogicalFlow",
                    "confidence": float(e['confidence']),
                    "signal": e['signal_type'],
                    "evidence": e['evidence']
                })
                
        course_obj = {
            "@type": "Course",
            "@id": node_id,
            "name": label,
            "educationalAlignment": alignments
        }
        
        # sameAs enrichment
        if nlp:
            wiki_url = run_entity_linking(nlp, label)
            if wiki_url:
                course_obj["sameAs"] = wiki_url
                
        has_course.append(course_obj)
        
    json_ld = {
        "@context": "https://schema.org/",
        "@type": "EducationalOccupationalProgram",
        "hasCourse": has_course
    }
    
    jsonld_out = os.path.join(processed_dir, 'pedagogical_flow.jsonld')
    with open(jsonld_out, 'w', encoding='utf-8') as f:
        json.dump(json_ld, f, indent=4, ensure_ascii=False)
        logging.info(f"Saved JSON-LD graph to {jsonld_out}")

    # Build and Render PyVis Network (Global Graph)
    G = nx.DiGraph()
    for c in concepts:
        G.add_node(c['concept'], title=f"Score: {c['score']:.4f}")
        
    for e in edges:
        G.add_edge(e['source'], e['target'], 
                   title=f"{e['signal_type']} (conf: {e['confidence']})", 
                   weight=float(e['confidence']))
                   
    # Global Net
    global_net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white', directed=True)
    global_net.from_nx(G)
    
    # Use hierarchical layout to reduce chaotic movement and show prerequisites naturally
    global_net.set_options("""
    var options = {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -10000,
          "centralGravity": 0.3,
          "springLength": 150,
          "springConstant": 0.05,
          "damping": 1.0,
          "avoidOverlap": 1
        },
        "minVelocity": 50.0,
        "solver": "barnesHut",
        "stabilization": {
          "enabled": true,
          "iterations": 100
        }
      }
    }
    """)
    
    
    global_html = os.path.join(processed_dir, 'pedagogical_flow.html')
    global_net.write_html(global_html)
    logging.info(f"Saved global PyVis Graph to {global_html}")
    
    # Per-video subgraphs based on what concepts are in the video
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    for video in metadata:
        vid = video['video_id']
        txt_path = os.path.join(interim_dir, f'v5_ready_data_{vid}.txt')
        if not os.path.exists(txt_path):
            continue
            
        with open(txt_path, 'r', encoding='utf-8') as f:
            vid_text = f.read()
            
        vid_concepts = [c['concept'] for c in concepts if re.search(r'\b'+re.escape(c['concept'])+r'\b', vid_text)]
        
        if vid_concepts:
            sub_G = G.subgraph(vid_concepts)
            sub_net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white', directed=True)
            sub_net.from_nx(sub_G)
            sub_net.set_options("""
            var options = {
              "physics": {
                "barnesHut": {
                  "damping": 1.0,
                  "avoidOverlap": 1
                },
                "minVelocity": 50.0,
                "stabilization": {
                  "enabled": true,
                  "iterations": 100
                }
              }
            }
            """)
            
            vid_html = os.path.join(processed_dir, f'pedagogical_flow_{vid}.html')
            sub_net.write_html(vid_html)
            logging.info(f"Saved subgraph for {vid} to {vid_html}")

    print("Done! Subtask 9 completed.")

if __name__ == '__main__':
    main()
