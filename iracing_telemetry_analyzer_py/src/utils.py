"""
Utility functions for the iRacing Telemetry Analyzer.
"""
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Union

def _to_xml_element(key: str, value: Any, parent_element: ET.Element) -> None:
    """
    Recursively converts a Python value to XML element(s) and appends to parent.
    - Dictionaries become nested elements.
    - Lists result in multiple elements with the same tag name.
    - Other values become text content of an element.
    """
    if isinstance(value, dict):
        # For a dict, create a new parent element with the key as its tag
        # Then, recursively add its items as children
        dict_element = ET.SubElement(parent_element, key)
        for sub_key, sub_value in value.items():
            _to_xml_element(sub_key, sub_value, dict_element)
    elif isinstance(value, list):
        # For a list, create multiple elements with the same tag name (key)
        # Each item in the list becomes a separate element.
        # The key here is often singular (e.g. "Driver" for a list of drivers)
        # If the key is plural (e.g. "Drivers"), each item might still use singular or a generic "item" tag.
        # For this generic helper, we'll use the provided key for each list item's element.
        # This means if key is "Drivers", we get <Drivers>...</Drivers>, <Drivers>...</Drivers>
        # A more sophisticated version might singularize the key for list items.
        # E.g. if key="Drivers", items become <Driver>...</Driver>
        # For now, repeating the key:
        for item in value:
            # Create a new element for each item in the list
            # If item itself is a dict, it will be handled by the dict case.
            # If item is a simple value, it will create <key>value</key>
            item_element = ET.SubElement(parent_element, key)
            if isinstance(item, (dict, list)): # If list items are complex
                 # This might lead to <Key><SubKey>...</SubKey></Key> if item is dict
                 # or nested lists.
                 # A common pattern for list of dicts: <Key_plural><Key_singular>...</Key_singular></Key_plural>
                 # This simple helper doesn't do that automatically.
                 # It would create: <ListKey>{dict_content_as_tags}</ListKey>
                 # Let's refine: if item is dict, don't use item_element.text, recurse
                if isinstance(item, dict):
                    for sub_key, sub_value in item.items():
                         _to_xml_element(sub_key, sub_value, item_element)
                else: # For lists of non-dicts (e.g., list of strings)
                    item_element.text = str(item)

            else: # Primitive value
                item_element.text = str(item)
    else:
        # For simple values, create an element with the key as tag and value as text
        element = ET.SubElement(parent_element, key)
        element.text = str(value)


def dict_to_xml_string(data_dict: Dict[str, Any], root_tag: str) -> str:
    """
    Converts a Python dictionary into a simple XML string.

    Args:
        data_dict: The dictionary to convert.
        root_tag: The tag name for the root XML element.

    Returns:
        An XML string representation of the dictionary.
    """
    if not isinstance(data_dict, dict):
        raise TypeError("Input 'data_dict' must be a dictionary.")
    if not isinstance(root_tag, str) or not root_tag:
        raise ValueError("Input 'root_tag' must be a non-empty string.")

    root = ET.Element(root_tag)
    for key, value in data_dict.items():
        _to_xml_element(key, value, root)

    # ET.indent(tree, space="  ", level=0) # Python 3.9+ for pretty print
    # For now, just tostring without indent for simplicity, as indent is not critical for data storage.
    xml_string = ET.tostring(root, encoding='unicode', method='xml')
    return xml_string

if __name__ == '__main__':
    print("--- dict_to_xml_string Demonstration ---")
    sample_dict_simple = {
        "name": "Test User",
        "age": "30", # XML typically uses strings for values unless schema specifies types
        "isMember": "true"
    }
    xml_simple = dict_to_xml_string(sample_dict_simple, "User")
    print("\nSimple Dictionary to XML:")
    print(xml_simple)
    # Expected: <User><name>Test User</name><age>30</age><isMember>true</isMember></User>

    sample_dict_nested = {
        "orderId": "12345",
        "customer": {
            "firstName": "John",
            "lastName": "Doe",
            "address": {
                "street": "123 Main St",
                "city": "Anytown"
            }
        },
        "notes": None # Test None value
    }
    xml_nested = dict_to_xml_string(sample_dict_nested, "Order")
    print("\nNested Dictionary to XML:")
    print(xml_nested)
    # Expected: <Order><orderId>12345</orderId><customer><firstName>John</firstName>...</customer><notes>None</notes></Order>

    sample_dict_with_list = {
        "courseName": "Python Programming",
        "students": [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"}
        ],
        "topics": ["Intro", "Variables", "Loops"] # List of simple strings
    }
    xml_list = dict_to_xml_string(sample_dict_with_list, "Course")
    print("\nDictionary with List to XML:")
    print(xml_list)
    # Expected (with current _to_xml_element for list of dicts):
    # <Course>
    #   <courseName>Python Programming</courseName>
    #   <students>  <!-- First student -->
    #     <id>1</id><name>Alice</name>
    #   </students>
    #   <students>  <!-- Second student -->
    #     <id>2</id><name>Bob</name>
    #   </students>
    #   <topics>Intro</topics>
    #   <topics>Variables</topics>
    #   <topics>Loops</topics>
    # </Course>

    # Test with a dictionary that might resemble iRacing SessionInfo structure
    sample_session_info = {
        "WeekendInfo": {
            "TrackName": "Daytona International Speedway",
            "TrackID": "1",
            "SessionID": "123456"
        },
        "DriverInfo": {
            "DriverHeadPosX": "0.123",
            "Drivers": [
                {"CarIdx": "0", "UserName": "Player One", "CarNumber": "101"},
                {"CarIdx": "1", "UserName": "AI Driver 1", "CarNumber": "102"},
                {"CarIdx": "2", "UserName": "AI Driver 2", "CarNumber": "103"}
            ]
        },
        "QualifyResultsInfo": {
            # This might be empty or None if not applicable
        }
    }
    xml_session = dict_to_xml_string(sample_session_info, "SessionInfo")
    print("\nSample SessionInfo-like Dictionary to XML:")
    print(xml_session)
    # Verify that this output can be stored in OverlayData.session_data_xml
```
