from collections import defaultdict


def set_delegate(address, value, last_claim=False):
    return {"address": address, "value": value, 'last_claim': last_claim}


def parse_delegation(agents, block_reward, power_factor=500):
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
    btc_count = 1
    coin_count = 0
    DENOMINATOR = 10000
    total_reward = block_reward
    delegator_coin_reward = {}
    delegator_power_reward = {}
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
    stake_score = {'power': 0,
                   'coin': 0}

    collateral_reward = {}
    for agent in agents:
        agent['totalReward'] = total_reward
        total_power = sum([item['value'] for item in agent['power']])
        agent['total_power'] = total_power
        btc_count += total_power
        total_coin = sum([item['value'] for item in agent['coin']])
        agent['total_coin'] = total_coin
        agent['validator_score'] = total_coin + total_power * power_factor
        coin_count += total_coin
        t += total_coin + total_power * power_factor
        stake_score['power'] += total_power * power_factor
        stake_score['coin'] += total_coin
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
                agent['coin_reward'] = total_reward * agent['total_coin'] // agent['validator_score'] * \
                                       collateral_state[s] // DENOMINATOR
                collateral_reward[s][agent['address']] = agent['coin_reward']
            elif s == 'power':
                if agent['total_power'] == 0:
                    continue
                agent['power_reward'] = total_reward * (agent['total_power'] * power_factor) // agent[
                    'validator_score'] * collateral_state[s] // DENOMINATOR
                agent['single_power_reward'] = agent['power_reward'] // agent['total_power']
                collateral_reward[s][agent['address']] = agent['power_reward']

    account_rewards = {}
    for agent in agents:
        agent_coin = agent['coin']
        agent_power = agent['power']
        for item in agent_power:
            account_reward = agent['power_reward'] * (item['value'] * power_factor) // (
                    agent['total_power'] * power_factor)
            actual_account_reward = agent['single_power_reward'] * item['value']
            if delegator_power_reward.get(item['address']) is None:
                delegator_power_reward[item['address']] = actual_account_reward
            else:
                delegator_power_reward[item['address']] += actual_account_reward
            print(f"power reward00: {agent['address']} on {item['address']} => {account_reward}")
            print(f"power reward11: {agent['address']} on {item['address']} => {actual_account_reward}")
        for item in agent_coin:
            reward = agent['coin_reward'] * item['value'] // agent['total_coin']
            if delegator_coin_reward.get(item['address']) is None:
                delegator_coin_reward[item['address']] = reward
            else:
                delegator_coin_reward[item['address']] += reward
            print(f"coin reward: {agent['address']} on {item['address']} => {reward}")
    for d in delegator_coin_reward:
        if account_rewards.get(d) is None:
            account_rewards[d] = 0
        account_rewards[d] += delegator_coin_reward.get(d)
    for s in delegator_power_reward:
        if account_rewards.get(s) is None:
            account_rewards[s] = 0
        account_rewards[s] += delegator_power_reward.get(s)
    print('account_rewards>>>>>>>>', account_rewards)
    print('collateral_state>>>>>>>>', collateral_state)
    print('collateral_reward>>>>>>>>There are different types of total rewards on validators', collateral_reward)
    print('delegator_coin_reward>>>>>>>>', delegator_coin_reward)
    print('delegator_power_reward>>>>>>>', delegator_power_reward)
    return delegator_coin_reward, delegator_power_reward, account_rewards, collateral_reward,collateral_state


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


if __name__ == '__main__':
    # delegate_info = [{
    #     "address": "n1",
    #     "coin": [set_delegate("x", 4), set_delegate("y", 2)],
    #     "power": [set_delegate("x", 2), set_delegate("y", 1)]
    # }, {
    #     "address": "n2",
    #     "coin": [{"address": "z", "value": 9}],
    #     "power": [{"address": "z", "value": 2}]
    # }]

    delegate_info = [{
        "address": "n0",
        "active": True,
        "coin": [set_delegate("x", 2e18)],
        "power": [set_delegate("x", 6e18)]
    }]

    _agent_score, _delegator_reward = parse_delegation(delegate_info, 324000000)
    print(_agent_score)
    print(_delegator_reward)
