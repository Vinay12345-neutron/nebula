---
name: gpu-profiling
description: >-
  Use this skill to profile MoE forward passes, capture expert routing traces,
  and monitor NVIDIA RTX A6000 GPU memory allocation without modifying model weights.
---

# GPU Profiling Skill

Use this procedure when instrumenting or profiling MoE inference on the physical A6000 workstation.

## Profiling Protocol

1. **Device Verification:**
   - Verify CUDA device availability and ensure zero memory leakage from prior runs.
2. **Routing Trace Capture:**
   - Attach read-only PyTorch forward hooks to MoE router gating layers.
   - Record active expert IDs per token and per layer.
   - Capture router logits/probabilities if co-activation tracking is enabled.
3. **Memory Tracking:**
   - Record `torch.cuda.memory_allocated()` and `torch.cuda.max_memory_allocated()` for:
     - Base model weights (attention + shared parameters)
     - Dynamic KV cache allocation
     - Expert parameter residency
4. **Trace Serialization:**
   - Save extracted routing matrices directly to compressed parquet/binary formats for trace-driven simulation.
