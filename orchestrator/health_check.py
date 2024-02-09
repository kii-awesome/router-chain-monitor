import requests
from typing import Optional, List, Dict, Any

def fetch_health_data(api_url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch health data from a given API URL.
    
    :param api_url: URL of the API to fetch health data from.
    :return: JSON response as a dictionary, or None if an error occurs.
    """
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raises an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching health data: {e}")
        return None

def filter_unhealthy_chains(health_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Filter and return unhealthy chains from health data.
    
    :param health_data: Health data dictionary.
    :return: List of unhealthy chains or None if health_data is None.
    """
    if health_data is None:
        return None    
    return [health for health in health_data.get("healthSpecs", []) if not health.get("chainRpcHealth", False)]

def validate_orchestrator_health(url: str) -> Optional[List[Dict[str, Any]]]:
    """
    Validate orchestrator health by fetching and filtering health data.
    
    :param url: URL to fetch orchestrator health data from.
    :return: List of unhealthy chains or None if an error occurs or URL is empty.
    """
    if not url:
        print("URL is empty for Orchestrator Health. Skipping...")
        return None

    health_data = fetch_health_data(url)
    return filter_unhealthy_chains(health_data) if health_data is not None else None
