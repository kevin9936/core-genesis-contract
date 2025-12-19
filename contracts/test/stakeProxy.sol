// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;

contract delegateCoinProxy {
    address public pledgeAgent;
    address public stakeHub;
    bool public  receiveState;

    event delegate(bool success);
    event claim(bool allClaimed, address delegator, uint256 [] rewards);
    constructor(address pledgeAgentAddress, address stakeHubAddress) public {
        pledgeAgent = pledgeAgentAddress;
        stakeHub = stakeHubAddress;
    }
    function delegateCoin(address agent) external payable {
        bytes memory payload = abi.encodeWithSignature("delegateCoin(address)", agent);
        (bool success, bytes memory returnData) = pledgeAgent.call{value: msg.value}(payload);
        emit delegate(success);
    }

    function claimReward() external {
        bytes memory payload = abi.encodeWithSignature("claimReward()");
        (bool success, bytes memory returnData) = stakeHub.call(payload);
        require(success, "call to claimReward failed");
        (uint256[] memory rewards) = abi.decode(returnData, (uint256 []));
        emit claim(success, msg.sender, rewards);
    }

    function setReceiveState(bool state) external {
        receiveState = state;
    }

    receive() external payable {
        if (receiveState == false) {
            revert("refused");
        }
    }
}


contract callPledgeAgentAccount0 {
    receive() external payable {}
}
contract callPledgeAgentAccount1 {
    receive() external payable {}
}
contract callPledgeAgentAccount2 {
    receive() external payable {}
}
contract callPledgeAgentAccount3 {
    receive() external payable {}
}

contract refuseAccount {
    receive() external payable {
        revert("refused");
    }
}