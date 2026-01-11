#!/usr/bin/env python3
"""
Greedy selection of top 5 architectures based on critical layer results.
Scoring: minimize DRAM accesses first, then energy, then cycles.
"""

import os
import sys
import csv
import json
from collections import defaultdict

def load_results(csv_file):
    """Load parsed results from CSV."""
    results = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            for key in ['total_energy', 'runtime_cycles', 'DRAM_accesses_ifmap',
                       'DRAM_accesses_filter', 'DRAM_accesses_ofmap', 'utilization_ratio']:
                if row.get(key):
                    try:
                        row[key] = float(row[key])
                    except (ValueError, TypeError):
                        row[key] = None
                else:
                    row[key] = None
            results.append(row)
    return results

def aggregate_architecture_metrics(results):
    """Aggregate metrics per architecture across all critical layers."""
    arch_metrics = defaultdict(lambda: {
        'total_dram_ifmap': 0.0,
        'total_dram_filter': 0.0,
        'total_dram_ofmap': 0.0,
        'total_energy': 0.0,
        'total_cycles': 0.0,
        'layers': []
    })
    
    for result in results:
        arch_name = result['arch_name']
        layer_name = result['layer_name']
        
        # Sum up metrics across layers
        if result['DRAM_accesses_ifmap'] is not None:
            arch_metrics[arch_name]['total_dram_ifmap'] += result['DRAM_accesses_ifmap']
        if result['DRAM_accesses_filter'] is not None:
            arch_metrics[arch_name]['total_dram_filter'] += result['DRAM_accesses_filter']
        if result['DRAM_accesses_ofmap'] is not None:
            arch_metrics[arch_name]['total_dram_ofmap'] += result['DRAM_accesses_ofmap']
        if result['total_energy'] is not None:
            arch_metrics[arch_name]['total_energy'] += result['total_energy']
        if result['runtime_cycles'] is not None:
            arch_metrics[arch_name]['total_cycles'] += result['runtime_cycles']
        
        arch_metrics[arch_name]['layers'].append(layer_name)
    
    return arch_metrics

def calculate_dram_total(metrics):
    """Calculate total DRAM accesses."""
    return (metrics['total_dram_ifmap'] or 0.0) + \
           (metrics['total_dram_filter'] or 0.0) + \
           (metrics['total_dram_ofmap'] or 0.0)

def score_architecture(arch_name, metrics):
    """Score an architecture for greedy selection.
    
    Lower is better. Scoring priority:
    1. Total DRAM accesses (most important)
    2. Total energy
    3. Total cycles
    
    Returns (score, dram_total, energy, cycles) tuple for sorting.
    """
    dram_total = calculate_dram_total(metrics)
    energy = metrics['total_energy'] or float('inf')
    cycles = metrics['total_cycles'] or float('inf')
    
    # Normalize and weight (DRAM most important)
    # Use a large multiplier for DRAM to ensure it dominates
    # Assuming DRAM values are in thousands-millions, energy in millions, cycles in millions
    # We'll use a simple weighted sum where DRAM has highest weight
    score = (
        dram_total * 1e6 +  # DRAM accesses scaled up (highest priority)
        energy * 1.0 +       # Energy (medium priority)
        cycles * 1e-3        # Cycles (lowest priority)
    )
    
    return (score, dram_total, energy, cycles)

def select_top_architectures(arch_metrics, top_k=5):
    """Select top K architectures based on greedy scoring."""
    scored_archs = []
    
    for arch_name, metrics in arch_metrics.items():
        score, dram_total, energy, cycles = score_architecture(arch_name, metrics)
        scored_archs.append({
            'arch_name': arch_name,
            'score': score,
            'total_dram_accesses': dram_total,
            'total_energy': energy,
            'total_cycles': cycles,
            'dram_ifmap': metrics['total_dram_ifmap'],
            'dram_filter': metrics['total_dram_filter'],
            'dram_ofmap': metrics['total_dram_ofmap'],
            'layers_evaluated': ', '.join(metrics['layers'])
        })
    
    # Sort by score (lower is better)
    scored_archs.sort(key=lambda x: (x['score'], x['total_dram_accesses'], 
                                     x['total_energy'], x['total_cycles']))
    
    return scored_archs[:top_k]

def main():
    """Main function."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    exp_dir = os.path.dirname(script_dir)
    results_dir = os.path.join(exp_dir, "results")
    
    input_csv = os.path.join(results_dir, "greedy_critical_layers.csv")
    output_csv = os.path.join(results_dir, "top5_archs.csv")
    
    if not os.path.exists(input_csv):
        print(f"ERROR: Input CSV not found: {input_csv}", file=sys.stderr)
        return 1
    
    print(f"Loading results from {input_csv}...")
    results = load_results(input_csv)
    
    if not results:
        print("ERROR: No results to process", file=sys.stderr)
        return 1
    
    print(f"Found {len(results)} result entries")
    
    # Aggregate by architecture
    arch_metrics = aggregate_architecture_metrics(results)
    print(f"Found {len(arch_metrics)} unique architectures")
    
    # Select top 5
    top_archs = select_top_architectures(arch_metrics, top_k=5)
    
    if not top_archs:
        print("ERROR: No architectures selected", file=sys.stderr)
        return 1
    
    # Write top 5 to CSV
    fieldnames = [
        'arch_name',
        'total_dram_accesses',
        'total_energy',
        'total_cycles',
        'dram_ifmap',
        'dram_filter',
        'dram_ofmap',
        'layers_evaluated',
        'score'
    ]
    
    os.makedirs(results_dir, exist_ok=True)
    
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(top_archs)
    
    print(f"\nTop 5 architectures:")
    print("=" * 100)
    for i, arch in enumerate(top_archs, 1):
        print(f"{i}. {arch['arch_name']}")
        print(f"   Total DRAM Accesses: {arch['total_dram_accesses']:.2e}")
        print(f"   Total Energy (pJ): {arch['total_energy']:.2e}")
        print(f"   Total Cycles: {arch['total_cycles']:.2e}")
        print(f"   Layers: {arch['layers_evaluated']}")
        print()
    
    print(f"Results saved to: {output_csv}")
    print(f"Best architecture: {top_archs[0]['arch_name']}")
    
    return 0

if __name__ == "__main__":
    exit(main())

