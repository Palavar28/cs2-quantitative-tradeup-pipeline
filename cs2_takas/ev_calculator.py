import sys
from typing import List, Dict, Any
from trade_up_math import calculate_output_float

def get_wear_condition(float_value: float) -> str:
    """Strictly maps a float value to a CS2 wear condition."""
    if 0.0 <= float_value < 0.07:
        return "Factory New"
    elif 0.07 <= float_value < 0.15:
        return "Minimal Wear"
    elif 0.15 <= float_value < 0.223:
        return "Good Field-Tested"
    elif 0.223 <= float_value < 0.296:
        return "Average Field-Tested"
    elif 0.296 <= float_value < 0.37:
        return "Bad Field-Tested"
    elif 0.37 <= float_value < 0.44:
        return "Well-Worn"
    elif 0.44 <= float_value < 0.626:
        return "Good Battle-Scarred"
    elif 0.626 <= float_value < 0.812:
        return "Average Battle-Scarred"
    elif 0.812 <= float_value <= 1.00:
        return "Bad Battle-Scarred"
    else:
        raise ValueError(f"Invalid float value: {float_value}")

def calculate_trade_up_profitability(input_skins: List[Dict[str, Any]], possible_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates the expected value and ROI for a given CS2 trade-up.
    """
    if len(input_skins) != 10:
        raise ValueError("A CS2 trade-up must contain exactly 10 input skins.")

    # Calculate total input cost
    total_input_cost = sum(skin["price_usd"] for skin in input_skins)
    
    # Extract input floats
    input_floats = [skin["float_value"] for skin in input_skins]

    expected_value_sum = 0.0
    outcomes = []

    for output in possible_outputs:
        # Calculate exact output float
        out_float = calculate_output_float(
            input_floats=input_floats,
            min_float=output["min_float"],
            max_float=output["max_float"]
        )
        
        # Determine wear condition
        wear_condition = get_wear_condition(out_float)
        
        # Retrieve expected market price
        market_price = output["price_map"].get(wear_condition, 0.0)
        
        # No Steam tax applied for CSFloat prices
        post_tax_price = market_price*0.98
        
        # Probability weighted value
        probability = output["probability"]
        outcome_ev_contribution = probability * post_tax_price
        expected_value_sum += outcome_ev_contribution
        
        outcomes.append({
            "name": output["name"],
            "probability": probability,
            "calculated_float": out_float,
            "wear_condition": wear_condition,
            "market_price": market_price,
            "post_tax_price": post_tax_price
        })

    # EV is (Sum of Probability * Post_Tax_Price) - Cost
    total_ev = expected_value_sum - total_input_cost
    roi = (total_ev / total_input_cost) * 100 if total_input_cost > 0 else 0.0

    return {
        "total_input_cost": total_input_cost,
        "total_ev": total_ev,
        "roi_percentage": roi,
        "outcomes": outcomes
    }

def print_ev_report(results: Dict[str, Any]):
    """Prints a clean, formatted report of the Trade-up EV analysis."""
    print("=" * 50)
    print("CS2 TRADE-UP EV REPORT")
    print("=" * 50)
    
    print(f"Total Input Cost: ${results['total_input_cost']:.2f}")
    print(f"Expected Value (EV): ${results['total_ev']:.2f}")
    print(f"ROI: {results['roi_percentage']:.2f}%\n")
    
    print("--- Outcomes ---")
    for outcome in results['outcomes']:
        print(f"Skin: {outcome['name']}")
        print(f"  Odds: {outcome['probability'] * 100:.1f}%")
        print(f"  Expected Float: {outcome['calculated_float']:.5f} ({outcome['wear_condition']})")
        print(f"  Market Price: ${outcome['market_price']:.2f} (Post-Tax: ${outcome['post_tax_price']:.2f})")
    
    print("-" * 50)
    if results['total_ev'] > 0:
        print("RECOMMENDATION: [ PROCEED ] - This trade-up is mathematically profitable.")
    else:
        print("RECOMMENDATION: [ ABORT ] - This trade-up loses money on average.")
    print("=" * 50)


if __name__ == "__main__":
    # Mock testing block
    # 10 fake input skins, approx total cost $25.00
    mock_inputs = [
        {"price_usd": 2.50, "float_value": 0.12},
        {"price_usd": 2.45, "float_value": 0.11},
        {"price_usd": 2.55, "float_value": 0.13},
        {"price_usd": 2.50, "float_value": 0.14},
        {"price_usd": 2.60, "float_value": 0.10},
        {"price_usd": 2.40, "float_value": 0.15},
        {"price_usd": 2.50, "float_value": 0.12},
        {"price_usd": 2.45, "float_value": 0.13},
        {"price_usd": 2.55, "float_value": 0.12},
        {"price_usd": 2.50, "float_value": 0.11},
    ]
    
    # 2 fake possible outcomes (50% odds each)
    mock_outputs = [
        {
            "name": "AK-47 | Redline",
            "probability": 0.50,
            "min_float": 0.10,
            "max_float": 0.70,
            "price_map": {
                "Minimal Wear": 45.00,
                "Good Field-Tested": 30.00,
                "Average Field-Tested": 25.00,
                "Bad Field-Tested": 22.00,
                "Well-Worn": 18.00,
                "Good Battle-Scarred": 14.00,
                "Average Battle-Scarred": 12.00,
                "Bad Battle-Scarred": 10.00
            }
        },
        {
            "name": "AWP | Asiimov",
            "probability": 0.50,
            "min_float": 0.80,
            "max_float": 1.00,
            "price_map": {
                "Bad Battle-Scarred": 60.00
            }
        }
    ]
    
    try:
        results = calculate_trade_up_profitability(mock_inputs, mock_outputs)
        print_ev_report(results)
    except Exception as e:
        print(f"Error running EV Calculator: {e}")
