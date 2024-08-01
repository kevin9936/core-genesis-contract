pragma solidity 0.8.4;

import "../BitcoinAgent.sol";
import {BitcoinLSTStake} from "../BitcoinLSTStake.sol";

contract BitcoinLSTStakeMock is BitcoinLSTStake {
    
    function developmentInit() external {
//        minBtcValue = INIT_MIN_BTC_VALUE / 1000;
    }


    
    function setInitRound(uint256 value) external {
        initRound = value;
    }
   function setRoundTag(uint256 value) external {
        roundTag = value;
    }



}
