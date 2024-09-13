import time

import pytest
from web3 import Web3
import brownie
from brownie import *
from .common import register_candidate, turn_round, stake_hub_claim_reward, get_current_round, set_round_tag
from .delegate import *
from .utils import get_tracker, random_address, expect_event, update_system_contract_address
from .calc_reward import *

MIN_INIT_DELEGATE_VALUE = 0
BLOCK_REWARD = 0
TOTAL_REWARD = 0
COIN_REWARD = 0
ONE_ETHER = Web3.to_wei(1, 'ether')
TX_FEE = 100


@pytest.fixture(scope="module", autouse=True)
def deposit_for_reward(validator_set):
    accounts[-12].transfer(validator_set.address, Web3.to_wei(100000, 'ether'))


@pytest.fixture(scope="module", autouse=True)
def set_min_init_delegate_value(min_init_delegate_value):
    global MIN_INIT_DELEGATE_VALUE
    MIN_INIT_DELEGATE_VALUE = min_init_delegate_value


@pytest.fixture(scope="module", autouse=True)
def set_block_reward(validator_set, pledge_agent, stake_hub, btc_stake):
    global BLOCK_REWARD, TOTAL_REWARD
    global COIN_REWARD, PLEDGE_AGENT, STAKE_HUB, BTC_STAKE
    block_reward = validator_set.blockReward()
    block_reward_incentive_percent = validator_set.blockRewardIncentivePercent()
    total_block_reward = block_reward + TX_FEE
    BLOCK_REWARD = total_block_reward * ((100 - block_reward_incentive_percent) / 100)
    TOTAL_REWARD = BLOCK_REWARD // 2
    COIN_REWARD = TOTAL_REWARD * HardCap.CORE_HARD_CAP // HardCap.SUM_HARD_CAP
    PLEDGE_AGENT = pledge_agent
    STAKE_HUB = stake_hub
    BTC_STAKE = btc_stake


@pytest.fixture()
def set_candidate():
    operators = []
    consensuses = []
    for operator in accounts[5:8]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    return operators, consensuses


def test_reinit(pledge_agent):
    with brownie.reverts("the contract already init"):
        pledge_agent.init()


@pytest.mark.parametrize("store_old_data", [True, False])
def test_delegate_coin(pledge_agent, set_candidate, store_old_data: bool):
    operators, consensuses = set_candidate
    if store_old_data:
        pledge_agent.delegateCoinOld(operators[0], {"value": MIN_INIT_DELEGATE_VALUE})
        __old_turn_round()
        __old_turn_round(consensuses)
        tx = pledge_agent.delegateCoin(operators[0], {"value": MIN_INIT_DELEGATE_VALUE})
        assert 'delegatedCoin' in tx.events
        tx = pledge_agent.delegateCoin(operators[0], {"value": MIN_INIT_DELEGATE_VALUE})
        assert 'delegatedCoin' in tx.events
    else:
        tx = pledge_agent.delegateCoin(operators[0], {"value": web3.to_wei(1, 'ether')})
        assert 'delegatedCoin' in tx.events


@pytest.mark.parametrize("operate", ['delegate', 'undelegate', 'transfer', 'claim'])
def test_reentry_stake_hub_claim(pledge_agent, stake_hub, set_candidate, validator_set, operate):
    operators, consensuses = set_candidate
    reentry_ = ClaimRewardReentry.deploy(pledge_agent.address, stake_hub, {'from': accounts[0]})
    accounts[2].transfer(reentry_, ONE_ETHER)
    accounts[2].transfer(stake_hub, ONE_ETHER)
    old_delegate_coin_success(operators[0], reentry_, MIN_INIT_DELEGATE_VALUE)
    old_turn_round(consensuses, round_count=2)
    __init_hybrid_score_mock()
    if operate == 'delegate':
        tx = reentry_.delegateCoin(operators[0], {'value': MIN_INIT_DELEGATE_VALUE})
    elif operate == 'undelegate':
        tx = reentry_.undelegateCoin(operators[0])
    elif operate == 'transfer':
        tx = reentry_.transferCoin(operators[0], operators[1])
    else:
        tx = reentry_.claimReward([operators[0]])
    assert tx.events['claimedReward']['amount'] == TOTAL_REWARD
    assert len(tx.events['claimedReward']) == 1


@pytest.mark.parametrize("operate", ['delegate', 'undelegate', 'transfer', 'claim'])
def test_reentry_pledge_agent_claim(pledge_agent, stake_hub, set_candidate, validator_set, operate):
    operators, consensuses = set_candidate
    reentry_ = OldClaimRewardReentry.deploy(pledge_agent.address, stake_hub, {'from': accounts[0]})
    accounts[2].transfer(reentry_, ONE_ETHER)
    accounts[2].transfer(pledge_agent, ONE_ETHER)
    old_delegate_coin_success(operators[0], reentry_, MIN_INIT_DELEGATE_VALUE)
    old_turn_round(consensuses, round_count=2)
    __init_hybrid_score_mock()
    reentry_.setAgents(operators)
    after = reentry_.balance()
    amount = 0
    if operate == 'delegate':
        tx = reentry_.delegateCoin(operators[0], {'value': MIN_INIT_DELEGATE_VALUE})
        assert tx.events['proxyDelegate']['success'] is False
        amount = MIN_INIT_DELEGATE_VALUE
    elif operate == 'undelegate':
        tx = reentry_.undelegateCoin(operators[0])
        assert tx.events['proxyUndelegate']['success'] is False
    elif operate == 'transfer':
        tx = reentry_.transferCoin(operators[0], operators[1])
        assert len(tx.events) == 0
    else:
        tx = reentry_.claimReward([operators[0]])
        assert len(tx.events) == 0
    assert reentry_.balance() == after + amount


@pytest.mark.parametrize("operate", ['delegate', 'undelegate', 'transfer'])
def test_auto_issue_historical_rewards(pledge_agent, set_candidate, core_agent, operate):
    old_turn_round()
    operators, consensuses = set_candidate
    pledge_agent.delegateCoinOld(operators[0], {"value": MIN_INIT_DELEGATE_VALUE})
    __old_turn_round()
    __old_turn_round(consensuses)
    __init_hybrid_score_mock()
    if operate == 'delegate':
        tx = old_delegate_coin_success(operators[0], accounts[0], MIN_INIT_DELEGATE_VALUE, False)
    elif operate == 'undelegate':
        tx = old_undelegate_coin_success(operators[0], accounts[0], MIN_INIT_DELEGATE_VALUE, False)
    else:
        tx = old_transfer_coin_success(operators[0], operators[1], accounts[0], MIN_INIT_DELEGATE_VALUE, False)
    assert tx.events['claimedReward']['amount'] == TOTAL_REWARD


@pytest.mark.parametrize("is_validator", [True, False])
@pytest.mark.parametrize("partial", [True, False])
def test_undelegate_coin(pledge_agent, candidate_hub, is_validator: bool, partial: bool):
    operators = accounts[1:3]
    consensus = []
    for operator in operators:
        consensus.append(register_candidate(operator=operator))
        pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE * 2})
    __old_turn_round()
    __old_turn_round(consensus)
    __init_hybrid_score_mock()
    turn_round(round_count=2)

    undelegate_amount = MIN_INIT_DELEGATE_VALUE if partial else 0
    if is_validator:
        pledge_agent.undelegateCoin(operators[0], undelegate_amount)
        if partial:
            tx = pledge_agent.undelegateCoin(operators[0], undelegate_amount)
            assert 'undelegatedCoin' in tx.events
    else:
        candidate_hub.refuseDelegate({'from': operators[0]})
        turn_round()
        candidate_hub.unregister({'from': operators[0]})
        turn_round()
        pledge_agent.undelegateCoin(operators[0], undelegate_amount)
        if partial:
            tx = pledge_agent.undelegateCoin(operators[0], undelegate_amount)
            assert 'undelegatedCoin' in tx.events


@pytest.mark.parametrize("is_validator", [True, False])
@pytest.mark.parametrize("partial", [True, False])
def test_transfer_coin(pledge_agent, candidate_hub, is_validator: bool, partial: bool):
    operators = accounts[1:3]
    consensus = []
    for operator in operators:
        consensus.append(register_candidate(operator=operator))
        pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE * 2})
    __old_turn_round()
    __old_turn_round(consensus)
    __init_hybrid_score_mock()
    turn_round(round_count=2)

    transfer_amount = MIN_INIT_DELEGATE_VALUE if partial else 0
    if is_validator:
        tx = pledge_agent.transferCoin(operators[0], operators[1], transfer_amount)
        assert 'transferredCoin' in tx.events

        if partial:
            tx = pledge_agent.transferCoin(operators[0], operators[1], transfer_amount)
            assert 'transferredCoin' in tx.events
    else:
        candidate_hub.refuseDelegate({'from': operators[0]})
        turn_round()
        candidate_hub.unregister({'from': operators[0]})
        turn_round()
        tx = pledge_agent.transferCoin(operators[0], operators[1], transfer_amount)
        assert 'transferredCoin' in tx.events

        if partial:
            tx = pledge_agent.transferCoin(operators[0], operators[1], transfer_amount)
            assert 'transferredCoin' in tx.events


@pytest.mark.parametrize("agents_type", ["empty", "all", "partial", "none"])
def test_claim_reward(pledge_agent, candidate_hub, agents_type: str):
    operators = accounts[1:4]
    consensus = []
    for operator in operators:
        consensus.append(register_candidate(operator=operator))
        pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    __old_turn_round()
    __old_turn_round(consensus)
    __init_hybrid_score_mock()
    turn_round(round_count=2)
    actual_reward = 0
    event_length = 0
    if agents_type == "empty":
        tx = pledge_agent.claimReward([])
        assert len(tx.events) == 0
    elif agents_type == "all":
        tx = pledge_agent.claimReward(operators)
        actual_reward = TOTAL_REWARD * 3
        event_length = 1
    elif agents_type == "none":
        tx = pledge_agent.claimReward([random_address()])
        assert len(tx.events) == 0
    else:
        event_length = 1
        tx = pledge_agent.claimReward(operators[:2] + [random_address()])
        actual_reward = TOTAL_REWARD * 2
    if event_length == 1:
        assert tx.events['claimedReward']['amount'] == actual_reward


@pytest.mark.parametrize("agents_type", ["empty", "all", "partial", "none"])
def test_calculate_reward(pledge_agent, candidate_hub, agents_type: str):
    operators = accounts[1:4]
    consensus = []
    for operator in operators:
        consensus.append(register_candidate(operator=operator))
        pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    __old_turn_round()
    __old_turn_round(consensus)
    __init_hybrid_score_mock()
    turn_round(round_count=2)
    actual_reward = 0
    calc_reward = 0
    if agents_type == "empty":
        calc_reward = pledge_agent.calculateReward([], accounts[0])
    elif agents_type == "all":
        calc_reward = pledge_agent.calculateReward(operators, accounts[0])
        actual_reward = TOTAL_REWARD * 3
    elif agents_type == "none":
        calc_reward = pledge_agent.calculateReward([random_address()], accounts[0])
    elif agents_type == "partial":
        calc_reward = pledge_agent.calculateReward(operators[:2] + [random_address()], accounts[0])
        actual_reward = TOTAL_REWARD * 2
    assert calc_reward.return_value == actual_reward


@pytest.mark.parametrize("operate", [
    ['undelegate', 'delegate'],
    ['delegate', 'undelegate'],
    ['delegate', 'transfer'],
    ['transfer', 'undelegate'],
    ['delegate', 'delegate', 'transfer'],
    ['delegate', 'delegate', 'undelegate'],
    ['undelegate', 'transfer', 'delegate'],
    ['undelegate', 'undelegate', 'delegate'],
    ["delegate", "undelegate", "transfer"],
    ['transfer', 'undelegate', 'delegate'],
    ['undelegate', 'transfer', 'delegate'],
    ['delegate', 'delegate', 'undelegate', 'undelegate'],
    ['undelegate', 'delegate', 'transfer', 'transfer'],
    ['transfer', 'transfer', 'delegate', 'undelegate']
])
def test_calculate_reward_withdraw_transfer_reward(pledge_agent, set_candidate, operate):
    operators, consensus = set_candidate
    for index, op in enumerate(operators):
        old_delegate_coin_success(op, accounts[0], MIN_INIT_DELEGATE_VALUE * 2)
    __old_turn_round()
    total_undelegate_amount = 0
    delegate_count = []
    for index, o in enumerate(operate):
        if o == 'delegate':
            tx = old_delegate_coin_success(operators[0], accounts[0], MIN_INIT_DELEGATE_VALUE)
            assert 'delegatedCoinOld' in tx.events
            delegate_count.append(index)
        elif o == 'undelegate':
            if len(delegate_count) == 0:
                total_undelegate_amount += MIN_INIT_DELEGATE_VALUE
            else:
                delegate_count.pop()
            tx = old_undelegate_coin_success(operators[0], accounts[0], MIN_INIT_DELEGATE_VALUE)
            assert 'undelegatedCoinOld' in tx.events
        elif o == 'transfer':
            tx = old_transfer_coin_success(operators[0], operators[1], accounts[0], MIN_INIT_DELEGATE_VALUE)
            assert 'transferredCoinOld' in tx.events
    __old_turn_round(consensus)
    __init_hybrid_score_mock()
    debt_reward = (TOTAL_REWARD * total_undelegate_amount // (MIN_INIT_DELEGATE_VALUE * 2))
    calc_reward = pledge_agent.calculateReward(operators, accounts[0])
    assert calc_reward.return_value == TOTAL_REWARD * 3 - debt_reward


def test_claim_btc_reward(pledge_agent, btc_stake):
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    __old_turn_round()

    tx_id = "88c233d8d6980d2c486a055c804544faa8de93eadc4a00d5bd075d19f3190b4d"
    btc_value = 1000000
    agent = operator
    delegator = accounts[0]
    script = "0x1234"
    lock_time = int(time.time()) + 3600
    fee = 0
    pledge_agent.delegateBtcMock(tx_id, btc_value, agent, delegator, script, lock_time, fee)
    __old_turn_round()
    __old_turn_round([consensus])
    __init_hybrid_score_mock()
    tx = pledge_agent.claimBtcReward([tx_id])
    expect_event(tx, "claimedReward")


@pytest.mark.parametrize("success", [True, False])
def test_move_btc_data_then_claim_btc_reward(pledge_agent, btc_stake, success):
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    __old_turn_round()
    tx_id = "88c233d8d6980d2c486a055c804544faa8de93eadc4a00d5bd075d19f3190b4d"
    btc_value = 1000000
    agent = operator
    delegator = accounts[0]
    script = "0x1234"
    lock_time = int(time.time()) + 3600
    fee = 0
    pledge_agent.delegateBtcMock(tx_id, btc_value, agent, delegator, script, lock_time, fee)
    __old_turn_round()
    __old_turn_round([consensus])
    __init_hybrid_score_mock()
    tx_ids = []
    if success:
        tx_ids.append(tx_id)
        __move_btc_data([tx_id])
        with brownie.reverts("btc tx not found"):
            pledge_agent.claimBtcReward(tx_ids)
    else:
        tx = pledge_agent.claimBtcReward(tx_ids)
        assert len(tx.events) == 0


def test_only_btc_stake_can_call(pledge_agent, btc_stake):
    with brownie.reverts("the msg sender must be bitcoin stake contract"):
        pledge_agent.moveBtcData(random_btc_tx_id(), {'from': accounts[0]})


def test_move_btc_data(pledge_agent, btc_stake):
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    __old_turn_round()
    tx_id = "88c233d8d6980d2c486a055c804544faa8de93eadc4a00d5bd075d19f3190b4d"
    btc_value = 1000000
    agent = operator
    delegator = accounts[0]
    script = "0x1234"
    lock_time = int(time.time()) + 3600
    fee = 0
    pledge_agent.delegateBtcMock(tx_id, btc_value, agent, delegator, script, lock_time, fee)
    __old_turn_round()
    __old_turn_round([consensus])
    update_system_contract_address(pledge_agent, btc_stake=accounts[0])
    candidate, delegator, amount, round, lockTime = pledge_agent.moveBtcData(tx_id, {'from': accounts[0]}).return_value
    assert candidate == agent
    assert delegator == accounts[0]
    assert amount == btc_value
    assert lock_time // Utils.ROUND_INTERVAL * Utils.ROUND_INTERVAL == lockTime
    assert round == get_current_round() - 1
    assert pledge_agent.rewardMap(delegator) == TOTAL_REWARD // 2 * 2


def test_tx_id_not_found(pledge_agent, btc_stake):
    tx_id = random_btc_tx_id()
    update_system_contract_address(pledge_agent, btc_stake=accounts[0])
    candidate, delegator, amount, round, lock_time = pledge_agent.moveBtcData(tx_id, {'from': accounts[0]}).return_value
    assert candidate == delegator == ZERO_ADDRESS
    assert amount == round == lock_time == 0


def test_multiple_txids_end_round(pledge_agent, btc_stake, set_candidate):
    operators, consensuses = set_candidate
    pledge_agent.delegateCoinOld(operators[0], {"value": MIN_INIT_DELEGATE_VALUE})
    lock_time = int(time.time()) + 3600
    set_round_tag(lock_time // Utils.ROUND_INTERVAL - 3)
    __old_turn_round()
    round_tag = get_current_round()
    btc_value = 1000000
    script = "0x1234"
    fee = 0
    tx_ids0 = []
    tx_ids1 = []
    for index, op in enumerate(operators):
        tx_id0 = random_btc_tx_id()
        tx_id1 = random_btc_tx_id()
        pledge_agent.delegateBtcMock(tx_id0, btc_value + index, op, accounts[0], script, lock_time, fee)
        pledge_agent.delegateBtcMock(tx_id1, btc_value + index, op, accounts[1], script, lock_time, fee)
        tx_ids0.append(tx_id0)
        tx_ids1.append(tx_id1)
    __old_turn_round()
    assert pledge_agent.getAgent2valueMap(round_tag + 2, operators[0]) == btc_value * 2
    assert len(pledge_agent.getAgentAddrList(round_tag + 2)) == 3
    update_system_contract_address(pledge_agent, btc_stake=accounts[0])
    candidate, delegator, amount, _, _ = pledge_agent.moveBtcData(tx_ids0[0], {'from': accounts[0]}).return_value
    assert pledge_agent.getAgent2valueMap(round_tag + 2, operators[0]) == btc_value
    assert len(pledge_agent.getAgentAddrList(round_tag + 2)) == 3
    candidate, delegator, amount, round, _ = pledge_agent.moveBtcData(tx_ids1[0], {'from': accounts[0]}).return_value
    assert pledge_agent.getAgent2valueMap(round_tag + 2, operators[0]) == 0
    assert len(pledge_agent.getAgentAddrList(round_tag + 2)) == 2


def test_move_candidate_data(pledge_agent, core_agent, btc_stake, btc_agent, candidate_hub):
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE})

    tx_id = "88c233d8d6980d2c486a055c804544faa8de93eadc4a00d5bd075d19f3190b4d"
    btc_value = 1000000
    agent = operator
    delegator = accounts[0]
    script = "0x1234"
    lock_time = int(time.time()) + 3600
    fee = 0
    pledge_agent.delegateBtcMock(tx_id, btc_value, agent, delegator, script, lock_time, fee)

    __old_turn_round()
    assert operator in candidate_hub.getCandidates()
    __old_turn_round([consensus])

    pledge_agent.moveCandidateData([operator])
    agent = pledge_agent.agentsMap(operator)
    assert agent[-1] is True

    candidate_in_core_agent = core_agent.candidateMap(operator)
    assert candidate_in_core_agent[0] == MIN_INIT_DELEGATE_VALUE
    assert candidate_in_core_agent[1] == MIN_INIT_DELEGATE_VALUE

    candidate_in_btc_stake = btc_stake.candidateMap(operator)
    assert candidate_in_btc_stake[0] == btc_value
    assert candidate_in_btc_stake[1] == btc_value

    candidate_in_btc_agent = btc_agent.candidateMap(operator)
    assert candidate_in_btc_agent[1] == btc_value


def test_move_core_data(pledge_agent, core_agent):
    operator = accounts[1]
    operator2 = accounts[2]
    consensus = register_candidate(operator=operator)
    register_candidate(operator=operator2)
    pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE * 2})
    pledge_agent.delegateCoinOld(operator2, {"value": MIN_INIT_DELEGATE_VALUE})
    __old_turn_round()
    __old_turn_round([consensus])
    pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    pledge_agent.transferCoinOld(operator, operator2, MIN_INIT_DELEGATE_VALUE * 2)

    __init_hybrid_score_mock()
    turn_round(round_count=2)

    pledge_agent.moveCOREData(operator, accounts[0])

    delegator_info_in_core_agent = core_agent.getDelegator(operator, accounts[0])
    _staked_amount, _realtime_amount, _, _transferred_amount = delegator_info_in_core_agent
    assert _staked_amount == MIN_INIT_DELEGATE_VALUE
    assert _realtime_amount == MIN_INIT_DELEGATE_VALUE
    assert _transferred_amount == 0


def test_get_stake_info(pledge_agent):
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE})

    tx_id = "88c233d8d6980d2c486a055c804544faa8de93eadc4a00d5bd075d19f3190b4d"
    btc_value = 1000000
    agent = operator
    delegator = accounts[0]
    script = "0x1234"
    lock_time = int(time.time()) + 3600
    fee = 0
    pledge_agent.delegateBtcMock(tx_id, btc_value, agent, delegator, script, lock_time, fee)

    __old_turn_round()
    __old_turn_round([consensus])

    stake_info = pledge_agent.getStakeInfo([operator])
    assert stake_info[0][0] == MIN_INIT_DELEGATE_VALUE
    assert stake_info[2][0] == btc_value


@pytest.mark.parametrize("operate", ['delegate', 'undelegate', 'transfer', 'claim'])
def test_move2_core_agent_execution_success(pledge_agent, validator_set, stake_hub, core_agent, operate):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    operators, consensuses = __register_candidates(accounts[2:4])
    __old_turn_round()
    __old_delegate_coin(operators[0], accounts[0], MIN_INIT_DELEGATE_VALUE * 5)
    __old_delegate_coin(operators[1], accounts[1])
    __check_old_delegate_info(operators[0], accounts[0], {
        'deposit': 0,
        'newDeposit': MIN_INIT_DELEGATE_VALUE * 5,
        'changeRound': get_current_round(),
        'rewardIndex': 1,
        'transferOutDeposit': 0,
        'transferInDeposit': 0,
    })
    __old_turn_round()
    __init_hybrid_score_mock()
    real_amount = delegate_amount
    transferred_amount = 0
    change_round = 1
    if operate == 'delegate':
        __old_delegate_coin(operators[0], accounts[0], old=False)
        staked_amount = delegate_amount
        real_amount = MIN_INIT_DELEGATE_VALUE * 6
    elif operate == 'undelegate':
        turn_round()
        tx = __old_undelegate_coin(operators[0], accounts[0], MIN_INIT_DELEGATE_VALUE, old=False)
        assert 'undelegatedCoin' in tx.events
        staked_amount = delegate_amount - MIN_INIT_DELEGATE_VALUE
        real_amount = staked_amount
        change_round = get_current_round()
    elif operate == 'transfer':
        turn_round()
        tx = __old_transfer_coin(operators[0], operators[1], accounts[0], MIN_INIT_DELEGATE_VALUE, old=False)
        assert 'transferredCoin' in tx.events
        staked_amount = delegate_amount - MIN_INIT_DELEGATE_VALUE
        real_amount = staked_amount
        change_round = get_current_round()
        transferred_amount = MIN_INIT_DELEGATE_VALUE
    else:
        # core agent init roundTag - 1
        staked_amount = MIN_INIT_DELEGATE_VALUE * 5
        change_round = 0
        __old_claim_reward(operators)

    __check_old_delegate_info(operators[0], accounts[0], {
        'deposit': 0,
        'newDeposit': 0,
        'changeRound': 0,
        'rewardIndex': 0,
        'transferOutDeposit': 0,
        'transferInDeposit': 0,

    })
    __check_delegate_info(operators[0], accounts[0], {
        'stakedAmount': staked_amount,
        'realtimeAmount': real_amount,
        'changeRound': change_round,
        'transferredAmount': transferred_amount
    })


def test_init_hybrid_score_success():
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    operators, consensuses = __register_candidates(accounts[2:4])
    __old_turn_round()
    candidate_size = 3
    for i in range(candidate_size - 1):
        __old_delegate_coin(operators[i], accounts[i], MIN_INIT_DELEGATE_VALUE * 5 + i)
    __old_turn_round()
    operators1, consensuses1 = __register_candidates(accounts[4:5])
    operators.append(operators1[0])
    consensuses.append(consensuses1[0])
    __old_delegate_coin(operators[2], accounts[2], MIN_INIT_DELEGATE_VALUE * 5 + 2)
    for i in range(candidate_size):
        coin = delegate_amount + i
        if operators[i] == operators[-1]:
            coin = 0
        __check_old_agent_map_info(operators[i], {
            'totalDeposit': delegate_amount + i,
            'power': 0,
            'coin': coin,
            'btc': 0,
            'totalBtc': 0,
            'moved': False,
        })
    __init_hybrid_score_mock()
    for i in range(candidate_size):
        core_amount = delegate_amount + i
        if operators[i] == operators[-1]:
            core_amount = 0
        __check_candidate_amount_map_info(operators[i], [core_amount, core_amount, 0, 0])


def test_move_agent_success(pledge_agent, validator_set, stake_hub, core_agent):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    operators, consensuses = __register_candidates(accounts[2:4])
    __old_turn_round()
    candidate_size = 2
    for i in range(candidate_size):
        __old_delegate_coin(operators[i], accounts[i], delegate_amount + i)
        __get_old_delegator_info(operators[i], accounts[i])
    __old_turn_round()
    for i in range(candidate_size):
        __check_old_agent_map_info(operators[i], {
            'totalDeposit': delegate_amount + i,
            'coin': delegate_amount + i,
            'moved': False,
        })
    pledge_agent.moveCandidateData(operators)
    for i in range(candidate_size):
        __check_candidate_map_info(operators[i], {
            'amount': delegate_amount + i,
            'realtimeAmount': delegate_amount + i
        })
        __check_old_agent_map_info(operators[i], {
            # because the contract also has a staked core
            'totalDeposit': delegate_amount + i,
            'coin': 0,
            'moved': True,
        })


@pytest.mark.parametrize("claim", ['old', 'new'])
def test_migration_scenario_1(pledge_agent, validator_set, stake_hub, claim):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    operators, consensuses = __register_candidates(accounts[2:4])
    __old_turn_round()
    candidate_size = 2
    for i in range(candidate_size):
        __old_delegate_coin(operators[i], accounts[0], delegate_amount + i)
        __get_old_delegator_info(operators[i], accounts[i])
    __old_turn_round(consensuses)
    __old_turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    reward = BLOCK_REWARD
    if claim == 'old':
        __old_claim_reward(operators, accounts[0])
    else:
        stake_hub_claim_reward(accounts[0])
        reward = 0
    assert tracker0.delta() == reward


@pytest.mark.parametrize("operate", ['undelegate', 'transfer'])
def test_migration_scenario_2(pledge_agent, validator_set, stake_hub, operate):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    operators, consensuses = __register_candidates(accounts[2:4])
    __old_turn_round()
    candidate_size = 2
    for i in range(candidate_size):
        __old_delegate_coin(operators[i], accounts[0], delegate_amount + i)
    __old_turn_round(consensuses)
    reward = BLOCK_REWARD
    if operate == 'undelegate':
        __old_undelegate_coin(operators[0], accounts[0], delegate_amount)
        reward = reward // 2
    else:
        __old_transfer_coin(operators[0], operators[1], accounts[0], delegate_amount)
    __old_turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    __old_claim_reward(operators, accounts[0])
    assert tracker0.delta() == reward


@pytest.mark.parametrize("operate", ['undelegate', 'transfer'])
def test_migration_scenario_3(pledge_agent, validator_set, stake_hub, operate):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    operators, consensuses = __register_candidates(accounts[2:4])
    __old_turn_round()
    candidate_size = 2
    for i in range(candidate_size):
        __old_delegate_coin(operators[i], accounts[0], delegate_amount)
    __old_turn_round(consensuses)
    reward = BLOCK_REWARD
    if operate == 'undelegate':
        __old_undelegate_coin(operators[0], accounts[0])
        reward = reward // 2
    else:
        __old_transfer_coin(operators[0], operators[1], accounts[0], delegate_amount)
    __init_hybrid_score_mock()
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    __old_claim_reward(operators, accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == reward


@pytest.mark.parametrize("operate", ['undelegate', 'transfer'])
def test_migration_scenario_4(pledge_agent, validator_set, stake_hub, operate):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    undelegate_amount = delegate_amount // 2
    operators, consensuses = __register_candidates(accounts[2:4])
    __old_turn_round()
    candidate_size = 2
    for i in range(candidate_size):
        __old_delegate_coin(operators[i], accounts[0], delegate_amount)
    __old_turn_round(consensuses)
    reward = BLOCK_REWARD
    if operate == 'undelegate':
        __old_undelegate_coin(operators[0], accounts[0], undelegate_amount)
        reward = TOTAL_REWARD + BLOCK_REWARD // 4
    else:
        __old_transfer_coin(operators[0], operators[1], accounts[0], undelegate_amount)
    __init_hybrid_score_mock()
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    __old_claim_reward(operators, accounts[0])
    assert tracker0.delta() == 0
    assert stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == reward


@pytest.mark.parametrize("operate", ['undelegate', 'transfer'])
def test_migration_scenario_5(pledge_agent, validator_set, stake_hub, operate):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    undelegate_amount = delegate_amount // 2
    operators, consensuses = __register_candidates(accounts[2:4])
    __old_turn_round()
    candidate_size = 2
    for i in range(candidate_size):
        __old_delegate_coin(operators[i], accounts[0], delegate_amount)
    __old_turn_round(consensuses)
    reward = BLOCK_REWARD
    if operate == 'undelegate':
        __old_undelegate_coin(operators[0], accounts[0], undelegate_amount)
        reward = TOTAL_REWARD + TOTAL_REWARD - TOTAL_REWARD // 2
        delegate_amount0 = delegate_amount // 2
        delegate_amount1 = delegate_amount
    else:
        __old_transfer_coin(operators[0], operators[1], accounts[0], undelegate_amount)
        delegate_amount0 = delegate_amount // 2
        delegate_amount1 = delegate_amount + delegate_amount // 2
    __old_turn_round(consensuses)
    __init_hybrid_score_mock()
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == 0
    __old_claim_reward(operators, accounts[0])
    assert tracker0.delta() == reward
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == BLOCK_REWARD
    turn_round(consensuses, round_count=1)
    stake_hub_claim_reward(accounts[0])
    _, _, account_rewards, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount0)],
        "btc": [],
    }, {
        "address": operators[1],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount1)],
        "btc": [],
    }], BLOCK_REWARD // 2)

    assert tracker0.delta() == account_rewards[accounts[0]]


def __init_hybrid_score_mock():
    STAKE_HUB.initHybridScoreMock()


def __move_btc_data(tx_ids):
    BTC_STAKE.moveData(tx_ids)


def __old_delegate_coin(candidate, account=None, amount=None, old=True):
    if account is None:
        account = accounts[0]
    if amount is None:
        amount = MIN_INIT_DELEGATE_VALUE
    if old is True:
        tx = PLEDGE_AGENT.delegateCoinOld(candidate, {'value': amount, 'from': account})
    else:
        tx = PLEDGE_AGENT.delegateCoin(candidate, {'value': amount, 'from': account})


def __old_undelegate_coin(candidate, account=None, amount=0, old=True):
    if account is None:
        account = accounts[0]
    if old is True:
        tx = PLEDGE_AGENT.undelegateCoinOld(candidate, amount, {'from': account})
    else:
        tx = PLEDGE_AGENT.undelegateCoin(candidate, amount, {'from': account})
    return tx


def __old_transfer_coin(source_agent, target_agent, account=None, amount=0, old=True):
    if account is None:
        account = accounts[0]
    if old is True:
        tx = PLEDGE_AGENT.transferCoinOld(source_agent, target_agent, amount, {'from': account})
    else:
        tx = PLEDGE_AGENT.transferCoin(source_agent, target_agent, amount, {'from': account})
    return tx


def __old_claim_reward(candidates, account=None):
    if account is None:
        account = accounts[0]
    tx = PLEDGE_AGENT.claimReward(candidates, {'from': account})


def __old_turn_round(miners: list = None, tx_fee=100, round_count=1):
    if miners is None:
        miners = []
    tx = None
    for _ in range(round_count):
        for miner in miners:
            ValidatorSetMock[0].deposit(miner, {"value": tx_fee, "from": accounts[-10]})
        tx = CandidateHubMock[0].turnRoundOld()
        chain.sleep(1)
    return tx


def __get_old_reward_index_info(candidate, index):
    reward_index = PLEDGE_AGENT.getReward(candidate, index)
    return reward_index


def __get_old_agent_map_info(candidate):
    agent_map = PLEDGE_AGENT.agentsMap(candidate)
    return agent_map


def __get_old_delegator_info(candidate, delegator):
    delegator_info = PLEDGE_AGENT.getDelegator(candidate, delegator)
    return delegator_info


def __get_delegator_info(candidate, delegator):
    delegator_info = CoreAgentMock[0].getDelegator(candidate, delegator)
    return delegator_info


def __get_reward_map_info(delegator):
    delegator_info = CoreAgentMock[0].rewardMap(delegator)
    return delegator_info


def __get_candidate_map_info(candidate):
    candidate_info = CoreAgentMock[0].candidateMap(candidate)
    return candidate_info


def __check_candidate_map_info(candidate, result: dict):
    old_info = __get_candidate_map_info(candidate)
    for i in result:
        assert old_info[i] == result[i]


def __get_candidate_amount_map_info(candidate):
    # The order is core, hash, btc.
    candidate_score = STAKE_HUB.getCandidateScoresMap(candidate)
    return candidate_score


def __check_old_delegate_info(candidate, delegator, result: dict):
    old_info = __get_old_delegator_info(candidate, delegator)
    for i in result:
        assert old_info[i] == result[i]


def __check_delegate_info(candidate, delegator, result: dict):
    old_info = __get_delegator_info(candidate, delegator)
    for i in result:
        assert old_info[i] == result[i]


def __check_candidate_amount_map_info(candidate, result: list):
    candidate_amounts = __get_candidate_amount_map_info(candidate)
    if candidate_amounts == ():
        candidate_amounts = [0, 0, 0, 0]
    for index, r in enumerate(result):
        assert candidate_amounts[index] == r


def __get_btc_receipt_map(tx_id):
    receipt_map = BTC_STAKE.receiptMap(tx_id)
    print('__check_btc_receipt_map>>>>>>>>>>>>>>>>', receipt_map)
    print('__get_btc_receipt_map>>>>>>>>>>>>>>>>', receipt_map)
    return receipt_map


def __check_btc_receipt_map(candidate, result: dict):
    receipt = __get_btc_receipt_map(candidate)
    for i in result:
        assert receipt[i] == result[i]


def __check_old_agent_map_info(candidate, result: dict):
    old_info = __get_old_agent_map_info(candidate)
    for i in result:
        assert old_info[i] == result[i]


def __register_candidates(agents=None):
    operators = []
    consensuses = []
    if agents is None:
        agents = accounts[2:5]
    for operator in agents:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    return operators, consensuses
