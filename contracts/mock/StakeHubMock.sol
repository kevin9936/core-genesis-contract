pragma solidity 0.8.4;

import "../StakeHub.sol";
import "../interface/IPledgeAgent.sol";
import "../interface/IAgent.sol";

contract StakeHubMock is StakeHub {
    uint256 public rewardAmountM;

    uint256 public constant TEST_HASH_UNIT_CONVERSION = 10;
    uint256 public constant TEST_INIT_HASH_FACTOR = 50;
    uint256 public constant TEST_BTC_UNIT_CONVERSION = 5;
    uint256 public constant TEST_INIT_BTC_FACTOR = 2;


    function developmentInit() external {
        // avoid altering the contract's global initialization state to prevent affecting other test cases.
        // If changes to the default configuration are necessary for specific test cases,
        // ensure they only apply to those cases
        // _reinitAssetFactor();
    }

    function _reinitAssetFactor() internal {
        address[] memory validators = IValidatorSet(VALIDATOR_CONTRACT_ADDR).getValidatorOps();
        uint256 validatorSize = validators.length;
        for (uint256 i = 0; i < validatorSize; ++i) {
            address validator = validators[i];
        }
        // init asset factor of asset state map
        uint256 assetLen = assets.length;
        for (uint256 i = 1; i < assetLen; i++) {
            stateMap[assets[i].agent].factor = 10000;
        }
    }
    
    function setOperators(address delegator, bool value) external {
        operators[delegator] = value;
    }
    

    function getDebts(address delegator) external view returns (NotePayable[] memory) {
        return debts[delegator].notes;
    }

    function getCandidateScoresMap(address candidate) external view returns (uint256[] memory) {
        return candidateScoresMap[candidate];
    }


    function setStateMapDiscount(address agent, uint256 value, uint256 value1) external {
        stateMap[agent] = AssetState(value, value1);
    }


    function initHybridScoreMock() external {
        _initializeFromPledgeAgent();
    }

//    receive() external payable {
//    }

    function coreAgentDistributeReward(address[] calldata validators, uint256[] calldata rewardList, uint256 round) external {
        IAgent(CORE_AGENT_ADDR).distributeReward(validators, rewardList, round);
    }

}
