// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.4;

import {Test, console} from "forge-std/Test.sol";
import {System} from "../contracts/System.sol";
import {ValidatorSet} from "../contracts/ValidatorSet.sol";
import {SlashIndicator} from "../contracts/SlashIndicator.sol";
import {SystemReward} from "../contracts/SystemReward.sol";
import {BtcLightClient} from "../contracts/BtcLightClient.sol";
import {RelayerHub} from "../contracts/RelayerHub.sol";
import {CandidateHub} from "../contracts/CandidateHub.sol";
import {GovHub} from "../contracts/GovHub.sol";
import {PledgeAgent} from "../contracts/PledgeAgent.sol";
import {Burn} from "../contracts/Burn.sol";
import {Foundation} from "../contracts/Foundation.sol";
import {StakeHub} from "../contracts/StakeHub.sol";
import {CoreAgent} from "../contracts/CoreAgent.sol";
import {HashPowerAgent} from "../contracts/HashPowerAgent.sol";
import {BitcoinAgent} from "../contracts/BitcoinAgent.sol";
import {BitcoinStake} from "../contracts/BitcoinStake.sol";
import {BitcoinLSTStake} from "../contracts/BitcoinLSTStake.sol";
import {BitcoinLSTToken} from "../contracts/BitcoinLSTToken.sol";
import {Utils} from "./Utils.t.sol";

contract DelegatTest is Test, Utils {
    function test_DelegateCoin() public {
        address[] memory operates = new address[](3);
        address[] memory consensuses = new address[](3);
        for (uint256 i = 0; i < 3; i++) {
            address operateAddr = accountList[i];
            address consensus = consensusAddr[i];
            vm.prank(operateAddr);
            candidateHub.register{value: 10000 ether}(consensus, payable(operateAddr), 500);
            operates[i] = operateAddr;
            consensuses[i] = consensus;
        }
        manualDelegateCoin(operates[0], accountList[8], 100 ether);
        manualTurnRound();
        manualUndelegateCoin(operates[0], accountList[8], 50 ether);
        manualTransferCoin(operates[0], operates[1], accountList[8], 25 ether);
        manualTurnRound(consensuses);
        manualClaimReward(accountList[8]);
        manualTurnRound(consensuses);
        manualClaimReward(accountList[8]);
        bytes32 myData = 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef;
        uint32 lockTime = 1739435523;
        address candidate = operates[1];
        address delegator = accountList[3];
        uint64 amount = 3 * 10 ** 8;
        uint256 blockTimestamp = block.timestamp;
        bytes memory script = hex"0480db8767b17576a914574fdd26858c28ede5225a809f747c01fcc1f92a88ac";
        manualDelegateBtc(candidate, delegator,amount,lockTime, blockTimestamp, accountList[8]);
        manualTurnRound(consensuses);
        manualTurnRound(consensuses);
        manualClaimReward(accountList[3]);
        

    }

}

contract BurnTest is Test, Utils {
    event isR();

    function test_Burn111() public {
        vm.deal(address(this), 1000);
        vm.deal(address(burn), 4000);
        burn.burn{value: 1000}();


    }

    receive() external payable {
        emit isR();
        if (msg.value != 0) {
            burn.burn{value: 1000}();
        }
    }

}
