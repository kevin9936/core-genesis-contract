from collections import defaultdict


def set_delegate(address, value, undelegate_amount=0, stake_duration=False):
    return {"address": address, "value": value, "undelegate_amount": undelegate_amount,
            'stake_duration': stake_duration}


def parse_delegation(agents, block_reward, power_factor=500, btc_factor=10, core_lp=False, compensation_reward=None):
    """
    :param block_reward:
    :param agents:
        example:
        [{
            "address": 0xdasdas213123,
            "active": True,
            "coin": [{
                "address": 0x21312321389123890,
                "value: 3,
                "last_claim": true
            }, {
                "address": 0x21312321389123890,
                "value: 4
            }],
            "power": [{
                "address": 0x128381290830912,
                "value: 99
            }]
        }]
    :return: agent score dict and delegate reward dict
        example:
        {"0xdasdas213123": 33, "0x12321312312": 23}
        {"0x21312321389123890": 13, "0x21312321389123890": 3}
    """
    DENOMINATOR = 10000
    CORE_STAKE_DECIMAL = 1000000
    BTC_DECIMAL = 100000000
    total_reward = block_reward
    delegator_coin_reward = {}
    delegator_power_reward = {}
    delegator_btc_reward = {}
    reward_cap = {
        'coin': 6000,
        'power': 2000,
        'btc': 4000
    }
    collateral_state = {
        'coin': 10000,
        'power': 10000,
        'btc': 10000
    }
    sum_hard_cap = 12000
    t = 0
    stake_score = {
        'coin': 0,
        'power': 0,
        'btc': 0}

    collateral_reward = {}

    for agent in agents:
        agent['totalReward'] = total_reward
        total_power = sum([item['value'] for item in agent['power']])
        agent['total_power'] = total_power
        total_coin = sum([item['value'] for item in agent['coin']])
        agent['total_coin'] = total_coin
        total_btc = sum([item['value'] for item in agent['btc']])
        agent['total_btc'] = total_btc
        agent['validator_score'] = total_coin + total_power * power_factor + total_btc * btc_factor
        t += total_coin + total_power * power_factor + total_btc * btc_factor
        stake_score['power'] += total_power * power_factor
        stake_score['coin'] += total_coin
        stake_score['btc'] += total_btc * btc_factor
    for i in stake_score:
        if stake_score.get(i) * sum_hard_cap > reward_cap[i] * t:
            discount = reward_cap[i] * t * DENOMINATOR // (sum_hard_cap * stake_score[i])
            collateral_state[i] = discount
    # calculate the final reward
    for s in stake_score:
        for agent in agents:
            if collateral_reward.get(s) is None:
                collateral_reward[s] = {}
            if s == 'coin':
                if agent['total_coin'] == 0:
                    continue
                agent['coin_reward'] = total_reward * agent['total_coin'] // agent['validator_score'] * \
                                       collateral_state[s] // DENOMINATOR
                if compensation_reward:
                    reward = compensation_reward[s].get(agent['address'], 0)
                    agent['coin_reward'] += reward
                agent['single_coin_reward'] = agent['coin_reward'] * CORE_STAKE_DECIMAL // agent['total_coin']

                collateral_reward[s][agent['address']] = agent['coin_reward']
            elif s == 'power':
                if agent['total_power'] == 0:
                    continue
                agent['power_reward'] = total_reward * (agent['total_power'] * power_factor) // agent[
                    'validator_score'] * collateral_state[s] // DENOMINATOR
                agent['single_power_reward'] = agent['power_reward'] // agent['total_power']
                collateral_reward[s][agent['address']] = agent['power_reward']
            elif s == 'btc':
                if agent['total_btc'] == 0:
                    continue
                agent['btc_reward'] = total_reward * (agent['total_btc'] * btc_factor) // agent[
                    'validator_score'] * collateral_state[s] // DENOMINATOR
                if compensation_reward:
                    reward = compensation_reward[s].get(agent['address'], 0)
                    agent['btc_reward'] += reward
                agent['single_btc_reward'] = agent['btc_reward'] * BTC_DECIMAL // agent['total_btc']
                collateral_reward[s][agent['address']] = agent['btc_reward']

    account_rewards = {}
    unclaimed_reward = {}
    unclaimed_info = {
        'core': 0,
        'days': 0
    }
    rates_core = {}
    for agent in agents:
        agent_coin = agent['coin']
        agent_power = agent['power']
        agent_btc = agent['btc']
        for item in agent_coin:
            account_coin_reward = agent['coin_reward'] * (item['value'] - item['undelegate_amount']) // agent[
                'total_coin']
            actual_account_coin_reward = agent['single_coin_reward'] * (
                    item['value'] - item['undelegate_amount']) // CORE_STAKE_DECIMAL
            # CORE_STAKE_DECIMAL
            if delegator_coin_reward.get(item['address']) is None:
                delegator_coin_reward[item['address']] = actual_account_coin_reward
            else:
                delegator_coin_reward[item['address']] += actual_account_coin_reward
            # print(f"coin reward00: {agent['address']} on {item['address']} => {account_coin_reward}")
            print(f"coin reward: {agent['address']} on {item['address']} => {actual_account_coin_reward}")
        for item in agent_power:
            account_reward = agent['power_reward'] * (item['value'] * power_factor) // (
                    agent['total_power'] * power_factor)
            actual_account_reward = agent['single_power_reward'] * item['value']
            if delegator_power_reward.get(item['address']) is None:
                delegator_power_reward[item['address']] = actual_account_reward
            else:
                delegator_power_reward[item['address']] += actual_account_reward
            # print(f"power reward00: {agent['address']} on {item['address']} => {account_reward}")
            print(f"power reward: {agent['address']} on {item['address']} => {actual_account_reward}")
        for item in agent_btc:
            account_btc_reward = agent['btc_reward'] * (item['value'] * btc_factor) // (
                    agent['total_btc'] * btc_factor)
            actual_account_btc_reward = agent['single_btc_reward'] * item['value'] // BTC_DECIMAL
            b_btc_reward = actual_account_btc_reward
            if item['stake_duration']:
                day = item['stake_duration']
                tlp_rates = {
                    12: 10000,
                    8: 8000,
                    5: 5000,
                    1: 4000,
                    0: 2000
                }
                p = 10000
                day = day // 30
                for i in tlp_rates:
                    if day >= i:
                        p = tlp_rates[i]
                        break
                actual_account_btc_reward = actual_account_btc_reward * p // DENOMINATOR
                if unclaimed_reward.get(item['address']) is None:
                    unclaimed_reward[item['address']] = 0
                unclaimed_reward[item['address']] += b_btc_reward - actual_account_btc_reward
                unclaimed_info['days'] += b_btc_reward - actual_account_btc_reward

                rates_key = str(item['address']) + str(agent['address'])
                rates_core[rates_key] = {
                    'days': [item['stake_duration'], day, p, b_btc_reward - actual_account_btc_reward]}
            # print(f"btc reward00: {agent['address']} on {item['address']} => {account_btc_reward}")
            if core_lp:
                if unclaimed_reward.get(item['address']) is None:
                    unclaimed_reward[item['address']] = 0

            if delegator_btc_reward.get(item['address']) is None:
                delegator_btc_reward[item['address']] = actual_account_btc_reward
            else:
                delegator_btc_reward[item['address']] += actual_account_btc_reward
            print(f"btc reward: {agent['address']} on {item['address']} => {actual_account_btc_reward}")

    for c in unclaimed_reward:
        coin_reward = delegator_coin_reward.get(c, 0)
        actual_account_btc_reward0 = delegator_btc_reward.get(c)
        lp_rates = {
            12000: 10000,
            5000: 6000,
            0: 1000
        }
        p = 10000
        bb = coin_reward * DENOMINATOR // actual_account_btc_reward0
        for i in lp_rates:
            if bb >= i:
                p = lp_rates[i]
                break
        actual_account_btc_reward = actual_account_btc_reward0 * p // DENOMINATOR
        delegator_btc_reward[c] = actual_account_btc_reward
        unclaimed_reward[c] += actual_account_btc_reward0 - actual_account_btc_reward
        unclaimed_info['core'] += actual_account_btc_reward0 - actual_account_btc_reward
        rates_core[c] = {'core_rate': [bb, p]}
    for d in delegator_coin_reward:
        if account_rewards.get(d) is None:
            account_rewards[d] = 0
        account_rewards[d] += delegator_coin_reward.get(d)
    for s in delegator_power_reward:
        if account_rewards.get(s) is None:
            account_rewards[s] = 0
        account_rewards[s] += delegator_power_reward.get(s)
    for s in delegator_btc_reward:
        if account_rewards.get(s) is None:
            account_rewards[s] = 0
        account_rewards[s] += delegator_btc_reward.get(s)
    print('collateral_state>>>>>>>>', collateral_state)
    print('collateral_reward>>>>>>>>There are different types of total rewards on validators', collateral_reward)
    print('delegator_coin_reward>>>>>>>>', delegator_coin_reward)
    print('delegator_power_reward>>>>>>>', delegator_power_reward)
    print('delegator_btc_reward>>>>>>>', delegator_btc_reward)
    print('account_rewards>>>>>>>>', account_rewards)
    print('unclaimed_reward>>>>>>>>', unclaimed_reward)
    print('unclaimed_info>>>>>>>>', unclaimed_info)
    print('rates_core>>>>>>>>>>>>', rates_core)
    rewards = [delegator_coin_reward, delegator_power_reward, delegator_btc_reward]
    unclaimed = [unclaimed_reward, unclaimed_info]
    return rewards, unclaimed, account_rewards, collateral_reward, collateral_state


def set_coin_delegator(coin_delegator, validator, delegator, remain_coin, transfer_out_deposit, total_coin):
    coin_delegator[validator] = {delegator: {'remain_coin': remain_coin, 'transferOutDeposit': transfer_out_deposit,
                                             'total_pledged_amount': total_coin}}


def calculate_rewards(agent_list: list, coin_delegator: dict, actual_debt_deposit, account, block_reward):
    result = []
    total_reward = block_reward
    for agent in agent_list:
        d = coin_delegator.get(agent, {}).get(account, 0)
        expect_reward = 0
        if d == 0:
            result.append(expect_reward)
        else:
            if d['transferOutDeposit'] > actual_debt_deposit:
                d['transferOutDeposit'] -= actual_debt_deposit
                actual_debt_deposit = 0
            else:
                actual_debt_deposit -= d['transferOutDeposit']
                d['transferOutDeposit'] = 0
            expect_reward = total_reward * (d['transferOutDeposit'] + d['remain_coin']) // d['total_pledged_amount']
            result.append(expect_reward)
    return result


def calculate_coin_rewards(score, sum_score, coin_reward):
    return coin_reward * score // sum_score


def calculate_power_rewards(score, sum_score, coin_reward):
    return coin_reward * score // sum_score


def calculate_reward(reward):
    x = reward * 1000000 // 80000

    btc_reward = 13545
    bb = x * 10000 / 13545

    return x


if __name__ == '__main__':
    print(calculate_reward(6000))
    # delegate_info = [{
    #     "address": "n0",
    #     "active": True,
    #     "coin": [set_delegate("x1", 250)],
    #     "power": [set_delegate("x1a", 1)],
    #     "btc": [set_delegate("x", 50)],
    # }]

    # parse_delegation(delegate_info, 13545)
    # delegate_info = [
    #     {
    #         "address": "n2",
    #         "active": True,
    #         "coin": [],
    #         "power": [set_delegate("a2", 200)],
    #         "btc": []
    #     }, {
    #         "address": "n1",
    #         "active": True,
    #         "coin": [set_delegate("a0", 80000)],
    #         "power": [],
    #         "btc": []
    #     },
    #     {
    #         "address": "n0",
    #         "active": True,
    #         "coin": [],
    #         "power": [],
    #         "btc": [set_delegate("a0", 2000)],
    #     }
    # ]
    # parse_delegation(delegate_info, 13545, core_lp=True)
