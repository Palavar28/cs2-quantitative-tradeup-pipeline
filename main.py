import asyncio
import logging
import aiohttp
from typing import List, Dict, Any

from market_fetcher import CS2MarketFetcher, MarketListing
from ev_calculator import calculate_trade_up_profitability, print_ev_report

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ==========================================
# CONFIGURATION: TARGET CONTRACT
# ==========================================
TARGET_CONTRACT = {
    "inputs": [
        "P250 | Valence (Field-Tested)",
        "FAMAS | Survivor Z (Field-Tested)"
    ],
    "target_avg_float": 0.135,
    "outputs": [
        {
            "name": "M4A1-S | Chantico's Fire",
            "probability": 0.50,
            "min_float": 0.00,
            "max_float": 0.99,
            "price_map": {
                "Factory New": 100.00,
                "Minimal Wear": 45.00,
                "Good Field-Tested": 25.00,
                "Average Field-Tested": 20.00,
                "Bad Field-Tested": 18.00,
                "Well-Worn": 15.00,
                "Good Battle-Scarred": 12.00,
                "Average Battle-Scarred": 10.00,
                "Bad Battle-Scarred": 9.00
            }
        },
        {
            "name": "AK-47 | Point Disarray",
            "probability": 0.50,
            "min_float": 0.00,
            "max_float": 0.67,
            "price_map": {
                "Factory New": 40.00,
                "Minimal Wear": 25.00,
                "Good Field-Tested": 18.00,
                "Average Field-Tested": 16.00,
                "Bad Field-Tested": 14.00,
                "Well-Worn": 12.00,
                "Good Battle-Scarred": 10.00,
                "Average Battle-Scarred": 9.00,
                "Bad Battle-Scarred": 8.00
            }
        }
    ]
}


# ==========================================
# OPTIMIZER ALGORITHM
# ==========================================
async def find_optimal_inputs(fetcher: CS2MarketFetcher, input_skin_names: List[str], target_avg_float: float) -> List[Dict[str, Any]]:
    """
    Fetches live listings and attempts to find 10 skins where sum(prices) is minimized,
    but the average float is <= target_avg_float.
    """
    logging.info(f"Fetching live market data for {len(input_skin_names)} input skins...")
    market_data = await fetcher.fetch_multiple_skins(input_skin_names)
    
    # Pool all listings together
    all_listings: List[MarketListing] = []
    for skin, listings in market_data.items():
        all_listings.extend(listings)
        
    if len(all_listings) < 10:
        logging.warning("Not enough skins found on the market to complete a 10-skin trade-up.")
        return []

    # Sort all listings by price (ascending)
    all_listings.sort(key=lambda x: x.price)
    
    # Start with the absolute cheapest 10 skins
    selected_skins = all_listings[:10]
    remaining_skins = all_listings[10:]
    
    def get_avg_float(skins: List[MarketListing]) -> float:
        return sum(s.float_value for s in skins) / 10.0

    current_avg = get_avg_float(selected_skins)
    logging.info(f"Initial cheapest 10 skins avg float: {current_avg:.5f}")

    # Greedy optimization to reduce float if necessary
    # Swap high-float items in our selection with lower-float items from the remaining pool
    # prioritizing swaps that cost the least per unit of float reduction.
    iterations = 0
    max_iterations = 1000
    
    while current_avg > target_avg_float and iterations < max_iterations:
        best_swap = None
        best_ratio = -1.0
        
        for i, sel_skin in enumerate(selected_skins):
            for j, rem_skin in enumerate(remaining_skins):
                # We only want to swap if the remaining skin lowers the float
                if rem_skin.float_value < sel_skin.float_value:
                    float_reduction = sel_skin.float_value - rem_skin.float_value
                    price_increase = rem_skin.price - sel_skin.price
                    
                    if price_increase <= 0:
                        # Lower float AND cheaper/same price (rare but possible due to sorting/data overlap)
                        ratio = float('inf')
                    else:
                        ratio = float_reduction / price_increase
                        
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_swap = (i, j)
                        
        if best_swap:
            sel_idx, rem_idx = best_swap
            # Execute swap
            selected_skins[sel_idx], remaining_skins[rem_idx] = remaining_skins[rem_idx], selected_skins[sel_idx]
            current_avg = get_avg_float(selected_skins)
        else:
            # No possible swaps can reduce the float further
            break
            
        iterations += 1

    if current_avg > target_avg_float:
        logging.warning(f"Could not find a combination of 10 skins meeting the target float {target_avg_float}. Best avg float found: {current_avg:.5f}")
        return []
        
    logging.info(f"Successfully found optimal 10 skins. Target Avg: {target_avg_float}, Actual Avg: {current_avg:.5f}, Total Cost: ${sum(s.price for s in selected_skins):.2f}")
    
    # Convert MarketListing objects to the expected dict format for the EV calculator
    final_inputs = [
        {"skin_name": s.skin_name, "price_usd": s.price, "float_value": s.float_value}
        for s in selected_skins
    ]
    return final_inputs


# ==========================================
# EXECUTION FLOW
# ==========================================
async def run_pipeline():
    logging.info("Starting CS2 Trade-up Pipeline...")
    
    async with aiohttp.ClientSession() as session:
        fetcher = CS2MarketFetcher(session=session, requests_per_second=2, max_retries=3)
        
        logging.info("Searching for optimal input combinations...")
        optimal_inputs = await find_optimal_inputs(
            fetcher=fetcher,
            input_skin_names=TARGET_CONTRACT["inputs"],
            target_avg_float=TARGET_CONTRACT["target_avg_float"]
        )
        
        if not optimal_inputs:
            logging.error("Pipeline aborted due to lack of valid input combinations.")
            return
            
        logging.info("Calculating Trade-up Expected Value...")
        results = calculate_trade_up_profitability(
            input_skins=optimal_inputs,
            possible_outputs=TARGET_CONTRACT["outputs"]
        )
        
        print_ev_report(results)
        logging.info("Pipeline finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
