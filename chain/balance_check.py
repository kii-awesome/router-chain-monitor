import requests

class AccountBalanceFetcher:
    def __init__(self, rpc,min_balance, validator_address, orchestrator_address):
        self.rpc = rpc
        self.validator_address = validator_address
        self.orchestrator_address = orchestrator_address
        self.min_balance = self.get_min_balance(min_balance)
        print('min balance', self.min_balance)

    def fetch_json(self, url):
        try:
            response = requests.get(url)
            return response.json()
        except Exception as e:
            print(f'Error fetching {url}: {str(e)}')
            raise e

    def get_min_balance(self, min_balance):
        try:
            if min_balance[-5:] == 'ROUTE':
                min_balance = int(min_balance[:-5])
            else:
                min_balance = 0
            return min_balance
        except:
            return 0
    
    def convert_to_float(self, balance):
        try:
            return float(balance)/10**18
        except:
            return 0
    
    def validate_balances(self):
        validator_balance = self.convert_to_float(self.fetch_balance_by_address(self.validator_address))
        orchestrator_balance = self.convert_to_float(self.fetch_balance_by_address(self.orchestrator_address))
        # convert balance of this type "89923000035815961600" to float by dividing by 10^18
        isValidatorBalanceLow = validator_balance < self.min_balance
        isOrchestratorBalanceLow = orchestrator_balance < self.min_balance
        return {
            "validator_balance": validator_balance,
            "orchestrator_balance": orchestrator_balance,
            "isValidatorBalanceLow": isValidatorBalanceLow,
            "isOrchestratorBalanceLow": isOrchestratorBalanceLow
        }

    def fetch_balance_by_address(self, address):
        url = f"{self.rpc}/cosmos/bank/v1beta1/balances/{address}?pagination.limit=1000"
        try:
            response = self.fetch_json(url)
            balances = response.get('balances', [])
            print('user balances', balances)
            return balances[0].get('amount', '0')
        except Exception as e:
            print(f'Error fetching balances for {address}: {str(e)}')
            return 0
            

# # Example usage
# async def main():
#     rpc = "RPC_ENDPOINT_HERE"
#     account_address = "ACCOUNT_ADDRESS_HERE"
#     fetcher = AccountBalanceFetcher(rpc, account_address)
#     balances = await fetcher.fetch_balances()
#     # Replace 'setBalances(balances)' with the equivalent Python code, depending on your application
#     # For
