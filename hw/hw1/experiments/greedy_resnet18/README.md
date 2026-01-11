# Greedy ResNet-18 Architecture Exploration

This experiment implements a greedy methodology to find a close-to-optimal hardware architecture for ResNet-18.

## Overview

The workflow consists of:
1. **Critical Layer Evaluation**: Evaluate only critical layers (conv1, conv2_x rep, conv3_1, conv5_x rep) on 27 architectures
2. **Greedy Selection**: Select top 5 architectures based on DRAM accesses, energy, and cycles
3. **Full Network Evaluation**: Run complete ResNet-18 on the best architecture

## Directory Structure

```
experiments/greedy_resnet18/
├── arch_sweep/          # Generated architecture JSON files (27 files)
├── results/
│   ├── logs/            # Optimizer output logs
│   │   └── full_network/ # Full network evaluation logs
│   ├── greedy_critical_layers.csv  # Parsed critical layer results
│   ├── top5_archs.csv              # Top 5 architectures
│   ├── final_per_layer.csv         # Full network per-layer results
│   ├── final_best_arch_summary.txt # Full network summary
│   └── FINAL_SUMMARY.txt           # Complete summary with baseline comparison
└── scripts/
    ├── generate_archs.py        # Generate 27 architecture files
    ├── run_greedy_sweep.sh      # Run optimizer on critical layers
    ├── parse_results.py         # Parse optimizer logs to CSV
    ├── greedy_selection.py      # Select top 5 architectures
    ├── run_full_network.py      # Evaluate full ResNet-18
    ├── generate_final_summary.py # Generate final summary
    └── run_complete_workflow.sh  # Master script (runs everything)
```

## Architecture Space

The experiment explores:
- **PEs (parallel_count[0])**: [64, 256]
  - Note: PE=1024 is excluded as it's incompatible with C|K dataflow schedule (causes optimizer TypeError)
- **RF capacity**: [128, 256, 512] bytes
- **Buffer capacity**: [32768, 65536, 131072, 262144, 524288] bytes (32KB, 64KB, 128KB, 256KB, 512KB)
- **Total designs**: 2 × 3 × 5 = 30 architectures

## Critical Layers

The following critical layers are evaluated first:
1. `resnet_gen_conv1_batch16.json` - conv1
2. `resnet_gen_conv2_batch16.json` - conv2_x representative
3. `resnet_gen_conv5_batch16.json` - conv3_1 (stride 2 transition, 28x28)
4. `resnet_gen_conv8_batch16.json` - conv5_x representative

## Usage

### Option 1: Run Complete Workflow (Recommended)

```bash
cd /home/users/eraltam/272/VLSI/hw/hw1
bash ./experiments/greedy_resnet18/scripts/run_complete_workflow.sh
```

### Option 2: Run Individual Steps

```bash
cd /home/users/eraltam/272/VLSI/hw/hw1

# Step 1: Run greedy sweep on critical layers
bash ./experiments/greedy_resnet18/scripts/run_greedy_sweep.sh

# Step 2: Parse results
python3 ./experiments/greedy_resnet18/scripts/parse_results.py

# Step 3: Select top 5 architectures
python3 ./experiments/greedy_resnet18/scripts/greedy_selection.py

# Step 4: Run full network evaluation
python3 ./experiments/greedy_resnet18/scripts/run_full_network.py

# Step 5: Generate final summary
python3 ./experiments/greedy_resnet18/scripts/generate_final_summary.py
```

### Option 3: Minimal Commands (as specified)

```bash
cd /home/users/eraltam/272/VLSI/hw/hw1

bash ./experiments/greedy_resnet18/scripts/run_greedy_sweep.sh
python3 ./experiments/greedy_resnet18/scripts/parse_results.py
```

Then manually run selection and full evaluation steps.

## Constraints

- Dataflow: **C|K** fixed (IC and OC unrolled)
- Architectures: Only `[x,1,1]` parallel_count modes where x>1
- Capacities: Powers of 2 only
- Precision: 16 bits (fixed)
- DRAM: Fixed large capacity (1073741824 bytes)

## Access Costs

### Register File (RF)
- 16B → 0.03 pJ
- 32B → 0.06 pJ
- 64B → 0.12 pJ
- 128B → 0.24 pJ
- 256B → 0.48 pJ
- 512B → 0.96 pJ

### Buffer
- 32KB → 12 pJ
- 64KB → 16.9 pJ
- 128KB → 20.2 pJ
- 256KB → 30.4 pJ
- 512KB → 45.6 pJ

### DRAM
- Fixed: 200 pJ

## Output Files

- `greedy_critical_layers.csv`: All critical layer results with metrics
- `top5_archs.csv`: Top 5 architectures ranked by greedy scoring
- `final_per_layer.csv`: Full ResNet-18 per-layer breakdown
- `final_best_arch_summary.txt`: Full network aggregate metrics
- `FINAL_SUMMARY.txt`: Complete summary with baseline comparison

## Greedy Scoring

Architectures are scored with priority:
1. **Minimize DRAM accesses** (highest priority)
2. **Minimize energy**
3. **Minimize cycles** (lowest priority)

The scoring function uses weighted sums where DRAM dominates.

## Notes

- All scripts use relative paths from the project root (`hw1/`)
- Scripts fail fast with meaningful error messages
- Optimizer runs with verbose mode (`-v`) to capture all metrics
- Each layer evaluation has a 5-minute timeout

