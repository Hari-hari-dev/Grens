// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract WageMint {
    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;
    bytes32 private storedNextPKH;

    uint256 private _totalSupply;
    string private _name;
    string private _symbol;

    address private authorizedMinter;
    address private _commissionAddress;
    address private _commissionAddress2;
    uint256 private _coinCommission;
    uint256 private _coinCommission2;

    uint256 private lastUsedCommission;
    bytes32 private lastUsedCommissionAddressHash;
    bool init2 = false;
    mapping(address => address) private proposedMinters; // Temporary storage for proposed minters

    // Staking variables
    mapping(address => uint256) private _stakedBalances;
    mapping(address => uint256) private _lastStakedTime;
    uint256 private _annualStakingRate = 55556; // 0.05556% represented in basis points (parts per 10^8)
    uint256 private _stakingInterval = 1 days; // Staking interval (daily)

    event AuthorizedMinterSet(address indexed minter);
    event AuthorizedMinterRemoved(address indexed minter);
    event CommissionSet(uint256 newCoinCommission);
    event CommissionSet2(uint256 newCoinCommission);
    event CommissionAddressSet(address newCommissionAddress);
    event CommissionAddressSet2(address newCommissionAddress);
    event Minted(
        address indexed minter,
        address indexed account,
        uint256 amount
    );
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(
        address indexed owner,
        address indexed spender,
        uint256 value
    );
    event Staked(address indexed staker, uint256 amount);
    event Unstaked(address indexed staker, uint256 amount);

    constructor(
        //address lamportBaseAddress,
        //address initialAuthorizedMinter,
        string memory __name,
        string memory __symbol
    ) {
        _name = __name;
        _symbol = __symbol;

        //_initializeMintProcess(initialAuthorizedMinter);
    }

    function _initializeMintProcess(address initialAuthorizedMinter) private {
        authorizedMinter = initialAuthorizedMinter;
        _mint(authorizedMinter, 80000 * (10**uint256(decimals())));
        authorizedMinter = address(0);
    }

    function batchMintTokens(
        address[] memory accounts,
        uint256[] memory amounts
    ) external {
        require(msg.sender == authorizedMinter, "GP_Mint: Unauthorized minter");
        require(
            accounts.length == amounts.length,
            "GP_Mint: Accounts and amounts length mismatch"
        );

        uint256 totalAmount = 0;

        for (uint256 i = 0; i < accounts.length; i++) {
            if (accounts[i] == address(0)) {
                continue; // Skip the zero address
            }

            // Mint tokens to the user
            _mint(accounts[i], amounts[i]);

            // Update the total supply
            _totalSupply += totalAmount;
        }
        // Staking Functions
    }

    function stakeTokens(uint256 amount) public {
        require(amount > 0, "Amount must be greater than 0");
        require(
            _balances[msg.sender] >= amount,
            "Insufficient balance to stake"
        );

        // Update the staked balance with any pending rewards
        _updateStakedBalance(msg.sender);

        _balances[msg.sender] -= amount;
        _stakedBalances[msg.sender] += amount;
        _lastStakedTime[msg.sender] = block.timestamp;

        emit Staked(msg.sender, amount);
    }

    function unstakeTokens(uint256 amount) public {
        require(amount > 0, "Amount must be greater than 0");

        // Update the staked balance with any pending rewards
        _updateStakedBalance(msg.sender);

        require(
            _stakedBalances[msg.sender] >= amount,
            "Insufficient staked balance"
        );

        // Ensure that two staking intervals have passed since the last stake
        require(
            block.timestamp >=
                _lastStakedTime[msg.sender] + 2 * _stakingInterval,
            "Tokens are still locked"
        );

        _stakedBalances[msg.sender] -= amount;
        _balances[msg.sender] += amount;

        // Update the last staked time
        _lastStakedTime[msg.sender] = block.timestamp;

        emit Unstaked(msg.sender, amount);
    }

    function _updateStakedBalance(address staker) internal {
        uint256 stakedDuration = block.timestamp - _lastStakedTime[staker];
        uint256 periods = stakedDuration / _stakingInterval;

        if (periods > 0) {
            uint256 newStakedBalance = calculateCompoundedStakedBalance(staker);
            _stakedBalances[staker] = newStakedBalance;
            _lastStakedTime[staker] = block.timestamp;
        }
    }

    function calculateCompoundedStakedBalance(address staker)
        public
        view
        returns (uint256)
    {
        uint256 stakedAmount = _stakedBalances[staker];
        uint256 stakedDuration = block.timestamp - _lastStakedTime[staker];
        uint256 periods = stakedDuration / _stakingInterval;

        if (periods == 0) {
            return stakedAmount;
        }

        uint256 dailyRate = _annualStakingRate / 365; // in parts per 10^8

        // Calculate interest factor per period (1 + rate)
        uint256 interestFactor = 1e18 + (dailyRate * 1e10); // Scale rate to 1e18

        // Calculate total interest factor: (1 + rate) ^ periods
        uint256 totalInterestFactor = _pow(interestFactor, periods);

        // Calculate new staked amount: principal * totalInterestFactor / 1e18
        uint256 newStakedAmount = (stakedAmount * totalInterestFactor) / 1e18;

        return newStakedAmount;
    }

    function _pow(uint256 base, uint256 exponent)
        internal
        pure
        returns (uint256 result)
    {
        result = 1e18; // Start with 1 in 1e18 scale
        while (exponent > 0) {
            if (exponent % 2 == 1) {
                result = (result * base) / 1e18;
            }
            exponent = exponent / 2;
            base = (base * base) / 1e18;
        }
    }

    function stakedBalanceOf(address account) public view returns (uint256) {
        uint256 stakedDuration = block.timestamp - _lastStakedTime[account];
        uint256 periods = stakedDuration / _stakingInterval;

        if (periods == 0) {
            return _stakedBalances[account];
        }

        uint256 newStakedBalance = calculateCompoundedStakedBalance(account);
        return newStakedBalance;
    }

    // Existing functions...

    function setAuthorizedMinter(address minter) public {
        require(!init2);
        // Perform Lamport Master Check
        authorizedMinter = minter;
        init2 = false;
    }

    // Internal mint function to handle actual minting and balance updating
    function _mint(address account, uint256 amount) internal {
        require(
            account != address(0),
            "GP_Mint: Cannot mint to the zero address"
        );
        _totalSupply += amount;
        _balances[account] += amount;
        emit Minted(msg.sender, account, amount);
    }

    // ERC20 Standard Functions
    function name() public view returns (string memory) {
        return _name;
    }

    function symbol() public view returns (string memory) {
        return _symbol;
    }

    function decimals() public pure returns (uint8) {
        return 18;
    }

    function totalSupply() public view returns (uint256) {
        return _totalSupply;
    }

    function balanceOf(address account) public view returns (uint256) {
        return _balances[account];
    }

    function transfer(address to, uint256 amount) public returns (bool) {
        require(to != address(0), "ERC20: transfer to the zero address");
        require(
            _balances[msg.sender] >= amount,
            "ERC20: transfer amount exceeds balance"
        );

        _balances[msg.sender] -= amount;
        _balances[to] += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) public returns (bool) {
        _allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function allowance(address owner, address spender)
        public
        view
        returns (uint256)
    {
        return _allowances[owner][spender];
    }

    function transferFrom(
        address from,
        address to,
        uint256 amount
    ) public returns (bool) {
        require(from != address(0), "ERC20: transfer from the zero address");
        require(to != address(0), "ERC20: transfer to the zero address");
        require(
            _balances[from] >= amount,
            "ERC20: transfer amount exceeds balance"
        );
        require(
            _allowances[from][msg.sender] >= amount,
            "ERC20: transfer amount exceeds allowance"
        );

        _balances[from] -= amount;
        _balances[to] += amount;
        _allowances[from][msg.sender] -= amount;
        emit Transfer(from, to, amount);
        return true;
    }

    function increaseAllowance(address spender, uint256 addedValue)
        public
        returns (bool)
    {
        _allowances[msg.sender][spender] += addedValue;
        emit Approval(msg.sender, spender, _allowances[msg.sender][spender]);
        return true;
    }

    function decreaseAllowance(address spender, uint256 subtractedValue)
        public
        returns (bool)
    {
        uint256 currentAllowance = _allowances[msg.sender][spender];
        require(
            currentAllowance >= subtractedValue,
            "ERC20: decreased allowance below zero"
        );
        _allowances[msg.sender][spender] = currentAllowance - subtractedValue;
        emit Approval(msg.sender, spender, _allowances[msg.sender][spender]);
        return true;
    }

    // Commission-related functions and other existing functions unchanged...

    // Commission-related functions
}
