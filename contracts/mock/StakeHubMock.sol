pragma solidity 0.8.4;

import "../StakeHub.sol";

contract StakeHubMock is StakeHub {
    uint256 public rewardAmountM;

    function developmentInit() external {
//        BTC_UNIT_CONVERSION = BTC_UNIT_CONVERSION / 1e9 / 2;
    }

    function setCandidateAmountMap(address account, uint256[] memory value, uint256 value1) external {
        candidateAmountMap[account] = value;
        candidateScoreMap[account] = value1;
    }


}
