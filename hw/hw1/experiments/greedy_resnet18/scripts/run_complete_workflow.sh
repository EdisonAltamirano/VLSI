#!/bin/bash
# Complete workflow for greedy ResNet-18 architecture exploration
# Runs all steps: sweep, parse, selection, full network evaluation, summary

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "GREEDY RESNET-18 ARCHITECTURE EXPLORATION"
echo "=========================================="
echo ""

# Step 1: Run greedy sweep
echo "STEP 1: Running greedy sweep on critical layers..."
echo "---------------------------------------------------"
bash "$SCRIPT_DIR/run_greedy_sweep.sh"
echo ""

# Step 2: Parse results
echo "STEP 2: Parsing results..."
echo "---------------------------------------------------"
python3 "$SCRIPT_DIR/parse_results.py"
echo ""

# Step 3: Greedy selection
echo "STEP 3: Selecting top 5 architectures..."
echo "---------------------------------------------------"
python3 "$SCRIPT_DIR/greedy_selection.py"
echo ""

# Step 4: Full network evaluation
echo "STEP 4: Running full network evaluation on best architecture..."
echo "---------------------------------------------------"
python3 "$SCRIPT_DIR/run_full_network.py"
echo ""

# Step 5: Generate final summary
echo "STEP 5: Generating final summary..."
echo "---------------------------------------------------"
python3 "$SCRIPT_DIR/generate_final_summary.py"
echo ""

echo "=========================================="
echo "WORKFLOW COMPLETED SUCCESSFULLY!"
echo "=========================================="
echo ""
echo "Results saved to: $EXP_DIR/results/"
echo "  - greedy_critical_layers.csv: All critical layer results"
echo "  - top5_archs.csv: Top 5 architectures"
echo "  - final_per_layer.csv: Full network per-layer results"
echo "  - final_best_arch_summary.txt: Full network summary"
echo "  - FINAL_SUMMARY.txt: Complete summary with baseline comparison"
echo ""

