from typing import Dict, List, Set
import time
import random
from copy import copy
from collections import defaultdict
import brownie
from brownie import accounts, history
from brownie.test import strategy
from hypothesis.strategies import integers

from .utils import get_tracker, encode_args_with_signature
from web3 import Web3

from .calc_reward import init_current_round_factor
from .common import turn_round, register_candidate, stake_hub_claim_reward
from .delegate import *
from .utils import *

btc_script = BtcScript()
TX_FEE = int(1e4)


def set_relayer_register(relay_hub):
    for account in accounts[:3]:
        relay_hub.setRelayerRegister(account.address, True)


class Status:
    REGISTER = 1 << 0
    UNREGISTER = 1 << 2
    VALIDATOR = 1 << 3
    REFUSED = 1 << 4


class Agent:
    def __init__(self, margin):
        self.delegators = {}
        self.status = Status.REGISTER
        self.total_power = 0
        self.total_coin = 0
        self.total_btc = 0
        self.total_btc_lst = 0
        self.agent_score = 0
        self.score = 0
        self.margin = margin
        self.reward = {
            'coin_reward': 0,
            'power_reward': 0,
            'btc_reward': 0,
            'btc_lst_reward': 0,
        }
        self.coin_reward = []
        self.power_reward = []
        self.btc_reward = []

    def clear_score(self):
        self.agent_score = 0


class Validator:
    def __init__(self, operator, consensus, fee, commission):
        self.operator_address = operator
        self.consensus_address = consensus
        self.fee_address = fee
        self.commission = commission
        self.income = 0


class Delegator:
    def __init__(self):
        self.btc_delegate = BtcStake()
        self.delegator = None

    def add_delegator(self, delegator):
        self.delegator = delegator

    def delegate_btc(self, agent, btc_amount, lock_script, lock_data=None, relay=None, stake_duration=None,
                     fee=1,
                     script_type='p2sh', lock_time=None):
        tx_id = delegate_btc_success(agent, self.delegator, btc_amount, lock_script, lock_data, relay, stake_duration,
                                     fee, script_type, lock_time)
        print('delegate_btc_success>>>>>>>>>', lock_data // Utils.ROUND_INTERVAL)

        return tx_id

    def transfer_btc(self, tx_id, target_candidate):
        tx = transfer_btc_success(tx_id, target_candidate, self.delegator)
        return tx

    def delegate_btc_lst(self, btc_amount, lock_script, percentage, relay=None):
        delegate_btc_lst_success(self.delegator, btc_amount, lock_script, percentage, relay)

    def redeem_btc_lst(self, amount, pkscript):
        redeem_btc_lst_success(self.delegator, amount, pkscript)

    def transfer_btc_lst(self, amount, to):
        transfer_btc_lst_success(self.delegator, amount, to)

    def delegate_power(self, candidate, value=1, stake_round=0):
        delegate_power_success(candidate, self.delegator, value, stake_round)

    def delegate_coin(self, candidate, amount):
        tx = delegate_coin_success(candidate, amount, self.delegator)
        return tx

    def undelegate_coin(self, candidate, amount):
        undelegate_coin_success(candidate, amount, self.delegator)

    def transfer_coin(self, source_agent, target_agent, amount):
        transfer_coin_success(source_agent, target_agent, amount, self.delegator)


N = 0


class StateMachine:
    core_amount = strategy('uint', min_value="10 ether", max_value="10000 ether")
    hash_value = strategy('uint', min_value=1, max_value=100)
    btc_amount = strategy('uint', min_value=1e8, max_value=1000e8)
    is_turn_round = strategy('bool')
    operate_count = strategy('uint', min_value=10, max_value=40)

    def __init__(self, candidate_hub, pledge_agent, validator_set, btc_light_client, slash_indicator,
                 stake_hub, btc_stake, btc_lst_stake, core_agent, relay_hub, gov_hub):
        self.candidate_hub = candidate_hub
        self.pledge_agent = pledge_agent
        self.validator_set = validator_set
        self.btc_light_client = btc_light_client
        self.slash_indicator = slash_indicator
        self.stake_hub = stake_hub
        self.btc_stake = btc_stake
        self.btc_lst_stake = btc_lst_stake
        self.relay_hub = relay_hub
        self.core_agent = core_agent
        self.gov_hub = gov_hub
        self.min_init_delegate_value = 100 * 100
        self.btc_value = 100
        self.btc_lst_value = 300
        self.power_value = 20
        self.candidate_margin = self.candidate_hub.requiredMargin()
        accounts[-2].transfer(self.validator_set.address, Web3.to_wei(100000, 'ether'))

    def setup(self):
        global N
        N += 1
        print(f"Scenario {N}")
        random.seed(time.time_ns())

        """
        delegator address => {agent1: count, agent2: count}
        """
        self.agents: Dict[str, Agent] = {}
        self.delegate = {}
        self.candidate_hub.setControlRoundTimeTag(True)
        self.btc_light_client.setCheckResult(True, 0)
        self.candidate_hub.setRoundTag(7)
        self.operators = []
        for operator in accounts[-4:-1]:
            register_candidate(consensus=operator, fee_address=operator, operator=operator,
                               margin=self.candidate_margin)
            self.operators.append(operator)
        old_turn_round()

    def initialize(self, core_amount, hash_value, btc_amount, is_turn_round, operate_count):
        print('Generate old data')
        tx_ids = self.__random_old_delegate(core_amount, hash_value, btc_amount, operate_count)
        self.stake_hub.initHybridScoreMock()
        self.btc_stake.moveData(tx_ids)
        if is_turn_round:
            turn_round(self.operators)
        print(f"{'@' * 48} initialize end {'@' * 48}")

    def invariant(self):
        print('invariant>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')

    def rule_delegate_coin(self, core_amount):
        candidates = self.candidate_hub.getCanDelegateCandidates()
        if not candidates:
            return
        agent = random.choice(candidates)
        delegator = random.choice(accounts[:-1])
        self.__add_delegate(delegator)
        value = core_amount
        self.delegate[delegator].delegate_coin(agent, value)
        print('rule_delegate_coin>>>>')

    def rule_delegate_btc(self, btc_amount):
        set_relayer_register(self.relay_hub)
        candidates = self.candidate_hub.getCanDelegateCandidates()
        if not candidates:
            return
        agent = random.choice(candidates)
        delegator = random.choice(accounts[:-1])
        self.__add_delegate(delegator)
        value = btc_amount
        lock_script, _, lock_time = random_btc_lock_script()
        self.delegate[delegator].delegate_btc(agent, value, lock_script, lock_time)

    def rule_delegate_btc_lst(self, btc_amount):
        set_relayer_register(self.relay_hub)
        delegator = random.choice(accounts[:-1])
        self.__add_delegate(delegator)
        value = btc_amount * 2
        lock_script = random_btc_lst_lock_script()
        self.btc_lst_stake.setWallet(lock_script)
        self.delegate[delegator].delegate_btc_lst(value, lock_script, 5000)

    def rule_delegate_power(self, hash_value):
        candidates = self.candidate_hub.getCanDelegateCandidates()
        if not candidates:
            return
        agent = random.choice(candidates)
        delegator = random.choice(accounts[:-1])
        self.__add_delegate(delegator)
        value = hash_value
        lock_script, _, lock_time = random_btc_lock_script()
        self.delegate[delegator].delegate_power(agent, value)

    def rule_claim_reward(self):
        delegator = list(self.delegate.keys())
        if len(delegator) < 2:
            return
        index = len(delegator) // 2
        delegate = random.choice(list(self.delegate.keys()))[:index]
        for i in delegate:
            stake_hub_claim_reward(i)

    def rule_turn_round(self, core_amount, hash_value, btc_amount, operate_count, is_turn_round):
        if is_turn_round:
            valid_candidates = self.candidate_hub.getCanDelegateCandidates()
            turn_round(valid_candidates)
        self.__random_new_delegate(core_amount, hash_value, btc_amount, operate_count)
        valid_candidates = self.candidate_hub.getCanDelegateCandidates()
        turn_round(valid_candidates)

    def teardown(self):
        print(f"{'@' * 51} teardown {'@' * 51}")
        valid_candidates = self.candidate_hub.getCanDelegateCandidates()
        turn_round(valid_candidates)

    def __add_delegate(self, address):
        if address not in self.delegate:
            delegate = Delegator()
            delegate.add_delegator(address)
            self.delegate[address] = delegate

    def __turn_round(self, valid_candidates: list):
        reward_cap = {
            'coin': HardCap.CORE_HARD_CAP,
            'power': HardCap.POWER_HARD_CAP,
            'btc': HardCap.BTC_HARD_CAP
        }
        # calc factor for  coin power btc
        for asset in reward_cap:
            for i in valid_candidates:
                self.stake_count[asset] += self.agents[i].get_agent_assets(asset)
                self.agents[i].clear_score()
        init_current_round_factor(self.factor_map, self.stake_count, reward_cap)
        # calc validators scores
        for i in valid_candidates:
            agent_coin = self.agents[i].total_coin
            agent_btc = self.agents[i].total_btc
            agent_power = self.agents[i].total_power
            agent_score = agent_coin + agent_btc * self.factor_map['btc'] + agent_power * self.factor_map['power']
            self.agents[i].agent_score += agent_score
            print('self.agents[i]', self.agents[i].agent_score)
        # calc assets reward
        for asset in self.factor_map:
            key_asset_reward = f'{asset}_reward'
            asset_factor = self.factor_map[asset]
            for candidate in valid_candidates:
                agent = self.agents[candidate]
                assert_amount = agent.get_agent_assets(asset)
                total_score = agent.get_agent_assets('agent_score')
                total_reward = self.block_reward
                asset_reward = total_reward * (assert_amount * asset_factor) // total_score
                agent.add_reward(key_asset_reward, asset_reward)
                if asset == 'btc':
                    total_btc_reward = agent.get_agent_assets_reward(key_asset_reward)
                    lst_amount = agent.total_btc_lst
                    btc_lst_reward = total_btc_reward * lst_amount // assert_amount
                    agent.add_reward('btc_lst', btc_lst_reward)
                    agent.add_reward(asset, total_btc_reward - btc_lst_reward)
                    agent.total_btc -= lst_amount
        # calc the accrued reward
        total_btc_lst_reward = 0
        total_btc_lst = 300
        reward_unit_amount_map = {
            'coin': Utils.CORE_STAKE_DECIMAL,
            'power': 1,
            'btc': Utils.BTC_DECIMAL
        }
        if total_btc_lst > 0:
            for candidate in valid_candidates:
                agent = self.agents[candidate]
                total_btc_lst_reward += agent.get_agent_assets_reward('btc_lst_reward')
            asset_unit_reward = total_btc_lst_reward * reward_unit_amount_map['btc'] // total_btc_lst
            self.btc_lst_reward.append(asset_unit_reward)
        for asset in reward_unit_amount_map:
            for candidate in valid_candidates:
                agent = self.agents[candidate]
                unit_amount = reward_unit_amount_map[asset]
                if agent.get_agent_assets(asset) == 0:
                    continue
                asset_unit_reward = agent.get_agent_assets_reward(
                    f'{asset}_reward') * unit_amount // agent.get_agent_assets(asset)
                agent.add_singe_reward(asset, asset_unit_reward)
        for c in valid_candidates:
            agent = self.agents[c]
            print('power_reward', agent.power_reward)
            print('btc_reward', agent.btc_reward)
            print('coin_reward', agent.coin_reward)

    def __random_old_delegate(self, core_amount, hash_value, btc_amount, operate_count):
        old_operate = ['btc', 'power', 'core']
        delegate_map = {
            'coin': {},
            'power': {},
            'btc': {}
        }
        agents_map = {}
        tx_ids = []
        time.sleep(3)
        for i in range(operate_count):
            delegator = random.choice(accounts[:-6])
            operator = random.choice(self.operators)
            if agents_map.get(operator) is None:
                agents_map[operator] = {
                    'coin': 0,
                    'power': 0,
                    'btc': 0
                }
            op = random.choice(old_operate)
            if op == 'btc':
                if delegate_map['btc'].get(delegator) is None:
                    delegate_map['btc'][delegator] = 0
                tx_id = old_delegate_btc_success(btc_amount, operator, delegator)
                delegate_map['btc'][delegator] += btc_amount
                agents_map[operator]['btc'] += btc_amount
                tx_ids.append(tx_id)
            elif op == 'power':
                if delegate_map['power'].get(delegator) is None:
                    delegate_map['power'][delegator] = 0
                delegate_power_success(operator, delegator, hash_value)
                delegate_map['power'][delegator] += hash_value
                agents_map[operator]['power'] += hash_value

            else:
                if delegate_map['coin'].get(delegator) is None:
                    delegate_map['coin'][delegator] = 0
                old_delegate_coin_success(operator, delegator, core_amount)
                delegate_map['coin'][delegator] += core_amount
                agents_map[operator]['coin'] += core_amount
        for i in self.operators:
            print('self.pledge_agent.agentsMap', self.pledge_agent.agentsMap(i))
        print('delegate_map>>>>>>>>>>>>>>>>>', delegate_map)
        print('agents_map>>>>>>>>>>>>>>>>>', agents_map)
        return tx_ids

    def __random_new_delegate(self, core_amount, hash_value, btc_amount, operate_count):
        new_operate = ['btc', 'power', 'core']
        delegate_map = {
            'coin': {},
            'power': {},
            'btc': {}
        }
        agents_map = {}
        lst_lock_script = random_btc_lst_lock_script()
        update_system_contract_address(self.btc_lst_stake, gov_hub=accounts[0])
        self.btc_lst_stake.updateParam('add', lst_lock_script)
        update_system_contract_address(self.btc_lst_stake, gov_hub=self.gov_hub)
        for i in range(operate_count):
            delegator = random.choice(accounts[:-6])
            operator = random.choice(self.operators)
            if agents_map.get(operator) is None:
                agents_map[operator] = {
                    'coin': 0,
                    'power': 0,
                    'btc': 0
                }
            op = random.choice(new_operate)
            if op == 'btc':
                if delegate_map['btc'].get(delegator) is None:
                    delegate_map['btc'][delegator] = 0
                btc = ['btc_lst', 'btc']
                if random.choice(btc) == 'btc':
                    lock_script, _, lock_time = random_btc_lock_script()
                    delegate_btc_success(operator, delegator, btc_amount, lock_script, lock_time, relay=delegator)
                else:
                    delegate_btc_lst_success(delegator, btc_amount, lst_lock_script, relay=delegator)
                delegate_map['btc'][delegator] += btc_amount
                agents_map[operator]['btc'] += btc_amount
            elif op == 'power':
                if delegate_map['power'].get(delegator) is None:
                    delegate_map['power'][delegator] = 0
                delegate_power_success(operator, delegator, hash_value)
                delegate_map['power'][delegator] += hash_value
                agents_map[operator]['power'] += hash_value

            else:
                if delegate_map['coin'].get(delegator) is None:
                    delegate_map['coin'][delegator] = 0
                delegate_coin_success(operator, core_amount, delegator)
                delegate_map['coin'][delegator] += core_amount
                agents_map[operator]['coin'] += core_amount


def test_stateful(state_machine, candidate_hub, pledge_agent, validator_set, btc_light_client, slash_indicator,
                  stake_hub, btc_stake, btc_lst_stake, core_agent, relay_hub, gov_hub):
    state_machine(
        StateMachine,
        candidate_hub,
        pledge_agent,
        validator_set,
        btc_light_client,
        slash_indicator,
        stake_hub,
        btc_stake,
        btc_lst_stake,
        core_agent,
        relay_hub,
        gov_hub,
        settings={"max_examples": 30, "stateful_step_count": 3}
    )
