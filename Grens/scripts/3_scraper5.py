import socket
import a2s
import re
import json
from eth_account import Account  # Requires: pip install eth-account
from mcstatus import JavaServer

# Function to load servers from servers.txt
def load_servers_from_file(filename):
    servers = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                # Split each line based on commas
                parts = line.strip().split(',')
                if len(parts) == 4:
                    game_code = parts[0]  # Game code (e.g., "CS")
                    country_code = parts[1]  # Country code (e.g., "IN")
                    title = parts[2]  # Server title (e.g., "SportsKeeda Mix Clan woowoo")
                    ip_port = parts[3]  # IP and port combined (e.g., "43.205.69.43:27215")

                    # Split IP and port
                    ip, port = ip_port.replace('::', ':').split(':')
                    port = int(port)

                    # Append to the list
                    servers.append((ip, port, title, game_code, country_code))
    except FileNotFoundError:
        print(f"File {filename} not found.")
    return servers

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

# Player extraction functions based on game type
def clean_brackets_and_contents(name):
    """Remove color codes (^#), brackets and their contents, and sanitize the name to allow only alphanumeric, _, and -."""
    # Step 1: Remove color codes like ^1, ^2, etc.
    name = re.sub(r'\^\d', '', name)

    # Step 2: Remove contents inside any type of bracket pairs ([], {}, (), <>)
    name = re.sub(r'\[.*?\]', '', name)  # Remove content inside []
    name = re.sub(r'\{.*?\}', '', name)  # Remove content inside {}
    name = re.sub(r'\(.*?\)', '', name)  # Remove content inside ()
    name = re.sub(r'<.*?>', '', name)    # Remove content inside <>

    # Step 3: Remove any remaining hanging brackets
    name = re.sub(r'[\[\]\{\}\(\)<>]', '', name)

    # Step 4: Remove any non-alphanumeric characters except underscores and hyphens
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name)

    # Step 5: Remove leading/trailing spaces
    return name.strip()

def extract_player_names_from_response(response, game):
    """Extract player names from the raw server response, ignoring models."""
    if not response:
        return []

    decoded_response = response.decode('utf-8', errors='ignore')

    # QuakeWorld player extraction
    if game == "QW":
        # Match player names: we only want the first quoted string after the numbers (ignoring the second quoted string)
        player_regex = re.compile(r'\d+\s+\d+\s+\d+\s+\d+\s+"([^"]+)"')  # Capture the first quoted name
        player_names = player_regex.findall(decoded_response)
        # Clean player names by removing bracket spam and non-alphanumeric characters
        cleaned_player_names = [clean_brackets_and_contents(name) for name in player_names]
        return cleaned_player_names

    # Quake 2 player extraction
    elif game == "Q2":
        # Same logic as QuakeWorld since the format is similar
        player_regex = re.compile(r'\d+\s+\d+\s+"([^"]+)"')  # Capture the first quoted name
        player_names = player_regex.findall(decoded_response)
        # Clean player names by removing bracket spam and non-alphanumeric characters
        cleaned_player_names = [clean_brackets_and_contents(name) for name in player_names]
        return cleaned_player_names

    # Quake 3 and Quake Live (QL) player extraction (names may have color codes)
    elif game in ["Q3", "QL"]:
        # Match player names in quotes, and clean them up
        player_regex = re.compile(r'"\^?[0-9A-Za-z\^]*[^\"]+"')  # Match player names in quotes
        player_names = player_regex.findall(decoded_response)
        # Clean up the player names (remove color codes like ^1, ^7, etc., and sanitize)
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

def get_player_list_a2s(ip, port):
    """Query a server using A2S and return the player list."""
    try:
        address = (ip, port)
        players = a2s.players(address)
        return players
    except Exception as e:
        print(f"Failed to query server at {ip}:{port}: {e}")
        return []

# Generate a new Ethereum account (private key and address)
def generate_account():
    acct = Account.create()  # Generate private key and address
    return acct._private_key.hex(), acct.address  # Return as hex

def decode_and_collect_players(players, ip, port, title, game):
    """Collect players into an array and create JSON data."""
    player_data = {}
    
    if players:
        for player in players:
            sanitized_name = clean_brackets_and_contents(player.name)
            if sanitized_name:  # If the name is not empty after sanitization
                private_key, address = generate_account()
                player_data[sanitized_name] = {
                    "private_key": private_key,
                    "address": address
                }
    return player_data

def save_as_json(data, filename='player_wallets.json'):
    """Save the collected player data as JSON."""
    with open(filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)

def decode_and_print_raw(response, ip, port, title, game):
    """Decode the raw response from servers and print player names (for raw-response games like QuakeWorld, Quake 2)."""
    if response:
        player_names = extract_player_names_from_response(response, game)
        if player_names:
            print(f"Players on {ip}:{port} - {title}:")
            for name in player_names:
                print(f"{name}")
        else:
            print(f"No players found on {ip}:{port} - {title}")
    else:
        print(f"No response from {ip}:{port} - {title}")

def main():
    # Load servers from file instead of hardcoding
    servers = load_servers_from_file('sanitized_servers.txt')
    all_player_data = {}  # To collect all players across servers

    for ip, port, title, game, country_code in servers:
        print(f"Querying server: {game} {country_code} {title} at {ip}:{port}")
        
        if game == "QW":
            response = get_player_list_quakeworld(ip, port)
            decode_and_print_raw(response, ip, port, title, game)
        elif game == "Q2":
            response = get_player_list_quake2(ip, port)
            decode_and_print_raw(response, ip, port, title, game)
        elif game == "Q3":
            response = get_player_list_quake3(ip, port)
            decode_and_print_raw(response, ip, port, title, game)
        elif game in ["QL", "TFC", "CS", "HL", "L4D", "Rust"]:
            players = get_player_list_a2s(ip, port)  # Get players from A2S
            player_data = decode_and_collect_players(players, ip, port, title, game)
            all_player_data.update(player_data)  # Add to global player data
        else:
            print(f"Unsupported game type: {game}")
    
    # Save all collected players to a JSON file
    save_as_json(all_player_data)

if __name__ == "__main__":
    main()
