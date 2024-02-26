import os
import json
import requests
import time
import concurrent.futures
from web3 import Web3
from collections import defaultdict
from dotenv import load_dotenv
from enum import Enum
from utils.read_config import ConfigManager

class ValidatorInfo:
    def __init__(self, lcd_url) -> None:
        self.lcd_url = lcd_url
    
    def fetch_json(self, url):
        try:
            response = requests.get(url)
            return response.json()
        except Exception as e:
            print(f'Error fetching {url}: {str(e)}')
            raise e

    def get_validator_info(self, validator_address):
        if not validator_address:
            print("Validator address is not provided.")
            return None
        if not self.lcd_url:
            print("LCD URL is not provided.")
            return None
    
        endpoint = self.lcd_url
        validators_info_endpoint = f"{endpoint}/cosmos/staking/v1beta1/validators/{validator_address}"
        result = self.fetch_json(validators_info_endpoint)
        return result

    def validate_info(self, validator_info):
        isHealthy = True
        if not validator_info:
            print("Validator info is not provided.")
            return None
        val_info=validator_info.get('validator', {})
        if not val_info:
            print("Validator info is not provided.")
            return None
        moniker=val_info.get('description', {}).get('moniker', '')
        jailed_status=val_info.get('jailed', False)
        if not moniker:
            print("Moniker is not provided.")
            isHealthy = False
        if jailed_status:
            print("Validator is jailed.")
            isHealthy = False
        res = {
            "moniker": moniker,
            "isHealthy": isHealthy,
            "jailed": jailed_status,
            "validator_address": val_info.get('operator_address', ''),
        }
        return res