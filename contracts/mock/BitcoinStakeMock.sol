// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;

import "../BitcoinStake.sol";
import "../lib/BytesLib.sol";

contract BitcoinStakeMock is BitcoinStake {
    uint64 public MONTH_TIMESTAMP = 2592000;

    function developmentInit() external {
        gradeActive = true;
    }

    // function getRewardMap(address delegator) external view returns (uint256, uint256) {
    //     uint256 reward;
    //     uint256 unclaimedReward;
    //     reward = rewardMap[delegator].reward;
    //     unclaimedReward = rewardMap[delegator].unclaimedReward;
    //     return (reward, unclaimedReward);
    // }
    
    // function setRewardMap(address delegator, uint256 reward, uint256 unclaimedReward) external {
    //     rewardMap[delegator].reward = reward;
    //     rewardMap[delegator].unclaimedReward = unclaimedReward;
    // }

    function setRoundTag(uint value) external {
        roundTag = value;
    }

    // function setInitTlpRates(
    //     uint64[5] calldata values, 
    //     uint32[5] calldata rates
    // ) external {
    //     for (uint256 i = 0; i < 5; i++) {
    //         grades.push(LockLengthGrade(values[i] * MONTH_TIMESTAMP, rates[i]));
    //     }
    // }


    // function popTtlpRates() external {
    //     delete grades;
    // }

    function getGradesLength() external view returns (uint256) {
        return grades.length;
    }

    // function setBtcRewardMap(address delegator, uint256 reward, uint256 unclaimed, uint256 accStakedAmount) external {
    //     rewardMap[delegator] = Reward(reward, unclaimed, accStakedAmount);
    // }

    function setIsActive(bool value) external {
        gradeActive = value;
    }

    function setDelegatorMap(address delegator, bytes32 value) external {
        delegatorMap[delegator].txids.push(value);
    }

    function getRound2expireInfoMap(uint256 round) external view returns (address[] memory candidateList, uint256[] memory amounts) {
        ExpireInfo storage expireInfo = round2expireInfoMap[round];
        candidateList = expireInfo.candidateList;
        amounts = new uint256[](candidateList.length);
        for (uint256 i = 0; i < candidateList.length; i++) {
            amounts[i] = expireInfo.amountMap[candidateList[i]];
        }
        return (candidateList, amounts);
    }


    function setCandidateMap(address validator, uint256 stakedAmount, uint256 realtimeAmount, uint256 [] memory value, uint256 undelegateAmount) external {
        candidateMap[validator] = Candidate(stakedAmount, realtimeAmount, value, undelegateAmount);
    }

    function setAccruedRewardPerBTCMap(address validator, uint256 round, uint256 value) external {
        accruedRewardPerBTCMap[validator][round] = value;
    }

    function getAgentAddrList(uint256 index) external view returns (address[] memory) {
        ExpireInfo storage expireInfo = round2expireInfoMap[index];
        uint256 length = expireInfo.candidateList.length;
        address[] memory agentAddresses = new address[](length);
        for (uint256 i = 0; i < length; i++) {
            agentAddresses[i] = expireInfo.candidateList[i];
        }
        return agentAddresses;
    }

    // function getDelegatorReward(address delegator) external view returns (uint256) {
    //     return delegatorMap[delegator];
    // }
    // for unit test
    function collectRewardMock(bytes32 txid, uint256 coreAmount, uint256 settleRound,bool isStakeWeight) external returns (uint256 reward, bool expired, int256 floatReward, uint256 remainingCoreAmount) {
        return _collectReward(txid, coreAmount, settleRound, isStakeWeight);
    }
    function getCalculateRoundMock(uint32 lockTime, uint256 settleRound) external view returns (uint calculateRound, bool expired) {
        return _getCalculateRound(lockTime, settleRound);
    }
    function getReceiptMapNotExpiredReward(bytes32 txid) external view returns (uint256 reward) {
        if (receiptMap[txid].expired) {
            return 0;
        }
        return receiptMap[txid].reward;
    }
    function getReceiptMapExpiredReward(bytes32 txid) external view returns (uint256 reward) {
        if (receiptMap[txid].expired) {
            return receiptMap[txid].reward;
        }
        return 0;
    }



}
