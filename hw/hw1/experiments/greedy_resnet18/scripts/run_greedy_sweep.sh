#!/bin/bash
# Architecture sweep for ResNet18 critical path analysis
# Iterates through all architecture files and runs optimizer for representative ResNet18 layers
# Representative layers: 1, 2, 3 (represents 3-5), 7 (represents 7-9), 11 (represents 11-13), 15 (represents 15-17), 18
# Results can be parsed to find the best architecture compared to baseline

set -e  # Exit on error

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Paths
ARCH_SWEEP_DIR="$EXP_DIR/arch_sweep"
RESULTS_DIR="$EXP_DIR/results"
LOGS_DIR="$RESULTS_DIR/logs"
TOOLS_DIR="$PROJECT_ROOT/tools"
EXAMPLES_DIR="$PROJECT_ROOT/examples"

# Representative ResNet18 layers for critical path analysis
# Layers 3, 7, 11, 15 represent identical architecture groups (3-5, 7-9, 11-13, 15-17)
CRITICAL_LAYERS=(
    "resnet_layer1_conv1_batch16.json"
    "resnet_layer2_conv2_1_1_batch16.json"
    "resnet_layer3_conv2_1_2_batch16.json"      # Represents layers 3-5
    "resnet_layer7_conv3_1_2_batch16.json"      # Represents layers 7-9
    "resnet_layer11_conv4_1_2_batch16.json"     # Represents layers 11-13
    "resnet_layer15_conv5_1_2_batch16.json"     # Represents layers 15-17
    "resnet_layer18_fc1000_batch16.json"
)

SCHEDULE_FILE="$EXAMPLES_DIR/schedule/dataflow_C_K.json"

# Create logs directory
mkdir -p "$LOGS_DIR"

# Check that required files exist
if [ ! -f "$SCHEDULE_FILE" ]; then
    echo "ERROR: Schedule file not found: $SCHEDULE_FILE" >&2
    exit 1
fi

if [ ! -d "$ARCH_SWEEP_DIR" ]; then
    echo "ERROR: Architecture sweep directory not found: $ARCH_SWEEP_DIR" >&2
    exit 1
fi

# Verify all critical layer files exist
for layer in "${CRITICAL_LAYERS[@]}"; do
    layer_path="$EXAMPLES_DIR/layer/$layer"
    if [ ! -f "$layer_path" ]; then
        echo "ERROR: Critical layer file not found: $layer_path" >&2
        exit 1
    fi
done

# Change to project root for relative paths
cd "$PROJECT_ROOT"

# Counter for tracking progress
total_archs=0
total_runs=0
successful_runs=0
failed_runs=0
failed_combinations=()

# Find all architecture JSON files
echo "Starting architecture sweep for ResNet18 critical path analysis..."
echo "Architecture directory: $ARCH_SWEEP_DIR"
echo "Critical layers: ${#CRITICAL_LAYERS[@]} representative layers"
echo "  - Layer 1 (conv1)"
echo "  - Layer 2 (conv2_1_1)"
echo "  - Layer 3 (represents layers 3-5)"
echo "  - Layer 7 (represents layers 7-9)"
echo "  - Layer 11 (represents layers 11-13)"
echo "  - Layer 15 (represents layers 15-17)"
echo "  - Layer 18 (fc1000)"
echo "Results directory: $LOGS_DIR"
echo ""

# Disable exit on error for the sweep loops since we want to continue even if some combinations fail
set +e

# Iterate through all architecture files
for arch_file in "$ARCH_SWEEP_DIR"/arch_*.json; do
    if [ ! -f "$arch_file" ]; then
        continue
    fi
    
    arch_basename=$(basename "$arch_file" .json)
    total_archs=$((total_archs + 1))
    
    echo "[Architecture $total_archs] Processing: $arch_basename"
    
    # Iterate through critical layers
    for test_layer in "${CRITICAL_LAYERS[@]}"; do
        total_runs=$((total_runs + 1))
        layer_basename=$(basename "$test_layer" .json)
        
        log_file="$LOGS_DIR/${arch_basename}_${layer_basename}.txt"
        
        # Check if this combination has already been successfully completed
        if [ -f "$log_file" ]; then
            # Check if log file contains successful completion marker
            if grep -q "Optimal_Energy_(pJ):" "$log_file" 2>/dev/null; then
                echo "  [$total_runs] Skipping (already completed): $layer_basename"
                successful_runs=$((successful_runs + 1))
                continue
            fi
            # If log file exists but doesn't have success marker, it's a failed run
            # We'll re-run it to try again
        fi
        
        echo "  [$total_runs] Running: $layer_basename -> $log_file"
        
        # Run optimizer with verbose output
        # Using relative paths from project root
        arch_rel_path="experiments/greedy_resnet18/arch_sweep/$(basename "$arch_file")"
        layer_rel_path="examples/layer/$test_layer"
        schedule_rel_path="examples/schedule/dataflow_C_K.json"
        
        # Run optimizer and capture all output
        # Use PIPESTATUS to get exit code after tee
        python3 "$TOOLS_DIR/run_optimizer.py" basic \
            "$arch_rel_path" \
            "$layer_rel_path" \
            -s "$schedule_rel_path" \
            -v 2>&1 | tee "$log_file"
        exit_code=${PIPESTATUS[0]}
        
        if [ $exit_code -eq 0 ]; then
            echo "      [OK] Completed successfully"
            successful_runs=$((successful_runs + 1))
        else
            echo "      [FAIL] Failed with exit code $exit_code" >&2
            failed_runs=$((failed_runs + 1))
            failed_combinations+=("${arch_basename} + ${layer_basename}")
            # Mark as failed in log file
            echo "OPTIMIZER_FAILED_EXIT_CODE=$exit_code" >> "$log_file"
            # Continue with next layer/architecture even if one fails
        fi
    done
    
    echo ""
done

# Re-enable exit on error after sweep loops complete
set -e

echo "=========================================="
echo "ResNet18 Critical Path Sweep Completed!"
echo "Total architectures evaluated: $total_archs"
echo "Critical layers per architecture: ${#CRITICAL_LAYERS[@]}"
echo "Total optimization runs: $total_runs"
echo "  Successful: $successful_runs"
echo "  Failed: $failed_runs"
if [ $failed_runs -gt 0 ]; then
    echo ""
    echo "Failed combinations (architecture + layer):"
    for combination in "${failed_combinations[@]}"; do
        echo "  - $combination"
    done
    echo ""
    echo "Note: Some layer-architecture combinations may fail due to resource constraints."
    echo "      This is expected behavior when resources are too constrained for certain layers."
fi
echo "Logs saved to: $LOGS_DIR"
echo "=========================================="

