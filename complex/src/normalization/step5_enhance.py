import os
import json
import re
import jellyfish
from symspellpy import SymSpell, Verbosity

def enhance_text(text, sym_spell, domain_vocab, soundex_map, lexicon):
    # Stage 1: Text Normalization for lookup
    # Only lowercase and strip punctuation for lookup strings
    
    tokens = text.split()
    enhanced_tokens = []
    
    for original_token in tokens:
        # Stage 1
        lookup_token = re.sub(r'[^\w\s-]', '', original_token).lower()
        
        if not lookup_token or lookup_token.isdigit():
            enhanced_tokens.append(original_token)
            continue
            
        # Optional: fast path if it's already perfectly valid vocab
        if lookup_token in domain_vocab:
            enhanced_tokens.append(original_token) # we can choose to canonicalize casing later, but keep as is for now
            continue
            
        # Stage 2: SymSpell spelling correction
        suggestions = sym_spell.lookup(lookup_token, Verbosity.CLOSEST, max_edit_distance=2)
        if suggestions and suggestions[0].distance > 0:
            # Found a correction in our targeted vocab that is NOT exact match
            corrected_word = suggestions[0].term
            if corrected_word in domain_vocab:
                enhanced_tokens.append(corrected_word)
                continue
                
        # Stage 3: Roman Phonetic fallback instead of IndicSoundex
        # The text is already romanized, so we use canonical Soundex/Metaphone on the roman string.
        ph_code = jellyfish.soundex(lookup_token)
        if ph_code in soundex_map:
            matches = soundex_map[ph_code]
            if len(matches) == 1:
                enhanced_tokens.append(matches[0])
                continue
            else:
                # Multiple matches found, pick lowest edit distance
                best_match = None
                best_dist = float('inf')
                for match in matches:
                    dist = jellyfish.damerau_levenshtein_distance(lookup_token, match)
                    if dist < best_dist:
                        best_dist = dist
                        best_match = match
                enhanced_tokens.append(best_match)
                continue
                
        # If no correction applies
        enhanced_tokens.append(original_token)
        
    enhanced_str = ' '.join(enhanced_tokens)
    
    # Stage 4: Domain Dictionary Replacement (Phrasal longest match)
    # We sort keys by length descending to match longest phrases first
    sorted_keys = sorted(lexicon.keys(), key=lambda k: len(k.split()), reverse=True)
    
    for phrase in sorted_keys:
        # Simple string replace with boundaries to not overwrite partial words
        pattern = r'\b' + re.escape(phrase) + r'\b'
        enhanced_str = re.sub(pattern, lexicon[phrase], enhanced_str, flags=re.IGNORECASE)
        
    return enhanced_str

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    metadata_file = os.path.join(root_dir, 'data', 'raw', 'metadata.json')
    interim_dir = os.path.join(root_dir, 'data', 'interim')
    
    vocab_file = os.path.join(root_dir, 'assets', 'domain_vocab.txt')
    lexicon_file = os.path.join(root_dir, 'assets', 'domain_lexicon.json')
    
    # Init SymSpell
    sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    domain_vocab = set()
    soundex_map = {}
    
    with open(vocab_file, 'r', encoding='utf-8') as f:
        for line in f:
            w = line.strip().lower()
            if w:
                domain_vocab.add(w)
                sym_spell.create_dictionary_entry(w, 1)
                
                # Precompute soundex
                code = jellyfish.soundex(w)
                if code not in soundex_map:
                    soundex_map[code] = []
                soundex_map[code].append(w)
                
    with open(lexicon_file, 'r', encoding='utf-8') as f:
        lexicon = json.load(f)
        
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    for video in metadata:
        video_id = video['video_id']
        input_file = os.path.join(interim_dir, f'v3_cleaned_sentences_{video_id}.txt')
        output_file = os.path.join(interim_dir, f'v4_standardized_terms_{video_id}.txt')
        
        print(f"Enhancing {video_id}...")
        if not os.path.exists(input_file):
            print(f"  Warning: {input_file} not found.")
            continue
            
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        with open(output_file, 'w', encoding='utf-8') as out_f:
            for line in lines:
                line = line.strip()
                if not line: continue
                enhanced_line = enhance_text(line, sym_spell, domain_vocab, soundex_map, lexicon)
                out_f.write(f"{enhanced_line}\n")
                
        print(f"  Saved to {output_file}")
        
    print("Done! Subtask 5 completed.")

if __name__ == '__main__':
    main()
