import os
import json
import re
import math
from collections import Counter, defaultdict
import networkx as nx
from metaphone import doublemetaphone
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
import yake

nltk.download('stopwords', quiet=True)

def generate_ngrams(words, n):
    return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]

def get_most_frequent_form(surface_forms):
    return max(set(surface_forms), key=surface_forms.count)

def get_tf_idf_weights(corpus):
    vectorizer = TfidfVectorizer(ngram_range=(1, 3))
    tfidf_matrix = vectorizer.fit_transform(corpus)
    feature_names = vectorizer.get_feature_names_out()
    
    # We take the max tf-idf score for each term across all documents
    max_scores = tfidf_matrix.max(axis=0).toarray().flatten()
    return dict(zip(feature_names, max_scores))

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    interim_dir = os.path.join(root_dir, 'data', 'interim')
    metadata_file = os.path.join(root_dir, 'data', 'raw', 'metadata.json')
    assets_dir = os.path.join(root_dir, 'assets')
    
    with open(os.path.join(assets_dir, 'hinglish_fillers.json'), 'r') as f:
        custom_stops = set(json.load(f))
    
    eng_stops = set(stopwords.words('english'))
    all_stops = eng_stops.union(custom_stops)
    
    with open(os.path.join(assets_dir, 'so_tags.txt'), 'r') as f:
        so_anchors = {line.strip().lower() for line in f if line.strip()}
    
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
        
    corpus = []
    video_texts = {}
    
    for video in metadata:
        vid = video['video_id']
        file_path = os.path.join(interim_dir, f'v5_ready_data_{vid}.txt')
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            
        text_blob = " ".join(lines)
        corpus.append(text_blob)
        video_texts[vid] = lines
        
        # Baseline YAKE
        yk = yake.KeywordExtractor(lan="en", n=3, top=20)
        keywords = yk.extract_keywords(text_blob)
        yake_out = os.path.join(interim_dir, f'baseline_yake_{vid}.json')
        with open(yake_out, 'w') as out_f:
            json.dump(keywords, out_f, indent=2)

    if not corpus:
        print("No texts found to extract concepts from!")
        return

    print("Phase 1: Phonetic normalization and TF-IDF computation...")
    tfidf_weights = get_tf_idf_weights(corpus)
    
    all_sentences = []
    for lines in video_texts.values():
        all_sentences.extend(lines)
        
    # Build phonetic map
    metaphone_groups = defaultdict(list)
    for sent in all_sentences:
        for w in sent.split():
            clean_w = re.sub(r'[^\w\s-]', '', w.lower())
            if clean_w and clean_w not in all_stops:
                code = doublemetaphone(clean_w)[0]
                if code:
                    metaphone_groups[code].append(clean_w)
                    
    canonical_forms = {}
    for code, words in metaphone_groups.items():
        canonical_forms[code] = get_most_frequent_form(words)
        
    # Normalize corpus sentences
    norm_sentences = []
    for sent in all_sentences:
        norm_tokens = []
        for w in sent.split():
            clean_w = re.sub(r'[^\w\s-]', '', w.lower())
            if clean_w in all_stops: continue
            code = doublemetaphone(clean_w)[0]
            if code and code in canonical_forms:
                norm_tokens.append(canonical_forms[code])
        if norm_tokens:
            norm_sentences.append(norm_tokens)
            
    print("Phase 2: Candidate generation with Anchor Rule...")
    ngram_freqs = Counter()
    for tokens in norm_sentences:
        for n in [1, 2, 3]:
            ngrams = generate_ngrams(tokens, n)
            ngram_freqs.update(ngrams)
            
    # Anchor rule + simple pseudo-C-value
    candidates = {}
    for ngram, freq in ngram_freqs.items():
        if freq < 2: continue
        
        # Checking anchor
        words = ngram.split()
        has_anchor = any(w in so_anchors for w in words)
        if not has_anchor:
            continue
            
        c_value = math.log2(len(words) + 1) * freq
        tf_idf = tfidf_weights.get(ngram, 0.01)
        score = c_value * tf_idf
        if score > 0:
            candidates[ngram] = score
            
    print(f"Generated {len(candidates)} anchored candidates.")
    
    print("Phase 3: Semantic Graph TextRank...")
    promoted_candidates = list(candidates.keys())
    model = SentenceTransformer('sentence-transformers/LaBSE')
    embeddings = model.encode(promoted_candidates, show_progress_bar=True)
    
    G = nx.Graph()
    G.add_nodes_from(promoted_candidates)
    
    # Co-occurrence in 5-sentence sliding window
    co_occurrences = defaultdict(int)
    for i in range(len(norm_sentences) - 5):
        window_text = " ".join([" ".join(s) for s in norm_sentences[i:i+5]])
        window_matches = [c for c in promoted_candidates if c in window_text]
        for a in window_matches:
            for b in window_matches:
                if a < b:
                    co_occurrences[(a, b)] += 1
                    
    for (a, b), count in co_occurrences.items():
        if count > 0:
            idx_a = promoted_candidates.index(a)
            idx_b = promoted_candidates.index(b)
            # Only connect nodes strongly
            sim = cosine_similarity([embeddings[idx_a]], [embeddings[idx_b]])[0][0]
            if sim > 0.4:
                G.add_edge(a, b, weight=sim * count)
                
    pagerank_scores = nx.pagerank(G, weight='weight')
    top_candidates = sorted(pagerank_scores.keys(), key=lambda x: pagerank_scores[x], reverse=True)[:50]
    
    print("Phase 4: Semantic Deduplication...")
    final_concepts = []
    skip = set()
    
    for i in range(len(top_candidates)):
        if i in skip: continue
        cluster = [top_candidates[i]]
        idx_i = promoted_candidates.index(top_candidates[i])
        
        for j in range(i+1, len(top_candidates)):
            if j in skip: continue
            idx_j = promoted_candidates.index(top_candidates[j])
            sim = cosine_similarity([embeddings[idx_i]], [embeddings[idx_j]])[0][0]
            if sim > 0.85:
                cluster.append(top_candidates[j])
                skip.add(j)
                
        # Pick shortest as canonical (often most formal concept rather than descriptive phrase)
        canonical = min(cluster, key=len)
        final_concepts.append({
            "concept": canonical,
            "score": pagerank_scores[canonical],
            "synonyms": [c for c in cluster if c != canonical]
        })
        
    out_file = os.path.join(interim_dir, 'concepts.json')
    with open(out_file, 'w') as f:
        json.dump(final_concepts, f, indent=4)
        
    print(f"Extracted {len(final_concepts)} canonical concepts.")
    print("Done! Subtask 7 completed.")

if __name__ == '__main__':
    main()
