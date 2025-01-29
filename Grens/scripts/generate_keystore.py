# scripts/generate_keystore.py

from eth_account import Account
import json

def main():
    # Replace this with your actual private key
    private_key = ""

    # Set a strong password for encryption
    password = input("Enter a strong password for the keystore file: ")

    # Encrypt the private key
    encrypted = Account.encrypt(private_key, password)

    # Define the filename
    filename = 'test2.json'  # You can change this as needed

    # Save the encrypted keystore to a JSON file
    with open(filename, 'w') as f:
        json.dump(encrypted, f)

    print(f"\nKeystore JSON saved as '{filename}'.")
    print(f"Address: {Account.from_key(private_key).address}")
    print("**Important:** Keep your private key and password secure. Do not share them.")

if __name__ == "__main__":
    main()
