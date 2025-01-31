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

# --------------------------------------------------------------------------
#                             HELPER FUNCTIONS
# --------------------------------------------------------------------------

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

def clean_brackets_and_contents(name):
    name = re.sub(r'\^\d', '', name)          # remove Quake color codes
    name = re.sub(r'\[.*?\]', '', name)       # remove [stuff]
    name = re.sub(r'\{.*?\}', '', name)       # remove {stuff}
    name = re.sub(r'\(.*?\)', '', name)       # remove (stuff)
    name = re.sub(r'<.*?>', '', name)         # remove <stuff>
    name = re.sub(r'[\[\]\{\}\(\)<>]', '', name)
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    return name.strip()

def extract_player_names_from_response(response, game):
    if not response:
        return []
    decoded_response = response.decode('utf-8', errors='ignore')

    if game == "QW":
        # quakeworld pattern: "frags ping color shirt "playerName"
        player_regex = re.compile(r'\d+\s+\d+\s+\d+\s+\d+\s+"([^"]+)"')
        player_names = player_regex.findall(decoded_response)
        return [clean_brackets_and_contents(name) for name in player_names]

    elif game == "Q2":
        # quake2 pattern: "frags ping "playerName"
        player_regex = re.compile(r'\d+\s+\d+\s+"([^"]+)"')
        player_names = player_regex.findall(decoded_response)
        return [clean_brackets_and_contents(name) for name in player_names]

    elif game in ["Q3", "QL"]:
        player_regex = re.compile(r'"\^?[0-9A-Za-z\^]*[^\"]+"')
        player_names = player_regex.findall(decoded_response)
        return [clean_brackets_and_contents(name.strip('"')) for name in player_names]

    return []

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

def get_player_list_quakeworld(ip, port):
    player_request = b'\xFF\xFF\xFF\xFFstatus\x00'
    return send_udp_request(ip, port, player_request)

def get_player_list_quake2(ip, port):
    player_request = b'\xFF\xFF\xFF\xFFstatus\x00'
    return send_udp_request(ip, port, player_request)

def get_player_list_quake3(ip, port):
    player_request = b'\xFF\xFF\xFF\xFFgetstatus\x00'
    return send_udp_request(ip, port, player_request)

def get_player_list_a2s(ip, port):
    try:
        address = (ip, port)
        players = a2s.players(address)
        time.sleep(1)
        return players
    except Exception as e:
        print(f"Failed to query server at {ip}:{port}: {e}")
        return []

def decode_and_collect_a2s_players(players, ip, port, title, game):
    if not players:
        print(f"No players found on server {title} at {ip}:{port}")
        return []
    player_names = [clean_brackets_and_contents(p.name) for p in players]
    if player_names:
        print(f"Found {len(player_names)} players on {title} ({ip}:{port}): {player_names}")
    return player_names

def decode_and_collect_raw(response, ip, port, title, game):
    if not response:
        print(f"No response from {ip}:{port} - {title}")
        return []
    player_names = extract_player_names_from_response(response, game)
    if player_names:
        print(f"Found {len(player_names)} players on {title} ({ip}:{port}): {player_names}")
    else:
        print(f"No players found on server {title} at {ip}:{port}")
    return player_names

def chunk_players(player_list, chunk_size=32):
    for i in range(0, len(player_list), chunk_size):
        yield player_list[i:i+chunk_size]

# --------------------------------------------------------------------------
#                         ACCUMULATED PLAYERS LOGIC
# --------------------------------------------------------------------------

def load_accumulated_players(file_path):
    if not os.path.exists(file_path):
        return set()
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    return set(lines)

def save_accumulated_players(file_path, players_set):
    with open(file_path, 'w', encoding='utf-8') as f:
        for p in sorted(players_set):
            f.write(p + "\n")

# --------------------------------------------------------------------------
#                                MAIN LOGIC
# --------------------------------------------------------------------------

def main():
    # Load your validator account
    validator_account = accounts.load('test2')

    # Load your contract addresses
    with open('Mint-address.txt', 'r') as file:
        mint_address = file.read().strip()
    mint_contract = WageMint.at(mint_address)

    with open('Dapp-address.txt', 'r') as file:
        wage_dapp_address = file.read().strip()
    wage_dapp = TFCWageDapp.at(wage_dapp_address)

    # This file will store the persistent set of all players seen
    accumulated_file_path = 'accumulated_players.txt'
    accumulated_players = load_accumulated_players(accumulated_file_path)

    # Brownie contract call: all known (registered) players in the dApp
    known_players = set(wage_dapp.getAllPlayerNames())

    print("=== Starting the player scanner/minter loop ===")
    print(f"Loaded {len(accumulated_players)} previously-seen players from {accumulated_file_path}")
    print(f"Contract has {len(known_players)} known/registered player names.")

    # We'll keep a counter for which scan iteration we're on:
    scan_iteration = 0

    while True:
        scan_iteration += 1  # Increment each loop

        # ------------------------------------------------------------------
        # 1) Print Current Balances
        # ------------------------------------------------------------------
        eth_balance = web3.from_wei(web3.eth.get_balance(validator_account.address), 'ether')
        token_balance = web3.from_wei(mint_contract.balanceOf(validator_account.address), 'ether')
        print(f"\n[INFO] Scan #{scan_iteration}")
        print(f"[INFO] Validator Balance: {eth_balance} ETH, {token_balance} ACoins")

        # ------------------------------------------------------------------
        # 2) Query All Servers
        # ------------------------------------------------------------------
        servers = load_servers_from_file('sanitized_servers.txt')
        newly_scanned_players = set()

        for ip, port, title, game, country_code in servers:
            print(f"Querying server: {game}, {country_code}, {title} at {ip}:{port}")
            try:
                if game in ["QL", "TFC", "CS", "HL", "L4D", "Rust"]:
                    players = get_player_list_a2s(ip, port)
                    found_names = decode_and_collect_a2s_players(players, ip, port, title, game)
                elif game == "QW":
                    response = get_player_list_quakeworld(ip, port)
                    found_names = decode_and_collect_raw(response, ip, port, title, game)
                elif game == "Q2":
                    response = get_player_list_quake2(ip, port)
                    found_names = decode_and_collect_raw(response, ip, port, title, game)
                elif game == "Q3":
                    response = get_player_list_quake3(ip, port)
                    found_names = decode_and_collect_raw(response, ip, port, title, game)
                else:
                    found_names = []

                newly_scanned_players.update(found_names)

            except Exception as err:
                print(f"Error while querying {title} at {ip}:{port}: {err}")

        # ------------------------------------------------------------------
        # 3) Update our accumulated set of all-time players
        # ------------------------------------------------------------------
        old_count = len(accumulated_players)
        accumulated_players.update(newly_scanned_players)
        new_count = len(accumulated_players)

        if new_count > old_count:
            print(f"[INFO] Found {new_count - old_count} new unique players this round.")
            save_accumulated_players(accumulated_file_path, accumulated_players)
        else:
            print("[INFO] No new unique players discovered in this scan.")

        # ------------------------------------------------------------------
        # 4) Decide whether to Mint or Skip
        # ------------------------------------------------------------------
        # We only mint on scan #1, 5, 9, 13, ... i.e. (scan_iteration % 4 == 1)
        if (scan_iteration % 4) == 1:
            # Filter out players who are actually known/registered
            to_mint = list(accumulated_players.intersection(known_players))
            if not to_mint:
                print("[INFO] No overlapping players to mint for. Skipping mint process.")
            else:
                print(f"[INFO] Attempting to mint for {len(to_mint)} known players...")

                chunks = list(chunk_players(to_mint, 32))
                for chunk in chunks:
                    print(f"Minting chunk: {chunk}")
                    try:
                        tx = wage_dapp.mintForPlayersBatch(
                            chunk,
                            {'from': validator_account, 'required_confs': 1}
                        )
                        # Check for event logs
                        if 'PlayerMinted' in tx.events:
                            for event_data in tx.events['PlayerMinted']:
                                gating_address = event_data['gatingAddress']
                                amount_to_player = event_data['amountToPlayer'] / 1e18
                                amount_to_validator = event_data['amountToValidator'] / 1e18

                                print(
                                    f"PlayerMinted - gatingAddress: {gating_address}, "
                                    f"playerCut: {amount_to_player}, validatorCut: {amount_to_validator}"
                                )

                        tx.wait(1)
                        print(f"[INFO] Mint Tx completed. Hash: {tx.txid}")
                        time.sleep(2)

                    except Exception as e:
                        print(f"[ERROR] Transaction failed: {str(e)}")
                        continue
        else:
            print(f"[INFO] Skipping mint on scan #{scan_iteration}. Only tracking players.")

        # ------------------------------------------------------------------
        # 5) Sleep 5 minutes, then repeat
        # ------------------------------------------------------------------
        print("[INFO] Sleeping for 5 minutes before next scan...\n")
        time.sleep(300)


if __name__ == "__main__":
    main()
