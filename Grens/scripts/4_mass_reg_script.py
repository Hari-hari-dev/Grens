# scripts/mass_mint.py

import json
from brownie import accounts, Contract, network, TFCWageDapp
from brownie.exceptions import VirtualMachineError
from time import sleep
from brownie.network import gas_price
from brownie.network.gas.strategies import LinearScalingStrategy

gas_strategy = LinearScalingStrategy("120 gwei", "1200 gwei", 1.1)

# if network.show_active() == "development":
gas_price(gas_strategy)

def main():
    # -----------------------------
    # 1. Configuration
    # -----------------------------
    
    # Define the network you are interacting with
    # e.g., 'development', 'mainnet', 'ropsten', etc.

    # -----------------------------
    # 2. Load the Owner Account
    # -----------------------------
    
    # Replace 'owner_account' with the actual account name you have set up in Brownie
    try:
        owner_account = accounts.load('test2')  # Ensure you have 'owner_account' saved
    except Exception as e:
        print("Error loading owner account. Ensure the account is saved in Brownie.")
        print(e)
        return

    # -----------------------------
    # 3. Load the Contract
    # -----------------------------
    
    # Replace 'TFCWageDapp' with the actual contract name if different
    # Ensure the contract is deployed on the target network
    try:
        # If you have the contract ABI and address, you can load it like this:
        with open('Dapp-address.txt', 'r') as f:
            onboard_address = f.read().strip()
                
        _TFCWageDapp = TFCWageDapp.at(onboard_address)
    except Exception as e:
        print("Error loading the TFCWageDapp contract.")
        print(e)
        return

    # Alternatively, if deploying locally, you can use:
    # TFCWageDapp = TFCWageDapp[-1]  # Gets the latest deployment

    # -----------------------------
    # 4. Load Player Data from JSON
    # -----------------------------
    
    try:
        with open('player_wallets.json', 'r') as f:
            player_data = json.load(f)
    except Exception as e:
        print("Error reading 'player_wallets.json'. Ensure the file exists and is valid JSON.")
        print(e)
        return

    # -----------------------------
    # 5. Onboard Players
    # -----------------------------
    
    for player_name, data in player_data.items():
        address = data.get('address')

        # Validate the address
        if not address or not isinstance(address, str) or not address.startswith('0x') or len(address) != 42:
            print(f"Invalid address for player '{player_name}': {address}. Skipping.")
            continue

        print(f"Attempting to onboard player '{player_name}' with address {address}...")

        try:
            # Call the debugOnboard function
            # Ensure that the owner has the necessary permissions and the contract is connected correctly
            tx = _TFCWageDapp.debugOnboard(
                address,
                player_name,
                {'from': owner_account, 'required_confs': 0}
            )
            tx.wait(1)  # Wait for 1 block confirmation
            print(f"Successfully onboarded '{player_name}' at address {address}.")

        except VirtualMachineError as vm_err:
            # Handle reverts and other VM errors
            print(f"Failed to onboard '{player_name}' at address {address}. Reason:")
            print(vm_err)
            continue
        except Exception as e:
            # Handle other exceptions
            print(f"An unexpected error occurred while onboarding '{player_name}':")
            print(e)
            continue

        # Optional: Sleep between transactions to avoid potential issues
        sleep(1)  # Sleep for 1 second

    print("Mass onboarding process completed.")
