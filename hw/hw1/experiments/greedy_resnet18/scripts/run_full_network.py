#!/usr/bin/env python3
"""
Run evaluation on the best architecture from greedy selection using alex_conv3_batch16.
Generates per-layer and summary results.
"""

import os
import sys
import csv
import json
import subprocess
import glob
from pathlib import Path

def find_best_architecture(results_dir):
    """Find the best architecture from top5_archs.csv."""
    top5_csv = os.path.join(results_dir, "top5_archs.csv")
    
    if not os.path.exists(top5_csv):
        print(f"ERROR: Top 5 architectures CSV not found: {top5_csv}", file=sys.stderr)
        return None
    
    with open(top5_csv, 'r') as f:
        reader = csv.DictReader(f)
        first_row = next(reader, None)
        if first_row:
            return first_row['arch_name']
    
    return None

def find_test_layer(examples_dir):
    """Find the test layer file (alex_conv3_batch16.json)."""
    layer_file = "alex_conv3_batch16.json"
    layer_path = os.path.join(examples_dir, "layer", layer_file)
    
    if os.path.exists(layer_path):
        return [layer_file]
    else:
        return []

def run_full_network_evaluation(arch_name, exp_dir, project_root):
    """Run optimizer for all ResNet-18 layers with the best architecture."""
    arch_file = os.path.join(exp_dir, "arch_sweep", f"{arch_name}.json")
    tools_dir = os.path.join(project_root, "tools")
    examples_dir = os.path.join(project_root, "examples")
    schedule_file = os.path.join(examples_dir, "schedule", "dataflow_C_K.json")
    results_dir = os.path.join(exp_dir, "results")
    logs_dir = os.path.join(results_dir, "logs")
    full_network_logs_dir = os.path.join(logs_dir, "full_network")
    
    os.makedirs(full_network_logs_dir, exist_ok=True)
    
    if not os.path.exists(arch_file):
        print(f"ERROR: Architecture file not found: {arch_file}", file=sys.stderr)
        return None
    
    # Check if we already have results from the sweep
    layer_basename = "alex_conv3_batch16"
    existing_log = os.path.join(logs_dir, f"{arch_name}_{layer_basename}.txt")
    target_log = os.path.join(full_network_logs_dir, f"{arch_name}_{layer_basename}.txt")
    
    print(f"Evaluating architecture: {arch_name}")
    print(f"Test layer: {layer_basename}")
    print("")
    
    results = []
    
    # If log file already exists from sweep, copy it instead of re-running
    if os.path.exists(existing_log) and os.path.getsize(existing_log) > 0:
        print(f"Using existing results from sweep...")
        import shutil
        os.makedirs(full_network_logs_dir, exist_ok=True)
        shutil.copy2(existing_log, target_log)
        print(f"  [OK] Copied existing log file")
        results.append({
            'arch_name': arch_name,
            'layer_name': layer_basename,
            'log_file': target_log,
            'success': True
        })
    else:
        # Need to run optimizer
        layer_file = "alex_conv3_batch16.json"
        layer_path = os.path.join(examples_dir, "layer", layer_file)
        
        if not os.path.exists(layer_path):
            print(f"ERROR: Test layer file not found: {layer_path}", file=sys.stderr)
            return None
        
        # Change to project root for relative paths
        original_dir = os.getcwd()
        os.chdir(project_root)
        
        try:
            log_file = target_log
            os.makedirs(full_network_logs_dir, exist_ok=True)
            
            # Use relative paths from project root
            arch_rel = f"experiments/greedy_resnet18/arch_sweep/{arch_name}.json"
            layer_rel = f"examples/layer/{layer_file}"
            schedule_rel = "examples/schedule/dataflow_C_K.json"
            
            print(f"Running optimizer...")
            
            try:
                # Run optimizer - capture output to file
                with open(log_file, 'w') as log_f:
                    result = subprocess.run(
                        [sys.executable, os.path.join(tools_dir, "run_optimizer.py"),
                         "basic", arch_rel, layer_rel, "-s", schedule_rel, "-v"],
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        cwd=project_root,
                        timeout=300  # 5 minute timeout
                    )
                
                if result.returncode == 0:
                    print(f"  [OK] Completed")
                    results.append({
                        'arch_name': arch_name,
                        'layer_name': layer_basename,
                        'log_file': log_file,
                        'success': True
                    })
                else:
                    print(f"  [FAIL] Failed with exit code {result.returncode}")
                    # Check log file for errors
                    if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
                        with open(log_file, 'r') as f:
                            log_content = f.read()
                            if 'Traceback' in log_content:
                                print(f"  Error details in: {log_file}")
                    results.append({
                        'arch_name': arch_name,
                        'layer_name': layer_basename,
                        'log_file': log_file,
                        'success': False
                    })
            
            except subprocess.TimeoutExpired:
                print(f"  [FAIL] Timeout after 5 minutes")
                results.append({
                    'arch_name': arch_name,
                    'layer_name': layer_basename,
                    'log_file': log_file,
                    'success': False
                })
            except Exception as e:
                print(f"  [FAIL] Error: {e}")
                results.append({
                    'arch_name': arch_name,
                    'layer_name': layer_basename,
                    'log_file': log_file,
                    'success': False
                })
        
        finally:
            os.chdir(original_dir)
    
    return results

def parse_evaluation_results(logs_dir, arch_name):
    """Parse results from evaluation logs."""
    # Reuse the parse_results.py logic
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    parse_results_path = os.path.join(scripts_dir, "parse_results.py")
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("parse_results", parse_results_path)
    parse_results_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parse_results_module)
    parse_log_file = parse_results_module.parse_log_file
    
    # Look for log files with the architecture name
    log_files = glob.glob(os.path.join(logs_dir, f"{arch_name}_*.txt"))
    
    parsed_results = []
    for log_file in sorted(log_files):
        result = parse_log_file(log_file)
        if result:
            parsed_results.append(result)
    
    return parsed_results

def main():
    """Main function."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    exp_dir = os.path.dirname(script_dir)
    # project_root is hw1 directory (2 levels up from exp_dir: experiments/greedy_resnet18 -> experiments -> hw1)
    project_root = os.path.dirname(os.path.dirname(exp_dir))
    results_dir = os.path.join(exp_dir, "results")
    logs_dir = os.path.join(results_dir, "logs")
    full_network_logs_dir = os.path.join(logs_dir, "full_network")
    
    # Find best architecture
    arch_name = find_best_architecture(results_dir)
    if not arch_name:
        print("ERROR: Could not find best architecture. Run greedy_selection.py first.", file=sys.stderr)
        return 1
    
    print(f"Best architecture from greedy selection: {arch_name}")
    print("")
    
    # Run evaluation on best architecture
    run_results = run_full_network_evaluation(arch_name, exp_dir, project_root)
    
    if not run_results:
        print("ERROR: Evaluation failed", file=sys.stderr)
        return 1
    
    # Parse results
    print("\nParsing results...")
    
    # Get the full_network_logs_dir from the run results
    full_network_logs_dir = os.path.join(results_dir, "logs", "full_network")
    parsed_results = parse_evaluation_results(full_network_logs_dir, arch_name)
    
    if not parsed_results:
        print("ERROR: No results parsed", file=sys.stderr)
        return 1
    
    # Write per-layer CSV
    per_layer_csv = os.path.join(results_dir, "final_per_layer.csv")
    fieldnames = [
        'arch_name', 'layer_name', 'total_energy', 'runtime_cycles',
        'DRAM_accesses_ifmap', 'DRAM_accesses_filter', 'DRAM_accesses_ofmap',
        'utilization_ratio'
    ]
    
    with open(per_layer_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(parsed_results)
    
    # Aggregate totals (for single layer, these are just the layer values)
    total_energy = sum(r['total_energy'] or 0.0 for r in parsed_results)
    total_cycles = sum(r['runtime_cycles'] or 0.0 for r in parsed_results)
    total_dram_ifmap = sum(r['DRAM_accesses_ifmap'] or 0.0 for r in parsed_results)
    total_dram_filter = sum(r['DRAM_accesses_filter'] or 0.0 for r in parsed_results)
    total_dram_ofmap = sum(r['DRAM_accesses_ofmap'] or 0.0 for r in parsed_results)
    total_dram = total_dram_ifmap + total_dram_filter + total_dram_ofmap
    
    # Write summary
    summary_file = os.path.join(results_dir, "final_best_arch_summary.txt")
    with open(summary_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("Best Architecture Evaluation Summary (alex_conv3_batch16)\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Best Architecture: {arch_name}\n")
        f.write(f"Layer Evaluated: alex_conv3_batch16\n\n")
        f.write("Metrics:\n")
        f.write(f"  Total Energy (pJ): {total_energy:.2e}\n")
        f.write(f"  Total Runtime (cycles): {total_cycles:.2e}\n")
        f.write(f"  Total DRAM Accesses: {total_dram:.2e}\n")
        f.write(f"    - DRAM IFMAP Accesses: {total_dram_ifmap:.2e}\n")
        f.write(f"    - DRAM Filter Accesses: {total_dram_filter:.2e}\n")
        f.write(f"    - DRAM OFMAP Accesses: {total_dram_ofmap:.2e}\n\n")
        f.write(f"Per-layer results saved to: {per_layer_csv}\n")
        f.write("=" * 80 + "\n")
    
    print(f"\nEvaluation completed!")
    print(f"  Total Energy (pJ): {total_energy:.2e}")
    print(f"  Total Runtime (cycles): {total_cycles:.2e}")
    print(f"  Total DRAM Accesses: {total_dram:.2e}")
    print(f"\nResults saved to:")
    print(f"  Summary: {summary_file}")
    print(f"  Per-layer CSV: {per_layer_csv}")
    
    return 0

if __name__ == "__main__":
    exit(main())

