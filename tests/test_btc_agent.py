import pytest
import brownie
from brownie import accounts
from web3 import Web3, constants
from eth_abi import encode

from .constant import Utils
from .utils import expect_event, get_tracker, padding_left, encode_args_with_signature, update_system_contract_address
from .common import execute_proposal, turn_round, get_current_round, register_candidate


@pytest.fixture(scope="module", autouse=True)
def set_up():
    pass


@pytest.fixture()
def set_candidate():
    operators = []
    consensuses = []
    for operator in accounts[5:8]:
        operators.append(operator)
        consensuses.append(register_candidate(operator=operator))
    return operators, consensuses


def test_btc_agent_init_once_only(btc_agent):
    with brownie.reverts("the contract already init"):
        btc_agent.init()


def test_initialize_from_pledge_agent_success(btc_agent):
    candidates = accounts[:3]
    amounts = [100, 200, 300]
    update_system_contract_address(btc_agent, pledge_agent=accounts[0])
    btc_agent._initializeFromPledgeAgent(candidates, amounts)
    for index, candidate in enumerate(candidates):
        assert btc_agent.candidateMap(candidate)[1] == amounts[index]


def test_distribute_reward_success(btc_agent, btc_stake, btc_lst_stake):
    history_reward = 200
    turn_round()
    round_tag = get_current_round()
    candidates = accounts[:3]
    btc_amount = 1000
    lst_btc_amount = 4000
    rewards = [10000, 20000, 30000]
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    for c in candidates:
        btc_agent.setCandidateMap(c, lst_btc_amount, btc_amount)
        btc_stake.setCandidateMap(c, btc_amount, btc_amount, [round_tag])
        btc_stake.setAccuredRewardPerBTCMap(c, round_tag, history_reward)
    btc_lst_stake.setAccuredRewardPerBTCMap(round_tag - 1, history_reward)
    btc_lst_stake.setStakedAmount(lst_btc_amount)
    btc_agent.distributeReward(candidates, rewards, 0)
    btc_reward = sum(rewards)
    for index, c in enumerate(candidates):
        reward = rewards[index]
        lst_btc_reward = reward * lst_btc_amount / (lst_btc_amount + btc_amount)
        btc_reward -= lst_btc_reward
        assert btc_stake.accuredRewardPerBTCMap(c,
                                                round_tag) == history_reward + lst_btc_reward * Utils.BTC_DECIMAL // lst_btc_amount
    assert btc_lst_stake.getAccuredRewardPerBTCMap(
        round_tag) == history_reward + btc_reward * Utils.BTC_DECIMAL // btc_amount


def test_validators_and_reward_list_length_mismatch_failed(btc_agent):
    candidates = accounts[:3]
    rewards = [10000, 20000]
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    with brownie.reverts("the length of validators and rewardList should be equal"):
        btc_agent.distributeReward(candidates, rewards, 0)


def test_only_stake_hub_can_call_distribute_reward(btc_agent):
    candidates = accounts[:3]
    rewards = [10000, 20000, 30000]
    with brownie.reverts("the msg sender must be stake hub contract"):
        btc_agent.distributeReward(candidates, rewards, 0)


def test_get_stake_amounts_success(btc_agent, btc_stake, btc_lst_stake, set_candidate):
    lst_amount = 6000
    btc_amount = 3000
    operators, consensuses = set_candidate
    turn_round()
    btc_agent.getStakeAmounts(operators, 0)
    for o in operators:
        btc_stake.setCandidateMap(o, btc_amount, btc_amount, [])
    btc_lst_stake.setRealtimeAmount(lst_amount)
    amounts, total_amount = btc_agent.getStakeAmounts(operators, 0).return_value
    lst_validator_amount = lst_amount // 3
    amount = lst_validator_amount + btc_amount
    assert amounts == [amount, amount, amount]
    assert total_amount == amount * 3


def test_set_new_round_success(btc_agent, btc_stake, btc_lst_stake, set_candidate):
    lst_amount = 6000
    btc_amount = 3000
    operators, consensuses = set_candidate
    round_tag = 7
    assert btc_stake.roundTag() == btc_lst_stake.roundTag() == round_tag
    turn_round()
    round_tag += 1
    for o in operators:
        btc_stake.setCandidateMap(o, 0, btc_amount, [])
    btc_lst_stake.setRealtimeAmount(lst_amount)
    update_system_contract_address(btc_agent, stake_hub=accounts[0])
    btc_agent.setNewRound(operators, get_current_round())
    for op in operators:
        assert btc_stake.candidateMap(op) == [btc_amount, btc_amount]
    assert btc_lst_stake.stakedAmount() == lst_amount
    assert btc_stake.roundTag() == btc_lst_stake.roundTag() == round_tag


def test_only_stake_hub_can_call_set_new_round(btc_agent, btc_stake, btc_lst_stake, set_candidate):
    with brownie.reverts("the msg sender must be stake hub contract"):
        btc_agent.setNewRound(accounts[:3], get_current_round())


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
