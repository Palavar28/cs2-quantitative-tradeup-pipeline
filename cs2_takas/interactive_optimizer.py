import json
import asyncio
import aiohttp
import os
from typing import List, Dict, Optional
from collections import defaultdict
from market_fetcher import CS2MarketFetcher

RARITY_ORDER = [
    "Consumer", "Industrial", "Mil-Spec", 
    "Restricted", "Classified", "Covert"
]

def get_next_rarity(rarity: str) -> Optional[str]:
    try:
        idx = RARITY_ORDER.index(rarity)
        if idx + 1 < len(RARITY_ORDER):
            return RARITY_ORDER[idx + 1]
    except ValueError:
        pass
    return None

async def main():
    json_path = os.path.join(os.path.dirname(__file__), "cs2_items.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        items = json.load(f)

    # Group items by collection -> rarity
    collection_map = defaultdict(lambda: defaultdict(list))
    collections_set = set()
    
    for item in items:
        coll = item.get("collection", "Unknown")
        rar = item.get("rarity", "Unknown")
        name = f"{item['weapon']} | {item['skin_name']}"
        item["full_name"] = name
        collection_map[coll][rar].append(item)
        collections_set.add(coll)
        
    collections_list = sorted(list(collections_set))
    
    # 1. Interactive Menu
    print("=" * 50)
    print("CS2 INTERACTIVE TRADE-UP OPTIMIZER")
    print("=" * 50)
    print("Available Collections:")
    
    # Optional: Display in columns for better readability if list is long
    for i, c in enumerate(collections_list, 1):
        print(f"{i:2}. {c}")
        
    try:
        coll_idx = int(input("\nEnter the number of your Target Collection: ")) - 1
        if coll_idx < 0 or coll_idx >= len(collections_list):
            raise ValueError
        target_collection = collections_list[coll_idx]
    except ValueError:
        print("Invalid selection. Exiting.")
        return
        
    input_rarity = input("Enter the Input Rarity (e.g., Mil-Spec, Restricted): ").strip().title()
    
    next_rarity = get_next_rarity(input_rarity)
    if not next_rarity:
        print("Invalid rarity or no higher tier available.")
        return
        
    # 2. Logic Structure (Target vs. Filler)
    # Using The Safehouse Collection as a default cheap filler
    filler_collection = "The Safehouse Collection"
    print(f"\n[INFO] Target Collection: {target_collection}")
    print(f"[INFO] Filler Collection (Hardcoded Default): {filler_collection}")
    print(f"[INFO] Input Rarity: {input_rarity} -> Output Rarity: {next_rarity}")
    
    target_inputs = collection_map[target_collection].get(input_rarity, [])
    target_outputs = collection_map[target_collection].get(next_rarity, [])
    filler_inputs = collection_map[filler_collection].get(input_rarity, [])
    filler_outputs = collection_map[filler_collection].get(next_rarity, [])
    
    if not target_inputs or not target_outputs:
        print(f"\n[ERROR] {target_collection} does not have both {input_rarity} inputs and {next_rarity} outputs.")
        return
    if not filler_inputs or not filler_outputs:
        print(f"\n[ERROR] Filler {filler_collection} does not have both {input_rarity} and {next_rarity} items.")
        return

    # 3. Live API Fetching
    required_skins = set()
    for item in target_inputs + target_outputs + filler_inputs + filler_outputs:
        required_skins.add(item["full_name"])
        
    print(f"\n[API] Fetching live prices for {len(required_skins)} specific items to respect rate limits...")
    print("This will take a moment (1.5s delay per item).\n")
    
    live_prices = {}
    async with aiohttp.ClientSession() as session:
        fetcher = CS2MarketFetcher(session=session, requests_per_second=1, max_retries=3)
        for skin in required_skins:
            print(f"Fetching: {skin}...")
            listings = await fetcher.fetch_listings(skin)
            if listings:
                # Find the absolute cheapest listing for EV calculation
                cheapest = min(listings, key=lambda x: x.price)
                live_prices[skin] = cheapest.price
            else:
                print(f"  -> WARNING: No active listings found for {skin}. Defaulting to $0.00")
                live_prices[skin] = 0.0
            
            # Explicit strict delay to avoid HTTP 429 Rate Limits
            await asyncio.sleep(1.5)
            
    print("\nLive prices fetched successfully!")

    # 4. The Combinator & EV Math
    # Select the single cheapest skin from the target collection inputs and filler inputs
    t_input = min(target_inputs, key=lambda x: live_prices.get(x["full_name"], 9999))
    f_input = min(filler_inputs, key=lambda x: live_prices.get(x["full_name"], 9999))
    
    print("\n" + "=" * 70)
    print(f"TRADE-UP EV REPORT (Target: {target_collection})")
    print("=" * 70)
    
    for target_qty in range(1, 6):
        filler_qty = 10 - target_qty
        
        target_cost = live_prices.get(t_input["full_name"], 0)
        filler_cost = live_prices.get(f_input["full_name"], 0)
        total_cost = (target_qty * target_cost) + (filler_qty * filler_cost)
        
        if total_cost == 0:
            print(f"[ERROR] Could not calculate cost for {target_qty}x combo. Missing prices.")
            continue
            
        target_prob = target_qty / 10.0
        filler_prob = filler_qty / 10.0
        
        expected_revenue = 0.0
        
        # Calculate expected return from the target collection
        prob_per_target = target_prob / len(target_outputs)
        for out in target_outputs:
            out_price = live_prices.get(out["full_name"], 0)
            expected_revenue += prob_per_target * (out_price * 0.98) # 2% CSFloat Tax
            
        # Calculate expected return from the filler collection
        prob_per_filler = filler_prob / len(filler_outputs)
        for out in filler_outputs:
            out_price = live_prices.get(out["full_name"], 0)
            expected_revenue += prob_per_filler * (out_price * 0.98) # 2% CSFloat Tax
            
        ev = expected_revenue - total_cost
        roi = (ev / total_cost) * 100
        
        # Output formatting
        if ev > 0:
            status = "✅ PROFITABLE"
        else:
            status = "❌ LOSS"
            
        print(f"{status} | {target_qty}x {t_input['full_name']} + {filler_qty}x {f_input['full_name']}")
        print(f"   Total Cost: ${total_cost:.2f} | Net EV: ${ev:.2f} | ROI: {roi:.2f}%")
        print("-" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOptimization aborted by user.")
