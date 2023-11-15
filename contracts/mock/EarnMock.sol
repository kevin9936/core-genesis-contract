pragma solidity 0.8.4;

import "../Earn.sol";

contract EarnMock is Earn {
    function developmentInit() external {
    }

    function setContractAddress(address candidateHubAddress, address pledgeAgentAddress, address stCoreAddress) external {
        CANDIDATE_HUB = candidateHubAddress;
        PLEDGE_AGENT = pledgeAgentAddress;
        STCORE = stCoreAddress;
    }

    function getExchangeRate() external view returns (uint256) {
        return exchangeRate;
    }
    
    function setAfterTurnRoundClaimReward(bool claim) external {
        afterTurnRoundClaimReward = claim;
    }
    
}