import time

import pytest
import brownie
from web3 import Web3
from brownie import accounts, Wei
from brownie.network import gas_price
from .utils import expect_event, get_tracker, padding_left, encode_args_with_signature, expect_array
from .common import register_relayer, get_exchangerate
from .btc_block_data import btc_block_data
import brownie
import pytest
from web3 import Web3
from .common import register_candidate, turn_round
from .utils import get_tracker, expect_event, expect_query, encode_args_with_signature

MIN_DELEGATE_VALUE = Wei(10000)
RATE_MULTIPLE = 10000
BLOCK_REWARD = 0

ONE_ETHER = Web3.toWei(1, 'ether')
TX_FEE = 100


@pytest.fixture(scope="module", autouse=True)
def deposit_for_reward(validator_set):
    accounts[-2].transfer(validator_set.address, Web3.toWei(100000, 'ether'))


@pytest.fixture(scope="module", autouse=True)
def set_block_reward(validator_set):
    global BLOCK_REWARD
    # validator_set.updateBlockReward(3 * ONE_ETHER)
    block_reward = validator_set.blockReward()
    block_reward_incentive_percent = validator_set.blockRewardIncentivePercent()
    # NEW_TX_FEE = TX_FEE * 1e14
    total_block_reward = block_reward + TX_FEE
    BLOCK_REWARD = int(total_block_reward * (100 - block_reward_incentive_percent) / 100)


@pytest.fixture(scope="module", autouse=True)
def set_agent_pledge_contract_address(earn, pledge_agent, candidate_hub, stcore):
    earn.setContractAddress(candidate_hub.address, pledge_agent.address, stcore.address)
    # earn.initialize()
    round_time_tag = 7
    candidate_hub.setControlRoundTimeTag(True)
    candidate_hub.setRoundTag(round_time_tag)


@pytest.fixture(scope="module", autouse=True)
def init_contracts_variable():
    global LOCK_DAY, INIT_DAY_INTERVAL
    LOCK_DAY = 7
    INIT_DAY_INTERVAL = 86400


def test_delegate_one(pledge_agent, validator_set):
    operators = []
    total_reward = BLOCK_REWARD // 2
    consensuses = []
    for operator in accounts[4:7]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': 1000, 'from': accounts[0]})
    turn_round()
    pledge_agent.transferCoin(operators[0], operators[2], 500, {'from': accounts[0]})
    pledge_agent.undelegateCoin(operators[2], 400, {'from': accounts[0]})
    turn_round(consensuses)
    tracker0 = get_tracker(accounts[0])
    pledge_agent.claimReward(operators, {'from': accounts[0]})
    assert tracker0.delta() == int(total_reward * 600 // 1000)


def test_delegate_staking(earn, pledge_agent, stcore):
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    turn_round()
    earn.afterTurnRound()
    tx = earn.delegateStaking(operators[0], {'value': ONE_ETHER * 30})
    print(tx.events)
    validator_delegate = earn.getValidatorDelegate(operators[0])
    delegate_action = earn.getDelegateActionQueue(0)
    expect_query(validator_delegate, {'amount': ONE_ETHER * 30,
                                      'earning': 0})
    expect_query(delegate_action, {'validator': operators[0],
                                   'amount': ONE_ETHER * 30})
    delegator_info0 = pledge_agent.getDelegator(operators[0], earn.address)
    expect_query(delegator_info0, {'deposit': 0,
                                   'newDeposit': ONE_ETHER * 30})
    expect_event(tx, "delegatedCoin", {
        "agent": operators[0],
        "delegator": earn.address,
        "amount": ONE_ETHER * 30,
        "totalAmount": ONE_ETHER * 30,
    })
    expect_event(tx, "Transfer", {
        "from": '0x0000000000000000000000000000000000000000',
        "to": accounts[0],
        "value": ONE_ETHER * 30
    })
    assert stcore.totalSupply() == ONE_ETHER * 30
    assert stcore.balanceOf(accounts[0]) == ONE_ETHER * 30
    assert stcore.balanceOf(accounts[1]) == 0


def test_delegate_staking_core_exchange_rate(earn, pledge_agent, stcore):
    operators = []
    consensuses = []
    total_supply = MIN_DELEGATE_VALUE
    total_reward = BLOCK_REWARD // 2
    total_delegate_amount = MIN_DELEGATE_VALUE
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    turn_round(trigger=True)
    turn_round(consensuses, trigger=True)
    total_delegate_amount += total_reward
    exchange_rate = total_delegate_amount * RATE_MULTIPLE // total_supply
    token_value = MIN_DELEGATE_VALUE * RATE_MULTIPLE // exchange_rate
    total_supply += token_value
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    delegate_info = earn.getValidatorDelegate(operators[0])
    total_delegate_amount += MIN_DELEGATE_VALUE
    assert delegate_info['amount'] == total_delegate_amount
    assert stcore.totalSupply() == total_supply
    assert stcore.balanceOf(accounts[0]) == total_supply - token_value
    assert stcore.balanceOf(accounts[1]) == token_value


def test_invalid_delegate_amount(earn, pledge_agent, stcore):
    operator = accounts[3]
    register_candidate(operator=operator)
    turn_round()
    earn.afterTurnRound()
    error_msg = encode_args_with_signature("EarnInvalidDelegateAmount(address,uint256)", [str(accounts[0]), int(100)])
    with brownie.reverts(f"typed error: {error_msg}"):
        earn.delegateStaking(operator, {'value': 100})


def test_invalid_validator(earn, pledge_agent, stcore):
    error_msg = encode_args_with_signature("EarnInvalidValidator(address)",
                                           ["0x0000000000000000000000000000000000000000"])
    with brownie.reverts(f"typed error: {error_msg}"):
        earn.delegateStaking("0x0000000000000000000000000000000000000000", {"value": ONE_ETHER * 30})


def test_delegate_staking_failed(earn, pledge_agent, stcore):
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    turn_round()
    earn.afterTurnRound()
    error_msg = encode_args_with_signature("EarnDelegateFailed(address,address,uint256)",
                                           [str(accounts[0]), str(accounts[-5]), ONE_ETHER * 30])
    with brownie.reverts(f"typed error: {error_msg}"):
        earn.delegateStaking(accounts[-5], {'value': ONE_ETHER * 30})


def test_multiple_users_delegate_stake(earn, pledge_agent, stcore):
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    turn_round()
    earn.afterTurnRound()
    delegate_staking_information = [(operators[0], ONE_ETHER * 22, accounts[0]),
                                    (operators[1], ONE_ETHER * 11, accounts[0]),
                                    (operators[2], ONE_ETHER * 3, accounts[1]),
                                    (operators[1], ONE_ETHER * 6, accounts[2])]
    for index, delegate in enumerate(delegate_staking_information):
        validator = delegate[0]
        amount = delegate[1]
        account = delegate[2]
        earn.delegateStaking(validator, {'value': amount, 'from': account})
        assert earn.getDelegateActionQueue(index) == [validator, amount]
    assert earn.getValidatorDelegate(operators[0])['amount'] == ONE_ETHER * 22
    assert earn.getValidatorDelegate(operators[1])['amount'] == ONE_ETHER * 17
    assert earn.getValidatorDelegate(operators[2])['amount'] == ONE_ETHER * 3
    assert stcore.totalSupply() == ONE_ETHER * 42
    assert stcore.balanceOf(accounts[0]) == ONE_ETHER * 33
    assert stcore.balanceOf(accounts[1]) == ONE_ETHER * 3
    assert stcore.balanceOf(accounts[2]) == ONE_ETHER * 6


def test_trigger_rewards_claim_and_reinvest(earn, pledge_agent, stcore, validator_set):
    operators = []
    consensuses = []
    delegate_amount = MIN_DELEGATE_VALUE * 3
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': delegate_amount})
    turn_round()
    turn_round(consensuses, round_count=1)
    tx = earn.afterTurnRound()
    assert 'claimedReward' in tx.events
    assert 'delegatedCoin' in tx.events
    assert tx.events['claimedReward']['amount'] == tx.events['delegatedCoin']['amount'] == BLOCK_REWARD // 2
    delegator_info0 = pledge_agent.getDelegator(operators[0], earn.address)
    assert delegator_info0['newDeposit'] == delegate_amount + BLOCK_REWARD // 2


def test_trigger_handle_staking_failure(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    delegate_amount = MIN_DELEGATE_VALUE * 3
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': delegate_amount})
    turn_round()
    earn.afterTurnRound()
    candidate_hub.refuseDelegate({'from': operators[0]})
    turn_round(consensuses, round_count=1)
    tx = earn.afterTurnRound()
    assert 'delegatedCoin' not in tx.events
    delegate_info = earn.getValidatorDelegate(operators[0])
    assert delegate_info['earning'] == BLOCK_REWARD // 2
    assert delegate_info['amount'] == delegate_amount
    turn_round(consensuses, round_count=1, trigger=True)
    candidate_hub.acceptDelegate({'from': operators[0]})
    tx1 = turn_round(consensuses, round_count=1, trigger=True)
    delegate_info = earn.getValidatorDelegate(operators[0])
    assert delegate_info['earning'] == 0
    assert delegate_info['amount'] == delegate_amount + BLOCK_REWARD // 2 == tx1.events['delegatedCoin']['totalAmount']
    assert 'delegatedCoin' in tx1.events
    assert tx1.events['delegatedCoin']['agent'] == operators[0]


def test_trigger_reward_too_small(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    block_reward0 = 8000
    block_reward1 = 200
    total_reward0 = (block_reward0 + 100) * 90 / 100
    total_reward1 = (block_reward1 + 100) * 90 / 100 // 2
    consensuses = []
    delegate_amount = MIN_DELEGATE_VALUE * 3
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': delegate_amount})
    turn_round(trigger=True)
    validator_set.updateBlockReward(block_reward0)
    tx = turn_round(consensuses, round_count=1, trigger=True)
    assert 'delegatedCoin' not in tx.events
    delegate_info = earn.getValidatorDelegate(operators[0])
    assert delegate_info['earning'] == total_reward0 // 2 == tx.events['claimedReward']['amount']
    assert delegate_info['amount'] == delegate_amount
    validator_set.updateBlockReward(block_reward1)
    turn_round(consensuses, round_count=1, trigger=True)
    validator_set.updateBlockReward(block_reward0)
    assert get_exchangerate() == RATE_MULTIPLE
    tx1 = turn_round(consensuses, round_count=1, trigger=True)
    assert 'delegatedCoin' in tx1.events
    delegate_info = earn.getValidatorDelegate(operators[0])
    assert delegate_info['earning'] == 0
    assert delegate_info['amount'] == total_reward0 + delegate_amount + total_reward1
    assert tx1.events['delegatedCoin']['amount'] == total_reward0 + total_reward1
    assert get_exchangerate() == (total_reward0 + delegate_amount + total_reward1) * RATE_MULTIPLE / delegate_amount


def test_trigger_delegate_failed(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    block_reward0 = 8000
    total_reward0 = (block_reward0 + 100) * 90 / 100
    consensuses = []
    delegate_amount = MIN_DELEGATE_VALUE * 3
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': delegate_amount})
    turn_round(trigger=True)
    validator_set.updateBlockReward(block_reward0)
    tx = turn_round(consensuses, round_count=1, trigger=True)
    assert 'delegatedCoin' not in tx.events
    candidate_hub.refuseDelegate({'from': operators[0]})
    turn_round(consensuses, round_count=1, trigger=True)
    delegate_info = earn.getValidatorDelegate(operators[0])
    assert delegate_info['earning'] == total_reward0
    candidate_hub.acceptDelegate({'from': operators[0]})
    tx1 = turn_round(consensuses, round_count=1, trigger=True)
    assert 'delegatedCoin' in tx1.events


def test_trigger_claim_reward_failed_delegate(earn, pledge_agent, stcore, candidate_hub):
    operators = []
    consensuses = []
    delegate_amount = MIN_DELEGATE_VALUE
    total_reward = BLOCK_REWARD // 2
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': delegate_amount})
    turn_round(trigger=True)
    earn.setAfterTurnRoundClaimReward(False)
    tx0 = turn_round(consensuses, round_count=1, trigger=True)
    assert 'claimedReward' not in tx0.events
    assert earn.getValidatorDelegate(operators[0])['earning'] == 0
    tx1 = earn.delegateStaking(operators[0], {'value': delegate_amount})
    assert 'claimedReward' in tx1.events
    assert tx1.events['delegatedCoin']['amount'] == delegate_amount
    assert earn.getValidatorDelegate(operators[0])['earning'] == tx1.events['claimedReward'][
        'amount'] == BLOCK_REWARD // 2
    tx2 = turn_round(consensuses, trigger=True)
    assert 'claimedReward' in tx2.events
    assert earn.getValidatorDelegate(operators[0])['earning'] == BLOCK_REWARD // 2
    assert tx1.events['claimedReward']['amount'] == tx2.events['delegatedCoin']['amount'] == BLOCK_REWARD // 2
    assert get_exchangerate() == (delegate_amount * 2 + total_reward) * RATE_MULTIPLE // (delegate_amount * 2)
    earn.setAfterTurnRoundClaimReward(True)
    tx3 = turn_round(consensuses, trigger=True)
    assert 'claimedReward' in tx3.events
    assert earn.getValidatorDelegate(operators[0])['earning'] == 0
    assert tx3.events['claimedReward']['amount'] == BLOCK_REWARD // 2
    assert tx3.events['delegatedCoin']['amount'] == BLOCK_REWARD
    assert tx3.events['delegatedCoin']['totalAmount'] == delegate_amount * 2 + BLOCK_REWARD // 2 * 3
    assert get_exchangerate() == (delegate_amount * 2 + total_reward * 3) * RATE_MULTIPLE // (delegate_amount * 2)


def test_trigger_claim_reward_failed_undelegate(earn, pledge_agent, stcore, candidate_hub):
    operators = []
    consensuses = []
    delegate_amount = MIN_DELEGATE_VALUE
    total_reward = BLOCK_REWARD // 2
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': delegate_amount})
    turn_round(trigger=True)
    earn.setAfterTurnRoundClaimReward(False)
    tx0 = turn_round(consensuses, round_count=1, trigger=True)
    assert 'claimedReward' not in tx0.events
    assert earn.getValidatorDelegate(operators[0])['earning'] == 0
    token_value = delegate_amount // 2
    tx1 = earn.redeem(token_value)
    assert 'claimedReward' in tx1.events
    assert tx1.events['undelegatedCoin']['amount'] == token_value
    assert earn.getValidatorDelegate(operators[0])['earning'] == tx1.events['claimedReward'][
        'amount'] == BLOCK_REWARD // 2
    tx2 = turn_round(consensuses, trigger=True)
    assert 'claimedReward' in tx2.events
    assert earn.getValidatorDelegate(operators[0])['earning'] == total_reward - total_reward // 2
    assert tx1.events['claimedReward']['amount'] == tx2.events['delegatedCoin']['amount'] == BLOCK_REWARD // 2
    assert get_exchangerate() == (delegate_amount + total_reward - delegate_amount // 2) * RATE_MULTIPLE // (
            delegate_amount // 2)
    earn.setAfterTurnRoundClaimReward(True)
    tx3 = turn_round(consensuses, trigger=True)
    assert 'claimedReward' in tx3.events
    total_amount = token_value + BLOCK_REWARD + total_reward - total_reward // 2
    assert earn.getValidatorDelegate(operators[0])['earning'] == 0
    assert tx3.events['claimedReward']['amount'] == BLOCK_REWARD // 2
    assert tx3.events['delegatedCoin']['amount'] == total_reward + (total_reward - total_reward // 2)
    assert tx3.events['delegatedCoin']['totalAmount'] == total_amount
    assert get_exchangerate() == total_amount * RATE_MULTIPLE // token_value


def test_minimum_reinvestment_limit_in_trigger_reward(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    block_reward0 = 8000
    total_reward0 = (block_reward0 + 100) * 90 / 100
    consensuses = []
    delegate_amount = MIN_DELEGATE_VALUE * 3
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': delegate_amount})
    turn_round(trigger=True)
    validator_set.updateBlockReward(block_reward0)
    tx = turn_round(consensuses, round_count=1, trigger=True)
    assert 'delegatedCoin' not in tx.events
    tx1 = turn_round(consensuses, round_count=1, trigger=True)
    delegate_info = earn.getValidatorDelegate(operators[0])
    assert delegate_info['earning'] == 0
    assert delegate_info['amount'] == delegate_amount + total_reward0
    assert 'delegatedCoin' in tx1.events
    assert get_exchangerate() == (total_reward0 + delegate_amount) * RATE_MULTIPLE / delegate_amount


def test_trigger_calculate_exchange_rate_scenario_1(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    total_reward = BLOCK_REWARD // 4 * 2
    block_reward0 = 40000
    total_reward0 = (block_reward0 + 100) * 90 / 100 // 4 * 2
    total_supply = MIN_DELEGATE_VALUE * 4
    total_delegate_amount = MIN_DELEGATE_VALUE * 4
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': MIN_DELEGATE_VALUE * 2, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': MIN_DELEGATE_VALUE * 2, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, trigger=True)
    total_delegate_amount += total_reward
    assert get_exchangerate() == total_delegate_amount * RATE_MULTIPLE / total_supply
    validator_set.updateBlockReward(block_reward0)
    turn_round(consensuses, round_count=1, trigger=True)
    total_delegate_amount += total_reward0
    assert get_exchangerate() == total_delegate_amount * RATE_MULTIPLE / total_supply


def test_trigger_calculate_exchange_rate_scenario_2(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    total_reward = BLOCK_REWARD // 4 * 2
    total_supply = MIN_DELEGATE_VALUE * 4
    total_delegate_amount = MIN_DELEGATE_VALUE * 4
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': MIN_DELEGATE_VALUE * 2, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': MIN_DELEGATE_VALUE * 2, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round(trigger=True)
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    turn_round(consensuses, round_count=1, trigger=True)
    added_amount = total_reward + MIN_DELEGATE_VALUE
    total_delegate_amount += added_amount
    total_supply += MIN_DELEGATE_VALUE
    assert get_exchangerate() == total_delegate_amount * RATE_MULTIPLE // total_supply
    turn_round(consensuses, round_count=1, trigger=True)
    total_delegate_amount += (total_reward * 3 / 5 + total_reward // 2)
    assert int(stcore.totalSupply()) == total_supply
    assert get_exchangerate() == total_delegate_amount * RATE_MULTIPLE // total_supply


def test_trigger_calculate_exchange_rate_scenario_3(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    total_reward = BLOCK_REWARD // 4 * 2
    total_supply = MIN_DELEGATE_VALUE * 4
    total_delegate_amount = MIN_DELEGATE_VALUE * 4
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': MIN_DELEGATE_VALUE * 2, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': MIN_DELEGATE_VALUE * 2, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, trigger=True)
    total_delegate_amount += total_reward
    exchange_rate = total_delegate_amount * RATE_MULTIPLE / total_supply
    assert get_exchangerate() == exchange_rate
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    stcore_value = MIN_DELEGATE_VALUE * RATE_MULTIPLE // exchange_rate
    total_supply += stcore_value
    turn_round(consensuses, round_count=1, trigger=True)
    total_delegate_amount += (total_reward + MIN_DELEGATE_VALUE)
    assert stcore.totalSupply() == total_supply
    assert get_exchangerate() == total_delegate_amount * RATE_MULTIPLE // total_supply


def test_trigger_calculate_exchange_rate_scenario_4(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    block_reward0 = 360 * ONE_ETHER
    validator_set.updateBlockReward(block_reward0)
    tx_fee = 0.01 * ONE_ETHER
    total_reward0 = (block_reward0 + tx_fee) * 90 / 100 // 4 * 2
    total_supply = ONE_ETHER * 4000
    delegate_amount = ONE_ETHER * 1000
    total_delegate_amount = ONE_ETHER * 4000
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': delegate_amount * 2, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': delegate_amount * 2, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': delegate_amount})
    earn.delegateStaking(operators[1], {'value': delegate_amount})
    earn.delegateStaking(operators[0], {'value': delegate_amount, 'from': accounts[1]})
    earn.delegateStaking(operators[1], {'value': delegate_amount, 'from': accounts[1]})
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, tx_fee=tx_fee, trigger=True)
    total_delegate_amount += total_reward0
    exchange_rate = total_delegate_amount * RATE_MULTIPLE // total_supply
    assert get_exchangerate() == exchange_rate
    earn.delegateStaking(operators[0], {'value': delegate_amount})
    pledge_agent.delegateCoin(operators[0], {'value': delegate_amount, 'from': accounts[1]})
    turn_round(consensuses, round_count=1, tx_fee=tx_fee, trigger=True)
    stcore_value = delegate_amount * RATE_MULTIPLE // exchange_rate
    total_supply += stcore_value
    total_delegate_amount += delegate_amount + total_reward0
    assert get_exchangerate() == total_delegate_amount * RATE_MULTIPLE // total_supply


def test_redemption_successful(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    total_reward = BLOCK_REWARD // 4 * 2
    total_supply = MIN_DELEGATE_VALUE * 4
    total_delegate_amount = MIN_DELEGATE_VALUE * 4
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': MIN_DELEGATE_VALUE * 2, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': MIN_DELEGATE_VALUE * 2, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, trigger=True)
    # redeem
    token_value = MIN_DELEGATE_VALUE * 2
    total_delegate_amount += total_reward
    exchange_rate = total_delegate_amount * RATE_MULTIPLE / total_supply
    exchange_amount = token_value * exchange_rate / RATE_MULTIPLE

    assert stcore.totalSupply() == total_supply
    assert earn.getDelegateActionQueueLength() == 6
    tx = earn.redeem(token_value)
    expect_event(tx, "Transfer", {
        "from": accounts[0],
        "to": '0x0000000000000000000000000000000000000000',
        "value": token_value,
    })
    expect_event(tx, "undelegatedCoin", {
        "agent": operators[0],
        "delegator": earn.address,
        "amount": MIN_DELEGATE_VALUE,
    }, idx=0)
    expect_event(tx, "undelegatedCoin", {
        "agent": operators[1],
        "delegator": earn.address,
        "amount": MIN_DELEGATE_VALUE,
    }, idx=1)
    expect_event(tx, "undelegatedCoin", {
        "agent": operators[0],
        "delegator": earn.address,
        "amount": exchange_amount - MIN_DELEGATE_VALUE * 2,
    }, idx=2)
    assert stcore.balanceOf(accounts[0]) == 0
    queue_length = 4
    redeem_info = earn.getRedeemRecords()[0]
    assert earn.getDelegateActionQueueLength() == queue_length
    assert earn.getDelegateActionQueue(queue_length - 1)['amount'] == MIN_DELEGATE_VALUE * 3 - exchange_amount
    interval = INIT_DAY_INTERVAL * LOCK_DAY
    redeem_time = redeem_info[1] // 100
    now_time = time.time() // 100
    assert redeem_time == now_time
    assert redeem_info[2] - redeem_info[1] == interval
    assert redeem_info[3] == exchange_amount
    assert redeem_info[4] == token_value


def test_coin_redemption_in_second_round_successful(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    total_supply = MIN_DELEGATE_VALUE * 2
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, trigger=True)
    token_value = MIN_DELEGATE_VALUE // 2
    exchange_amount = token_value * get_exchangerate() / RATE_MULTIPLE
    print(exchange_amount)
    action_queue_length = 4
    assert stcore.totalSupply() == total_supply
    assert earn.getDelegateActionQueueLength() == action_queue_length
    earn.redeem(token_value)
    redeem_info = earn.getRedeemRecords()[0]
    assert redeem_info[3] == exchange_amount
    assert redeem_info[4] == token_value


def test_investment_redemption_queue(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    total_reward = BLOCK_REWARD // 4 * 2
    total_supply = MIN_DELEGATE_VALUE * 2
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, trigger=True)
    token_value = MIN_DELEGATE_VALUE
    exchange_amount = token_value * get_exchangerate() / RATE_MULTIPLE
    print(exchange_amount)
    action_queue_length = 4
    assert stcore.totalSupply() == total_supply
    assert earn.getDelegateActionQueueLength() == action_queue_length
    action_queue = []
    for i in range(action_queue_length):
        action_queue.append(earn.getDelegateActionQueue(i))
    assert action_queue == [(operators[0], MIN_DELEGATE_VALUE), (operators[1], MIN_DELEGATE_VALUE),
                            (operators[0], total_reward // 2), (operators[1], total_reward // 2)]
    tx = earn.redeem(token_value)
    print(tx.events)
    expect_event(tx, "undelegatedCoin", {
        "agent": operators[0],
        "delegator": earn.address,
        "amount": MIN_DELEGATE_VALUE,
    }, idx=0)
    expect_event(tx, "undelegatedCoin", {
        "agent": operators[1],
        "delegator": earn.address,
        "amount": exchange_amount - token_value,
    }, idx=1)
    action_queue = []
    for i in range(action_queue_length - 1):
        action_queue.append(earn.getDelegateActionQueue(i))
    assert action_queue == [(operators[0], total_reward // 2), (operators[1], total_reward // 2),
                            (operators[1], MIN_DELEGATE_VALUE - total_reward // 2)]


def test_redeem_and_undelegate_from_single_validator(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    total_supply = MIN_DELEGATE_VALUE * 2
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round(trigger=True)
    token_value = MIN_DELEGATE_VALUE
    assert stcore.totalSupply() == total_supply
    action_queue_length = 2
    assert earn.getDelegateActionQueueLength() == action_queue_length
    earn.redeem(token_value)
    action_queue = []
    action_queue_length = 2
    assert earn.getDelegateActionQueueLength() == action_queue_length - 1
    for i in range(action_queue_length - 1):
        action_queue.append(earn.getDelegateActionQueue(i))
    assert action_queue == [(operators[1], MIN_DELEGATE_VALUE)]
    redeem_info = earn.getRedeemRecords()[0]
    assert redeem_info[3] == MIN_DELEGATE_VALUE
    assert redeem_info[4] == MIN_DELEGATE_VALUE


def test_redeem_and_undelegate_from_multiple_validators(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    total_reward = BLOCK_REWARD // 4 * 2
    total_supply = MIN_DELEGATE_VALUE * 2
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    stcore.transfer(accounts[0], MIN_DELEGATE_VALUE, {'from': accounts[1]})
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, trigger=True)
    token_value = MIN_DELEGATE_VALUE * 2
    assert stcore.totalSupply() == total_supply
    assert earn.getDelegateActionQueueLength() == 4
    tracker0 = get_tracker(earn)
    tx = earn.redeem(token_value)
    assert earn.getDelegateActionQueueLength() == 0
    assert tracker0.delta() == token_value + total_reward
    redeem_info = earn.getRedeemRecords()[0]
    assert redeem_info[3] == token_value + total_reward
    assert redeem_info[4] == token_value


def test_redeem_and_undelegate(earn, pledge_agent, validator_set, stcore, candidate_hub):
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    pledge_agent.delegateCoin(operators[0], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    pledge_agent.delegateCoin(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, trigger=True)
    token_value = MIN_DELEGATE_VALUE // 2
    queue_length = 4
    assert earn.getDelegateActionQueueLength() == queue_length
    tracker0 = get_tracker(earn)
    exchange_amount = token_value * get_exchangerate() / RATE_MULTIPLE
    earn.redeem(token_value)
    assert earn.getDelegateActionQueue(queue_length - 1)['amount'] == MIN_DELEGATE_VALUE - exchange_amount
    assert tracker0.delta() == exchange_amount
    redeem_info = earn.getRedeemRecords()[0]
    assert redeem_info[3] == exchange_amount
    assert redeem_info[4] == token_value


def test_redeem_below_min_limit(earn, stcore):
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    token_value = 100
    error_msg = encode_args_with_signature("EarnInvalidExchangeAmount(address,uint256)",
                                           [accounts[0].address, token_value])
    with brownie.reverts(f"typed error: {error_msg}"):
        earn.redeem(token_value)


def test_redeem_no_investment(earn, stcore):
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    token_value = MIN_DELEGATE_VALUE
    error_msg = encode_args_with_signature("EarnERC20InsufficientTotalSupply(address,uint256,uint256)",
                                           [accounts[0].address, token_value, 0])
    with brownie.reverts(f"typed error: {error_msg}"):
        earn.redeem(token_value)


def test_redeem_exceed_token_limit(earn):
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    token_value = MIN_DELEGATE_VALUE + 100
    error_msg = encode_args_with_signature("EarnERC20InsufficientTotalSupply(address,uint256,uint256)",
                                           [accounts[0].address, token_value, MIN_DELEGATE_VALUE])
    with brownie.reverts(f"typed error: {error_msg}"):
        earn.redeem(token_value)


def test_redeem_exceed_own_token_balance(earn, stcore):
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    stcore.transfer(accounts[1], MIN_DELEGATE_VALUE // 2)
    token_value = MIN_DELEGATE_VALUE
    error_msg = encode_args_with_signature("EarnBurnFailed(address,uint256,uint256)",
                                           [accounts[0].address, MIN_DELEGATE_VALUE, MIN_DELEGATE_VALUE])
    with brownie.reverts(f"typed error: {error_msg}"):
        earn.redeem(token_value, {'from': accounts[0]})


def test_redeem_all_tokens_single_user(earn, stcore):
    operators = []
    consensuses = []
    total_reward = BLOCK_REWARD // 2
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, trigger=True)
    stcore.transfer(accounts[0], MIN_DELEGATE_VALUE, {'from': accounts[1]})
    token_value = MIN_DELEGATE_VALUE * 2
    tracker0 = get_tracker(earn)
    exchange_amount = token_value * get_exchangerate() / RATE_MULTIPLE
    earn.redeem(token_value)
    assert tracker0.delta() == exchange_amount == MIN_DELEGATE_VALUE * 2 + total_reward * 2


def test_partial_undelegate_requeue(earn):
    operators = []
    consensuses = []
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    turn_round(trigger=True)
    token_value = MIN_DELEGATE_VALUE // 2
    action_queue_length = 1
    assert earn.getDelegateActionQueueLength() == action_queue_length
    assert earn.getDelegateActionQueue(0)['validator'] == operators[0]
    assert earn.getDelegateActionQueue(0)['amount'] == MIN_DELEGATE_VALUE
    earn.redeem(token_value)
    assert earn.getDelegateActionQueueLength() == action_queue_length
    assert earn.getDelegateActionQueue(0)['validator'] == operators[0]
    assert earn.getDelegateActionQueue(0)['amount'] == MIN_DELEGATE_VALUE // 2


def test_redeem_without_rewards(earn, stcore):
    operators = []
    consensuses = []
    total_supply = MIN_DELEGATE_VALUE * 2
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    earn.delegateStaking(operators[1], {'value': MIN_DELEGATE_VALUE, 'from': accounts[1]})
    tx = earn.redeem(MIN_DELEGATE_VALUE)
    expect_event(tx, "undelegatedCoin", {
        "agent": operators[0],
        "delegator": earn.address,
        "amount": MIN_DELEGATE_VALUE,
    }, idx=0)
    total_supply -= MIN_DELEGATE_VALUE
    turn_round(trigger=True)
    turn_round(consensuses, round_count=1, trigger=True)
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE * 3})
    token_value = MIN_DELEGATE_VALUE * 3 * RATE_MULTIPLE // get_exchangerate()
    assert stcore.balanceOf(accounts[0]) == token_value
    earn.redeem(token_value)
    assert stcore.balanceOf(accounts[0]) == 0
    assert stcore.totalSupply() == total_supply
    redeem_info = earn.getRedeemRecords()[1]
    assert redeem_info[3] == token_value * get_exchangerate() // RATE_MULTIPLE
    assert redeem_info[4] == token_value


def test_user_redeem_unlocked_token(earn, stcore):
    operators = []
    consensuses = []
    total_supply = MIN_DELEGATE_VALUE * 2
    for operator in accounts[2:5]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    earn.delegateStaking(operators[0], {'value': MIN_DELEGATE_VALUE})
    tx = earn.redeem(MIN_DELEGATE_VALUE)
    print(tx.events)
    redeem_records = earn.getRedeemRecords()
    print(redeem_records)
    earn.withdraw(1)
