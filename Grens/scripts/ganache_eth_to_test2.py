from brownie import accounts, web3

def main():
    # Load the test2 account to receive the ETH
    test2 = accounts.load('test2')

    # Private key of the sender address (account 9)
    sender_private_key = "0xc05e835b0dace5ff99a46432faf5561a58755edda8d53259051dc6bfa24f5c35"
    
    # Get the sender address from the private key
    sender_account = web3.eth.account.from_key(sender_private_key)
    sender_address = sender_account.address

    # Calculate the balance of the sender address
    balance = web3.eth.get_balance(sender_address)
    print(f'Sender balance: {web3.from_wei(balance, "ether")} ETH')
    
    # Ensure there's a balance to transfer
    if balance == 0:
        print('No ETH to transfer.')
        return

    # Calculate the gas price and gas limit
    gas_price = web3.eth.gas_price
    gas_limit = 21000  # Basic transaction cost

    # Calculate the amount to send (subtracting gas cost)
    amount_to_send = 500000000000000000000
    
    # Create and sign the transaction
    tx = {
        'from': sender_address,
        'to': test2.address,
        'value': amount_to_send,
        'gas': gas_limit,
        'gasPrice': gas_price,
        'nonce': web3.eth.get_transaction_count(sender_address),
    }

    signed_tx = web3.eth.account.sign_transaction(tx, sender_private_key)
    
    # Send the transaction
    tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

    print(f'Transaction successful with hash: {tx_hash.hex()}')
    print(f'New balance of test2: {web3.from_wei(web3.eth.get_balance(test2.address), "ether")} ETH')

if __name__ == "__main__":
    main()
