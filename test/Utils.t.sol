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
import "./BTCUtils.sol";
import "../contracts/lib/BitcoinHelper.sol";

contract Utils is Test {
    ValidatorSet public newValidatorAgent;
    SlashIndicator public newSlashIndicator;
    SystemReward public newSystemReward;
    BtcLightClient public newBtcLightClient;
    RelayerHub public newRelayerHub;
    CandidateHub public newCandidateHub;
    GovHub public newGovHub;
    PledgeAgent public newPledgeAgent;
    Burn public newBurn;
    Foundation public newFoundation;
    StakeHub public newStakeHub;

    CoreAgent public newCoreAgent;
    HashPowerAgent public newHashPowerAgent;
    BitcoinAgent public newBitcoinAgent;
    BitcoinStake public newBitcoinStake;
    BitcoinLSTStake public newBitcoinLSTStake;
    BitcoinLSTToken public newBitcoinLSTToken;
    System public system;
    address[]public accountList;
    address[]public consensusAddr;

    ValidatorSet public validatorSet;
    SlashIndicator public slashIndicator;
    SystemReward public systemReward;
    BtcLightClient public btcLightClient;
    RelayerHub public relayerHub;
    CandidateHub public candidateHub;
    GovHub public govHub;
    PledgeAgent public pledgeAgent;
    Burn public burn;
    Foundation public foundation;
    StakeHub public stakeHub;
    CoreAgent public coreAgent;
    HashPowerAgent public hashPowerAgent;
    BitcoinAgent public bitcoinAgent;
    BitcoinStake public bitcoinStake;
    BitcoinLSTStake public bitcoinLSTStake;
    BitcoinLSTToken public bitcoinLSTToken;


    address public constant VALIDATOR_CONTRACT_ADDR = 0x0000000000000000000000000000000000001000;
    address public constant SLASH_CONTRACT_ADDR = 0x0000000000000000000000000000000000001001;
    address public constant SYSTEM_REWARD_ADDR = 0x0000000000000000000000000000000000001002;
    address public constant LIGHT_CLIENT_ADDR = 0x0000000000000000000000000000000000001003;
    address public constant RELAYER_HUB_ADDR = 0x0000000000000000000000000000000000001004;
    address public constant CANDIDATE_HUB_ADDR = 0x0000000000000000000000000000000000001005;
    address public constant GOV_HUB_ADDR = 0x0000000000000000000000000000000000001006;
    address public constant PLEDGE_AGENT_ADDR = 0x0000000000000000000000000000000000001007;
    address public constant BURN_ADDR = 0x0000000000000000000000000000000000001008;
    address public constant FOUNDATION_ADDR = 0x0000000000000000000000000000000000001009;
    address public constant STAKE_HUB_ADDR = 0x0000000000000000000000000000000000001010;

    address public constant CORE_AGENT_ADDR = 0x0000000000000000000000000000000000001011;
    address public constant HASH_AGENT_ADDR = 0x0000000000000000000000000000000000001012;
    address public constant BTC_AGENT_ADDR = 0x0000000000000000000000000000000000001013;
    address public constant BTC_STAKE_ADDR = 0x0000000000000000000000000000000000001014;
    address public constant BTCLST_STAKE_ADDR = 0x0000000000000000000000000000000000001015;
    address public constant BTCLST_TOKEN_ADDR = 0x0000000000000000000000000000000000010001;


    address public constant COIN_BASE_ADDR = 0xffffFFFfFFffffffffffffffFfFFFfffFFFfFFfE;
    uint256 public  blockTimeStamp = 1641070800;
    function initContract() public {
        vm.warp(blockTimeStamp);
        newValidatorAgent = new ValidatorSet();
        newSlashIndicator = new SlashIndicator();
        newSystemReward = new SystemReward();
        newBtcLightClient = new BtcLightClient();
        newRelayerHub = new RelayerHub();
        newCandidateHub = new CandidateHub();
        newGovHub = new GovHub();
        newPledgeAgent = new PledgeAgent();
        newBurn = new Burn();
        newFoundation = new Foundation();
        newStakeHub = new StakeHub();
        newCoreAgent = new CoreAgent();
        newHashPowerAgent = new HashPowerAgent();
        newBitcoinAgent = new BitcoinAgent();
        newBitcoinStake = new BitcoinStake();
        newBitcoinLSTStake = new BitcoinLSTStake();
        newBitcoinLSTToken = new BitcoinLSTToken();

        address[17] memory contractAddr = [
                        address(newValidatorAgent),
                        address(newSlashIndicator),
                        address(newSystemReward),
                        address(newBtcLightClient),
                        address(newRelayerHub),
                        address(newCandidateHub),
                        address(newGovHub),
                        address(newPledgeAgent),
                        address(newBurn),
                        address(newFoundation),
                        address(newStakeHub),
                        address(newCoreAgent),
                        address(newHashPowerAgent),
                        address(newBitcoinAgent),
                        address(newBitcoinStake),
                        address(newBitcoinLSTStake),
                        address(newBitcoinLSTToken)
            ];


        string [17] memory contractInit = [
                    'VALIDATOR_CONTRACT_ADDR',
                    'SLASH_CONTRACT_ADDR',
                    'SYSTEM_REWARD_ADDR',
                    'LIGHT_CLIENT_ADDR',
                    'RELAYER_HUB_ADDR',
                    'CANDIDATE_HUB_ADDR',
                    'GOV_HUB_ADDR',
                    'PLEDGE_AGENT_ADDR',
                    'BURN_ADDR',
                    'FOUNDATION_ADDR',
                    'STAKE_HUB_ADDR',
                    'CORE_AGENT_ADDR',
                    'HASH_AGENT_ADDR',
                    'BTC_AGENT_ADDR',
                    'BTC_STAKE_ADDR',
                    'BTCLST_STAKE_ADDR',
                    'BTCLST_TOKEN_ADDR'
            ];
        address [17] memory systemContractInit = [
                        address(0x0000000000000000000000000000000000001000),
                        address(0x0000000000000000000000000000000000001001),
                        address(0x0000000000000000000000000000000000001002),
                        address(0x0000000000000000000000000000000000001003),
                        address(0x0000000000000000000000000000000000001004),
                        address(0x0000000000000000000000000000000000001005),
                        address(0x0000000000000000000000000000000000001006),
                        address(0x0000000000000000000000000000000000001007),
                        address(0x0000000000000000000000000000000000001008),
                        address(0x0000000000000000000000000000000000001009),
                        address(0x0000000000000000000000000000000000001010),
                        address(0x0000000000000000000000000000000000001011),
                        address(0x0000000000000000000000000000000000001012),
                        address(0x0000000000000000000000000000000000001013),
                        address(0x0000000000000000000000000000000000001014),
                        address(0x0000000000000000000000000000000000001015),
                        address(0x0000000000000000000000000000000000010001)
            ];
        string memory selector;
        address contractAddress;
        for (uint256 j = 0; j < 17; j++) {
            contractAddress = contractAddr[j];
            bytes memory code = address(contractAddress).code;
            address targetAddr = systemContractInit[j];
            vm.etch(targetAddr, code);
        }
        validatorSet = ValidatorSet(payable(VALIDATOR_CONTRACT_ADDR));
        slashIndicator = SlashIndicator(SLASH_CONTRACT_ADDR);
        systemReward = SystemReward(payable(SYSTEM_REWARD_ADDR));
        btcLightClient = BtcLightClient(LIGHT_CLIENT_ADDR);
        relayerHub = RelayerHub(RELAYER_HUB_ADDR);
        candidateHub = CandidateHub(CANDIDATE_HUB_ADDR);
        govHub = GovHub(payable(GOV_HUB_ADDR));
        pledgeAgent = PledgeAgent(payable(PLEDGE_AGENT_ADDR));
        burn = Burn(BURN_ADDR);
        foundation = Foundation(payable(FOUNDATION_ADDR));
        stakeHub = StakeHub(payable(STAKE_HUB_ADDR));
        coreAgent = CoreAgent(CORE_AGENT_ADDR);
        hashPowerAgent = HashPowerAgent(HASH_AGENT_ADDR);
        bitcoinAgent = BitcoinAgent(BTC_AGENT_ADDR);
        bitcoinStake = BitcoinStake(BTC_STAKE_ADDR);
        bitcoinLSTStake = BitcoinLSTStake(BTCLST_STAKE_ADDR);
        bitcoinLSTToken = BitcoinLSTToken(BTCLST_TOKEN_ADDR);

        candidateHub.init();
        validatorSet.init();
        systemReward.init();
        slashIndicator.init();
        btcLightClient.init();
        relayerHub.init();
        govHub.init();
        pledgeAgent.init();
        burn.init();
        coreAgent.init();
        hashPowerAgent.init();
        bitcoinAgent.init();
        stakeHub.init();
        bitcoinLSTToken.init();
        bitcoinStake.init();
        bitcoinLSTStake.init();
    }

    function setUp() public {
        initContract();
        for (uint256 i = 1; i < 15; i++) {
            accountList.push(vm.addr(i));
            consensusAddr.push(vm.addr(i * 100));
            vm.deal(vm.addr(i), 10000000 ether);
        }
        // set coinbase address
        vm.coinbase(COIN_BASE_ADDR);
        vm.deal(COIN_BASE_ADDR, 20000000 ether);
        // 
        vm.deal(address(validatorSet), 10000000 ether);


    }


    function manualTurnRound() public {
        address[] memory addresses = new address[](1);
        uint256 turnRoundCount = 1;
        _manualTurnRound(addresses, turnRoundCount);
    }

    function manualTurnRound(address [] memory consensuses) public {
        uint256 turnRoundCount = 1;
        _manualTurnRound(consensuses, turnRoundCount);
    }

    function manualTurnRound(address [] memory consensuses, uint256 turnRoundCount) public {
        _manualTurnRound(consensuses, turnRoundCount);
    }

    function _manualTurnRound(address [] memory consensuses, uint256 turnRoundCount) internal {
        vm.startPrank(COIN_BASE_ADDR);
        for (uint256 j = 0; j < turnRoundCount; j++) {
            assertEq(blockTimeStamp, vm.getBlockTimestamp());
            blockTimeStamp = blockTimeStamp + 86400;
            for (uint256 j = 0; j < consensuses.length; j++) {
                validatorSet.deposit{value: 1 ether}(consensuses[j]);
            }
            vm.warp(blockTimeStamp);
            candidateHub.turnRound();
        }
        vm.stopPrank();
    }

    // stake Coin 
    function manualDelegateCoin(address candidate, address account, uint256 amount) public {
        vm.prank(account);
        coreAgent.delegateCoin{value: amount}(candidate);
    }

    function manualUndelegateCoin(address candidate, address account, uint256 amount) public {
        vm.prank(account);
        coreAgent.undelegateCoin(candidate, amount);
    }

    function manualTransferCoin(address sourceCandidate, address targetCandidate, address account, uint256 amount) public {
        vm.prank(account);
        coreAgent.transferCoin(sourceCandidate, targetCandidate, amount);
    }
    // claim reward (coin & power & btc)
    function manualClaimReward(address account) public {
        vm.prank(account);
        stakeHub.claimReward();
    }

    function mockDelegateBtc(bytes32 txId, address relay, uint256 blockTimestamp) internal {
        uint256 [] memory arry;
        vm.mockCall(
            address(btcLightClient),
            abi.encodeWithSelector(btcLightClient.checkTxProofAndGetTime.selector, txId, 1000, 6, arry, 20),
            abi.encode(1, blockTimestamp)
        );
        vm.mockCall(
            address(relayerHub),
            abi.encodeWithSelector(relayerHub.isRelayer.selector, relay),
            abi.encode(1)
        );
        vm.prank(relay);
    }
    // stake btc
    function manualDelegateBtc(address candidate, address delegator, uint64 btcAmount, uint32 lockTime, uint256 blockTimestamp, address relay) public {
        bytes32 []  memory nodes;
        bytes memory hexLockTime = BTCUtils.convertHexStringToBytes(BTCUtils.uintToHexNoPadding(lockTime));
        bytes memory script = abi.encodePacked(hex"04", hexLockTime, hex"b17576a914574fdd26858c28ede5225a809f747c01fcc1f92a88ac");
        bytes memory concatenatedHex = BTCUtils.calculateOpReturn(candidate, delegator, btcAmount, script);
        mockDelegateBtc(BTCUtils.calculateTxId(concatenatedHex), relay, blockTimestamp);
        bitcoinStake.delegate(concatenatedHex, 1000, nodes, 20, script);
    }
}
