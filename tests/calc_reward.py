from tests.constant import *


class Discount:
    # month:discount
    tlp_rates = {
        12: 10000,
        8: 8000,
        5: 5000,
        1: 4000,
        0: 2000
    }
    # Core reward ratio: discount
    lp_rates = {
        15000: 12000,
        12000: 10000,
        5000: 6000,
        0: 1000
    }
    percentage = 5000
    state_map = {
        'percentage': percentage,
        'core_lp': 0,
        'btc_lst_gradeActive': 1,
        'btc_gradeActive': 1,
        'btc_rate': [0, 0, Utils.DENOMINATOR]
    }

    def get_init_discount(self):
        tlp_rates = []
        lp_rates = []
        for t in list(self.tlp_rates.keys())[::-1]:
            tlp_rates.append(t)
            tlp_rates.append(self.tlp_rates[t])
        for l in list(self.lp_rates.keys())[::-1]:
            lp_rates.append(l)
            lp_rates.append(self.lp_rates[l])
        return tlp_rates, lp_rates


def set_delegate(address, value, undelegate_amount=0, stake_duration=500):
    return {"address": address, "value": value, "undelegate_amount": undelegate_amount,
            'stake_duration': stake_duration}


def set_btc_lst_delegate(delegate_amount, redeem_amount=0):
    return {"delegate_amount": delegate_amount, "redeem_amount": redeem_amount}


def get_tlp_rate(day):
    rate = Utils.DENOMINATOR
    months = day // 30
    for i in Discount.tlp_rates:
        if months >= i:
            rate = Discount.tlp_rates[i]
            break

    return months, rate


def get_lp_rate(coin_reward, asset_reward):
    discount = Utils.DENOMINATOR
    level = coin_reward * Utils.DENOMINATOR // asset_reward
    for l in Discount.lp_rates:
        if level >= l:
            discount = Discount.lp_rates[l]
            break
    return level, discount


def init_btc_lst_count(btc_lst_stake, validator_count):
    if btc_lst_stake is None:
        return 0, 0, 0
    btc_lst_stake_amount = sum(amount['delegate_amount'] for amount in btc_lst_stake.values())
    single_agent_btc_lst = btc_lst_stake_amount // validator_count
    agent_btc_lst = single_agent_btc_lst * validator_count
    return btc_lst_stake_amount, single_agent_btc_lst, agent_btc_lst


def init_validators_score(agents, factor_map):
    for agent in agents:
        total_power = agent['total_power']
        total_coin = agent['total_coin']
        total_btc = agent['total_btc']
        agent['validator_score'] = total_coin * factor_map['coin'] + total_power * factor_map['power'] + (
            total_btc) * factor_map['btc']


def init_current_round_factor(factor_map, stake_count, reward_cap):
    factor1 = 0
    for s in factor_map:
        factor = 1
        if s == 'coin':
            factor1 = factor
        else:
            if stake_count['coin'] > 0 and stake_count[s] > 0:
                factor = (factor1 * stake_count['coin']) * reward_cap[s] // reward_cap['coin'] // stake_count[s]
        factor_map[s] = factor


def init_stake_score(agents, total_reward, btc_lst_stake):
    stake_count = {
        'coin': 0,
        'power': 0,
        'btc': 0
    }
    validator_count = 0
    for agent in agents:
        agent['totalReward'] = total_reward
        total_power = sum([item['value'] for item in agent.get('power', [])])
        agent['total_power'] = total_power
        total_coin = sum([item['value'] for item in agent.get('coin', [])])
        agent['total_coin'] = total_coin
        total_btc = sum([item['value'] for item in agent.get('btc', [])])
        agent['total_btc'] = total_btc
        stake_count['power'] += total_power
        stake_count['coin'] += total_coin
        stake_count['btc'] += total_btc
        validator_count += 1
    btc_lst_amount, single_agent_btc_lst, agent_btc_lst = init_btc_lst_count(btc_lst_stake, validator_count)
    for agent in agents:
        agent['total_btc'] += single_agent_btc_lst
        agent['total_btc_lst'] = single_agent_btc_lst
    stake_count['btc'] += agent_btc_lst
    return stake_count


def init_bonus_distribution_per_asset(reward_cap, bonus):
    btc_rate = {key: value for key, value in zip(list(reward_cap.keys()), Discount.state_map['btc_rate'])}
    total_bonus = bonus.get('total_bonus', 0)
    for i in btc_rate:
        bonus[i] = total_bonus * btc_rate[i] // Utils.DENOMINATOR


def calc_agent_asset_reward_distribution(agent, asset, asset_factor):
    key_asset_amount = 'total_' + asset  # e.g. total_coin, total_power, total_btc
    key_asset_reward = asset + '_reward'  # e.g. coin_reward, power_reward, btc_reward
    key_total_score = 'validator_score'
    key_total_reward = 'totalReward'
    if agent[key_asset_amount] == 0:
        return 0
    asset_amount = agent[key_asset_amount]
    total_score = agent[key_total_score]
    total_reward = agent[key_total_reward]
    agent[key_asset_reward] = total_reward * (asset_amount * asset_factor) // total_score
    if asset == 'btc':
        agent['sum_btc'] = asset_amount
        total_btc_reward = agent[key_asset_reward]
        lst_amount = agent['total_btc_lst']
        agent['btc_lst_reward'] = total_btc_reward * lst_amount // asset_amount
        agent[key_asset_reward] = total_btc_reward - agent['btc_lst_reward']
        agent[key_asset_amount] -= lst_amount


def calc_agent_asset_reward(agent, asset, unit_amount):
    key_asset_reward = asset + '_reward'  # e.g. coin_reward, power_reward, btc_reward
    key_asset_amount = 'total_' + asset  # e.g. total_coin, total_power, total_btc,total_btc_lst
    if agent[key_asset_amount] == 0:
        return 0
    key_asset_unit_reward = 'single_' + asset + '_reward'
    agent[key_asset_unit_reward] = agent[key_asset_reward] * unit_amount // agent[key_asset_amount]
    return agent[key_asset_unit_reward]


def calc_btc_lst_asset_reward(agents, btc_lst_stake, asset, unit_amount):
    key_asset_reward = asset + '_reward'  # e.g. coin_reward, power_reward, btc_reward
    total_btc_lst_reward = 0
    total_btc_lst = sum(amount['delegate_amount'] for amount in btc_lst_stake.values())
    if total_btc_lst == 0:
        return 0
    for agent in agents:
        total_btc_lst_reward += agent[key_asset_reward]
    asset_unit_reward = total_btc_lst_reward * unit_amount // total_btc_lst
    for agent in agents:
        agent['single_btc_lst_reward'] = asset_unit_reward
    return asset_unit_reward


def calc_coin_delegator_reward(agent, stake_list, delegator_asset_reward):
    for item in stake_list:
        actual_account_coin_reward = agent['single_coin_reward'] * (
                item['value'] - item['undelegate_amount']) // Utils.CORE_STAKE_DECIMAL
        if delegator_asset_reward['coin'].get(item['address']) is None:
            delegator_asset_reward['coin'][item['address']] = actual_account_coin_reward
        else:
            delegator_asset_reward['coin'][item['address']] += actual_account_coin_reward
        print(f"coin reward: {agent['address']} on {item['address']} => {actual_account_coin_reward}")


def calc_power_delegator_reward(agent, stake_list, delegator_asset_reward):
    for item in stake_list:
        actual_account_reward = agent['single_power_reward'] * item['value']
        if delegator_asset_reward['power'].get(item['address']) is None:
            delegator_asset_reward['power'][item['address']] = actual_account_reward
        else:
            delegator_asset_reward['power'][item['address']] += actual_account_reward
        print(f"power reward: {agent['address']} on {item['address']} => {actual_account_reward}")


def calc_btc_delegator_reward(agent, stake_list, delegator_asset_reward, bonus):
    for item in stake_list:
        actual_account_btc_reward = agent['single_btc_reward'] * (
                item['value'] - item['undelegate_amount']) // Utils.BTC_DECIMAL
        # staking duration discount logic
        if item['stake_duration'] < 360:
            months, duration_discount = get_tlp_rate(item['stake_duration'])
            if Discount.state_map['btc_gradeActive']:
                actual_account_btc_reward, unclaimed = calc_discounted_reward_amount(actual_account_btc_reward,
                                                                                     duration_discount)
                bonus['total_bonus'] += unclaimed
        if delegator_asset_reward['btc'].get(item['address']) is None:
            delegator_asset_reward['btc'][item['address']] = actual_account_btc_reward
        else:
            delegator_asset_reward['btc'][item['address']] += actual_account_btc_reward
        print(f"btc reward: {agent['address']} on {item['address']} => {actual_account_btc_reward}")


def calc_discounted_reward_amount(round_reward, duration_discount):
    actual_reward = round_reward * duration_discount // Utils.DENOMINATOR
    unclaimed_reward = round_reward - actual_reward
    return actual_reward, unclaimed_reward


def calc_btc_lst_delegator_reward(stake_list, asset_unit_reward_map, delegator_asset_reward, bonus):
    for delegator in stake_list:
        stake_amount = stake_list[delegator]['delegate_amount'] - stake_list[delegator]['redeem_amount']
        account_btc_lst_reward = asset_unit_reward_map['btc_lst'] * stake_amount // Utils.BTC_DECIMAL
        if Discount.state_map['btc_lst_gradeActive']:
            account_btc_lst_reward, unclaimed = calc_discounted_reward_amount(account_btc_lst_reward,
                                                                              Discount.state_map['percentage'])
            bonus['total_bonus'] += unclaimed
        if delegator_asset_reward['btc'].get(delegator) is None:
            delegator_asset_reward['btc'][delegator] = account_btc_lst_reward
        else:
            delegator_asset_reward['btc'][delegator] += account_btc_lst_reward
        print(f"btc lst reward: {delegator} => {account_btc_lst_reward}")


def calc_delegator_actual_reward(delegator, coin_reward_map, btc_reward_map, unclaimed_reward_map, unclaimed_info_map,
                                 rates_core_map, compensation_reward):
    coin_reward = coin_reward_map.get(delegator, 0)
    btc_reward = btc_reward_map.get(delegator)

    level, reward_discount = get_lp_rate(coin_reward, btc_reward)
    actual_account_btc_reward = -1
    if reward_discount < Utils.DENOMINATOR:
        actual_account_btc_reward = btc_reward * reward_discount // Utils.DENOMINATOR
        unclaimed_reward_map[delegator] += btc_reward - actual_account_btc_reward
    elif reward_discount >= Utils.DENOMINATOR:
        if compensation_reward is None:
            reward_discount = Utils.DENOMINATOR
            actual_account_btc_reward = btc_reward * reward_discount // Utils.DENOMINATOR
        else:
            actual_account_btc_reward = btc_reward * reward_discount // Utils.DENOMINATOR
            for r in compensation_reward:
                if r == 'btc':
                    bonus = actual_account_btc_reward - btc_reward
                    asset_bonus = compensation_reward[r]
                    if bonus > asset_bonus:
                        bonus = compensation_reward[r]
                        compensation_reward[r] = 0
                    else:
                        compensation_reward[r] -= bonus
                    actual_account_btc_reward = btc_reward + bonus
    btc_reward_map[delegator] = actual_account_btc_reward
    unclaimed_info_map['core'] += btc_reward - actual_account_btc_reward
    rates_core_map[delegator] = {'core_rate': [level, reward_discount]}


def calc_core_discounted_reward(discount_asset, delegator_asset_reward, bonus, compensation_reward):
    for r in discount_asset:
        delegator_reward = delegator_asset_reward.get(r, {})
        for delegator in delegator_reward:
            coin_reward = delegator_asset_reward['coin'].get(delegator, 0)
            asset_reward = delegator_reward[delegator]
            level, reward_discount = get_lp_rate(coin_reward, asset_reward)
            actual_account_btc_reward = -1
            if reward_discount < Utils.DENOMINATOR:
                actual_account_btc_reward = asset_reward * reward_discount // Utils.DENOMINATOR
                bonus['total_bonus'] += asset_reward - actual_account_btc_reward
            elif reward_discount >= Utils.DENOMINATOR:
                if compensation_reward is None:
                    reward_discount = Utils.DENOMINATOR
                    actual_account_btc_reward = asset_reward * reward_discount // Utils.DENOMINATOR
                else:
                    actual_account_btc_reward = asset_reward * reward_discount // Utils.DENOMINATOR
                    new_bonus = actual_account_btc_reward - asset_reward
                    asset_bonus = compensation_reward[r]
                    if new_bonus > asset_bonus:
                        new_bonus = compensation_reward[r]
                        compensation_reward[r] = 0
                    else:
                        compensation_reward[r] -= new_bonus
                    actual_account_btc_reward = asset_reward + new_bonus
            print(
                f'core_lp:{r}:{delegator}>>>asset_reward>>>>{asset_reward}actual_account_btc_reward:{actual_account_btc_reward}>>>>>>>>',
                level, reward_discount)

            delegator_reward[delegator] = actual_account_btc_reward


def calc_accrued_reward_per_asset(agents, btc_lst_stake, reward_unit_amount_map, asset_unit_reward_map):
    # calculate the reward for BTC LST separately
    asset = 'btc_lst'
    asset_unit_reward = calc_btc_lst_asset_reward(agents, btc_lst_stake, asset, reward_unit_amount_map['btc'])
    asset_unit_reward_map[asset] = asset_unit_reward
    # calculate Core Power BTC reward
    for asset in reward_unit_amount_map:
        if asset_unit_reward_map.get(asset) is None:
            asset_unit_reward_map[asset] = {}
        for agent in agents:
            unit_amount = reward_unit_amount_map[asset]
            asset_unit_reward = calc_agent_asset_reward(agent, asset, unit_amount)
            asset_unit_reward_map[asset][agent['address']] = asset_unit_reward


def update_delegator_total_reward(asset_reward_map, account_rewards_map):
    for asset in asset_reward_map:
        for delegator in asset_reward_map[asset]:
            if account_rewards_map.get(delegator) is None:
                account_rewards_map[delegator] = 0
            account_rewards_map[delegator] += asset_reward_map[asset][delegator]


def parse_delegation(agents, block_reward, btc_lst_stake=None, state_map=None, compensation_reward=None,
                     reward_cap=None):
    if btc_lst_stake is None:
        btc_lst_stake = {}
    if state_map is None:
        state_map = {}
    for i in state_map:
        Discount.state_map[i] = state_map[i]
    total_reward = block_reward
    if reward_cap is None:
        reward_cap = {
            'coin': HardCap.CORE_HARD_CAP,
            'power': HardCap.POWER_HARD_CAP,
            'btc': HardCap.BTC_HARD_CAP
        }
    factor_map = {
        'coin': 1,
        'power': 0,
        'btc': 0
    }
    reward_unit_amount_map = {
        'coin': Utils.CORE_STAKE_DECIMAL,
        'power': 1,
        'btc': Utils.BTC_DECIMAL
    }

    # init asset score for 3 assets: coin, power, btc
    stake_count = init_stake_score(agents, total_reward, btc_lst_stake)

    # init asset factor for 3 assets: coin, power, btc
    init_current_round_factor(factor_map, stake_count, reward_cap)

    # calculate the total score for each validator
    init_validators_score(agents, factor_map)

    # calc the reward distribution of each asset for each agent
    for asset in factor_map:
        for agent in agents:
            calc_agent_asset_reward_distribution(agent, asset, factor_map[asset])

    asset_unit_reward_map = {}
    # calculate the accrued reward for each asset (coin power btc btc_lst)
    calc_accrued_reward_per_asset(agents, btc_lst_stake, reward_unit_amount_map, asset_unit_reward_map)

    delegator_asset_reward = {
        'coin': {},
        'power': {},
        'btc': {},
        'btc_lst': {},
    }
    bonus = {
        'total_bonus': 0
    }
    # calculate rewards for each asset of the delegator
    calc_btc_lst_delegator_reward(btc_lst_stake, asset_unit_reward_map, delegator_asset_reward, bonus)
    for agent in agents:
        calc_coin_delegator_reward(agent, agent.get('coin', []), delegator_asset_reward)
        calc_power_delegator_reward(agent, agent.get('power', []), delegator_asset_reward)
        calc_btc_delegator_reward(agent, agent.get('btc', []), delegator_asset_reward, bonus)
    print('delegator_asset_reward0>>>>', delegator_asset_reward)
    # calculate Core reward ratio discount
    core_lp = Discount.state_map['core_lp']
    if core_lp:
        discount_assets = get_core_lp_asset(core_lp).rsplit(',')
        calc_core_discounted_reward(discount_assets, delegator_asset_reward, bonus, compensation_reward)

    # distribute the bonus proportionally to assets (coin, power, btc)
    init_bonus_distribution_per_asset(reward_cap, bonus)
    account_rewards = {}
    update_delegator_total_reward(delegator_asset_reward, account_rewards)
    print('delegator_asset_reward>>>>>>>>>>>>', delegator_asset_reward)
    print('unclaimed bonus>>>>>', bonus)
    print('current stake factor>>>>>>>>>>>>', factor_map)
    print('asset_unit_reward_map>>>>>>>>>', asset_unit_reward_map)
    print(f'account_rewards>>>>>>>>>>>>>>>>>>>: {account_rewards}')
    return delegator_asset_reward, bonus, account_rewards, asset_unit_reward_map


def get_core_lp_asset(n):
    mapping = {1: 'coin', 2: 'power', 4: 'btc'}
    result = ','.join(value for key, value in mapping.items() if n & key)
    return result


def set_coin_delegator(coin_delegator, validator, delegator, remain_coin, transfer_out_deposit, total_coin):
    coin_delegator[validator] = {delegator: {'remain_coin': remain_coin, 'transferOutDeposit': transfer_out_deposit,
                                             'total_pledged_amount': total_coin}}


def calculate_coin_rewards(score, sum_score, coin_reward):
    return coin_reward * score // sum_score


if __name__ == '__main__':
    reward, unclaimed_reward, account_rewards, round_reward = parse_delegation([{
        "address": 'v0',
        "active": True,
        "power": [set_delegate('a0', 20)],
        "coin": [set_delegate('a0', 10000)],
        "btc": [set_delegate('a0', 100)]
    }], 13545, {'v1': set_btc_lst_delegate(300)}, state_map={'core_lp': 4, 'btc_rate': [2500, 2500, 5000]})
