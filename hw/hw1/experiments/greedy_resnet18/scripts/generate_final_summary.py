#!/usr/bin/env python3
"""
Generate final summary comparing best architecture to baseline.
"""

import os
import csv
import json
import sys

def load_baseline_metrics(baseline_arch_file, examples_dir, project_root, tools_dir):
    """Run baseline architecture on critical layers to get baseline metrics."""
    critical_layers = [
        "resnet_gen_conv1_batch16.json",
        "resnet_gen_conv2_batch16.json",
        "resnet_gen_conv5_batch16.json",
        "resnet_gen_conv8_batch16.json",
    ]
    
    schedule_file = os.path.join(examples_dir, "schedule", "dataflow_C_K.json")
    total_energy = 0.0
    total_cycles = 0.0
    total_dram = 0.0
    
    print("Evaluating baseline architecture on critical layers...")
    
    # Import parse_log_file
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    parse_results_path = os.path.join(scripts_dir, "parse_results.py")
    import importlib.util
    spec = importlib.util.spec_from_file_location("parse_results", parse_results_path)
    parse_results_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parse_results_module)
    parse_log_file = parse_results_module.parse_log_file
    
    import subprocess
    import tempfile
    
    original_dir = os.getcwd()
    os.chdir(project_root)
    
    try:
        for layer_file in critical_layers:
            layer_path = os.path.join(examples_dir, "layer", layer_file)
            if not os.path.exists(layer_path):
                continue
            
            # Run optimizer
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
                tmp_file = tmp.name
            
            try:
                arch_rel = baseline_arch_file if os.path.isabs(baseline_arch_file) else baseline_arch_file
                layer_rel = f"examples/layer/{layer_file}"
                schedule_rel = "examples/schedule/dataflow_C_K.json"
                
                result = subprocess.run(
                    [sys.executable, os.path.join(tools_dir, "run_optimizer.py"),
                     "basic", arch_rel, layer_rel, "-s", schedule_rel, "-v"],
                    stdout=open(tmp_file, 'w'),
                    stderr=subprocess.STDOUT,
                    cwd=project_root,
                    timeout=300
                )
                
                if result.returncode == 0:
                    parsed = parse_log_file(tmp_file)
                    if parsed:
                        total_energy += parsed.get('total_energy', 0.0) or 0.0
                        total_cycles += parsed.get('runtime_cycles', 0.0) or 0.0
                        dram_ifmap = parsed.get('DRAM_accesses_ifmap', 0.0) or 0.0
                        dram_filter = parsed.get('DRAM_accesses_filter', 0.0) or 0.0
                        dram_ofmap = parsed.get('DRAM_accesses_ofmap', 0.0) or 0.0
                        total_dram += dram_ifmap + dram_filter + dram_ofmap
            finally:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
    
    finally:
        os.chdir(original_dir)
    
    return {
        'total_energy': total_energy,
        'total_cycles': total_cycles,
        'total_dram': total_dram
    }

def load_best_architecture_metrics(results_dir):
    """Load metrics from top5_archs.csv (best architecture)."""
    top5_csv = os.path.join(results_dir, "top5_archs.csv")
    
    if not os.path.exists(top5_csv):
        return None
    
    with open(top5_csv, 'r') as f:
        reader = csv.DictReader(f)
        first_row = next(reader, None)
        if first_row:
            return {
                'arch_name': first_row['arch_name'],
                'total_energy': float(first_row.get('total_energy', 0) or 0),
                'total_cycles': float(first_row.get('total_cycles', 0) or 0),
                'total_dram': float(first_row.get('total_dram_accesses', 0) or 0)
            }
    
    return None

def load_full_network_metrics(results_dir):
    """Load full network metrics from summary file."""
    summary_file = os.path.join(results_dir, "final_best_arch_summary.txt")
    
    if not os.path.exists(summary_file):
        return None
    
    metrics = {}
    with open(summary_file, 'r') as f:
        for line in f:
            if 'Total Energy (pJ):' in line:
                match = line.split(':')[1].strip()
                try:
                    metrics['total_energy'] = float(match.replace(',', ''))
                except:
                    pass
            elif 'Total Runtime (cycles):' in line:
                match = line.split(':')[1].strip()
                try:
                    metrics['total_cycles'] = float(match.replace(',', ''))
                except:
                    pass
            elif 'Total DRAM Accesses:' in line and 'IFMAP' not in line and 'Filter' not in line and 'OFMAP' not in line:
                match = line.split(':')[1].strip()
                try:
                    metrics['total_dram'] = float(match.replace(',', ''))
                except:
                    pass
    
    return metrics if metrics else None

def main():
    """Generate final summary."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    exp_dir = os.path.dirname(script_dir)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(exp_dir)))
    results_dir = os.path.join(exp_dir, "results")
    
    # Baseline architecture
    baseline_arch = os.path.join(project_root, "examples", "arch", "3_level_mem_basic_example.json")
    
    # Load best architecture metrics (from critical layers)
    best_arch_critical = load_best_architecture_metrics(results_dir)
    
    if not best_arch_critical:
        print("ERROR: Could not load best architecture metrics. Run greedy_selection.py first.", file=sys.stderr)
        return 1
    
    # Load full network metrics if available
    full_network_metrics = load_full_network_metrics(results_dir)
    
    # Try to get baseline metrics (optional, might take time)
    baseline_metrics = None
    try:
        examples_dir = os.path.join(project_root, "examples")
        tools_dir = os.path.join(project_root, "tools")
        baseline_rel = "examples/arch/3_level_mem_basic_example.json"
        baseline_metrics = load_baseline_metrics(
            baseline_rel, examples_dir, project_root, tools_dir
        )
    except Exception as e:
        print(f"WARNING: Could not compute baseline metrics: {e}", file=sys.stderr)
        # Use placeholder baseline (from the example file specs)
        baseline_metrics = {
            'total_energy': None,
            'total_cycles': None,
            'total_dram': None
        }
    
    # Generate summary
    summary_file = os.path.join(results_dir, "FINAL_SUMMARY.txt")
    
    with open(summary_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("GREEDY RESNET-18 ARCHITECTURE EXPLORATION - FINAL SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("BEST ARCHITECTURE (from critical layer evaluation):\n")
        f.write(f"  Name: {best_arch_critical['arch_name']}\n")
        f.write(f"  Critical Layers Total Energy (pJ): {best_arch_critical['total_energy']:.2e}\n")
        f.write(f"  Critical Layers Total Cycles: {best_arch_critical['total_cycles']:.2e}\n")
        f.write(f"  Critical Layers Total DRAM Accesses: {best_arch_critical['total_dram']:.2e}\n\n")
        
        if full_network_metrics:
            f.write("FULL NETWORK EVALUATION:\n")
            f.write(f"  Total Energy (pJ): {full_network_metrics.get('total_energy', 'N/A')}\n")
            f.write(f"  Total Cycles: {full_network_metrics.get('total_cycles', 'N/A')}\n")
            f.write(f"  Total DRAM Accesses: {full_network_metrics.get('total_dram', 'N/A')}\n\n")
        
        if baseline_metrics and baseline_metrics.get('total_energy') is not None:
            f.write("BASELINE ARCHITECTURE COMPARISON (critical layers):\n")
            f.write(f"  Baseline Total Energy (pJ): {baseline_metrics['total_energy']:.2e}\n")
            f.write(f"  Best Architecture Total Energy (pJ): {best_arch_critical['total_energy']:.2e}\n")
            
            if baseline_metrics['total_energy'] > 0:
                energy_improvement = ((baseline_metrics['total_energy'] - best_arch_critical['total_energy']) / baseline_metrics['total_energy']) * 100
                f.write(f"  Energy Improvement: {energy_improvement:.2f}%\n")
            
            f.write(f"\n  Baseline Total Cycles: {baseline_metrics['total_cycles']:.2e}\n")
            f.write(f"  Best Architecture Total Cycles: {best_arch_critical['total_cycles']:.2e}\n")
            
            if baseline_metrics['total_cycles'] > 0:
                cycles_improvement = ((baseline_metrics['total_cycles'] - best_arch_critical['total_cycles']) / baseline_metrics['total_cycles']) * 100
                f.write(f"  Cycles Improvement: {cycles_improvement:.2f}%\n")
            
            f.write(f"\n  Baseline Total DRAM Accesses: {baseline_metrics['total_dram']:.2e}\n")
            f.write(f"  Best Architecture Total DRAM Accesses: {best_arch_critical['total_dram']:.2e}\n")
            
            if baseline_metrics['total_dram'] > 0:
                dram_reduction = ((baseline_metrics['total_dram'] - best_arch_critical['total_dram']) / baseline_metrics['total_dram']) * 100
                f.write(f"  DRAM Traffic Reduction: {dram_reduction:.2f}%\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("Files Generated:\n")
        f.write(f"  - Top 5 architectures: {os.path.join(results_dir, 'top5_archs.csv')}\n")
        if full_network_metrics:
            f.write(f"  - Full network per-layer: {os.path.join(results_dir, 'final_per_layer.csv')}\n")
            f.write(f"  - Full network summary: {os.path.join(results_dir, 'final_best_arch_summary.txt')}\n")
        f.write("=" * 80 + "\n")
    
    # Print summary to stdout
    print("\n" + "=" * 80)
    print("GREEDY RESNET-18 ARCHITECTURE EXPLORATION - FINAL SUMMARY")
    print("=" * 80)
    print(f"\nBEST ARCHITECTURE: {best_arch_critical['arch_name']}")
    print(f"  Critical Layers Energy: {best_arch_critical['total_energy']:.2e} pJ")
    print(f"  Critical Layers Cycles: {best_arch_critical['total_cycles']:.2e}")
    print(f"  Critical Layers DRAM Accesses: {best_arch_critical['total_dram']:.2e}")
    
    if baseline_metrics and baseline_metrics.get('total_dram') is not None:
        if baseline_metrics['total_dram'] > 0:
            dram_reduction = ((baseline_metrics['total_dram'] - best_arch_critical['total_dram']) / baseline_metrics['total_dram']) * 100
            print(f"\nDRAM Traffic Reduction vs Baseline: {dram_reduction:.2f}%")
    
    if full_network_metrics:
        print(f"\nFull Network Evaluation:")
        print(f"  Total Energy: {full_network_metrics.get('total_energy', 'N/A')}")
        print(f"  Total Cycles: {full_network_metrics.get('total_cycles', 'N/A')}")
        print(f"  Total DRAM Accesses: {full_network_metrics.get('total_dram', 'N/A')}")
    
    print(f"\nFull summary saved to: {summary_file}")
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    exit(main())

