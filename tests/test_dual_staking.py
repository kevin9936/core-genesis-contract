import brownie
import pytest
from brownie import *
from .calc_reward import set_delegate, parse_delegation, Discount, set_btc_lst_delegate
from .common import register_candidate, turn_round, get_current_round, claim_stake_and_relay_reward, \
    stake_hub_claim_reward, claim_relayer_reward, set_round_tag
from .delegate import *
from .utils import *

MIN_INIT_DELEGATE_VALUE = 0
DELEGATE_VALUE = 2000000
BLOCK_REWARD = 0
BTC_VALUE = 200
POWER_VALUE = 2
BTC_LST_VALUE = 600
TX_FEE = 100
FEE = 100
BTC_REWARD = 0
MONTH = 30
YEAR = 360
TOTAL_REWARD = 0
# BTC delegation-related
PUBLIC_KEY = "0223dd766d6e38eaf9c044dcb18d8221fe8c9a5763ca331e93fadc8f55949b8e12"
LOCK_SCRIPT = "0480db8767b17576a914574fdd26858c28ede5225a809f747c01fcc1f92a88ac"
PAY_ADDRESS = "0xa914c0958c8d9357598c5f7a6eea8a807d81683f9bb687"
LOCK_TIME = 1736956800
# BTCLST delegation-related
BTCLST_LOCK_SCRIPT = "0xa914cdf3d02dd323c14bea0bed94962496c80c09334487"
BTCLST_REDEEM_SCRIPT = "0xa914047b9ba09367c1b213b5ba2184fba3fababcdc0287"


@pytest.fixture(scope="module", autouse=True)
def deposit_for_reward(validator_set, gov_hub, system_reward):
    accounts[-10].transfer(validator_set.address, Web3.to_wei(100000, 'ether'))
    accounts[-10].transfer(gov_hub.address, Web3.to_wei(100000, 'ether'))
    accounts[-10].transfer(system_reward.address, Web3.to_wei(100000, 'ether'))


@pytest.fixture(scope="module", autouse=True)
def set_block_reward(validator_set, candidate_hub, btc_light_client, btc_stake, stake_hub, core_agent, pledge_agent,
                     btc_lst_stake, gov_hub, hash_power_agent, btc_agent, system_reward):
    global BLOCK_REWARD, FEE, BTC_REWARD, COIN_REWARD, TOTAL_REWAR, TOTAL_REWARD, HASH_POWER_AGENT, BTC_AGENT
    global BTC_STAKE, STAKE_HUB, CORE_AGENT, BTC_LIGHT_CLIENT, MIN_INIT_DELEGATE_VALUE, CANDIDATE_HUB, BTC_LST_STAKE
    FEE = FEE * 100
    block_reward = validator_set.blockReward()
    block_reward_incentive_percent = validator_set.blockRewardIncentivePercent()
    total_block_reward = block_reward + TX_FEE
    BLOCK_REWARD = total_block_reward * ((100 - block_reward_incentive_percent) / 100)
    TOTAL_REWARD = BLOCK_REWARD // 2
    BTC_REWARD = TOTAL_REWARD
    MIN_INIT_DELEGATE_VALUE = pledge_agent.requiredCoinDeposit()
    BTC_STAKE = btc_stake
    STAKE_HUB = stake_hub
    CORE_AGENT = core_agent
    CANDIDATE_HUB = candidate_hub
    BTC_LIGHT_CLIENT = btc_light_client
    BTC_AGENT = btc_agent
    candidate_hub.setControlRoundTimeTag(True)
    # The default staking time is 150 days
    set_block_time_stamp(150, LOCK_TIME)
    tlp_rates, lp_rates = Discount().get_init_discount()
    btc_stake.setInitTlpRates(*tlp_rates)
    btc_agent.setInitLpRates(*lp_rates)
    btc_agent.setIsActive(True)
    btc_agent.setAssetWeight(100)
    btc_agent.setAssetWeight(1)
    system_reward.setOperator(stake_hub.address)
    BTC_LST_STAKE = btc_lst_stake
    HASH_POWER_AGENT = hash_power_agent
    btc_lst_stake.updateParam('add', BTCLST_LOCK_SCRIPT, {'from': gov_hub.address})


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


def test_delegate_btc_success_public_hash(btc_stake, set_candidate):
    stake_duration = 31
    __set_lp_rates()
    set_block_time_stamp(stake_duration, LOCK_TIME)
    operators, consensuses = set_candidate
    btc_tx = build_btc_tx(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT, LOCK_SCRIPT)
    tx = btc_stake.delegate(btc_tx, 0, [], 0, LOCK_SCRIPT)
    turn_round()
    expect_event(tx, 'delegated', {
        'txid': get_transaction_txid(btc_tx),
        'candidate': operators[0],
        'delegator': accounts[0],
        'script': '0x' + LOCK_SCRIPT,
        'amount': BTC_VALUE
    })
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    tx = claim_stake_and_relay_reward(accounts[0])
    assert "claimedReward" in tx.events
    reward, _ = __calc_btc_deducted_stake_duration_reward(TOTAL_REWARD, stake_duration)
    assert tracker.delta() == reward


@pytest.mark.parametrize("pledge_days", [1, 2, 29, 30, 31, 149, 150, 151, 239, 240, 241, 359, 360, 361])
def test_claim_btc_rewards_for_various_stake_durations(btc_stake, set_candidate, stake_hub,
                                                       pledge_days):
    __set_lp_rates()
    operators, consensuses = set_candidate
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT, stake_duration=pledge_days)
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    tx = claim_stake_and_relay_reward(accounts[0])
    assert "claimedReward" in tx.events
    reward, unclaimed_reward = __calc_btc_deducted_stake_duration_reward(TOTAL_REWARD, pledge_days)
    assert tracker.delta() == reward
    assert stake_hub.rewardPool() == unclaimed_reward


def test_no_duration_discount_without_btc_rewards(btc_stake, set_candidate):
    __set_lp_rates()
    operators, consensuses = set_candidate
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == 0
    assert STAKE_HUB.rewardPool() == 0


@pytest.mark.parametrize("is_active", [0, 1])
def test_enable_disable_duration_discount(btc_stake, set_candidate, is_active):
    __set_lp_rates()
    __set_is_btc_stake_active(is_active)
    stake_duration = MONTH
    operators, consensuses = set_candidate
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    if is_active == 0:
        stake_duration = 360
    reward, unclaimed_reward = __calc_btc_deducted_stake_duration_reward(TOTAL_REWARD, stake_duration)
    assert tracker.delta() == reward
    assert STAKE_HUB.rewardPool() == unclaimed_reward


@pytest.mark.parametrize("is_active", [True, False])
def test_no_stake_duration_rewards(btc_stake, set_candidate, is_active):
    __set_lp_rates()
    __set_tlp_rates()
    operators, consensuses = set_candidate
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == TOTAL_REWARD
    assert STAKE_HUB.rewardPool() == 0


@pytest.mark.parametrize("tlp", [[0, 3000], [2592000, 5000], [9092000, 8000]])
def test_one_level_stake_duration_reward(btc_stake, set_candidate, tlp):
    __set_lp_rates()
    __set_tlp_rates([tlp])
    operators, consensuses = set_candidate
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    reward, unclaimed_reward = __calc_btc_deducted_stake_duration_reward(TOTAL_REWARD, MONTH,
                                                                         tlp_rates={tlp[0]: tlp[1]})
    assert tracker.delta() == reward
    assert STAKE_HUB.rewardPool() == unclaimed_reward


@pytest.mark.parametrize("core_rate", [0, 1989, 2001, 5000, 6000, 7000, 9000, 11000, 12001, 13000, 15000, 15001, 16000])
def test_each_bracket_discounted_rewards_accuracy(btc_stake, candidate_hub, btc_light_client, set_candidate, core_agent,
                                                  core_rate, system_reward):
    __set_tlp_rates()
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    turn_round()
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    round_time_tag = candidate_hub.roundTag() - 6
    btc_light_client.setMiners(round_time_tag, operators[2], [accounts[2]] * 2)
    turn_round(consensuses, round_count=2)
    core_acc_stake_amount = __update_core_stake_amount(accounts[0], core_rate, BTC_VALUE)
    tracker = get_tracker(accounts[0])
    reward, unclaimed_reward = __calc_stake_amount_discount(BLOCK_REWARD // 2, BTC_VALUE, core_acc_stake_amount)
    tx = claim_stake_and_relay_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == reward
    assert STAKE_HUB.rewardPool() == unclaimed_reward


@pytest.mark.parametrize("core_rate", [1989, 2001, 5000, 6000, 7000, 9000, 11000, 12001, 13000, 15000, 15001, 16000])
def test_btc_reward_discount_by_core_stake_amount(btc_stake, candidate_hub, btc_light_client, set_candidate,
                                                  core_agent,
                                                  core_rate, system_reward):
    __set_tlp_rates()
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    turn_round()
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    if core_rate > 0:
        delegate_coin_success(operators[1], BTC_VALUE * core_rate, accounts[0])
    turn_round(consensuses, round_count=2)
    tracker = get_tracker(accounts[0])
    core_reward = 0
    if core_rate > 0:
        core_reward = TOTAL_REWARD * Utils.CORE_STAKE_DECIMAL // (BTC_VALUE * core_rate) * (
                BTC_VALUE * core_rate) // Utils.CORE_STAKE_DECIMAL
    reward, unclaimed_reward = __calc_stake_amount_discount(TOTAL_REWARD, BTC_VALUE, BTC_VALUE * core_rate)
    tx = claim_stake_and_relay_reward(accounts[0])
    if core_rate >= 15000:
        assert tx.events['rewardTo']['amount'] == (reward - TOTAL_REWARD) * 10
    assert tracker.delta() == reward + core_reward
    assert STAKE_HUB.rewardPool() == unclaimed_reward


def __mock_core_reward_map(delegator, reward, acc_stake_amount):
    CORE_AGENT.setCoreRewardMap(delegator, reward, acc_stake_amount)


def __mock_btc_lst_reward_map(delegator, reward, delegate_amount):
    BTC_LST_STAKE.setBtcLstRewardMap(delegator, reward, delegate_amount)


def __mock_power_reward_map(delegator, reward, delegate_amount):
    HASH_POWER_AGENT.setPowerRewardMap(delegator, reward, delegate_amount)


@pytest.mark.parametrize("core_rate", [0, 4500, 8000, 11000, 12001, 17000])
def test_btc_lst_reward_unaffected_by_core_amount(btc_stake, set_candidate, btc_lst_stake, core_rate):
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    turn_round()
    turn_round(consensuses, round_count=3)
    delegate_btc_lst_success(accounts[0], BTC_VALUE, BTCLST_LOCK_SCRIPT)
    turn_round(consensuses, round_count=2)
    btc_reward = TOTAL_REWARD * 3
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == btc_reward // 2
    assert STAKE_HUB.rewardPool() == btc_reward - btc_reward // 2


@pytest.mark.parametrize("percentage", [0, 1000, 4500, 5000, 6000, 7000, 10000])
def test_update_btc_lst_percentage_and_claim(btc_stake, set_candidate, btc_lst_stake, percentage):
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    turn_round()
    delegate_btc_lst_success(accounts[0], BTC_VALUE, BTCLST_LOCK_SCRIPT, percentage)
    turn_round(consensuses, round_count=2)
    btc_reward = TOTAL_REWARD * 3
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == btc_reward * percentage // Utils.DENOMINATOR
    assert STAKE_HUB.rewardPool() == btc_reward - btc_reward * percentage // Utils.DENOMINATOR


@pytest.mark.parametrize("core_rate", [0, 2001, 8000, 12000, 15000, 18000, 22001, 28000])
def test_core_hash_btc_rewards_discounted_by_core_ratio(btc_stake, candidate_hub, btc_light_client, set_candidate,
                                                        core_agent, core_rate):
    btc_value = 100
    power_value = 1
    __set_tlp_rates()
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    turn_round()
    turn_round(consensuses)
    delegate_power_success(operators[1], accounts[0], value=power_value)
    delegate_btc_success(operators[2], accounts[0], btc_value, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round(consensuses, round_count=2)
    core_acc_stake_amount = __update_core_stake_amount(accounts[0], core_rate, btc_value)
    btc_reward, btc_unclaimed_reward = __calc_stake_amount_discount(TOTAL_REWARD, btc_value, core_acc_stake_amount)
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == btc_reward + TOTAL_REWARD
    assert STAKE_HUB.rewardPool() == btc_unclaimed_reward


def test_power_btc_discount_conversion_success(btc_stake, btc_agent,
                                               set_candidate, core_agent, stake_hub):
    __set_lp_rates([[0, 1000], [10000, 10000], [10001, 1000]])
    btc_agent.setAssetWeight(1e10)
    delegate_amount = 1000000e18
    btc_value = 100e8
    power_value = 1
    __set_tlp_rates()
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    turn_round()
    turn_round(consensuses)
    delegate_coin_success(operators[0], delegate_amount, accounts[0])
    delegate_btc_success(operators[2], accounts[0], btc_value, LOCK_SCRIPT)
    delegate_power_success(operators[1], accounts[0], power_value)
    turn_round(consensuses, round_count=2)
    rewards, debt_amount = stake_hub.claimReward.call()
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert rewards[1] == TOTAL_REWARD
    assert rewards[2] == TOTAL_REWARD * Utils.BTC_DECIMAL // btc_value * 100
    assert tracker.delta() == sum(rewards) - debt_amount


def test_multiple_validators_stake_ratio(btc_stake, candidate_hub, btc_light_client,
                                         set_candidate, core_agent):
    __set_lp_rates([[0, 1000], [6000, 5000], [6001, 1000]])
    __set_tlp_rates()
    delegate_amount = 3000
    btc_value = 1
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    for i in range(2):
        for op in operators[:2]:
            delegate_coin_success(op, delegate_amount, accounts[i])
    delegate_btc_success(operators[2], accounts[0], btc_value, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round()
    turn_round(consensuses)
    rewards, debt_amount = stake_hub_claim_reward(accounts[0]).return_value
    assert rewards[2] == TOTAL_REWARD // 2


def test_same_candidate_rewards_with_discounts(btc_stake, candidate_hub, btc_light_client, set_candidate, core_agent):
    __set_tlp_rates()
    __set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    for index in range(3):
        delegate_coin_success(operators[0], DELEGATE_VALUE, accounts[index])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[0], DELEGATE_VALUE), set_delegate(accounts[1], DELEGATE_VALUE),
                 set_delegate(accounts[2], DELEGATE_VALUE)],
        "btc": [set_delegate(accounts[0], BTC_VALUE)]
    }], BLOCK_REWARD // 2, state_map={'core_lp': True})
    tracker = get_tracker(accounts[0])
    tx = claim_stake_and_relay_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == account_rewards[accounts[0]]


def test_success_with_over_100_percent_discount(btc_stake, set_candidate):
    __set_tlp_rates()
    __set_is_stake_hub_active(1)
    __set_lp_rates([[0, 12000]])
    operators, consensuses = set_candidate
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    for index in range(3):
        delegate_coin_success(operators[0], delegate_amount, accounts[index])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round()
    turn_round(consensuses)
    tx = claim_stake_and_relay_reward(accounts[0])
    assert 'claimedReward' in tx.events


def test_normal_duration_and_reward_discounts(btc_stake, set_candidate, candidate_hub, btc_light_client):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 200
    operators, consensuses = set_candidate
    for i in range(2):
        for op in operators[:2]:
            stake_amount = delegate_amount
            if i == 0:
                stake_amount = DELEGATE_VALUE
            delegate_coin_success(op, stake_amount, accounts[i])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    round_time_tag = candidate_hub.roundTag() - 6
    btc_light_client.setMiners(round_time_tag, operators[1], [accounts[1]] * 10)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _ = parse_delegation([{
        "address": operators[0],
        "coin": [set_delegate(accounts[0], DELEGATE_VALUE), set_delegate(accounts[1], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[1],
        "power": [set_delegate(accounts[1], 10)],
        "coin": [set_delegate(accounts[0], DELEGATE_VALUE), set_delegate(accounts[1], delegate_amount)],
    }], BLOCK_REWARD // 2, state_map={'core_lp': True})
    tracker = get_tracker(accounts[0])
    tx = claim_stake_and_relay_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == account_rewards[accounts[0]]
    assert STAKE_HUB.rewardPool() == unclaimed_reward['total_bonus'] > 0


def test_multiple_btc_stakes_and_reward_claim(btc_stake, set_candidate, candidate_hub, btc_light_client):
    operators, consensuses = set_candidate
    for i in range(2):
        for index, op in enumerate(operators):
            stake_amount = DELEGATE_VALUE
            if index == 2:
                stake_amount = DELEGATE_VALUE // 2
            delegate_coin_success(op, stake_amount, accounts[i])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    delegate_btc_success(operators[1], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    round_time_tag = candidate_hub.roundTag() - 6
    btc_light_client.setMiners(round_time_tag, operators[2], [accounts[2]] * 100)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, _ = parse_delegation([{
        "address": operators[0],
        "coin": [set_delegate(accounts[0], DELEGATE_VALUE), set_delegate(accounts[1], DELEGATE_VALUE)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[1],
        "coin": [set_delegate(accounts[0], DELEGATE_VALUE), set_delegate(accounts[1], DELEGATE_VALUE)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }, {
        "address": operators[2],
        "power": [set_delegate(accounts[2], 100)],
        "coin": [set_delegate(accounts[0], DELEGATE_VALUE // 2), set_delegate(accounts[1], DELEGATE_VALUE // 2)],
    }], BLOCK_REWARD // 2, state_map={'core_lp': True})
    tracker = get_tracker(accounts[0])
    tx = claim_stake_and_relay_reward(accounts[0])
    assert "claimedReward" in tx.events
    assert tracker.delta() == account_rewards[accounts[0]]
    assert STAKE_HUB.rewardPool() == unclaimed_reward['total_bonus'] > 0


def test_deducted_rewards_added_to_next_round_btc(btc_stake, set_candidate, candidate_hub):
    operators, consensuses = set_candidate
    delegate_coin_success(operators[0], DELEGATE_VALUE, accounts[0])
    delegate_btc_success(operators[1], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    delegate_coin_success(operators[0], DELEGATE_VALUE, accounts[0])
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, round_reward = parse_delegation([{
        "address": operators[0],
        "coin": [set_delegate(accounts[0], DELEGATE_VALUE)],
    }, {
        "address": operators[1],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }], BLOCK_REWARD // 2, state_map={'core_lp': True})
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == account_rewards[accounts[0]]
    turn_round(consensuses)
    assert STAKE_HUB.rewardPool() == unclaimed_reward['btc']
    _, unclaimed_reward1, account_rewards, _ = parse_delegation([{
        "address": operators[0],
        "coin": [set_delegate(accounts[0], DELEGATE_VALUE * 2)]
    }, {
        "address": operators[1],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }
    ], BLOCK_REWARD // 2, state_map={'core_lp': True}, compensation_reward=unclaimed_reward)
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == account_rewards[accounts[0]]
    assert STAKE_HUB.rewardPool() == unclaimed_reward1['btc']


def test_deducted_rewards_added_to_next_round_core(btc_stake, set_candidate, candidate_hub, btc_light_client):
    __set_btc_pool_rate([Utils.DENOMINATOR, 0, 0])
    operators, consensuses = set_candidate
    delegate_coin_success(operators[0], DELEGATE_VALUE // 2, accounts[0])
    delegate_btc_success(operators[1], accounts[1], BTC_VALUE, LOCK_SCRIPT)
    operators, consensuses = set_candidate
    turn_round()
    delegate_coin_success(operators[0], DELEGATE_VALUE, accounts[0])
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[1])
    btc_reward_claimed, _ = __calc_btc_deducted_stake_duration_reward(TOTAL_REWARD, MONTH)
    btc_reward, _ = __calc_stake_amount_discount(btc_reward_claimed, BTC_VALUE, 0,
                                                 'btc')
    __set_lp_rates([[0, 12000]])
    __set_is_stake_hub_active(1)
    tx = turn_round(consensuses)
    bonus = __get_candidate_bonus(tx)
    assert bonus['coin']['bonus'] == TOTAL_REWARD - btc_reward
    tracker = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker.delta() == TOTAL_REWARD * 2


@pytest.mark.parametrize("pool_rate", [1000, 4000, 5000, 6000, 7500, 9500])
def test_next_round_successfully_includes_deducted_rewards(btc_stake, set_candidate, pool_rate):
    __set_btc_pool_rate([Utils.DENOMINATOR - pool_rate, 0, pool_rate])
    operators, consensuses = set_candidate
    delegate_coin_success(operators[1], DELEGATE_VALUE, accounts[0])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    tx = turn_round(consensuses)
    bonus = __get_candidate_bonus(tx)
    btc_reward_claimed, unclaim0 = __calc_btc_deducted_stake_duration_reward(TOTAL_REWARD, MONTH)
    btc_reward, unclaim1 = __calc_stake_amount_discount(btc_reward_claimed, BTC_VALUE, DELEGATE_VALUE, 'btc')
    unclaim = unclaim0 + unclaim1
    assert bonus['coin']['bonus'] == unclaim * (Utils.DENOMINATOR - pool_rate) // Utils.DENOMINATOR
    assert bonus['btc']['bonus'] == unclaim * pool_rate // Utils.DENOMINATOR


def test_multiple_users_rewards_deducted(btc_stake, set_candidate, candidate_hub, btc_light_client):
    set_block_time_stamp(MONTH, LOCK_TIME)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    delegate_coin_success(operators[0], delegate_amount, accounts[2])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    delegate_btc_success(operators[0], accounts[1], BTC_VALUE // 4, LOCK_SCRIPT, stake_duration=150)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_rewards, account_rewards, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[2], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH),
                set_delegate(accounts[1], BTC_VALUE // 4, stake_duration=150)]
    }], BLOCK_REWARD // 2, state_map={'core_lp': 4})
    claim_stake_and_relay_reward(accounts[0])
    claim_stake_and_relay_reward(accounts[1])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    assert unclaimed_reward == unclaimed_rewards['total_bonus']


def test_no_coin_rewards_for_btc_stake(btc_stake, set_candidate, candidate_hub, btc_light_client):
    pool_rate = 4000
    __set_btc_pool_rate([Utils.DENOMINATOR - pool_rate, 0, pool_rate])
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    delegate_coin_success(operators[0], delegate_amount, accounts[1])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_rewards, account_rewards, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "power": [],
        "coin": [set_delegate(accounts[2], delegate_amount)],
        "btc": [set_delegate(accounts[0], BTC_VALUE, stake_duration=MONTH)]
    }], BLOCK_REWARD // 2, state_map={'core_lp': 4})
    claim_stake_and_relay_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)
    bonus = __get_candidate_bonus(tx)
    actual_core_bonus = bonus['coin']['bonus']
    assert len(bonus) == 3
    assert unclaimed_reward == unclaimed_rewards['total_bonus']
    assert unclaimed_reward * (Utils.DENOMINATOR - pool_rate) // Utils.DENOMINATOR == actual_core_bonus


def test_turn_round_btc_rewards_without_btc_stake(btc_stake, set_candidate, candidate_hub, btc_light_client):
    __set_btc_pool_rate([0, 0, Utils.DENOMINATOR])
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    delegate_coin_success(operators[1], delegate_amount, accounts[2])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round()
    turn_round(consensuses)
    claim_stake_and_relay_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)
    assert 'roundReward' in tx.events
    bonus = __get_candidate_bonus(tx)
    assert bonus['coin']['bonus'] == 0
    assert bonus['btc']['bonus'] == unclaimed_reward


def test_turn_round_core_rewards_without_core_stake(btc_stake, stake_hub, set_candidate, candidate_hub,
                                                    btc_light_client):
    __set_btc_pool_rate([Utils.DENOMINATOR, 0, 0])
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    delegate_coin_success(operators[1], delegate_amount, accounts[2])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round()
    turn_round(consensuses)
    claim_stake_and_relay_reward(accounts[0])
    turn_round(consensuses)
    claim_stake_and_relay_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)
    assert 'roundReward' in tx.events
    bonus = __get_candidate_bonus(tx)
    assert bonus['coin']['bonus'] == unclaimed_reward
    assert bonus['btc']['bonus'] == 0


def test_turn_round_rewards_with_single_stake(btc_stake, set_candidate, candidate_hub, btc_light_client):
    pool_rate = 5000
    __set_btc_pool_rate([pool_rate, 0, pool_rate])
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    operators, consensuses = set_candidate
    delegate_coin_success(operators[1], delegate_amount, accounts[2])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round()
    turn_round(consensuses)
    claim_stake_and_relay_reward(accounts[0])
    unclaimed_reward = STAKE_HUB.unclaimedReward()
    tx = turn_round(consensuses)
    assert 'roundReward' in tx.events
    bonus = __get_candidate_bonus(tx)
    assert bonus['coin']['bonus'] == unclaimed_reward // 2
    assert bonus['btc']['bonus'] == unclaimed_reward // 2


@pytest.mark.parametrize("percentage", [400, 1000, 8800, 10000])
def test_btc_lst_discount_by_percentage(btc_stake, set_candidate, btc_lst_stake, percentage):
    __set_lp_rates()
    operators, consensuses = set_candidate
    turn_round()
    delegate_btc_lst_success(accounts[0], BTC_VALUE, BTCLST_LOCK_SCRIPT)
    turn_round(consensuses, round_count=2)
    update_system_contract_address(btc_lst_stake, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(int(percentage)), 64)
    btc_lst_stake.updateParam('percentage', hex_value, {'from': accounts[0]})
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    btc_reward = TOTAL_REWARD * 3
    actual_reward = TOTAL_REWARD * 3 * percentage // Utils.DENOMINATOR
    bonus = btc_reward - actual_reward
    assert tracker.delta() == actual_reward
    assert STAKE_HUB.unclaimedReward() == bonus


@pytest.mark.parametrize("bonus_ratio", [
    [0, 0, 2000],
    [0, 2000, 5000],
    [1000, 0, 0],
    [4000, 3000, 0],
    [4000, 0, 4000],
    [2000, 4000, 4000]
])
def test_bonus_distribution_success_by_percentage(btc_stake, set_candidate, stake_hub, bonus_ratio):
    __set_is_stake_hub_active()
    operators, consensuses = set_candidate
    turn_round()
    delegate_btc_lst_success(accounts[0], BTC_VALUE, BTCLST_LOCK_SCRIPT)
    turn_round(consensuses, round_count=2)
    claim_stake_and_relay_reward(accounts[0])
    btc_reward = TOTAL_REWARD * 3
    actual_reward = TOTAL_REWARD * 3 // 2
    bonus = btc_reward - actual_reward
    __set_btc_pool_rate(bonus_ratio)
    tx = turn_round(consensuses)
    round_reward = tx.events['roundReward']
    total_bonus_amount = 0
    for index, r in enumerate(bonus_ratio):
        bonus_amount = bonus * r // Utils.DENOMINATOR
        assert round_reward[index]['bonus'] == bonus_amount
        assert stake_hub.assets(index)['bonusAmount'] == bonus_amount
        total_bonus_amount += bonus_amount
    assert stake_hub.unclaimedReward() == bonus - total_bonus_amount


@pytest.mark.parametrize("bonus_ratio",
                         [[3000, 4000, 2000],
                          [3000, 4000, 3000],
                          [3000, 4000, 1000],
                          [0, 4000, 3000],
                          [3000, 0, 5000],
                          [0, 4000, 0],
                          [1000, 4000, 0],
                          ])
def test_bonus_reward_when_claiming_btc(btc_stake, set_candidate, btc_lst_stake, stake_hub, bonus_ratio):
    __set_is_btc_lst_stake_active()
    lst_reward = 10000
    unclaim_reward = 10000
    core_reward = lst_reward * 2
    operators, consensuses = set_candidate
    delegate_btc_lst_success(accounts[1], BTC_VALUE, BTCLST_LOCK_SCRIPT)
    turn_round()
    rete = 15000
    __mock_stake_hub_with_rewards({
        'core': set_rewards(core_reward, BTC_LST_VALUE * rete),
        'btc': set_rewards(lst_reward, BTC_LST_VALUE)
    }, accounts[0], unclaim_reward)
    __set_btc_pool_rate(bonus_ratio)
    turn_round(consensuses)
    __set_is_stake_hub_active(4)
    additional_bonus = lst_reward * Discount.lp_rates[rete] // Utils.DENOMINATOR - lst_reward
    if additional_bonus > bonus_ratio[-1]:
        additional_bonus = bonus_ratio[-1]
    actual_reward = core_reward + lst_reward + additional_bonus
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == actual_reward
    assert stake_hub.unclaimedReward() == lst_reward - sum(bonus_ratio)


@pytest.mark.parametrize("bonus_ratio",
                         [[0, 4000, 3000],
                          [1000, 4000, 5000],
                          [2000, 4000, 1000],
                          [3000, 4000, 2000],
                          [3000, 0, 5000],
                          [0, 4000, 0]
                          ])
def test_bonus_reward_when_claiming_core(btc_stake, set_candidate, btc_lst_stake, stake_hub, bonus_ratio):
    __set_lp_rates([[10000, 12000]])
    core_reward = 10000
    unclaim_reward = 10000
    operators, consensuses = set_candidate
    delegate_coin_success(operators[0], BTC_VALUE, accounts[1])
    turn_round()
    __mock_stake_hub_with_rewards({
        'core': set_rewards(core_reward, DELEGATE_VALUE),
    }, accounts[0], unclaim_reward)
    __set_btc_pool_rate(bonus_ratio)
    turn_round(consensuses)
    __set_is_stake_hub_active(1)
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == core_reward


@pytest.mark.parametrize("bonus_ratio",
                         [[0, 0, 3000],
                          [4000, 1000, 5000],
                          [4000, 2000, 1000],
                          [4000, 3000, 2000],
                          [3000, 0, 5000],
                          [0, 4000, 0]
                          ])
def test_bonus_reward_when_claiming_power(btc_stake, set_candidate, btc_lst_stake, stake_hub, bonus_ratio):
    power_reward = 10000
    unclaim_reward = 10000
    core_reward = power_reward
    operators, consensuses = set_candidate
    delegate_power_success(operators[0], accounts[1], POWER_VALUE)
    turn_round()
    rate = 16000
    __mock_stake_hub_with_rewards({
        'core': set_rewards(core_reward, POWER_VALUE * rate * 100),
        'power': set_rewards(power_reward, POWER_VALUE),
    }, accounts[0], unclaim_reward)
    __set_btc_pool_rate(bonus_ratio)
    turn_round(consensuses)
    __set_is_stake_hub_active(2)
    additional_bonus = power_reward * Discount.lp_rates[15000] // Utils.DENOMINATOR - power_reward
    if additional_bonus > bonus_ratio[1]:
        additional_bonus = bonus_ratio[1]
    actual_reward = core_reward + power_reward + additional_bonus
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == actual_reward
    assert stake_hub.unclaimedReward() == power_reward - sum(bonus_ratio)


@pytest.mark.parametrize("bonus_ratio",
                         [[1000, 0, 0], [0, 3000, 0], [0, 4000, 0], [0, 5000, 0], [0, 0, 1000], [0, 0, 2000],
                          [0, 0, 3000], [1000, 4000, 4000], [3000, 2000, 2000], [1000, 4000, 2000], [1000, 2000, 3000],
                          [1000, 4000, 3000], [1000, 6000, 3000], [1000, 6000, 1000], [3000, 3000, 1000],
                          [3000, 0, 2000],
                          [2000, 1000, 0]
                          ])
def test_extra_reward_claim_success(btc_stake, set_candidate, btc_lst_stake, stake_hub, bonus_ratio):
    __set_lp_rates([[10000, 12000]])
    __set_is_btc_stake_active()
    __set_is_btc_lst_stake_active()
    btc_reward = 10000
    power_reward = 20000
    core_reward = 30000
    unclaim_reward = 10000
    operators, consensuses = set_candidate
    delegate_btc_success(operators[0], accounts[1], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    rewards = {
        'core': set_rewards(core_reward, DELEGATE_VALUE * 2),
        'power': set_rewards(power_reward, POWER_VALUE),
        'btc': set_rewards(btc_reward, BTC_VALUE),
    }
    __mock_stake_hub_with_rewards(rewards, accounts[0], unclaim_reward)
    __set_btc_pool_rate(bonus_ratio)
    turn_round(consensuses)
    __set_is_stake_hub_active(7)
    additional_bonus = 0
    for index, r in enumerate(rewards):
        if r == 'core':
            continue
        bonus = rewards[r]['reward'] * Discount.lp_rates[15000] // Utils.DENOMINATOR - rewards[r]['reward']
        if bonus > bonus_ratio[index]:
            bonus = bonus_ratio[index]
        additional_bonus += bonus
    actual_reward = core_reward + btc_reward + power_reward + additional_bonus
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == actual_reward
    assert stake_hub.unclaimedReward() == btc_reward - sum(bonus_ratio)


def test_claim_rewards_after_unclaimed_accumulation(btc_stake, set_candidate, btc_lst_stake, stake_hub):
    __set_is_btc_lst_stake_active(1)
    btc_reward = 10000
    unclaim_reward = 10000
    operators, consensuses = set_candidate
    delegate_btc_success(operators[0], accounts[1], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    rewards = {'btc': set_rewards(btc_reward, BTC_VALUE)}
    __mock_stake_hub_with_rewards(rewards, accounts[0], unclaim_reward)
    pool_rate = [1500, 2000, 2500]
    __set_btc_pool_rate(pool_rate)
    turn_round(consensuses)
    __set_is_stake_hub_active()
    bonus_amount = Utils.DENOMINATOR - sum(pool_rate) + btc_reward // 2
    assert stake_hub.unclaimedReward() == Utils.DENOMINATOR - sum(pool_rate)
    claim_stake_and_relay_reward(accounts[0])
    assert stake_hub.unclaimedReward() == bonus_amount
    bonus_reward = pool_rate[-1] + bonus_amount * pool_rate[-1] // Utils.DENOMINATOR
    turn_round(consensuses)
    __set_is_stake_hub_active(4)
    __set_lp_rates([[0, 30000]])
    __set_is_btc_lst_stake_active()
    __mock_stake_hub_with_rewards({'btc': set_rewards(btc_reward, BTC_VALUE)}, accounts[0])
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == btc_reward + bonus_reward
    assert stake_hub.unclaimedReward() == bonus_amount - bonus_amount * sum(pool_rate) // Utils.DENOMINATOR


def test_claim_success_after_bonus_depleted(btc_stake, set_candidate, btc_lst_stake, stake_hub):
    __set_is_btc_lst_stake_active(0)
    reward = 10000
    unclaim_reward = 10000
    operators, consensuses = set_candidate
    delegate_btc_success(operators[0], accounts[1], BTC_VALUE, LOCK_SCRIPT)
    turn_round()
    rewards = {
        'btc': set_rewards(reward, 100),
        'power': set_rewards(reward, 10),
        'core': set_rewards(reward, 1000),
    }
    __mock_stake_hub_with_rewards(rewards, accounts[0], unclaim_reward)
    pool_rate = [1000, 2000, 1000]
    __set_btc_pool_rate(pool_rate)
    turn_round(consensuses)
    assert stake_hub.unclaimedReward() == Utils.DENOMINATOR - sum(pool_rate)
    __set_is_stake_hub_active(7)
    __set_lp_rates([[0, 12000]])
    __set_is_btc_lst_stake_active()
    __mock_stake_hub_with_rewards(rewards, accounts[0])
    __mock_stake_hub_with_rewards(rewards, accounts[2])
    tracker0 = get_tracker(accounts[0])
    tracker1 = get_tracker(accounts[2])
    claim_stake_and_relay_reward(accounts[0])
    claim_stake_and_relay_reward(accounts[2])
    assert tracker0.delta() == reward * 3 + sum(pool_rate[:2])
    assert tracker1.delta() == reward * 3
    turn_round(consensuses)


def test_both_btc_lst_and_core_have_no_rewards(btc_stake, set_candidate, btc_lst_stake, stake_hub):
    __set_is_btc_lst_stake_active(1)
    __set_is_btc_stake_active(1)
    __set_tlp_rates([[0, 0]])
    operators, consensuses = set_candidate
    turn_round()
    delegate_btc_lst_success(accounts[0], BTC_VALUE, BTCLST_LOCK_SCRIPT, 0)
    delegate_btc_success(operators[1], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    turn_round(consensuses, round_count=2)
    tracker0 = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker0.delta() == 0
    turn_round(consensuses)


def test_core_reward_ratio_too_low_to_claim_rewards(set_candidate):
    __set_is_btc_lst_stake_active()
    __set_is_btc_stake_active()
    __set_lp_rates([[0, 0]])
    operators, consensuses = set_candidate
    turn_round()
    delegate_btc_lst_success(accounts[0], BTC_VALUE, BTCLST_LOCK_SCRIPT, 0)
    delegate_btc_success(operators[1], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    turn_round(consensuses, round_count=2)
    tracker0 = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker0.delta() == 0
    turn_round(consensuses)


def test_validator_joining_midway_and_claiming_rewards(set_candidate):
    operators, consensuses = set_candidate
    turn_round()
    delegate_btc_lst_success(accounts[0], BTC_VALUE, BTCLST_LOCK_SCRIPT, Utils.DENOMINATOR)
    turn_round(consensuses)
    operators.append(accounts[4])
    consensuses.append(register_candidate(operator=accounts[4]))
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker0.delta() == TOTAL_REWARD * 3 * 1000 // Utils.DENOMINATOR
    turn_round(consensuses, round_count=2)
    claim_stake_and_relay_reward(accounts[0])
    assert tracker0.delta() == TOTAL_REWARD * 7 * 1000 // Utils.DENOMINATOR
    turn_round(consensuses)
    claim_stake_and_relay_reward(accounts[0])
    assert tracker0.delta() == TOTAL_REWARD * 4 * 1000 // Utils.DENOMINATOR
    turn_round(consensuses)


def test_btc_expired_excluded_from_stake(btc_stake, set_candidate, btc_lst_stake):
    delegate_amount = 10000
    btc_amount = 1
    __set_lp_rates([[10000, 5000], [30000, 2000], [40000, 10000], [40001, 3000]])
    __set_is_stake_hub_active(4)
    operators, consensuses = set_candidate
    set_round_tag(LOCK_TIME // Utils.ROUND_INTERVAL - 3)
    # endRound = 20103
    # current_round = 20100
    turn_round()
    delegate_coin_success(operators[0], delegate_amount, accounts[0])
    # current_round = 20101
    delegate_btc_success(operators[1], accounts[0], btc_amount, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round(consensuses, round_count=5)
    # current_round = 20106
    # the effective staking duration of BTC is only 1 round, and Coin has 4 rounds, so the acc_stake_amount ratio is 1:40000
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == TOTAL_REWARD * 5


@pytest.mark.parametrize("round", [0, 1, 2, 3])
def test_acc_stake_amount_after_btc_transfer(btc_stake, set_candidate, btc_lst_stake, round):
    delegate_amount = 10000
    btc_amount = 1
    __set_lp_rates([[10000, 5000], [30000, 2000], [40000, 10000], [40001, 3000]])
    __set_is_stake_hub_active(4)
    operators, consensuses = set_candidate
    set_round_tag(LOCK_TIME // Utils.ROUND_INTERVAL - 3)
    turn_round()
    delegate_coin_success(operators[0], delegate_amount, accounts[0])
    tx_id = delegate_btc_success(operators[1], accounts[0], btc_amount, LOCK_SCRIPT, stake_duration=YEAR)
    transfer_btc_success(tx_id, operators[2], accounts[0])
    turn_round(consensuses, round_count=round)
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    btc_round = 0
    core_round = 0
    if round > 1:
        btc_round = 1
        core_round = round - 1
    btc_reward = TOTAL_REWARD * btc_round // 2
    core_reward = TOTAL_REWARD * core_round
    assert tracker.delta() == core_reward + btc_reward


def test_power_valid_for_one_round(btc_stake, set_candidate, btc_lst_stake):
    delegate_amount = 1000000
    power_value = 1
    __set_lp_rates([[10000, 5000], [30000, 2000], [40000, 10000], [40001, 3000]])
    __set_is_stake_hub_active(2)
    operators, consensuses = set_candidate
    set_round_tag(LOCK_TIME // Utils.ROUND_INTERVAL - 3)
    # endRound = 20103
    # current_round = 20100
    turn_round()
    delegate_coin_success(operators[0], delegate_amount, accounts[0])
    # current_round = 20101
    delegate_power_success(operators[1], accounts[0], power_value)
    turn_round(consensuses, round_count=5)
    # current_round = 20106
    # the effective staking duration of POWER is only 1 round, and Coin has 4 rounds, so the acc_stake_amount ratio is 1:40000
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == TOTAL_REWARD * 5


@pytest.mark.parametrize("stake_amounts", [
    [([0, 1000], [5000, 5000], [10000, 10000], [10001, 3000]), 10000000, 10, 2000],
    [([0, 1000], [5000, 5000], [10000, 10000], [10001, 3000]), 1000000, 1, 200],
    [([0, 1000], [5000, 10000], [10000, 5000], [10001, 3000]), 10000000, 20, 1000]]
                         )
def test_calc_stake_after_coin_unstake(btc_stake, set_candidate, btc_lst_stake, stake_amounts):
    delegate_amount = stake_amounts[1]
    power_value = stake_amounts[2]
    btc_value = stake_amounts[3]
    rates = stake_amounts[0]
    __set_lp_rates(rates)
    __set_is_stake_hub_active(7)
    operators, consensuses = set_candidate
    set_round_tag(LOCK_TIME // Utils.ROUND_INTERVAL - 3)
    turn_round()
    delegate_coin_success(operators[0], delegate_amount, accounts[0])
    delegate_power_success(operators[2], accounts[0], power_value)
    delegate_btc_success(operators[1], accounts[0], btc_value, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round(consensuses)
    undelegate_coin_success(operators[0], delegate_amount // 2, accounts[0])
    turn_round(consensuses, round_count=2)
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    power_reward = TOTAL_REWARD // power_value * power_value
    btc_reward = TOTAL_REWARD // 2
    coin_reward = TOTAL_REWARD + TOTAL_REWARD * Utils.CORE_STAKE_DECIMAL // delegate_amount * (
            delegate_amount // 2) // Utils.CORE_STAKE_DECIMAL
    assert tracker.delta() == power_reward + btc_reward + coin_reward


def test_calc_stake_after_coin_transfer(btc_stake, btc_lst_stake):
    delegate_amount = 1000000
    power_value = 1
    btc_value = 100
    __set_is_stake_hub_active(7)
    __set_lp_rates([[0, 1000], [20000, 10000], [20001, 1000]])
    operators = []
    consensuses = []
    for operator in accounts[5:9]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    set_round_tag(LOCK_TIME // Utils.ROUND_INTERVAL - 3)
    turn_round()
    delegate_coin_success(operators[0], delegate_amount, accounts[0])
    delegate_power_success(operators[2], accounts[0], power_value)
    delegate_btc_success(operators[1], accounts[0], btc_value, LOCK_SCRIPT, stake_duration=YEAR)
    turn_round(consensuses)
    transfer_coin_success(operators[0], operators[3], delegate_amount, accounts[0])
    turn_round(consensuses, round_count=2)
    tracker = get_tracker(accounts[0])
    claim_stake_and_relay_reward(accounts[0])
    power_reward = TOTAL_REWARD
    btc_reward = TOTAL_REWARD * Utils.BTC_DECIMAL // btc_value * btc_value // Utils.BTC_DECIMAL
    coin_reward = TOTAL_REWARD * 2
    assert tracker.delta() == power_reward + btc_reward + coin_reward


def __set_is_btc_stake_active(value=0):
    BTC_STAKE.setIsActive(value)


def __set_is_btc_lst_stake_active(value=0):
    BTC_LST_STAKE.setIsActive(value)


def __set_is_stake_hub_active(value=False):
    BTC_AGENT.setIsActive(value)


def __set_btc_pool_rate(value):
    STAKE_HUB.setBtcPoolRate(value)


def __set_tlp_rates(rates=None):
    BTC_STAKE.popTtlpRates()
    if rates:
        for r in rates:
            tl = r[0]
            tp = r[1]
            BTC_STAKE.setTlpRates(tl, tp)


def __set_lp_rates(rates=None):
    BTC_AGENT.popLpRates()
    if rates:
        for r in rates:
            tl = r[0]
            tp = r[1]
            BTC_AGENT.setLpRates(tl, tp)


def __get_candidate_bonus(tx):
    bonus = {
        'coin': {},
        'power': {},
        'btc': {}
    }
    for t in tx.events['roundReward']:
        # core
        if t['name'] == Web3.keccak(text='CORE').hex():
            for index, v in enumerate(t['validator']):
                bonus['coin'][v] = t['amount'][index]
            bonus['coin']['bonus'] = t['bonus']
        # power
        elif t['name'] == Web3.keccak(text='HASHPOWER').hex():
            for index, v in enumerate(t['validator']):
                bonus['power'][v] = t['amount'][index]
            bonus['power']['bonus'] = t['bonus']

        # btc
        elif t['name'] == Web3.keccak(text='BTC').hex():
            for index, v in enumerate(t['validator']):
                bonus['btc'][v] = t['amount'][index]
            bonus['btc']['bonus'] = t['bonus']

    return bonus


def __get_candidate_list_by_delegator(delegator):
    candidate_info = CORE_AGENT.getCandidateListByDelegator(delegator)
    return candidate_info


def __get_reward_map_info(delegate):
    rewards, unclaimed_reward = BTC_STAKE.getRewardMap(delegate)
    return rewards, unclaimed_reward


def __get_receipt_map_info(tx_id):
    receipt_map = BTC_STAKE.receiptMap(tx_id)
    return receipt_map


def __calc_stake_amount_discount(asset_reward, asset_stake_amount, coin_stake_amount, reward_pool=0,
                                 system_reward=100000000,
                                 asset_weight=1):
    lp_rates = Discount.lp_rates
    discount = Utils.DENOMINATOR
    stake_rate = int(coin_stake_amount / (asset_stake_amount / asset_weight))
    for i in lp_rates:
        if stake_rate >= i:
            discount = lp_rates[i]
            break
    print('__calc_stake_amount_discount>>>>>>', stake_rate, discount)
    actual_account_btc_reward = asset_reward * discount // Utils.DENOMINATOR
    if discount > Utils.DENOMINATOR:
        actual_bonus = actual_account_btc_reward - asset_reward
        if actual_bonus > reward_pool:
            system_reward -= actual_bonus * 10
            reward_pool += actual_bonus * 10
        reward_pool -= actual_bonus
    if asset_reward > actual_account_btc_reward:
        reward_pool += asset_reward - actual_account_btc_reward
    return actual_account_btc_reward, reward_pool


def __distribute_next_round_rewards(candidates, unclaimed, round_reward, btc_pool_rate=None):
    candidates_reward = {
        'coin': {},
        'power': {},
        'btc': {}
    }
    bonuses = [0, 0, 0]
    if btc_pool_rate is None:
        btc_pool_rate = Utils.DENOMINATOR
    unclaimed_reward = 0
    for u in unclaimed:
        unclaimed_reward += unclaimed[u]
    bonuses[2] = unclaimed_reward * btc_pool_rate // Utils.DENOMINATOR
    bonuses[0] = unclaimed_reward * (Utils.DENOMINATOR - btc_pool_rate) // Utils.DENOMINATOR
    for c in candidates_reward:
        total_reward = 0
        collateral_reward = round_reward[1][c]
        for i in collateral_reward:
            total_reward += collateral_reward[i]
        for i in collateral_reward:
            reward = collateral_reward[i]
            if c == 'coin':
                asset_bonus = bonuses[0]
            elif c == 'btc':
                asset_bonus = bonuses[2]
            else:
                asset_bonus = 0
            bonus = reward * asset_bonus // total_reward
            candidates_reward[c][i] = bonus

    return candidates_reward, bonuses


def __update_core_stake_amount(delegator, core_rate, asset_stake_amount):
    core_acc_stake_amount = asset_stake_amount * core_rate
    CORE_AGENT.setCoreRewardMap(delegator, 0, core_acc_stake_amount)
    return core_acc_stake_amount


def __calculate_compensation_reward_for_staking(operators, consensuses):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 50
    delegate_coin_success(operators[0], delegate_amount, accounts[0])
    delegate_coin_success(operators[1], delegate_amount, accounts[0])
    delegate_coin_success(operators[0], delegate_amount, accounts[1])
    delegate_coin_success(operators[1], delegate_amount, accounts[1])
    delegate_btc_success(operators[0], accounts[0], BTC_VALUE, LOCK_SCRIPT)
    delegate_btc_success(operators[1], accounts[0], BTC_VALUE * 2, LOCK_SCRIPT, stake_duration=150)
    round_time_tag = CANDIDATE_HUB.roundTag() - 6
    BTC_LIGHT_CLIENT.setMiners(round_time_tag, operators[2], [accounts[2]] * 100)
    turn_round()
    turn_round(consensuses)
    _, unclaimed_reward, account_rewards, round_reward, _ = parse_delegation([{
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
    claim_stake_and_relay_reward(accounts[0])
    assert tracker.delta() == account_rewards[accounts[0]]
    return (unclaimed_reward, round_reward)


def __calc_btc_deducted_stake_duration_reward(validator_reward, duration, tlp_rates=None):
    duration = duration * Utils.ROUND_INTERVAL
    if tlp_rates is None:
        tlp_rates = Discount.tlp_rates
    stake_duration = Utils.DENOMINATOR
    if len(tlp_rates) == 1:
        for t in tlp_rates:
            stake_duration = tlp_rates[t]
    for i in tlp_rates:
        time_stamp = i * Utils.MONTH_TIMESTAMP
        if duration >= time_stamp:
            stake_duration = tlp_rates[i]
            break
    if validator_reward is None:
        validator_reward = BLOCK_REWARD // 2
    btc_reward_claimed = validator_reward * stake_duration // Utils.DENOMINATOR
    unclaim_amount = validator_reward - btc_reward_claimed
    return btc_reward_claimed, unclaim_amount


def set_rewards(reward, delegate_amount):
    return {
        'reward': reward,
        'delegate_amount': delegate_amount
    }


def __mock_stake_hub_with_rewards(asset_reward, delegator, unclaimed_reward=None):
    accounts[3].transfer(STAKE_HUB, Web3.to_wei(1, 'ether'))
    for i in asset_reward:
        reward = asset_reward.get(i).get('reward', 0)
        delegate_amount = asset_reward.get(i).get('delegate_amount', 0)
        if i == 'core':
            __mock_core_reward_map(delegator, reward, delegate_amount)
        elif i == 'power':
            __mock_power_reward_map(delegator, reward, delegate_amount)
        else:
            __mock_btc_lst_reward_map(delegator, reward, delegate_amount)
    if unclaimed_reward:
        STAKE_HUB.setUnclaimedReward(unclaimed_reward)
