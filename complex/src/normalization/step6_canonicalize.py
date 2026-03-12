import os
import json
import jellyfish

def process_token(token, dialect_map, contractions, hinglish_fillers, domain_vocab):
    lower_token = token.lower()
    
    # 1. Check Hinglish whitelist
    if lower_token in hinglish_fillers:
        return token
        
    # 2. Dialect map
    if lower_token in dialect_map:
        return dialect_map[lower_token]
        
    # 3. Contractions
    if lower_token in contractions:
        return contractions[lower_token]
        
    # Fast path if it's already perfectly matched in domain vocab
    if lower_token in domain_vocab:
        return lower_token
        
    # 4. Fallback Damerau-Levenshtein against domain terms
    candidates = []
    # Only evaluate distance for words length > 3 to avoid aggressive matching of small particles
    if len(lower_token) > 3:
        for vocab_word in domain_vocab:
            # Damerau-Levenshtein counts transpositions as distance 1 (e.g. teh -> the)
            dist = jellyfish.damerau_levenshtein_distance(lower_token, vocab_word)
            if dist == 1:
                candidates.append(vocab_word)
                
    if len(candidates) == 1:
        return candidates[0]
        
    return token

def canonicalize_line(line, dialect_map, contractions, hinglish_fillers, domain_vocab):
    tokens = line.split()
    processed_tokens = [process_token(t, dialect_map, contractions, hinglish_fillers, domain_vocab) for t in tokens]
    return ' '.join(processed_tokens)

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    interim_dir = os.path.join(root_dir, 'data', 'interim')
    metadata_file = os.path.join(root_dir, 'data', 'raw', 'metadata.json')
    assets_dir = os.path.join(root_dir, 'assets')
    
    try:
        with open(os.path.join(assets_dir, 'dialect_map.json'), 'r', encoding='utf-8') as f:
            dialect_map = json.load(f)
            
        with open(os.path.join(assets_dir, 'contractions.json'), 'r', encoding='utf-8') as f:
            contractions = json.load(f)
            
        with open(os.path.join(assets_dir, 'hinglish_fillers.json'), 'r', encoding='utf-8') as f:
            hinglish_fillers = set(json.load(f))
            
        domain_vocab = set()
        with open(os.path.join(assets_dir, 'domain_vocab.txt'), 'r', encoding='utf-8') as f:
            for line in f:
                w = line.strip().lower()
                if w:
                    domain_vocab.add(w)
                    
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            
    except Exception as e:
        print(f"Error loading assets or metadata: {e}")
        return

    for video in metadata:
        video_id = video['video_id']
        input_file = os.path.join(interim_dir, f'v4_standardized_terms_{video_id}.txt')
        output_file = os.path.join(interim_dir, f'v5_ready_data_{video_id}.txt')
        
        print(f"Canonicalizing {video_id}...")
        if not os.path.exists(input_file):
            print(f"  Warning: {input_file} not found.")
            continue
            
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        with open(output_file, 'w', encoding='utf-8') as out_f:
            for line in lines:
                line = line.strip()
                if not line: continue
                can_line = canonicalize_line(line, dialect_map, contractions, hinglish_fillers, domain_vocab)
                out_f.write(f"{can_line}\n")
                
        print(f"  Saved to {output_file}")
        
    print("Done! Subtask 6 completed.")

if __name__ == '__main__':
    main()
