#!/usr/bin/env python3
"""
build_phylo_embeddings.py — Build phylogenetic distance embeddings for SINR v3.

Pipeline:
  1. Load species list from local PostgreSQL (50K species)
  2. Parse OToL v15.1 synthetic tree (labelled_supertree_ottnames.tre)
  3. Match species to tree tips
  4. Compute pairwise phylogenetic distances (path length)
  5. Run MDS (Multidimensional Scaling) to embed into ~32D continuous space
  6. Save embeddings as species_phylo_embeddings.npz

For unmatched species, we use genus-level centroids (average of matched congeners).

Usage:
  python3 build_phylo_embeddings.py --match-only    # Just show match stats
  python3 build_phylo_embeddings.py --build          # Build full embeddings
  python3 build_phylo_embeddings.py --build --dims 32  # Custom dimensionality
"""

import argparse
import json
import re
import time
import numpy as np
from datetime import datetime
from pathlib import Path
from collections import defaultdict

TREE_FILE = Path(__file__).parent / 'reference_datasets/phylo/opentree15.1_tree/labelled_supertree/labelled_supertree_ottnames.tre'
OUTPUT_DIR = Path(__file__).parent / 'sinr_training_data'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_species_from_db():
    """Load species scientific names from local PostgreSQL."""
    import psycopg2
    conn = psycopg2.connect(dbname='treekipedia')
    cur = conn.cursor()
    # Get species-level records (not subspecies) with their taxonomy
    cur.execute("""
        SELECT taxon_id, species_scientific_name, genus, family, taxonomic_order
        FROM species
        WHERE species_scientific_name IS NOT NULL
        AND species_scientific_name != ''
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    species = []
    for taxon_id, name, genus, family, order in rows:
        # Normalize: "Quercus robur" → "Quercus_robur"
        normalized = name.strip().replace(' ', '_')
        species.append({
            'taxon_id': taxon_id,
            'name': name.strip(),
            'normalized': normalized,
            'genus': (genus or '').strip(),
            'family': (family or '').strip(),
            'order': (order or '').strip(),
        })

    log(f"Loaded {len(species):,} species from database")
    return species


def parse_tree_tip_labels(tree_file):
    """Extract tip labels from Newick tree without loading full tree into memory.

    Labels are in format: Genus_species_ottNNNN
    We extract Genus_species → ott_id mapping.
    """
    log(f"Parsing tip labels from {tree_file.name} ({tree_file.stat().st_size / 1e6:.0f} MB)...")

    # Read the entire tree string
    with open(tree_file, 'r') as f:
        tree_str = f.read()

    # Extract all tip labels using regex
    # Tips are strings that appear before a colon or comma/paren, not containing those chars
    # In Newick: (A:0.1,B:0.2) — A and B are tips
    # OToL labels: Genus_species_ottNNN or higher_taxa_ottNNN

    # Find all label_ott patterns
    pattern = re.compile(r'([A-Z][a-z]+_[a-z][a-z_]+?)_ott(\d+)')

    tip_map = {}  # normalized_name → ott_id
    genus_tips = defaultdict(list)  # genus → [normalized_names]

    for match in pattern.finditer(tree_str):
        name = match.group(1)
        ott_id = int(match.group(2))
        tip_map[name] = ott_id

        # Track genus membership
        parts = name.split('_')
        if len(parts) >= 2:
            genus_tips[parts[0]].append(name)

    log(f"Found {len(tip_map):,} species-level tips in tree")
    log(f"Spanning {len(genus_tips):,} genera")

    del tree_str  # Free memory
    return tip_map, genus_tips


def match_species_to_tree(species_list, tip_map, genus_tips):
    """Match our species to tree tips."""

    matched = []      # (species_dict, ott_name)
    genus_only = []   # Species where only genus matches
    unmatched = []    # No match at all

    for sp in species_list:
        norm = sp['normalized']

        if norm in tip_map:
            matched.append((sp, norm))
        else:
            # Try genus match
            genus = sp['genus'] or sp['normalized'].split('_')[0]
            if genus in genus_tips and len(genus_tips[genus]) > 0:
                genus_only.append((sp, genus))
            else:
                unmatched.append(sp)

    log(f"\nMatch Results:")
    log(f"  Direct match:  {len(matched):>8,} ({100*len(matched)/len(species_list):.1f}%)")
    log(f"  Genus fallback: {len(genus_only):>7,} ({100*len(genus_only)/len(species_list):.1f}%)")
    log(f"  Unmatched:     {len(unmatched):>8,} ({100*len(unmatched)/len(species_list):.1f}%)")

    return matched, genus_only, unmatched


def build_distance_matrix_dendropy(tree_file, target_tips, sample_size=5000):
    """Build pairwise phylogenetic distance matrix using DendroPy.

    For computational tractability, if we have > sample_size tips,
    we sample a representative subset and project the rest.

    Strategy for large datasets:
    - If <= sample_size matched tips: compute full distance matrix
    - If > sample_size: sample representative tips (stratified by genus),
      compute distances for sample, project others via nearest-genus centroids
    """
    import dendropy

    n_tips = len(target_tips)
    log(f"\nBuilding distance matrix for {n_tips:,} tips...")

    if n_tips > sample_size:
        log(f"Too many tips for full pairwise ({n_tips}×{n_tips}). Sampling {sample_size}...")
        # Stratified sampling: keep proportional genus representation
        genus_groups = defaultdict(list)
        for tip_name in target_tips:
            genus = tip_name.split('_')[0]
            genus_groups[genus].append(tip_name)

        sampled = []
        # Ensure at least 1 per genus (up to a limit)
        for genus, tips in genus_groups.items():
            sampled.append(tips[0])  # Always keep at least one per genus

        # Fill remaining slots randomly
        remaining_budget = sample_size - len(sampled)
        if remaining_budget > 0:
            all_remaining = [t for t in target_tips if t not in set(sampled)]
            np.random.seed(42)
            if len(all_remaining) > remaining_budget:
                extra = list(np.random.choice(all_remaining, remaining_budget, replace=False))
            else:
                extra = all_remaining
            sampled.extend(extra)

        sampled = list(set(sampled))[:sample_size]
        log(f"Sampled {len(sampled):,} tips across {len(genus_groups):,} genera")
        compute_tips = sampled
        all_target_tips = target_tips
    else:
        compute_tips = target_tips
        all_target_tips = target_tips

    # Load and prune tree
    log("Loading Newick tree with DendroPy (this may take a few minutes)...")
    t0 = time.time()
    tree = dendropy.Tree.get(
        path=str(tree_file),
        schema="newick",
        preserve_underscores=True
    )
    log(f"Tree loaded in {time.time()-t0:.0f}s — {len(tree.leaf_nodes()):,} total tips")

    # Build label → node mapping
    log("Building label index...")
    label_to_node = {}
    for leaf in tree.leaf_node_iter():
        if leaf.taxon:
            # Extract Genus_species from Genus_species_ottNNN
            label = leaf.taxon.label
            match = re.match(r'([A-Z][a-z]+_[a-z][a-z_]+?)_ott\d+', label)
            if match:
                label_to_node[match.group(1)] = leaf

    log(f"Indexed {len(label_to_node):,} species tips")

    # Filter to tips that exist in the tree
    valid_tips = [t for t in compute_tips if t in label_to_node]
    log(f"Found {len(valid_tips):,}/{len(compute_tips):,} compute tips in tree")

    if len(valid_tips) < 100:
        log("ERROR: Too few tips matched. Check label format.")
        return None, None, None

    # Create taxon set for pruning
    log(f"Computing pairwise distances for {len(valid_tips):,} tips...")

    # Use DendroPy's PhylogeneticDistanceMatrix
    t0 = time.time()

    # Prune tree to our tips for faster distance computation
    keep_taxa = set()
    for tip_name in valid_tips:
        node = label_to_node[tip_name]
        if node.taxon:
            keep_taxa.add(node.taxon)

    log(f"Pruning tree to {len(keep_taxa):,} taxa...")
    tree.retain_taxa(keep_taxa)
    log(f"Pruned in {time.time()-t0:.0f}s — {len(tree.leaf_nodes()):,} tips remaining")

    # OToL synthetic tree has NO branch lengths — use topological distance
    # (number of edges on the path between two tips)
    # First, assign unit branch lengths so DendroPy distance works
    log("Assigning unit branch lengths (topology-only tree)...")
    for edge in tree.preorder_edge_iter():
        edge.length = 1.0

    log("Computing phylogenetic distance matrix (topological)...")
    t0 = time.time()
    pdm = tree.phylogenetic_distance_matrix()
    log(f"Distance matrix computed in {time.time()-t0:.0f}s")

    # Extract distances into numpy array
    log("Extracting distance array...")
    taxon_to_name = {}
    for tip_name in valid_tips:
        node = label_to_node.get(tip_name)
        if node and node.taxon:
            taxon_to_name[node.taxon] = tip_name

    ordered_taxa = [t for t in pdm if t in taxon_to_name]
    ordered_names = [taxon_to_name[t] for t in ordered_taxa]
    n = len(ordered_names)

    dist_matrix = np.zeros((n, n), dtype=np.float32)
    for i, t1 in enumerate(ordered_taxa):
        for j, t2 in enumerate(ordered_taxa):
            if i < j:
                d = pdm(t1, t2)
                dist_matrix[i, j] = d
                dist_matrix[j, i] = d
        if (i + 1) % 500 == 0:
            log(f"  Distances: {i+1}/{n} rows...")

    log(f"Distance matrix: {n}×{n}, range [{dist_matrix[dist_matrix>0].min():.2f}, {dist_matrix.max():.2f}]")

    return dist_matrix, ordered_names, all_target_tips


def compute_mds_embeddings(dist_matrix, names, n_dims=32):
    """Run MDS to embed phylogenetic distances into continuous space."""
    from sklearn.manifold import MDS

    n = len(names)
    log(f"\nRunning MDS: {n} species → {n_dims}D embeddings...")

    # Use metric MDS with precomputed distances
    mds = MDS(
        n_components=n_dims,
        dissimilarity='precomputed',
        random_state=42,
        n_init=4,
        max_iter=300,
        n_jobs=-1,
        normalized_stress='auto'
    )

    t0 = time.time()
    embeddings = mds.fit_transform(dist_matrix)
    stress = mds.stress_
    log(f"MDS completed in {time.time()-t0:.0f}s — stress: {stress:.4f}")

    return embeddings


def assign_genus_embeddings(matched_names, matched_embeddings, genus_species, all_species):
    """Assign embeddings to genus-only and unmatched species.

    Strategy:
    - Genus-only match: average of all matched congeners' embeddings
    - Unmatched: average of family-level embeddings, or global mean
    """
    n_dims = matched_embeddings.shape[1]

    # Build genus → embeddings mapping
    genus_embs = defaultdict(list)
    name_to_emb = {}
    for name, emb in zip(matched_names, matched_embeddings):
        genus = name.split('_')[0]
        genus_embs[genus].append(emb)
        name_to_emb[name] = emb

    # Compute genus centroids
    genus_centroids = {}
    for genus, embs in genus_embs.items():
        genus_centroids[genus] = np.mean(embs, axis=0)

    # Global mean for completely unmatched
    global_mean = np.mean(matched_embeddings, axis=0)

    # Assign embeddings to all species
    all_embeddings = {}
    stats = {'direct': 0, 'genus': 0, 'global': 0}

    for sp in all_species:
        norm = sp['normalized']
        if norm in name_to_emb:
            all_embeddings[sp['taxon_id']] = name_to_emb[norm]
            stats['direct'] += 1
        else:
            genus = sp['genus'] or norm.split('_')[0]
            if genus in genus_centroids:
                all_embeddings[sp['taxon_id']] = genus_centroids[genus]
                stats['genus'] += 1
            else:
                all_embeddings[sp['taxon_id']] = global_mean
                stats['global'] += 1

    log(f"\nEmbedding assignment:")
    log(f"  Direct match:    {stats['direct']:>8,}")
    log(f"  Genus centroid:  {stats['genus']:>8,}")
    log(f"  Global mean:     {stats['global']:>8,}")
    log(f"  Total:           {sum(stats.values()):>8,}")

    return all_embeddings


def main():
    parser = argparse.ArgumentParser(description='Build phylogenetic embeddings for SINR v3')
    parser.add_argument('--match-only', action='store_true', help='Just show match statistics')
    parser.add_argument('--build', action='store_true', help='Build full embeddings')
    parser.add_argument('--dims', type=int, default=32, help='Embedding dimensionality (default: 32)')
    parser.add_argument('--sample-size', type=int, default=5000, help='Max tips for full distance computation')
    args = parser.parse_args()

    if not args.match_only and not args.build:
        parser.print_help()
        return

    # Step 1: Load species from DB
    species_list = load_species_from_db()

    # Step 2: Parse tree tip labels
    tip_map, genus_tips = parse_tree_tip_labels(TREE_FILE)

    # Step 3: Match
    matched, genus_only, unmatched = match_species_to_tree(species_list, tip_map, genus_tips)

    if args.match_only:
        # Show some examples
        log("\nSample matched species:")
        for sp, name in matched[:10]:
            log(f"  {sp['name']} → {name} (ott{tip_map[name]})")
        log("\nSample genus-only matches:")
        for sp, genus in genus_only[:10]:
            log(f"  {sp['name']} → genus {genus} ({len(genus_tips[genus])} congeners in tree)")
        log("\nSample unmatched:")
        for sp in unmatched[:10]:
            log(f"  {sp['name']} (genus: {sp['genus']}, family: {sp['family']})")
        return

    if args.build:
        # Step 4: Build distance matrix
        target_tips = [name for _, name in matched]
        dist_matrix, ordered_names, all_targets = build_distance_matrix_dendropy(
            TREE_FILE, target_tips, sample_size=args.sample_size
        )

        if dist_matrix is None:
            log("Failed to build distance matrix. Exiting.")
            return

        # Step 5: MDS embeddings
        embeddings = compute_mds_embeddings(dist_matrix, ordered_names, n_dims=args.dims)

        # Step 6: Assign to all species (including genus fallback)
        all_embeddings = assign_genus_embeddings(
            ordered_names, embeddings, genus_only, species_list
        )

        # Step 7: Save
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_file = OUTPUT_DIR / 'species_phylo_embeddings.npz'

        taxon_ids = list(all_embeddings.keys())
        emb_array = np.array([all_embeddings[tid] for tid in taxon_ids], dtype=np.float32)

        np.savez_compressed(
            output_file,
            taxon_ids=np.array(taxon_ids),
            embeddings=emb_array,
            dims=args.dims,
            n_species=len(taxon_ids),
        )

        log(f"\nSaved to {output_file}")
        log(f"Shape: {emb_array.shape} ({emb_array.nbytes / 1e6:.1f} MB)")

        # Also save a JSON mapping for easy lookup
        mapping_file = OUTPUT_DIR / 'species_phylo_mapping.json'
        mapping = {tid: emb.tolist() for tid, emb in all_embeddings.items()}
        with open(mapping_file, 'w') as f:
            json.dump(mapping, f)
        log(f"Saved mapping to {mapping_file} ({mapping_file.stat().st_size / 1e6:.1f} MB)")


if __name__ == '__main__':
    main()
