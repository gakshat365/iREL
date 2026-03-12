import os
import json
from indic_transliteration import sanscript

def transliterate_to_roman(text):
    """Transliterate Devanagari Unicode to Roman ITRANS scheme."""
    return sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)

def apply_schwa_deletion(text, schwa_dict):
    """Apply exact-match token replacement for schwa-deletion post-processing."""
    tokens = text.split()
    corrected_tokens = []
    for token in tokens:
        # Check exact lowercase token in schwa dictionary for exact replacement
        lower_token = token.lower()
        if lower_token in schwa_dict:
            # Preserve original casing if possible, or just replace with lowercased matched target
            corrected_tokens.append(schwa_dict[lower_token])
        else:
            corrected_tokens.append(token)
    return ' '.join(corrected_tokens)

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    metadata_file = os.path.join(root_dir, 'data', 'raw', 'metadata.json')
    interim_dir = os.path.join(root_dir, 'data', 'interim')
    schwa_corrections_file = os.path.join(root_dir, 'assets', 'schwa_corrections.json')
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    with open(schwa_corrections_file, 'r', encoding='utf-8') as f:
        schwa_corrections = json.load(f)
        
    for video in metadata:
        video_id = video['video_id']
        input_file = os.path.join(interim_dir, f'v1_raw_transcript_{video_id}.json')
        output_file = os.path.join(interim_dir, f'v2_hinglish_roman_{video_id}.txt')
        
        print(f"Processing {video_id}...")
        
        if not os.path.exists(input_file):
            print(f"  Warning: {input_file} not found. Skipping.")
            continue
            
        with open(input_file, 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
            
        segments = transcript_data.get('segments', [])
        
        with open(output_file, 'w', encoding='utf-8') as out_f:
            for segment in segments:
                text = segment.get('text', '')
                
                # 1. Transliterate Devanagari to Roman (ITRANS)
                romanized_text = transliterate_to_roman(text)
                
                # 2. Apply explicit schwa deletion corrections
                corrected_text = apply_schwa_deletion(romanized_text, schwa_corrections)
                
                out_f.write(f"{corrected_text}\n")
                
        print(f"  Saved to {output_file}")
        
    print("Done! Subtask 3 completed.")
                
if __name__ == '__main__':
    main()
