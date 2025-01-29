from brownie import accounts, web3, TFCWageDapp, WageMint
from pathlib import Path
import socket
import time
import a2s
import re
import os
from brownie.network.gas.strategies import LinearScalingStrategy
from brownie.network import gas_price
gas_strategy = LinearScalingStrategy("120 gwei", "1200 gwei", 1.1)

gas_price(gas_strategy)
web3.provider.timeout = 1200

# Function to load servers from servers.txt
def load_servers_from_file(filename):
    servers = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 4:
                    game_code = parts[0]
                    country_code = parts[1]
                    title = parts[2]
                    ip_port = parts[3]
                    ip, port = ip_port.replace('::', ':').split(':')
                    port = int(port)
                    servers.append((ip, port, title, game_code, country_code))
    except FileNotFoundError:
        print(f"File {filename} not found.")
    return servers

# Clean brackets and other unwanted characters from player names
def clean_brackets_and_contents(name):
    name = re.sub(r'\^\d', '', name)
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\{.*?\}', '', name)
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'<.*?>', '', name)
    name = re.sub(r'[\[\]\{\}\(\)<>]', '', name)
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    return name.strip()

# Extract player names based on game type
def extract_player_names_from_response(response, game):
    if not response:
        return []
    decoded_response = response.decode('utf-8', errors='ignore')
    if game == "QW":
        player_regex = re.compile(r'\d+\s+\d+\s+\d+\s+\d+\s+"([^"]+)"')
        player_names = player_regex.findall(decoded_response)
        cleaned_player_names = [clean_brackets_and_contents(name) for name in player_names]
        return cleaned_player_names
    elif game == "Q2":
        player_regex = re.compile(r'\d+\s+\d+\s+"([^"]+)"')
        player_names = player_regex.findall(decoded_response)
        cleaned_player_names = [clean_brackets_and_contents(name) for name in player_names]
        return cleaned_player_names
    elif game in ["Q3", "QL"]:
        player_regex = re.compile(r'"\^?[0-9A-Za-z\^]*[^\"]+"')
        player_names = player_regex.findall(decoded_response)
        cleaned_player_names = [clean_brackets_and_contents(name.strip('"')) for name in player_names]
        return cleaned_player_names
    return []

def get_player_list_quakeworld(ip, port):
    """Query a Quakeworld server to get the player list."""
    player_request = b'\xFF\xFF\xFF\xFFstatus\x00'
    response = send_udp_request(ip, port, player_request)
    return response

def get_player_list_quake2(ip, port):
    """Query a Quake 2 server to get the player list."""
    player_request = b'\xFF\xFF\xFF\xFFstatus\x00'
    response = send_udp_request(ip, port, player_request)
    return response

def get_player_list_quake3(ip, port):
    """Query a Quake 3 or Quake Live server to get the player list."""
    player_request = b'\xFF\xFF\xFF\xFFgetstatus\x00'
    response = send_udp_request(ip, port, player_request)
    return response

# Query players using A2S protocol
def get_player_list_a2s(ip, port):
    try:
        address = (ip, port)
        players = a2s.players(address)
        time.sleep(1)
        return players
    except Exception as e:
        print(f"Failed to query server at {ip}:{port}: {e}")
        return []

# Function to decode and collect player data
def decode_and_collect_players(players, ip, port, title, game, serverPlayersLists, known_players):
    if players:
        player_names = [clean_brackets_and_contents(player.name) for player in players]
        if len(player_names) > 0:
            registered_players = find_known_players(player_names, known_players)
            print(f"Found {len(player_names)} players on server at {ip}:{port}; reg'd ones: {', '.join(registered_players) if registered_players else 'None'}")
        else:
            print(f"No players found on server {title} at {ip}:{port}")
        serverPlayersLists.append({
            "serverIP": f"{ip}:{port}",
            "playerNames": player_names
        })

def decode_and_print_raw(response, ip, port, title, game, serverPlayersLists, known_players):
    """Decode the raw response from servers and print player names."""
    if response:
        player_names = extract_player_names_from_response(response, game)
        if player_names:
            registered_players = find_known_players(player_names, known_players)
            print(f"Found {len(player_names)} players on server at {ip}:{port}; reg'd ones: {', '.join(registered_players) if registered_players else 'None'}")
            serverPlayersLists.append({
                "serverIP": f"{ip}:{port}",
                "playerNames": player_names
            })
        else:
            print(f"No players found on server {ip}:{port} - {title}")
    else:
        print(f"No response from {ip}:{port} - {title}")

# Query real-time players from the servers
def query_real_players(known_players):
    serverPlayersLists = []
    servers = load_servers_from_file('sanitized_servers.txt')

    for ip, port, title, game, country_code in servers:
        print(f"Querying server: {game}, {country_code}, {title} at {ip}:{port}")
        if game in ["QL", "TFC", "CS", "HL", "L4D", "Rust"]:
            players = get_player_list_a2s(ip, port)
            decode_and_collect_players(players, ip, port, title, game, serverPlayersLists, known_players)
        elif game == "QW":
            response = get_player_list_quakeworld(ip, port)
            decode_and_print_raw(response, ip, port, title, game, serverPlayersLists, known_players)
        elif game == "Q2":
            response = get_player_list_quake2(ip, port)
            decode_and_print_raw(response, ip, port, title, game, serverPlayersLists, known_players)
        elif game == "Q3":
            response = get_player_list_quake3(ip, port)
            decode_and_print_raw(response, ip, port, title, game, serverPlayersLists, known_players)

    return serverPlayersLists

def send_udp_request(ip, port, message, timeout=5):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.sendto(message, (ip, port))
            response, _ = sock.recvfrom(4096)
            return response
        except socket.timeout:
            print(f"Request to {ip}:{port} timed out")
            return None

# Compare real-time players to registered players
def find_known_players(players, known_players):
    return [player for player in players if player in known_players]

# Chunk player list into smaller groups for transactions
def chunk_players(player_list, chunk_size=32):
    for i in range(0, len(player_list), chunk_size):
        yield player_list[i:i + chunk_size]

def write_known_players_to_file(file_path, serverPlayersLists):
    with open(file_path, 'w') as file:
        for server in serverPlayersLists:
            ip_port = server["serverIP"]
            players = server["playerNames"]
            if len(players) > 0:
                file.write(f"Server {ip_port}:\n")
                for player in players:
                    file.write(f"{player}\n")
                file.write("\n")

def main():
    validator_account = accounts.load('test2')

    # Load the contract addresses
    with open('Mint-address.txt', 'r') as file:
        mint_address = file.read().strip()
    mint_contract = WageMint.at(mint_address)

    with open('Dapp-address.txt', 'r') as file:
        wage_dapp_address = file.read().strip()

    # Initialize contract instances

    wage_dapp = TFCWageDapp.at(wage_dapp_address)

    # gas_price = web3.to_wei('39', 'gwei')
    # gas_limit = 10000000

    player_file_path = 'live_known_players.txt'
    known_players = wage_dapp.getAllPlayerNames()

    while True:
        # Fetch balances
        eth_balance = web3.from_wei(web3.eth.get_balance(validator_account.address), 'ether')
        token_balance = web3.from_wei(mint_contract.balanceOf(validator_account.address), 'ether')
        print(f"Balance of {validator_account.address}: {eth_balance} ETH, {token_balance} ACoins")

        # Query real players from the servers
        serverPlayersLists = query_real_players(known_players)
        write_known_players_to_file(player_file_path, serverPlayersLists)

        # Process each server and mint tokens
        for server in serverPlayersLists:
            players = server["playerNames"]
            filtered_players = find_known_players(players, known_players)

            chunks = list(chunk_players(filtered_players, 32))

            for chunk in chunks:
                try:
                    current_nonce = web3.eth.get_transaction_count(validator_account.address)
                    print(f"Mass minting for chunk: {chunk}")

                    # Send the transaction
                    tx = wage_dapp.mintForPlayersBatch(
                        chunk,  # Pass player names
                        {'from': validator_account,   'nonce': current_nonce}
                    )

                    # Event capturing: DebugLog, PlayerEligibleForMint, PlayerMinted
                    if 'DebugLog' in tx.events:
                        for log in tx.events['DebugLog']:
                            print(f"Debug Log - Player: {log['playerName']}, Message: {log['message']}, TokensToMint: {log['tokensToMint']}")

                    if 'PlayerEligibleForMint' in tx.events:
                        for log in tx.events['PlayerEligibleForMint']:
                            print(f"Player {log['playerName']} is eligible for {log['tokensToMint']} tokens. Elapsed time: {log['elapsedTime']}")

                    if 'PlayerMinted' in tx.events:
                        for log in tx.events['PlayerMinted']:
                            tokens_minted_raw = log['finalTokenAmounts']
                            tokens_minted = tokens_minted_raw / 1e18  # Adjust for 18 decimal places
                            print(f"Player {log['finalPlayerNames']} minted {tokens_minted} tokens.")

                    # Wait for transaction confirmation and log
                    tx.wait(1)
                    time.sleep(1)
                    print(f"Mass minted for players. Transaction hash: {tx.txid}")

                except Exception as e:
                    print(f"Transaction failed: {str(e)}")
                    continue

        # Wait before the next iteration
        time.sleep(305)

        # Update and print account balances
        eth_balance = web3.from_wei(web3.eth.get_balance(validator_account.address), 'ether')
        token_balance = web3.from_wei(mint_contract.balanceOf(validator_account.address), 'ether')
        print(f"Balance of {validator_account.address}: {eth_balance} ETH, {token_balance} ACoins")

if __name__ == "__main__":
    main()
