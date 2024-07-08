pragma solidity 0.8.4;

import "../BitcoinAgent.sol";

contract BitcoinAgentMock is BitcoinAgent {
    uint256 public rewardAmountM;

    function developmentInit() external {
        minBtcValue = INIT_MIN_BTC_VALUE / 1000;
    }
    
     function setBtcStake(address btcStakeAddr,address btcLSTStakeAddr) external {
        btcStake = btcStakeAddr;
        btcLSTStake = btcLSTStakeAddr;
    }

}
