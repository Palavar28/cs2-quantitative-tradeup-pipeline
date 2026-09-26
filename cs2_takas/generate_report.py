import json
import asyncio
import aiohttp
import os
import sys
from typing import List, Dict, Optional
from collections import defaultdict
from market_fetcher import CS2MarketFetcher
from trade_up_math import calculate_output_float, get_wear_condition

sys.path.append(os.path.dirname(__file__))

from trade_up_optimizer import get_baseline_wear_and_float, format_specific_market_name, get_next_rarity, FILLER_POOL

async def run_report():
    json_path = os.path.join(os.path.dirname(__file__), "cs2_items.json")
    with open(json_path, 'r', encoding='utf-8') as f:
        items = json.load(f)

    collection_map = defaultdict(lambda: defaultdict(list))
    for item in items:
        coll = item.get("collection", "Unknown")
        rar = item.get("rarity", "Unknown")
        collection_map[coll][rar].append(item)

    test_cases = [
        "Limited Edition Item",
        "The 2018 Inferno Collection",
        "The 2018 Nuke Collection",
        "The 2021 Dust 2 Collection",
        "The 2021 Mirage Collection"
    ]
    
    i_rar = "Industrial"
    n_rar = get_next_rarity(i_rar)
    float_strategy = "worst" # Defaulting to worst case for the report
    
    live_prices = {}
    report_lines = []
    
    report_lines.append(f"# CS2 Trade-Up Smart Gamble Report (Float-Aware Edition)")
    report_lines.append(f"**Target Rarity:** {i_rar} -> {n_rar}")
    report_lines.append(f"**Assumed Float Strategy:** {float_strategy.title()}-Case Floats\n")

    async with aiohttp.ClientSession() as session:
        fetcher = CS2MarketFetcher(session=session, requests_per_second=1, max_retries=3)
        
        for t_coll in test_cases:
            print(f"\nEvaluating {t_coll} ({i_rar})")
            
            target_inputs = collection_map[t_coll].get(i_rar, [])
            target_outputs = collection_map[t_coll].get(n_rar, [])
            
            if not target_inputs or not target_outputs:
                report_lines.append(f"## {t_coll}\n*Skipped: No Industrial/Mil-Spec items found.*\n")
                continue
                
            for inp in target_inputs:
                w, fl = get_baseline_wear_and_float(inp['min_float'], inp['max_float'], i_rar, float_strategy)
                inp['assumed_float'] = fl
                inp['market_hash_name'] = format_specific_market_name(inp['weapon'], inp['skin_name'], w)
                
            filler_collection_costs = {}
            for f_coll in FILLER_POOL:
                f_inputs = collection_map[f_coll].get(i_rar, [])
                f_outputs = collection_map[f_coll].get(n_rar, [])
                if not f_inputs or not f_outputs:
                    continue
                    
                collection_input_prices = []
                for item in f_inputs:
                    w, fl = get_baseline_wear_and_float(item['min_float'], item['max_float'], i_rar, float_strategy)
                    item['assumed_float'] = fl
                    skin_name = format_specific_market_name(item['weapon'], item['skin_name'], w)
                    item['market_hash_name'] = skin_name
                    
                    if skin_name not in live_prices:
                        listings = await fetcher.fetch_listings(skin_name)
                        live_prices[skin_name] = min(listings, key=lambda x: x.price).price if listings else 9999.0
                        await asyncio.sleep(1.5)
                    collection_input_prices.append(live_prices[skin_name])
                if collection_input_prices:
                    filler_collection_costs[f_coll] = min(collection_input_prices)
                    
            if not filler_collection_costs:
                continue
                
            cheapest_filler = min(filler_collection_costs, key=filler_collection_costs.get)
            f_inputs = collection_map[cheapest_filler].get(i_rar, [])
            f_outputs = collection_map[cheapest_filler].get(n_rar, [])
            
            for item in target_inputs:
                skin = item['market_hash_name']
                if skin not in live_prices:
                    listings = await fetcher.fetch_listings(skin)
                    live_prices[skin] = min(listings, key=lambda x: x.price).price if listings else 9999.0
                    await asyncio.sleep(1.5)
                    
            t_input = min(target_inputs, key=lambda x: live_prices.get(x["market_hash_name"], 9999))
            f_input = min(f_inputs, key=lambda x: live_prices.get(x["market_hash_name"], 9999))
            target_cost = live_prices.get(t_input["market_hash_name"], 0)
            filler_cost = live_prices.get(f_input["market_hash_name"], 0)
            
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
                    
                for out in f_outputs:
                    out_float = calculate_output_float(floats, mins, maxs, out['min_float'], out['max_float'])
                    wear = get_wear_condition(out_float)
                    hash_name = format_specific_market_name(out['weapon'], out['skin_name'], wear)
                    combo_outputs[target_qty]['filler_outputs'].append({'hash_name': hash_name, 'out_float': out_float})
                    required_output_skins.add(hash_name)

            for skin in required_output_skins:
                if skin not in live_prices:
                    listings = await fetcher.fetch_listings(skin)
                    live_prices[skin] = min(listings, key=lambda x: x.price).price if listings else 9999.0
                    await asyncio.sleep(1.5)
            
            valid_combinations = []
            for target_qty in range(1, 10):
                filler_qty = 10 - target_qty
                total_cost = (target_qty * target_cost) + (filler_qty * filler_cost)
                if total_cost <= 0 or total_cost > 9000: continue
                
                target_prob = target_qty / 10.0
                filler_prob = filler_qty / 10.0
                expected_revenue = 0.0
                
                t_outs = combo_outputs[target_qty]['target_outputs']
                f_outs = combo_outputs[target_qty]['filler_outputs']
                
                prob_per_target = target_prob / len(t_outs)
                for out in t_outs:
                    expected_revenue += prob_per_target * (live_prices.get(out["hash_name"], 0) * 0.98)
                    
                prob_per_filler = filler_prob / len(f_outs)
                for out in f_outs:
                    expected_revenue += prob_per_filler * (live_prices.get(out["hash_name"], 0) * 0.98)
                    
                net_ev = expected_revenue - total_cost
                
                jackpot_skin = max(t_outs, key=lambda x: live_prices.get(x["hash_name"], 0))
                jackpot_payout = live_prices.get(jackpot_skin["hash_name"], 0) * 0.98
                
                if jackpot_payout > total_cost:
                    sustainability_score = total_cost / abs(net_ev) if net_ev != 0 else 9999.99
                    jackpot_chance_pct = prob_per_target * 100
                    avg_tries_to_hit = 100 / jackpot_chance_pct if jackpot_chance_pct > 0 else 0
                    
                    valid_combinations.append({
                        'target_qty': target_qty, 'filler_qty': filler_qty, 'total_cost': total_cost,
                        'net_ev': net_ev, 'sustainability_score': sustainability_score,
                        'jackpot_name': jackpot_skin['hash_name'], 'jackpot_chance_pct': jackpot_chance_pct,
                        'jackpot_payout': jackpot_payout, 'avg_tries_to_hit': avg_tries_to_hit,
                        'cost_to_hit': avg_tries_to_hit * total_cost,
                        'avg_input_float': combo_outputs[target_qty]['avg_input_float'],
                        'expected_output_float': jackpot_skin['out_float']
                    })
                    
            report_lines.append(f"## {t_coll}")
            report_lines.append(f"**Filler Collection:** {cheapest_filler}")
            report_lines.append(f"**Inputs:** {t_input['market_hash_name']} (${target_cost:.2f}) & {f_input['market_hash_name']} (${filler_cost:.2f})\n")
            
            if not valid_combinations:
                report_lines.append("[-] No combinations found where the Jackpot covers the total cost.\n")
            else:
                valid_combinations.sort(key=lambda x: x['sustainability_score'], reverse=True)
                for combo in valid_combinations:
                    report_lines.append(f"### {combo['target_qty']}x Target + {combo['filler_qty']}x Filler")
                    
                    if combo['net_ev'] > 0:
                        report_lines.append(f"**[⚠️ POSITIVE EV ANOMALY (Penny Trade-up / Data Error)]**")
                    elif combo['sustainability_score'] < 2.0:
                        report_lines.append(f"**[📉 LOW SUSTAINABILITY]**")
                        
                    report_lines.append(f"- **Avg Input Float:** {combo['avg_input_float']:.5f} -> **Expected Output Float:** {combo['expected_output_float']:.5f}")
                    report_lines.append(f"- **Cost:** ${combo['total_cost']:.2f} | **Net EV:** ${combo['net_ev']:.2f}")
                    report_lines.append(f"- **Jackpot:** {combo['jackpot_name']} | **Chance:** {combo['jackpot_chance_pct']:.2f}% | **Payout (after tax):** ${combo['jackpot_payout']:.2f}")
                    report_lines.append(f"  - *Sustainability Score:* {combo['sustainability_score']:.2f} (Tries before losing 1 trade-up cost)")
                    report_lines.append(f"  - *Avg Tries to Hit:* {combo['avg_tries_to_hit']:.1f}")
                    report_lines.append(f"  - *Expected Cost to Hit:* ${combo['cost_to_hit']:.2f}\n")
            
    with open(os.path.join(os.path.dirname(__file__), "industrial_report.md"), "w", encoding="utf-8") as rf:
        rf.write("\n".join(report_lines))
        
    print("\nReport saved to industrial_report.md")

if __name__ == "__main__":
    asyncio.run(run_report())
