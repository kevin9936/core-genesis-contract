pragma solidity 0.8.4;

import {CoreAgent} from "../CoreAgent.sol";

contract CoreAgentMock is CoreAgent {
    uint256 public rewardAmountM;

    function developmentInit() external {
        requiredCoinDeposit = requiredCoinDeposit / 1e16;
        roundTag = 1;
    }

    function setRoundTag(uint value) external {
        roundTag = value;
    }


    function getDelegatorMap(address delegator) external view returns (address[] memory, uint256) {
        address[] memory candidates = delegatorMap[delegator].candidates;
        uint256 amount = delegatorMap[delegator].amount;
        return (candidates, amount);
    }

    function getAccuredRewardMap(address validator, uint256 round) external view returns (uint256) {
        uint256 accuredReward = accuredRewardMap[validator][round];
        return accuredReward;
    }

    function setAccuredRewardMap(address candidate, uint256 round, uint256 amount) external {
        accuredRewardMap[candidate][round] = amount;
    }

    function setCoreRewardMap(address delegator, uint256 reward) external {
        rewardMap[delegator] = reward;
    }


    function getContinuousRewardEndRounds(address candidate) external view returns (uint256[] memory) {
        return candidateMap[candidate].continuousRewardEndRounds;
    }


    function setCandidateMapAmount(address candidate, uint256 amount, uint256 realAmount, uint256 endRound) external {
        candidateMap[candidate].amount = amount;
        candidateMap[candidate].realtimeAmount = realAmount;
        if (endRound > 0) {
            candidateMap[candidate].continuousRewardEndRounds.push(endRound);
        }
    }

    function getRewardAmount() external view returns (uint256) {
        return rewardAmountM;
    }

    function setRewardMap(address delegator, uint256 reward, uint256 unclaimedReward) external {
        rewardMap[delegator] = reward;
    }

    function collectCoinRewardMock(address agent, address delegator, bool clearRewardMap) external returns (uint256) {
        Candidate storage a = candidateMap[agent];
        CoinDelegator storage d = a.cDelegatorMap[delegator];
        rewardAmountM = calculateRewardInternal(delegator, clearRewardMap);
        return rewardAmountM;
    }


}
