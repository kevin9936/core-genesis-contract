import brownie
import pytest
from web3 import Web3
from brownie import accounts, PledgeAgentProxy, DelegateReentry, UndelegateReentry, ClaimRewardReentry
from .common import register_candidate, turn_round, stake_hub_claim_reward
from .utils import get_tracker, expect_event, expect_query, encode_args_with_signature
from .calc_reward import parse_delegation, set_delegate, set_coin_delegator, calculate_rewards, calculate_coin_rewards

core_hardcap = 6000
power_hardcap = 2000
btc_hardcap = 4000
sum_hardcap = core_hardcap + power_hardcap + btc_hardcap

MIN_INIT_DELEGATE_VALUE = 0
BLOCK_REWARD = 0
total_reward = 0
COIN_REWARD = 0
POWER_REWARD = 0
BTC_REWARD = 0

ONE_ETHER = Web3.toWei(1, 'ether')
TX_FEE = 100


@pytest.fixture(scope="module", autouse=True)
def deposit_for_reward(validator_set):
    accounts[-2].transfer(validator_set.address, Web3.toWei(100000, 'ether'))


@pytest.fixture(scope="module", autouse=True)
def set_min_init_delegate_value(min_init_delegate_value):
    global MIN_INIT_DELEGATE_VALUE
    MIN_INIT_DELEGATE_VALUE = min_init_delegate_value


@pytest.fixture(scope="module", autouse=True)
def set_block_reward(validator_set):
    global BLOCK_REWARD, POWER_REWARD, BTC_REWARD, total_reward
    global COIN_REWARD
    block_reward = validator_set.blockReward()
    block_reward_incentive_percent = validator_set.blockRewardIncentivePercent()
    total_block_reward = block_reward + TX_FEE
    BLOCK_REWARD = total_block_reward * ((100 - block_reward_incentive_percent) / 100)
    total_reward = BLOCK_REWARD // 2
    POWER_REWARD = total_reward * power_hardcap // sum_hardcap
    BTC_REWARD = total_reward * btc_hardcap // sum_hardcap
    COIN_REWARD = total_reward * core_hardcap // sum_hardcap


@pytest.fixture()
def set_candidate():
    operator = accounts[1]
    consensus = operator
    register_candidate(consensus=consensus, operator=operator)
    return consensus, operator


@pytest.mark.parametrize("claim_type", ["claim", "delegate", "undelegate", "transfer"])
def test_delegate_once(pledge_agent, validator_set, claim_type, stake_hub):
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    turn_round()
    # Core staking can earn up to 50% of the total rewards
    assert consensus in validator_set.getValidators()

    turn_round([consensus])
    tracker = get_tracker(accounts[0])

    if claim_type == "claim":
        stake_hub.claimReward()
        assert tracker.delta() == COIN_REWARD
    elif claim_type == "delegate":
        # delegate do not automatically method historical rewards
        pledge_agent.delegateCoin(operator, {"value": 100})
        assert tracker.delta() == -100
    elif claim_type == "undelegate":
        # undelegate do not automatically method historical rewards
        pledge_agent.undelegateCoin(operator)
        assert tracker.delta() == MIN_INIT_DELEGATE_VALUE
    elif claim_type == "transfer":
        register_candidate(operator=accounts[2])
        # transfer do not automatically method historical rewards
        pledge_agent.transferCoin(operator, accounts[2])
        assert tracker.delta() == 0


@pytest.mark.parametrize("internal", [
    pytest.param(0, id="same round"),
    pytest.param(1, id="adjacent rounds"),
    pytest.param(2, id="spanning multiple rounds"),
])
def test_delegate2one_agent_twice_in_different_rounds(pledge_agent, set_candidate, internal, stake_hub):
    consensus, operator = set_candidate
    turn_round()

    for _ in range(2):
        pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
        turn_round(round_count=internal)
    if internal == 0:
        turn_round()
    turn_round([consensus])

    tracker = get_tracker(accounts[0])
    stake_hub.claimReward()
    assert tracker.delta() == COIN_REWARD


@pytest.mark.parametrize("internal", [
    pytest.param(0, id="same round"),
    pytest.param(1, id="adjacent rounds"),
    pytest.param(2, id="spanning multiple rounds"),
])
def test_delegate2two_agents_in_different_rounds(pledge_agent, internal, stake_hub):
    operators = []
    consensuses = []
    for operator in accounts[1:3]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))

    turn_round()

    for operator in operators:
        pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
        turn_round(round_count=internal)

    if internal == 0:
        turn_round()

    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    stake_hub.claimReward()
    # coin staking can get 50% of the rewards 
    # 2 validators each receive 50% of the reward
    assert tracker.delta() == COIN_REWARD * 2


def test_claim_reward_after_transfer_to_candidate(pledge_agent, candidate_hub, validator_set, stake_hub):
    operators = []
    consensuses = []

    for operator in accounts[1:4]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    candidate_hub.refuseDelegate({'from': operators[2]})

    turn_round()
    validators = validator_set.getValidators()
    assert len(validators) == 2
    assert operators[2] not in validators

    pledge_agent.delegateCoin(operators[0], {"value": MIN_INIT_DELEGATE_VALUE})
    pledge_agent.delegateCoin(operators[1], {"value": MIN_INIT_DELEGATE_VALUE})
    turn_round()
    turn_round(consensuses)

    tracker = get_tracker(accounts[0])

    candidate_hub.acceptDelegate({'from': operators[2]})
    pledge_agent.transferCoin(operators[1], operators[2])
    candidate_hub.refuseDelegate({'from': operators[2]})

    turn_round(consensuses, round_count=2)
    # There are a total of 5 rounds of rewards
    stake_hub.claimReward()
    assert tracker.delta() == COIN_REWARD * 5


def test_claim_reward_after_transfer_to_validator(pledge_agent, validator_set, stake_hub):
    operators = []
    consensuses = []

    for operator in accounts[1:4]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))

    turn_round()
    validators = validator_set.getValidators()
    assert len(validators) == 3
    pledge_agent.delegateCoin(operators[0], {"value": MIN_INIT_DELEGATE_VALUE})
    pledge_agent.delegateCoin(operators[1], {"value": MIN_INIT_DELEGATE_VALUE})
    turn_round()
    turn_round(consensuses)
    tracker = get_tracker(accounts[0])
    pledge_agent.transferCoin(operators[1], operators[2])
    turn_round(consensuses, round_count=2)
    stake_hub.claimReward()
    assert tracker.delta() == COIN_REWARD * 6


def test_claim_reward_after_transfer_to_duplicated_validator(pledge_agent, stake_hub):
    operators = []
    consensuses = []
    clients = accounts[:2]

    for operator in accounts[2:4]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
        for client in clients:
            pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE, "from": client})

    turn_round()

    pledge_agent.transferCoin(operators[0], operators[1], {"from": clients[0]})
    turn_round(consensuses, round_count=2)

    _, _, account_rewards0, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "coin": [set_delegate(clients[0], MIN_INIT_DELEGATE_VALUE),
                 set_delegate(clients[1], MIN_INIT_DELEGATE_VALUE)],
        "power": [],
        "btc":[]
    }, {
        "address": operators[1],
        "active": True,
        "coin": [set_delegate(clients[0], MIN_INIT_DELEGATE_VALUE),
                 set_delegate(clients[1], MIN_INIT_DELEGATE_VALUE)],
        "power": [],
        "btc": []

    }], BLOCK_REWARD // 2)

    _, _, account_rewards1, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "coin": [set_delegate(clients[1], MIN_INIT_DELEGATE_VALUE)],
        "power": [],
        "btc": []

    }, {
        "address": operators[1],
        "active": True,
        "coin": [set_delegate(clients[0], MIN_INIT_DELEGATE_VALUE * 2),
                 set_delegate(clients[1], MIN_INIT_DELEGATE_VALUE)],
        "power": [],
        "btc": []

    }], BLOCK_REWARD // 2)

    tracker1 = get_tracker(clients[0])
    tracker2 = get_tracker(clients[1])
    for client in clients:
        stake_hub.claimReward({'from': client})

    assert tracker1.delta() == account_rewards0[clients[0]] + account_rewards1[clients[0]]
    assert tracker2.delta() == account_rewards0[clients[1]] + account_rewards1[clients[1]]


def test_undelegate_coin_next_round(pledge_agent, stake_hub):
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    turn_round()
    pledge_agent.undelegateCoin(operator)
    turn_round([consensus])
    reward_sum = stake_hub.claimReward.call()
    assert reward_sum == 0


def test_undelegate_coin_reward(pledge_agent, stake_hub):
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    turn_round()
    pledge_agent.undelegateCoin(operator)
    tx = turn_round([consensus])
    assert "receiveDeposit" in tx.events
    # Only the rewards that exceed the hard cap are burned
    event = tx.events['receiveDeposit'][-1]
    assert event['from'] == stake_hub.address
    assert event['amount'] == total_reward - COIN_REWARD
    tx = stake_hub.claimReward({'from': accounts[0]})
    assert 'claimedReward' not in tx.events


def test_proxy_claim_reward_success(pledge_agent, stake_hub):
    pledge_agent_proxy = PledgeAgentProxy.deploy(pledge_agent.address, stake_hub.address, {'from': accounts[0]})
    pledge_agent_proxy.setReceiveState(True)
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    tx = pledge_agent_proxy.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    expect_event(tx, "delegate", {"success": True})
    assert tx.events['delegatedCoin']['delegator'] == pledge_agent_proxy.address
    turn_round()
    turn_round([consensus])
    reward = pledge_agent_proxy.claimReward.call()
    assert reward == COIN_REWARD
    tx = pledge_agent_proxy.claimReward()
    expect_event(tx, "claim", {
        "reward": reward,
        "allClaimed": True,
        "delegator": accounts[0],
    })
    expect_event(tx, "claimedReward", {
        "delegator": pledge_agent_proxy.address,
        "amount": COIN_REWARD
    })
    assert pledge_agent.rewardMap(pledge_agent_proxy.address) == 0


def test_claim_reward_failed(pledge_agent, stake_hub):
    pledge_agent_proxy = PledgeAgentProxy.deploy(pledge_agent.address, stake_hub.address, {'from': accounts[0]})
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    tx = pledge_agent_proxy.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    expect_event(tx, "delegate", {"success": True})
    turn_round()
    turn_round([consensus])
    pledge_agent_proxy.setReceiveState(False)
    assert pledge_agent.rewardMap(pledge_agent_proxy.address) == 0
    with brownie.reverts("call to claimReward failed"):
        pledge_agent_proxy.claimReward.call()


def test_delegate_coin_reentry(pledge_agent, stake_hub):
    pledge_agent_proxy = DelegateReentry.deploy(
        pledge_agent.address, stake_hub, {'from': accounts[0], 'value': MIN_INIT_DELEGATE_VALUE * 2})
    operators = accounts[1:3]
    consensus = []
    for _operator in operators:
        consensus.append(register_candidate(operator=_operator))
    pledge_agent_proxy.delegateCoin(operators[0], {'value': MIN_INIT_DELEGATE_VALUE})
    turn_round()
    turn_round(consensus)
    pledge_agent_proxy.setAgent(operators[0])
    tx = pledge_agent_proxy.delegateCoin(operators[0], {'value': MIN_INIT_DELEGATE_VALUE})
    expect_event(tx, "proxyDelegate", {"success": True})
    assert pledge_agent_proxy.balance() == 200


def test_claim_reward_reentry(pledge_agent, stake_hub):
    pledge_agent_proxy = ClaimRewardReentry.deploy(pledge_agent.address, stake_hub.address, {'from': accounts[0]})
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    tx = pledge_agent_proxy.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    assert tx.events['delegatedCoin']['delegator'] == pledge_agent_proxy.address
    pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round()
    turn_round([consensus])
    assert stake_hub.balance() == COIN_REWARD
    tracker = get_tracker(pledge_agent_proxy)
    tx = pledge_agent_proxy.claimReward()
    expect_event(tx, "proxyClaim", {
        "success": False
    })
    assert tracker.delta() == 0


def test_undelegate_amount_small(pledge_agent, validator_set):
    undelegate_value = MIN_INIT_DELEGATE_VALUE - 1
    operator = accounts[1]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    turn_round()
    assert consensus in validator_set.getValidators()
    with brownie.reverts("undelegate amount is too small"):
        pledge_agent.undelegateCoin(operator, undelegate_value)


def test_transfer_remain_amount_small(pledge_agent, validator_set):
    operators = []
    for operator in accounts[2:5]:
        operators.append(operator)
        register_candidate(operator=operator)
    operator = operators[0]
    undelegate_value = MIN_INIT_DELEGATE_VALUE + 99
    pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE * 2})
    turn_round()
    assert len(validator_set.getValidators()) == 3
    with brownie.reverts("remaining amount is too small"):
        pledge_agent.transferCoin(operators[0], operators[1], undelegate_value)


def test_transfer_undelegate_amount_small(pledge_agent, validator_set):
    undelegate_value = MIN_INIT_DELEGATE_VALUE - 1
    operators = []
    for operator in accounts[2:5]:
        operators.append(operator)
        register_candidate(operator=operator)
    operator = operators[0]
    pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
    turn_round()
    assert len(validator_set.getValidators()) == 3
    with brownie.reverts("undelegate amount is too small"):
        pledge_agent.transferCoin(operators[0], operators[1], undelegate_value)


def test_claim_reward_after_undelegate_one_round(pledge_agent, validator_set, stake_hub):
    operator = accounts[2]
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    undelegate_amount = delegate_amount // 2
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    tracker0 = get_tracker(accounts[0])
    tracker1 = get_tracker(accounts[1])
    pledge_agent.undelegateCoin(operator, undelegate_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operator, 0, {'from': accounts[1]})
    delegator_info0 = pledge_agent.getDelegator(operator, accounts[0])
    reward_info = pledge_agent.getReward(operator, delegator_info0['rewardIndex'])
    assert tracker0.delta() == undelegate_amount
    assert tracker1.delta() == delegate_amount
    remain_pledged_amount = delegate_amount - undelegate_amount
    total_pledged_amount = delegate_amount * 2
    assert reward_info['coin'] == remain_pledged_amount
    assert reward_info['score'] == total_pledged_amount
    turn_round([consensus], round_count=1)
    delegator_info0 = pledge_agent.getDelegator(operator, accounts[0])
    assert delegator_info0[0] == delegate_amount // 2
    reward_info = pledge_agent.getReward(operator, 0)
    assert reward_info['totalReward'] == COIN_REWARD
    _, _, account_rewards, _, _ = parse_delegation([{
        "address": operator,
        "active": True,
        "coin": [set_delegate(accounts[0], 500, 250), set_delegate(accounts[1], 500, 500)],
        "power": [],
        "btc":[]
    }], BLOCK_REWARD // 2)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == account_rewards[accounts[0]]
    assert tracker1.delta() == account_rewards[accounts[1]]


def test_claim_reward_after_undelegate_multiple_round(pledge_agent, validator_set, stake_hub):
    operator = accounts[2]
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    undelegate_amount = delegate_amount // 2
    undelegate_amount1 = undelegate_amount // 2
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    tracker0 = get_tracker(accounts[0])
    tracker1 = get_tracker(accounts[1])
    pledge_agent.undelegateCoin(operator, undelegate_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operator, undelegate_amount1, {'from': accounts[1]})
    delegator_info0 = pledge_agent.getDelegator(operator, accounts[0])
    reward_info = pledge_agent.getReward(operator, delegator_info0['rewardIndex'])
    assert tracker0.delta() == undelegate_amount
    assert tracker1.delta() == undelegate_amount1
    remain_pledged_amount0 = delegate_amount - undelegate_amount
    remain_pledged_amount1 = delegate_amount - undelegate_amount1
    total_pledged_amount = delegate_amount * 2
    total_undelegate_amount = undelegate_amount + undelegate_amount1
    assert reward_info['coin'] == total_pledged_amount - total_undelegate_amount
    assert reward_info['score'] == total_pledged_amount
    turn_round([consensus], round_count=1)
    _, _, account_rewards0, _, _ = parse_delegation([{
        "address": operator,
        "active": True,
        "coin": [set_delegate(accounts[0], delegate_amount, undelegate_amount),
                 set_delegate(accounts[1], delegate_amount, undelegate_amount1)],
        "power": [],
        "btc":[]
    }], BLOCK_REWARD // 2)
    pledge_agent.undelegateCoin(operator, undelegate_amount1, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operator, 0, {'from': accounts[1]})
    _, _, account_rewards1, _, _ = parse_delegation([{
        "address": operator,
        "active": True,
        "coin": [set_delegate(accounts[0], remain_pledged_amount0, undelegate_amount1),
                 set_delegate(accounts[1], remain_pledged_amount1, delegate_amount - undelegate_amount1)],
        "power": [],
        "btc": []
    }], BLOCK_REWARD // 2)
    turn_round([consensus], round_count=1)
    stake_hub_claim_reward(accounts[0])
    stake_hub_claim_reward(accounts[1])
    assert tracker0.delta() == account_rewards0[accounts[0]] + account_rewards1[accounts[0]] + undelegate_amount1
    assert tracker1.delta() == account_rewards0[accounts[1]] + account_rewards1[
        accounts[1]] + delegate_amount - undelegate_amount1


def test_undelegate_all_coins_on_validator_and_claim_rewards(pledge_agent, validator_set):
    operator = accounts[2]
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.undelegateCoin(operator, delegate_amount, {'from': accounts[0]})
    turn_round([consensus], round_count=1)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == 0


def test_claim_reward_after_undelegate_coin_partially(pledge_agent, validator_set):
    operator = accounts[2]
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 8
    undelegate_amount = delegate_amount // 5
    undelegate_amount1 = delegate_amount // 7
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    tracker0 = get_tracker(accounts[0])
    pledge_agent.undelegateCoin(operator, undelegate_amount, {'from': accounts[0]})
    assert tracker0.delta() == undelegate_amount
    remain_pledged_amount = delegate_amount - undelegate_amount
    total_pledged_amount = delegate_amount
    turn_round([consensus], round_count=1)
    _, _, account_rewards0, _, _ = parse_delegation([{
        "address": operator,
        "active": True,
        "coin": [set_delegate(accounts[0], delegate_amount, undelegate_amount)],
        "power": [],
        "btc":[]
    }], BLOCK_REWARD // 2)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == account_rewards0[accounts[0]]
    pledge_agent.undelegateCoin(operator, undelegate_amount1, {'from': accounts[0]})
    turn_round([consensus], round_count=1)
    remain_pledged_amount -= undelegate_amount1
    total_pledged_amount -= undelegate_amount
    delegator_info0 = pledge_agent.getDelegator(operator, accounts[0])
    reward_info = pledge_agent.getReward(operator, delegator_info0['rewardIndex'])
    assert reward_info['coin'] == remain_pledged_amount
    assert reward_info['score'] == total_pledged_amount
    assert delegator_info0['newDeposit'] == remain_pledged_amount
    tracker0.update_height()
    stake_hub_claim_reward(accounts[0])
    _, _, account_rewards1, _, _ = parse_delegation([{
        "address": operator,
        "active": True,
        "coin": [set_delegate(accounts[0], total_pledged_amount, undelegate_amount1)],
        "power": [],
        "btc":[]
    }], BLOCK_REWARD // 2)
    assert tracker0.delta() == account_rewards1[accounts[0]]
    pledge_agent.undelegateCoin(operator, {'from': accounts[0]})
    turn_round([consensus], round_count=1)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == remain_pledged_amount


def test_multi_delegators_claim_reward_after_undelegate_coin_partially(pledge_agent, validator_set):
    operator = accounts[2]
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    undelegate_amount0 = delegate_amount // 2
    undelegate_amount1 = undelegate_amount0 // 2
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    tracker0 = get_tracker(accounts[0])
    tracker1 = get_tracker(accounts[1])
    pledge_agent.undelegateCoin(operator, undelegate_amount0, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operator, undelegate_amount1, {'from': accounts[1]})
    total_pledged_amount = delegate_amount * 2
    turn_round([consensus], round_count=1)
    tracker0.update_height()
    tracker1.update_height()
    stake_hub_claim_reward(accounts[0])
    stake_hub_claim_reward(accounts[1])
    actual_reward0 = COIN_REWARD * undelegate_amount0 // total_pledged_amount
    # There are changes to how rewards are calculated
    # Each time you claim a reward, you will be counted according to the percentage of points
    actual_reward1 = COIN_REWARD * (delegate_amount - undelegate_amount1) // total_pledged_amount
    assert tracker0.delta() == actual_reward0
    assert tracker1.delta() == actual_reward1


@pytest.mark.parametrize("undelegate_type", ['all', 'part'])
def test_withdraw_principal(pledge_agent, validator_set, undelegate_type):
    operator = accounts[2]
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 8
    undelegate_amount = delegate_amount // 5
    if undelegate_type == 'all':
        undelegate_amount = delegate_amount
    register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    tracker0 = get_tracker(accounts[0])
    pledge_agent.undelegateCoin(operator, undelegate_amount, {'from': accounts[0]})
    assert tracker0.delta() == undelegate_amount


def test_claim_rewards_for_multiple_validators(pledge_agent, validator_set):
    operators = []
    consensuses = []
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    undelegate_amount = delegate_amount // 3
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[1], 0, {'from': accounts[0]})
    tracker0 = get_tracker(accounts[0])
    turn_round(consensuses, round_count=2)
    stake_hub_claim_reward(accounts[0])
    actual_reward = COIN_REWARD + COIN_REWARD * (delegate_amount - undelegate_amount) // delegate_amount
    assert tracker0.delta() == actual_reward


def test_claim_rewards_each_round_after_undelegate_or_delegate(pledge_agent, validator_set, candidate_hub):
    operators = []
    consensuses = []
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 4
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    turn_round()
    validators = validator_set.getValidators()
    assert len(validators) == 3
    tracker0 = get_tracker(accounts[0])
    tracker1 = get_tracker(accounts[1])
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    assert tracker0.delta() == 0 - delegate_amount
    assert tracker1.delta() == 0 - delegate_amount * 2
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    stake_hub_claim_reward(accounts[0])
    stake_hub_claim_reward(accounts[1])
    assert tracker0.delta() == 0 - delegate_amount
    assert tracker1.delta() == 0
    turn_round(consensuses)
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    stake_hub_claim_reward(accounts[0])
    stake_hub_claim_reward(accounts[1])
    assert tracker0.delta() == COIN_REWARD // 2 + undelegate_amount
    assert tracker1.delta() == COIN_REWARD // 2 + COIN_REWARD
    remain_pledged_amount = delegate_amount * 2 - undelegate_amount
    total_pledged_amount = delegate_amount * 3
    turn_round(consensuses)
    actual_reward0 = COIN_REWARD * remain_pledged_amount // total_pledged_amount
    actual_reward1 = COIN_REWARD * delegate_amount // total_pledged_amount + COIN_REWARD
    stake_hub_claim_reward(accounts[0])
    stake_hub_claim_reward(accounts[1])
    assert tracker0.delta() == actual_reward0
    assert tracker1.delta() == actual_reward1


def test_auto_reward_distribution_on_undelegate(pledge_agent, validator_set, candidate_hub):
    operator = accounts[2]
    operator1 = accounts[4]
    delegate_amount0 = MIN_INIT_DELEGATE_VALUE * 2
    consensus = register_candidate(operator=operator)
    consensus1 = register_candidate(operator=operator1)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount0, 'from': accounts[0]})
    pledge_agent.delegateCoin(operator1, {"value": delegate_amount0, 'from': accounts[0]})
    pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round()
    tracker0 = get_tracker(accounts[0])
    tracker1 = get_tracker(accounts[1])
    turn_round([consensus1, consensus])
    pledge_agent.undelegateCoin(operator, MIN_INIT_DELEGATE_VALUE, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operator, {'from': accounts[1]})
    assert tracker0.delta() == MIN_INIT_DELEGATE_VALUE
    assert tracker1.delta() == MIN_INIT_DELEGATE_VALUE


def test_undelegate_claim_principal_for_candidate_node(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 2
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    candidate_hub.refuseDelegate({'from': operators[2]})
    turn_round()
    tracker0 = get_tracker(accounts[0])
    pledge_agent.undelegateCoin(operators[2], MIN_INIT_DELEGATE_VALUE, {'from': accounts[0]})
    turn_round(consensuses, round_count=1)
    pledge_agent.undelegateCoin(operators[2], MIN_INIT_DELEGATE_VALUE, {'from': accounts[0]})
    assert tracker0.delta() == delegate_amount
    turn_round(consensuses, round_count=1)
    candidate_hub.acceptDelegate({'from': operators[2]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount * 5, 'from': accounts[0]})
    assert tracker0.delta() == 0 - delegate_amount * 5
    turn_round(consensuses, round_count=1)
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 3
    total_delegate_amount = delegate_amount * 5
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses, round_count=1)
    expect_reward = calculate_coin_rewards(total_delegate_amount - undelegate_amount, total_delegate_amount,
                                           COIN_REWARD)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward + undelegate_amount
    pledge_agent.undelegateCoin(operators[2], MIN_INIT_DELEGATE_VALUE, {'from': accounts[0]})
    candidate_hub.refuseDelegate({'from': operators[2]})
    turn_round(consensuses, round_count=1)
    tracker0.update_height()
    total_delegate_amount -= undelegate_amount
    expect_reward = calculate_coin_rewards(total_delegate_amount - MIN_INIT_DELEGATE_VALUE, total_delegate_amount,
                                           COIN_REWARD)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward


def test_undelegate_claim_principal_for_unregister_node(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 2
    operator = accounts[2]
    operator1 = accounts[3]
    tracker0 = get_tracker(accounts[0])
    consensus = register_candidate(operator=operator)
    register_candidate(operator=operator1)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    candidate_hub.unregister({'from': operator})
    turn_round()
    validators = validator_set.getValidators()
    assert len(validators) == 1
    assert operator not in validators
    tracker0.update_height()
    pledge_agent.undelegateCoin(operator, MIN_INIT_DELEGATE_VALUE, {'from': accounts[0]})
    assert tracker0.delta() == MIN_INIT_DELEGATE_VALUE
    turn_round([consensus], round_count=3)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == 0
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    candidate_hub.unregister({'from': operator})
    tx = pledge_agent.undelegateCoin(operator, 0, {'from': accounts[0]})
    assert tx.events['undelegatedCoin']['amount'] == MIN_INIT_DELEGATE_VALUE
    turn_round([consensus], round_count=2)
    tx = pledge_agent.transferCoin(operator, operator1, {'from': accounts[0]})
    assert tx.events['transferredCoin']['amount'] == MIN_INIT_DELEGATE_VALUE * 2
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == -100
    turn_round([consensus])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == 0


@pytest.mark.parametrize("undelegate_type", ['all', 'part'])
def test_transfer_with_partial_undelegate_and_claimed_rewards(pledge_agent, validator_set, candidate_hub,
                                                              undelegate_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount = delegate_amount // 3
    undelegate_amount = delegate_amount // 3
    if undelegate_type == 'all':
        undelegate_amount = delegate_amount
    operators = []
    remain_pledged_amount = delegate_amount
    total_pledged_amount = delegate_amount * 2
    consensuses = []
    for operator in accounts[3:6]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    operator = operators[0]
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[2]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[1]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount, {'from': accounts[2]})
    turn_round(consensuses, round_count=1)
    tracker1 = get_tracker(accounts[1])
    stake_hub_claim_reward(accounts[1])
    remain_pledged_amount -= undelegate_amount
    expect_reward = COIN_REWARD * remain_pledged_amount // total_pledged_amount
    assert tracker1.delta() == expect_reward


def test_delegate_then_all_undelegate(pledge_agent, validator_set):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 2
    additional_amount = MIN_INIT_DELEGATE_VALUE * 3
    operator = accounts[2]
    consensus = register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.delegateCoin(operator, {"value": additional_amount, 'from': accounts[0]})
    tracker0 = get_tracker(accounts[0])
    pledge_agent.undelegateCoin(operator, MIN_INIT_DELEGATE_VALUE, {'from': accounts[0]})
    turn_round([consensus], round_count=1)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD // 2 + MIN_INIT_DELEGATE_VALUE


@pytest.mark.parametrize("undelegate_type", ['all', 'part'])
def test_undelegate_with_recent_stake(pledge_agent, validator_set, undelegate_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 2
    additional_amount = MIN_INIT_DELEGATE_VALUE * 3
    operator = accounts[2]
    register_candidate(operator=operator)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.delegateCoin(operator, {"value": additional_amount, 'from': accounts[0]})
    undelegate_amount = additional_amount
    if undelegate_type == 'all':
        undelegate_amount = additional_amount + delegate_amount
    with brownie.reverts("Not enough deposit token"):
        pledge_agent.undelegateCoin(operator, undelegate_amount, {'from': accounts[0]})


@pytest.mark.parametrize("undelegate_type", ['all', 'part'])
def test_undelegate_from_recent_transfer(pledge_agent, validator_set, undelegate_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 2
    operators = []
    consensuses = []
    for operator in accounts[3:6]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[1], operators[0], {'from': accounts[0]})
    undelegate_amount = delegate_amount + MIN_INIT_DELEGATE_VALUE
    if undelegate_type == 'all':
        undelegate_amount = delegate_amount * 2
    with brownie.reverts("Not enough deposit token"):
        pledge_agent.undelegateCoin(operator, undelegate_amount, {'from': accounts[0]})


@pytest.mark.parametrize("undelegate_type", ['all', 'part'])
def test_undelagate_current_stake(pledge_agent, validator_set, undelegate_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 2
    operators = []
    consensuses = []
    for operator in accounts[3:6]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    undelegate_amount = delegate_amount // 2
    if undelegate_type == 'all':
        undelegate_amount = 0
    with brownie.reverts("Not enough deposit token"):
        pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})


@pytest.mark.parametrize("undelegate_type", ['all', 'part'])
def test_undelagate_current_transfer(pledge_agent, validator_set, undelegate_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 2
    operators = []
    consensuses = []
    for operator in accounts[3:6]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[1], operators[0], {'from': accounts[0]})
    undelegate_amount = delegate_amount // 2
    if undelegate_type == 'all':
        undelegate_amount = 0
    with brownie.reverts("Not enough deposit token"):
        pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})


def test_undelegate_transfer_input_and_deposit(pledge_agent, validator_set):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount = delegate_amount // 5
    transfer_amount1 = delegate_amount // 4
    operators = []
    consensuses = []
    for operator in accounts[3:6]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[0], transfer_amount1, {'from': accounts[0]})
    tx = pledge_agent.undelegateCoin(operators[0], {'from': accounts[0]})
    assert tx.events['undelegatedCoin']['amount'] == delegate_amount - transfer_amount
    tx = pledge_agent.undelegateCoin(operators[2], {'from': accounts[0]})
    assert tx.events['undelegatedCoin']['amount'] == delegate_amount - transfer_amount1
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    _, _, account_rewards, _, _ = parse_delegation([{
        "address": operators[0],
        "active": True,
        "coin": [set_delegate(accounts[0], delegate_amount, delegate_amount - transfer_amount)],
        "power": [],
        "btc":[]
    }, {
        "address": operators[1],
        "active": True,
        "coin": [set_delegate(accounts[0], delegate_amount)],
        "power": [],
        "btc":[]
    }, {
        "address": operators[2],
        "active": True,
        "coin": [set_delegate(accounts[0], delegate_amount, delegate_amount - transfer_amount1)],
        "power": [],
        "btc":[]
    }], BLOCK_REWARD // 2)

    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == account_rewards[accounts[0]]


def test_claim_rewards_after_transfers_undelegations_both_validators(pledge_agent, validator_set):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount = delegate_amount // 5
    undelegate_amount = MIN_INIT_DELEGATE_VALUE
    operators = []
    consensuses = []
    for operator in accounts[3:6]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[0], transfer_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[1], transfer_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[1], undelegate_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    expect_reward = COIN_REWARD * (delegate_amount - undelegate_amount) // delegate_amount
    assert tracker0.delta() == expect_reward * 3


def test_all_validators_transfer_then_claim_reward(pledge_agent, validator_set):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount = delegate_amount // 5
    undelegate_amount = transfer_amount + MIN_INIT_DELEGATE_VALUE
    undelegate_amount1 = transfer_amount + MIN_INIT_DELEGATE_VALUE * 2
    operators = []
    consensuses = []
    for operator in accounts[3:6]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[0], transfer_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[1], transfer_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[1], undelegate_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[2], undelegate_amount1, {'from': accounts[0]})
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    expect_reward = COIN_REWARD * (delegate_amount - undelegate_amount) // delegate_amount
    expect_reward2 = COIN_REWARD * (delegate_amount - undelegate_amount1) // delegate_amount
    assert tracker0.delta() == expect_reward * 2 + expect_reward2


@pytest.mark.parametrize("round_number", [1, 2, 3])
def test_claim_undelegated_rewards_after_multiple_rounds(pledge_agent, validator_set, round_number):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    undelegate_amount = transfer_amount0 // 2
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    tracker0 = get_tracker(accounts[0])
    remain_reward = COIN_REWARD * (delegate_amount - undelegate_amount) // delegate_amount
    turn_round(consensuses, round_count=round_number)
    stake_hub_claim_reward(accounts[0])
    reward_round = round_number - 1
    expect_reward = remain_reward + COIN_REWARD * 2 * reward_round
    assert tracker0.delta() == expect_reward


def test_transfer_auto_claim_rewards(pledge_agent, candidate_hub, validator_set):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount = delegate_amount // 2
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    tracker0 = get_tracker(accounts[0])
    tracker1 = get_tracker(accounts[1])
    turn_round(consensuses)
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount)
    assert tracker0.delta() == 0
    assert tracker1.delta() == 0


def test_claim_reward_after_transfer_coin(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount = MIN_INIT_DELEGATE_VALUE
    remain_pledged_amount0 = delegate_amount
    total_pledged_amount0 = delegate_amount * 3
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount * 2, 'from': accounts[1]})
    turn_round()
    candidate_hub.acceptDelegate({'from': operators[2]})
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount)
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    remain_pledged_amount0 -= transfer_amount
    expect_query(delegator_info0, {'deposit': remain_pledged_amount0, 'newDeposit': remain_pledged_amount0,
                                   'transferOutDeposit': transfer_amount, 'transferInDeposit': 0})
    expect_query(delegator_info2, {'newDeposit': transfer_amount, 'transferOutDeposit': 0, 'transferInDeposit': 0})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    tracker1 = get_tracker(accounts[1])
    stake_hub_claim_reward(accounts[0])
    stake_hub_claim_reward(accounts[1])
    expect_reward0 = calculate_coin_rewards(delegate_amount, total_pledged_amount0, COIN_REWARD)
    expect_reward1 = calculate_coin_rewards(delegate_amount * 2, total_pledged_amount0, COIN_REWARD)
    assert tracker0.delta() == expect_reward0
    assert tracker1.delta() == expect_reward1
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    expect_reward0 = calculate_coin_rewards(delegate_amount - transfer_amount, total_pledged_amount0 - transfer_amount,
                                            COIN_REWARD)
    assert tracker0.delta() == expect_reward0 + COIN_REWARD


@pytest.mark.parametrize("validator_type", ['candidate', 'unregister', 'active'])
def test_transfer_coin_and_undelegate_to_active_validator(pledge_agent, validator_set, candidate_hub, validator_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount = MIN_INIT_DELEGATE_VALUE * 2
    undelegate_amount = MIN_INIT_DELEGATE_VALUE
    operators = []
    consensuses = []
    validator_count = 2
    is_validator = False
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount, COIN_REWARD)
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    if validator_type == 'candidate':
        candidate_hub.refuseDelegate({'from': operators[0]})
    elif validator_type == 'unregister':
        candidate_hub.unregister({'from': operators[0]})
    else:
        validator_count = 3
        is_validator = True
        expect_reward += COIN_REWARD
    turn_round()
    validators = validator_set.getValidators()
    assert validator_set.isValidator(consensuses[0]) == is_validator
    assert len(validators) == validator_count
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount)
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward


@pytest.mark.parametrize("validator_type", ['candidate', 'unregister', 'active'])
def test_transfer_coin_to_active_validator(pledge_agent, validator_set, candidate_hub, validator_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount = MIN_INIT_DELEGATE_VALUE
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    expect_reward = 0
    if validator_type == 'candidate':
        candidate_hub.refuseDelegate({'from': operators[0]})
    elif validator_type == 'unregister':
        candidate_hub.unregister({'from': operators[0]})
    else:
        expect_reward = COIN_REWARD
    turn_round()
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    expect_query(delegator_info0, {'newDeposit': delegate_amount})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount)
    pledge_agent.transferCoin(operators[0], operators[2], delegate_amount - transfer_amount)
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward


@pytest.mark.parametrize("validator_type", ['candidate', 'unregister'])
def test_transfer_to_unregister_and_candidate_validator(pledge_agent, candidate_hub, validator_set, validator_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount = delegate_amount // 3
    operator = accounts[2]
    operator1 = accounts[3]
    register_candidate(operator=operator)
    register_candidate(operator=operator1)
    pledge_agent.delegateCoin(operator, {"value": delegate_amount, 'from': accounts[0]})
    if validator_type == 'candidate':
        candidate_hub.refuseDelegate({'from': operator1})
    elif validator_type == 'unregister':
        candidate_hub.unregister({'from': operator1})
    turn_round()
    error_msg = encode_args_with_signature("InactiveAgent(address)", [operator1.address])
    with brownie.reverts(f"typed error: {error_msg}"):
        pledge_agent.transferCoin(operator, operator1, transfer_amount, {"from": accounts[0]})


def test_transfer_multiple_times_and_claim_rewards(pledge_agent, validator_set):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount = MIN_INIT_DELEGATE_VALUE * 2
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount, {"from": accounts[0]})
    turn_round(consensuses)
    delegator_info1 = pledge_agent.getDelegator(operators[1], accounts[0])
    expect_query(delegator_info1, {'newDeposit': transfer_amount, 'transferOutDeposit': 0})
    tracker0 = get_tracker(accounts[0])
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount, {"from": accounts[0]})
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD // 2
    delegator_info1 = pledge_agent.getDelegator(operators[1], accounts[0])
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    expect_query(delegator_info1,
                 {'deposit': transfer_amount, 'newDeposit': transfer_amount * 2, 'transferOutDeposit': 0})
    expect_query(delegator_info0,
                 {'deposit': delegate_amount - transfer_amount * 2, 'newDeposit': delegate_amount - transfer_amount * 2,
                  'transferOutDeposit': transfer_amount, })
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    remain_pledged_amount = delegate_amount - transfer_amount
    total_pledged_amount = delegate_amount * 2 - transfer_amount
    expect_reward = COIN_REWARD * remain_pledged_amount // total_pledged_amount
    assert tracker0.delta() == expect_reward + COIN_REWARD


@pytest.mark.parametrize("undelegate_amount", [500, 700, 750])
def test_claim_rewards_after_additional_cancel_delegate_and_transfer(pledge_agent, validator_set, candidate_hub,
                                                                     undelegate_amount):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 4
    additional_amount = delegate_amount
    total_pledged_amount0 = delegate_amount * 3
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount * 2, 'from': accounts[3]})
    turn_round()
    pledge_agent.delegateCoin(operators[0], {"value": additional_amount, 'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})

    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    expect_reward0 = calculate_coin_rewards(delegate_amount - undelegate_amount, total_pledged_amount0, COIN_REWARD)
    assert tracker0.delta() == expect_reward0


@pytest.mark.parametrize("undelegate_amount", [400, 800, 900])
def test_transfer_to_existing_validator_and_undelegate_claim_rewards(pledge_agent, validator_set, undelegate_amount):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    transfer_out_deposit0 = transfer_amount0
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    assert delegator_info0['transferOutDeposit'] == transfer_out_deposit0
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    tracker1 = get_tracker(accounts[1])
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2, COIN_REWARD)
    stake_hub_claim_reward(accounts[0])
    stake_hub_claim_reward(accounts[1])
    assert tracker0.delta() == expect_reward + COIN_REWARD // 2
    assert tracker1.delta() == COIN_REWARD


def test_transfer_to_queued_validator_and_undelegate_claim_rewards(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    undelegate_amount = transfer_amount0 - MIN_INIT_DELEGATE_VALUE
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    candidate_hub.setValidatorCount(2)
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    validators = validator_set.getValidators()
    assert consensuses[1] not in validators
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2, COIN_REWARD)
    assert tracker0.delta() == expect_reward


def test_transfer_to_already_delegate_validator_in_queue(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = 500
    transfer_amount1 = 700
    undelegate_amount = 900
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    candidate_hub.setValidatorCount(2)
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    validators = validator_set.getValidators()
    assert consensuses[1] not in validators
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount1, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2, COIN_REWARD)
    # operators[1] are not rewarded
    assert tracker0.delta() == expect_reward + COIN_REWARD // 2


def test_single_transfer_to_already_delegate_queued_validator(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = MIN_INIT_DELEGATE_VALUE * 5
    undelegate_amount0 = MIN_INIT_DELEGATE_VALUE * 4
    undelegate_amount1 = MIN_INIT_DELEGATE_VALUE * 12
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    candidate_hub.setValidatorCount(2)
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    validators = validator_set.getValidators()
    assert consensuses[1] not in validators
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
    with brownie.reverts("Not enough deposit token"):
        pledge_agent.undelegateCoin(operators[1], undelegate_amount1, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[1], undelegate_amount0, {'from': accounts[0]})
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD + COIN_REWARD // 2


def test_multiple_transfers_and_undelegate_claim_rewards(pledge_agent, validator_set, candidate_hub):
    candidate_hub.setValidatorCount(21)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount1 = MIN_INIT_DELEGATE_VALUE * 9
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 9
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount1, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2, COIN_REWARD)
    assert tracker0.delta() == COIN_REWARD + expect_reward


def test_claim_rewards_after_additional_and_transfer(pledge_agent, validator_set, candidate_hub):
    candidate_hub.setValidatorCount(21)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    additional_amount = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount1 = MIN_INIT_DELEGATE_VALUE * 3
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 3
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.delegateCoin(operators[0], {"value": additional_amount, 'from': accounts[0]})
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount1, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[1], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2, COIN_REWARD)
    assert tracker0.delta() == reward + COIN_REWARD // 2


def test_transfer_and_delegate_with_reward_claim(pledge_agent, validator_set, candidate_hub):
    candidate_hub.setValidatorCount(21)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = MIN_INIT_DELEGATE_VALUE * 5
    additional_amount = MIN_INIT_DELEGATE_VALUE * 3
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 3
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": additional_amount, 'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[1], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2, COIN_REWARD)
    assert tracker0.delta() == reward + COIN_REWARD // 2


def test_undelegate_and_transfer_with_rewards(pledge_agent, validator_set, candidate_hub):
    candidate_hub.setValidatorCount(21)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount1 = MIN_INIT_DELEGATE_VALUE * 3
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 6
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount * 2, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[1], undelegate_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[1], transfer_amount1, {'from': accounts[0]})
    expect_reward0 = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2, COIN_REWARD)
    expect_reward1 = calculate_coin_rewards(delegate_amount, delegate_amount * 3, COIN_REWARD)
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward0 + expect_reward1 + COIN_REWARD // 2


def test_transfer_to_same_validator_and_undelegate(pledge_agent, validator_set, candidate_hub):
    candidate_hub.setValidatorCount(21)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount1 = MIN_INIT_DELEGATE_VALUE * 3
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 8
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[2], operators[1], transfer_amount1, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[1], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2, COIN_REWARD)
    assert tracker0.delta() == COIN_REWARD + expect_reward + COIN_REWARD // 2


def test_transfer_and_delegate_and_then_transfer(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = MIN_INIT_DELEGATE_VALUE * 5
    additional_amount = MIN_INIT_DELEGATE_VALUE * 6
    transfer_amount1 = MIN_INIT_DELEGATE_VALUE * 10
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": additional_amount, 'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount1, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD + COIN_REWARD // 2


def test_transfer_then_validator_refuses_delegate(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 5
    transfer_amount = MIN_INIT_DELEGATE_VALUE * 2
    undelegate_amount = MIN_INIT_DELEGATE_VALUE
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    candidate_hub.refuseDelegate({'from': operators[0]})
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount)
    candidate_hub.refuseDelegate({'from': operators[2]})
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount, COIN_REWARD)
    assert tracker0.delta() == expect_reward + COIN_REWARD


def test_unstake_except_transfer_then_claim_reward(pledge_agent, validator_set):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 11
    transfer_amount = MIN_INIT_DELEGATE_VALUE
    transfer_amount2 = MIN_INIT_DELEGATE_VALUE * 4
    operators = []
    consensuses = []
    for operator in accounts[3:6]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[0], transfer_amount2, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[0], transfer_amount2, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[0], {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[1], {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[2], {'from': accounts[0]})
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    expect_reward0 = calculate_coin_rewards(transfer_amount * 2, delegate_amount, COIN_REWARD)
    expect_reward1 = calculate_coin_rewards(transfer_amount2, delegate_amount, COIN_REWARD)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward0 + expect_reward1 * 2


def test_transfer_and_check_transfer_info(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    transfer_amount1 = delegate_amount // 4
    transfer_amount2 = delegate_amount // 4
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount1, {'from': accounts[0]})
    tx = pledge_agent.transferCoin(operators[2], operators[0], transfer_amount2, {'from': accounts[0]})
    expect_event(tx, "transferredCoin", {
        "sourceAgent": operators[2],
        "targetAgent": operators[0],
        "delegator": accounts[0],
        "amount": transfer_amount1,
        "totalAmount": delegate_amount - transfer_amount0 + transfer_amount1,
    })
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    delegator_info1 = pledge_agent.getDelegator(operators[1], accounts[0])
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    expect_query(delegator_info0, {'newDeposit': delegate_amount - transfer_amount0 + transfer_amount2,
                                   'transferOutDeposit': transfer_amount0, 'transferInDeposit': 0})
    expect_query(delegator_info1, {'newDeposit': delegate_amount + transfer_amount0 - transfer_amount1,
                                   'transferOutDeposit': transfer_amount1, 'transferInDeposit': 0})
    expect_query(delegator_info2, {'newDeposit': delegate_amount + transfer_amount1 - transfer_amount2,
                                   'transferOutDeposit': transfer_amount2, 'transferInDeposit': 0})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD * 2


def test_multiple_transfers_and_check_transfer_info(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    transfer_amount1 = delegate_amount // 4
    transfer_amount2 = delegate_amount // 4
    undelegate_amount = transfer_amount1 + MIN_INIT_DELEGATE_VALUE
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount1, {'from': accounts[0]})
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    delegator_info1 = pledge_agent.getDelegator(operators[1], accounts[0])
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    new_deposit1 = delegate_amount - transfer_amount1
    new_deposit2 = delegate_amount + transfer_amount0 + transfer_amount1
    expect_query(delegator_info0, {'deposit': transfer_amount0, 'newDeposit': delegate_amount - transfer_amount0,
                                   'transferOutDeposit': transfer_amount0, })
    expect_query(delegator_info1,
                 {'newDeposit': new_deposit1, 'transferOutDeposit': transfer_amount1, 'transferInDeposit': 0})
    expect_query(delegator_info2, {'newDeposit': new_deposit2, 'transferOutDeposit': 0})
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    new_deposit2 -= undelegate_amount
    new_deposit1 -= transfer_amount2
    expect_query(delegator_info2, {'newDeposit': new_deposit2, 'transferOutDeposit': 0})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount2, {'from': accounts[0]})
    new_deposit2 += transfer_amount2
    delegator_info1 = pledge_agent.getDelegator(operators[1], accounts[0])
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    expect_query(delegator_info1,
                 {'newDeposit': new_deposit1, 'transferOutDeposit': transfer_amount1 + transfer_amount2})
    expect_query(delegator_info2, {'newDeposit': new_deposit2, 'transferOutDeposit': 0})
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2, COIN_REWARD)
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward + COIN_REWARD + COIN_REWARD // 2


def test_transfer_info_accumulation(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    transfer_amount1 = delegate_amount // 4
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    new_deposit0 = delegate_amount
    new_deposit2 = delegate_amount
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    new_deposit0 -= transfer_amount0
    new_deposit2 += transfer_amount0
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    expect_query(delegator_info0, {'newDeposit': new_deposit0, 'transferOutDeposit': transfer_amount0})
    expect_query(delegator_info2, {'newDeposit': new_deposit2, 'transferOutDeposit': 0})
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount1, {'from': accounts[0]})
    new_deposit0 -= transfer_amount1
    new_deposit2 += transfer_amount1
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    expect_query(delegator_info0,
                 {'newDeposit': new_deposit0, 'transferOutDeposit': transfer_amount0 + transfer_amount1})
    expect_query(delegator_info2, {'newDeposit': new_deposit2, 'transferOutDeposit': 0})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount1, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount1, {'from': accounts[0]})
    new_deposit2 += transfer_amount1 * 2
    delegator_info1 = pledge_agent.getDelegator(operators[1], accounts[0])
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    expect_query(delegator_info1,
                 {'newDeposit': delegate_amount - transfer_amount1 * 2, 'transferOutDeposit': transfer_amount1 * 2})
    expect_query(delegator_info2, {'newDeposit': new_deposit2, 'transferOutDeposit': 0})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD * 3


def test_batch_transfer_to_multiple_validators(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    transfer_amount1 = delegate_amount // 4
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount1, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[0], transfer_amount1, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[1], transfer_amount0, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD * 3


def test_single_transfer_and_check_transfer_info(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    expect_query(delegator_info0, {'transferOutDeposit': transfer_amount0})
    expect_query(delegator_info2, {'transferOutDeposit': 0})
    turn_round(consensuses, round_count=2)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD * 3


@pytest.mark.parametrize("threshold_type", ['minor', 'major'])
def test_reward_claim_after_slash(pledge_agent, validator_set, slash_indicator, threshold_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    operators = []
    transfer_amount = delegate_amount // 3
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    tx = None
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount)
    if threshold_type == 'minor':
        slash_threshold = slash_indicator.misdemeanorThreshold()
        event_name = 'validatorMisdemeanor'
        expect_reward = COIN_REWARD
    else:
        slash_threshold = slash_indicator.felonyThreshold()
        event_name = 'validatorFelony'
        expect_reward = 0
    for count in range(slash_threshold):
        tx = slash_indicator.slash(consensuses[0])
    assert event_name in tx.events
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    expect_query(delegator_info0, {'transferOutDeposit': transfer_amount})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    assert delegator_info0['transferOutDeposit'] == 0
    assert tracker0.delta() == expect_reward


@pytest.mark.parametrize("threshold_type", ['minor', 'major'])
def test_reward_after_slash_and_transfer(pledge_agent, validator_set, slash_indicator, threshold_type, candidate_hub):
    round_time_tag = 7
    candidate_hub.setControlRoundTimeTag(True)
    candidate_hub.setRoundTag(round_time_tag)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    operators = []
    transfer_amount = delegate_amount // 3
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    tx0 = None
    tx1 = None
    if threshold_type == 'minor':
        slash_threshold = slash_indicator.misdemeanorThreshold()
        event_name = 'validatorMisdemeanor'
        expect_reward = COIN_REWARD
    else:
        slash_threshold = slash_indicator.felonyThreshold()
        event_name = 'validatorFelony'
        expect_reward = 0
    for count in range(slash_threshold):
        tx0 = slash_indicator.slash(consensuses[0])
    assert event_name in tx0.events
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount)
    for count in range(slash_threshold):
        tx1 = slash_indicator.slash(consensuses[2])
    assert event_name in tx1.events
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward
    required_margin = 1000001
    candidate_hub.addMargin({'value': required_margin, 'from': operators[2]})
    turn_round(consensuses, round_count=2)
    tx = pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    assert 'delegatedCoin' in tx.events


@pytest.mark.parametrize("threshold_type", ['minor', 'major'])
def test_post_transfer_major_slash(pledge_agent, validator_set, slash_indicator, threshold_type, candidate_hub):
    round_time_tag = 7
    candidate_hub.setControlRoundTimeTag(True)
    candidate_hub.setRoundTag(round_time_tag)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    operators = []
    undelegate_amount = MIN_INIT_DELEGATE_VALUE
    transfer_amount = delegate_amount // 3
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    tx0 = None
    tx1 = None
    if threshold_type == 'minor':
        slash_threshold = slash_indicator.misdemeanorThreshold()
        event_name = 'validatorMisdemeanor'
        expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount, COIN_REWARD)
        expect_reward1 = COIN_REWARD * 6
    else:
        slash_threshold = slash_indicator.felonyThreshold()
        event_name = 'validatorFelony'
        expect_reward = 0
        expect_reward1 = COIN_REWARD
    for count in range(slash_threshold):
        tx0 = slash_indicator.slash(consensuses[0])
    assert event_name in tx0.events
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount)
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    for count in range(slash_threshold):
        tx1 = slash_indicator.slash(consensuses[2])
    assert event_name in tx1.events
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward
    required_margin = 100000000001
    #
    candidate_hub.addMargin({'value': required_margin, 'from': operators[2]})
    turn_round(consensuses, round_count=3)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward1


@pytest.mark.parametrize("threshold_type", ['minor', 'major'])
def test_major_violation_followed_by_reward_claim(pledge_agent, validator_set, slash_indicator, threshold_type,
                                                  candidate_hub):
    round_time_tag = 7
    candidate_hub.setControlRoundTimeTag(True)
    candidate_hub.setRoundTag(round_time_tag)
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    operators = []
    undelegate_amount = MIN_INIT_DELEGATE_VALUE
    transfer_amount = delegate_amount // 3
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    tx1 = None
    if threshold_type == 'minor':
        slash_threshold = slash_indicator.misdemeanorThreshold()
        event_name = 'validatorMisdemeanor'
        expect_reward = COIN_REWARD + calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount,
                                                             COIN_REWARD)
        expect_reward1 = COIN_REWARD * 6
    else:
        slash_threshold = slash_indicator.felonyThreshold()
        event_name = 'validatorFelony'
        expect_reward = COIN_REWARD
        expect_reward1 = COIN_REWARD * 3 + COIN_REWARD
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount)
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    for count in range(slash_threshold):
        tx1 = slash_indicator.slash(consensuses[2])
    assert event_name in tx1.events
    turn_round(consensuses, round_count=1)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward
    required_margin = 100000000001
    candidate_hub.addMargin({'value': required_margin, 'from': operators[2]})
    turn_round(consensuses, round_count=3)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward1


def test_undelegate_then_transfer(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 4
    undelegate_amount = delegate_amount // 6
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    expect_query(delegator_info0, {'newDeposit': delegate_amount - undelegate_amount - transfer_amount0,
                                   'transferOutDeposit': transfer_amount0})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount, COIN_REWARD)
    assert tracker0.delta() == expect_reward


def test_batch_transfer_to_one_validator(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    transfer_amount1 = delegate_amount // 4
    operators = []
    consensuses = []
    for operator in accounts[4:8]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    pledge_agent.transferCoin(operators[1], operators[2], transfer_amount1, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD * 2


def test_transfer_after_claim_reward(pledge_agent, validator_set, candidate_hub):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    turn_round(consensuses)
    delegator_info2 = pledge_agent.getDelegator(operators[2], accounts[0])
    new_deposit0 = transfer_amount0
    expect_query(delegator_info2, {'newDeposit': new_deposit0})
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD


def test_reward_claim_midway_doesnt_affect_current_round(pledge_agent, validator_set):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 4
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    tx = stake_hub_claim_reward(accounts[0])
    assert 'claimedReward' not in tx.events
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    expect_query(delegator_info0, {'transferOutDeposit': transfer_amount0})
    tracker0 = get_tracker(accounts[0])
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    reward_info = pledge_agent.getReward(operators[0], delegator_info0['rewardIndex'])
    assert reward_info['score'] == delegate_amount
    assert reward_info['coin'] == delegate_amount - undelegate_amount
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount, COIN_REWARD)
    assert tracker0.delta() == expect_reward


@pytest.mark.parametrize("undelegate_amount", [400, 800])
def test_transfer_and_undelegate_in_different_rounds(pledge_agent, validator_set, undelegate_amount):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[2], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    pledge_agent.undelegateCoin(operators[2], undelegate_amount, {'from': accounts[0]})
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD + undelegate_amount
    turn_round(consensuses)
    expect_reward0 = calculate_coin_rewards(delegate_amount - transfer_amount0, delegate_amount * 2 - transfer_amount0,
                                            COIN_REWARD)
    expect_reward1 = calculate_coin_rewards(delegate_amount + transfer_amount0 - undelegate_amount,
                                            delegate_amount * 2 + transfer_amount0, COIN_REWARD)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward0 + expect_reward1


@pytest.mark.parametrize("operator_type", ['undelegate', 'delegate', 'transfer', 'claim'])
def test_operations_in_next_round_after_transfer(pledge_agent, validator_set, operator_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    operation_amount = delegate_amount // 4
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    if operator_type == 'undelegate':
        pledge_agent.undelegateCoin(operators[2], operation_amount, {'from': accounts[0]})
        expect_reward0 = operation_amount
        expect_reward1 = calculate_coin_rewards(delegate_amount - operation_amount, transfer_amount0,
                                                COIN_REWARD) + COIN_REWARD
    elif operator_type == 'transfer':
        pledge_agent.transferCoin(operators[2], operators[1], operation_amount, {'from': accounts[0]})
        expect_reward0 = 0
        expect_reward1 = COIN_REWARD * 3
    elif operator_type == 'claim':
        stake_hub_claim_reward(accounts[0])
        expect_reward0 = COIN_REWARD
        expect_reward1 = COIN_REWARD * 2
    else:
        pledge_agent.delegateCoin(operators[2], {"value": operation_amount, 'from': accounts[0]})
        expect_reward0 = -operation_amount
        expect_reward1 = COIN_REWARD * 3
    assert tracker0.delta() == expect_reward0
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward1


@pytest.mark.parametrize("operator_type", ['undelegate', 'delegate', 'transfer', 'claim'])
def test_operations_in_current_round_after_transfer(pledge_agent, validator_set, operator_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    operation_amount = delegate_amount // 4
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    if operator_type == 'undelegate':
        pledge_agent.undelegateCoin(operators[0], operation_amount, {'from': accounts[0]})
        expect_reward = calculate_coin_rewards(delegate_amount - operation_amount, delegate_amount, COIN_REWARD)
    elif operator_type == 'transfer':
        pledge_agent.transferCoin(operators[0], operators[1], operation_amount, {'from': accounts[0]})
        expect_reward = COIN_REWARD
    elif operator_type == 'claim':
        tx = stake_hub_claim_reward(accounts[0])
        assert 'claimedReward' not in tx.events
        expect_reward = COIN_REWARD
    else:
        pledge_agent.delegateCoin(operators[0], {"value": operation_amount, 'from': accounts[0]})
        expect_reward = COIN_REWARD
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward


def test_transfer_to_validator_with_existing_transfers(pledge_agent, validator_set):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    operation_amount = delegate_amount // 4
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    pledge_agent.transferCoin(operators[1], operators[2], operation_amount, {'from': accounts[0]})
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD * 2
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD * 3


@pytest.mark.parametrize("operator_type", ['undelegate', 'delegate', 'transfer', 'claim'])
def test_operation_on_validator_with_no_transfer(pledge_agent, validator_set, operator_type):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    operation_amount = delegate_amount // 4
    operators = []
    consensuses = []
    for operator in accounts[4:9]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[1], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[3], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    expect_query(delegator_info0, {'transferOutDeposit': transfer_amount0})
    expect_reward = COIN_REWARD * 4
    if operator_type == 'undelegate':
        pledge_agent.undelegateCoin(operators[3], operation_amount, {'from': accounts[0]})
        remain_reward = COIN_REWARD * 3 + operation_amount
        expect_reward = COIN_REWARD * 3 + calculate_coin_rewards(delegate_amount - operation_amount, delegate_amount,
                                                                 COIN_REWARD)
    elif operator_type == 'transfer':
        pledge_agent.transferCoin(operators[3], operators[4], operation_amount, {'from': accounts[0]})
        remain_reward = COIN_REWARD * 3
    elif operator_type == 'claim':
        tx = stake_hub_claim_reward(accounts[0])
        assert 'claimedReward' in tx.events
        assert tx.events['claimedReward']['amount'] == COIN_REWARD * 3
        remain_reward = COIN_REWARD * 3
    else:
        pledge_agent.delegateCoin(operators[3], {"value": operation_amount, 'from': accounts[0]})
        remain_reward = COIN_REWARD * 3 - operation_amount
    stake_hub_claim_reward(accounts[0])
    delegator_info0 = pledge_agent.getDelegator(operators[0], accounts[0])
    expect_query(delegator_info0, {'transferOutDeposit': 0})
    assert tracker0.delta() == remain_reward
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == expect_reward


def test_transfer_and_delegate_in_different_rounds(pledge_agent, validator_set):
    additional_delegate = MIN_INIT_DELEGATE_VALUE * 4
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    transfer_amount1 = transfer_amount0 // 2
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD // 2
    pledge_agent.delegateCoin(operators[0], {"value": additional_delegate, 'from': accounts[0]})
    turn_round(consensuses)
    pledge_agent.transferCoin(operators[2], operators[1], transfer_amount1, {'from': accounts[0]})
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - transfer_amount0, delegate_amount * 2 - transfer_amount0,
                                           COIN_REWARD) + COIN_REWARD - additional_delegate
    assert tracker0.delta() == expect_reward
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    expect_reward = COIN_REWARD + calculate_coin_rewards(delegate_amount - transfer_amount0 + additional_delegate,
                                                         delegate_amount * 2 - transfer_amount0 + additional_delegate,
                                                         COIN_REWARD)
    assert tracker0.delta() == expect_reward


def test_transfer_and_undelegate_and_delegate_in_different_rounds(pledge_agent, validator_set):
    additional_delegate = MIN_INIT_DELEGATE_VALUE * 3 / 2
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    transfer_amount1 = transfer_amount0 // 2
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 3
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD + undelegate_amount
    pledge_agent.delegateCoin(operators[2], {"value": additional_delegate, 'from': accounts[0]})
    pledge_agent.transferCoin(operators[2], operators[1], transfer_amount1, {'from': accounts[0]})
    new_deposit2 = transfer_amount0 + additional_delegate - transfer_amount1
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - transfer_amount0 - undelegate_amount,
                                           delegate_amount - transfer_amount0, COIN_REWARD) + COIN_REWARD
    assert tracker0.delta() == expect_reward - additional_delegate
    tracker0.update_height()
    pledge_agent.transferCoin(operators[2], operators[1], new_deposit2, {'from': accounts[0]})
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD * 3


def test_multiple_operations_in_different_rounds(pledge_agent, validator_set):
    additional_delegate = MIN_INIT_DELEGATE_VALUE * 3 / 2
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    transfer_amount1 = transfer_amount0 // 2
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 2.5
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[1]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    pledge_agent.delegateCoin(operators[0], {"value": additional_delegate, 'from': accounts[0]})
    stake_hub_claim_reward(accounts[0])
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount * 2,
                                           COIN_REWARD)
    assert tracker0.delta() == expect_reward - additional_delegate
    pledge_agent.transferCoin(operators[0], operators[1], transfer_amount1, {'from': accounts[0]})
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    tx = pledge_agent.undelegateCoin(operators[0], 0, {'from': accounts[0]})
    assert tx.events['undelegatedCoin']['amount'] == additional_delegate
    expect_reward = calculate_coin_rewards(delegate_amount - transfer_amount0 - undelegate_amount,
                                           delegate_amount * 2 - transfer_amount0 - undelegate_amount,
                                           COIN_REWARD)
    assert tracker0.delta() == expect_reward + COIN_REWARD + additional_delegate
    turn_round(consensuses)
    stake_hub_claim_reward(accounts[0])
    assert tracker0.delta() == COIN_REWARD * 2


@pytest.mark.parametrize("round_number", [1, 2, 3])
def test_transfer_rewards_and_claim_after_multiple_rounds(pledge_agent, validator_set, round_number):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    tracker0 = get_tracker(accounts[0])
    turn_round(consensuses, round_count=round_number)
    stake_hub_claim_reward(accounts[0])
    reward_round = round_number - 1
    expect_reward = COIN_REWARD + COIN_REWARD * 2 * reward_round
    assert tracker0.delta() == expect_reward


@pytest.mark.parametrize("round_number", [1, 2, 3])
def test_claim_rewards_after_transfer_and_undelegate_in_multiple_rounds(pledge_agent, validator_set, round_number):
    delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
    transfer_amount0 = delegate_amount // 2
    undelegate_amount = MIN_INIT_DELEGATE_VALUE * 4
    operators = []
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], transfer_amount0, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[0], undelegate_amount, {'from': accounts[0]})
    tracker0 = get_tracker(accounts[0])
    turn_round(consensuses, round_count=round_number)
    stake_hub_claim_reward(accounts[0])
    reward_round = round_number - 1
    expect_reward = calculate_coin_rewards(delegate_amount - undelegate_amount, delegate_amount,
                                           COIN_REWARD) + COIN_REWARD * 2 * reward_round
    assert tracker0.delta() == expect_reward
