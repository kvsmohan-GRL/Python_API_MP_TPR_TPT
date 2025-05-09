def extract_enabled_keys(json_data):
    """
    Recursively extract all keys from JSON data where 'enable' is True
    and the node is a leaf node (has empty children array).

    Args:
        json_data: JSON data structure (list or dict)

    Returns:
        list: List of test case keys where enable is True and node is a leaf node
    """
    enabled_keys = []

    def is_test_case_node(node):
        return 'children' in node and node['children'] == []

    def traverse(node):
        if not isinstance(node, dict):
            return

        is_enabled = node.get('enable') is True
        has_key = 'key' in node

        if is_enabled and has_key and is_test_case_node(node):
            enabled_keys.append(node['key'])

        if 'children' in node and isinstance(node['children'], list):
            for child in node['children']:
                traverse(child)

    if isinstance(json_data, list):
        for item in json_data:
            traverse(item)
    else:
        traverse(json_data)

    return enabled_keys


if __name__ == "__main__":
    import json

    # Load JSON data from file
    with open('Test_cases_list_Sample_Test_20250508_0237.json', 'r') as file:
        json_data = json.load(file)

    # Extract enabled keys
    enabled_keys = extract_enabled_keys(json_data)

    # Save results to a JSON file
    with open('selected_test_cases.json', 'w') as output_file:
        json.dump(enabled_keys, output_file, indent=2)

    # Print confirmation
    print(f"{len(enabled_keys)} enabled keys extracted and saved to 'enabled_keys.json'.")
