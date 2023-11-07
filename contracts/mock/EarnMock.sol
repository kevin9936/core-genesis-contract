pragma solidity 0.8.4;

import "../Earn.sol";

contract EarnMock is Earn {
    function developmentInit() external {
        uint256 a = 0;
    }

    function setContractAddress(address candidateHubAddress, address pledgeAgentAddress, address stCoreAddress) external {
        CANDIDATE_HUB = candidateHubAddress;
        PLEDGE_AGENT = pledgeAgentAddress;
        STCORE = stCoreAddress;
    }
}