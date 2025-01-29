import re

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
                    servers.append((game_code, country_code, title, ip_port))
    except FileNotFoundError:
        print(f"File {filename} not found.")
    return servers

def remove_duplicate_servers(servers):
    seen = set()
    unique_servers = []
    
    for server in servers:
        ip_port = server[3]  # The IP:Port is the key we're checking for duplicates
        if ip_port not in seen:
            unique_servers.append(server)
            seen.add(ip_port)
    
    return unique_servers

def write_sanitized_servers(filename, servers):
    with open(filename, 'w') as f:
        for server in servers:
            f.write(','.join(server) + '\n')

def main():
    input_file = 'servers.txt'
    output_file = 'sanitized_servers.txt'

    # Load servers from the file
    servers = load_servers_from_file(input_file)

    # Remove duplicates
    unique_servers = remove_duplicate_servers(servers)

    # Write the sanitized list back to a new file
    write_sanitized_servers(output_file, unique_servers)

    print(f"Sanitized server list written to {output_file}")

if __name__ == "__main__":
    main()
