pragma solidity 0.8.4;

import "../BitcoinAgent.sol";

contract BitcoinAgentMock is BitcoinAgent {
    uint256 public rewardAmountM;

    function developmentInit() external {
//        minBtcValue = INIT_MIN_BTC_VALUE / 1000;
    }
    
     function setBtcStake(address btcStakeAddr,address btcLSTStakeAddr) external {
        BTC_STAKE_ADDR = btcStakeAddr;
        BTCLST_STAKE_ADDR = btcLSTStakeAddr;
    }
    
    
    function setCandidateMap(address agent, uint256 value, uint256 value1) external {
        candidateMap[agent] = StakeAmount(value,value1);
    }


}
