import tkinter as tk
from brownie import accounts, web3, PlayerDatabase, Activity_Mint
from pathlib import Path

class PlayerMonitorApp:
    def __init__(self, main_window, player_db_contract, mint_contract):
        self.main_window = main_window
        self.player_db_contract = player_db_contract
        self.mint_contract = mint_contract

        self.server_players = {}
        self.player_balances = {}

        self.create_gui()

    # Fetch player names with reward addresses
    def get_player_data(self):
        print("Fetching player data...")  # Debug
        player_data = self.player_db_contract.getPlayerNamesWithRewardAddresses(0, 200)
        print(f"Fetched player data: {player_data}")  # Debug: Print player data
        return player_data

    # Fetch altcoin balance for a specific address and format it
    def get_altcoin_balance(self, address):
        balance_wei = self.mint_contract.balanceOf(address)
        balance_str = balance_wei / 10**18
        return balance_str

    # Update the listbox based on search query
    def update_listbox(self, search_query):
        self.listbox.delete(0, tk.END)  # Clear the listbox

        for server, players in self.server_players.items():
            matching_players = [player for player in players if search_query.lower() in player["name"].lower()]

            if matching_players:
                self.listbox.insert(tk.END, f"Server {server}:")
                self.listbox.insert(tk.END, "----------------------------------")
                for player in matching_players:
                    player_name = player["name"]
                    player_address = player["address"]
                    balance = self.player_balances.get(player_address, "N/A")
                    self.listbox.insert(tk.END, f"Name: {player_name} | Address: {player_address} | Balance: {balance} ALT")
                self.listbox.insert(tk.END, "")

    # Create the GUI components
    def create_gui(self):
        # Create a frame for the scrollbar and list
        frame = tk.Frame(self.main_window)
        frame.pack(fill=tk.BOTH, expand=1)

        # Create a search field
        search_frame = tk.Frame(self.main_window)
        search_frame.pack(fill=tk.X)
        search_label = tk.Label(search_frame, text="Search Player Name:")
        search_label.pack(side=tk.LEFT, padx=10)
        search_entry = tk.Entry(search_frame)
        search_entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=1)

        # Add a scrollbar
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create a listbox that uses the scrollbar
        self.listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, width=100)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scrollbar.config(command=self.listbox.yview)

        # Search button to trigger the search and update the listbox
        search_button = tk.Button(search_frame, text="Search", command=lambda: self.update_listbox(search_entry.get()))
        search_button.pack(side=tk.RIGHT, padx=10)

        # Start the refresh loop
        self.refresh_data()

    # Refresh the player data every 10 seconds
    def refresh_data(self):
        print("Refreshing player data...")  # Debug
        players_with_addresses = self.get_player_data()

        # Check if data is being fetched correctly
        if not players_with_addresses:
            print("No player data found.")  # Debug
            return

        self.server_players = {}
        for player_name, player_address in players_with_addresses:
            server = player_name.split('_')[0]  # Customize this if needed
            if server not in self.server_players:
                self.server_players[server] = []
            self.server_players[server].append({"name": player_name, "address": player_address})

        print(f"Server players: {self.server_players}")  # Debug

        self.player_balances = {}
        for server, players in self.server_players.items():
            for player in players:
                player_address = player["address"]
                self.player_balances[player_address] = self.get_altcoin_balance(player_address)

        print(f"Player balances: {self.player_balances}")  # Debug

        # Update the listbox with new data (without search filter for now)
        self.update_listbox("")

        # Schedule the next refresh after 10 seconds
        self.main_window.after(10000, self.refresh_data)


# Load PlayerDatabase and Activity_Mint contracts
def load_contracts():
    with open('Activity-PlayerDatabase.txt', 'r') as file:
        database_address = file.read().strip()

    with open('Activity-Mint.txt', 'r') as file:
        mint_address = file.read().strip()

    player_db_contract = PlayerDatabase.at(database_address)
    mint_contract = Activity_Mint.at(mint_address)

    return player_db_contract, mint_contract

# Main function to run the entire setup
def main():
    main_window = tk.Tk()
    main_window.title("Live Known Players by Server")

    player_db_contract, mint_contract = load_contracts()

    app = PlayerMonitorApp(main_window, player_db_contract, mint_contract)

    main_window.mainloop()

if __name__ == "__main__":
    main()
