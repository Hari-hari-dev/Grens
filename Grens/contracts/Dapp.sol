// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IActivityMint {
    function batchMintTokens(address[] memory accounts, uint256[] memory amounts) external;
    function balanceOf(address account) external view returns (uint256);
}

interface IGatewayTokenVerifier {
    function verifyToken(address owner, uint256 network) external view returns (bool);
}

contract TFCWageDapp {
    // ----------------------------------------------------------------------
    // Ownership (lightweight Ownable logic)
    // ----------------------------------------------------------------------
    address private _owner;

    error OwnableUnauthorizedAccount(address account);
    error OwnableInvalidOwner(address owner);

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        _checkOwner();
        _;
    }

    // For validators
    function setValidator(address _validator, bool _status) external onlyOwner {
        validators[_validator] = _status;
        emit ValidatorSet(_validator, _status);
    }
    mapping(address => bool) public validators;
    event ValidatorSet(address indexed validator, bool status);

    // (A) The special whitelisted address
    address public constant WHITELISTED_ADDRESS = 0xb69f3807EB3E415756426Fa5DEfA6Fc97a167fd0;

    constructor(address _activityMintContract) {
        _transferOwnership(msg.sender);

        activityMintContract = IActivityMint(_activityMintContract);
        gatewayVerifier      = IGatewayTokenVerifier(0xF65b6396dF6B7e2D8a6270E3AB6c7BB08BAEF22E);
        gatekeeperNetwork    = 10;

        validators[msg.sender] = true;

        players[WHITELISTED_ADDRESS] = Player({
            gatingAddress: WHITELISTED_ADDRESS,
            playerName:    "legopowa",
            lastMintTime:  block.timestamp,
            exists:        true
        });

        nameToAddress["legopowa"] = WHITELISTED_ADDRESS;
        allPlayerNames.push("legopowa");
    }

    function owner() public view returns (address) {
        return _owner;
    }
    function _checkOwner() internal view {
        if (msg.sender != _owner) {
            revert OwnableUnauthorizedAccount(msg.sender);
        }
    }
    function _transferOwnership(address newOwner) internal {
        if (newOwner == address(0)) {
            revert OwnableInvalidOwner(address(0));
        }
        address oldOwner = _owner;
        _owner = newOwner;
        emit OwnershipTransferred(oldOwner, newOwner);
    }
    function transferOwnership(address newOwner) external onlyOwner {
        _transferOwnership(newOwner);
    }
    function renounceOwnership() external onlyOwner {
        _transferOwnership(address(0));
    }

    // ----------------------------------------------------------------------
    // External references
    // ----------------------------------------------------------------------
    IActivityMint public activityMintContract;
    IGatewayTokenVerifier public gatewayVerifier;
    uint256 public gatekeeperNetwork;

    // ----------------------------------------------------------------------
    // Player data
    // ----------------------------------------------------------------------
    struct Player {
        address gatingAddress;  
        string  playerName;     
        uint256 lastMintTime;
        bool    exists;         // "true" if active, "false" if deleted
    }

    mapping(address => Player) private players;
    mapping(string => address)  private nameToAddress;
    string[] private allPlayerNames;

    // The mint rate for TFC
    uint256 private constant REWARD_PER_HOUR = 170 ether;

    // ----------------------------------------------------------------------
    // Events
    // ----------------------------------------------------------------------
    event PlayerOnboarded(address indexed gatingAddress, string playerName);
    event PlayerMinted(address indexed gatingAddress, uint256 amountToPlayer, uint256 amountToValidator);
    event GatewayNetworkUpdated(address indexed verifier, uint256 network);

    // ----------------------------------------------------------------------
    // Modifiers
    // ----------------------------------------------------------------------
    modifier gated() {
        // Now we do `_checkPassOk(msg.sender)` instead of gatewayVerifier directly
        require(
            _checkPassOk(msg.sender),
            "Invalid gateway token"
        );
        _;
    }
    modifier onlyValidator() {
        require(validators[msg.sender], "Caller is not a validator");
        _;
    }

    // ----------------------------------------------------------------------
    // Internal check for passOk, with whitelist override
    // ----------------------------------------------------------------------
    function _checkPassOk(address addr) internal view returns (bool) {
        // If it's the whitelisted address => automatically pass
        if (addr == WHITELISTED_ADDRESS) {
            return true;
        }
        // Otherwise, do the normal gateway check
        return gatewayVerifier.verifyToken(addr, gatekeeperNetwork);
    }

    // ----------------------------------------------------------------------
    // Player Onboarding
    // ----------------------------------------------------------------------
    function onboardPlayerGated(string calldata _playerName) external gated {
        require(bytes(_playerName).length > 0,            "Empty name");
        require(!players[msg.sender].exists,              "Address already onboarded");
        require(nameToAddress[_playerName] == address(0), "Name already in use");

        players[msg.sender] = Player({
            gatingAddress: msg.sender,
            playerName:    _playerName,
            lastMintTime:  block.timestamp,
            exists:        true
        });

        nameToAddress[_playerName] = msg.sender;
        allPlayerNames.push(_playerName);

        emit PlayerOnboarded(msg.sender, _playerName);
    }

    // ----------------------------------------------------------------------
    // Bulk Minting Logic
    // ----------------------------------------------------------------------
    function mintForPlayersBatch(string[] calldata _playerNames) external onlyValidator {
        address[] memory recipients = new address[](_playerNames.length * 2);
        uint256[] memory amounts    = new uint256[](_playerNames.length * 2);

        uint256 arrayIndex = 0;

        for (uint256 i = 0; i < _playerNames.length; i++) {
            address gatingAddr = nameToAddress[_playerNames[i]];
            if (gatingAddr == address(0)) {
                // No record of this name -> skip
                continue;
            }

            Player storage p = players[gatingAddr];
            if (!p.exists) {
                // Player was deleted or never existed -> skip
                continue;
            }

            // (B) Use `_checkPassOk(gatingAddr)` instead of direct `verifyToken(...)`
            if (!_checkPassOk(gatingAddr)) {
                // Not a valid gating address => skip
                continue;
            }

            uint256 delta = block.timestamp - p.lastMintTime;
            if (delta == 0) {
                continue;
            }

            // If delta < 4min => skip, if > 34min => skip but reset lastMintTime
            if (delta < 4 minutes ) {
                continue;
            }
            if (delta > 34 minutes) {
                p.lastMintTime = block.timestamp;
                continue;
            }

            // Normal mint
            p.lastMintTime = block.timestamp;

            uint256 totalMint   = (delta * REWARD_PER_HOUR) / 3600;
            uint256 validatorCut = (totalMint * 4) / 100;
            uint256 playerCut    = totalMint - validatorCut;

            recipients[arrayIndex] = gatingAddr;
            amounts[arrayIndex]    = playerCut;
            arrayIndex++;

            recipients[arrayIndex] = msg.sender; 
            amounts[arrayIndex]    = validatorCut;
            arrayIndex++;

            emit PlayerMinted(gatingAddr, playerCut, validatorCut);
        }

        // If no mints, stop
        if (arrayIndex == 0) {
            return;
        }

        address[] memory finalRecipients = new address[](arrayIndex);
        uint256[] memory finalAmounts    = new uint256[](arrayIndex);

        for (uint256 j = 0; j < arrayIndex; j++) {
            finalRecipients[j] = recipients[j];
            finalAmounts[j]    = amounts[j];
        }

        activityMintContract.batchMintTokens(finalRecipients, finalAmounts);
    }

    // ----------------------------------------------------------------------
    // Name/Address Data + Soft Gating
    // ----------------------------------------------------------------------
    function getAddressByName(string calldata _playerName)
        external
        view
        returns (address gatingAddr, bool passOk)
    {
        gatingAddr = nameToAddress[_playerName];
        if (gatingAddr == address(0)) {
            // Name not used or not found
            return (address(0), false);
        }

        passOk = _checkPassOk(gatingAddr);
    }

    function getNameByAddress(address addr)
        external
        view
        returns (string memory playerName, bool passOk)
    {
        Player storage p = players[addr];
        if (!p.exists) {
            return ("", false);
        }

        playerName = p.playerName;
        passOk     = _checkPassOk(addr);
    }

    // Some example helpers for iteration/pagination
    function getPlayerNamesCount() external view returns (uint256) {
        return allPlayerNames.length;
    }
    function getAllPlayerNames() external view returns (string[] memory) {
        return allPlayerNames;
    }
    function getPlayerNameByIndex(uint256 index) external view returns (string memory) {
        require(index < allPlayerNames.length, "Out of range");
        return allPlayerNames[index];
    }
    function getPlayerNamesPaginated(uint256 start, uint256 count)
        external
        view
        returns (string[] memory page, uint256 nextIndex)
    {
        uint256 end = start + count;
        if (end > allPlayerNames.length) {
            end = allPlayerNames.length;
        }
        if (start >= end) {
            return (new string[](0), allPlayerNames.length);
        }

        string[] memory names = new string[](end - start);
        for (uint256 i = start; i < end; i++) {
            names[i - start] = allPlayerNames[i];
        }
        return (names, end);
    }
}
