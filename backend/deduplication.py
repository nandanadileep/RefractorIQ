# RefractorIQ/backend/deduplication.py
import os
import re
from datasketch import MinHash, MinHashLSH
from .analysis import is_third_party_file, is_test_file, get_parser_and_language

# --- Tokenization / Shingling ---

# Create k-grams (shingles) from text content
def get_shingles(text, k=5):
    """Create a set of k-grams (shingles) from a string."""
    shingles = set()
    if not text:
        return shingles
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    for i in range(len(text) - k + 1):
        shingles.add(text[i:i+k])
    return shingles

# --- MinHash Analysis ---

def analyze_duplicates_minhash(
    repo_path, 
    exclude_third_party=True, 
    exclude_tests=True, 
    threshold=0.85, 
    num_perm=128,
    k=5
):
    """
    Analyzes code duplication using MinHash and LSH.
    
    Args:
        repo_path (str): Path to the repository.
        exclude_third_party (bool): Exclude third-party dirs.
        exclude_tests (bool): Exclude test files.
        threshold (float): Jaccard similarity threshold to consider a duplicate.
        num_perm (int): Number of permutations for MinHash.
        k (int): Shingle size.

    Returns:
        dict: A dictionary containing duplicate pairs and statistics.
    """
    
    # Initialize MinHash LSH index
    # Jaccard similarity threshold
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm) 
    
    file_hashes = {}
    files_analyzed = 0

    # First pass: Iterate files, create MinHash, and insert into LSH
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in [".py", ".js", ".ts", ".java"]:
                filepath = os.path.join(root, file)
                
                # Apply exclusions
                if exclude_third_party and is_third_party_file(filepath, repo_path):
                    continue
                if exclude_tests and is_test_file(filepath, repo_path):
                    continue
                
                files_analyzed += 1
                rel_path = os.path.relpath(filepath, repo_path)
                
                try:
                    with open(filepath, "r", errors="ignore") as f:
                        content = f.read()
                    
                    # Create MinHash for the file
                    m = MinHash(num_perm=num_perm)
                    shingles = get_shingles(content, k=k)
                    if not shingles:
                        continue # Skip empty files
                        
                    for s in shingles:
                        m.update(s.encode('utf8'))
                    
                    # Store the hash and insert into LSH
                    file_hashes[rel_path] = m
                    lsh.insert(rel_path, m)
                
                except Exception as e:
                    print(f"Error hashing file {rel_path}: {e}")

    # Second pass: Query LSH to find candidate pairs
    duplicate_pairs = []
    processed = set() # Avoid reporting (A,B) and (B,A)

    for rel_path, m in file_hashes.items():
        if rel_path in processed:
            continue
            
        # Find approximate neighbors
        candidates = lsh.query(m)
        
        for candidate in candidates:
            if candidate == rel_path or candidate in processed:
                continue
            
            # Verify similarity (LSH is approximate)
            m2 = file_hashes[candidate]
            similarity = m.jaccard(m2)
            
            if similarity >= threshold:
                duplicate_pairs.append({
                    "file_a": rel_path,
                    "file_b": candidate,
                    "similarity": round(similarity, 4)
                })
        
        processed.add(rel_path)

    return {
        "files_analyzed": files_analyzed,
        "duplicate_pairs_found": len(duplicate_pairs),
        "similarity_threshold": threshold,
        "shingle_size_k": k,
        "duplicates": duplicate_pairs
    }

# --- Simhash Analysis (Alternative) ---
# You could use this instead of MinHash. Simhash is good for
# near-duplicate detection based on Hamming distance.

from simhash import Simhash, SimhashIndex

def analyze_duplicates_simhash(
    repo_path, 
    exclude_third_party=True, 
    exclude_tests=True, 
    hamming_distance_k=3
):
    """Analyzes code duplication using Simhash."""
    
    file_hashes = {} # Store {rel_path: simhash_obj}
    
    # 1. Get features (tokens) from text
    def get_features(s):
        s = s.lower()
        s = re.sub(r'[^\w]+', '', s)
        width = 3
        return [s[i:i + width] for i in range(max(len(s) - width + 1, 1))]

    # 2. Iterate and hash files
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in [".py", ".js", ".ts", ".java"]:
                filepath = os.path.join(root, file)
                
                if exclude_third_party and is_third_party_file(filepath, repo_path):
                    continue
                if exclude_tests and is_test_file(filepath, repo_path):
                    continue
                
                rel_path = os.path.relpath(filepath, repo_path)
                try:
                    with open(filepath, "r", errors="ignore") as f:
                        content = f.read()
                    if not content.strip():
                        continue
                    
                    file_hashes[rel_path] = Simhash(get_features(content))
                except Exception:
                    pass

    # 3. Build index
    index = SimhashIndex(file_hashes.items(), k=hamming_distance_k)
    
    # 4. Find duplicates
    duplicate_pairs = []
    processed = set()
    
    for rel_path in file_hashes.keys():
        if rel_path in processed:
            continue
            
        near_dups = index.get_near_dups(file_hashes[rel_path])
        # near_dups will include the file itself, filter it out
        
        file_dups = []
        for dup_path in near_dups:
            if dup_path != rel_path and dup_path not in processed:
                file_dups.append(dup_path)
                processed.add(dup_path) # Mark as processed
        
        if file_dups:
             duplicate_pairs.append({
                 "file": rel_path,
                 "duplicates_found": file_dups
             })
        processed.add(rel_path)

    return {
        "files_analyzed": len(file_hashes),
        "duplicate_groups_found": len(duplicate_pairs),
        "hamming_distance_k": hamming_distance_k,
        "duplicates": duplicate_pairs
    }

