# scripts/block_cycler.py

from brownie import accounts, web3, network
from brownie.exceptions import VirtualMachineError
import time
import os
from web3 import Web3
from brownie.network.gas.strategies import LinearScalingStrategy
from brownie.network import gas_price
gas_strategy = LinearScalingStrategy("120 gwei", "1200 gwei", 1.1)

gas_price(gas_strategy)

def main():
    """
    Block Cycler for Ganache:
    - Continuously sends 1 wei from the sender account to the test2 account to mine new blocks.
    - Includes error handling and delays to ensure smooth operation.
    """

    # -----------------------------
    # 1. Configuration
    # -----------------------------

    # Interval settings
    block_interval = 3       # Seconds between each block cycle
    time_increment = 0       # Seconds to advance blockchain time each cycle (set to 0 if not needed)

    # Minimal transfer amount to trigger block mining
    transfer_amount = 1       # 1 wei

    # -----------------------------
    # 2. Network Verification
    # -----------------------------

    if network.show_active() != 'development':
        print("Please run this script on the 'development' network (Ganache).")
        return

    # -----------------------------
    # 3. Load the 'test2' Account
    # -----------------------------

    try:
        test2 = accounts.load('test2')  # 'test2' is the alias
    except Exception as e:
        print(f"Error loading 'test2' account: {e}")
        return

    # -----------------------------
    # 4. Load the Sender Account
    # -----------------------------

    # Retrieve the sender's private key from the environment variable
    sender_private_key = "0xc05e835b0dace5ff99a46432faf5561a58755edda8d53259051dc6bfa24f5c35"

    # Derive the sender's address from the private key
    try:
        sender_account = web3.eth.account.from_key(sender_private_key)
        sender_address = sender_account.address
    except Exception as e:
        print(f"Error deriving sender address from private key: {e}")
        return

    # -----------------------------
    # 5. Initialize Web3
    # -----------------------------

    w3 = network.web3

    # -----------------------------
    # 6. Verify Sender Balance
    # -----------------------------

    try:
        balance = w3.eth.get_balance(sender_address)
        print(f"Sender balance: {w3.from_wei(balance, 'ether')} ETH")
    except Exception as e:
        print(f"Error fetching sender balance: {e}")
        return

    if balance < transfer_amount:
        print(f"Insufficient balance to send {transfer_amount} wei.")
        return

    # -----------------------------
    # 7. Start the Block Cycler
    # -----------------------------

    print("Starting Block Cycler...")
    try:
        while True:
            # 1. Advance Blockchain Time (Optional)
            if time_increment > 0:
                advance_time(w3, time_increment)

            # 2. Mine a New Block by Sending a Minimal Transaction
            mine_block(w3, sender_private_key, sender_address, test2.address, transfer_amount)

            print(f"Sent {transfer_amount} wei from {sender_address} to {test2.address}.")
            print(f"New balance of test2: {w3.from_wei(w3.eth.get_balance(test2.address), 'ether')} ETH\n")

            # 3. Sleep before next cycle
            time.sleep(block_interval)
    except KeyboardInterrupt:
        print("\nBlock Cycler stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def get_private_key_securely():
    """
    Securely retrieves the sender's private key from the environment variable.
    """
    private_key = os.getenv('SENDER_PRIVATE_KEY')
    if not private_key:
        raise ValueError("SENDER_PRIVATE_KEY environment variable not set.")
    # Validate the private key format
    if not isinstance(private_key, str) or not private_key.startswith('0x') or len(private_key) != 66:
        raise ValueError("Invalid private key format. Ensure it is a 66-character hexadecimal string starting with '0x'.")
    return private_key

def advance_time(w3, seconds):
    """
    Advances the blockchain time by the specified number of seconds.
    """
    try:
        w3.provider.make_request("evm_increaseTime", [seconds])
        w3.provider.make_request("evm_mine", [])  # Mine a new block to apply the time change
        print(f"Advanced blockchain time by {seconds} seconds.")
    except Exception as e:
        print(f"Error advancing time: {e}")

def mine_block(w3, private_key, sender_address, receiver_address, amount):
    """
    Mines a new block by sending a minimal transaction.
    """
    try:
        # Create the transaction dictionary
        tx = {
            'from': sender_address,
            'to': receiver_address,
            'value': amount,
            'gas': web3.to_wei("0.03", "gwei"),  # Standard gas limit for ETH transfer
            'gasPrice': web3.to_wei("120", "gwei"),
            'nonce': w3.eth.get_transaction_count(sender_address),
        }

        # Sign the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)

        # Send the signed transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        # Wait for the transaction to be mined
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    except VirtualMachineError as vm_err:
        print(f"VM Error while sending transaction: {vm_err}")
    except Exception as e:
        print(f"Error while sending transaction: {e}")
