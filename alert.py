import requests

def send_pagerduty_alert(routing_key, incident_title, incident_detail):
    url = "https://events.pagerduty.com/v2/enqueue"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "payload": {
            "summary": incident_title,
            "source": "router-chain-monitor",
            "severity": "error",
            "custom_details": incident_detail
        }
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 202:
        print("Alert sent successfully.")
        return response.json()
    else:
        print(f"Failed to send alert. Status code: {response.status_code} {response.reason}")
        return response.text