import time

import brownie
import pytest
from brownie.network import gas_price
from web3 import Web3
from brownie import *
from .btc_block_data import *
from .calc_reward import set_delegate, parse_delegation
from .common import register_candidate, turn_round, get_current_round, set_last_round_tag, stake_hub_claim_reward
from .utils import *

MIN_INIT_DELEGATE_VALUE = 0
BLOCK_REWARD = 0
ROUND_INTERVAL = 86400
BTC_VALUE = 2000
btcFactor = 0
MIN_BTC_LOCK_ROUND = 0
BTC_AMOUNT = 0
ONE_ETHER = Web3.to_wei(1, 'ether')
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
TX_FEE = 100
public_key = "0223dd766d6e38eaf9c044dcb18d8221fe8c9a5763ca331e93fadc8f55949b8e12"
lock_time = 1736956800
chain_id = 1112
lock_script_type = 'hash'
FEE = 0
core_hardcap = 6000
power_hardcap = 2000
btc_hardcap = 4000
BTC_DECIMAL = 100000000
sum_hardcap = core_hardcap + power_hardcap + btc_hardcap
COIN_REWARD = 0
POWER_REWARD = 0
BTC_REWARD = 0
BTC_REWARD1 = 0
STAKE_ROUND = 3
MONTH = 30
DENOMINATOR = 10000


# 
# BTC_STAKE = None
# STAKE_HUB = None
# CORE_AGENT = None
# BTC_LIGHT_CLIENT = None
# CANDIDATE_HUB = None


@pytest.fixture(scope="module", autouse=True)
def deposit_for_reward(validator_set, gov_hub):
    accounts[-10].transfer(validator_set.address, Web3.to_wei(100000, 'ether'))
    accounts[-10].transfer(gov_hub.address, Web3.to_wei(100000, 'ether'))


@pytest.fixture(scope="module", autouse=True)
def set_block_reward(validator_set, candidate_hub, btc_light_client, btc_stake, stake_hub, core_agent, pledge_agent):
    global BLOCK_REWARD, btcFactor, MIN_BTC_LOCK_ROUND, FEE, BTC_AMOUNT, POWER_REWARD, BTC_REWARD, COIN_REWARD
    global BTC_STAKE, BTC_REWARD1, STAKE_HUB, CORE_AGENT, BTC_LIGHT_CLIENT, MIN_INIT_DELEGATE_VALUE, CANDIDATE_HUB
    FEE = FEE * 100
    block_reward = validator_set.blockReward()
    block_reward_incentive_percent = validator_set.blockRewardIncentivePercent()
    total_block_reward = block_reward + TX_FEE
    BLOCK_REWARD = total_block_reward * ((100 - block_reward_incentive_percent) / 100)
    btcFactor = stake_hub.INIT_BTC_FACTOR() * stake_hub.BTC_UNIT_CONVERSION()
    print('stake_hub.BTC_UNIT_CONVERSION()', stake_hub.BTC_UNIT_CONVERSION())
    BTC_AMOUNT = BTC_VALUE * btcFactor
    MIN_BTC_LOCK_ROUND = btc_stake.minBtcLockRound()
    candidate_hub.setControlRoundTimeTag(True)
    btc_light_client.setCheckResult(True, 1723046400)
    total_reward = BLOCK_REWARD // 2
    POWER_REWARD = total_reward * power_hardcap // sum_hardcap
    # BTC_AMOUNT =2000
    BTC_REWARD = total_reward * 3333 // 10000
    single_btc_reward = BTC_REWARD * BTC_DECIMAL // 3000
    # BTC_AMOUNT =3000
    BTC_REWARD1 = single_btc_reward * 3000 // BTC_DECIMAL
    MIN_INIT_DELEGATE_VALUE = pledge_agent.requiredCoinDeposit()
    #   actual_account_btc_reward = agent['single_btc_reward'] * item['value'] // BTC_DECIMAL
    COIN_REWARD = total_reward * core_hardcap // sum_hardcap
    BTC_STAKE = btc_stake
    STAKE_HUB = stake_hub
    CORE_AGENT = core_agent
    CANDIDATE_HUB = candidate_hub
    btc_stake.setInitTlpRates(0, 2000, 1, 4000, 5, 5000, 8, 8000, 12, 10000)
    stake_hub.setInitLpRates(0, 1000, 5000, 6000, 12000, 10000)

    btc_stake.setIsActive(True)
    stake_hub.setIsActive(True)
    BTC_LIGHT_CLIENT = btc_light_client


@pytest.fixture(scope="module", autouse=True)
def set_relayer_register(relay_hub):
    for account in accounts[:3]:
        relay_hub.setRelayerRegister(account.address, True)


@pytest.fixture()
def set_candidate():
    operators = []
    consensuses = []
    for operator in accounts[5:8]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    return operators, consensuses


@pytest.fixture()
def delegate_btc_valid_tx():
    operator = accounts[5]
    lock_script = get_lock_script(lock_time, public_key, lock_script_type)
    btc_tx, tx_id = get_btc_tx(BTC_VALUE, chain_id, operator, accounts[0], lock_script_type, lock_script)
    tx_id_list = [tx_id]
    return lock_script, btc_tx, tx_id_list


def __get_month_timestamp():
    return 2592000


def __set_is_btc_stake_active(value=False):
    BTC_STAKE.setIsActive(value)
    print('__set_is_active>>>>>>>>success', value)


def __set_is_stake_hub_active(value):
    STAKE_HUB.setIsActive(value)
    print('__set_is_active>>>>>>>>success', value)


def __set_block_time_stamp(timestamp, lock_time1=None, time_type='day'):
    if lock_time1 is None:
        lock_time1 = lock_time
    # the default timestamp is days
    if time_type == 'day':
        timestamp = timestamp * 86400
        time1 = lock_time1 - timestamp
    else:
        timestamp = timestamp * 2592000
        time1 = lock_time1 - timestamp
    print(f'__set_block_time_stamp>>>>>>>>>{time1},{lock_time1 - time1 // 86400}')
    BTC_LIGHT_CLIENT.setCheckResult(True, time1)


def test_delegate_btc_success_public_hash(btc_stake, set_candidate, delegate_btc_valid_tx):
    __set_lp_rates()
    __set_block_time_stamp(31)
    operators, consensuses = set_candidate
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    tx = btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    expect_event(tx, 'delegatedBtc', {
        'txid': tx_id_list[0],
        'candidate': operators[0],
        'delegator': accounts[0],
        'script': '0x' + lock_script,
        'amount': BTC_VALUE
    })
    turn_round(consensuses)

    print('lpRates(0', btc_stake.tlpRates(0))
    print('lpRates(1', btc_stake.tlpRates(1))
    print('lpRates(2', btc_stake.tlpRates(2))
    print('lpRates(3', btc_stake.tlpRates(3))
    print('lpRates(4', btc_stake.tlpRates(4))
    # __set_block_time_stamp()
    tracker = get_tracker(accounts[0])
    tx = stake_hub_claim_reward(accounts[0])
    assert "claimedReward" in tx.events
    reward, _ = __calculate_btc_only_rewards(BTC_VALUE, 31)
    assert tracker.delta() == reward


"""
    tlp_rates = {
        12: 10000,
        8: 8000,
        5: 5000,
        1: 4000,
        0: 2000
    }"""


def __get_reward_map_info(delegate):
    """
    uint256 reward;
    uint256 unclaimedReward;
    """
    rewards, unclaimed_reward = BTC_STAKE.getRewardMap(delegate)
    print(f'__get_reward_map_info>>>>>>>>>>{rewards}:{unclaimed_reward}')
    return rewards, unclaimed_reward


def __get_receipt_map_info(tx_id):
    """
    address candidate;
    address delegator;
    uint256 round; // 
    """
    receipt_map = BTC_STAKE.receiptMap(tx_id)
    print('__get_receipt_map_info>>>>', receipt_map)
    return receipt_map


@pytest.mark.parametrize("pledge_days", [1, 2, 29, 30, 31, 149, 150, 151, 239, 240, 241, 359, 360, 361])
def test_claim_btc_rewards_for_various_stake_durations(btc_stake, set_candidate, delegate_btc_valid_tx, stake_hub,
                                                       pledge_days):
    __set_lp_rates()
    __set_block_time_stamp(pledge_days)
    operators, consensuses = set_candidate
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    tx = stake_hub_claim_reward(accounts[0])
    assert "claimedReward" in tx.events
    # print('hub.lpRa', stake_hub.lpRates(0))
    reward, unclaimed_reward = __calculate_btc_only_rewards(BTC_VALUE, pledge_days)
    assert tracker.delta() == reward
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward


def test_no_duration_discount_without_btc_rewards(btc_stake, set_candidate, delegate_btc_valid_tx):
    __set_lp_rates()
    __set_block_time_stamp(MONTH)
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker.delta() == 0
    assert STAKE_HUB.unclaimedReward() == 0


@pytest.mark.parametrize("is_active", [True, False])
def test_enable_disable_duration_discount(btc_stake, set_candidate, delegate_btc_valid_tx, is_active):
    __set_lp_rates()
    __set_is_btc_stake_active(is_active)
    operators, consensuses = set_candidate
    __set_block_time_stamp(MONTH)
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    stake_day = 360
    if is_active is True:
        stake_day = MONTH
    reward, unclaimed_reward = __calculate_btc_only_rewards(BTC_VALUE, stake_day)
    assert tracker.delta() == reward
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward


def __set_tlp_rates(rates=None):
    BTC_STAKE.popTtlpRates()
    if rates:
        for r in rates:
            tl = r[0]
            tp = r[1]
            BTC_STAKE.setTlpRates(tl, tp)
        for i in range(0, len(rates)):
            print(f'lpRates{i}', BTC_STAKE.tlpRates(i))
    print('__set_tlp_rates>>>>>>>>>>>>>>')


@pytest.mark.parametrize("is_active", [True, False])
def test_no_stake_duration_rewards(btc_stake, set_candidate, delegate_btc_valid_tx, is_active):
    __set_lp_rates()
    __set_tlp_rates()
    operators, consensuses = set_candidate
    __set_block_time_stamp(MONTH)
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    reward, unclaimed_reward = __calculate_btc_only_rewards(BTC_VALUE)
    assert tracker.delta() == reward
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward


@pytest.mark.parametrize("tlp", [[0, 3000], [1, 5000]])
def test_one_level_stake_duration_reward(btc_stake, set_candidate, delegate_btc_valid_tx, tlp):
    __set_lp_rates()
    __set_tlp_rates([tlp])
    operators, consensuses = set_candidate
    __set_block_time_stamp(MONTH)
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    reward, unclaimed_reward = __calculate_btc_only_rewards(BTC_VALUE, MONTH, tlp_rates={tlp[0]: tlp[1]})
    assert tracker.delta() == reward
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward


def __calculate_btc_only_rewards(total_btc, day=360, claim_btc=None, validator_score=None,
                                 btc_factor=10,
                                 total_reward=None, tlp_rates=None, lp_rates=None):
    if tlp_rates is None:
        tlp_rates = {
            12: 10000,
            8: 8000,
            5: 5000,
            1: 4000,
            0: 2000
        }
    p = 10000
    day = day // 30
    for i in tlp_rates:
        if day >= i:
            p = tlp_rates[i]
            break
    DENOMINATOR = 10000
    collateral_state_btc = 3333
    if total_reward is None:
        total_reward = BLOCK_REWARD // 2
    if validator_score is None:
        validator_score = total_btc
    if claim_btc is None:
        claim_btc = total_btc
    reward = total_reward * (total_btc * btc_factor) // (
            validator_score * btc_factor) * collateral_state_btc // DENOMINATOR
    reward1 = reward * BTC_DECIMAL // total_btc
    reward2 = reward1 * claim_btc // BTC_DECIMAL
    btc_reward_claimed = reward2 * p // 10000
    unclaim_amount = reward2 - btc_reward_claimed
    # if coin_reward is not None:
    #     p = 10000
    #     bb = coin_reward * DENOMINATOR / btc_reward_claimed
    #     for i in lp_rates:
    #         if bb >= i:
    #             p = lp_rates[i]
    #             break
    #     btc_reward_claimed = btc_reward_claimed * p / DENOMINATOR
    #     btc_reward_claimed += coin_reward
    #     unclaim_amount += btc_reward_claimed - btc_reward_claimed
    #     print('__calculate_btc_only_rewards>>>>', btc_reward_claimed, unclaim_amount)

    return btc_reward_claimed, unclaim_amount


def __set_lp_rates(rates=None):
    STAKE_HUB.popLpRates()
    if rates:
        for r in rates:
            tl = r[0]
            tp = r[1]
            STAKE_HUB.setLpRates(tl, tp)
        for i in range(0, len(rates)):
            print(f'lpRates{i}', STAKE_HUB.lpRates(i))
    print('__set_lp_rates>>>>>>>>>>>>>>')


def __cal_core_btc_reward(btc_reward, coin_reward, unclaimed_reward):
    DENOMINATOR = 10000
    lp_rates = {
        12000: 10000,
        5000: 6000,
        0: 1000
    }
    p = 10000
    bb = coin_reward * DENOMINATOR // btc_reward
    for i in lp_rates:
        if bb >= i:
            p = lp_rates[i]
            break
    print('nbbbbb', bb)
    actual_account_btc_reward = btc_reward * p // DENOMINATOR
    unclaimed_reward += btc_reward - actual_account_btc_reward
    print(f'__cal_core_btc_reward>>>>>>>>>{actual_account_btc_reward}:{unclaimed_reward}ppppppp{p}')
    return actual_account_btc_reward, unclaimed_reward


def __get_candidate_list_by_delegator(delegator):
    candidate_info = CORE_AGENT.getCandidateListByDelegator(delegator)
    print('__get_candidate_list_by_delegator>>>>', candidate_info)
    return candidate_info


def __delegate_coin(candidate, value=None, delegate=None):
    if value is None:
        value = MIN_INIT_DELEGATE_VALUE
    if delegate is None:
        delegate = accounts[0]
    CORE_AGENT.delegateCoin(candidate, {"value": value, "from": delegate})
    print('__delegate_coin>>>>>>>>>>')


def test_core_rewards_discount_btc_rewards(btc_stake, candidate_hub, btc_light_client, set_candidate,
                                           delegate_btc_valid_tx, core_agent):
    __set_tlp_rates()
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    __delegate_coin(operators[1], MIN_INIT_DELEGATE_VALUE * 800)
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    round_time_tag = candidate_hub.roundTag() - 6
    btc_light_client.setMiners(round_time_tag, operators[2], [accounts[2]] * 1000)
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    reward, unclaimed_reward = __cal_core_btc_reward(BLOCK_REWARD // 2, COIN_REWARD * 2, 0)
    tx = stake_hub_claim_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == reward + COIN_REWARD * 2
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward


def __core_reward_ratio(candidate, core_rate, btc_reward, stake_amount):
    DENOMINATOR = 10000
    core_value = 1e6
    reward = core_rate * btc_reward // DENOMINATOR
    x = reward * core_value // stake_amount
    CORE_AGENT.setAccuredRewardMap(candidate, get_current_round() - 1, x)
    print('__core_reward_ratio>>>>>>', reward)
    return reward


@pytest.mark.parametrize("core_rate",
                         [0, 1989, 2001, 5000, 6000, 7000, 9000, 11000, 12001, 13000])
def test_each_bracket_discounted_rewards_accuracy(btc_stake, candidate_hub, btc_light_client, set_candidate,
                                                  delegate_btc_valid_tx, core_agent, core_rate):
    __set_tlp_rates()
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    __delegate_coin(operators[1], MIN_INIT_DELEGATE_VALUE * 1000, delegate=accounts[0])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    round_time_tag = candidate_hub.roundTag() - 6
    btc_light_client.setMiners(round_time_tag, operators[2], [accounts[2]] * 100)
    turn_round()
    turn_round(consensuses)
    reward1 = __core_reward_ratio(operators[1], core_rate, BLOCK_REWARD // 2, MIN_INIT_DELEGATE_VALUE * 1000)
    tracker = get_tracker(accounts[0])
    reward, unclaimed_reward = __cal_core_btc_reward(BLOCK_REWARD // 2, reward1, 0)
    __get_candidate_list_by_delegator(accounts[0])
    tx = stake_hub_claim_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == reward + reward1
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward


def test_discount_applied_to_core_total_rewards(btc_stake, candidate_hub, btc_light_client, set_candidate,
                                                delegate_btc_valid_tx, core_agent):
    __set_tlp_rates()
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 100
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[1])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[1])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE)]
    }, {
        "address": operators[1],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": []
    }], BLOCK_REWARD // 2, core_lp=True)
    tracker = get_tracker(accounts[0])
    __get_candidate_list_by_delegator(accounts[0])
    tx = stake_hub_claim_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == account_rewards[accounts[0]]
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward[0][accounts[0]] > 0


def test_same_candidate_rewards_with_discounts(btc_stake, candidate_hub, btc_light_client, set_candidate,
                                               delegate_btc_valid_tx, core_agent):
    __set_tlp_rates()
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[1])
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[2])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount),
                 set_delegate(accounts[2], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE)]
    }], BLOCK_REWARD // 2, core_lp=True)
    tracker = get_tracker(accounts[0])
    __get_candidate_list_by_delegator(accounts[0])
    tx = stake_hub_claim_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == account_rewards[accounts[0]]
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward[0][accounts[0]] > 0


def test_revert_on_discount_exceeding_100_percent(btc_stake, set_candidate,
                                                  delegate_btc_valid_tx):
    __set_tlp_rates()
    __set_is_stake_hub_active(True)
    __set_lp_rates([[0, 12000]])
    operators, consensuses = set_candidate
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[1])
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[2])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount),
                 set_delegate(accounts[2], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE)]
    }], BLOCK_REWARD // 2, core_lp=True)
    with brownie.reverts("Integer overflow"):
        stake_hub_claim_reward(accounts[0])


def test_normal_duration_and_reward_discounts(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                              delegate_btc_valid_tx):
    __set_block_time_stamp(MONTH)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[1])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[1])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    round_time_tag = candidate_hub.roundTag() - 6
    btc_light_client.setMiners(round_time_tag, operators[1], [accounts[1]] * 100)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[1],
        "active": True,
        "power": [set_delegate(accounts[1], 100)],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": []
    }], BLOCK_REWARD // 2, core_lp=True)
    tracker = get_tracker(accounts[0])
    __get_candidate_list_by_delegator(accounts[0])
    tx = stake_hub_claim_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == account_rewards[accounts[0]]
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward[0][accounts[0]] > 0


def test_multiple_btc_stakes_and_reward_claim(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                              delegate_btc_valid_tx):
    __set_block_time_stamp(MONTH)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[1])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[1])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    lock_script = get_lock_script(lock_time, public_key, lock_script_type)
    btc_tx, _ = get_btc_tx(BTC_VALUE, chain_id, operators[1], accounts[0], lock_script_type, lock_script)
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    round_time_tag = candidate_hub.roundTag() - 6
    btc_light_client.setMiners(round_time_tag, operators[2], [accounts[2]] * 100)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[1],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[2],
        "active": True,
        "power": [set_delegate(accounts[2], 100)],
        "coin": [],
        "btc": []
    }], BLOCK_REWARD // 2, core_lp=True)
    tracker = get_tracker(accounts[0])
    __get_candidate_list_by_delegator(accounts[0])
    tx = stake_hub_claim_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == account_rewards[accounts[0]]
    assert STAKE_HUB.unclaimedReward() == unclaimed_reward[0][accounts[0]] > 0
    assert unclaimed_reward[1]['days'] > unclaimed_reward[1]['core'] > 0


def __distribute_next_round_rewards(candidates, unclaimed, btcPoolRate=None):
    candidates_reward = {
        'btc': {},
        'coin': {}
    }
    bonuses = [0, 0, 0]
    if btcPoolRate is None:
        btcPoolRate = 10000
    validatorSize = len(candidates)
    unclaimed_reward = 0
    unclaimed_rewards = unclaimed[0]
    for i in unclaimed_rewards:
        unclaimed_reward += unclaimed_rewards[i]
    bonuses[2] = unclaimed_reward * btcPoolRate // DENOMINATOR // validatorSize
    bonuses[0] = unclaimed_reward * (DENOMINATOR - btcPoolRate) // DENOMINATOR // validatorSize
    for i in candidates:
        candidates_reward['btc'][i] = bonuses[2]
        candidates_reward['coin'][i] = bonuses[0]
    print(
        f'__distribute_next_round_rewards>>>>>>>>>>core>>{candidates_reward}>>bonuses>{bonuses}')
    return candidates_reward, bonuses


def test_deducted_rewards_added_to_next_round_btc(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                                  delegate_btc_valid_tx):
    __set_block_time_stamp(MONTH)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[1])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[1])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    lock_script = get_lock_script(lock_time, public_key, lock_script_type)
    btc_tx, _ = get_btc_tx(BTC_VALUE, chain_id, operators[1], accounts[0], lock_script_type, lock_script)
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    round_time_tag = candidate_hub.roundTag() - 6
    btc_light_client.setMiners(round_time_tag, operators[2], [accounts[2]] * 100)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[1],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[2],
        "active": True,
        "power": [set_delegate(accounts[2], 100)],
        "coin": [],
        "btc": []
    }], BLOCK_REWARD // 2, core_lp=True)
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker.delta() == account_rewards[accounts[0]]
    candidates_reward, _ = __distribute_next_round_rewards(operators, unclaimed_reward)
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[1],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }], BLOCK_REWARD // 2, core_lp=True, compensation_reward=candidates_reward)
    stake_hub_claim_reward(accounts[0])
    assert tracker.delta() == account_rewards[accounts[0]]


def __compensation_reward_init(operators, consensuses):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[0])
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[1])
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[1])
    lock_script = get_lock_script(lock_time, public_key, lock_script_type)
    btc_tx, _ = get_btc_tx(BTC_VALUE, chain_id, operators[0], accounts[0], lock_script_type, lock_script)
    BTC_STAKE.delegate(btc_tx, 0, [], 0, lock_script)
    __set_block_time_stamp(150)
    btc_tx, _ = get_btc_tx(BTC_VALUE * 2, chain_id, operators[1], accounts[0], lock_script_type, lock_script)
    BTC_STAKE.delegate(btc_tx, 0, [], 0, lock_script)
    round_time_tag = CANDIDATE_HUB.roundTag() - 6
    BTC_LIGHT_CLIENT.setMiners(round_time_tag, operators[2], [accounts[2]] * 100)
    turn_round()
    # CANDIDATE_HUB.refuseDelegate({'from': operators[2]})
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[1],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE * 2, stake_duration=150)]
    }, {
        "address": operators[2],
        "active": True,
        "power": [set_delegate(accounts[2], 100)],
        "coin": [],
        "btc": []
    }], BLOCK_REWARD // 2, core_lp=True)
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker.delta() == account_rewards[accounts[0]]
    unclaimed_rewards = STAKE_HUB.unclaimedReward()

    return unclaimed_reward


def __set_btcPoolRate(value):
    STAKE_HUB.setBtcPoolRate(value)
    print('__set_btcPoolRate>>>>>>>', value)


def test_deducted_rewards_added_to_next_round_core(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                                   delegate_btc_valid_tx):
    __set_btcPoolRate(0)
    __set_block_time_stamp(MONTH)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    unclaimed_reward = __compensation_reward_init(operators, consensuses)
    candidates_reward, _ = __distribute_next_round_rewards(operators, unclaimed_reward, 0)
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[1],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE * 2, stake_duration=150)]
    }], BLOCK_REWARD // 2, core_lp=True, compensation_reward=candidates_reward)
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert account_rewards[accounts[0]] == tracker.delta()


@pytest.mark.parametrize("pool_rate", [1000, 4000, 5000, 6000, 8000, 9500])
def test_next_round_successfully_includes_deducted_rewards(btc_stake, set_candidate, pool_rate):
    __set_btcPoolRate(pool_rate)
    __set_block_time_stamp(MONTH)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    unclaimed_reward = __compensation_reward_init(operators, consensuses)
    candidates_reward, bonus = __distribute_next_round_rewards(operators, unclaimed_reward, pool_rate)
    tx = turn_round(consensuses)
    actual_core_bonus = tx.events['roundReward'][0]['bonus']
    actual_btc_bonus = tx.events['roundReward'][-1]['bonus']
    assert actual_core_bonus == bonus[0]
    assert actual_btc_bonus == bonus[2]
    _, unclaimed_reward, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[1],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], delegate_amount), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE * 2, stake_duration=150)]
    }], BLOCK_REWARD // 2, core_lp=True, compensation_reward=candidates_reward)
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert account_rewards[accounts[0]] == tracker.delta()


def test_non_validators_cannot_receive_deducted_rewards(btc_stake, set_candidate):
    __set_btcPoolRate(5000)
    __set_block_time_stamp(MONTH)
    operators, consensuses = set_candidate
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[0])
    lock_script = get_lock_script(lock_time, public_key, lock_script_type)
    btc_tx, _ = get_btc_tx(BTC_VALUE, chain_id, operators[0], accounts[0], lock_script_type, lock_script)
    BTC_STAKE.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    CANDIDATE_HUB.refuseDelegate({'from': operators[2]})
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)
    actual_core_bonus = tx.events['roundReward'][0]['bonus']
    actual_btc_bonus = tx.events['roundReward'][-1]['bonus']
    assert actual_core_bonus + actual_btc_bonus == unclaimed_reward // 2


def test_no_stake_still_gets_deducted_rewards(btc_stake, set_candidate):
    __set_block_time_stamp(MONTH)
    operators, consensuses = set_candidate
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[0])
    lock_script = get_lock_script(lock_time, public_key, lock_script_type)
    btc_tx, _ = get_btc_tx(BTC_VALUE, chain_id, operators[0], accounts[0], lock_script_type, lock_script)
    BTC_STAKE.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)
    actual_core_bonus = tx.events['roundReward'][0]['bonus']
    actual_btc_bonus = tx.events['roundReward'][-1]['bonus']
    assert actual_core_bonus + actual_btc_bonus == unclaimed_reward // 3


def test_multiple_users_rewards_deducted(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                         delegate_btc_valid_tx):
    __set_block_time_stamp(MONTH)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[2])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    __set_block_time_stamp(150)
    btc_tx1, _ = get_btc_tx(BTC_VALUE // 4, chain_id, operators[0], accounts[1], lock_script_type, lock_script)
    btc_stake.delegate(btc_tx1, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_rewards, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[2], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH),
                set_delegate(accounts[1], BTC_VALUE // 4, stake_duration=150)]
    }], BLOCK_REWARD // 2, core_lp=True)
    stake_hub_claim_reward(accounts[0])
    stake_hub_claim_reward(accounts[1])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    assert unclaimed_reward == unclaimed_rewards[0][accounts[0]] + unclaimed_rewards[0][accounts[1]]


def __delegate_btc(btc_amount, operator, delegator, lock_script, stake_duration=None):
    if stake_duration is None:
        stake_duration = MONTH
    __set_block_time_stamp(stake_duration)
    btc_tx1, _ = get_btc_tx(btc_amount, chain_id, operator, delegator, lock_script_type, lock_script)
    BTC_STAKE.delegate(btc_tx1, 0, [], 0, lock_script)
    print('__delegate_btc>>>>>>>>>>success')


def test_no_coin_rewards_for_btc_stake(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                       delegate_btc_valid_tx):
    __set_block_time_stamp(MONTH)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[1])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_rewards, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[2], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }], BLOCK_REWARD // 2, core_lp=True)
    stake_hub_claim_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)
    assert unclaimed_reward == unclaimed_rewards[0][accounts[0]]
    assert unclaimed_reward // len(operators) == tx.events['roundReward'][-1]['bonus']


def test_turn_round_btc_rewards_without_btc_stake(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                                  delegate_btc_valid_tx):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[2])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    # __delegate_btc(BTC_VALUE,operators[1],accounts[1],lock_script)
    turn_round()
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)


def test_turn_round_core_rewards_without_core_stake(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                                    delegate_btc_valid_tx):
    __set_btcPoolRate(0)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[2])
    # __delegate_coin(operators[0], delegate_amount, delegate=accounts[2])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)


def test_turn_round_rewards_with_single_stake(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                                    delegate_btc_valid_tx):
    __set_btcPoolRate(5000)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    __delegate_coin(operators[1], delegate_amount, delegate=accounts[2])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)



def test_turn_round_rewards_without_staking(btc_stake, set_candidate, candidate_hub, btc_light_client,
                                            delegate_btc_valid_tx):
    __set_btcPoolRate(5000)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    __delegate_coin(operators[0], delegate_amount, delegate=accounts[2])
    lock_script, btc_tx, tx_id_list = delegate_btc_valid_tx
    btc_stake.delegate(btc_tx, 0, [], 0, lock_script)
    turn_round()
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    assert unclaimed_reward > 0
    tx = turn_round(consensuses)
    assert len(tx.events['roundReward']) == 3
