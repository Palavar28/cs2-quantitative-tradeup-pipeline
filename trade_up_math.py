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

def calculate_output_float(input_floats: List[float], min_float: float, max_float: float) -> float:
    """
    Calculate the precise output float of a CS2 trade-up contract.
    
    Formula: Output Float = Min Float + (Max Float - Min Float) * Average(Input_Floats)
    
    Args:
        input_floats (List[float]): A list of exactly 10 float values representing the input skins.
        min_float (float): The minimum float value boundary of the desired output skin.
        max_float (float): The maximum float value boundary of the desired output skin.
        
    Returns:
        float: The calculated output float value.
        
    Raises:
        ValueError: If the input_floats list does not contain exactly 10 items.
        ValueError: If any float value in input_floats, min_float, or max_float is outside the 0.0 - 1.0 range.
        ValueError: If min_float is greater than or equal to max_float.
    """
    if len(input_floats) != 10:
        raise ValueError(f"A trade-up contract requires exactly 10 input skins, but got {len(input_floats)}.")
        
    for f in input_floats:
        if not (0.0 <= f <= 1.0):
            raise ValueError(f"Input float {f} is outside the valid range of 0.0 - 1.0.")
            
    if not (0.0 <= min_float <= 1.0):
        raise ValueError(f"Minimum float {min_float} is outside the valid range of 0.0 - 1.0.")
        
    if not (0.0 <= max_float <= 1.0):
        raise ValueError(f"Maximum float {max_float} is outside the valid range of 0.0 - 1.0.")
        
    if min_float >= max_float:
        raise ValueError(f"Minimum float ({min_float}) must be strictly less than maximum float ({max_float}).")
        
    avg_input_float = sum(input_floats) / len(input_floats)
    output_float = min_float + (max_float - min_float) * avg_input_float
    
    return output_float

if __name__ == "__main__":
    # Mock list of 10 inputs with an exact average of 0.135
    mock_inputs = [0.135 for _ in range(10)]
    
    avg_val = sum(mock_inputs) / len(mock_inputs)
    print(f"Simulating Trade-up with 10 skins.")
    print(f"Average Input Float: {avg_val:.5f}")
    print("=" * 50)
    
    for skin_name, data in SKIN_DATABASE.items():
        try:
            out_float = calculate_output_float(
                input_floats=mock_inputs, 
                min_float=data["min_float"], 
                max_float=data["max_float"]
            )
            print(f"Target Skin: {skin_name}")
            print(f"Float Range: [{data['min_float']:.2f}, {data['max_float']:.2f}]")
            print(f"Calculated Output Float: {out_float:.6f}")
            print("-" * 50)
        except ValueError as e:
            print(f"Error calculating {skin_name}: {e}")
            print("-" * 50)
