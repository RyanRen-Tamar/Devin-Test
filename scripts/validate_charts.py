"""Validate chart configurations in the final report."""
import json
import re

def validate_chart_config(config_str):
    """Validate a single chart configuration."""
    try:
        config = json.loads(config_str)
        if "type" not in config or "data" not in config:
            return False, "Missing required fields: type or data"
        if config["type"] not in ["bar", "line", "gauge"]:
            return False, f"Invalid chart type: {config['type']}"
        return True, "Valid configuration"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}"

def main():
    """Main validation function."""
    print("[INFO] Validating chart configurations...")
    
    with open("data/final_report.md", "r") as f:
        content = f.read()

    chart_blocks = re.findall(r"```chart\n(.*?)\n```", content, re.DOTALL)
    print(f"\nFound {len(chart_blocks)} chart configurations")

    for i, chart in enumerate(chart_blocks, 1):
        print(f"\nValidating Chart {i}:")
        print(chart)
        is_valid, message = validate_chart_config(chart)
        print(f"Result: {message}")
        if not is_valid:
            raise ValueError(f"Chart {i} validation failed: {message}")

    print("\n[SUCCESS] All chart configurations are valid")

if __name__ == "__main__":
    main()
