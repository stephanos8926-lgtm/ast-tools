ts_rows = conn.execute(fts_sql, params).fetchall()
    fts_results = [(row['symbol_id'], row['score']) for row in fts_rows]
    
    # 4. Reciprocal Rank Fusion
    fused_scores = {}
    
    # Vector results: rank by distance (lower = better)
    for i, (symbol_id, distance) in enumerate(vec_results):
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (i + 1 + RRF_K)
    
    # FTS5 results: rank by BM25 score (lower = better)
    for i, (symbol_id, score) in enumerate(fts_results):
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (i + 1 + RRF_K)
    
    # 5. Sort by fused score (higher = better)
    top_k = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:k]
    
    # 6. Fetch full symbol details
    symbols = []
    if top_k:
        placeholders = ",".join("?" for _ in top_k)
        symbol_ids = [sid for sid, _ in top_k]
        rows = conn.execute(
            f"SELECT * FROM symbols WHERE id IN ({placeholders})",
            symbol_ids
        ).fetchall()
        
        row_map = {row['id']: dict(row) for row in rows}
        for symbol_id, fused_score in top_k:
            if symbol_id in row_map:
                symbol = row_map[symbol_id]
                symbol['relevance_score'] = fused_score
                symbols.append(symbol)
    
    return symbols