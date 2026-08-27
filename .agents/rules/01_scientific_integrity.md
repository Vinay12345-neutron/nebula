# Rule 01: Scientific Integrity & Rigor

1. **Core Principle**: Follow the guiding mandate from `README.md`: *"Do not optimize what we have not measured."*
2. **No Invented Speedups**: Never claim or assume performance improvements prior to empirical measurement.
3. **Overhead Accounting**: All placement and tiering evaluations must explicitly account for:
   - Placement solver execution time and CPU/GPU overhead.
   - Expert migration latency and memory transfer volume across tiers.
   - Interconnect bandwidth contention.
4. **Statistical Rigor & Seeds**:
   - For **stochastic workloads** (e.g., randomized request arrival, randomized sampling, non-deterministic routing): multiple random seeds are required, and distributions (mean, std dev, P50, P95, P99) must be reported.
   - For **deterministic workloads** (e.g., static trace replays with deterministic greedy placement): a single execution is acceptable provided that the deterministic nature and exact inputs are explicitly recorded.
5. **Negative Results**: Treat negative or neutral findings (e.g., workloads where simple frequency placement matches batch-aware placement) as valid scientific findings. Do not manipulate parameters to force positive outcomes.
