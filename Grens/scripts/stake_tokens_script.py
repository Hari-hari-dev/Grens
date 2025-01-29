from brownie import Activity_Mint, accounts

def main():
    # Load contract address from Activity_Mint.txt
    with open("Activity-Mint.txt", "r") as file:
        contract_address = file.readline().strip()

    # Define the test account (test2) and the staking amount
    test2 = accounts.load('test2')  # Ensure 'test2' is unlocked or set up in Brownie


    # Connect to the deployed contract
    activity_mint = Activity_Mint.at(contract_address)
    # Check staked balance
    staked_balance = activity_mint.stakedBalanceOf(test2.address)
    print(f"Staked Balance: {staked_balance / (10 ** 18)} tokens")
    stake_amount = float(input("Enter the amount of tokens to stake: "))  # Get amount to stake as input

    # Convert stake amount to the token's smallest unit (wei equivalent)
    stake_amount_wei = int(stake_amount * (10 ** 18))
    # Execute the stakeTokens function with the specified amount
    tx = activity_mint.stakeTokens(stake_amount_wei, {'from': test2})

    # Confirm and display transaction details
    print(f"Staked {stake_amount} tokens from account {test2.address}")
    print(f"Transaction details: {tx.info()}")

