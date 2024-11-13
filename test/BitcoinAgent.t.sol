// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.4;

import {Test, console} from "forge-std/Test.sol";
import {BitcoinAgent} from "../contracts/BitcoinAgent.sol";
import {PledgeAgent} from "../contracts/PledgeAgent.sol";
import {System} from "../contracts/System.sol";

contract BitcoinAgentTest is Test {
    BitcoinAgent public bitCoinAgent;
    PledgeAgent public pledgeAgent;
    System public system;

    function setUp() public {
        bitCoinAgent = new BitcoinAgent();
        pledgeAgent = new PledgeAgent();
        system = new System();
        bitCoinAgent.init();
        pledgeAgent.init();
    }

    function test_initializeFromPledgeAgent() public {
        address[] memory candidates = new address[](1) ;
        uint256[] memory amounts = new uint256[](1);
        vm.prank(address(4103));
        bitCoinAgent._initializeFromPledgeAgent(candidates, amounts);
//        assertEq(bitCoinAgent.candidateMap[candidates[0]].stakeAmount(), 1000);
    }
}
