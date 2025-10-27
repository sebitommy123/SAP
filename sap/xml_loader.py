"""
XML loader module for converting XML files to SA objects.
"""
import xml.etree.ElementTree as ET
import re
from typing import List, Dict, Any, Optional
from .models import make_object
from .sap_types import link


def _sanitize_id(path: str) -> str:
    """
    Convert XML path to a valid SA object ID.
    Allows alphanumeric characters, underscores, dashes, and forward slashes.
    """
    # Replace special characters but keep forward slashes, dashes, and underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_/-]', '_', path)
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    # Ensure it starts with a letter or underscore
    if sanitized and not re.match(r'^[a-zA-Z_]', sanitized):
        sanitized = 'xml_' + sanitized
    return sanitized or 'xml_root'


def _get_xml_path(element: ET.Element, parent_path: str = "") -> str:
    """
    Generate a unique path for an XML element based on its position in the tree.
    Uses "/" as path separators and "-" for indices.
    """
    if parent_path:
        current_path = f"{parent_path}/{element.tag}"
    else:
        current_path = element.tag
    
    # Add index if there are siblings with the same tag
    parent = element.getparent() if hasattr(element, 'getparent') else None
    if parent is not None:
        siblings = [child for child in parent if child.tag == element.tag]
        if len(siblings) > 1:
            index = siblings.index(element)
            current_path = f"{current_path}-{index}"
    
    return current_path


def _xml_to_sa_objects(element: ET.Element, source: str, type_name: str, root_element_id: str, parent_path: str = "", parent_id: Optional[str] = None, sibling_counts: Optional[Dict[str, int]] = None, parent_element: Optional[ET.Element] = None) -> List[Dict[str, Any]]:
    """
    Recursively convert XML elements to SA objects.
    """
    objects = []
    
    # Initialize sibling counts if not provided
    if sibling_counts is None:
        sibling_counts = {}
    
    # First pass: count all siblings to determine if we need indices
    tag_key = f"{parent_path}/{element.tag}" if parent_path else element.tag
    if tag_key not in sibling_counts:
        # Count all siblings with the same tag
        if parent_element is not None:
            siblings = [child for child in parent_element if child.tag == element.tag]
            sibling_counts[tag_key] = len(siblings)
        else:
            sibling_counts[tag_key] = 1
    
    # Generate current element's path and ID
    current_path = _get_xml_path_with_counts(element, parent_path, sibling_counts, parent_element)
    current_id = f"xml_{_sanitize_id(current_path)}"
    
    # Create attributes dictionary
    attributes = dict(element.attrib) if element.attrib else {}
    
    # Determine if this element has text content or child elements
    has_text = element.text and element.text.strip()
    has_children = len(element) > 0

    properties = {}

    children_names = [child.tag for child in element]
    for child in element:
        tag_occurences = len([name for name in children_names if name == child.tag])
        if tag_occurences == 1:
            properties[child.tag] = link(f"{type_name}#'{current_id}/{child.tag}'", child.tag)
    
    for attribute in attributes:
        properties[attribute] = element.attrib[attribute]
    
    # Create properties for this XML node
    properties.update({
        "tag": element.tag,
        "attributes": attributes,
        "children": link(f"{type_name}[.parent.# == '{current_id}']", "Children"),
    })
    
    # Add parent link if this is not the root element
    if parent_id is not None:
        properties["parent"] = link(f"{type_name}#'{parent_id}'", parent_id)
    
    # Add value if the element has text content and no children
    if has_text and not has_children:
        properties["value"] = element.text.strip()

    if parent_element is None:
        current_id = root_element_id
    
    # Create the SA object for this XML node
    xml_object = make_object(
        id=current_id,
        types=[type_name],
        source=source,
        properties=properties,
    )
    
    objects.append(xml_object)
    
    # Track sibling counts for child elements
    child_sibling_counts = {}
    
    # Recursively process child elements
    for child in element:
        child_objects = _xml_to_sa_objects(child, source, type_name, root_element_id, current_path, current_id, child_sibling_counts, element)
        objects.extend(child_objects)
    
    return objects


def _get_xml_path_with_counts(element: ET.Element, parent_path: str, sibling_counts: Dict[str, int], parent_element: Optional[ET.Element] = None) -> str:
    """
    Generate a unique path for an XML element with proper sibling counting.
    """
    if parent_path:
        current_path = f"{parent_path}/{element.tag}"
    else:
        current_path = element.tag
    
    # Get the total count of siblings with the same tag
    tag_key = f"{parent_path}/{element.tag}" if parent_path else element.tag
    total_siblings = sibling_counts.get(tag_key, 1)
    
    # Only add index if there are multiple siblings with the same tag
    if total_siblings > 1:
        # Find the position of this element among its siblings
        if parent_element is not None:
            siblings = [child for child in parent_element if child.tag == element.tag]
            index = siblings.index(element) + 1
            current_path = f"{current_path}-{index}"
    
    return current_path


def load_xml(file_path: str, source: str, type_name: str, root_element_id: str) -> List[Dict[str, Any]]:
    """
    Load an XML file and convert all nodes to SA objects.
    
    Args:
        file_path: Path to the XML file
        source: Source identifier for the SA objects
        
    Returns:
        List of SA objects representing the XML structure
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Convert the entire XML tree to SA objects
        objects = _xml_to_sa_objects(root, source, f"{type_name}_xml_node", root_element_id)
        
        return objects
        
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse XML file '{file_path}': {e}")
    except FileNotFoundError:
        raise FileNotFoundError(f"XML file '{file_path}' not found")
    except Exception as e:
        raise RuntimeError(f"Error loading XML file '{file_path}': {e}")
