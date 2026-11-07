"""
StockPilot Agent Tools package.
Contains deterministic tools for supply chain operations:
- inventory_lookup: Current stock and catalog queries
- sales_analysis: Rolling demand calculation and spike detection
- supplier_comparison: Supplier costs and lead times comparison
- reorder_calculation: Reorder points, safety stock, and quantity recommendations
"""

from tools.inventory_lookup import inventory_lookup, list_products
from tools.sales_analysis import analyze_sales
from tools.supplier_comparison import compare_suppliers
from tools.reorder_calculation import calculate_reorder

__all__ = [
    "inventory_lookup",
    "list_products",
    "analyze_sales",
    "compare_suppliers",
    "calculate_reorder",
]
