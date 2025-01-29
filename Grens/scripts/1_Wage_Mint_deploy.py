import os
from brownie import WageMint, accounts
from time import sleep
from brownie.network.gas.strategies import LinearScalingStrategy
from brownie.network import gas_price
gas_strategy = LinearScalingStrategy("120 gwei", "1200 gwei", 1.1)

gas_price(gas_strategy)


def main():
    # Load the deployer account
    deployer = accounts.load('test2')  # Make sure 'test2' is added to Brownie accounts
    # with open('GasInWei.txt', 'r') as f:
    #     gas_price = f.read().strip()
    # gas_limit = 5000000  # Adjust as necessary

    # Read the LamportBase address from the file
    # lamport_base_address = None
    # try:
    #     with open('Activity-LamportBase2.txt', 'r') as f:
    #         lamport_base_address = f.read().strip()
    # except FileNotFoundError:
    #     print("Error: Activity-LamportBase2.txt not found.")
    #     return

    # Read the initial authorized minter address from the file
    # initial_authorized_minter = None
    # try:
    #     with open('TheBase-commissionaddress.txt', 'r') as f:
    #         initial_authorized_minter = f.read().strip()
    # except FileNotFoundError:
    #     print("Error: TheBase-commissionaddress.txt not found.")
    #     return

    
    warning = input("STOP MASHING ENTER HERE. ENTER TOKEN NAMES NEXT LINE.") or "null"
    name = input("Please input the token name (default 'Test'): ") or "Test"
    symbol = input("Please input the token symbol (default 'ATest'): ") or "ATest"

    # Deploy the contract
    your_contract = WageMint.deploy(
        #  initial_authorized_minter,
        name,
        symbol,

        {'from': deployer,   'required_confs': 3}
    )
    sleep(1)
    # Output the contract address to a file
    with open('Mint-address.txt', 'w') as f:
        f.write(str(your_contract.address))

    # Display deployment details
    print(f"Contract deployed at address: {your_contract.address}")
    #print(f"Initial Mint goes to: {initial_authorized_minter}")

    print(f"Token name: {name}")
    print(f"Token symbol: {symbol}")
