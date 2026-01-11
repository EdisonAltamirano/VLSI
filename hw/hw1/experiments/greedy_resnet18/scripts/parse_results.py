#!/usr/bin/env python3
"""
Parse optimizer output logs and extract metrics into CSV.
Extracts:
- arch_name
- layer_name
- total_energy (pJ)
- runtime_cycles
- DRAM_accesses_ifmap
- DRAM_accesses_filter
- DRAM_accesses_ofmap
- utilization_ratio (if available)
- Tiles_Accessed_from DRAM counts
"""

import os
import sys
import re
import csv
import glob
from pathlib import Path

def parse_energy(line):
    """Parse Optimal_Energy_(pJ) line."""
    match = re.search(r'Optimal_Energy_\(pJ\):\s+([\d.eE+-]+)', line)
    if match:
        return float(match.group(1))
    return None

def parse_runtime_cycles(line):
    """Parse Runtime_(cycles) line."""
    match = re.search(r'Runtime_\(cycles\):\s*([\d.eE+-]+)', line)
    if match:
        return float(match.group(1))
    return None

def parse_tiles_accessed_block(lines, start_idx):
    """Parse Tiles_Accessed_from block.
    
    Format:
    Tiles_Accessed_from_[RegisterFile(s),Buffer,DRAM]_in_Layer:
        ifmap: [val1, val2, val3]
        ofmap: [val1, val2, val3]
        filter: [val1, val2, val3]
    
    Returns dict with DRAM values (index 2 for 3-level memory).
    """
    dram_accesses = {
        'ifmap': None,
        'ofmap': None,
        'filter': None
    }
    
    i = start_idx
    # Look ahead max 15 lines to find all three arrays
    # Format uses newline+tab: "\n\tifmap: [...]\n\tofmap: [...]\n\tfilter: [...]"
    while i < len(lines) and i < start_idx + 15:
        line = lines[i]  # Don't strip yet, we need to check for tabs
        line_stripped = line.strip()
        
        # Parse ifmap line - starts with tab after the header line
        if ('ifmap:' in line_stripped.lower() and 
            (line.startswith('\t') or '\tifmap:' in line)):
            match = re.search(r'ifmap:\s*\[([^\]]+)\]', line, re.IGNORECASE)
            if match:
                try:
                    values_str = match.group(1)
                    values = [float(x.strip()) for x in values_str.split(',')]
                    if len(values) >= 3:
                        dram_accesses['ifmap'] = values[2]  # DRAM is index 2 (0=RF, 1=Buffer, 2=DRAM)
                except (ValueError, IndexError):
                    pass
        
        # Parse ofmap line - starts with tab
        if ('ofmap:' in line_stripped.lower() and 
            (line.startswith('\t') or '\tofmap:' in line)):
            match = re.search(r'ofmap:\s*\[([^\]]+)\]', line, re.IGNORECASE)
            if match:
                try:
                    values_str = match.group(1)
                    values = [float(x.strip()) for x in values_str.split(',')]
                    if len(values) >= 3:
                        dram_accesses['ofmap'] = values[2]
                except (ValueError, IndexError):
                    pass
        
        # Parse filter line - starts with tab
        if ('filter:' in line_stripped.lower() and 
            'ifmap' not in line_stripped.lower() and
            (line.startswith('\t') or '\tfilter:' in line)):
            match = re.search(r'filter:\s*\[([^\]]+)\]', line, re.IGNORECASE)
            if match:
                try:
                    values_str = match.group(1)
                    values = [float(x.strip()) for x in values_str.split(',')]
                    if len(values) >= 3:
                        dram_accesses['filter'] = values[2]
                except (ValueError, IndexError):
                    pass
        
        i += 1
    
    return dram_accesses

def parse_utilization(lines):
    """Parse utilization ratio if available."""
    for line in lines:
        match = re.search(r'utilization[:\s]+([\d.]+)', line, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None

def parse_log_file(log_file):
    """Parse a single log file and extract metrics."""
    arch_name = None
    layer_name = None
    total_energy = None
    runtime_cycles = None
    dram_ifmap = None
    dram_ofmap = None
    dram_filter = None
    utilization_ratio = None
    
    # Extract arch_name and layer_name from filename
    basename = os.path.basename(log_file)
    # Format: arch_pe{PE}_rf{RF}_buf{BUF}_{layer}.txt or {arch}_{layer}.txt
    # Try to match various patterns: resnet_*, alex_*, etc.
    match = re.match(r'(.+?)_(resnet_.+|alex_.+)\.txt', basename)
    if match:
        arch_name = match.group(1)
        layer_name = match.group(2).replace('.json', '')
    else:
        # Fallback: try to extract from filename without specific pattern
        # Split on last underscore before .txt
        name_without_ext = basename.replace('.txt', '')
        parts = name_without_ext.rsplit('_', 1)
        if len(parts) == 2:
            arch_name = parts[0]
            layer_name = parts[1]
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Check if optimizer failed - look for error traces or explicit failure markers
        log_content = ''.join(lines)
        
        # Check for explicit failure marker
        if 'OPTIMIZER_FAILED_EXIT_CODE' in log_content:
            return None
        
        # Check for Python errors/tracebacks (but be careful - verbose output might mention "Error" in other contexts)
        if 'Traceback (most recent call last):' in log_content:
            # This is a real error, skip it
            return None
        
        # Check for TypeError in the optimizer code (the specific error we're seeing)
        if 'TypeError:' in log_content and 'partition_loops' in log_content:
            # Architecture/schedule incompatibility, skip it
            return None
        
        # Parse each line
        for i, line in enumerate(lines):
            # Parse energy
            if 'Optimal_Energy_(pJ)' in line:
                energy = parse_energy(line)
                if energy is not None:
                    total_energy = energy
            
            # Parse runtime cycles
            elif 'Runtime_(cycles)' in line:
                cycles = parse_runtime_cycles(line)
                if cycles is not None:
                    runtime_cycles = cycles
            
            # Parse DRAM accesses from Tiles_Accessed block
            # Format: "Tiles_Accessed_from_[RegisterFile(s),Buffer,DRAM]_in_Layer: \n\tifmap: [...]\n\tofmap: [...]\n\tfilter: [...]"
            elif 'Tiles_Accessed_from' in line and 'DRAM' in line and 'in_Layer' in line:
                dram_accesses = parse_tiles_accessed_block(lines, i)
                if dram_accesses['ifmap'] is not None:
                    dram_ifmap = dram_accesses['ifmap']
                if dram_accesses['ofmap'] is not None:
                    dram_ofmap = dram_accesses['ofmap']
                if dram_accesses['filter'] is not None:
                    dram_filter = dram_accesses['filter']
            
            # Parse utilization (optional)
            utilization = parse_utilization(lines)
            if utilization is not None:
                utilization_ratio = utilization
        
    except Exception as e:
        print(f"ERROR parsing {log_file}: {e}", file=sys.stderr)
        return None
    
    return {
        'arch_name': arch_name or 'unknown',
        'layer_name': layer_name or 'unknown',
        'total_energy': total_energy,
        'runtime_cycles': runtime_cycles,
        'DRAM_accesses_ifmap': dram_ifmap,
        'DRAM_accesses_filter': dram_filter,
        'DRAM_accesses_ofmap': dram_ofmap,
        'utilization_ratio': utilization_ratio
    }

def main():
    """Parse all log files and generate CSV."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    exp_dir = os.path.dirname(script_dir)
    logs_dir = os.path.join(exp_dir, "results", "logs")
    output_csv = os.path.join(exp_dir, "results", "greedy_critical_layers.csv")
    
    if not os.path.isdir(logs_dir):
        print(f"ERROR: Logs directory not found: {logs_dir}", file=sys.stderr)
        return 1
    
    # Find all log files
    log_files = glob.glob(os.path.join(logs_dir, "*.txt"))
    
    if not log_files:
        print(f"WARNING: No log files found in {logs_dir}", file=sys.stderr)
        return 1
    
    print(f"Parsing {len(log_files)} log files...")
    
    results = []
    failed_count = 0
    for log_file in sorted(log_files):
        result = parse_log_file(log_file)
        if result:
            results.append(result)
        else:
            failed_count += 1
            # Only print warning if it's not a known optimizer failure
            # (to avoid spam from expected failures)
            if failed_count <= 5:
                print(f"  WARNING: Skipping failed/incomplete run: {os.path.basename(log_file)}", file=sys.stderr)
    
    if failed_count > 5:
        print(f"  ... and {failed_count - 5} more failed runs (skipped)", file=sys.stderr)
    
    # Write CSV
    if not results:
        print("ERROR: No results to write", file=sys.stderr)
        return 1
    
    fieldnames = [
        'arch_name',
        'layer_name',
        'total_energy',
        'runtime_cycles',
        'DRAM_accesses_ifmap',
        'DRAM_accesses_filter',
        'DRAM_accesses_ofmap',
        'utilization_ratio'
    ]
    
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\nParsed {len(results)} results")
    print(f"Output CSV: {output_csv}")
    
    return 0

if __name__ == "__main__":
    exit(main())

