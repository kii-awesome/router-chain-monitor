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
from chain.balance_check import AccountBalanceFetcher

app = Flask(__name__)

class OrchestratorValidator:
    def __init__(self, config_file_path: str):
        self.config_manager = ConfigManager(config_file_path)
        self.pager_duty_routing = self.config_manager.read_config("settings.pager_duty_routing", "")
        self.orchestrator_health_endpoint = self.config_manager.read_config("settings.orchestrator_health_endpoint", "")
        self.schedule_interval_seconds = int(self.config_manager.read_config("settings.schedule_interval_seconds", "-1"))
        lcd_url=self.config_manager.read_config("settings.router_chain_lcd_url", "")
        self.operator_address=self.config_manager.read_config('settings.operator_address', '')
        self.missing_nonce_orchestrator = MissingNonceOrchestrator(self.config_manager)
        self.validator_info = ValidatorInfo(lcd_url)

        self.validator_address=self.config_manager.read_config('settings.validator_address', '')
        self.orchestrator_address=self.config_manager.read_config('settings.orchestrator_address', '')
        min_balance=self.config_manager.read_config('settings.min_wallet_balance', "4ROUTE")
        self.balance_fetcher = AccountBalanceFetcher(lcd_url,min_balance, self.validator_address, self.orchestrator_address)

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
        if not self.orchestrator_health_endpoint:
            logging.warning("ORCHESTRATOR_HEALTH_ENDPOINT is not configured. Skipping health check.")
            return
        orch_health = validate_orchestrator_health(self.orchestrator_health_endpoint)
        if orch_health:
            alert_title = f"Orchestrator Health Alert. {len(orch_health)} RPCs are unhealthy."
            self.send_alert(alert_title, orch_health)
            logging.info("orch_health: %s", orch_health)
        else:
            logging.info("No unhealthy RPCs found or ORCHESTRATOR_HEALTH_ENDPOINT is not configured.")

    def validate_pending_nonce(self) -> None:
        val_info=self.validator_info.get_validator_info(self.operator_address)
        
        # Validate validator health
        validator_health=self.validator_info.validate_info(val_info)
        if not validator_health.get('isHealthy', False):
            title = f"Validator Health Alert - {validator_health.get('moniker', '')} is unhealthy"
            self.send_alert(title, [validator_health])

        # Validate orchestrator health
        for source in ["GATEWAY", "VOYAGER"]:
            result = self.missing_nonce_orchestrator.get_orchestrators_by_pending_nonce(val_info, source)
            if not result:
                logging.error(f"Failed to get orchestrators by pending nonce for {source}.")
                continue
            result_json = json.loads(result)
            filtered_result = self.get_filtered_results(result_json)

            if filtered_result:
                title = f"{source} Orchestrator Alert - nonce behind for {len(filtered_result)} chains"
                self.send_alert(title, filtered_result)
        
        balance_results = self.balance_fetcher.validate_balances()
        isValidatorBalanceLow = balance_results.get('isValidatorBalanceLow', False)
        isOrchestratorBalanceLow = balance_results.get('isOrchestratorBalanceLow', False)
        if isValidatorBalanceLow:
            validator_balance = balance_results.get('validator_balance', 0)
            title = f"Validator Balance Alert - Validator balance is {validator_balance} for {self.validator_address}"
            self.send_alert(title, [validator_balance])
        if isOrchestratorBalanceLow:
            orchestrator_balance = balance_results.get('orchestrator_balance', 0)
            title = f"Orchestrator Balance Alert - Orchestrator balance is {orchestrator_balance} for {self.orchestrator_address}"
            self.send_alert(title, [orchestrator_balance])
    
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
        
        val_info=self.validator_info.get_validator_info(self.operator_address)
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

is_scheduler_running = False
def schedule_validator(validator: OrchestratorValidator):
    global is_scheduler_running
    if is_scheduler_running:
        logging.info("A scheduler process is already running. Stopping it before starting a new one.")
        schedule.clear()
        is_scheduler_running = False

    if validator.schedule_interval_seconds <= 0:
        logging.error("Invalid schedule interval. Cron job not scheduled")
        return
    print(f"Scheduling validator with interval {validator.schedule_interval_seconds} seconds...")
    schedule.every(validator.schedule_interval_seconds).seconds.do(validator.validate_pending_nonce)
    is_scheduler_running = True

    while True:
        schedule.run_pending()
        time.sleep(1)
        if not is_scheduler_running:
            break

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Validate orchestrator health and pending nonces.")
    parser.add_argument('--config', type=str, help="Path to the JSON configuration file.", required=True)
    args = parser.parse_args()
    validator = OrchestratorValidator(args.config)
    logging.info(f"Reading configuration from {args.config}...")
    Thread(target=schedule_validator, args=(validator,), daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
