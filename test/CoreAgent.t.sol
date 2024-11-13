// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.4;

import {Test, console} from "forge-std/Test.sol";
import {CoreAgent} from "../contracts/CoreAgent.sol";
import {CandidateHub} from "../contracts/CandidateHub.sol";

contract CoreAgentTest is Test {
    CoreAgent public coreAgent;
    CandidateHub public candidateHub;

    error InactiveCandidate(address candidate);

    function setUp() public {
        coreAgent = new CoreAgent();
        candidateHub = new CandidateHub();
        coreAgent.init();
    }

    function test_Revert_delegateCoin1() public {
        vm.mockCall(
            candidateHub.CANDIDATE_HUB_ADDR(),
            abi.encodeWithSelector(candidateHub.canDelegate.selector, address(1)),
            abi.encode(0)
        );
        vm.expectRevert(
            abi.encodeWithSelector(InactiveCandidate.selector, address(1))
        );
        coreAgent.delegateCoin(address(1));
    }

    function test_Revert_delegateCoin2() public {
        vm.mockCall(
            candidateHub.CANDIDATE_HUB_ADDR(),
            abi.encodeWithSelector(candidateHub.canDelegate.selector, address(1)),
            abi.encode(1)
        );
        vm.expectRevert('delegate amount is too small');
        coreAgent.delegateCoin(address(1));
    }
}


contract CoreAgentTestDelegate is Test {
    CoreAgent public coreAgent;
    CandidateHub public candidateHub;

    error InactiveCandidate(address candidate);

    function setUp() public {
        coreAgent = new CoreAgent();
        candidateHub = new CandidateHub();
        coreAgent.init();
    }

    function test_Revert_delegateCoin3() public {
        vm.mockCall(
            candidateHub.CANDIDATE_HUB_ADDR(),
            abi.encodeWithSelector(candidateHub.canDelegate.selector, address(1)),
            abi.encode(0)
        );
        vm.expectRevert(
            abi.encodeWithSelector(InactiveCandidate.selector, address(1))
        );
        coreAgent.delegateCoin(address(1));
    }

    function test_Revert_delegateCoin4() public {
        vm.mockCall(
            candidateHub.CANDIDATE_HUB_ADDR(),
            abi.encodeWithSelector(candidateHub.canDelegate.selector, address(1)),
            abi.encode(1)
        );
        vm.expectRevert('delegate amount is too small');
        coreAgent.delegateCoin(address(1));
    }
}
