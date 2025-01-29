import os
from brownie import TFCWageDapp, WageMint, accounts
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
    # Read the MintContract address from the file

    with open('Mint-address.txt', 'r') as file:
        wage_mint_addy = file.read().strip()
    wage_mint = WageMint.at(wage_mint_addy)

    dapp = TFCWageDapp.deploy(

        wage_mint_addy,
        {'from': deployer,   'required_confs': 3}
    )
    sleep(1)
    tx = wage_mint.setAuthorizedMinter(dapp, {'from': deployer,  'required_confs': 0})

    # Output the contract address to a file
    with open('Dapp-address.txt', 'w') as f:
        f.write(str(dapp.address))

    print(f"Mint contract referenced: {wage_mint_addy}")
    print(f"Dapp address deployed: {dapp}")
    print(f"Mint Minter address used: {dapp}")
