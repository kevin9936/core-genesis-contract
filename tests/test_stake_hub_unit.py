import pytest
import brownie
import rlp
from brownie import *
from web3 import Web3
from .calc_reward import parse_delegation, set_delegate
from .constant import *
from .delegate import delegate_btc_success, delegate_coin_success
from .utils import expect_event, update_system_contract_address, padding_left
from .common import register_candidate, turn_round, get_current_round, stake_hub_claim_reward
from collections import OrderedDict

MIN_INIT_DELEGATE_VALUE = 0
CANDIDATE_REGISTER_MARGIN = 0
candidate_hub_instance = None
core_agent_instance = None
btc_light_client_instance = None
required_coin_deposit = 0
TX_FEE = Web3.to_wei(1, 'ether')
# the tx fee is 1 ether
actual_block_reward = 0
COIN_REWARD = 0
BLOCK_REWARD = 0


@pytest.fixture()
def set_candidate():
    operators = []
    consensuses = []
    for operator in accounts[5:8]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    return operators, consensuses


@pytest.fixture(scope="module", autouse=True)
def set_up(min_init_delegate_value, core_agent, candidate_hub, btc_light_client, validator_set, stake_hub):
    global MIN_INIT_DELEGATE_VALUE
    global CANDIDATE_REGISTER_MARGIN
    global candidate_hub_instance
    global core_agent_instance
    global required_coin_deposit
    global btc_light_client_instance
    global actual_block_reward
    global COIN_REWARD
    global BLOCK_REWARD

    candidate_hub_instance = candidate_hub
    core_agent_instance = core_agent
    btc_light_client_instance = btc_light_client
    MIN_INIT_DELEGATE_VALUE = min_init_delegate_value
    CANDIDATE_REGISTER_MARGIN = candidate_hub.requiredMargin()
    required_coin_deposit = core_agent.requiredCoinDeposit()

    block_reward = validator_set.blockReward()
    block_reward_incentive_percent = validator_set.blockRewardIncentivePercent()
    total_block_reward = block_reward + TX_FEE
    actual_block_reward = total_block_reward * (100 - block_reward_incentive_percent) // 100
    tx_fee = 100
    BLOCK_REWARD = (block_reward + tx_fee) * ((100 - block_reward_incentive_percent) / 100)
    total_reward = BLOCK_REWARD // 2
    COIN_REWARD = total_reward * HardCap.CORE_HARD_CAP // HardCap.SUM_HARD_CAP
    STAKE_HUB = stake_hub


@pytest.fixture(scope="module", autouse=True)
def deposit_for_reward(validator_set):
    accounts[-10].transfer(validator_set.address, Web3.to_wei(100000, 'ether'))


def test_reinit(pledge_agent):
    with brownie.reverts("the contract already init"):
        pledge_agent.init()


def test_validators_and_rewards_length_mismatch_revert(validator_set):
    validators = [accounts[1], accounts[2]]
    reward_list = [1000]
    value_sum = sum(reward_list)
    with brownie.reverts('the length of validators and rewardList should be equal'):
        validator_set.addRoundRewardMock(validators, reward_list, 100,
                                         {'from': accounts[0], 'value': value_sum})


def test_only_validator_can_call_add_round_reward(stake_hub):
    validators = [accounts[1], accounts[2]]
    reward_list = [1000, 1000]
    value_sum = sum(reward_list)
    with brownie.reverts('the msg sender must be validatorSet contract'):
        stake_hub.addRoundReward(validators, reward_list, 100,
                                 {'from': accounts[0], 'value': value_sum})


def test_add_round_reward_success(validator_set, core_agent, btc_light_client, btc_stake, candidate_hub, stake_hub):
    round_tag = 100
    validators = [accounts[1], accounts[2]]
    reward_list = [1000, 2000]
    value_sum = sum(reward_list)
    power_value = 5
    core_value = 100
    btc_value = 10
    unclaimed_reward = 10000
    for validator in validators:
        core_agent.setCandidateMapAmount(validator, core_value, core_value, 0)
        btc_light_client.setMiners(round_tag - 7, validator, [accounts[0]] * power_value)
        btc_stake.setCandidateMap(validator, btc_value, btc_value, [])
    stake_hub.setUnclaimedReward(unclaimed_reward)
    candidate_hub.getScoreMock(validators, round_tag)
    tx = validator_set.addRoundRewardMock(validators, reward_list, round_tag,
                                          {'from': accounts[0], 'value': value_sum})
    for index, round_reward in enumerate(tx.events['roundReward']):
        amounts = []
        for v1, v2 in enumerate(validators):
            scores = stake_hub.getCandidateScoresMap(v2)
            reward = reward_list[v1] * scores[index + 1] // scores[0]
            amounts.append(reward)
        assert round_reward['amount'] == amounts


def test_add_asset_bonus_success(validator_set, core_agent, btc_light_client, btc_stake, candidate_hub, stake_hub):
    round_tag = 100
    validators = [accounts[1], accounts[2]]
    reward_list = [1000, 2000]
    value_sum = sum(reward_list)
    power_value = 5
    core_value = 100
    btc_value = 10
    unclaimed_reward = 10000
    for validator in validators:
        core_agent.setCandidateMapAmount(validator, core_value, core_value, 0)
        btc_light_client.setMiners(round_tag - 7, validator, [accounts[0]] * power_value)
        btc_stake.setCandidateMap(validator, btc_value, btc_value, [])
    stake_hub.setUnclaimedReward(unclaimed_reward)
    candidate_hub.getScoreMock(validators, round_tag)
    bonus_rate = [2000, 3000, 5000]
    stake_hub.setBtcPoolRate(bonus_rate)
    tx = validator_set.addRoundRewardMock(validators, reward_list, round_tag,
                                          {'from': accounts[0], 'value': value_sum})
    for index, round_reward in enumerate(tx.events['roundReward']):
        bonus_amount = unclaimed_reward * bonus_rate[index] // Utils.DENOMINATOR
        assert round_reward['bonus'] == bonus_amount
        assert stake_hub.assets(index)[-1] == bonus_amount
    assert stake_hub.unclaimedReward() == 0
    assert stake_hub.balance() == value_sum


def test_asset_bonus_accumulation(validator_set, core_agent, btc_light_client, btc_stake, candidate_hub, stake_hub):
    round_tag = 100
    validators = [accounts[1]]
    reward_list = [1000]
    value_sum = sum(reward_list)
    power_value = 5
    core_value = 100
    btc_value = 10
    unclaimed_reward = 10000
    for validator in validators:
        core_agent.setCandidateMapAmount(validator, core_value, core_value, 0)
        btc_light_client.setMiners(round_tag - 7, validator, [accounts[0]] * power_value)
        btc_stake.setCandidateMap(validator, btc_value, btc_value, [])
    stake_hub.setUnclaimedReward(unclaimed_reward)
    candidate_hub.getScoreMock(validators, round_tag)
    bonus_rate = [0, 2000, 2000]
    stake_hub.setBtcPoolRate(bonus_rate)
    tx = validator_set.addRoundRewardMock(validators, reward_list, round_tag,
                                          {'from': accounts[0], 'value': value_sum})
    bonus = []
    for index, round_reward in enumerate(tx.events['roundReward']):
        bonus_amount0 = unclaimed_reward * bonus_rate[index] // Utils.DENOMINATOR
        assert round_reward['bonus'] == bonus_amount0
        assert stake_hub.assets(index)[-1] == bonus_amount0
        bonus.append(bonus_amount0)
    unclaimed_reward = Utils.DENOMINATOR - sum(bonus_rate)
    assert stake_hub.unclaimedReward() == unclaimed_reward
    bonus_rate = [3000, 0, 1000]
    stake_hub.setBtcPoolRate(bonus_rate)
    tx = validator_set.addRoundRewardMock(validators, reward_list, round_tag,
                                          {'from': accounts[0], 'value': value_sum})
    for index, round_reward in enumerate(tx.events['roundReward']):
        bonus_amount1 = unclaimed_reward * bonus_rate[index] // Utils.DENOMINATOR
        assert round_reward['bonus'] == bonus_amount1
        assert stake_hub.assets(index)[-1] == bonus_amount1 + bonus[index]
    unclaimed_reward = Utils.DENOMINATOR - sum(bonus_rate)
    assert stake_hub.unclaimedReward() == unclaimed_reward - unclaimed_reward * sum(bonus_rate) // Utils.DENOMINATOR


def test_no_stake_on_validator(validator_set, core_agent, btc_light_client, btc_stake, candidate_hub, stake_hub):
    round_tag = 100
    validators = [accounts[1], accounts[2]]
    reward_list = [1000, 2000]
    value_sum = sum(reward_list)
    candidate_hub.getScoreMock(validators, round_tag)
    tx = validator_set.addRoundRewardMock(validators, reward_list, round_tag,
                                          {'from': accounts[0], 'value': value_sum})
    expect_event(tx, 'receiveDeposit', {
        'from': stake_hub.address,
        'amount': value_sum
    })


def test_reward_without_stake(validator_set, core_agent, btc_light_client, btc_stake, candidate_hub, stake_hub):
    round_tag = 100
    validators = [accounts[1], accounts[2]]
    reward_list = [0, 0]
    value_sum = sum(reward_list)
    power_value = 5
    core_value = 100
    btc_value = 10
    for validator in validators:
        core_agent.setCandidateMapAmount(validator, core_value, core_value, 0)
        btc_light_client.setMiners(round_tag - 7, validator, [accounts[0]] * power_value)
        btc_stake.setCandidateMap(validator, btc_value, btc_value, [])
    candidate_hub.getScoreMock(validators, round_tag)
    tx = validator_set.addRoundRewardMock(validators, reward_list, round_tag,
                                          {'from': accounts[0], 'value': value_sum})
    for round_reward in tx.events['roundReward']:
        assert round_reward['amount'] == [0, 0]


def test_only_candidate_can_call(validator_set, stake_hub):
    round_tag = 100
    validators = [accounts[1], accounts[2]]
    with brownie.reverts('the msg sender must be candidate contract'):
        stake_hub.getHybridScore(validators, round_tag)


@pytest.mark.parametrize("test", [
    pytest.param({'add_core': 10e18}, id="core"),
    pytest.param({'add_hash': 100}, id="hash"),
    pytest.param({'add_btc': 10e8}, id="btc"),
    pytest.param({'add_core': 1e18, 'add_hash': 200}, id="core & hash"),
    pytest.param({'add_core': 1e18, 'add_btc': 100e8}, id="core & btc"),
    pytest.param({'add_hash': 200, 'add_btc': 100e8}, id="hash & btc"),
    pytest.param({'add_core': 10e8, 'add_hash': 200, 'add_btc': 1000e8}, id="core & hash & btc"),
    pytest.param({'add_core': 1e8, 'add_hash': 100, 'add_btc': 10e8}, id="core & hash & btc"),
    pytest.param({'add_core': 0, 'add_hash': 0, 'add_btc': 0}, id="core & hash & btc"),
])
def test_get_hybrid_score_success(core_agent, btc_light_client, btc_stake, candidate_hub, stake_hub,
                                  hash_power_agent, btc_agent, test):
    round_tag = 100
    validators = [accounts[1], accounts[2]]
    core_value = test.get('add_core', 0)
    power_value = test.get('add_hash', 0)
    btc_value = test.get('add_btc', 0)
    values = [core_value, power_value, btc_value]
    for validator in validators[:1]:
        core_agent.setCandidateMapAmount(validator, core_value, core_value, 0)
        btc_light_client.setMiners(round_tag - 7, validator, [accounts[0]] * power_value)
        btc_stake.setCandidateMap(validator, btc_value, btc_value, [])
    tx = candidate_hub.getScoreMock(validators, round_tag)
    scores = tx.return_value
    hard_cap = [6000, 2000, 4000]
    factors = []
    factor0 = 0
    for index, h in enumerate(hard_cap):
        factor = 1
        if index == 0:
            factor0 = 1
        if index > 0 and values[0] != 0 and values[index] != 0:
            factor = (factor0 * core_value) * h // hard_cap[0] // values[index]
        factors.append(factor)
    assets = [core_agent, hash_power_agent, btc_agent]
    for index, asset in enumerate(assets):
        factor = stake_hub.stateMap(asset)
        assert factor == [values[index], int(factors[index])]
    candidate_scores = stake_hub.getCandidateScoresMap(validators[0])
    assert candidate_scores[0] == sum(candidate_scores[1:4])
    for index, score in enumerate(candidate_scores[1:]):
        assert score == values[index] * factors[index]
    assert scores == [candidate_scores[0], 0]


def test_calculate_factor_success(core_agent, btc_light_client, btc_stake, candidate_hub, stake_hub,
                                  hash_power_agent, btc_agent):
    round_tag = 100
    validators = [accounts[1]]
    core_value = 100e18
    power_value = 200
    for validator in validators[:1]:
        core_agent.setCandidateMapAmount(validator, core_value, core_value, 0)
        btc_light_client.setMiners(round_tag - 7, validator, [accounts[0]] * power_value)
    candidate_hub.getScoreMock(validators, round_tag)
    candidate_scores = stake_hub.getCandidateScoresMap(validators[0])
    assert candidate_scores[0] == sum(candidate_scores[1:4])
    assert candidate_scores[1] - candidate_scores[2] * 3 < 1000


def test_two_rounds_score_calculation_success(core_agent, btc_light_client, btc_stake, candidate_hub, stake_hub,
                                              hash_power_agent, btc_agent):
    round_tag = 100
    validators = [accounts[1]]
    core_value = 100e18
    power_value = 200
    btc_value = 200
    for validator in validators[:1]:
        core_agent.setCandidateMapAmount(validator, core_value, core_value, 0)
        btc_light_client.setMiners(round_tag - 7, validator, [accounts[0]] * power_value)
    candidate_hub.getScoreMock(validators, round_tag)
    candidate_scores = stake_hub.getCandidateScoresMap(validators[0])
    assert candidate_scores[-1] == 0
    btc_stake.setCandidateMap(validators[0], btc_value, btc_value, [])
    candidate_hub.getScoreMock(validators, round_tag)
    candidate_scores = stake_hub.getCandidateScoresMap(validators[0])
    assert candidate_scores[0] == sum(candidate_scores[1:4])
    assert candidate_scores[-1] != 0


def test_validators_score_calculation_success(core_agent, btc_light_client, btc_stake, candidate_hub, stake_hub,
                                              hash_power_agent, btc_agent):
    round_tag = 100
    validators = [accounts[1], accounts[2]]
    core_value = 100e18
    power_value = 200
    btc_value = 200
    for validator in validators:
        core_agent.setCandidateMapAmount(validator, core_value, core_value, 0)
        btc_light_client.setMiners(round_tag - 7, validator, [accounts[0]] * power_value)
        btc_stake.setCandidateMap(validators[0], btc_value, btc_value, [])
    tx = candidate_hub.getScoreMock(validators, round_tag)
    scores = tx.return_value
    actual_scores = []
    for v in validators:
        candidate_scores = stake_hub.getCandidateScoresMap(v)
        actual_scores.append(candidate_scores[0])
    assert scores == actual_scores


def test_only_candidate_can_call_set_new_round(stake_hub):
    with brownie.reverts("the msg sender must be candidate contract"):
        stake_hub.setNewRound(accounts[:2], 100)


def test_set_new_round_success(stake_hub, core_agent, btc_lst_stake, btc_stake):
    round_tag = 100
    update_system_contract_address(stake_hub, candidate_hub=accounts[0])
    stake_hub.setNewRound(accounts[:2], round_tag)
    assert core_agent.roundTag() == btc_lst_stake.roundTag() == btc_stake.roundTag() == round_tag


def test_only_operators_can_call(stake_hub, core_agent, btc_lst_stake, btc_stake):
    amount = 100
    with brownie.reverts("only debt operators"):
        stake_hub.addNotePayable(accounts[0], accounts[1], amount)


def test_add_note_payable_success(stake_hub, core_agent, btc_lst_stake, btc_stake, set_candidate):
    btc_value = 1000
    operators, consensuses = set_candidate
    lock_script = '0480db8767b17576a914574fdd26858c28ede5225a809f747c01fcc1f92a88ac'
    delegate_btc_success(operators[0], accounts[1], btc_value, lock_script, relay=accounts[1])
    turn_round()
    turn_round(consensuses)
    amount = 200
    stake_hub.setOperators(accounts[0], True)
    stake_hub.addNotePayable(accounts[1], accounts[2], amount)
    stake_hub_claim_reward(accounts[1])
    tx = stake_hub.claimRelayerReward({'from': accounts[2]})
    assert tx.events['claimedRelayerReward']['amount'] == amount


def test_only_pledge_agent_can_call(stake_hub):
    with brownie.reverts("the sender must be pledge agent contract"):
        stake_hub.proxyClaimReward(accounts[0])


def test_proxy_claim_reward_success(stake_hub, set_candidate):
    update_system_contract_address(stake_hub, pledge_agent=accounts[0])
    operators, consensuses = set_candidate
    delegate_coin_success(operators[0], MIN_INIT_DELEGATE_VALUE, accounts[2])
    delegate_coin_success(operators[0], MIN_INIT_DELEGATE_VALUE, accounts[0])
    turn_round(consensuses, round_count=2)
    tx = stake_hub.proxyClaimReward(accounts[2])
    expect_event(tx, 'claimedReward', {
        'delegator': accounts[2],
        'amount': BLOCK_REWARD // 4
    })


def test_calculate_reward_success(stake_hub, core_agent, btc_lst_stake, btc_stake, hash_power_agent, set_candidate):
    accounts[3].transfer(stake_hub, Web3.to_wei(1, 'ether'))
    reward = 10000
    actual_rewards = [reward, reward, reward // 2]
    core_agent.setCoreRewardMap(accounts[0], reward,0)
    btc_lst_stake.setBtcLstRewardMap(accounts[0], reward,0)
    hash_power_agent.setPowerRewardMap(accounts[0], reward,0)
    stake_hub.setIsActive(7)
    stake_hub.setLpRates(0, 5000)
    stake_hub.setOperators(accounts[3], True)
    amount = 1000
    stake_hub.addNotePayable(accounts[0], accounts[2], amount, {'from': accounts[3]})
    rewards, debt_amount, bonuses = stake_hub.calculateReward(accounts[0]).return_value
    converted_list = [x // 2 for x in actual_rewards]
    assert rewards == converted_list
    assert debt_amount == amount
    actual_bonuses = [-(x // 2) for x in actual_rewards]
    assert bonuses == actual_bonuses
    tx = stake_hub_claim_reward(accounts[0])
    


@pytest.mark.parametrize("lp_rates", [[
    (0, 1000), (1000, 5000), (30000, 10000),
    (0, 1000), (1000, 2000), (2000, 5000),
    (0, 5000), (12000, 10000), (20000, 12000)
]])
def test_claim_rewards_multiple_grades(stake_hub, core_agent, btc_lst_stake, hash_power_agent, lp_rates):
    accounts[3].transfer(stake_hub, Web3.to_wei(1, 'ether'))
    reward = 10000
    actual_rewards = [reward, reward, reward // 2]
    core_agent.setCoreRewardMap(accounts[0], reward)
    btc_lst_stake.setBtcLstRewardMap(accounts[0], reward)
    hash_power_agent.setPowerRewardMap(accounts[0], reward)
    stake_hub.setIsActive(7)
    for lp in lp_rates:
        stake_hub.setLpRates(lp[0], lp[1])
    rewards, debt_amount, bonuses = stake_hub.calculateReward(accounts[0]).return_value
    converted_list = [x // 2 for x in actual_rewards]
    assert rewards == converted_list
    actual_bonuses = [-(x // 2) for x in actual_rewards]
    assert bonuses == actual_bonuses


@pytest.mark.parametrize("bonus_amount", [
    [1000, 2000, 3000],
    [1000, 1000, 1000],
    [3000, 3000, 3000],
    [3000, 1999, 3001],
    [3000, 2001, 1999],
    [3000, 3000, 500]
])
def test_calc_claimable_rewards_with_bonus(stake_hub, core_agent, btc_lst_stake, hash_power_agent, bonus_amount):
    accounts[3].transfer(stake_hub, Web3.to_wei(1, 'ether'))
    reward = 10000
    stake_rewards = [reward, reward, reward]
    core_agent.setCoreRewardMap(accounts[0], reward)
    btc_lst_stake.setBtcLstRewardMap(accounts[0], reward)
    hash_power_agent.setPowerRewardMap(accounts[0], reward)
    stake_hub.setIsActive(6)
    btc_lst_stake.setIsActive(0)
    stake_hub.setAssetBonusAmount(bonus_amount[0], bonus_amount[1], bonus_amount[2])
    rate = 12000
    stake_hub.setLpRates(0, rate)
    rewards, debt_amount, bonuses = stake_hub.calculateReward(accounts[0]).return_value
    actual_rewards = [reward]
    actual_bonuses = [0]
    for index, reward in enumerate(stake_rewards[1:]):
        actual_bonus_amount = reward * rate // Utils.DENOMINATOR - reward
        if bonus_amount[index + 1] < actual_bonus_amount:
            actual_bonus_amount = bonus_amount[index + 1]
        actual_rewards.append(reward + actual_bonus_amount)
        actual_bonuses.append(actual_bonus_amount)
    assert rewards == actual_rewards
    assert bonuses == actual_bonuses


@pytest.mark.parametrize("fee", [
    3000,
    5000,
    10000,
    12000,
    20000
])
def test_calc_rewards_with_extra_fee(stake_hub, core_agent, btc_lst_stake, hash_power_agent, fee):
    accounts[3].transfer(stake_hub, Web3.to_wei(1, 'ether'))
    reward = 10000
    core_agent.setCoreRewardMap(accounts[0], reward)
    stake_hub.setOperators(accounts[3], True)
    stake_hub.addNotePayable(accounts[0], accounts[2], fee, {'from': accounts[3]})
    _, debt_amount, _ = stake_hub.calculateReward(accounts[0]).return_value
    remain_fee = 0
    debt_fee = fee
    if fee > reward:
        debt_fee = reward
        remain_fee = fee - reward
    assert debt_amount == debt_fee
    reward = 10000
    core_agent.setCoreRewardMap(accounts[0], reward)
    _, debt_amount, _ = stake_hub.calculateReward(accounts[0]).return_value
    assert remain_fee == debt_amount


def test_calc_rewards_with_multiple_fees(stake_hub, core_agent):
    accounts[3].transfer(stake_hub, Web3.to_wei(1, 'ether'))
    reward = 10000
    core_agent.setCoreRewardMap(accounts[0], reward)
    stake_hub.setOperators(accounts[3], True)
    fee0 = 3000
    fee1 = 3000
    stake_hub.addNotePayable(accounts[0], accounts[2], fee0, {'from': accounts[3]})
    stake_hub.addNotePayable(accounts[0], accounts[2], fee1, {'from': accounts[3]})
    _, debt_amount, _ = stake_hub.calculateReward(accounts[0]).return_value
    assert debt_amount == fee0 + fee1


def test_duplicate_relayer_reward_claim(stake_hub, core_agent):
    accounts[3].transfer(stake_hub, Web3.to_wei(1, 'ether'))
    reward = 10000
    core_agent.setCoreRewardMap(accounts[0], reward)
    stake_hub.setOperators(accounts[3], True)
    fee0 = 3000
    fee1 = 2000
    stake_hub.addNotePayable(accounts[0], accounts[2], fee0, {'from': accounts[3]})
    stake_hub.addNotePayable(accounts[0], accounts[2], fee1, {'from': accounts[3]})
    stake_hub_claim_reward(accounts[0])
    tx = stake_hub.claimRelayerReward({'from': accounts[0]})
    assert 'claimedRelayerReward' not in tx.events
    tx = stake_hub.claimRelayerReward({'from': accounts[2]})
    assert tx.events['claimedRelayerReward']['amount'] == fee0 + fee1
    tx = stake_hub.claimRelayerReward({'from': accounts[2]})
    assert 'claimedRelayerReward' not in tx.events


def test_only_govhub_can_call(stake_hub):
    grades_encode = rlp.encode([])
    with brownie.reverts("the msg sender must be governance contract"):
        stake_hub.updateParam('grades', grades_encode)


@pytest.mark.parametrize("grades", [
    [[0, 1000], [1000, 10000]],
    [[0, 1200], [2000, 2000], [3000, 10000]],
    [[0, 1000], [2000, 2000], [3000, 4000], [3500, 9000], [4000, 10000]],
    [[0, 1000], [3000, 2000], [12000, 4000], [19000, 9000], [22222, 10000]]
])
def test_update_param_grades_success(stake_hub, grades):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    grades_encode = rlp.encode(grades)
    stake_hub.updateParam('grades', grades_encode)
    for i in range(stake_hub.getGradesLength()):
        grades_value = stake_hub.grades(i)
        assert grades_value == grades[i]


def test_length_error_revert(stake_hub):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    grades_encode = rlp.encode([])
    with brownie.reverts("MismatchParamLength: grades"):
        stake_hub.updateParam('grades', grades_encode)


@pytest.mark.parametrize("grades", [
    [[0, 1000], [1000, 10000]],
    [[0, 1200], [2000, 2000], [3000, 10000]],
    [[0, 1000], [3000, 2000], [12000, 14000], [19000, 19000], [22222, 20000]]
])
def test_duplicate_update_grades(stake_hub, grades):
    old_grades = [[0, 1000], [2000, 10000]]
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    grades_encode = rlp.encode(old_grades)
    stake_hub.updateParam('grades', grades_encode)
    for i in range(stake_hub.getGradesLength()):
        grades_value = stake_hub.grades(i)
        assert grades_value == old_grades[i]
    grades_encode = rlp.encode(grades)
    stake_hub.updateParam('grades', grades_encode)
    for i in range(stake_hub.getGradesLength()):
        grades_value = stake_hub.grades(i)
        assert grades_value == grades[i]


@pytest.mark.parametrize("grades", [
    [[1000001, 1000], [1000, 10000]],
    [[0, 1000], [1000001, 2000], [3000, 10000]],
    [[0, 1000], [2000, 2000], [1000001, 10000]],
    [[0, 1000], [1000001, 2000], [1000001, 10000]],
])
def test_reward_rate_exceeds_limit_reverts(stake_hub, grades):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    grades_encode = rlp.encode(grades)
    with brownie.reverts(f"OutOfBounds: rewardRate, 1000001, 0, 1000000"):
        stake_hub.updateParam('grades', grades_encode)


def test_final_percentage_below_1_reverts(stake_hub):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    grades = [[0, 1000], [2000, 100001]]
    grades_encode = rlp.encode(grades)
    with brownie.reverts(f"OutOfBounds: last percentage, {grades[-1][-1]}, 10000, 100000"):
        stake_hub.updateParam('grades', grades_encode)


def test_non_last_percentage_exceeds_limit_reverts(stake_hub):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    grades = [[0, 1000], [2000, 11000], [3000, 12000]]
    grades_encode = rlp.encode(grades)
    with brownie.reverts("OutOfBounds: percentage, 11000, 1, 10000"):
        stake_hub.updateParam('grades', grades_encode)


@pytest.mark.parametrize("grades", [
    ['rewardRate', [0, 1000], [2000, 10000], [1000, 12000]],
    ['rewardRate', [0, 1000], [5000, 2000], [4000, 10000]],
    ['rewardRate', [0, 1000], [3000, 9000], [3000, 8000], [4000, 10000]],
    ['percentage', [0, 8000], [3000, 7000], [4000, 10000]],
    ['percentage', [0, 1000], [2000, 7000], [3000, 6000], [4000, 10000]]
])
def test_incorrect_reward_rate_percentage_order_reverts(stake_hub, grades):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    grades_encode = rlp.encode(grades[1:])
    with brownie.reverts(f"{grades[0]} disorder"):
        stake_hub.updateParam('grades', grades_encode)


def test_percentage_cannot_be_zero(stake_hub):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    grades_encode = rlp.encode([[1000, 0]])
    with brownie.reverts(f"OutOfBounds: last percentage, 0, 10000, 100000"):
        stake_hub.updateParam('grades', grades_encode)


@pytest.mark.parametrize("grade_active", [0, 1, 2, 3, 4, 5, 6, 7])
def test_update_param_grade_active_success(stake_hub, grade_active):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(grade_active), 64)
    stake_hub.updateParam('gradeActive', hex_value)
    assert stake_hub.gradeActive() == grade_active


@pytest.mark.parametrize("grade_active", [8, 9, 100, 1000])
def test_update_param_grade_active_failed(stake_hub, grade_active):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(grade_active), 64)
    with brownie.reverts(f"OutOfBounds: gradeActive, {grade_active}, 0, 7"):
        stake_hub.updateParam('gradeActive', hex_value)


def test_update_param_grade_active_length_failed(stake_hub):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(0), 65)
    with brownie.reverts(f"MismatchParamLength: gradeActive"):
        stake_hub.updateParam('gradeActive', hex_value)


@pytest.mark.parametrize("hard_cap", [
    [['coreHardcap', 2000], ['hashHardcap', 9000], ['btcHardcap', 10000]],
    [['coreHardcap', 1000], ['hashHardcap', 2000], ['btcHardcap', 8000]],
    [['coreHardcap', 100000], ['hashHardcap', 20000], ['btcHardcap', 30000]],
    [['coreHardcap', 10000], ['hashHardcap', 100000], ['btcHardcap', 30000]],
    [['coreHardcap', 10000], ['hashHardcap', 10000], ['btcHardcap', 100000]]
])
def test_update_hard_cap_success(stake_hub, hard_cap):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    for h in hard_cap:
        hex_value = padding_left(Web3.to_hex(h[1]), 64)
        stake_hub.updateParam(h[0], hex_value)
    for i in range(3):
        assert stake_hub.assets(i)['hardcap'] == hard_cap[i][-1]


@pytest.mark.parametrize("hard_cap", [
    ['coreHardcap', 100001],
    ['hashHardcap', 100001],
    ['btcHardcap', 100001],
    ['btcHardcap', 200002],
])
def test_update_hard_cap_failed(stake_hub, hard_cap):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(hard_cap[1]), 64)
    with brownie.reverts(f"OutOfBounds: {hard_cap[0]}, {hard_cap[1]}, 1, 100000"):
        stake_hub.updateParam(hard_cap[0], hex_value)


@pytest.mark.parametrize("bonus", [
    [['coreBonusRate', 2000], ['hashBonusRate', 3000], ['btcBonusRate', 5000]],
    [['coreBonusRate', 0], ['hashBonusRate', 2000], ['btcBonusRate', 8000]],
    [['coreBonusRate', 5000], ['hashBonusRate', 0], ['btcBonusRate', 5000]],
    [['coreBonusRate', 7000], ['hashBonusRate', 3000], ['btcBonusRate', 0]],
    [['coreBonusRate', 2000], ['hashBonusRate', 0], ['btcBonusRate', 2000]],
    [['coreBonusRate', 2000], ['hashBonusRate', 3000], ['btcBonusRate', 2000]],
    [['coreBonusRate', 0], ['hashBonusRate', 0], ['btcBonusRate', 0]],
])
def test_update_bonus_rate_success(stake_hub, bonus):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    old_bonus = [['coreBonusRate', 0], ['hashBonusRate', 0], ['btcBonusRate', 0]]
    for o in old_bonus:
        hex_value = padding_left(Web3.to_hex(o[1]), 64)
        stake_hub.updateParam(o[0], hex_value)
    for h in bonus:
        hex_value = padding_left(Web3.to_hex(h[1]), 64)
        stake_hub.updateParam(h[0], hex_value)
    for i in range(3):
        assert stake_hub.assets(i)['bonusRate'] == bonus[i][-1]


def test_bonus_rate_exceeds_max_limit_reverts(stake_hub):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    bonus = [['coreBonusRate', 10001], ['hashBonusRate', 10002], ['btcBonusRate', 30000]]
    for b in bonus:
        hex_value = padding_left(Web3.to_hex(b[1]), 64)
        with brownie.reverts(f"OutOfBounds: {b[0]}, {b[1]}, 0, 10000"):
            stake_hub.updateParam(b[0], hex_value)


def test_total_bonus_rate_exceeds_max_limit_reverts(stake_hub):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    old_bonus = [['coreBonusRate', 0], ['hashBonusRate', 0], ['btcBonusRate', 0]]
    for o in old_bonus:
        hex_value = padding_left(Web3.to_hex(o[1]), 64)
        stake_hub.updateParam(o[0], hex_value)
    bonus = [['coreBonusRate', 3000], ['hashBonusRate', 2000]]
    for index, b in enumerate(bonus):
        hex_value = padding_left(Web3.to_hex(b[1]), 64)
        stake_hub.updateParam(b[0], hex_value)
    hex_value = padding_left(Web3.to_hex(5001), 64)
    with brownie.reverts(f"the sum of bonus rates out of bound."):
        stake_hub.updateParam('btcBonusRate', hex_value)


def test_update_param_nonexistent_governance_param_reverts(stake_hub):
    update_system_contract_address(stake_hub, gov_hub=accounts[0])
    with brownie.reverts(f"UnsupportedGovParam: error"):
        hex_value = padding_left(Web3.to_hex(100), 64)
        stake_hub.updateParam('error', hex_value)


def test_stake_hup_add_round_reward(stake_hub, validator_set, candidate_hub, core_agent, btc_light_client, btc_stake):
    turn_round()
    register_candidate(operator=accounts[1])
    register_candidate(operator=accounts[2])

    tests = [
        {'status': 'success', 'validators': [], 'reward_list': [], 'round': 100,
         'expect_round_reward': [OrderedDict([('round', 100), ('validator', ()), ('amount', ()), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('validator', ()), ('amount', ()), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('validator', ()), ('amount', ()), ('bonus', 0)])]},

        {'status': 'success', 'validators': [accounts[1]], 'reward_list': [100], 'round': 100,
         'expect_round_reward': [OrderedDict([('round', 100), ('amount', (0,)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0,)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0,)), ('bonus', 0)])]},

        {'status': 'success', 'validators': [accounts[1], accounts[2]], 'reward_list': [100, 200], 'round': 100,
         'expect_round_reward': [OrderedDict([('round', 100), ('amount', (0, 0)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0, 0)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0, 0)), ('bonus', 0)])]},

        {'status': 'success', 'validators': [accounts[1]], 'reward_list': [100], 'round': 100,
         'add_core': [(accounts[1], 100)],
         'expect_round_reward': [OrderedDict([('round', 100), ('amount', (100,)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0,)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0,)), ('bonus', 0)])]},

        {'status': 'success', 'validators': [accounts[1], accounts[2]], 'reward_list': [100, 100], 'round': 100,
         'add_core': [(accounts[1], 100), (accounts[2], 100)],
         'expect_round_reward': [OrderedDict([('round', 100), ('amount', (100, 100)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0, 0)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0, 0)), ('bonus', 0)])]},

        {'status': 'success', 'validators': [accounts[1]], 'reward_list': [100], 'round': 100,
         'add_core': [(accounts[1], 100)], 'add_pow': [(accounts[1], [accounts[0]])],
         'expect_round_reward': [OrderedDict([('round', 100), ('amount', (75,)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (24,)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0,)), ('bonus', 0)])]},

        {'status': 'success', 'validators': [accounts[1], accounts[1]], 'reward_list': [100, 100], 'round': 100,
         'add_core': [(accounts[1], 100), (accounts[2], 100)], 'add_pow': [(accounts[1], [accounts[0]])],
         'expect_round_reward': [OrderedDict([('round', 100), ('amount', (75, 75)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (24, 24)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (0, 0)), ('bonus', 0)])]},

        {'status': 'success', 'validators': [accounts[1]], 'reward_list': [100], 'round': 100,
         'add_core': [(accounts[1], 100)], 'add_pow': [(accounts[1], [accounts[0]])],
         'add_btc': [(accounts[1], 1, 1, [])],
         'expect_round_reward': [OrderedDict([('round', 100), ('amount', (50,)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (16,)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (33,)), ('bonus', 0)])]},

        {'status': 'success', 'validators': [accounts[1], accounts[1]], 'reward_list': [100, 100], 'round': 100,
         'add_core': [(accounts[1], 100), (accounts[2], 100)], 'add_pow': [(accounts[1], [accounts[0]])],
         'add_btc': [(accounts[1], 1, 1, []), (accounts[2], 1, 1, [])],
         'expect_round_reward': [OrderedDict([('round', 100), ('amount', (50, 50)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (16, 16)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (33, 33)), ('bonus', 0)])]},

        {'status': 'success', 'validators': [accounts[1], accounts[1]], 'reward_list': [100, 100], 'round': 100,
         'add_core': [(accounts[1], 100), (accounts[2], 100)], 'add_pow': [(accounts[1], [accounts[0]])],
         'add_btc': [(accounts[1], 1, 1, []), (accounts[2], 1, 1, [])], 'unclaimed_reward': 10,
         'expect_round_reward': [OrderedDict([('round', 100), ('amount', (50, 50)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (16, 16)), ('bonus', 0)]),
                                 OrderedDict([('round', 100), ('amount', (33, 33)), ('bonus', 10)])]},

        {'status': 'failed', 'err': 'the length of validators and rewardList should be equal',
         'validators': [accounts[1], accounts[2]], 'reward_list': [100], 'round': 100, 'expect_round_reward': []},
    ]

    for test in tests:
        print(f'case{tests.index(test)}:', test)
        value_sum = 0
        for v in test['reward_list']:
            value_sum += v
        if 'add_core' in test:
            for validator, v in test['add_core']:
                core_agent.setCandidateMapAmount(validator, v, v, 0)
        if 'add_pow' in test:
            for v1, v2 in test['add_pow']:
                btc_light_client.setMiners(test['round'] - 7, v1, v2)
        if 'add_btc' in test:
            for validator, v1, v2, arr in test['add_btc']:
                btc_stake.setCandidateMap(validator, v1, v2, arr)
        if 'unclaimed_reward' in test:
            stake_hub.setUnclaimedReward(test['unclaimed_reward'])
        tx = candidate_hub.getScoreMock(test['validators'], test['round'])
        if test['status'] == 'success':
            tx = validator_set.addRoundRewardMock(test['validators'], test['reward_list'], test['round'],
                                                  {'from': accounts[0], 'value': value_sum})
            print(tx.events['roundReward'])
            for i in range(len(test['expect_round_reward'])):
                expect_event(tx, 'roundReward', test['expect_round_reward'][i], i)
        else:
            with brownie.reverts(test['err']):
                validator_set.addRoundRewardMock(test['validators'], test['reward_list'], test['round'],
                                                 {'from': accounts[0], 'value': value_sum})


def test_stake_hup_get_hybrid_score(stake_hub, validator_set, candidate_hub, core_agent, btc_light_client, btc_stake):
    turn_round()
    register_candidate(operator=accounts[1])
    register_candidate(operator=accounts[2])

    tests = [
        {'status': 'success', 'validators': [], 'round': 100, 'expect_scores': ()},
        {'status': 'success', 'validators': [accounts[1]], 'round': 100, 'expect_scores': [(0, 0, 0, 0)]},
        {'status': 'success', 'validators': [accounts[1]], 'round': 100, 'add_core': [(accounts[1], 100)],
         'expect_scores': [(100, 100, 0, 0)]},
        {'status': 'success', 'validators': [accounts[1]], 'round': 100, 'add_core': [(accounts[1], 100)],
         'add_pow': [(accounts[1], [accounts[0]])], 'expect_scores': [(133, 100, 33, 0)]},
        {'status': 'success', 'validators': [accounts[1]], 'round': 100, 'add_core': [(accounts[1], 100)],
         'add_pow': [(accounts[1], [accounts[0]])], 'add_btc': [(accounts[1], 1, 1, [])],
         'expect_scores': [(199, 100, 33, 66)]},
        {'status': 'success', 'validators': [accounts[1], accounts[2]], 'round': 100,
         'add_core': [(accounts[1], 100), (accounts[2], 200)],
         'add_pow': [(accounts[1], [accounts[0]]), (accounts[2], [accounts[0]])],
         'add_btc': [(accounts[1], 1, 1, []), (accounts[2], 1, 1, [])],
         'expect_scores': [(250, 100, 50, 100), (350, 200, 50, 100)]}
    ]

    for test in tests:
        print(f'case{tests.index(test)}:', test)
        if 'add_core' in test:
            for validator, v in test['add_core']:
                core_agent.setCandidateMapAmount(validator, v, v, 0)
        if 'add_pow' in test:
            for v1, v2 in test['add_pow']:
                btc_light_client.setMiners(test['round'] - 7, v1, v2)
        if 'add_btc' in test:
            for validator, v1, v2, arr in test['add_btc']:
                btc_stake.setCandidateMap(validator, v1, v2, arr)
        if test['status'] == 'success':
            tx = candidate_hub.getScoreMock(test['validators'], test['round'])
            for validator, expect_score in zip(test['validators'], test['expect_scores']):
                assert stake_hub.getCandidateScores(validator) == expect_score


def test_stake_hup_calculate_reward(stake_hub, validator_set, candidate_hub, core_agent, btc_light_client, btc_stake):
    turn_round()
    register_candidate(operator=accounts[1])
    register_candidate(operator=accounts[2])

    tests = [
        {'status': 'success', 'delegator': accounts[1], 'expect_rewards': (0, 0, 0), 'expect_debt_amount': 0},
        {'status': 'success', 'delegator': accounts[1], 'add_core': [(accounts[1], 100, 0)],
         'expect_rewards': (100, 0, 0), 'expect_debt_amount': 0},
        {'status': 'success', 'delegator': accounts[1], 'add_core': [(accounts[1], 10000, 0)],
         'add_btc': [(accounts[1], 10000, 0)], 'expect_rewards': (10000, 0, 10000), 'expect_debt_amount': 0},
        {'status': 'success', 'delegator': accounts[1], 'add_core': [(accounts[1], 10000, 0)],
         'add_btc': [(accounts[1], 10000, 0)], 'set_grades': (1000, 5000, 4000, 7000, 5000, 8000, 10000, 10000),
         'expect_rewards': (10000, 0, 10000), 'expect_debt_amount': 0},
        {'status': 'success', 'delegator': accounts[1], 'add_core': [(accounts[1], 10000, 0)],
         'add_btc': [(accounts[1], 20000, 0)], 'set_grades': (1000, 5000, 4000, 7000, 5000, 8000, 10000, 10000),
         'expect_rewards': (10000, 0, 16000), 'expect_debt_amount': 0},
        {'status': 'success', 'delegator': accounts[1], 'add_core': [(accounts[1], 10000, 0)],
         'add_btc': [(accounts[1], 100000, 0)], 'set_grades': (1000, 5000, 4000, 7000, 5000, 8000, 10000, 10000),
         'expect_rewards': (10000, 0, 50000), 'expect_debt_amount': 0},

    ]

    for test in tests:
        print(f'case{tests.index(test)}:', test)
        if 'add_core' in test:
            for delegator, v1, v2 in test['add_core']:
                core_agent.setCoreRewardMap(delegator, v1, v2)
        # if 'add_pow' in test:
        #     for v1, v2 in test['add_pow']:
        #         btc_light_client.setMiners(test['round']-7, v1, v2)
        if 'add_btc' in test:
            for validator, v1, v2 in test['add_btc']:
                btc_stake.setCoreRewardMap(validator, v1, v2)
        if 'set_grades' in test:
            stake_hub.setInitLpRates(*test['set_grades'])
        if test['status'] == 'success':
            assert stake_hub.calculateReward(test['delegator']).return_value[:2] == (
                test['expect_rewards'], test['expect_debt_amount'])
