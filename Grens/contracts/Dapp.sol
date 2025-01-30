// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * Minimal interface for the Activity_Mint contract.
 * We only need to call `batchMintTokens(...)`.
 */
interface IActivityMint {
    function batchMintTokens(address[] memory accounts, uint256[] memory amounts) external;
    function balanceOf(address account) external view returns (uint256);
}

/**
 * Minimal interface for the Gateway Token Verifier (face-scan / civic gating).
 */
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
    function setValidator(address _validator, bool _status) external onlyOwner {
        validators[_validator] = _status;
        emit ValidatorSet(_validator, _status);
    }
    mapping(address => bool) public validators;
    event ValidatorSet(address indexed validator, bool status);


    constructor(address _activityMintContract) {
        _transferOwnership(msg.sender);
        // Example references
        activityMintContract = IActivityMint(_activityMintContract);
        gatewayVerifier      = IGatewayTokenVerifier(0xF65b6396dF6B7e2D8a6270E3AB6c7BB08BAEF22E);
        gatekeeperNetwork    = 10; 
        validators[msg.sender] = true;
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
    // Validator management
    // ----------------------------------------------------------------------

    // ----------------------------------------------------------------------
    // Player Data
    // ----------------------------------------------------------------------
    struct Player {
        address gatingAddress;  
        string  playerName;     
        uint256 lastMintTime;
        bool    exists;         // "true" if active, "false" if deleted
    }

    // Keyed by gating address
    mapping(address => Player) private players;

    // Permanent name->address mapping
    // Once a name is set, it never returns to address(0), even if the player is deleted.
    mapping(string => address) private nameToAddress;

    // An array of all names, appended on each new registration
    // never removed from
    string[] private allPlayerNames;

    // ----------------------------------------------------------------------
    // Mint Rate
    // ----------------------------------------------------------------------
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
        require(
            gatewayVerifier.verifyToken(msg.sender, gatekeeperNetwork),
            "Invalid gateway token"
        );
        _;
    }
    modifier onlyValidator() {
        require(validators[msg.sender], "Caller is not a validator");
        _;
    }

    // ----------------------------------------------------------------------
    // Owner Admin
    // ----------------------------------------------------------------------


    // ----------------------------------------------------------------------
    // Player Onboarding
    // ----------------------------------------------------------------------

    /**
     * @dev Onboard a new player if they pass the gating check:
     *      - Name must NOT be in use (once used, it's forever taken).
     *      - Address must not already exist.
     *      - Mark them as `exists=true`.
     *      - Add the name to `allPlayerNames`.
     *      - We do NOT remove from either if the user is "deleted."
     */
    function onboardPlayerGated(string calldata _playerName) external gated {
        require(bytes(_playerName).length > 0,              "Empty name");
        require(!players[msg.sender].exists,                "Address already onboarded");
        require(nameToAddress[_playerName] == address(0),   "Name already in use");

        players[msg.sender] = Player({
            gatingAddress: msg.sender,
            playerName:    _playerName,
            lastMintTime:  block.timestamp,
            exists:        true
        });

        // Once set, we never reset nameToAddress[_playerName] to address(0)
        nameToAddress[_playerName] = msg.sender;

        allPlayerNames.push(_playerName);

        emit PlayerOnboarded(msg.sender, _playerName);
    }

    /**
     * @dev If the owner or a validator wants to forcibly onboard an address,
     *      ignoring the gating requirement. 
     */
    function debugOnboard(address _gatingAddress, string calldata _playerName) external onlyOwner {
        require(_gatingAddress != address(0),               "Zero address");
        require(bytes(_playerName).length > 0,              "Empty name");
        require(!players[_gatingAddress].exists,            "Address already onboarded");
        require(nameToAddress[_playerName] == address(0),   "Name already in use");

        players[_gatingAddress] = Player({
            gatingAddress: _gatingAddress,
            playerName:    _playerName,
            lastMintTime:  block.timestamp,
            exists:        true
        });

        nameToAddress[_playerName] = _gatingAddress;
        allPlayerNames.push(_playerName);

        emit PlayerOnboarded(_gatingAddress, _playerName);
    }

    /**
     * @dev "Soft-delete" a player. We do NOT remove the name from `nameToAddress`,
     *      because the name is "permanent." This function simply sets `exists = false`.
     */

    // ----------------------------------------------------------------------
    // Bulk Minting Logic
    // ----------------------------------------------------------------------
    function mintForPlayersBatch(string[] calldata _playerNames) external onlyValidator {
        address[] memory recipients = new address[](_playerNames.length * 2);
        uint256[] memory amounts    = new uint256[](_playerNames.length * 2);

        uint256 arrayIndex = 0;

        for (uint256 i = 0; i < _playerNames.length; i++) {
            // 1. Resolve the gating address from the name
            address gatingAddr = nameToAddress[_playerNames[i]];
            if (gatingAddr == address(0)) {
                // No record of this name -> skip
                continue;
            }

            // 2. Retrieve the player struct
            Player storage p = players[gatingAddr];
            if (!p.exists) {
                // Player was deleted or never existed -> skip
                continue;
            }

            // 2.1 Check gateway validity
            // If `gatewayVerifier.verifyToken()` is false => skip
            if (!gatewayVerifier.verifyToken(gatingAddr, gatekeeperNetwork)) {
                // Not a valid gating address => skip
                continue;
            }

            // 3. Check time delta
            uint256 delta = block.timestamp - p.lastMintTime;
            if (delta == 0) {
                // No time since last mint -> skip
                continue;
            }

            // If delta < 7min or > 34min => skip => but still update lastMintTime
            if (delta < 7 minutes || delta > 34 minutes) {
                p.lastMintTime = block.timestamp; 
                continue;
            }

            // (Otherwise, delta is within [7..34] => do a normal mint)
            p.lastMintTime = block.timestamp;

            // 4. Calculate total minted
            // ~2.833333 TFC/min => 170 TFC/hour => 170e18 per 3600
            uint256 totalMint = (delta * REWARD_PER_HOUR) / 3600;

            // 4% fee to validator, 96% to player
            uint256 validatorCut = (totalMint * 4) / 100;
            uint256 playerCut    = totalMint - validatorCut;

            // 5. Fill in the arrays
            recipients[arrayIndex] = gatingAddr;
            amounts[arrayIndex]    = playerCut;
            arrayIndex++;

            recipients[arrayIndex] = msg.sender; // The validator
            amounts[arrayIndex]    = validatorCut;
            arrayIndex++;

            emit PlayerMinted(gatingAddr, playerCut, validatorCut);
        }

        // If no mints, stop here
        if (arrayIndex == 0) {
            return;
        }

        // Slice arrays down to actual used length
        address[] memory finalRecipients = new address[](arrayIndex);
        uint256[] memory finalAmounts    = new uint256[](arrayIndex);
        for (uint256 j = 0; j < arrayIndex; j++) {
            finalRecipients[j] = recipients[j];
            finalAmounts[j]    = amounts[j];
        }

        // 6. One bulk mint call
        activityMintContract.batchMintTokens(finalRecipients, finalAmounts);
    }

    // --------------------------------------------------------------------
    // Name Iteration
    // ----------------------------------------------------------------------

    /**
     * @notice Because all names are permanent, `allPlayerNames` will hold every
     *         name ever used, even if the player is deleted or turned `exists=false`.
     */
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

    /**
     * @dev Example pagination
     */
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
            // Return empty
            return (new string[](0), allPlayerNames.length);
        }

        string[] memory names = new string[](end - start);
        for (uint256 i = start; i < end; i++) {
            names[i - start] = allPlayerNames[i];
        }
        return (names, end);
    }

    // ----------------------------------------------------------------------
    // Lookups
    // ----------------------------------------------------------------------

    /**
     * @notice If you want to see which address claimed a name,
     *         This never resets to `address(0)` once set.
     */
    function getAddressByName(string calldata _playerName) external view returns (address) {
        return nameToAddress[_playerName];
    }

    /**
     * @notice Returns the player's stored info by gating address.
     *         If `exists` is false, they've been "soft deleted."
     */
    // function getPlayerInfo(address _gatingAddress)
    //     external
    //     view
    //     returns (string memory playerName, uint256 lastMintTime, bool exists)
    // {
    //     Player memory p = players[_gatingAddress];
    //     return (p.playerName, p.lastMintTime, p.exists);
    // }
}
