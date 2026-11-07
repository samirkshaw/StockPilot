# StockPilot Operational Scenarios Analysis

This report presents three core simulated supply chain decision scenarios evaluated by StockPilot.

## Scenario A: Low Stock with a 5-Day Supplier (Product P001)

- **Product ID:** P001 (Ergonomic Office Chair)
- **Current Stock:** 15 units
- **Daily Demand Used:** 10.11 units/day
- **Evaluated Supplier Lead Time:** 5 days
- **Demand During Lead Time:** 50.55 units
- **Shortfall Before Arrival:** 35.55 units
- **Days of Cover:** 1.48 days
- **Days Uncovered Before Arrival:** 3.52 days
- **Risk Level:** `Critical`

### P001 Supplier Comparison Options

| Supplier ID | Supplier Name | Unit Cost ($) | Lead Time | Order Qty | Total Cost ($) | Shortfall | Days Uncovered | Rev at Risk ($) |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **SUP-101** | Apex Office Works | $88.00 | 14d | 289 | $25,432.00 | 126.54 | 12.52d | $25,306.73 |
| **SUP-102** | RapidSeat Logistics | $108.00 | 5d | 289 | $31,212.00 | 35.55 | 3.52d | $7,109.64 |
| **SUP-103** | SwiftFurnish Express | $125.00 | 2d | 289 | $36,125.00 | 5.22 | 0.52d | $1,043.95 |

- **Recommended Supplier:** **SUP-103** (SwiftFurnish Express)
- **Recommendation Reasoning:** *"No supplier avoids a stockout; SUP-103 minimises the gap with 5.22 units shortfall (lead time 2d, cost $36,125.00)."*

## Scenario B: Demand Spike Detection (Product P003)

- **Product ID:** P003 (USB-C Dual 4K Docking Station)
- **Current Stock:** 95 units
- **180-Day Baseline Daily Average:** 8.58 units/day
- **Last 14-Day Daily Average:** 15.00 units/day
- **Demand Trend Ratio (14d vs prior):** 1.87x
- **Spike Detected:** `True` (True: surge exceeds +30% threshold)
- **Forecast Model Selected by Backtest:** `exp_smoothing`
- **Forecast Daily Demand in Plan:** 13.42 units/day

### Days of Inventory Cover Across Demand Perspectives
- **Under 180-Day Baseline Demand (8.58/day):** **11.07 days** of cover (falsely appears safe)
- **Under Backtested Forecast Demand (13.42/day):** **7.08 days** of cover (realistic buffer)
- **Under Last 14-Day Spike Demand (15.00/day):** **6.33 days** of cover (critical depletion pace)

### Illustrative Baseline Calculation vs. StockPilot Plan
A naive inventory planner relying strictly on the 180-day historical mean would calculate required quantity as:
- **Naive 180-Day Quantity:** `ceil(max(0, 8.58 * 30 - 95))` = **163 units**
- **StockPilot Plan Quantity:** `ceil(max(0, 13.42 * 30 - 95))` = **308 units**
- **Replenishment Under-Order Deficit if Naive:** 145 units under-allocated!

During recommended supplier delivery transit (4 days with SUP-106):
- **Demand under 180-Day Assumption:** 34.32 units (expected buffer remaining: 60.68 units)
- **Demand under Forecast Assumption:** 53.68 units (expected buffer remaining: 41.32 units)
- **Demand under Recent 14d Spike Rate:** 60.00 units (expected buffer remaining: 35.00 units)

## Scenario C: Healthy Inventory & Surplus Coverage (Products P002 and P005)

| Product ID | Product Name | Current Stock | Daily Demand | Days of Cover | Plan Action | Risk Level |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **P002** | Wireless Mechanical Keyboard | 500 | 11.75 | 42.55 days | **No order needed** | `Low` |
| **P005** | Standing Desk Anti-Fatigue Mat | 250 | 1.07 | 233.64 days | **No order needed** | `Low` |

Both products hold sufficient stock exceeding the 30-day replenishment window without capital commitment.
