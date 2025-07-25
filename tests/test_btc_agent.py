import pytest
import brownie
import rlp
from web3 import constants
from .delegate import *
from .utils import expect_event, padding_left, update_system_contract_address
from .common import turn_round, get_current_round, register_candidate, set_round_tag

TOTAL_REWARD = None
TX_FEE = 100
# BTC delegation-related
LOCK_SCRIPT = "0480db8767b17576a914574fdd26858c28ede5225a809f747c01fcc1f92a88ac"
LOCK_TIME = 1736956800
stake_manager = StakeManager()
round_reward_manager = RoundRewardManager()


@pytest.fixture(scope="module", autouse=True)
def set_up(btc_stake, stake_hub, btc_agent, core_agent, hash_power_agent, validator_set, gov_hub):
    global BTC_STAKE, STAKE_HUB, BTC_AGENT, CORE_AGENT, HASH_POWER_AGENT, TOTAL_REWARD
    BTC_STAKE = btc_stake
    STAKE_HUB = stake_hub
    BTC_AGENT = btc_agent
    CORE_AGENT = core_agent
    HASH_POWER_AGENT = hash_power_agent
    btc_agent.setAssetWeight(1)
    block_reward = validator_set.blockReward()
    block_reward_incentive_percent = validator_set.blockRewardIncentivePercent()
    total_block_reward = block_reward + TX_FEE
    BLOCK_REWARD = total_block_reward * \
                   ((100 - block_reward_incentive_percent) / 100)
    TOTAL_REWARD = BLOCK_REWARD // 2
    set_block_time_stamp(150, LOCK_TIME)


@pytest.fixture(scope="module", autouse=True)
def deposit_for_reward(validator_set, gov_hub, system_reward):
    accounts[99].transfer(validator_set.address, Web3.to_wei(100000, 'ether'))
    accounts[99].transfer(gov_hub.address, Web3.to_wei(100000, 'ether'))
    accounts[99].transfer(system_reward.address, Web3.to_wei(100000, 'ether'))


@pytest.fixture()
def set_candidate():
    operators = []
    consensuses = []
    for operator in accounts[5:8]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    return operators, consensuses


def set_rewards(reward, delegate_amount, unclaimed_reward=0):
    return {
        'reward': reward,
        'delegate_amount': delegate_amount,
        'unclaimed_reward': unclaimed_reward,
    }


def test_btc_agent_init_once_only(btc_agent):
    with brownie.reverts("the contract already init"):
        btc_agent.init()


@pytest.mark.skip(reason="the data migration part has been removed, skip it.")
def test_initialize_from_pledge_agent_success(btc_agent):
    candidates = accounts[:3]
    amounts = [100, 200, 300]
    update_system_contract_address(btc_agent, pledge_agent=accounts[0])
    btc_agent._initializeFromPledgeAgent(candidates, amounts)
    for index, candidate in enumerate(candidates):
        assert btc_agent.candidateMap(candidate)[1] == amounts[index]


@pytest.mark.skip(reason="the data migration part has been removed, skip it.")
def test_only_pledge_agent_can_call(btc_agent):
    candidates = accounts[:3]
    amounts = [100, 200, 300]
    with brownie.reverts("the sender must be pledge agent contract"):
        btc_agent._initializeFromPledgeAgent(candidates, amounts)


@pytest.mark.parametrize('lst_btc_amount', [0, 4000])
def test_distribute_reward_success(btc_agent, btc_stake, lst_btc_amount):
    history_reward = 200
    turn_round()
    round_tag = get_current_round()
    candidates = accounts[:3]
    btc_amount = 1000
    rewards = [10000, 20000, 30000]
    set_round_tag(round_tag - 1)
    round_tag += 2
    btc_stake.setRoundTag(round_tag)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    for c in candidates:
        btc_agent.setCandidateMap(c, lst_btc_amount, btc_amount)
        btc_stake.setCandidateMap(c, btc_amount, btc_amount, [round_tag - 1])
        btc_stake.setAccruedRewardPerBTCMap(c, round_tag - 1, history_reward)
    btc_agent.distributeReward(candidates, rewards, 0)
    for index, c in enumerate(candidates):
        reward = rewards[index]
        assert btc_stake.accruedRewardPerBTCMap(c,
                                                round_tag) == history_reward + reward * Utils.BTC_DECIMAL // btc_amount


def test_validators_and_reward_list_length_mismatch_failed(btc_agent):
    candidates = accounts[:3]
    rewards = [10000, 20000]
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    with brownie.reverts():
        btc_agent.distributeReward(candidates, rewards, 0)


def test_only_stake_hub_can_call_distribute_reward(btc_agent):
    candidates = accounts[:3]
    rewards = [10000, 20000, 30000]
    with brownie.reverts("the msg sender must be stake hub contract"):
        btc_agent.distributeReward(candidates, rewards, 0)


def test_reward_not_zero_with_zero_staked_tokens(btc_agent, btc_stake):
    turn_round()
    round_tag = get_current_round()
    candidates = accounts[:3]
    rewards = [10000, 20000, 30000]
    set_round_tag(round_tag - 1)
    round_tag += 2
    btc_stake.setRoundTag(round_tag)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    btc_agent.distributeReward(candidates, rewards, 0)
    assert btc_stake.accruedRewardPerBTCMap(
        candidates[0], get_current_round()) == 0


def test_reward_zero_with_staked_tokens(btc_agent, btc_stake):
    candidates = accounts[:3]
    rewards = [0, 0, 0]
    round_tag = get_current_round() + 2
    btc_stake.setRoundTag(round_tag)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    btc_agent.distributeReward(candidates, rewards, 0)
    for index, c in enumerate(candidates):
        assert btc_stake.accruedRewardPerBTCMap(c, round_tag) == 0


def test_reward_zero_with_nonzero_stake(btc_agent, btc_stake):
    turn_round()
    btc_amount = 2000
    candidates = accounts[:3]
    rewards = [0, 0, 0]
    round_tag = get_current_round() + 2
    btc_stake.setRoundTag(round_tag)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    for c in candidates:
        btc_agent.setCandidateMap(c, 0, btc_amount)
        btc_stake.setCandidateMap(c, btc_amount, btc_amount, [round_tag - 1])
        btc_stake.setAccruedRewardPerBTCMap(c, round_tag - 1, 100)
    btc_agent.distributeReward(candidates, rewards, 0)
    for index, c in enumerate(candidates):
        assert btc_stake.accruedRewardPerBTCMap(c, round_tag) == 0


def test_get_stake_amounts_success(btc_agent, btc_stake, set_candidate):
    btc_amount = 3000
    operators, consensuses = set_candidate
    turn_round()
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    btc_agent.getStakeAmounts(operators, 0)
    for o in operators:
        btc_stake.setCandidateMap(o, btc_amount, btc_amount, [])
    amounts, total_amount = btc_agent.getStakeAmounts(
        operators, 0).return_value
    assert amounts == [btc_amount, btc_amount, btc_amount]
    assert total_amount == btc_amount * 3


def test_query_address_empty(btc_agent, btc_stake, set_candidate):
    operators = []
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    amounts, total_amount = btc_agent.getStakeAmounts(
        operators, 0).return_value
    assert sum(amounts) == total_amount == 0


def test_query_address_zero(btc_agent, btc_stake, set_candidate):
    operators = ZERO_ADDRESS
    turn_round()
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    amounts, total_amount = btc_agent.getStakeAmounts(
        [operators], 0).return_value
    assert sum(amounts) == total_amount == 0


def test_only_stake_hub_can_call(btc_agent, btc_stake, set_candidate):
    operators, consensuses = set_candidate
    turn_round()
    with brownie.reverts("the msg sender must be stake hub contract"):
        btc_agent.getStakeAmounts(operators, 0)


def test_set_new_round_success(btc_agent, btc_stake, set_candidate):
    btc_amount = 3000
    operators, consensuses = set_candidate
    round_tag = 7
    assert btc_stake.roundTag() == round_tag
    turn_round()
    round_tag += 1
    for o in operators:
        btc_stake.setCandidateMap(o, 0, btc_amount, [])
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    btc_agent.setNewRound(operators, get_current_round())
    for op in operators:
        assert btc_stake.candidateMap(op) == [btc_amount, btc_amount]
    assert btc_stake.roundTag() == round_tag


def test_only_stake_hub_can_call_set_new_round(btc_agent, btc_stake, set_candidate):
    with brownie.reverts("the msg sender must be stake hub contract"):
        btc_agent.setNewRound(accounts[:3], get_current_round())


def test_only_stake_hub_can_call_claim_reward(btc_agent):
    with brownie.reverts("the msg sender must be stake hub contract"):
        btc_agent.claimReward(constants.ADDRESS_ZERO, 1000, 1, False)


@pytest.mark.parametrize("grade", [True, False])
def test_reward_claiming_after_grade_update(btc_agent, grade):
    rates = [[0, 1000], [10000, 5000], [12000, 10000]]
    stake_manager.set_lp_rates(rates)
    btc_reward = 20000
    btc_amount = 1
    core_reward = 10000
    rate = 5000
    stake_manager.set_is_stake_hub_active(grade)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    round_reward_manager.mock_btc_reward_map(
        accounts[0], btc_reward, 0, btc_amount)
    reward = btc_agent.claimReward(
        accounts[0], core_reward, get_current_round() - 1, False).return_value
    if grade:
        float_reward = -btc_reward // 2
        actual_reward = btc_reward * rate // Utils.DENOMINATOR
    else:
        actual_reward = btc_reward
        float_reward = 0
    assert reward == [actual_reward, float_reward, btc_amount]


def test_grades_not_set(btc_agent):
    stake_manager.set_lp_rates()
    btc_reward = 20000
    btc_amount = 1
    core_reward = 10000
    stake_manager.set_is_stake_hub_active(True)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    round_reward_manager.mock_btc_reward_map(
        accounts[0], btc_reward, 0, btc_amount)
    reward = btc_agent.claimReward(
        accounts[0], core_reward, get_current_round() - 1, False).return_value
    assert reward[0] == btc_reward


@pytest.mark.parametrize("grades", [
    [[0, 5000]],
    [[0, 1000], [5000, 5000]],
    [[0, 1000], [5000, 5000], [10000, 10000]],
    [[0, 1000], [5000, 5000], [10000, 10000], [11000, 12000]]
])
def test_grades_length_mismatch(btc_agent, grades):
    stake_manager.set_lp_rates(grades)
    btc_reward = 20000
    btc_amount = 10
    core_reward = 50000
    stake_manager.set_is_stake_hub_active(True)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    round_reward_manager.mock_btc_reward_map(
        accounts[0], btc_reward, 0, btc_amount)
    reward = btc_agent.claimReward(
        accounts[0], core_reward, get_current_round() - 1, False).return_value
    assert reward[0] == btc_reward // 2


@pytest.mark.parametrize("tests", [
    [[[0, 5000]], 10000, 10, 20000, 5000],
    [[[0, 2000], [1000, 3000]], 10000, 20, 20000, 3000],
    [[[0, 2000], [1000, 3000], [10000, 15000]], 10000, 10, 100000, 15000],
])
def test_update_core_amount_and_claim_reward(btc_agent, tests):
    grades = tests[0]
    stake_manager.set_lp_rates(grades)
    btc_reward = tests[1]
    btc_amount = tests[2]
    core_amount = tests[3]
    actual_btc_reward = tests[4]
    unclaimed_reward = actual_btc_reward - btc_reward
    stake_manager.set_is_stake_hub_active(True)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    round_reward_manager.mock_btc_reward_map(
        accounts[0], btc_reward, 0, btc_amount)
    reward = btc_agent.claimReward.call(
        accounts[0], core_amount, get_current_round() - 2, False)
    assert reward == [actual_btc_reward, unclaimed_reward, btc_amount]
    tx = btc_agent.claimReward(
        accounts[0], core_amount, get_current_round() - 2, False)
    dual_staking_rate = actual_btc_reward
    expect_event(tx, 'storedBtcReward', {
        'delegator': accounts[0],
        'amount': actual_btc_reward,
        'unclaimedAmount': 0,
        'floatReward': unclaimed_reward,
        'accStakedAmount': btc_amount,
        'dualStakingRate': dual_staking_rate
    })


@pytest.mark.parametrize("claim", [True, False])
@pytest.mark.parametrize("tests", [
    [[[0, 5000]], 10000, 1, 2000, 5000],
    [[[0, 2000], [1000, 3000]], 10000, 20, 20000, 3000],
    [[[0, 2000], [1000, 3000], [10000, 15000]], 10000, 10, 100000, 15000],
    [[[0, 2000], [1000, 3000], [10000, 5000]], 100000, 10, 100000, 50000],
    [[[0, 2000], [1000, 3000], [10000, 15000]], 100000, 10, 100000, 150000]
])
def test_unclaimed_reward_record_correct(btc_agent, set_candidate, tests, claim):
    stake_manager.set_lp_rates(tests[0])
    stake_manager.set_is_stake_hub_active(True)
    operators, consensuses = set_candidate
    turn_round()
    turn_round(consensuses, round_count=2)
    btc_reward = tests[1]
    btc_amount = tests[2]
    core_amount = tests[3]
    actual_btc_reward = tests[4]
    unclaimed_reward = actual_btc_reward - btc_reward
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    round_reward_manager.mock_btc_reward_map(
        accounts[0], btc_reward, 0, btc_amount)
    reward = btc_agent.claimReward.call(
        accounts[0], core_amount, get_current_round() - 1, False)
    assert reward == [actual_btc_reward, unclaimed_reward, btc_amount]
    tx = btc_agent.claimReward(
        accounts[0], core_amount, get_current_round() - 1, claim)
    dual_staking_rate = tests[0][-1][-1]
    event_name = ['storedBtcReward']
    if claim:
        event_name = ['claimedBtcReward']
    expect_event(tx, event_name[0], {
        'amount': actual_btc_reward,
        'unclaimedAmount': 0,
        'floatReward': actual_btc_reward - btc_reward,
        'accStakedAmount': btc_amount,
        'dualStakingRate': dual_staking_rate
    })


@pytest.mark.parametrize("tests", [
    {'btc_reward': 10000, 'duration_unclaimed': 4000},
    {'btc_reward': 3000, 'duration_unclaimed': 0},
    {'btc_reward': 3000, 'duration_unclaimed': 1000},
    {'btc_reward': 3000, 'duration_unclaimed': 4000},
    {'btc_reward': 3000, 'duration_unclaimed': 1000},
    {'btc_reward': 20000, 'duration_unclaimed': 8000},
    {'btc_reward': 5000, 'duration_unclaimed': 6000},
    {'btc_reward': 5000, 'duration_unclaimed': 0},
    {'btc_reward': 5000, 'duration_unclaimed': 0}
])
def test_claim_reward_with_additional_bonus(btc_agent, tests):
    stake_manager.set_lp_rates([[0, 20000]])
    btc_reward = tests['btc_reward']
    additional_bonus = btc_reward * 2 - btc_reward
    duration_unclaimed = tests['duration_unclaimed']
    stake_manager.set_is_stake_hub_active(True)
    turn_round()
    round_reward_manager.mock_btc_reward_map(
        accounts[0], btc_reward, duration_unclaimed, 100)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    reward = btc_agent.claimReward.call(
        accounts[0], 0, get_current_round() - 1, False)
    actual_reward = btc_reward + additional_bonus
    if duration_unclaimed > 0:
        additional_bonus -= duration_unclaimed
    assert reward == [actual_reward, additional_bonus, 100]


@pytest.mark.parametrize("claim", [True, False])
@pytest.mark.parametrize("tests", [
    {'btc_reward': 10000, 'duration_unclaimed': 4000, 'btc_percentage': 12000, 'expect_reward': 12000,
     'expect_surplus': -2000},
    {'btc_reward': 10000, 'duration_unclaimed': 1000, 'btc_percentage': 12000, 'expect_reward': 12000,
     'expect_surplus': 1000},
    {'btc_reward': 10000, 'duration_unclaimed': 10000, 'btc_percentage': 18000, 'expect_reward': 18000,
     'expect_surplus': -2000},
    {'btc_reward': 10000, 'duration_unclaimed': 0, 'btc_percentage': 14000, 'expect_reward': 14000,
     'expect_surplus': 4000},
    {'btc_reward': 10000, 'duration_unclaimed': 2000, 'btc_percentage': 9000, 'expect_reward': 9000,
     'expect_surplus': -3000},
    {'btc_reward': 10000, 'duration_unclaimed': 0, 'btc_percentage': 15000, 'expect_reward': 15000,
     'expect_surplus': 5000}
])
def test_btc_extra_pool_reward(btc_agent, tests, claim):
    btc_reward = tests['btc_reward']
    duration_unclaimed = tests['duration_unclaimed']
    btc_percentage = tests['btc_percentage']
    stake_manager.set_lp_rates([[0, btc_percentage]])
    stake_manager.set_is_stake_hub_active(True)
    turn_round()
    actual_btc_reward = btc_reward * btc_percentage // Utils.DENOMINATOR
    additional_bonus = actual_btc_reward - btc_reward
    btc_acc_amount = 1100
    round_reward_manager.mock_btc_reward_map(
        accounts[0], btc_reward, duration_unclaimed, btc_acc_amount)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    reward = btc_agent.claimReward.call(
        accounts[0], 0, get_current_round() - 1, False)
    if duration_unclaimed > 0:
        additional_bonus -= duration_unclaimed
    actual_reward = actual_btc_reward
    assert actual_reward == tests['expect_reward']
    assert additional_bonus == tests['expect_surplus']
    assert reward == [actual_reward, additional_bonus, btc_acc_amount]
    tx = btc_agent.claimReward(accounts[0], 0, get_current_round() - 1, claim)
    event_name = ['storedBtcReward', 'storedBtcLstReward']
    if claim:
        event_name = ['claimedBtcReward', 'claimedBtcLstReward']
    expect_event(tx, event_name[0], {
        'delegator': accounts[0].address,
        'amount': actual_btc_reward,
        'unclaimedAmount': duration_unclaimed,
        'floatReward': actual_btc_reward - btc_reward - duration_unclaimed,
        'accStakedAmount': btc_acc_amount,
        'dualStakingRate': btc_percentage
    })


@pytest.mark.parametrize("tests", [
    {'btc_reward': 10000, 'duration_unclaimed': 0, 'btc_percentage': 8000, 'expect_reward': 8000,
     'expect_surplus': -2000},
    {'btc_reward': 10000, 'duration_unclaimed': 1000, 'btc_percentage': 8000, 'expect_reward': 8000,
     'expect_surplus': -3000},
    {'btc_reward': 3000, 'duration_unclaimed': 1000, 'btc_percentage': 0, 'expect_reward': 0, 'expect_surplus': -4000},
    {'btc_reward': 20000, 'duration_unclaimed': 3000, 'btc_percentage': 10000, 'expect_reward': 20000,
     'expect_surplus': -3000},
    {'btc_reward': 10000, 'duration_unclaimed': 0, 'btc_percentage': 7000, 'expect_reward': 7000,
     'expect_surplus': -3000},
    {'btc_reward': 10000, 'duration_unclaimed': 2000, 'btc_percentage': 9000, 'expect_reward': 9000,
     'expect_surplus': -3000},
    {'btc_reward': 10000, 'duration_unclaimed': 2000, 'btc_percentage': 12000, 'expect_reward': 12000,
     'expect_surplus': 0},
    {'btc_reward': 10000, 'duration_unclaimed': 3000, 'btc_percentage': 12000, 'expect_reward': 12000,
     'expect_surplus': -1000},
    {'btc_reward': 10000, 'duration_unclaimed': 1000, 'btc_percentage': 12000, 'expect_reward': 12000,
     'expect_surplus': 1000},
    {'btc_reward': 10000, 'duration_unclaimed': 0, 'btc_percentage': 12000, 'expect_reward': 12000,
     'expect_surplus': 2000},
    {'btc_reward': 20000, 'duration_unclaimed': 0, 'btc_percentage': 0, 'expect_reward': 0, 'expect_surplus': -20000},
    {'btc_reward': 20000, 'duration_unclaimed': 2000, 'btc_percentage': 0, 'expect_reward': 0,
     'expect_surplus': -22000},
    {'btc_reward': 20000, 'duration_unclaimed': 2000, 'btc_percentage': 5000, 'expect_reward': 10000,
     'expect_surplus': -12000}
])
def test_btc_add_reward_to_pool(btc_agent, tests):
    btc_reward = tests['btc_reward']
    duration_unclaimed = tests['duration_unclaimed']
    btc_percentage = tests['btc_percentage']
    stake_manager.set_lp_rates([[0, btc_percentage]])
    stake_manager.set_is_stake_hub_active(True)
    turn_round()
    actual_btc_reward = btc_reward * btc_percentage // Utils.DENOMINATOR
    additional_bonus = actual_btc_reward - btc_reward
    round_reward_manager.mock_btc_reward_map(
        accounts[0], btc_reward, duration_unclaimed, 100)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    reward = btc_agent.claimReward.call(
        accounts[0], 0, get_current_round() - 1, False)
    if duration_unclaimed > 0:
        additional_bonus -= duration_unclaimed
    actual_reward = actual_btc_reward
    assert actual_reward == tests['expect_reward']
    assert additional_bonus == tests['expect_surplus']
    assert reward == [actual_reward, additional_bonus, 100]


def test_get_acc_stake_amount_success(btc_agent, set_candidate):
    btc_value = 200
    operators, consensuses = set_candidate
    turn_round()
    delegate_btc_success(operators[1], accounts[0], btc_value, LOCK_SCRIPT)
    turn_round(consensuses, round_count=2)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    _, _, acc_staked_amount = btc_agent.claimReward(accounts[0], 100, get_current_round() - 1, False).return_value
    assert acc_staked_amount == btc_value


def test_get_grades(btc_agent, btc_stake):
    old_grades = [[0, 1000], [2000, 10000]]
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades_encode = rlp.encode(old_grades)
    btc_agent.updateParam('grades', grades_encode)
    assert old_grades == btc_agent.getGrades()


def test_update_param_failed(btc_agent):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    with brownie.reverts("UnsupportedGovParam: error key"):
        btc_agent.updateParam('error key', constants.ADDRESS_ZERO)


def test_only_gov_can_call_update_param(btc_agent):
    with brownie.reverts("the msg sender must be governance contract"):
        btc_agent.updateParam('error key', '0x00')


def test_update_param_allowed_only_after_init_by_gov(btc_agent):
    btc_agent.setAlreadyInit(False)
    with brownie.reverts("the contract not init yet"):
        btc_agent.updateParam('error key', '0x00')


@pytest.mark.parametrize("grades", [
    [[0, 1000], [1000, 10000]],
    [[0, 1200], [2000, 2000], [3000, 10000]],
    [[0, 1000], [2000, 2000], [3000, 4000], [3500, 9000], [4000, 10000]],
    [[0, 1000], [3000, 2000], [12000, 4000], [19000, 9000], [22222, 10000]]
])
def test_update_param_grades_success(btc_agent, grades):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades_encode = rlp.encode(grades)
    btc_agent.updateParam('grades', grades_encode)
    for i in range(btc_agent.getGradesLength()):
        grades_value = btc_agent.grades(i)
        assert grades_value == grades[i]


def test_length_error_revert(btc_agent):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades_encode = rlp.encode([])
    with brownie.reverts("MismatchParamLength: grades"):
        btc_agent.updateParam('grades', grades_encode)


@pytest.mark.parametrize("grades", [
    [[0, 1000], [1000, 10000]],
    [[0, 1200], [2000, 2000], [3000, 10000]],
    [[0, 1000], [3000, 2000], [12000, 14000], [19000, 19000], [22222, 20000]]
])
def test_duplicate_update_grades(btc_agent, grades):
    old_grades = [[0, 1000], [2000, 10000]]
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades_encode = rlp.encode(old_grades)
    btc_agent.updateParam('grades', grades_encode)
    for i in range(btc_agent.getGradesLength()):
        grades_value = btc_agent.grades(i)
        assert grades_value == old_grades[i]
    grades_encode = rlp.encode(grades)
    btc_agent.updateParam('grades', grades_encode)
    for i in range(btc_agent.getGradesLength()):
        grades_value = btc_agent.grades(i)
        assert grades_value == grades[i]


@pytest.mark.parametrize("grades", [
    [[100000001, 1000], [1000, 10000]],
    [[0, 1000], [100000001, 2000], [3000, 10000]],
    [[0, 1000], [2000, 2000], [100000001, 10000]],
    [[0, 1000], [100000001, 2000], [100000001, 10000]],
])
def test_stake_rate_exceeds_maximum(btc_agent, grades):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades_encode = rlp.encode(grades)
    with brownie.reverts(f"OutOfBounds: stakeRate, 100000001, 0, 100000000"):
        btc_agent.updateParam('grades', grades_encode)


@pytest.mark.parametrize("percentage", [99999, 1000000, 100000])
def test_final_percentage_below_1_reverts(btc_agent, percentage):
    max_percentage = 1000000
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades = [[0, 1000], [2000, percentage]]
    grades_encode = rlp.encode(grades)
    if percentage > max_percentage:
        with brownie.reverts(f"OutOfBounds: percentage, {grades[-1][-1]}, 0, 1000000"):
            btc_agent.updateParam('grades', grades_encode)
    else:
        btc_agent.updateParam('grades', grades_encode)


def test_non_last_percentage_can_exceed_limit(btc_agent):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades = [[0, 1000], [2000, 11000], [3000, 12000]]
    grades_encode = rlp.encode(grades)
    btc_agent.updateParam('grades', grades_encode)
    for i in range(btc_agent.getGradesLength()):
        grades_value = btc_agent.grades(i)
        assert grades_value == grades[i]


@pytest.mark.parametrize("grades", [
    ['stakeRate', [0, 1000], [2000, 10000], [1000, 12000]],
    ['stakeRate', [0, 1000], [5000, 2000], [4000, 10000]],
    ['stakeRate', [0, 1000], [3000, 9000], [3000, 8000], [4000, 10000]],
    ['percentage', [0, 8000], [3000, 7000], [4000, 10000]],
    ['percentage', [0, 1000], [2000, 7000], [3000, 6000], [4000, 10000]]
])
def test_incorrect_reward_rate_percentage_order_reverts(btc_agent, grades):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades_encode = rlp.encode(grades[1:])
    with brownie.reverts(f"{grades[0]} disorder"):
        btc_agent.updateParam('grades', grades_encode)


def test_lowest_stake_rate_must_be_zero(btc_agent):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades_encode = rlp.encode([[1000, 2000], [2000, 10000]])
    with brownie.reverts(f"lowest stakeRate must be zero"):
        btc_agent.updateParam('grades', grades_encode)


def test_percentage_cannot_be_zero(btc_agent):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    grades_encode = rlp.encode([[1000, 0]])
    with brownie.reverts(f"lowest stakeRate must be zero"):
        btc_agent.updateParam('grades', grades_encode)


def test_update_param_percentage_success(btc_agent):
    percentage = 4000
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(int(percentage)), 64)
    tx = btc_agent.updateParam('lstGradePercentage', hex_value)
    assert btc_agent.lstGradePercentage() == percentage
    expect_event(tx, 'paramChange', {
        'key': 'lstGradePercentage',
        'value': hex_value
    })


def test_update_param_percentage_length_error(btc_agent):
    percentage = 4000
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(int(percentage)), 65)
    with brownie.reverts(f"MismatchParamLength: lstGradePercentage"):
        btc_agent.updateParam('lstGradePercentage', hex_value)


@pytest.mark.skip(reason="deprecated")
def test_revert_on_percentage_zero(btc_agent):
    percentage = 0
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(percentage), 64)
    with brownie.reverts(f"OutOfBounds: lstGradePercentage, {percentage}, 1, 100000"):
        btc_agent.updateParam('lstGradePercentage', hex_value)

@pytest.mark.skip(reason="deprecated")
def test_revert_on_percentage_exceeding_limit(btc_agent):
    percentage = 100001
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(percentage), 64)
    with brownie.reverts(f"OutOfBounds: lstGradePercentage, {percentage}, 1, 100000"):
        btc_agent.updateParam('lstGradePercentage', hex_value)


@pytest.mark.parametrize("grade_active", [0, 1])
def test_update_param_grade_active_success(btc_agent, grade_active):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    btc_agent.updateParam('gradeActive', grade_active)
    if grade_active:
        actual_active = True
    else:
        actual_active = False
    assert btc_agent.gradeActive() == actual_active


@pytest.mark.parametrize("grade_active", [2, 3, 4])
def test_update_param_grade_active_failed(btc_agent, grade_active):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    with brownie.reverts(f"OutOfBounds: gradeActive, {grade_active}, 0, 1"):
        btc_agent.updateParam('gradeActive', grade_active)


def test_update_param_grade_active_length_failed(btc_agent):
    update_system_contract_address(btc_agent, gov_hub=accounts[0])
    hex_value = padding_left(Web3.to_hex(0), 64)
    with brownie.reverts(f"MismatchParamLength: gradeActive"):
        btc_agent.updateParam('gradeActive', hex_value)
