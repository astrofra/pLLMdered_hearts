import argparse
import json
import math
import os
import sys

def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)

def extract_source_embeddings(data):
    if isinstance(data, list):
        if not data:
            return []
        first = data[0]
        if isinstance(first, dict) and "embedding" in first:
            return [item["embedding"] for item in data]
        if isinstance(first, list):
            return data
    raise ValueError("Unsupported source embeddings format")

def extract_dest_embeddings(data):
    if not isinstance(data, list):
        raise ValueError("Destination embeddings should be a list")
    items = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Destination entries must be objects")
        if "timecode" not in item or "embedding" not in item:
            raise ValueError("Destination entries need timecode and embedding")
        items.append(item)
    return items

def dot_product(a, b):
    total = 0.0
    for x, y in zip(a, b):
        total += x * y
    return total

def l2_distance(a, b):
    total = 0.0
    for x, y in zip(a, b):
        diff = x - y
        total += diff * diff
    return math.sqrt(total)

def cosine_distance(a, b, a_norm, b_norm):
    if a_norm == 0.0 or b_norm == 0.0:
        return 1.0
    return 1.0 - (dot_product(a, b) / (a_norm * b_norm))

def find_matches(source_embeddings, dest_items, metric):
    dest_embeddings = [item["embedding"] for item in dest_items]
    dest_norms = None
    if metric == "cosine":
        dest_norms = [math.sqrt(dot_product(vec, vec)) for vec in dest_embeddings]

    results = []
    for src_index, src_vec in enumerate(source_embeddings):
        if metric == "cosine":
            src_norm = math.sqrt(dot_product(src_vec, src_vec))
        else:
            src_norm = None

        best_index = None
        best_distance = None
        for dest_index, dest_vec in enumerate(dest_embeddings):
            if metric == "cosine":
                distance = cosine_distance(src_vec, dest_vec, src_norm, dest_norms[dest_index])
            else:
                distance = l2_distance(src_vec, dest_vec)

            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_index = dest_index

        best_item = dest_items[best_index]
        results.append({
            "source_index": src_index,
            "timecode": best_item["timecode"],
            "destination_index": best_index,
            "distance": best_distance,
        })

    return results

def main():
    parser = argparse.ArgumentParser(description="Match source embeddings to nearest timecodes.")
    parser.add_argument("--source", default="assets/game-embeddings.json")
    parser.add_argument("--dest", default="www/static/video/abriggs-itw.embeddings.json")
    parser.add_argument("--output", default="assets/game-embeddings.closest-timecodes.json")
    parser.add_argument("--metric", choices=["cosine", "l2"], default="cosine")
    args = parser.parse_args()

    source_path = os.path.normpath(args.source)
    dest_path = os.path.normpath(args.dest)
    output_path = os.path.normpath(args.output)

    source_data = load_json(source_path)
    dest_data = load_json(dest_path)

    source_embeddings = extract_source_embeddings(source_data)
    dest_items = extract_dest_embeddings(dest_data)

    if not source_embeddings:
        print("Source embeddings are empty.", file=sys.stderr)
        return 1
    if not dest_items:
        print("Destination embeddings are empty.", file=sys.stderr)
        return 1

    results = find_matches(source_embeddings, dest_items, args.metric)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)

    print(f"Wrote {len(results)} matches to {output_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
