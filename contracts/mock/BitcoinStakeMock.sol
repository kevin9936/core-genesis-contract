pragma solidity 0.8.4;

import "../BitcoinStake.sol";
import "../lib/BytesLib.sol";

contract BitcoinStakeMock is BitcoinStake {
    uint256 public minBtcLockRound;

    function developmentInit() external {
        minBtcLockRound = 1;
    }

    function getDelegatorBtcMap(address delegator) external view returns (bytes32[] memory) {
        return delegatorMap[delegator].txids;
    }

    function setRoundTag(uint value) external {
        roundTag = value;
    }


}
