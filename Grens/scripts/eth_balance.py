from brownie import network, accounts

def main():
    # Set the network if not already set
    # network.connect('amoy')  # Replace 'amoy' with your network of choice if different

    # Load your account
    account = accounts.load('test2')

    # Get balance
    balance = account.balance()

    # Convert balance to Ether (from Wei) and print
    print("Balance:", balance / 10**18, "ETH")

    print("test")