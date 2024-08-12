from brownie import *
from . import constants
from .account_mgr import AccountMgr
addr_to_name = AccountMgr.addr_to_name

class RoundReward:
    def __init__(self, reward_amount, stake_amount):
        self.reward_amount = reward_amount # total reward amount in current round
        self.stake_amount = stake_amount  # total stake in current round
        # the reward for each portion is self.reward_amount / self.stake_amount

    def get_reward_per_stake(self):
        return self.reward_amount // self.stake_amount

class CoreRoundReward(RoundReward):
    def get_reward_per_stake(self):
        assert self.stake_amount > 0, f"{self.reward_amount}, {self.stake_amount}"
        return self.reward_amount * constants.CORE_AMOUNT_PER_REWARD // self.stake_amount

class BtcRoundReward(RoundReward):
    def get_reward_per_stake(self):
        assert self.stake_amount > 0, f"{self.reward_amount}, {self.stake_amount}"
        return self.reward_amount * constants.BTC_AMOUNT_PER_REWARD // self.stake_amount


class Asset:
    def __init__(self):
        self.name = None
        self.agent = None
        self.hardcap = None
        self.bonus_rate = None
        self.bonus_amount = None
        self.amount = None
        self.factor = None
        self.round_rewards = {}

        self.dual_stake_mask = 0

        self.init_state_off_chain()

    def __repr__(self):
        return f"Asset(name={self.name},agent={self.agent},hardcap={self.hardcap},bonus_rate={self.bonus_rate},bonus_amount={self.bonus_amount},amount={self.amount},factor={self.factor})"

    def __eq__(self, other):
        if isinstance(other, Asset):
            return self.name == other.name and \
                self.agent == other.agent and \
                self.hardcap == other.hardcap and \
                self.bonus_rate == other.bonus_rate and \
                self.bonus_amount == other.bonus_amount and \
                self.amount == other.amount and \
                self.factor == other.factor

        return False

    def calc_candidate_stake_amount_list(self, candidate, delegator_stake_state, round):
        pass

    def get_name(self):
        return self.name

    def get_bonus_rate(self):
        return self.bonus_rate

    def get_factor(self):
        return self.factor

    def init_state_off_chain(self):
        tuple_data = self.get_initial_state()
        tuple_data_on_chain = self.get_initial_state_on_chain()
        assert tuple_data == tuple_data_on_chain

        self.name = tuple_data[0]
        self.agent = tuple_data[1]
        self.hardcap = tuple_data[2]
        self.bonus_rate = tuple_data[3]
        self.bonus_amount = tuple_data[4]

        self.amount = tuple_data[5]
        self.factor = tuple_data[6]

    def get_initial_state_on_chain(self):
        state1 = StakeHubMock[0].assets(self.get_asset_idx())
        state2 = StakeHubMock[0].stateMap(self.get_agent_addr())
        return state1 + state2

    def set_total_amount(self, total_amount):
        self.total_amount = total_amount

    def get_initial_state(self):
        pass

    def get_asset_idx(self):
        pass

    def get_agent_addr(self):
        pass


    def update_factor(self, core_asset):
        if self == core_asset:
            return

        if core_asset.total_amount == 0 or self.total_amount == 0:
            self.factor = 1
            return

        assert core_asset.hardcap > 0
        self.factor = core_asset.factor * core_asset.total_amount * self.hardcap // core_asset.hardcap // self.total_amount

    def add_bonus_amount(self, delta_amount):
        self.bonus_amount += delta_amount

    def create_round_reward(self, reward_amount, stake_amount):
        return RoundReward(reward_amount, stake_amount)

    def add_round_reward(self, delegatee, round, reward_amount, stake_amount):
        print(f"Add {self.name} round({round}) reward: reward={reward_amount}, stake amount={stake_amount}")
        if reward_amount == 0:
            return

        assert stake_amount > 0, f"{round}, {reward_amount}"

        if self.round_rewards.get(delegatee) is None:
            self.round_rewards[delegatee] = {}

        assert self.round_rewards[delegatee].get(round) is None

        round_reward = self.create_round_reward(reward_amount, stake_amount)
        self.round_rewards[delegatee][round] = round_reward

    def get_reward_per_stake(self, delegatee, from_round, to_round):
        round_reward_list = self.round_rewards.get(delegatee)
        if round_reward_list is None:
            return 0

        reward_per_stake = 0
        for round in range(from_round, to_round+1):
            round_reward = round_reward_list.get(round)
            if round_reward is not None:
                reward_per_stake += round_reward.get_reward_per_stake()

        return reward_per_stake

    def distribute_reward(self, validators, delegator_stake_state,  round):
        print(f"{self.__class__.__name__} distribute_reward")

    def claim_reward(self, round, delegator, delegator_stake_state, candidates):
        return 0, 0

    def apply_dual_stake_reward(self, claimable_reward, unclaimable_reward, delegator_stake_state, core_reward):
        flag, grades = delegator_stake_state.get_core_stake_grade_data()

        if not self.enable_dual_stake(flag):
            return claimable_reward, unclaimable_reward

        if len(grades) == 0:
            return claimable_reward, unclaimable_reward

        if claimable_reward == 0:
            return claimable_reward, unclaimable_reward

        reward_rate = core_reward * constants.PERCENT_DECIMALS // claimable_reward
        percent = grades[0][1]
        for grade in reversed(grades):
            if reward_rate >= grade[0]:
                percent = grade[1]
                break

        if percent == constants.PERCENT_DECIMALS:
            return claimable_reward, unclaimable_reward

        new_claimable_reward = claimable_reward * percent // constants.PERCENT_DECIMALS
        if new_claimable_reward < claimable_reward:
            unclaimable_reward += claimable_reward - new_claimable_reward
            claimable_reward = new_claimable_reward
        else:
            bonus = min(new_claimable_reward - claimable_reward, self.bonus_amount)
            self.bonus_amount -= bonus
            claimable_reward += bonus

        return claimable_reward, unclaimable_reward


    def enable_dual_stake(self, flag):
        return self.dual_stake_mask == (flag & self.dual_stake_mask)

class CoreAsset(Asset):
    def __init__(self):
        super().__init__()

        self.dual_stake_mask = 1

    def get_initial_state(self):
        return ("CORE", self.get_agent_addr().address, 6000, 0, 0, 0, 1)

    def get_asset_idx(self):
        return 0

    def get_agent_addr(self):
        return CoreAgentMock[0]

    def create_round_reward(self, reward_amount, stake_amount):
        return CoreRoundReward(reward_amount, stake_amount)

    def distribute_reward(self, validators, delegator_stake_state, round):
        super().distribute_reward(validators, delegator_stake_state, round)

        for validator in validators.values():
            stake_state = validator.get_stake_state()
            reward_amount = stake_state.get_reward(self.name)
            if reward_amount == 0:
                continue

            # reward_amount is temp data,which will be cleared immediately after use
            stake_state.set_reward(self.name, 0)

            #[asset stake amount]
            amount_list = stake_state.get_round_stake_amount_list(self.name)
            assert len(amount_list) == 1
            stake_amount = amount_list[0]
            assert stake_amount == stake_state.get_stake_amount(self.name) # check data for test

            # add asset round reward for delegatee
            self.add_round_reward(validator.get_operator_addr(), round, reward_amount, stake_amount)

    def calc_candidate_stake_amount_list(self, candidate, delegator_stake_state, round):
        return [candidate.get_stake_state().get_realtime_amount(self.name)]

    # delegator_stake_state: saves the candidate addr list where the user has staked and the total asset amount
    # candidate_stake_state: saves the staking information of the user in the current candidate
    def claim_reward(self, round, delegator, delegator_stake_state, candidates):
        total_reward = 0
        remove_list = []
        staked_candidates = delegator_stake_state.get_core_stake_candidates(delegator)
        for addr in staked_candidates.keys():
            reward = self.collect_reward_in_candidate(round, delegator, candidates[addr])
            total_reward += reward
            print(f"{self.name} reward, candidate={addr}, {addr_to_name(addr)}, reward={reward}")

            candidate_stake_state = candidates[addr].get_stake_state()
            if candidate_stake_state.get_delegator_realtime_amount(self.name, delegator) == 0 and \
                candidate_stake_state.get_delegator_transferred_amount(self.name, delegator) == 0:
                remove_list.append(addr)
                candidate_stake_state.update_delegator_change_round(self.name, delegator, 0)

        for addr in remove_list:
            delegator_stake_state.rm_core_stake_candidate(delegator, addr)

        history_reward = delegator_stake_state.get_core_history_reward(delegator)
        if history_reward > 0:
            delegator_stake_state.update_core_history_reward(delegator, 0)

        print(f"{self.name}, history_reward={history_reward}")

        return total_reward + history_reward, 0

    def collect_reward_in_candidate(self, round, delegator, candidate):
        reward = 0
        delegatee = candidate.operator_addr
        candidate_stake_state = candidate.get_stake_state()
        change_round = candidate_stake_state.get_delegator_change_round(self.name, delegator)

        if change_round < round:
            realtime_amount = candidate_stake_state.get_delegator_realtime_amount(self.name, delegator)
            stake_amount = candidate_stake_state.get_delegator_stake_amount(self.name, delegator)
            transferred_amount = candidate_stake_state.get_delegator_transferred_amount(self.name, delegator)

            reward += stake_amount * self.get_reward_per_stake(delegatee, change_round, round-1)
            if transferred_amount > 0:
                reward += transferred_amount * self.get_reward_per_stake(delegatee, change_round, change_round)
                candidate_stake_state.update_delegator_transferred_amount(self.name, delegator, 0)

            assert realtime_amount >= stake_amount
            if realtime_amount > stake_amount:
                reward += (realtime_amount - stake_amount) * self.get_reward_per_stake(delegatee, change_round+1, round-1)
                candidate_stake_state.sync_delegator_stake_amount(self.name, delegator)

            candidate_stake_state.update_delegator_change_round(self.name, delegator, round)

        return reward // constants.CORE_AMOUNT_PER_REWARD


class PowerAsset(Asset):
    def __init__(self):
        super().__init__()
        self.dual_stake_mask = (1 << 1)

    def get_initial_state(self):
        return ("HASHPOWER", self.get_agent_addr().address, 2000, 0, 0, 0, 10**24)

    def get_asset_idx(self):
        return 1

    def get_agent_addr(self):
        return HashPowerAgentMock[0]

    def distribute_reward(self, validators, delegator_stake_state, round):
        super().distribute_reward(validators, delegator_stake_state, round)
        for validator in validators.values():
            stake_state = validator.get_stake_state()
            reward_amount = stake_state.get_reward(self.name)
            if reward_amount == 0:
                continue

            # reward_amount is temp data,which will be cleared immediately after use
            stake_state.set_reward(self.name, 0)

            miners = stake_state.get_round_miners(round-7)
            assert len(miners) > 0
            avg_reward = reward_amount // len(miners)

            for miner in miners:
                delegator_stake_state.add_power_history_reward(miner, avg_reward)


    def calc_candidate_stake_amount_list(self, candidate, delegator_stake_state, round):
        return [candidate.get_stake_state().get_round_powers(round-7)]

    def claim_reward(self, round, delegator, delegator_stake_state, candidates):
        history_reward = delegator_stake_state.get_power_history_reward(delegator)
        if history_reward > 0:
            delegator_stake_state.update_power_history_reward(delegator, 0)

        return history_reward, 0


class BtcAsset(Asset):
    def __init__(self):
        super().__init__()
        self.dual_stake_mask = (1 << 2)

        # btc lst data => single class
        self.btc_lst_round_rewards = {}

    def calc_candidate_stake_amount_list(self, candidate, delegator_stake_state, round):
        amount_list = [0,0]
        amount_list[0] = candidate.get_stake_state().get_realtime_amount(self.name)
        if candidate.is_validator():
            amount_list[1] = delegator_stake_state.get_btc_lst_avg_stake_amount()
        return amount_list

    def get_initial_state(self):
        return ("BTC", self.get_agent_addr().address, 4000, 10000, 0, 0, 2*(10**14))

    def get_asset_idx(self):
        return 2

    def get_agent_addr(self):
        return BitcoinAgentMock[0]

    def create_round_reward(self, reward_amount, stake_amount):
        return BtcRoundReward(reward_amount, stake_amount)

    def add_btc_lst_round_reward(self, round, reward_amount, stake_amount):
        print(f"Add BTCLST round({round}) reward:  reward={reward_amount}, stake amount={stake_amount}")

        if reward_amount == 0:
            return

        assert stake_amount > 0, f"{round}, {reward_amount}"

        assert self.btc_lst_round_rewards.get(round) is None

        round_reward = self.create_round_reward(reward_amount, stake_amount)
        self.btc_lst_round_rewards[round] = round_reward

    def get_btc_lst_reward_per_stake(self, from_round, to_round):
        reward_per_stake = 0
        for round in range(from_round, to_round+1):
            round_reward = self.btc_lst_round_rewards.get(round)
            if round_reward is not None:
                reward_per_stake += round_reward.get_reward_per_stake()

        return reward_per_stake

    def distribute_reward(self, validators, delegator_stake_state, round):
        super().distribute_reward(validators, delegator_stake_state, round)
        total_btc_lst_stake_reward = 0
        for validator in validators.values():
            stake_state = validator.get_stake_state()
            reward_amount = stake_state.get_reward(self.name)
            if reward_amount == 0:
                continue

            # [btc_stake_amount, btc_lst_stake_amount]
            amount_list = stake_state.get_round_stake_amount_list(self.name)
            assert len(amount_list) == 2
            btc_stake_amount = amount_list[0]
            btc_lst_stake_amount = amount_list[1]
            assert btc_stake_amount == stake_state.get_stake_amount(self.name) # check data for test

            # calc btc lst stake reward and stake amount
            btc_lst_stake_reward = reward_amount * btc_lst_stake_amount // (btc_lst_stake_amount + btc_stake_amount)
            total_btc_lst_stake_reward += btc_lst_stake_reward
            # avoid accumulation, as the btclst stake amount on the validator is an average value, and accumulation would overlook dust
            #total_btc_lst_stake_amount += btc_lst_stake_amount

            # add btc stake round reward for delegatee
            btc_stake_reward = reward_amount - btc_lst_stake_reward
            self.add_round_reward(validator.get_operator_addr(), round, btc_stake_reward, btc_stake_amount)

            # clear tmp data
            stake_state.set_reward(self.name, 0)

        # add btc lst stake round reward
        total_btc_lst_stake_amount = delegator_stake_state.get_btc_lst_total_stake_amount()
        self.add_btc_lst_round_reward(round, total_btc_lst_stake_reward, total_btc_lst_stake_amount)

    def claim_reward(self, round, delegator, delegator_stake_state, candidates):
        btc_stake_reward, unclaimable_btc_stake_reward = \
            self.claim_btc_stake_reward(round, delegator, delegator_stake_state)
        btclst_reward, unlaimable_btclst_reward = \
            self.claim_btc_lst_reward(round, delegator, delegator_stake_state)

        total_btc_reward = int(btc_stake_reward + btclst_reward)
        total_btc_unclaimable_reward =  int(unclaimable_btc_stake_reward + unlaimable_btclst_reward)

        print(f"BTC STAKE: {btc_stake_reward}, {unclaimable_btc_stake_reward}")
        print(f"BTC LST STAKE: {btclst_reward}, {unlaimable_btclst_reward}")
        return total_btc_reward, total_btc_unclaimable_reward

    def claim_btc_stake_reward(self, round, delegator, delegator_stake_state):
        txid_dict = delegator_stake_state.get_btc_stake_txids(delegator)
        if txid_dict is None:
            return 0, 0

        remove_txid_list = []

        total_claimable_reward = 0
        total_unclaimable_reward = 0
        for txid in txid_dict:
            tx = delegator_stake_state.get_btc_stake_tx(txid)

            claimable_reward, unclaimable_reward, expired = \
                self.collect_btc_stake_tx_reward(tx, delegator_stake_state, round)

            if expired:
                remove_txid_list.append(txid)

            total_claimable_reward += claimable_reward
            total_unclaimable_reward += unclaimable_reward

        for txid in remove_txid_list:
            delegator_stake_state.remove_btc_stake_txid(delegator, txid)

        history_claimable_reward = delegator_stake_state.get_btc_stake_history_reward(delegator)
        delegator_stake_state.update_btc_stake_history_reward(delegator, 0)

        history_unclaimable_reward = delegator_stake_state.get_btc_stake_history_unclaimable_reward(delegator)
        delegator_stake_state.update_btc_stake_history_unclaimable_reward(delegator, 0)

        return total_claimable_reward + history_claimable_reward, total_unclaimable_reward + history_unclaimable_reward

    def collect_btc_stake_tx_reward(self, tx, delegator_stake_state, round):
        from_round = tx.get_round() + 1
        unlock_round = tx.get_lock_time() // constants.ROUND_SECONDS
        to_round = min(round-1, unlock_round-1)

        claimable_reward = 0
        unclaimable_reward = 0

        # claim reward in round [from_round, to_round]
        if from_round <= to_round:
            reward = tx.get_amount() * self.get_reward_per_stake(tx.get_delegatee(), from_round, to_round) // constants.BTC_DECIMALS
            print(f"BTC reward={reward}")
            claimable_reward, unclaimable_reward = \
                delegator_stake_state.apply_btc_stake_grade_to_reward(reward, tx)

            print(f"    apply lock duration, claimable={claimable_reward}, unclaimable={unclaimable_reward}")
            tx.set_round(to_round)

        return  claimable_reward, unclaimable_reward, round >= unlock_round

    def claim_btc_lst_reward(self, round, delegator, delegator_stake_state):
        reward = self.collect_btc_lst_reward(round, delegator, delegator_stake_state)
        history_reward = delegator_stake_state.get_btc_lst_history_reward(delegator)
        if history_reward > 0:
            delegator_stake_state.update_btc_lst_history_reward(delegator, 0)
            print(f"{addr_to_name(delegator)} clear {self.name} history reward")

        print(f"claim_btc_lst_reward reward={reward}, history reward={history_reward}")

        claimable_reward, unclaimable_reward = \
            delegator_stake_state.apply_holding_time_to_reward(reward + history_reward)

        print(f"claim_btc_lst_reward claimable_reward={claimable_reward},unclaimable_reward={unclaimable_reward}")
        return claimable_reward, unclaimable_reward

    def collect_btc_lst_reward(self, round, delegator, delegator_stake_state):
        change_round = delegator_stake_state.get_btc_lst_change_round(delegator)
        if change_round == 0 or change_round == round:
            return 0

        stake_amount = delegator_stake_state.get_btc_lst_stake_amount(delegator)
        realtime_amount = delegator_stake_state.get_btc_lst_realtime_amount(delegator)
        from_round = change_round
        to_round = round - 1

        print(f"BTCLST stake amount={stake_amount}, reward_per_{from_round}_{to_round}={self.get_btc_lst_reward_per_stake(from_round, to_round)}");
        reward = stake_amount * self.get_btc_lst_reward_per_stake(from_round, to_round) // constants.BTC_AMOUNT_PER_REWARD
        assert realtime_amount >= stake_amount
        if realtime_amount > stake_amount:
            from_round += 1
            print(f"BTCLST changed amount={realtime_amount - stake_amount}, reward_per_{from_round}_{to_round}={self.get_btc_lst_reward_per_stake(from_round, to_round)}");
            reward += (realtime_amount - stake_amount) * self.get_btc_lst_reward_per_stake(from_round, to_round) // constants.BTC_AMOUNT_PER_REWARD
            delegator_stake_state.sync_btc_lst_stake_amount(delegator)

        delegator_stake_state.update_btc_lst_change_round(delegator, round)
        print(f"BTCLST round[{change_round, to_round}]: reward={reward}")
        return reward