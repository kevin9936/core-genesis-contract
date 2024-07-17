pragma solidity 0.8.4;

import "./BaseProxy.sol";

interface IPledgeAgent {
    function claimReward() external returns (uint256, bool);

    function claimBtcReward(bytes32[] calldata txidList) external returns (uint256, bool);

    function delegateCoin(address agent) external payable;

    function undelegateCoin(address agent) external;

    function undelegateCoin(address agent, uint256 amount) external;

    function transferCoin(address sourceAgent, address targetAgent) external;

    function transferCoin(address sourceAgent, address targetAgent, uint256 amount) external;

    function transferBtc(bytes32 txid, address targetAgent) external;

    function requiredCoinDeposit() external view returns (uint256);
}

contract ReentryPledgeAgentProxy is BaseProxy {
    event proxyDelegate(bool success, string data,address sender);
    event proxyClaim(bool success, string data, address sender);
    event proxyBtcClaim(bool success, string data);
    event proxyUndelegate(bool success, string data);
    event proxyTransferBtc(bool success, string data);
    event proxyUndelegatePartial(bool success, string data);

    constructor(address _pledgeAgent, address _stakeHub) BaseProxy(_pledgeAgent, _stakeHub) {}

    function delegateCoin(address agent) external payable {
        bytes memory payload = abi.encodeWithSignature("delegateCoin(address)", agent);
        (bool success, string memory _msg) = _call(payload);
        emit proxyDelegate(success, _msg,msg.sender);
    }

    function undelegateCoin(address agent) external payable {
        bytes memory payload = abi.encodeWithSignature("undelegateCoin(address)", agent);
        (bool success, string memory _msg) = _call(payload);
        emit proxyUndelegate(success, _msg);
    }

    function undelegateCoin(address agent, uint256 amount) external payable {
        bytes memory payload = abi.encodeWithSignature("undelegateCoin(address,uint256)", agent, amount);
        (bool success, string memory _msg) = _call(payload);
        emit proxyUndelegatePartial(success, _msg);
    }

    function transferCoin(address sourceAgent, address targetAgent) external payable {
        bytes memory payload = abi.encodeWithSignature("transferCoin(address,address)", sourceAgent, targetAgent);
        (bool success, string memory _msg) = _call(payload);
    }

    function transferCoin(address sourceAgent, address targetAgent, uint256 amount) external payable {
        bytes memory payload = abi.encodeWithSignature("transferCoin(address,address,uint256)", sourceAgent, targetAgent, amount);
        (bool success, string memory _msg) = _call(payload);
    }

    function transferBtc(bytes32 txid, address targetAgent) external {
        bytes memory payload = abi.encodeWithSignature("transferBtc(bytes32,address)", txid, targetAgent);
        (bool success, string memory _msg) = _call(payload);
        emit proxyTransferBtc(success, _msg);
    }

    function claimReward() external payable {
        bytes memory payload = abi.encodeWithSignature("claimReward()");
        (bool success, string memory _msg) = _callC(payload);
        emit proxyClaim(success, _msg, msg.sender);
    }

    function claimBtcReward(bytes32[] calldata txidList) external payable {
        bytes memory payload = abi.encodeWithSignature("claimBtcReward(bytes32[])", txidList);
        (bool success, string memory _msg) = _call(payload);
        emit proxyBtcClaim(success, _msg);
    }

}

contract DelegateReentry is ReentryPledgeAgentProxy {
    address public agent;
    uint256 public minDelegateAmount;

    constructor(address _pledgeAgentAddress, address _stakeHub) ReentryPledgeAgentProxy(_pledgeAgentAddress, _stakeHub) payable {
        minDelegateAmount = IPledgeAgent(impl).requiredCoinDeposit();
    }

    function setAgent(address _agent) external {
        agent = _agent;
    }

    receive() external payable {
        IPledgeAgent(impl).delegateCoin{value: address(this).balance}(agent);
    }
}


contract UndelegateReentry is ReentryPledgeAgentProxy {
    address public agent;

    constructor(address _pledgeAgentAddress, address _stakeHub) ReentryPledgeAgentProxy(_pledgeAgentAddress, _stakeHub) {}

    function setAgent(address _agent) external {
        agent = _agent;
    }

    receive() external payable {
        if (impl.balance > 0) {
            IPledgeAgent(impl).undelegateCoin(agent);
        }
    }
}


contract ClaimRewardReentry is ReentryPledgeAgentProxy {
    constructor(address _pledgeAgentAddress, address _stakeHub) ReentryPledgeAgentProxy(_pledgeAgentAddress, _stakeHub) {}
    receive() external payable {
        if (stakeHub.balance > 0) {
            IPledgeAgent(stakeHub).claimReward();
        }
        emit proxyClaim(true,'',msg.sender);
    }
}

contract ClaimBtcRewardReentry is ReentryPledgeAgentProxy {
    bytes32[]  public txidList;

    constructor(address _pledgeAgentAddress, address _stakeHub) ReentryPledgeAgentProxy(_pledgeAgentAddress, _stakeHub) {}

    function setTxidList(bytes32[] calldata _txid) external {
        delete txidList;
        txidList = new bytes32[](_txid.length);
        for (uint i = 0; i < _txid.length; i++) {
            txidList[i] = _txid[i];
        }
    }

    receive() external payable {
        IPledgeAgent(impl).claimBtcReward(txidList);
    }
}


contract TransferBtcReentry is ReentryPledgeAgentProxy {
    bytes32 public txid;
    address public targetAgent;
    constructor(address _pledgeAgentAddress, address _stakeHub) ReentryPledgeAgentProxy(_pledgeAgentAddress, _stakeHub) {}

    function setTxid(bytes32 _txid) external {
        txid = _txid;
    }

    function setTargetAgent(bytes32 _targetAgent) external {
        targetAgent = targetAgent;
    }

    receive() external payable {
        IPledgeAgent(impl).transferBtc(txid, targetAgent);
    }
}