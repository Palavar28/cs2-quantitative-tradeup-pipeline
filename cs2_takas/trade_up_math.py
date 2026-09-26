from typing import List, Dict, TypedDict

class SkinData(TypedDict):
    min_float: float
    max_float: float

# Mock database of popular output skins with their min and max float values
SKIN_DATABASE: Dict[str, SkinData] = {
    "AK-47 | Redline": {"min_float": 0.10, "max_float": 0.70},
    "Glock-18 | Moonrise": {"min_float": 0.00, "max_float": 0.65},
    "AWP | Asiimov": {"min_float": 0.18, "max_float": 1.00}
}

def calculate_output_float(
    input_floats: List[float],
    input_min_floats: List[float],
    input_max_floats: List[float],
    output_min_float: float,
    output_max_float: float
) -> float:
    """
    Calculate the precise output float of a CS2 trade-up contract using the Normalized (Weighted) Float formula.
    
    Formula: 
    Normalized Input = (Actual - Min) / (Max - Min)
    Output Float = (Average Normalized Input * (Max Output - Min Output)) + Min Output
    """
    if len(input_floats) != 10 or len(input_min_floats) != 10 or len(input_max_floats) != 10:
        raise ValueError("A trade-up contract requires exactly 10 inputs (floats, mins, and maxes).")
        
    normalized_inputs = []
    for f, f_min, f_max in zip(input_floats, input_min_floats, input_max_floats):
        if f_max == f_min:
            normalized = 0.0 # Prevent division by zero if a skin has a fixed float (rare)
        else:
            normalized = (f - f_min) / (f_max - f_min)
        normalized_inputs.append(normalized)
        
    avg_normalized = sum(normalized_inputs) / 10.0
    output_float = (avg_normalized * (output_max_float - output_min_float)) + output_min_float
    
    return output_float

def get_wear_condition(float_value: float) -> str:
    """Returns the wear condition for a given float value."""
    if float_value < 0.07:
        return "Factory New"
    elif float_value < 0.15:
        return "Minimal Wear"
    elif float_value < 0.38:
        return "Field-Tested"
    elif float_value < 0.45:
        return "Well-Worn"
    else:
        return "Battle-Scarred"

if __name__ == "__main__":
    # Example scenario: 10 inputs with float 0.37, capped between 0.0 and 1.0
    mock_inputs = [0.37] * 10
    mock_mins = [0.0] * 10
    mock_maxes = [1.0] * 10
    
    print("Testing Weighted Float Formula")
    print(f"Inputs Avg Float: {sum(mock_inputs)/10:.5f}")
    
    out_float = calculate_output_float(mock_inputs, mock_mins, mock_maxes, 0.0, 0.08)
    print(f"Output Float (0.0 - 0.08 caps): {out_float:.5f} -> {get_wear_condition(out_float)}")
