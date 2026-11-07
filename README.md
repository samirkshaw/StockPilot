# StockPilot

**Autonomous Supply Chain Decision Agent** — built for Agentic Chase, Mission 02 (PS 02: SupplyChainIQ).

StockPilot is an AI agent that analyses inventory, sales history and supplier data, detects products at risk of stocking out, and produces an actionable procurement plan with clear reasoning.

## Problem

Businesses face inventory shortages, delayed shipments and sudden demand spikes. Deciding what to reorder, how much, and from which supplier means juggling stock levels, demand patterns, supplier cost and delivery time. StockPilot automates that decision loop.

## What the agent does

1. Checks available inventory for each product
2. Analyses historical sales and estimates average daily demand
3. Forecasts demand over the supplier delivery window
4. Flags products at risk of a stockout and ranks them by urgency
5. Compares suppliers on cost and delivery time
6. Calculates a suitable reorder quantity
7. Generates a procurement plan and compares two alternative strategies (cost vs delivery time)

## Agent tools

| Tool | Purpose |
|------|---------|
| Inventory lookup | Returns current stock per product |
| Sales history analysis | Computes average daily demand and trends from sales data |
| Supplier comparison | Ranks suppliers by unit cost and lead time |
| Reorder calculation | Computes reorder quantity from demand, lead time and current stock |

## Example scenario

- Current stock: 15 units
- Average daily demand: 10 units/day
- Supplier delivery time: 5 days

Expected demand during delivery = 10 x 5 = **50 units**. Stock covers only 1.5 days, so the shortfall is **35 units** and a stockout occurs before the shipment arrives. The agent flags the risk, compares suppliers and recommends a replenishment quantity.

## Planned structure

```
StockPilot/
├── data/            # simulated inventory, sales and supplier data
├── tools/           # inventory, sales analysis, supplier comparison, reorder
├── agent/           # agent loop and reasoning
├── reports/         # generated procurement plans
├── main.py          # entry point
└── README.md
```

## Tech stack

- Python
- LLM API for agent reasoning and tool calling
- pandas / NumPy for data analysis and demand estimation

## Status

Work in progress. This README describes the planned scope; implementation is being added.

## Author

Samir Kumar Shaw — [@samirkshaw](https://github.com/samirkshaw)