import json
import os
import logging
import argparse
from typing import List, Dict, Any
import schedule
import time
from flask import Flask, jsonify
from threading import Thread

from orchestrator.missing_nonce import MissingNonceOrchestrator
from alert import send_pagerduty_alert
from orchestrator.health_check import validate_orchestrator_health
from utils.read_config import ConfigManager
from orchestrator.get_validator_info import ValidatorInfo

app = Flask(__name__)

class OrchestratorValidator:
    def __init__(self, config_file_path: str):
        self.config_manager = ConfigManager(config_file_path)
        self.pager_duty_routing = self.config_manager.read_config("settings.pager_duty_routing", "")
        self.orchestrator_health_endpoint = self.config_manager.read_config("settings.orchestrator_health_endpoint", "")
        self.schedule_interval_minutes = int(self.config_manager.read_config("settings.schedule_interval_minutes", "-1"))
        self.missing_nonce_orchestrator = MissingNonceOrchestrator(self.config_manager)
        self.validator_info = ValidatorInfo(self.config_manager.read_config("settings.lcd_url", ""))
        self.validator_address=self.config_manager.read_config('settings.validator_address', '')

    def get_filtered_results(self, result_json):
        return [r for r in result_json if isinstance(r, dict) and r.get('diff_nonces', 0) > 0]

    def send_alert(self, title: str, result: List[Dict[str, Any]]) -> None:
        # print(f"Alert: {title} - {json.dumps(result)}")
        if self.pager_duty_routing:
            send_pagerduty_alert(self.pager_duty_routing, title, json.dumps(result))
            logging.info("Alert sent: %s", title)
        else:
            logging.warning("PAGER_DUTY_ROUTING is not configured. Alert not sent.")

    def validate_orchestrator_health_endpoints(self) -> None:
        orch_health = validate_orchestrator_health(self.orchestrator_health_endpoint)
        if orch_health:
            alert_title = f"Orchestrator Health Alert. {len(orch_health)} RPCs are unhealthy."
            self.send_alert(alert_title, orch_health)
            logging.info("orch_health: %s", orch_health)
        else:
            logging.info("No unhealthy RPCs found or ORCHESTRATOR_HEALTH_ENDPOINT is not configured.")

    def validate_pending_nonce(self) -> None:
        val_info=self.validator_info.get_validator_info(self.validator_address)
        
        validator_health=self.validator_info.validate_info(val_info)
        if not validator_health.get('isHealthy', False):
            title = f"Validator Health Alert - {validator_health.get('moniker', '')} is unhealthy"
            self.send_alert(title, [validator_health])

        for source in ["GATEWAY", "VOYAGER"]:
            result = self.missing_nonce_orchestrator.get_orchestrators_by_pending_nonce(val_info, source)
            if not result:
                logging.error(f"Failed to get orchestrators by pending nonce for {source}.")
                continue
            result_json = json.loads(result)
            filtered_result = self.get_filtered_results(result_json)
            logging.info(f"filter_{source.lower()}_result: {filtered_result}")

            if filtered_result:
                title = f"{source} Orchestrator Alert - nonce behind for {len(filtered_result)} chains"
                self.send_alert(title, filtered_result)
    
    def check_health(self) -> Dict[str, Any]:
        """
        Perform on-demand health check and nonce validation, returning the results.
        """
        health_results = {}
        health_check = validate_orchestrator_health(self.orchestrator_health_endpoint)
        if health_check:
            health_results['orchestrator_health'] = health_check
        else:
            health_results['orchestrator_health'] = 'No unhealthy RPCs found or endpoint is not configured.'
        
        val_info=self.validator_info.get_validator_info(self.validator_address)
        validator_health=self.validator_info.validate_info(val_info)
        nonce_results = {}
        for source in ["GATEWAY", "VOYAGER"]:
            result = self.missing_nonce_orchestrator.get_orchestrators_by_pending_nonce(val_info, source)
            if result:
                result_json = json.loads(result)
                nonce_results[source] = self.get_filtered_results(result_json)
            else:
                nonce_results[source] = 'Failed to get data or none found.'
        
        # health_check: response of /health endpoint from orchestrator
        # nonce_validation: Validates current nonce and last processed nonce from Router Chain
        # validator_health: Validates if the validator is jailed or not

        return {
            'orchestrator_health':{
                'health_check': health_results["orchestrator_health"],
                'nonce_validation': nonce_results
            },
            'validator_health': validator_health
        }

@app.route('/health', methods=['GET'])
def check_health():
    print("Checking health...")
    results = validator.check_health()
    return jsonify(results)

def schedule_validator(validator: OrchestratorValidator):
    if validator.schedule_interval_minutes <= 0:
        logging.error("Invalid schedule interval. Cron job not scheduled")
        return
    schedule.every(validator.schedule_interval_minutes).minutes.do(validator.validate_pending_nonce)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Validate orchestrator health and pending nonces.")
    parser.add_argument('--config', type=str, help="Path to the JSON configuration file.", required=True)
    args = parser.parse_args()
    validator = OrchestratorValidator(args.config)
    logging.info(f"Reading configuration from {args.config}...")
    Thread(target=schedule_validator, args=(validator,), daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
