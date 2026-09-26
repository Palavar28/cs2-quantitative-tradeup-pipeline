import json
import asyncio
import aiohttp
import os
import sys
from typing import List, Dict, Optional
from collections import defaultdict

# Add current path to import custom modules
sys.path.append(os.path.dirname(__file__))

from market_fetcher import CS2MarketFetcher
from trade_up_optimizer import format_market_name, get_next_rarity, FILLER_POOL

async def test_combos():
    json_path = os.path.join(os.path.dirname(__file__), "cs2_items.json")
    with open(json_path, 'r', encoding='utf-8') as f:
        items = json.load(f)

    collection_map = defaultdict(lambda: defaultdict(list))
    for item in items:
        coll = item.get("collection", "Unknown")
        rar = item.get("rarity", "Unknown")
        
        min_float = item.get('min_float', 0.0)
        max_float = item.get('max_float', 1.0)
        item["market_hash_name"] = format_market_name(item['weapon'], item['skin_name'], min_float, max_float, rar)
        
        collection_map[coll][rar].append(item)

    test_cases = [
        ("The Canals Collection", "Consumer"),
        ("The Overpass Collection", "Consumer"),
        ("The Cobblestone Collection", "Industrial"),
        ("The Gods And Monsters Collection", "Mil-Spec"),
        ("The Chop Shop Collection", "Industrial")
    ]
    
    live_prices = {}
    profitable_count = 0

    async with aiohttp.ClientSession() as session:
        fetcher = CS2MarketFetcher(session=session, requests_per_second=1, max_retries=3)
        
        for t_coll, i_rar in test_cases:
            print(f"\nEvaluating {t_coll} ({i_rar})")
            n_rar = get_next_rarity(i_rar)
            
            target_inputs = collection_map[t_coll].get(i_rar, [])
            target_outputs = collection_map[t_coll].get(n_rar, [])
            if not target_inputs or not target_outputs:
                print(" -> Missing inputs or outputs, skipping.")
                continue
                
            filler_collection_costs = {}
            for f_coll in FILLER_POOL:
                f_inputs = collection_map[f_coll].get(i_rar, [])
                f_outputs = collection_map[f_coll].get(n_rar, [])
                if not f_inputs or not f_outputs:
                    continue
                    
                collection_input_prices = []
                for item in f_inputs:
                    skin_name = item["market_hash_name"]
                    if skin_name not in live_prices:
                        listings = await fetcher.fetch_listings(skin_name)
                        live_prices[skin_name] = min(listings, key=lambda x: x.price).price if listings else 9999.0
                        await asyncio.sleep(1.5)
                    collection_input_prices.append(live_prices[skin_name])
                if collection_input_prices:
                    filler_collection_costs[f_coll] = min(collection_input_prices)
                    
            if not filler_collection_costs:
                print(" -> No filler collections valid, skipping.")
                continue
                
            cheapest_filler = min(filler_collection_costs, key=filler_collection_costs.get)
            f_inputs = collection_map[cheapest_filler].get(i_rar, [])
            f_outputs = collection_map[cheapest_filler].get(n_rar, [])
            
            required_skins = set()
            for item in target_inputs + target_outputs + f_outputs:
                required_skins.add(item["market_hash_name"])
                
            for skin in required_skins:
                if skin not in live_prices:
                    listings = await fetcher.fetch_listings(skin)
                    live_prices[skin] = min(listings, key=lambda x: x.price).price if listings else 0.0
                    await asyncio.sleep(1.5)
                    
            t_input = min(target_inputs, key=lambda x: live_prices.get(x["market_hash_name"], 9999))
            f_input = min(f_inputs, key=lambda x: live_prices.get(x["market_hash_name"], 9999))
            
            target_cost = live_prices.get(t_input["market_hash_name"], 0)
            filler_cost = live_prices.get(f_input["market_hash_name"], 0)
            
            for target_qty in range(1, 6):
                filler_qty = 10 - target_qty
                total_cost = (target_qty * target_cost) + (filler_qty * filler_cost)
                if total_cost == 0: continue
                
                expected_revenue = 0.0
                prob_per_target = (target_qty / 10.0) / len(target_outputs)
                for out in target_outputs:
                    expected_revenue += prob_per_target * (live_prices.get(out["market_hash_name"], 0) * 0.98)
                    
                prob_per_filler = (filler_qty / 10.0) / len(f_outputs)
                for out in f_outputs:
                    expected_revenue += prob_per_filler * (live_prices.get(out["market_hash_name"], 0) * 0.98)
                    
                ev = expected_revenue - total_cost
                if ev > 0:
                    profitable_count += 1
                    roi = (ev / total_cost) * 100
                    print(f"[+] PROFITABLE: {target_qty}x {t_input['market_hash_name']} + {filler_qty}x {f_input['market_hash_name']}")
                    print(f"    Cost: ${total_cost:.2f}, EV: ${ev:.2f}, ROI: {roi:.2f}%")
                    
    print(f"\nTotal Profitable Combinations Found: {profitable_count}")

if __name__ == "__main__":
    asyncio.run(test_combos())
