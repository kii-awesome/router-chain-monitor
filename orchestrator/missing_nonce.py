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

load_dotenv()

class ContractType(Enum):
    GATEWAY = 'GATEWAY'
    VOYAGER = 'VOYAGER'

class MissingNonceOrchestrator:
    ABI = {
        'GATEWAY': "./artifacts/Gateway-ABI.json",
        'VOYAGER': "./artifacts/Voyager-ABI.json"
    }
    CHAIN_CONFIG = "/artifacts/chainInfos.json"
    CWD = os.getcwd()

    def __init__(self,config_manager):
        self.config_manager = config_manager
        self.DEBUG_MODE=self.config_manager.read_config('settings.debug_mode', 'False')
        self.VALIDATOR_ADDRESS=self.config_manager.read_config('settings.validator_address', '')
        self.SLEEP_TIME_FOR_EVENT_PROCESSING_IN_SEC = int(self.config_manager.read_config('settings.orch_sleep_time_for_event_processing_in_sec', 2))
        self.CHAIN_ENV = self.config_manager.read_config('settings.environment', 'testnet')
        self.lcd_url = self.config_manager.read_config('settings.lcd_url', '')


    def print_debug(self, *args, **kwargs):
        if self.DEBUG_MODE:
            print(*args, **kwargs)

    def fetch_json(self, url):
        try:
            response = requests.get(url)
            return response.json()
        except Exception as e:
            print(f'Error fetching {url}: {str(e)}')
            raise e

    def get_network(self):
        env = self.CHAIN_ENV
        env = env.lower()
        network_map = {
            'devnet': 'devnet',
            'testnet': 'testnet',
            'devnet-alpha': 'devnet-alpha',
            'mainnet': 'mainnet'
        }
        return network_map.get(env, '')

    def get_recent_nonce(self, rpc, address, contract_type):
        try:
            rpc = rpc.strip()        
            with open(self.ABI[contract_type.value]) as f:
                contract_json = json.load(f)
            web3_instance = Web3(Web3.HTTPProvider(rpc))
            address=Web3.to_checksum_address(address.lower())
            contract = web3_instance.eth.contract(address=address, abi=contract_json['abi'])
            if contract_type == ContractType.GATEWAY:
                response = int(contract.functions.eventNonce().call())
            else:
                response = int(contract.functions.depositNonce().call())
            return response
        except Exception as e:
            print(f'Error fetching nonce for {address}: {str(e)}')
            print(e.__traceback__)
            return 0

    def fetch_data(self, url):
        try:
            response = requests.get(url)
            return response.json()
        except Exception as e:
            print(e)
            return None

    def group_by_chain_id(self, array):
        result = defaultdict(list)
        for item in array:
            result[item['chainId']].append(item)
        return result

    def group_by_validator_address(self, array):
        result = defaultdict(list)
        for item in array:
            result[item['moniker']].append(item)
        return result

    def get_all_supported_chain(self, multi_chain_config_result):
        all_supported_chains=[]
        for chain_config in multi_chain_config_result['contractConfig']:
            chain_id = chain_config['chainId']
            all_supported_chains.append(chain_id)
        all_supported_chains = list(dict.fromkeys(all_supported_chains))
        return all_supported_chains

    def get_multi_chain_config(self, multi_chain_config_result):
        multi_chain_config = {}
        for chain_config in multi_chain_config_result['contractConfig']:
            if chain_config['contract_enabled'] == False:
                continue
            chain_id = chain_config['chainId']
            contract_type = chain_config['contractType']
            contract_address = chain_config['contractAddress']
            config = multi_chain_config.get(chain_id, ["", ""])
            if contract_type == ContractType.GATEWAY.value:
                config[0] = contract_address
            if contract_type == ContractType.VOYAGER.value:
                config[1] = contract_address
            multi_chain_config[chain_id] = config
        return multi_chain_config

    def process_chain_by_id(self, args):
        chain_id, chain_config, endpoint, result, multi_chain_config, contract_type = args
        return self.process_chain(chain_id, chain_config, endpoint, result, multi_chain_config, contract_type)

    def truncate_address(self, address, keep=10):
        return address[:keep] + '...' + address[-keep:]

    def process_validator(self, args):
        validator, endpoint, chain_id, contract_config, onchain_event_nonce, name, chain_buffer_nonce, contract_type, contract_address = args
        current_power = 0
        validator_address = validator['operator_address']
        last_nonce_handled_uri = f"{endpoint}/router-protocol/router-chain/attestation/last_event_nonce/{chain_id}/{contract_address}/{validator_address}"
        last_executed_nonce_data = self.fetch_data(last_nonce_handled_uri)
        
        if not last_executed_nonce_data:
            print("last_executed_nonce_data not found")
            return None

        last_executed_nonce = int(last_executed_nonce_data['eventNonce'])
        if last_executed_nonce < (onchain_event_nonce - chain_buffer_nonce):
            current_power += int(validator['tokens'])
            self.print_debug(f"[❌] {self.truncate_address(validator_address)} - {name}({chain_id}) as last_executed_nonce {last_executed_nonce} < {onchain_event_nonce}")
        else:
            self.print_debug(f"[✅] {self.truncate_address(validator_address)} - {chain_id} as last_executed_nonce {last_executed_nonce} > onchain_event_nonce {onchain_event_nonce}")
        
        diff_nonces = onchain_event_nonce - last_executed_nonce
        return {
                'validator_address': validator_address,
                'chainId': chain_id,
                'latest_onchain_eventNonce': onchain_event_nonce,
                'lastest_val_executed_nonce': last_executed_nonce,
                'chain_name': name,
                'moniker': validator['description']['moniker'],
                'jailed': validator['jailed'],
                'diff_nonces': diff_nonces
            }

    def process_chain(self, chain_id, chain_config, endpoint, result, multi_chain_config, contract_type):
        rpc_url = chain_config['rpc']
        name=chain_config['name']
        chain_buffer_nonce=chain_config['buffer']
        contract_config = multi_chain_config.get(chain_id)
        contract_address = contract_config[0]
        if contract_type == ContractType.VOYAGER:
            contract_address = contract_config[1]
        if not rpc_url or not contract_config or not contract_address:
            print(f"no rpc or contract config for chainId -> {chain_id}")
            return []
        onchain_event_nonce = self.get_recent_nonce(rpc_url, contract_address, contract_type)
        if not result or not result.get('validator'):
            print(f"Exiting! result is empty for chainId -> {chain_id} RPC -> {rpc_url} type -> {contract_type.value}")
            return []
        args_list=(result['validator'], endpoint, chain_id, contract_config, onchain_event_nonce, name, chain_buffer_nonce, contract_type, contract_address)
        res = self.process_validator(args_list)
        return res

    def get_orchestrators_by_pending_nonce(self, validator_info, contract_type="GATEWAY"):
        contract_type = ContractType(contract_type)
        if contract_type not in ContractType:
            print("contract_type is not supported, exiting")
            return None

        # validators_info_endpoint = f"{endpoint}/cosmos/staking/v1beta1/validators/{self.VALIDATOR_ADDRESS}"
        # validator_info = self.fetch_json(validators_info_endpoint)

        endpoint = self.lcd_url
        multi_chain_endpoint = f"{endpoint}/router-protocol/router-chain/multichain/contract_config"
        multi_chain_config_result = self.fetch_json(multi_chain_endpoint)
        multi_chain_config = self.get_multi_chain_config(multi_chain_config_result)

        chain_config_file_path=self.CWD+self.CHAIN_CONFIG
        with open(chain_config_file_path) as f:
            chain_infos_json = json.load(f)
        
        chain_infos = dict(chain_infos_json)
        all_supported_chains = self.get_all_supported_chain(multi_chain_config_result)

        if all_supported_chains and len(all_supported_chains) > 0:
            chain_infos = {k: v for k, v in chain_infos.items() if k in all_supported_chains}
        else:
            print("no supported chains found, exiting")
            return None
        tasks = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            print(f'Processing {len(chain_infos)} chains: ', chain_infos.keys())
            args_list = [(chain_id, chain_config, endpoint, validator_info, multi_chain_config, contract_type) for chain_id, chain_config in chain_infos.items()]
            results = list(executor.map(self.process_chain_by_id, args_list))
        if not results:
            print("no results found, exiting")
            exit(1)
        return json.dumps(results, indent=4)
