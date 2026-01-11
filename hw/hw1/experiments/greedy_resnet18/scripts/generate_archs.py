#!/usr/bin/env python3
"""
Generate architecture JSON files for greedy sweep.
Explores:
- PEs: [64, 256]
- RF capacity: [128, 256, 512] bytes
- Buffer capacity: [32768, 65536, 131072, 262144, 524288] bytes (32KB, 64KB, 128KB, 256KB, 512KB)
"""

import json
import os

# RF access costs (bytes -> pJ)
RF_COSTS = {
    128: 0.24,
    256: 0.48,
    512: 0.96
}

# Buffer access costs (bytes -> pJ)
BUFFER_COSTS = {
    32768: 12.0,     # 32KB
    65536: 16.9,     # 64KB
    131072: 20.2,    # 128KB
    262144: 30.4,    # 256KB
    524288: 45.6     # 512KB
}

# DRAM is fixed
DRAM_CAPACITY = 1073741824  # bytes
DRAM_COST = 200  # pJ

# Parallel costs
PARALLEL_COST = 0.035

# Precision
PRECISION = 16

# Exploration space
# NOTE: PE=1024 is incompatible with C|K dataflow schedule (causes TypeError in optimizer)
# Only exploring PE=64 and PE=256 which work with the schedule
PE_COUNTS = [64, 256, 1024]  # Removed 1024 due to schedule incompatibility
RF_CAPACITIES = [128, 256, 512]
BUFFER_CAPACITIES = [32768, 65536, 131072, 262144, 524288]  # 32KB, 64KB, 128KB, 256KB, 512KB
# Total designs: 2 × 3 × 5 = 30 architectures

def generate_arch_file(pe_count, rf_capacity, buffer_capacity, output_dir):
    """Generate a single architecture JSON file."""
    
    if rf_capacity not in RF_COSTS:
        raise ValueError(f"Invalid RF capacity: {rf_capacity}")
    if buffer_capacity not in BUFFER_COSTS:
        raise ValueError(f"Invalid buffer capacity: {buffer_capacity}")
    
    arch = {
        "mem_levels": 3,
        "capacity": [rf_capacity, buffer_capacity, DRAM_CAPACITY],
        "access_cost": [RF_COSTS[rf_capacity], BUFFER_COSTS[buffer_capacity], DRAM_COST],
        "parallel_count": [pe_count, 1, 1],
        "parallel_cost": [PARALLEL_COST],
        "precision": PRECISION
    }
    
    filename = f"arch_pe{pe_count}_rf{rf_capacity}_buf{buffer_capacity}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w') as f:
        json.dump(arch, f, indent=2)
    
    return filepath

def main():
    """Generate all architecture files (30 total: 2 PEs × 3 RFs × 5 Buffers)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    exp_dir = os.path.dirname(script_dir)
    arch_sweep_dir = os.path.join(exp_dir, "arch_sweep")
    
    # Ensure directory exists
    os.makedirs(arch_sweep_dir, exist_ok=True)
    
    generated = []
    for pe in PE_COUNTS:
        for rf in RF_CAPACITIES:
            for buf in BUFFER_CAPACITIES:
                filepath = generate_arch_file(pe, rf, buf, arch_sweep_dir)
                generated.append(filepath)
                print(f"Generated: {os.path.basename(filepath)}")
    
    print(f"\nGenerated {len(generated)} architecture files in {arch_sweep_dir}")

if __name__ == "__main__":
    main()

