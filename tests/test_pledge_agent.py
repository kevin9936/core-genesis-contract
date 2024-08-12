import time

import pytest
from web3 import Web3
import brownie
from brownie import *
from .common import register_candidate, turn_round, stake_hub_claim_reward, get_current_round
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
def set_block_reward(validator_set, pledge_agent, stake_hub):
    global BLOCK_REWARD, TOTAL_REWARD
    global COIN_REWARD, PLEDGE_AGENT, STAKE_HUB
    block_reward = validator_set.blockReward()
    block_reward_incentive_percent = validator_set.blockRewardIncentivePercent()
    total_block_reward = block_reward + TX_FEE
    BLOCK_REWARD = total_block_reward * ((100 - block_reward_incentive_percent) / 100)
    TOTAL_REWARD = BLOCK_REWARD // 2
    COIN_REWARD = TOTAL_REWARD * HardCap.CORE_HARD_CAP // HardCap.SUM_HARD_CAP
    PLEDGE_AGENT = pledge_agent
    STAKE_HUB = stake_hub


def test_reinit(pledge_agent):
    with brownie.reverts("the contract already init"):
        pledge_agent.init()


@pytest.mark.parametrize("store_old_data", [True, False])
def test_delegate_coin(pledge_agent, store_old_data: bool):
    if store_old_data:
        operator = accounts[1]
        consensus = register_candidate(operator=operator)
        pledge_agent.delegateCoinOld(operator, {"value": MIN_INIT_DELEGATE_VALUE})
        __old_turn_round()
        __old_turn_round([consensus])
        pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
        with brownie.reverts("No old data."):
            pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    else:
        with brownie.reverts("No old data."):
            pledge_agent.delegateCoin(random_address(), {"value": web3.to_wei(1, 'ether')})


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
        with brownie.reverts("No old data."):
            pledge_agent.undelegateCoin(operators[0], undelegate_amount)
    else:
        candidate_hub.refuseDelegate({'from': operators[0]})
        turn_round()
        candidate_hub.unregister({'from': operators[0]})
        turn_round()
        pledge_agent.undelegateCoin(operators[0], undelegate_amount)
        with brownie.reverts("No old data."):
            pledge_agent.undelegateCoin(operators[0], undelegate_amount)


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
        pledge_agent.transferCoin(operators[0], operators[1], transfer_amount)
        with brownie.reverts("No old data."):
            pledge_agent.transferCoin(operators[0], operators[1], transfer_amount)
    else:
        candidate_hub.refuseDelegate({'from': operators[0]})
        turn_round()
        candidate_hub.unregister({'from': operators[0]})
        turn_round()
        pledge_agent.transferCoin(operators[0], operators[1], transfer_amount)
        with brownie.reverts("No old data."):
            pledge_agent.transferCoin(operators[0], operators[1], transfer_amount)


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

    if agents_type == "empty":
        pledge_agent.claimReward([])
    elif agents_type == "all":
        pledge_agent.claimReward(operators)
    elif agents_type == "none":
        pledge_agent.claimReward([random_address()])
    elif agents_type == "partial":
        pledge_agent.claimReward(operators[:2] + [random_address()])


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

    if agents_type == "empty":
        pledge_agent.calculateReward([], accounts[0])
    elif agents_type == "all":
        pledge_agent.calculateReward(operators, accounts[0])
    elif agents_type == "none":
        pledge_agent.calculateReward([random_address()], accounts[0])
    elif agents_type == "partial":
        pledge_agent.calculateReward(operators[:2] + [random_address()], accounts[0])


def test_claim_btc_reward(pledge_agent):
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
    tx = pledge_agent.claimBtcReward([tx_id])
    expect_event(tx, "claimedReward")


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
    pledge_agent.moveBtcData(tx_id, {'from': accounts[0]})
    assert pledge_agent.rewardMap(delegator) > 0


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
