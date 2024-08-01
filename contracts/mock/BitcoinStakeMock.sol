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

    function getRewardMap(address delegator) external view returns (uint256, uint256) {
        uint256 reward;
        uint256 unclaimedReward;
        reward = rewardMap[delegator].reward;
        unclaimedReward = rewardMap[delegator].unclaimedReward;
        return (reward, unclaimedReward);
    }


    function setRoundTag(uint value) external {
        roundTag = value;
    }

    function setInitTlpRates(uint value1, uint balue01, uint value2, uint balue02, uint value3, uint balue03, uint value4, uint balue04, uint value5, uint balue05) external {
//        roundTag = value;
        tlpRates.push(TLP(value1, balue01));
        tlpRates.push(TLP(value2, balue02));
        tlpRates.push(TLP(value3, balue03));
        tlpRates.push(TLP(value4, balue04));
        tlpRates.push(TLP(value5, balue05));
    }

    function setTlpRates(uint value1, uint balue01) external {
        tlpRates.push(TLP(value1, balue01));
    }

    function popTtlpRates() external {
        delete tlpRates;
    }


    function setIsActive(bool value) external {
        isActive = value;
    }


}
