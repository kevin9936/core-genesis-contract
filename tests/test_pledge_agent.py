import pytest
import brownie
from brownie import accounts
from eth_abi import encode_abi
from web3 import Web3
from .calc_reward import parse_delegation, set_delegate
from .utils import random_address, expect_event, expect_event_not_emitted, get_tracker, \
    encode_args_with_signature
from .common import register_candidate, turn_round, get_current_round

MIN_INIT_DELEGATE_VALUE = 0
POWER_FACTOR = 0
POWER_BLOCK_FACTOR = 0
CANDIDATE_REGISTER_MARGIN = 0
candidate_hub_instance = None
pledge_agent_instance = None
btc_light_client_instance = None
required_coin_deposit = 0
TX_FEE = Web3.toWei(1, 'ether')
actual_block_reward = 0
DENOMINATOR = 10000


@pytest.fixture(scope="module", autouse=True)
def set_up(min_init_delegate_value, pledge_agent, candidate_hub, btc_light_client, validator_set):
    global MIN_INIT_DELEGATE_VALUE
    global POWER_FACTOR
    global POWER_BLOCK_FACTOR
    global CANDIDATE_REGISTER_MARGIN
    global candidate_hub_instance
    global pledge_agent_instance
    global required_coin_deposit
    global btc_light_client_instance
    global actual_block_reward

    candidate_hub_instance = candidate_hub
    pledge_agent_instance = pledge_agent
    btc_light_client_instance = btc_light_client
    MIN_INIT_DELEGATE_VALUE = min_init_delegate_value
    POWER_FACTOR = pledge_agent.powerFactor()
    POWER_BLOCK_FACTOR = pledge_agent.POWER_BLOCK_FACTOR()
    CANDIDATE_REGISTER_MARGIN = candidate_hub.requiredMargin()
    required_coin_deposit = pledge_agent.requiredCoinDeposit()

    block_reward = validator_set.blockReward()
    block_reward_incentive_percent = validator_set.blockRewardIncentivePercent()
    total_block_reward = block_reward + TX_FEE
    actual_block_reward = total_block_reward * (100 - block_reward_incentive_percent) // 100


@pytest.fixture(scope="module", autouse=True)
def deposit_for_reward(validator_set):
    accounts[-2].transfer(validator_set.address, Web3.toWei(100000, 'ether'))


class TestDelegateCoin:
    def test_delegate2unregistered_agent(self, pledge_agent):
        random_agent_addr = random_address()
        error_msg = encode_args_with_signature("InactiveAgent(address)", [random_agent_addr])
        with brownie.reverts(f"typed error: {error_msg}"):
            pledge_agent.delegateCoin(random_agent_addr)

    def test_delegate2registered_agent(self, pledge_agent):
        operator = accounts[1]
        register_candidate(operator=operator)
        tx = pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
        expect_event(tx, "delegatedCoin", {
            "agent": operator,
            "delegator": accounts[0],
            "amount": MIN_INIT_DELEGATE_VALUE,
            "totalAmount": MIN_INIT_DELEGATE_VALUE
        })

    @pytest.mark.parametrize("second_value", [
        pytest.param(0, marks=pytest.mark.xfail),
        1,
        100,
        10000000,
        9999999999
    ])
    def test_delegate_multiple_times(self, pledge_agent, second_value):
        operator = accounts[1]
        register_candidate(operator=operator)
        pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
        if second_value >= MIN_INIT_DELEGATE_VALUE:
            tx = pledge_agent.delegateCoin(operator, {"value": second_value})
            expect_event(tx, "delegatedCoin", {
                "amount": second_value,
                "totalAmount": MIN_INIT_DELEGATE_VALUE + second_value
            })
        else:
            with brownie.reverts('deposit is too small'):
                pledge_agent.delegateCoin(operator, {"value": second_value})

    def test_delegate2refused(self, pledge_agent, candidate_hub):
        operator = accounts[1]
        register_candidate(operator=operator)
        candidate_hub.refuseDelegate({'from': operator})
        error_msg = encode_args_with_signature("InactiveAgent(address)", [operator.address])
        with brownie.reverts(f"typed error: {error_msg}"):
            pledge_agent.delegateCoin(operator)

    def test_delegate2validator(self, pledge_agent, candidate_hub, validator_set):
        operator = accounts[1]
        consensus_address = register_candidate(operator=operator)
        candidate_hub.turnRound()
        assert validator_set.isValidator(consensus_address)
        tx = pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
        expect_event(tx, "delegatedCoin", {
            "agent": operator,
            "delegator": accounts[0],
            "amount": MIN_INIT_DELEGATE_VALUE,
            "totalAmount": MIN_INIT_DELEGATE_VALUE
        })

    def test_delegate2jailed(self, pledge_agent, slash_indicator, candidate_hub, validator_set):
        register_candidate(operator=accounts[10])

        operator = accounts[1]
        margin = candidate_hub.requiredMargin() + slash_indicator.felonyDeposit()
        consensus_address = register_candidate(operator=operator, margin=margin)
        candidate_hub.turnRound()

        assert len(validator_set.getValidators()) == 2

        felony_threshold = slash_indicator.felonyThreshold()
        for _ in range(felony_threshold):
            slash_indicator.slash(consensus_address)

        assert candidate_hub.isJailed(operator) is True
        error_msg = encode_args_with_signature("InactiveAgent(address)", [operator.address])
        with brownie.reverts(f"typed error: {error_msg}"):
            pledge_agent.delegateCoin(operator)

    def test_delegate2under_margin(self, pledge_agent, slash_indicator, candidate_hub, validator_set):
        register_candidate(operator=accounts[10])
        operator = accounts[1]
        consensus_address = register_candidate(operator=operator)
        turn_round()

        assert len(validator_set.getValidators()) == 2
        assert validator_set.currentValidatorSetMap(consensus_address) > 0
        felony_threshold = slash_indicator.felonyThreshold()
        for _ in range(felony_threshold):
            slash_indicator.slash(consensus_address)
        assert candidate_hub.isJailed(operator) is True

        felony_round = slash_indicator.felonyRound()
        turn_round(round_count=felony_round)
        assert candidate_hub.isJailed(operator) is False

        error_msg = encode_args_with_signature("InactiveAgent(address)", [operator.address])
        with brownie.reverts(f"typed error: {error_msg}"):
            pledge_agent.delegateCoin(operator)


class TestUndelegateCoin:
    def test_undelegate(self, pledge_agent):
        operator = accounts[1]
        register_candidate(operator=operator)
        pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
        turn_round()
        tx = pledge_agent.undelegateCoin(operator)
        expect_event(tx, "undelegatedCoin", {
            "agent": operator,
            "delegator": accounts[0],
            "amount": MIN_INIT_DELEGATE_VALUE
        })

    def test_undelegate_failed(self, pledge_agent):
        operator = accounts[1]
        register_candidate(operator=operator)
        turn_round()
        with brownie.reverts("Not enough deposit token"):
            pledge_agent.undelegateCoin(operator)

    def test_fail_to_undelegate_after_transfer(self, pledge_agent):
        delegate_amount = MIN_INIT_DELEGATE_VALUE * 10
        operators = []
        consensuses = []
        transfer_amount0 = delegate_amount // 2
        undelegate_amount = transfer_amount0 + MIN_INIT_DELEGATE_VALUE
        for operator in accounts[4:7]:
            operators.append(operator)
            consensuses.append(register_candidate(operator=operator))
        pledge_agent.delegateCoin(operators[0], {"value": delegate_amount, 'from': accounts[0]})
        turn_round()
        pledge_agent.transferCoin(operators[0], operators[1], transfer_amount0, {'from': accounts[0]})
        with brownie.reverts("Not enough deposit token"):
            pledge_agent.undelegateCoin(operators[0], undelegate_amount)

    def test_undelegeate_self(self, pledge_agent):
        register_candidate()
        pledge_agent.delegateCoin(accounts[0], {"value": MIN_INIT_DELEGATE_VALUE})
        turn_round()
        tx = pledge_agent.undelegateCoin(accounts[0])
        expect_event(tx, "undelegatedCoin", {
            "agent": accounts[0],
            "delegator": accounts[0],
            "amount": MIN_INIT_DELEGATE_VALUE
        })

    def test_undelegate_with_reward(self, pledge_agent):
        operator = accounts[1]
        consensus = register_candidate(operator=operator)
        pledge_agent.delegateCoin(operator, {"value": MIN_INIT_DELEGATE_VALUE})
        turn_round([consensus])

        pledge_agent.undelegateCoin(operator)


def test_add_round_reward_success_with_normal_agent(pledge_agent, validator_set, candidate_hub, hash_power_agent,
                                                    btc_agent, stake_hub):
    agents = accounts[1:4]
    rewards = [1e7, 1e8]
    coins = [1e6, 4e6]
    powers = [2, 5]
    __candidate_register(agents[0])
    __candidate_register(agents[1])
    stake_hub.setCandidateAmountMap(agents[0], coins[0], powers[0], 0)
    stake_hub.setCandidateAmountMap(agents[1], coins[1], powers[1], 0)
    _, _, account_rewards, _, collateral_state = parse_delegation([{
        "address": agents[0],
        "active": True,
        "coin": [set_delegate(accounts[0], coins[0])],
        "power": [set_delegate(accounts[0], powers[0])],
        "btc": []
    }, {
        "address": agents[1],
        "active": True,
        "coin": [set_delegate(accounts[0], coins[1])],
        "power": [set_delegate(accounts[0], powers[1])],
        "btc": []
    }], 0)
    stake_hub.setStateMapDiscount(pledge_agent.address, 0, 1, collateral_state['coin'])
    round_tag = candidate_hub.roundTag()
    tx = validator_set.addRoundRewardMock(agents[:2], rewards, round_tag)
    factor = 500
    reward0 = rewards[0] * coins[0] / (coins[0] + powers[0] * factor)
    reward1 = rewards[1] * coins[1] / (coins[1] + powers[1] * factor)
    validator_coin_reward0 = reward0 * collateral_state['coin'] // DENOMINATOR
    validator_coin_reward1 = reward1 * collateral_state['coin'] // DENOMINATOR
    validator_power_reward0 = rewards[0] * (powers[0] * factor) // (coins[0] + powers[0] * factor)
    validator_power_reward1 = rewards[1] * (powers[1] * factor) // (coins[1] + powers[1] * factor)
    except_reward = [validator_coin_reward0, validator_coin_reward1, validator_power_reward0, validator_power_reward1]
    agents = [accounts[1], accounts[2], accounts[1], accounts[2]]
    for i in range(len(except_reward)):
        expect_event(tx, "roundReward", {
            "validator": agents[i],
            "amounted": except_reward[i]
        }, idx=i)


def test_add_round_reward_success_with_no_agent(pledge_agent, validator_set, candidate_hub, stake_hub, btc_agent):
    agents = accounts[1:4]
    rewards = (1e7, 1e8, 1e8)
    __candidate_register(agents[0])
    __candidate_register(agents[1])
    round_tag = candidate_hub.roundTag()
    tx = validator_set.addRoundRewardMock(agents, rewards, round_tag)
    expect_event_not_emitted(tx, "roundReward")


def test_add_round_reward_success(pledge_agent, validator_set, candidate_hub, stake_hub, btc_agent, btc_lst_stake,
                                  hash_power_agent):
    agents = accounts[1:4]
    rewards = (1e8, 1e8, 1e8)
    total_coin = 250
    btc_coin = 10
    total_power = 5
    __candidate_register(agents[0])
    __candidate_register(agents[1])
    stake_hub.setCandidateAmountMap(agents[0], total_coin, total_power, btc_coin * 2)
    stake_hub.setCandidateAmountMap(agents[1], total_coin, total_power, btc_coin)
    btc_agent.setCandidateMap(agents[0], btc_coin * 2, 0)
    btc_agent.setCandidateMap(agents[1], btc_coin, 0)
    _, _, account_rewards, collateral_reward, collateral_state = parse_delegation([{
        "address": agents[0],
        "active": True,
        "coin": [set_delegate(accounts[0], total_coin)],
        "power": [set_delegate(accounts[0], total_power)],
        "btc": [set_delegate(accounts[0], btc_coin * 2)]
    }, {
        "address": agents[1],
        "active": True,
        "coin": [set_delegate(accounts[0], total_coin)],
        "power": [set_delegate(accounts[0], total_power)],
        "btc": [set_delegate(accounts[0], btc_coin)]
    }], 1e8)
    stake_hub.setStateMapDiscount(hash_power_agent.address, 0, 500, collateral_state['power'])
    round_tag = candidate_hub.roundTag()
    tx = validator_set.addRoundRewardMock(agents, rewards, round_tag)
    for index, t in enumerate(tx.events['roundReward']):
        # core
        if t['name'] == Web3.keccak(text='CORE').hex():
            assert t['amounted'] == collateral_reward['coin'][t['validator']]
        # power
        elif t['name'] == Web3.keccak(text='HASHPOWER').hex():
            assert t['amounted'] == collateral_reward['power'][t['validator']]
        # btc
        elif t['name'] == Web3.keccak(text='BTC').hex():
            assert t['amounted'] == collateral_reward['btc'][t['validator']]


def test_add_round_reward_failed_with_invalid_argument(validator_set):
    agents = accounts[1:4]
    rewards = [1e7, 1e8]
    round_tag = get_current_round()
    with brownie.reverts("the length of agentList and rewardList should be equal"):
        validator_set.addRoundRewardMock(agents, rewards, round_tag)


def test_get_coin_score_success(candidate_hub, validator_set, stake_hub, btc_light_client, pledge_agent,
                                hash_power_agent, btc_agent):
    operators = []
    consensuses = []
    for operator in accounts[6:11]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    for i in range(3):
        __delegate_coin_success(operators[i], accounts[i], 0, required_coin_deposit + i)
    turn_round()
    turn_round(consensuses, tx_fee=TX_FEE)
    for i in range(3, 5):
        __delegate_coin_success(operators[i], accounts[i], 0, required_coin_deposit + i)
    candidate_hub.getScoreMock(operators, get_current_round())
    scores = candidate_hub.getScores()
    coin_hard_cap = 6000
    hard_cap_sum = 12000
    discount = coin_hard_cap * sum(scores) * DENOMINATOR // (hard_cap_sum * sum(scores))
    assert len(scores) == 5
    for i in range(5):
        expected_score = required_coin_deposit + i
        assert expected_score == scores[i]
        assert stake_hub.candidateScoreMap(operators[i]) == scores[i]
    assert stake_hub.stateMap(pledge_agent.address)['discount'] == discount


def test_get_power_score_success(candidate_hub, validator_set, stake_hub, btc_light_client, hash_power_agent):
    operators = []
    consensuses = []
    for operator in accounts[6:11]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    for i in range(5):
        btc_light_client.setMiners(get_current_round() - 5, operators[i], [accounts[i]])
    turn_round()
    turn_round(consensuses, tx_fee=TX_FEE)
    power = 500
    candidate_hub.getScoreMock(operators, get_current_round())
    scores = candidate_hub.getScores()
    power_hard_cap = 2000
    hard_cap_sum = 12000
    discount = power_hard_cap * sum(scores) * DENOMINATOR // (hard_cap_sum * power * 5)
    assert len(scores) == 5
    for i in range(5):
        expected_score = power
        assert expected_score == scores[i]
        assert stake_hub.candidateScoreMap(operators[i]) == scores[i]
    assert stake_hub.stateMap(hash_power_agent.address)['discount'] == discount


def test_get_coin_and_power_score_success(candidate_hub, validator_set, stake_hub, btc_light_client, hash_power_agent):
    operators = []
    consensuses = []
    for operator in accounts[6:11]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    for i in range(3):
        __delegate_coin_success(operators[i], accounts[i], 0, required_coin_deposit + i)
    for i in range(5):
        btc_light_client.setMiners(get_current_round() - 5, operators[i], [accounts[i]])
    turn_round()
    turn_round(consensuses, tx_fee=TX_FEE)
    for i in range(3, 5):
        __delegate_coin_success(operators[i], accounts[i], 0, required_coin_deposit + i)
    power = 500
    candidate_hub.getScoreMock(operators, get_current_round())
    scores = candidate_hub.getScores()
    power_hard_cap = 2000
    hard_cap_sum = 12000
    discount = power_hard_cap * sum(scores) * DENOMINATOR // (hard_cap_sum * power * 5)
    assert len(scores) == 5
    for i in range(5):
        expected_score = (required_coin_deposit + i) + power
        assert expected_score == scores[i]
        assert stake_hub.candidateScoreMap(operators[i]) == scores[i]
    assert stake_hub.stateMap(hash_power_agent.address)['discount'] == discount


def test_collect_coin_reward_success(validator_set, pledge_agent, stake_hub):
    operators = []
    consensuses = []
    for operator in accounts[6:11]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    turn_round()
    __delegate_coin_success(operators[0], accounts[0], 0, required_coin_deposit)
    # turn_round(consensuses, round_count=2)
    validator_set.deposit(consensuses[0], {'value': TX_FEE})
    print('get_current_round', get_current_round())
    turn_round()
    validator_set.deposit(consensuses[0], {'value': TX_FEE})
    turn_round()
    # validator_set.deposit(consensuses[0], {'value': TX_FEE})
    # tx = stake_hub.claimReward()
    expect_reward = actual_block_reward * 90 // 100 * 4
    delegator_tracker = get_tracker(accounts[0])
    result = pledge_agent.getDelegator(operators[0], accounts[0]).dict()
    round_tag = result['changeRound']
    tx = pledge_agent.collectCoinRewardMock(operators[0], accounts[0], 10, {'from': accounts[0]})
    reward_amount_M = pledge_agent.rewardAmountM()
    result = pledge_agent.getDelegator(operators[0], accounts[0]).dict()
    assert expect_reward == reward_amount_M

    assert delegator_tracker.delta() == 0

    assert result['deposit'] == 0
    assert required_coin_deposit == result['newDeposit']
    assert round_tag == result['changeRound']
    assert result['rewardIndex'] == 6


def test_delegate_coin_success(pledge_agent):
    agent = accounts[1]
    delegator = accounts[2]
    __candidate_register(agent)

    __delegate_coin_success(agent, delegator, 0, required_coin_deposit)
    round_tag = pledge_agent.roundTag()
    result = pledge_agent.getDelegator(agent, delegator).dict()
    __check_coin_delegator(result, 0, required_coin_deposit, round_tag, 0)

    reward_length = pledge_agent.getRewardLength(agent)
    assert reward_length == 0

    deposit = int(1e9)
    __delegate_coin_success(agent, delegator, required_coin_deposit, deposit)

    result = pledge_agent.getDelegator(agent, delegator).dict()
    __check_coin_delegator(result, 0, required_coin_deposit + deposit, round_tag, 0)

    turn_round()
    assert pledge_agent.getRewardLength(agent) == 1
    turn_round()
    assert pledge_agent.getRewardLength(agent) == 2

    tx = pledge_agent.delegateCoin(agent, {'from': delegator, 'value': deposit})
    round_tag = pledge_agent.roundTag()
    expect_event(tx, "delegatedCoin", {
        'agent': agent,
        'delegator': delegator,
        'amount': deposit,
        'totalAmount': required_coin_deposit + deposit * 2
    })
    result = pledge_agent.getDelegator(agent, delegator).dict()
    __check_coin_delegator(result, required_coin_deposit + deposit, required_coin_deposit + deposit * 2, round_tag, 1)


def test_delegate_coin_failed_with_insufficient_deposit(pledge_agent):
    agent = accounts[1]
    delegator = accounts[2]

    __candidate_register(agent)
    with brownie.reverts("deposit is too small"):
        pledge_agent.delegateCoin(agent, {'from': delegator, 'value': required_coin_deposit - 1})

    with brownie.reverts("deposit is too small"):
        pledge_agent.delegateCoin(agent, {'from': delegator})

    __delegate_coin_success(agent, delegator, 0, required_coin_deposit)
    with brownie.reverts("deposit is too small"):
        pledge_agent.delegateCoin(agent, {'from': delegator})


def test_delegate_coin_failed_with_invalid_candidate(pledge_agent):
    agent = accounts[1]
    delegator = accounts[2]

    error_msg = encode_args_with_signature("InactiveAgent(address)", [agent.address])
    with brownie.reverts(f"typed error: {error_msg}"):
        pledge_agent.delegateCoin(agent, {'from': delegator, 'value': required_coin_deposit - 1})


def test_undelegate_coin_success(pledge_agent):
    agent = accounts[1]
    delegator = accounts[2]
    __candidate_register(agent)

    __delegate_coin_success(agent, delegator, 0, required_coin_deposit)
    round_tag = pledge_agent.roundTag()
    result = pledge_agent.getDelegator(agent, delegator).dict()
    __check_coin_delegator(result, 0, required_coin_deposit, round_tag, 0)

    tx = pledge_agent.undelegateCoin(agent, {'from': delegator})
    expect_event(tx, "undelegatedCoin", {
        'agent': agent,
        'delegator': delegator,
        'amount': required_coin_deposit
    })
    __check_coin_delegator(pledge_agent.getDelegator(agent, delegator).dict(), 0, 0, 0, 0)


def test_undelegate_coin_failed_with_no_delegate(pledge_agent):
    agent = accounts[1]
    delegator = accounts[2]
    __candidate_register(agent)

    with brownie.reverts("delegator does not exist"):
        pledge_agent.undelegateCoin(agent, {'from': delegator})


def test_transfer_coin_success(pledge_agent):
    agent_source = accounts[1]
    agent_target = accounts[3]
    __candidate_register(agent_source)
    __candidate_register(agent_target)
    delegator = accounts[2]

    __delegate_coin_success(agent_source, delegator, 0, required_coin_deposit)
    round_tag = pledge_agent.roundTag()
    result = pledge_agent.getDelegator(agent_source, delegator).dict()
    __check_coin_delegator(result, 0, required_coin_deposit, round_tag, 0)

    tx = pledge_agent.transferCoin(agent_source, agent_target, {'from': delegator})
    expect_event(tx, "transferredCoin", {
        'sourceAgent': agent_source,
        'targetAgent': agent_target,
        'delegator': delegator,
        'amount': required_coin_deposit,
        'totalAmount': required_coin_deposit
    })
    __check_coin_delegator(pledge_agent.getDelegator(agent_target, delegator), 0, required_coin_deposit, round_tag, 0)


def test_transfer_coin_failed_with_no_delegator_in_source_agent(pledge_agent):
    agent_source = accounts[1]
    agent_target = accounts[3]
    __candidate_register(agent_source)
    __candidate_register(agent_target)
    delegator = accounts[2]

    with brownie.reverts("delegator does not exist"):
        pledge_agent.transferCoin(agent_source, agent_target, {'from': delegator})


def test_transfer_coin_failed_with_inactive_target_agent(pledge_agent):
    agent_source = accounts[1]
    agent_target = accounts[3]
    __candidate_register(agent_source)
    delegator = accounts[2]

    __delegate_coin_success(agent_source, delegator, 0, required_coin_deposit)
    round_tag = pledge_agent.roundTag()
    __check_coin_delegator(pledge_agent.getDelegator(agent_source, delegator).dict(), 0, required_coin_deposit,
                           round_tag, 0)

    error_msg = encode_args_with_signature("InactiveAgent(address)", [agent_target.address])
    with brownie.reverts(f"typed error: {error_msg}"):
        pledge_agent.transferCoin(agent_source, agent_target, {'from': delegator})


def test_transfer_coin_failed_with_same_agent(pledge_agent):
    agent_source = accounts[1]
    agent_target = agent_source
    __candidate_register(agent_source)
    delegator = accounts[2]

    __delegate_coin_success(agent_source, delegator, 0, required_coin_deposit)

    error_msg = encode_args_with_signature("SameCandidate(address,address)",
                                           [agent_source.address, agent_target.address])
    with brownie.reverts(f"typed error: {error_msg}"):
        pledge_agent.transferCoin(agent_source, agent_target, {'from': delegator})


def test_claim_reward_success_with_one_agent(pledge_agent, validator_set):
    agent = accounts[1]
    consensus_address = __candidate_register(agent)
    delegator = accounts[2]

    pledge_agent.delegateCoin(agent, {'from': delegator, 'value': required_coin_deposit})
    turn_round()
    tracker = get_tracker(delegator)

    validator_set.deposit(consensus_address, {'value': TX_FEE})
    validator_set.deposit(consensus_address, {'value': TX_FEE})
    turn_round()

    pledge_agent.claimReward([agent], {'from': delegator})
    assert actual_block_reward * 2 * 900 // 1000 == tracker.delta()


def test_claim_reward_with_multi_agent(pledge_agent, validator_set):
    staked_num = 5
    delegator = accounts[1]
    agent_list = []
    consensus_list = []
    expect_reward = 0

    for i in range(staked_num):
        agent_list.append(accounts[2 + i])
        consensus_list.append(__candidate_register(agent_list[i], 100 + i))
        if i < 3:
            pledge_agent.delegateCoin(agent_list[i], {'from': delegator, 'value': required_coin_deposit})
            expect_reward += actual_block_reward * (1000 - 100 - i) // 1000
    turn_round()
    tracker = get_tracker(delegator)
    for i in range(staked_num):
        validator_set.deposit(consensus_list[i], {'value': TX_FEE})
    turn_round()
    pledge_agent.claimReward(agent_list[:5], {'from': delegator})
    assert expect_reward == tracker.delta()


def test_claim_reward_with_transfer_coin(pledge_agent, validator_set):
    agent1 = accounts[1]
    agent2 = accounts[2]
    delegator = accounts[3]
    consensus_addr1 = __candidate_register(agent1, 100)
    consensus_addr2 = __candidate_register(agent2, 500)
    pledge_agent.delegateCoin(agent1, {'from': delegator, 'value': required_coin_deposit})
    pledge_agent.delegateCoin(agent2, {'from': delegator, 'value': required_coin_deposit})

    turn_round()

    validator_set.deposit(consensus_addr1, {'value': TX_FEE})
    validator_set.deposit(consensus_addr2, {'value': TX_FEE})

    turn_round()
    tracker = get_tracker(delegator)

    tx = pledge_agent.transferCoin(agent1, agent2, {'from': delegator})
    validator_set.deposit(consensus_addr1, {'value': TX_FEE})
    validator_set.deposit(consensus_addr2, {'value': TX_FEE})

    turn_round()

    pledge_agent.claimReward([agent1, agent2], {'from': delegator})
    expect_reward1 = actual_block_reward * 900 // 1000
    expect_reward2 = actual_block_reward * 500 // 1000 * 2
    assert (expect_reward1 + expect_reward2 + expect_reward1) == tracker.delta()


def __candidate_register(agent, percent=100):
    consensus_addr = random_address()
    fee_addr = random_address()
    candidate_hub_instance.register(consensus_addr, fee_addr, percent,
                                    {'from': agent, 'value': CANDIDATE_REGISTER_MARGIN})
    return consensus_addr


def __delegate_coin_success(agent, delegator, old_value, new_value):
    tx = pledge_agent_instance.delegateCoin(agent, {'from': delegator, 'value': new_value})
    expect_event(tx, "delegatedCoin", {
        "agent": agent,
        "delegator": delegator,
        "amount": new_value,
        "totalAmount": new_value + old_value
    })


def __check_coin_delegator(c_delegator, deposit, new_deposit, change_round, reward_idx):
    assert c_delegator['deposit'] == deposit
    assert c_delegator['newDeposit'] == new_deposit
    assert c_delegator['changeRound'] == change_round
    assert c_delegator['rewardIndex'] == reward_idx
