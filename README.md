# router-chain-monitor

## Config creation

### Create `config.yml` file with the following content

```bash
cp config.yml.example config.yml
```

#### `config.yml` breakdown

`operator_address`: Node Operator address
`validator_address`: Node Validator address
`orchestrator_address`: Orchestrator address
`min_wallet_balance`: Minimum wallet balance required for the node to be considered healthy.
`debug_mode`: Toggles additional logging for debugging purposes.
`pager_duty_routing`: Configures the PagerDuty routing key for alerting and incident management.
`orchestrator_health_endpoint`: Specifies the endpoint URL for checking the health of the orchestrator service.
`schedule_interval_seconds`: Sets the time interval (in seconds) for scheduling health checks.
`router_chain_lcd_url`: URL for the LCD endpoint of the Router chain.

Note:

1. `buffer` param mentioned in `chainInfos.json` this sets a tolerance level for nonce discrepancy, allowing the node to be considered healthy within a defined range behind the current on-chain nonce

1. `rpc`: public RPC endpoint for the external chains are mentioned, please update the RPC accordingly if required.

## Setup

### Run manually using

```bash
python3 main.py --config config.yml
```

### Using `docker-compose`

```bash
docker-compose up -d
```

