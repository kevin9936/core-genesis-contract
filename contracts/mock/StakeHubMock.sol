pragma solidity 0.8.4;

import "../StakeHub.sol";
import "../interface/IPledgeAgent.sol";

contract StakeHubMock is StakeHub {
    uint256 public rewardAmountM;

    uint256 public constant TEST_HASH_UNIT_CONVERSION = 10;
    uint256 public constant TEST_INIT_HASH_FACTOR = 50;
    uint256 public constant TEST_BTC_UNIT_CONVERSION = 5;
    uint256 public constant TEST_INIT_BTC_FACTOR = 2;


    function developmentInit() external {
        _reinitAssetFactor();
    }

    function _reinitAssetFactor() internal {

        // init HASHPOWER factor
        assets[1].factor = TEST_HASH_UNIT_CONVERSION * TEST_INIT_HASH_FACTOR;

        // init BTC factor
        assets[2].factor = TEST_BTC_UNIT_CONVERSION * TEST_INIT_BTC_FACTOR;

        // init candidate score
        address[] memory validators = IValidatorSet(VALIDATOR_CONTRACT_ADDR).getValidatorOps();
        uint256 validatorSize = validators.length;
        for (uint256 i = 0; i < validatorSize; ++i) {
            address validator = validators[i];
            uint256[] memory candidateAssetAmount = candidateAmountMap[validator];

            candidateScoreMap[validator] = candidateAssetAmount[0] * assets[0].factor + candidateAssetAmount[1] * assets[1].factor + candidateAssetAmount[2] * assets[2].factor;
        }

        // init asset factor of asset state map
        uint256 assetLen = assets.length;
        for (uint256 i = 1; i < assetLen; i++) {
            stateMap[assets[i].agent].factor = assets[i].factor;
        }
    }

    function setInitLpRates(uint32 value1, uint32 value01, uint32 value2, uint32 value02, uint32 value3, uint32 value03) external {
        grades.push(DualStakingGrade(value1, value01));
        grades.push(DualStakingGrade(value2, value02));
        grades.push(DualStakingGrade(value3, value03));
    }

    function setLpRates(uint32 value1, uint32 balue01) external {
        grades.push(DualStakingGrade(value1, balue01));
    }


    function setIsActive(uint256 value) external {
        gradeActive = value;
    }

    function popLpRates() external {
        delete grades;
    }

    function setCandidateAmountMap(address agent, uint256 value, uint256 value1, uint256 value2) external {
        candidateAmountMap[agent].push(value);
        candidateAmountMap[agent].push(value1);
        candidateAmountMap[agent].push(value2);
        candidateScoreMap[agent] = value + value1 * TEST_HASH_UNIT_CONVERSION * TEST_INIT_HASH_FACTOR + value2 * TEST_BTC_UNIT_CONVERSION * TEST_INIT_BTC_FACTOR;
    }

    function getDebts(address delegator) external view returns (NotePayable[] memory) {
        return debts[delegator].notes;
    }


    function setStateMapDiscount(address agent, uint256 value, uint256 value1, uint32 value2) external {
        stateMap[agent] = AssetState(value, value1, value2);
    }

    function setBtcPoolRate(uint32 value) external {
        uint32 Rate = 10000;
        uint32 coreRare = Rate - value;
        assets[2].bonusRate = value;
        assets[0].bonusRate = coreRare;
    }

    function initHybridScoreMock() external {
        // get validator set
        address[] memory validators = IValidatorSet(VALIDATOR_CONTRACT_ADDR).getValidatorOps();
        (bool success, bytes memory data) = PLEDGE_AGENT_ADDR.call(abi.encodeWithSignature("getStakeInfo(address[])", validators));
        require(success, "call PLEDGE_AGENT_ADDR.getStakeInfo 2 fail");
        (uint256[] memory cores, uint256[] memory hashs, uint256[] memory btcs) = abi.decode(data, (uint256[], uint256[], uint256[]));
        uint256 validatorSize = validators.length;
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
        uint32 initDiscount = 1e4;
        for (uint256 j = 0; j < 3; j++) {
            stateMap[assets[j].agent] = AssetState(totalAmounts[j], assets[j].factor, initDiscount);
        }

        (success, data) = CANDIDATE_HUB_ADDR.call(abi.encodeWithSignature("getCandidates()"));
        require(success, "call CANDIDATE_HUB.getCandidates fail");
        address[] memory candidates = abi.decode(data, (address[]));

        (success, data) = PLEDGE_AGENT_ADDR.call(abi.encodeWithSignature("moveCandidateData(address[])", candidates));
        require(success, "call PLEDGE_AGENT_ADDR.moveCandidateData fail");
    }

    function setBtcFactor(uint newBtcFactor) external {
        assets[2].factor = newBtcFactor;
    }

    function setPowerFactor(uint newPowerFactor) external {
        assets[1].factor = newPowerFactor;
    }

}
