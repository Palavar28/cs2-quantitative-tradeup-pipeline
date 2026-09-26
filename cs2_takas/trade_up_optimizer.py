import json
import asyncio
import aiohttp
import os
import sys
from typing import List, Dict, Optional
from collections import defaultdict
from market_fetcher import CS2MarketFetcher
from trade_up_math import calculate_output_float, get_wear_condition

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

RARITY_ORDER = ["Consumer", "Industrial", "Mil-Spec", "Restricted", "Classified", "Covert"]

ALLOWED_RARITIES = {
    "Consumer Grade": "Consumer",
    "Industrial Grade": "Industrial",
    "Mil-Spec Grade": "Mil-Spec"
}

FILLER_POOL = [
    "The Train Collection",
    "The Safehouse Collection",
    "The Bank Collection",
    "The Lake Collection",
    "The Dust 2 Collection"
]

def get_baseline_wear_and_float(min_float: float, max_float: float, base_rarity: str, strategy: str = "worst") -> tuple:
    if base_rarity == "Consumer":
        if min_float < 0.07:
            wear = "Factory New"
        elif min_float < 0.15:
            wear = "Minimal Wear"
        else:
            wear = "Field-Tested" if min_float < 0.38 and max_float > 0.15 else "Battle-Scarred"
    elif min_float < 0.38 and max_float > 0.15:
        wear = "Field-Tested"
    elif max_float <= 0.15:
        wear = "Minimal Wear" if max_float > 0.07 and min_float < 0.15 else "Factory New"
    elif min_float >= 0.38:
        wear = "Well-Worn" if min_float < 0.45 and max_float > 0.38 else "Battle-Scarred"
    else:
        wear = "Factory New"

    if strategy == "worst":
        floats = {"Factory New": 0.069, "Minimal Wear": 0.149, "Field-Tested": 0.379, "Well-Worn": 0.449, "Battle-Scarred": 0.99}
    else:
        floats = {"Factory New": 0.035, "Minimal Wear": 0.11, "Field-Tested": 0.26, "Well-Worn": 0.41, "Battle-Scarred": 0.72}
        
    assumed_float = floats.get(wear, 0.0)
    assumed_float = max(min_float, min(max_float, assumed_float))
    
    return wear, assumed_float

def format_market_name(weapon: str, skin_name: str, min_float: float, max_float: float, base_rarity: str) -> str:
    weapon_fixes = {
        "AK-47": "AK-47", "M4A1-S": "M4A1-S", "M4A4": "M4A4", "MAC-10": "MAC-10", "MP9": "MP9",
        "MP7": "MP7", "MP5-SD": "MP5-SD", "UMP-45": "UMP-45", "AWP": "AWP", "SSG 08": "SSG 08",
        "SG 553": "SG 553", "AUG": "AUG", "FAMAS": "FAMAS", "GALIL AR": "Galil AR", "G3SG1": "G3SG1",
        "SCAR-20": "SCAR-20", "P250": "P250", "TEC-9": "Tec-9", "CZ75-AUTO": "CZ75-Auto",
        "GLOCK-18": "Glock-18", "DESERT EAGLE": "Desert Eagle", "DUAL BERETTAS": "Dual Berettas",
        "FIVE-SEVEN": "Five-SeveN", "P2000": "P2000", "USP-S": "USP-S", "PP-BIZON": "PP-Bizon",
        "P90": "P90", "MAG-7": "MAG-7", "NOVA": "Nova", "SAWED-OFF": "Sawed-Off", "XM1014": "XM1014",
        "M249": "M249", "NEGEV": "Negev"
    }
    formatted_skin_name = skin_name.title()
    formatted_skin_name = formatted_skin_name.replace("'S ", "'s ").replace("'S", "'s")
    formatted_skin_name = formatted_skin_name.replace("Ddpat", "DDPAT")
    formatted_weapon = weapon_fixes.get(weapon.upper(), weapon.title())
    wear_condition, _ = get_baseline_wear_and_float(min_float, max_float, base_rarity, strategy="worst")
    return f"{formatted_weapon} | {formatted_skin_name} ({wear_condition})"

def format_specific_market_name(weapon: str, skin_name: str, wear_condition: str) -> str:
    weapon_fixes = {
        "AK-47": "AK-47", "M4A1-S": "M4A1-S", "M4A4": "M4A4", "MAC-10": "MAC-10", "MP9": "MP9",
        "MP7": "MP7", "MP5-SD": "MP5-SD", "UMP-45": "UMP-45", "AWP": "AWP", "SSG 08": "SSG 08",
        "SG 553": "SG 553", "AUG": "AUG", "FAMAS": "FAMAS", "GALIL AR": "Galil AR", "G3SG1": "G3SG1",
        "SCAR-20": "SCAR-20", "P250": "P250", "TEC-9": "Tec-9", "CZ75-AUTO": "CZ75-Auto",
        "GLOCK-18": "Glock-18", "DESERT EAGLE": "Desert Eagle", "DUAL BERETTAS": "Dual Berettas",
        "FIVE-SEVEN": "Five-SeveN", "P2000": "P2000", "USP-S": "USP-S", "PP-BIZON": "PP-Bizon",
        "P90": "P90", "MAG-7": "MAG-7", "NOVA": "Nova", "SAWED-OFF": "Sawed-Off", "XM1014": "XM1014",
        "M249": "M249", "NEGEV": "Negev"
    }
    formatted_skin_name = skin_name.title()
    formatted_skin_name = formatted_skin_name.replace("'S ", "'s ").replace("'S", "'s")
    formatted_skin_name = formatted_skin_name.replace("Ddpat", "DDPAT")
    formatted_weapon = weapon_fixes.get(weapon.upper(), weapon.title())
    return f"{formatted_weapon} | {formatted_skin_name} ({wear_condition})"

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

    collection_map = defaultdict(lambda: defaultdict(list))
    collections_set = set()
    
    for item in items:
        coll = item.get("collection", "Unknown")
        rar = item.get("rarity", "Unknown")
        min_float = item.get('min_float', 0.0)
        max_float = item.get('max_float', 1.0)
        item["market_hash_name"] = format_market_name(item['weapon'], item['skin_name'], min_float, max_float, rar)
        collection_map[coll][rar].append(item)
        collections_set.add(coll)
        
    collections_list = sorted(list(collections_set))
    
    print("=" * 60)
    print("CS2 CLI TRADE-UP OPTIMIZER (Float Math Edition)")
    print("=" * 60)
    print("Available Target Collections:")
    
    for i in range(0, len(collections_list), 2):
        col1 = f"{i+1:2}. {collections_list[i]}"
        col2 = f"{i+2:2}. {collections_list[i+1]}" if i+1 < len(collections_list) else ""
        print(f"{col1:<40} {col2}")
        
    try:
        coll_idx = int(input("\nEnter the number of your Target Collection: ")) - 1
        target_collection = collections_list[coll_idx]
    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")
        return
        
    print("\nSelect Input Rarity:")
    print("1. Consumer Grade")
    print("2. Industrial Grade")
    print("3. Mil-Spec Grade")
    
    try:
        rarity_choice = int(input("Enter 1, 2, or 3: "))
        rarity_keys = list(ALLOWED_RARITIES.keys())
        selected_rarity_str = rarity_keys[rarity_choice - 1]
        input_rarity = ALLOWED_RARITIES[selected_rarity_str]
    except (ValueError, IndexError):
        print("Invalid rarity selection. Exiting.")
        return
    
    next_rarity = get_next_rarity(input_rarity)
    if not next_rarity:
        return
        
    target_inputs = collection_map[target_collection].get(input_rarity, [])
    target_outputs = collection_map[target_collection].get(next_rarity, [])
    if not target_inputs or not target_outputs:
        print(f"\n[ERROR] {target_collection} does not have both {input_rarity} inputs and {next_rarity} outputs.")
        return

    print("\nSelect Input Float Strategy:")
    print("1. Worst-Case Floats (Safest, assumes you buy bad floats like 0.379 for FT)")
    print("2. Average-Case Floats (Optimistic, assumes you buy decent floats like 0.26 for FT)")
    try:
        strat_choice = int(input("Enter 1 or 2: "))
        float_strategy = "worst" if strat_choice == 1 else "average"
    except ValueError:
        float_strategy = "worst"

    print("\n[INFO] Evaluating Dynamic Filler Pool to find the cheapest collection...")
    
    live_prices = {}
    
    async with aiohttp.ClientSession() as session:
        fetcher = CS2MarketFetcher(session=session, requests_per_second=1, max_retries=3)
        
        # Determine actual assumed floats and hash names for ALL possible inputs
        for inp in target_inputs:
            w, f = get_baseline_wear_and_float(inp['min_float'], inp['max_float'], input_rarity, float_strategy)
            inp['assumed_float'] = f
            inp['market_hash_name'] = format_specific_market_name(inp['weapon'], inp['skin_name'], w)

        filler_collection_costs = {}
        for f_coll in FILLER_POOL:
            f_inputs = collection_map[f_coll].get(input_rarity, [])
            f_outputs = collection_map[f_coll].get(next_rarity, [])
            if not f_inputs or not f_outputs:
                continue
                
            collection_input_prices = []
            for item in f_inputs:
                w, f = get_baseline_wear_and_float(item['min_float'], item['max_float'], input_rarity, float_strategy)
                item['assumed_float'] = f
                skin_name = format_specific_market_name(item['weapon'], item['skin_name'], w)
                item['market_hash_name'] = skin_name
                
                if skin_name not in live_prices:
                    print(f"Fetching filler baseline: {skin_name}...")
                    listings = await fetcher.fetch_listings(skin_name)
                    if listings:
                        live_prices[skin_name] = min(listings, key=lambda x: x.price).price
                    else:
                        live_prices[skin_name] = 9999.0
                    await asyncio.sleep(1.5)
                
                collection_input_prices.append(live_prices[skin_name])
                
            if collection_input_prices:
                filler_collection_costs[f_coll] = min(collection_input_prices)
                
        if not filler_collection_costs:
            return
            
        cheapest_filler_collection = min(filler_collection_costs, key=filler_collection_costs.get)
        print(f"\n[SUCCESS] Optimal Filler Collection selected: {cheapest_filler_collection}")
        
        filler_inputs = collection_map[cheapest_filler_collection].get(input_rarity, [])
        filler_outputs = collection_map[cheapest_filler_collection].get(next_rarity, [])
        
        # Ensure we fetched the target inputs
        for item in target_inputs:
            skin_name = item['market_hash_name']
            if skin_name not in live_prices:
                print(f"Fetching target baseline: {skin_name}...")
                listings = await fetcher.fetch_listings(skin_name)
                if listings:
                    live_prices[skin_name] = min(listings, key=lambda x: x.price).price
                else:
                    live_prices[skin_name] = 9999.0
                await asyncio.sleep(1.5)

        t_input = min(target_inputs, key=lambda x: live_prices.get(x["market_hash_name"], 9999))
        f_input = min(filler_inputs, key=lambda x: live_prices.get(x["market_hash_name"], 9999))
        
        target_cost = live_prices.get(t_input["market_hash_name"], 0)
        filler_cost = live_prices.get(f_input["market_hash_name"], 0)
        
        print(f"\n[INFO] Calculating Exact Output Floats...")
        
        # Calculate dynamic output names for all 1..9 combinations
        combo_outputs = {}
        required_output_skins = set()
        
        for target_qty in range(1, 10):
            filler_qty = 10 - target_qty
            
            floats = [t_input['assumed_float']] * target_qty + [f_input['assumed_float']] * filler_qty
            mins = [t_input['min_float']] * target_qty + [f_input['min_float']] * filler_qty
            maxs = [t_input['max_float']] * target_qty + [f_input['max_float']] * filler_qty
            
            combo_outputs[target_qty] = {'target_outputs': [], 'filler_outputs': [], 'avg_input_float': sum(floats)/10}
            
            for out in target_outputs:
                out_float = calculate_output_float(floats, mins, maxs, out['min_float'], out['max_float'])
                wear = get_wear_condition(out_float)
                hash_name = format_specific_market_name(out['weapon'], out['skin_name'], wear)
                combo_outputs[target_qty]['target_outputs'].append({'hash_name': hash_name, 'out_float': out_float})
                required_output_skins.add(hash_name)
                
            for out in filler_outputs:
                out_float = calculate_output_float(floats, mins, maxs, out['min_float'], out['max_float'])
                wear = get_wear_condition(out_float)
                hash_name = format_specific_market_name(out['weapon'], out['skin_name'], wear)
                combo_outputs[target_qty]['filler_outputs'].append({'hash_name': hash_name, 'out_float': out_float})
                required_output_skins.add(hash_name)

        skins_to_fetch = [s for s in required_output_skins if s not in live_prices]
        if skins_to_fetch:
            print(f"\n[INFO] Fetching live prices for {len(skins_to_fetch)} true calculated output items...")
            for skin in skins_to_fetch:
                print(f"Fetching Output: {skin}...")
                listings = await fetcher.fetch_listings(skin)
                if listings:
                    live_prices[skin] = min(listings, key=lambda x: x.price).price
                else:
                    live_prices[skin] = 9999.0
                await asyncio.sleep(1.5)
                
    print("\n" + "=" * 70)
    print(f"CS2 TRADE-UP SMART GAMBLE REPORT (FLOAT AWARE)")
    print(f"Target: {target_collection} | Filler: {cheapest_filler_collection}")
    print(f"Tier: {input_rarity} -> {next_rarity}")
    print("=" * 70)
    
    valid_combinations = []
    
    for target_qty in range(1, 10):
        filler_qty = 10 - target_qty
        total_cost = (target_qty * target_cost) + (filler_qty * filler_cost)
        
        if total_cost <= 0 or total_cost > 9000:
            continue
            
        target_prob = target_qty / 10.0
        filler_prob = filler_qty / 10.0
        expected_revenue = 0.0
        
        t_outs = combo_outputs[target_qty]['target_outputs']
        f_outs = combo_outputs[target_qty]['filler_outputs']
        avg_input_float = combo_outputs[target_qty]['avg_input_float']
        
        prob_per_target = target_prob / len(t_outs)
        for out in t_outs:
            out_price = live_prices.get(out["hash_name"], 0)
            expected_revenue += prob_per_target * (out_price * 0.98)
            
        prob_per_filler = filler_prob / len(f_outs)
        for out in f_outs:
            out_price = live_prices.get(out["hash_name"], 0)
            expected_revenue += prob_per_filler * (out_price * 0.98)
            
        net_ev = expected_revenue - total_cost
        
        jackpot_skin = max(t_outs, key=lambda x: live_prices.get(x["hash_name"], 0))
        jackpot_payout = live_prices.get(jackpot_skin["hash_name"], 0) * 0.98
        
        if jackpot_payout > total_cost:
            sustainability_score = total_cost / abs(net_ev) if net_ev != 0 else 9999.99
            jackpot_chance_pct = prob_per_target * 100
            avg_tries_to_hit = 100 / jackpot_chance_pct if jackpot_chance_pct > 0 else 0
            cost_to_hit = avg_tries_to_hit * total_cost
            
            valid_combinations.append({
                'target_qty': target_qty, 'filler_qty': filler_qty, 'total_cost': total_cost,
                'net_ev': net_ev, 'sustainability_score': sustainability_score,
                'jackpot_name': jackpot_skin['hash_name'], 'jackpot_chance_pct': jackpot_chance_pct,
                'jackpot_payout': jackpot_payout, 'avg_tries_to_hit': avg_tries_to_hit,
                'cost_to_hit': cost_to_hit, 'avg_input_float': avg_input_float, 'expected_output_float': jackpot_skin['out_float']
            })
            
    if not valid_combinations:
        print("\n[-] No combinations found where the Jackpot covers the total cost.")
        print("=" * 70)
    else:
        valid_combinations.sort(key=lambda x: x['sustainability_score'], reverse=True)
        for combo in valid_combinations:
            
            if combo['net_ev'] > 0:
                print(f"\n[⚠️ POSITIVE EV ANOMALY (Penny Trade-up / Data Error)]")
            elif combo['sustainability_score'] < 2.0:
                print(f"\n[📉 LOW SUSTAINABILITY]")
            else:
                print("\n")
                
            print(f"Combination: {combo['target_qty']}x {t_input['market_hash_name']} + {combo['filler_qty']}x {f_input['market_hash_name']}")
            print(f"Inputs Avg Float: {combo['avg_input_float']:.5f} -> Expected Output Float: {combo['expected_output_float']:.5f}")
            print(f"Cost: ${combo['total_cost']:.2f} | Net EV: ${combo['net_ev']:.2f}")
            print(f"Jackpot: {combo['jackpot_name']} | Chance: {combo['jackpot_chance_pct']:.2f}% | Payout (after 2% tax): ${combo['jackpot_payout']:.2f}")
            print("--- Risk Analytics ---")
            print(f"Sustainability Score: {combo['sustainability_score']:.2f} (Tries before losing one full trade-up cost in EV)")
            print(f"Avg Tries to Hit Jackpot: {combo['avg_tries_to_hit']:.1f} tries")
            print(f"Expected Cost to Hit Jackpot: ${combo['cost_to_hit']:.2f}")
            print("-" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOptimization aborted by user.")
