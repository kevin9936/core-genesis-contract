// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;

import "../BitcoinAgent.sol";

contract BitcoinAgentMock is BitcoinAgent {
    uint64 public MONTH_TIMESTAMP = 2592000;
    
    function setCandidateMap(address candidate, uint256 lstStakeAmount, uint256 stakeAmount) external {
        candidateMap[candidate] = StakeAmount(lstStakeAmount, stakeAmount);
    }
    
    function setInitLpRates(
        uint32[4] calldata values,
        uint32[4] calldata rates
    ) external {
        delete grades;
        for (uint256 i = 0; i < 4; i++) {
            grades.push(DualStakingGrade(values[i], rates[i]));
        }
    }
    function setInitTlpRates(
        uint64[5] calldata values, 
        uint32[5] calldata rates
    ) external {
        for (uint256 i = 0; i < 5; i++) {
            lockLengthGrades.push(LockLengthGrade(values[i] * MONTH_TIMESTAMP, rates[i]));
        }
    }

    function setLpRates(uint32 stakeRate, uint32 percentage) external {
        grades.push(DualStakingGrade(stakeRate, percentage));
    }


    function getGradesLength() external view returns (uint256) {
        return grades.length;
    }

    function popLpRates() external {
        delete grades;
    }

    function setIsActive(bool value) external {
        gradeActive = value;
    }
    function setAssetWeight(uint256 value) external {
        assetWeight = value;
    }

    function setTlpRates(uint64 lockDuration, uint32 percentage) external {
        lockLengthGrades.push(LockLengthGrade(lockDuration, percentage));
    }
    function popTtlpRates() external {
        delete lockLengthGrades;
    }
    function getTlpGradesLength() external view returns (uint256) {
        return lockLengthGrades.length;
    }

    // for unit test
    function applyDualStakingMock(uint256 coreAmount, uint256 btcAmount) external view returns (uint256, uint256) {
        return _applyDualStaking(coreAmount, btcAmount);
    }

}
