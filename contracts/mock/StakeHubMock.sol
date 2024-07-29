pragma solidity 0.8.4;

import "../StakeHub.sol";
import "../interface/IPledgeAgent.sol";

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

    function getDebts(address delegator) external view returns (NotePayable[] memory) {
        return debts[delegator].notes;
    }


    function setStateMapDiscount(address agent, uint256 value, uint256 value1, uint256 value2) external {
        stateMap[agent] = AssetState(value, value1, value2);
    }
    function uintToString(uint256 value) internal pure returns (string memory) {
    if (value == 0) {
        return "0";
    }

    uint256 tempValue = value;
    uint256 digits;

    while (tempValue != 0) {
        digits++;
        tempValue /= 10;
    }

    bytes memory buffer = new bytes(digits);

    while (value != 0) {
        buffer[--digits] = bytes1(uint8(48 + value % 10));
        value /= 10;
    }

    return string(buffer);
}


    function initHybridScoreMock() external {
    // get validator set
    address[] memory validators = IValidatorSet(VALIDATOR_CONTRACT_ADDR).getValidatorOps();
    (bool success, bytes memory data) = PLEDGE_AGENT_ADDR.call(abi.encodeWithSignature("getStakeInfo(address[])", validators));
    require (success, "call PLEDGE_AGENT_ADDR.getStakeInfo 2 fail");
    (uint256[] memory cores, uint256[] memory hashs, uint256[] memory btcs) = abi.decode(data, (uint256[], uint256[], uint256[]));

    (success,) = assets[2].agent.call(abi.encodeWithSignature("initHardforkRound(address[],uint256[])", validators, btcs));
    require (success, "call BTC_AGENT_ADDR.initHardforkRound fail");

    uint256 validatorSize = validators.length;
//    require(false,string(abi.encodePacked("Error: Your error message with number: ", uintToString(validatorSize))));
    uint256[] memory totalAmounts = new uint256[](3);
    for (uint256 i = 0; i < validatorSize; ++i) {
      address validator = validators[i];

      totalAmounts[0] += cores[i];
      totalAmounts[1] += hashs[i];
      totalAmounts[2] += btcs[i];

      candidateAmountMap[validator].push(cores[i]);
      candidateAmountMap[validator].push(hashs[i]);
      candidateAmountMap[validator].push(btcs[i]);

      candidateScoreMap[validator] = cores[i] * assets[0].factor + hashs[i] * assets[1].factor + btcs[i] * assets[2].factor;
    }

    for (uint256 j = 0; j < 3; j++) {
      stateMap[assets[j].agent] = AssetState(totalAmounts[j], assets[j].factor, SatoshiPlusHelper.DENOMINATOR);
    }

    // get active candidates.
    (success, data) = CANDIDATE_HUB_ADDR.call(abi.encodeWithSignature("getCandidates()"));
    require (success, "call CANDIDATE_HUB.getCandidates fail");
    address[] memory candidates = abi.decode(data, (address[]));
    // move candidate amount.
//    require(false,'sdfasf');
//    IPledgeAgent(PLEDGE_AGENT_ADDR).moveAgent(candidates);
    (success,data) = PLEDGE_AGENT_ADDR.call(abi.encodeWithSignature("moveAgent(address[])", candidates));
    require (success, "call PLEDGE_AGENT_ADDR.moveAgent fail");
  }

}
