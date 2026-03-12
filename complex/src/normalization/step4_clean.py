import os
import re
import json
import pysbd

def clean_text(text):
    """Apply regex and lexical cleaning to remove noise and disfluencies."""
    # Strip URLs
    text = re.sub(r'https?:\/\/\S+', '', text)
    # Strip hashtags and social media artifacts (basic @ and #)
    text = re.sub(r'[@#]\S+', '', text)
    
    # Remove residual non-ASCII characters (keep ascii and basic punctuation)
    # Using encode/decode to drop non-ascii, but we also want to keep Purn Viram (।) if it exists, 
    # though transliteration usually converts or drops it. Let's explicitly keep ASCII + Purn Viram.
    text = re.sub(r'[^\x00-\x7F\u0964]+', '', text)
    
    # Token-level cleaning for disfluencies
    disfluencies = {"uh", "um", "hmm", "uh-huh"}
    tokens = text.split()
    cleaned_tokens = []
    
    for token in tokens:
        # Strip punctuation just for the check
        clean_token = re.sub(r'[^\w\s-]', '', token).lower()
        if clean_token not in disfluencies:
            cleaned_tokens.append(token)
            
    return ' '.join(cleaned_tokens)

def segment_sentences(text, segmenter):
    """Segment sentences using pysbd and fallback Purn Viram splitting."""
    # Primary segmentation via pysbd
    sentences = segmenter.segment(text)
    
    # Secondary split on Purn Viram (।)
    final_sentences = []
    for sent in sentences:
        if '।' in sent:
            parts = [p.strip() for p in sent.split('।') if p.strip()]
            final_sentences.extend(parts)
        else:
            if sent.strip():
                final_sentences.append(sent.strip())
                
    return final_sentences

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    metadata_file = os.path.join(root_dir, 'data', 'raw', 'metadata.json')
    interim_dir = os.path.join(root_dir, 'data', 'interim')
    
    # Initialize pysbd segmenter once
    segmenter = pysbd.Segmenter(language="en", clean=False)
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    for video in metadata:
        video_id = video['video_id']
        input_file = os.path.join(interim_dir, f'v2_hinglish_roman_{video_id}.txt')
        output_file = os.path.join(interim_dir, f'v3_cleaned_sentences_{video_id}.txt')
        
        print(f"Processing {video_id}...")
        if not os.path.exists(input_file):
            print(f"  Warning: {input_file} not found. Skipping.")
            continue
            
        with open(input_file, 'r', encoding='utf-8') as f:
            # The previous step wrote one segment per line, but segments don't equal linguistic sentences.
            # We want to feed the entire transcript to the segmenter to fix bad breaks.
            raw_text = f.read().replace('\n', ' ')
            
        cleaned_blob = clean_text(raw_text)
        sentences = segment_sentences(cleaned_blob, segmenter)
        
        with open(output_file, 'w', encoding='utf-8') as out_f:
            for s in sentences:
                # Remove extra spaces inside sentences before writing
                s = re.sub(r'\s+', ' ', s).strip()
                if s:
                    out_f.write(f"{s}\n")
                    
        print(f"  Saved to {output_file}")
        
    print("Done! Subtask 4 completed.")

if __name__ == '__main__':
    main()
