import tkinter as tk
from tkinter import ttk, messagebox
import threading
from concurrent.futures import ThreadPoolExecutor
from web3 import Web3
import a2s
import socket
import time
import re
import json
import webbrowser

# Function to load servers from servers.txt
def load_servers_from_file(filename):
    servers = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                # Split each line based on commas
                parts = line.strip().split(',')
                if len(parts) >= 4:
                    game_code = parts[0].strip().upper()      # Game code (e.g., "CS", "QW")
                    country_code = parts[1].strip().upper()   # Country code (e.g., "IN")
                    title = parts[2].strip()                   # Server title
                    ip_port = parts[3].strip()                 # IP and port combined (e.g., "43.205.69.43:27215")
                    # Handle cases where IP might contain multiple colons (e.g., IPv6)
                    if ip_port.count(':') > 1 and not ip_port.startswith('['):
                        ip_port = f'[{ip_port}]'  # Enclose IPv6 addresses in brackets

                    # Split IP and port
                    if ':' in ip_port:
                        if ip_port.startswith('['):
                            # IPv6 address
                            ip_address, port = ip_port.rsplit(':', 1)
                            ip_address = ip_address.strip('[]')
                        else:
                            ip_address, port = ip_port.split(':')
                        try:
                            port = int(port)
                        except ValueError:
                            port = 27015  # Default port if invalid
                    else:
                        ip_address = ip_port
                        port = 27015  # Default port if not specified

                    # Append to the list
                    servers.append((ip_address, port, title, game_code, country_code))
    except FileNotFoundError:
        print(f"File {filename} not found.")
    return servers

def send_udp_request(ip, port, message, timeout=5):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            start_time = time.time()  # Start timing
            sock.sendto(message, (ip, port))
            response, _ = sock.recvfrom(4096)
            end_time = time.time()    # End timing
            rtt = (end_time - start_time) * 1000  # RTT in milliseconds
            return response, round(rtt, 2)
        except socket.timeout:
            # Handle timeout silently or log if needed
            return None, None
        except Exception:
            return None, None

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
    """Query a QuakeWorld server to get the player list and ping."""
    player_request = b'\xFF\xFF\xFF\xFFstatus\x00'
    response, rtt = send_udp_request(ip, port, player_request)
    return response, rtt

def get_player_list_quake2(ip, port):
    """Query a Quake II server to get the player list and ping."""
    player_request = b'\xFF\xFF\xFF\xFFstatus\x00'
    response, rtt = send_udp_request(ip, port, player_request)
    return response, rtt

def get_player_list_quake3(ip, port):
    """Query a Quake III or Quake Live server to get the player list and ping."""
    player_request = b'\xFF\xFF\xFF\xFFgetstatus\x00'
    response, rtt = send_udp_request(ip, port, player_request)
    return response, rtt

def get_player_list_a2s(ip, port):
    """Query a server using A2S and return the player list and ping."""
    try:
        address = (ip, port)
        start_time = time.time()
        players = a2s.players(address, timeout=5)
        end_time = time.time()
        rtt = (end_time - start_time) * 1000  # RTT in milliseconds
        return players, round(rtt, 2)
    except Exception:
        return [], None

def decode_and_collect_players(players, rtt, ip, port, title, game, player_list_dict):
    """Collect players into an array and associate with ping."""
    server_id = f"{ip}:{port}"
    if server_id not in player_list_dict:
        player_list_dict[server_id] = []

    if players:
        for player in players:
            sanitized_name = clean_brackets_and_contents(player.name)
            if sanitized_name:  # If the name is not empty after sanitization
                player_info = {
                    "player_name": sanitized_name,
                }
                player_list_dict[server_id].append(player_info)
    return

def decode_and_print_raw(response, rtt, ip, port, title, game):
    """Decode the raw response from servers and extract player names along with ping."""
    if response:
        player_names = extract_player_names_from_response(response, game)
        if player_names:
            return player_names, rtt
    return [], 'N/A'

def players_count(players, max_players=32):
    if players:
        return f"{len(players)}"  # Only player count, no "/max"
    else:
        return "0"

class ServerListerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Server Lister")
        self.server_list = []
        self.all_servers = []  # Master list of all servers
        self.player_list = {}  # Dictionary to store players per server
        self.lock = threading.Lock()  # To prevent multiple probes
        self.sort_keys = []  # List of tuples: (column, ascending)

        # Create a main frame
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Servers Frame
        self.servers_frame = ttk.Frame(self.main_frame)
        self.servers_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Players Sidebar
        self.players_frame = ttk.Frame(self.main_frame, width=300)
        self.players_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Define columns for Servers
        self.server_columns = ('game', 'country', 'server_name', 'ip', 'port', 'ping', 'map', 'players', 'default_max')
        self.server_tree = ttk.Treeview(self.servers_frame, columns=self.server_columns, show='headings', selectmode='browse')
        for col in self.server_columns:
            self.server_tree.heading(col, text=col.replace('_', ' ').capitalize(), command=lambda _col=col: self.sort_column(_col))
            self.server_tree.column(col, width=120, anchor='center')
        self.server_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.server_tree.bind('<Double-1>', self.on_double_click_server)
        self.server_tree.bind('<<TreeviewSelect>>', self.on_select_server)

        # Players Sidebar (Removed the "Players" label)
        # Define columns for Players
        player_columns = ('player_name',)
        self.player_tree = ttk.Treeview(self.players_frame, columns=player_columns, show='headings', selectmode='browse')
        for col in player_columns:
            self.player_tree.heading(col, text=col.replace('_', ' ').capitalize())
            self.player_tree.column(col, width=280, anchor='center')
        self.player_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Removed the double-click binding for players
        # self.player_tree.bind('<Double-1>', self.on_double_click_player)

        # Bottom Frame for Filter, Copy, and Refresh
        self.bottom_frame = ttk.Frame(self.servers_frame)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        # Filter by Game Frame
        self.filter_frame = ttk.Frame(self.bottom_frame)
        self.filter_frame.pack(side=tk.LEFT, fill=tk.NONE, padx=(0, 10))  # Added padding to center buttons

        self.filter_label = ttk.Label(self.filter_frame, text="Filter by game:")
        self.filter_label.pack(side=tk.LEFT, padx=(0,5))

        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(self.filter_frame, textvariable=self.filter_var, width=8)  # Set fixed width
        self.filter_entry.pack(side=tk.LEFT)
        self.filter_entry.bind('<Return>', self.apply_filter)

        self.clear_filter_button = ttk.Button(self.filter_frame, text="Clear", command=self.clear_filter)
        self.clear_filter_button.pack(side=tk.LEFT, padx=(5,0))

        # Copy Server IP Frame
        self.copy_frame = ttk.Frame(self.bottom_frame)
        self.copy_frame.pack(side=tk.LEFT, fill=tk.NONE, padx=(0, 10))

        self.copy_label = ttk.Label(self.copy_frame, text="Server IP:")
        self.copy_label.pack(side=tk.LEFT, padx=(0,5))

        self.copy_var = tk.StringVar()
        self.copy_entry = ttk.Entry(self.copy_frame, textvariable=self.copy_var, width=20, state='readonly')
        self.copy_entry.pack(side=tk.LEFT)

        self.copy_button = ttk.Button(self.copy_frame, text="Copy", command=self.copy_ip_to_clipboard)
        self.copy_button.pack(side=tk.LEFT, padx=(5,0))

        self.connect_var = tk.BooleanVar()
        self.connect_checkbox = ttk.Checkbutton(self.copy_frame, text="Connect", variable=self.connect_var, command=self.update_copy_entry)
        self.connect_checkbox.pack(side=tk.LEFT, padx=(5,0))

        # Refresh Button
        self.refresh_button = ttk.Button(self.bottom_frame, text="Refresh", command=self.refresh_servers)
        self.refresh_button.pack(side=tk.RIGHT)

        # Find a Friend Frame (Below Player List)
        self.find_friend_frame = ttk.Frame(self.players_frame)
        self.find_friend_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(10,0))

        self.find_friend_label = ttk.Label(self.find_friend_frame, text="Find a friend:")
        self.find_friend_label.pack(side=tk.LEFT, padx=(0,5))

        self.find_friend_var = tk.StringVar()
        self.find_friend_entry = ttk.Entry(self.find_friend_frame, textvariable=self.find_friend_var, width=15)
        self.find_friend_entry.pack(side=tk.LEFT, padx=(0,5))

        self.find_friend_button = ttk.Button(self.find_friend_frame, text="Find", command=self.find_friend)
        self.find_friend_button.pack(side=tk.LEFT)

        # Initialize ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=20)  # Adjust max_workers as needed

        # Load servers and start probing
        self.refresh_servers()

    def get_contract_address(self):
        try:
            with open('Activity-PlayerDatabase.txt', 'r') as f:
                contract_address = f.read().strip()
            return contract_address
        except FileNotFoundError:
            return None

    def get_server_data(self):
        # Connect to the Ganache local blockchain
        w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))

        # Read the contract address from the file
        contract_address = self.get_contract_address()
        if not contract_address:
            return [], []

        try:
            contract_address = Web3.to_checksum_address(contract_address)
        except ValueError:
            print("Invalid contract address format.")
            return [], []

        # Define the ABI with the getServerIPListWithFlavorText function
        contract_abi = [
            {
                "inputs": [],
                "name": "getServerIPListWithFlavorText",
                "outputs": [
                    {
                        "internalType": "string[]",
                        "name": "ips",
                        "type": "string[]"
                    },
                    {
                        "internalType": "string[]",
                        "name": "flavorTexts",
                        "type": "string[]"
                    }
                ],
                "stateMutability": "view",
                "type": "function"
            }
            # Include other ABI entries if needed
        ]

        # Create a contract instance
        try:
            contract = w3.eth.contract(address=contract_address, abi=contract_abi)
        except Exception as e:
            print(f"Error creating contract instance: {e}")
            return [], []

        # Call the function to get server data
        try:
            server_data = contract.functions.getServerIPListWithFlavorText().call()
            ips, flavor_texts = server_data
            return ips, flavor_texts
        except Exception as e:
            print(f"Error fetching server data: {e}")
            return [], []

    def parse_flavor_texts(self, ips, flavor_texts):
        server_list = []
        for ip_port, flavor_text in zip(ips, flavor_texts):
            # Extract IP and port from the ips array
            if ':' in ip_port:
                if ip_port.startswith('['):
                    # IPv6 address
                    ip_address, port = ip_port.rsplit(':', 1)
                    ip_address = ip_address.strip('[]')
                else:
                    ip_address, port = ip_port.split(':')
                try:
                    port = int(port)
                except ValueError:
                    port = 27015  # Default port if invalid
            else:
                ip_address = ip_port
                port = 27015  # Default port if not specified

            # Extract game, country, and server name from flavor text
            flavor_text = flavor_text.strip()
            # Split by commas and remove empty strings
            parts = [part.strip() for part in flavor_text.split(',') if part.strip()]
            if len(parts) >= 3:
                game = parts[0]
                country = parts[1]
                server_name = ', '.join(parts[2:])
            elif len(parts) == 2:
                game = parts[0]
                country = parts[1]
                server_name = ''
            elif len(parts) == 1:
                game = parts[0]
                country = ''
                server_name = ''
            else:
                continue  # Skip if unable to parse

            # Assign default max_players based on game
            default_max_players = {
                'CS': 32,
                'CSGO': 32,
                'TEAM FORTRESS': 32,
                'RUST': 100,
                'QL': 16,
                'Q3': 16,
                'QW': 32,
                'Q2': 32,
                'TFC': 32,
                'HL': 32,
                'L4D': 32,
                # Add other games as needed
            }
            max_players = default_max_players.get(game.upper(), 32)  # Default to 32 if game not found

            server_info = {
                'game': game,
                'country': country,
                'server_name': server_name,
                'ip': ip_address,
                'port': port,
                'ping': 'N/A',
                'map': '',
                'players': '',
                'default_max': max_players,
                'tree_item_id': None  # Will store the Treeview item ID
            }
            server_list.append(server_info)
        return server_list

    def probe_servers(self, server_list):
        with self.lock:
            for server in server_list:
                self.executor.submit(self.probe_server, server)

    def probe_server(self, server):
        game = server['game'].upper()
        ip = server['ip']
        port = server['port']

        if game in ["QL", "TFC", "CS", "HL", "L4D", "RUST"]:
            players, rtt = get_player_list_a2s(ip, port)
            decode_and_collect_players(players, rtt, ip, port, server['server_name'], game, self.player_list)
            server['players'] = players_count(players, server['default_max'])
            server['ping'] = rtt if rtt is not None else 'N/A'
            # Optionally, retrieve map name via a2s.info
            try:
                info = a2s.info((ip, port), timeout=5)
                server['map'] = info.map_name
                server['server_name'] = info.server_name
            except Exception:
                server['map'] = 'Unknown'
                # server['server_name'] remains unchanged
        elif game in ["QW", "Q2", "Q3"]:
            if game == "QW":
                response, rtt = get_player_list_quakeworld(ip, port)
            elif game == "Q2":
                response, rtt = get_player_list_quake2(ip, port)
            elif game == "Q3":
                response, rtt = get_player_list_quake3(ip, port)
            else:
                response, rtt = None, None

            player_names, ping_info = decode_and_print_raw(response, rtt, ip, port, server['server_name'], game)
            server['players'] = players_count(player_names, server['default_max'])
            server['ping'] = ping_info if ping_info is not None else 'N/A'
            server['map'] = 'Unknown'  # Implement map extraction if possible

            # Associate players with server
            server_id = f"{ip}:{port}"
            if player_names:
                if server_id not in self.player_list:
                    self.player_list[server_id] = []
                for name in player_names:
                    player_info = {
                        "player_name": name,
                    }
                    self.player_list[server_id].append(player_info)
        else:
            server['ping'] = 'N/A'
            server['players'] = 'N/A'
            server['map'] = 'N/A'

        # Update the Treeview with the new ping and player info
        self.root.after(0, self.update_treeview_entry, server)

    def refresh_servers(self, callback=None):
        # Prevent multiple refreshes
        if self.lock.locked():
            return

        # Disable the refresh button to prevent multiple clicks
        self.refresh_button.config(state=tk.DISABLED)

        # Clear existing server list and player list
        for row in self.server_tree.get_children():
            self.server_tree.delete(row)
        for row in self.player_tree.get_children():
            self.player_tree.delete(row)
        self.player_list.clear()

        # Reset sort keys
        self.sort_keys.clear()
        self.reset_column_headers()

        # Start loading and probing servers in a separate thread
        threading.Thread(target=self.load_and_display_servers, args=(callback,)).start()

    def load_and_display_servers(self, callback=None):
        ips, flavor_texts = self.get_server_data()
        if not ips or not flavor_texts:
            # Re-enable the refresh button if no data
            self.root.after(0, lambda: self.refresh_button.config(state=tk.NORMAL))
            return

        self.all_servers = self.parse_flavor_texts(ips, flavor_texts)

        # Apply current filter
        filter_code = self.filter_var.get().strip().upper()
        if filter_code:
            self.server_list = [s for s in self.all_servers if s['game'].upper() == filter_code]
        else:
            self.server_list = self.all_servers.copy()

        # Insert servers into Treeview with initial 'N/A' for ping
        self.root.after(0, self.update_treeview_initial, self.server_list)

        # Start probing servers
        self.probe_servers(self.server_list)

        # Shutdown executor and wait for all probes to finish
        self.executor.shutdown(wait=True)

        # Re-enable the refresh button
        self.root.after(0, lambda: self.refresh_button.config(state=tk.NORMAL))

        # Execute callback if provided
        if callback:
            self.root.after(0, callback)

        # Restart the executor for future probes
        self.executor = ThreadPoolExecutor(max_workers=20)

    def update_treeview_initial(self, server_list):
        for server in server_list:
            values = (
                server.get('game', ''),
                server.get('country', ''),
                server.get('server_name', ''),
                server.get('ip', ''),
                server.get('port', ''),
                server.get('ping', 'N/A'),
                server.get('map', ''),
                server.get('players', ''),
                server.get('default_max', 'N/A')
            )
            # Insert the server into the Treeview and keep track of the item ID
            item_id = self.server_tree.insert('', tk.END, values=values)
            server['tree_item_id'] = item_id

    def update_treeview_entry(self, server):
        item_id = server.get('tree_item_id')
        if item_id:
            # Update the Treeview entry with new ping and player info
            values = (
                server.get('game', ''),
                server.get('country', ''),
                server.get('server_name', ''),
                server.get('ip', ''),
                server.get('port', ''),
                server.get('ping', 'N/A'),
                server.get('map', ''),
                server.get('players', ''),
                server.get('default_max', 'N/A')
            )
            self.server_tree.item(item_id, values=values)
            # Optionally, update the Players sidebar if the server is selected
            selected = self.server_tree.selection()
            if selected and server['tree_item_id'] in selected:
                server_id = f"{server['ip']}:{server['port']}"
                self.update_player_sidebar(server_id)
            # Update the Copy Server IP field if this server is selected
            if selected and server['tree_item_id'] in selected:
                self.update_copy_entry()

    def update_player_sidebar(self, server_id):
        """Update the Players sidebar with players from the specified server."""
        # Clear existing players
        for row in self.player_tree.get_children():
            self.player_tree.delete(row)

        # Populate with players from the selected server
        if server_id in self.player_list:
            for player in self.player_list[server_id]:
                values = (
                    player['player_name'],
                )
                self.player_tree.insert('', tk.END, values=values)
        else:
            # No players found for this server
            pass

    def on_select_server(self, event):
        selected_item = self.server_tree.selection()
        if selected_item:
            item = selected_item[0]
            server = self.server_tree.item(item, 'values')
            ip = server[3]
            port = server[4]
            server_id = f"{ip}:{port}"
            self.update_player_sidebar(server_id)
            self.update_copy_entry()

    def on_double_click_server(self, event):
        selected_item = self.server_tree.selection()
        if selected_item:
            item = selected_item[0]
            server = self.server_tree.item(item, 'values')
            ip = server[3]
            port = server[4]
            game = server[0]
            self.launch_game(game, ip, port)

    # Removed the on_double_click_player method entirely

    def launch_game(self, game, ip, port):
        # Map game identifiers to Steam App IDs
        game_app_ids = {
            'CS': '10',                 # Counter-Strike
            'CSGO': '730',              # Counter-Strike: Global Offensive
            'TEAM FORTRESS': '440',     # Team Fortress 2
            'QL': '278820',             # Quake Live (AppID may vary)
            'Q3': '366890',             # Quake III Arena
            'QW': 'unknown',            # QuakeWorld does not have a Steam AppID
            'Q2': 'unknown',            # Quake II does not have a Steam AppID
            'TFC': 'unknown',           # Team Fortress Classic
            'HL': '730',                # Half-Life (Assuming CS:GO)
            'L4D': '550',               # Left 4 Dead
            'RUST': '252490',           # Rust
            # Add other games and their App IDs here
        }

        if game in game_app_ids and game_app_ids[game] != 'unknown':
            app_id = game_app_ids[game]

            # For games that support 'connect' parameter
            steam_url = f'steam://connect/{ip}:{port}'

            # For games requiring 'run' command with parameters
            # steam_url = f'steam://run/{app_id}//+connect {ip}:{port}'

            try:
                # Open the Steam URL
                webbrowser.open(steam_url)
            except Exception:
                messagebox.showerror("Error", "Failed to launch the game.")
        else:
            # For games without a Steam AppID or not configured
            messagebox.showwarning("Unsupported", f"Launching {game} is not supported.")

    def sort_column(self, col):
        """Sort Treeview column when header is clicked, cycling through unsorted, ascending, descending."""
        # Determine current sort state for the column
        current_sort = None
        for i, (key, asc) in enumerate(self.sort_keys):
            if key == col:
                current_sort = asc
                del self.sort_keys[i]
                break

        # Cycle through sort states: unsorted -> ascending -> descending -> unsorted
        if current_sort is None:
            # Currently unsorted, set to ascending
            self.sort_keys.insert(0, (col, True))
            sort_state = '↑'
        elif current_sort:
            # Currently ascending, set to descending
            self.sort_keys.insert(0, (col, False))
            sort_state = '↓'
        else:
            # Currently descending, set to unsorted
            sort_state = ''

        # Apply sorting
        self.apply_sorting()

        # Update column headers with sort indicators
        self.update_column_headers()

    def apply_sorting(self):
        """Sort the server_list based on sort_keys."""
        def sort_key(server):
            key = []
            for col, asc in self.sort_keys:
                value = server.get(col, '')
                # Handle 'N/A' values
                if col == 'ping':
                    if value == 'N/A':
                        # Assign a value that ensures 'N/A' is always at the bottom
                        sort_value = float('inf') if asc else float('-inf')
                    else:
                        try:
                            sort_value = float(value)
                        except ValueError:
                            sort_value = float('inf') if asc else float('-inf')
                elif col in ['players', 'default_max', 'port']:
                    try:
                        sort_value = float(value)
                    except ValueError:
                        sort_value = float('-inf') if not asc else float('inf')
                else:
                    sort_value = value.lower()  # Case-insensitive sorting for strings
                # For descending order, invert the value where applicable
                if not asc:
                    if isinstance(sort_value, float):
                        sort_value = -sort_value
                    elif isinstance(sort_value, str):
                        sort_value = ''.join(chr(255 - ord(c)) for c in sort_value)
                key.append(sort_value)
            return key

        self.server_list.sort(key=sort_key)

        # Clear and re-insert sorted servers
        for row in self.server_tree.get_children():
            self.server_tree.delete(row)
        self.update_treeview_initial(self.server_list)

    def update_column_headers(self):
        """Update the column headers with sort indicators."""
        for col in self.server_columns:
            # Remove existing sort indicators
            base_text = col.replace('_', ' ').capitalize().replace('↑', '').replace('↓', '').strip()
            # Check if this column is in sort_keys
            indicator = ''
            for key, asc in self.sort_keys:
                if key == col:
                    indicator = '↑' if asc else '↓'
                    break
            # Update the header text with indicator
            self.server_tree.heading(col, text=f"{base_text} {indicator}".strip(), command=lambda _col=col: self.sort_column(_col))

    def reset_column_headers(self):
        """Reset column headers to default without sort indicators."""
        for col in self.server_columns:
            self.server_tree.heading(col, text=col.replace('_', ' ').capitalize(), command=lambda _col=col: self.sort_column(_col))

    def apply_filter(self, event=None):
        """Apply the game code filter to the server list."""
        filter_code = self.filter_var.get().strip().upper()
        if filter_code:
            filtered = [s for s in self.all_servers if s['game'].upper() == filter_code]
        else:
            filtered = self.all_servers.copy()

        self.server_list = filtered
        self.apply_sorting()

    def clear_filter(self):
        """Clear the game code filter and show all servers."""
        self.filter_var.set('')
        self.server_list = self.all_servers.copy()
        self.apply_sorting()

    def copy_ip_to_clipboard(self):
        """Copy the content of the copy_entry to the clipboard."""
        ip_text = self.copy_var.get()
        if ip_text:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(ip_text)
                self.root.update()  # Now it stays on the clipboard after the window is closed
                messagebox.showinfo("Copied", "Server IP copied to clipboard.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy to clipboard: {e}")
        else:
            messagebox.showwarning("No IP", "No server IP to copy.")

    def update_copy_entry(self):
        """Update the copy_entry field based on the selected server and checkbox state."""
        selected_item = self.server_tree.selection()
        if selected_item:
            item = selected_item[0]
            server = self.server_tree.item(item, 'values')
            ip = server[3]
            port = server[4]
            formatted_ip = f"{ip}:{port}"
            if self.connect_var.get():
                formatted_ip = f"connect {formatted_ip}"
            # Update the copy_entry
            self.copy_var.set(formatted_ip)

    def update_copy_entry_checkbox(self):
        """Update the copy_entry when the checkbox state changes."""
        self.update_copy_entry()

    def find_friend(self):
        """Find a friend by name across all servers."""
        friend_name = self.find_friend_var.get().strip()
        if not friend_name:
            messagebox.showwarning("Input Required", "Please enter a player name to find.")
            return
        # Disable the Find button to prevent multiple clicks
        self.find_friend_button.config(state=tk.DISABLED)
        # Define the callback
        def callback():
            self.search_friend(friend_name)
            # Re-enable the Find button
            self.find_friend_button.config(state=tk.NORMAL)
        # Call refresh_servers with callback
        self.refresh_servers(callback)

    def search_friend(self, friend_name):
        """Search for the friend in the player list and select the server if found."""
        found = False
        for server_id, players in self.player_list.items():
            for player in players:
                if player['player_name'].lower() == friend_name.lower():
                    # Find the server in self.server_list
                    for server in self.server_list:
                        if f"{server['ip']}:{server['port']}" == server_id:
                            # Select the server in the Treeview
                            self.server_tree.selection_set(server['tree_item_id'])
                            self.server_tree.see(server['tree_item_id'])
                            # Update player sidebar
                            self.update_player_sidebar(server_id)
                            # Notify user
                            messagebox.showinfo("Found", f"Player '{friend_name}' found on server: {server['server_name']} ({server['ip']}:{server['port']})")
                            found = True
                            return
        if not found:
            messagebox.showinfo("Not Found", f"Player '{friend_name}' was not found on any server.")

def main():
    root = tk.Tk()
    app = ServerListerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
