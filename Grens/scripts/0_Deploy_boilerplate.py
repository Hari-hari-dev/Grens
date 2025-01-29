import os
import sys
import time
from brownie import project, network, accounts

# Cross-platform function to wait for 'q' key press or timeout
if sys.platform == 'win32':
    import msvcrt
    def wait_for_q_or_timeout(timeout):
        start_time = time.time()
        print("Press 'q' to exit, or wait for 2 seconds to continue...")
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key.lower() == b'q':
                    return True
            if time.time() - start_time > timeout:
                return False
            time.sleep(0.1)
else:
    import select
    def wait_for_q_or_timeout(timeout):
        print("Press 'CTRL-C' to exit, or wait for 5 seconds to continue...")
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            key = sys.stdin.read(1)
            if key.lower() == 'q':
                return True
        return False

def main():
    # Load the deployer account
    deployer = accounts.load('test2')  # Make sure 'test2' is added to Brownie accounts

    # Define gas price and gas limit
    gas_price = 39 * 10**9  # 2 gwei in wei
    gas_limit = 3000000  # Adjust as necessary

    # Ensure the correct network is selected
    # network.connect('development')

    # List of scripts to run in sequence
    scripts = [
        "1_Wage_Mint_deploy",
        "2_TFCWageDapp_deploy",
        "3_scraper5",
        "4_mass_reg_script-",
        "5_scrape_and_mint",

    ]

    # Run each script in sequence
    for script in scripts:
        print(f"Running {script}...")
        project.run(script)
        print(f"Finished running {script}")

        # Wait for 2 seconds, allow user to press 'q' to exit
        if wait_for_q_or_timeout(5):
            print("Exit signal received. Exiting script.")
            break

    print("All scripts have been executed or exited early.")

if __name__ == "__main__":
    main()
