pragma solidity 0.8.4;

import "../StakeHub.sol";

contract StakeHubMock is StakeHub {
    uint256 public rewardAmountM;

    function developmentInit() external {
//        BTC_UNIT_CONVERSION = BTC_UNIT_CONVERSION / 1e9 / 2;
    }

    function setCandidateAmountMap(address agent, uint256 value, uint256 value1, uint256 value2) external {
        candidateAmountMap[agent].push(value);
        candidateAmountMap[agent].push(value1);
        candidateAmountMap[agent].push(value2);
        candidateScoreMap[agent] = value + value1 * HASH_UNIT_CONVERSION * INIT_HASH_FACTOR + value2 * BTC_UNIT_CONVERSION * INIT_BTC_FACTOR;
    }

    function setLiabilityOperators(address value, address value1) external {
        BTC_STAKE_ADDR = value;
        BTCLST_STAKE_ADDR = value1;
    }

    function getLiabilities(address delegator) external view returns (NotePayable[] memory) {
        return liabilities[delegator].notes;
    }


    function setStateMapDiscount(address agent, uint256 value, uint256 value1, uint256 value2) external {
        stateMap[agent] = AssetState(value, value1, value2);
    }

}
