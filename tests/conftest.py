import pytest
import web3.constants
from web3 import Web3
from brownie import *


@pytest.fixture(scope="session", autouse=True)
def is_development() -> bool:
    return network.show_active() == "development"


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@pytest.fixture(scope="session")
def library_set_up(accounts):
    accounts[0].deploy(BytesLib)
    accounts[0].deploy(BytesToTypes)
    accounts[0].deploy(Memory)
    accounts[0].deploy(RLPDecode)
    accounts[0].deploy(RLPEncode)
    accounts[0].deploy(SafeMath)
    # accounts[0].deploy(SatoshiPlusHelper)


@pytest.fixture(scope="module")
def candidate_hub(accounts):
    c = accounts[0].deploy(CandidateHubMock)
    c.init()
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def btc_light_client(accounts):
    c = accounts[0].deploy(BtcLightClientMock)
    c.init()
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def gov_hub(accounts):
    c = accounts[0].deploy(GovHubMock)
    c.init()
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def relay_hub(accounts):
    c = accounts[0].deploy(RelayerHubMock)
    c.init()
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def slash_indicator(accounts):
    c = accounts[0].deploy(SlashIndicatorMock)
    c.init()
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def system_reward(accounts):
    return accounts[0].deploy(SystemRewardMock)


@pytest.fixture(scope="module")
def validator_set(accounts):
    c = accounts[0].deploy(ValidatorSetMock)
    c.init()
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def pledge_agent(accounts, core_agent):
    accounts[0].deploy(BitcoinHelper)
    accounts[0].deploy(TypedMemView)
    accounts[0].deploy(SafeCast)
    c = accounts[0].deploy(PledgeAgentMock)
    c.init()
    c.updateContractCoreAgent(core_agent)
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def burn(accounts):
    c = accounts[0].deploy(Burn)
    c.init()
    return c


@pytest.fixture(scope="module")
def core_agent(accounts):
    c = accounts[0].deploy(CoreAgentMock)
    c.init()
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def foundation(accounts):
    c = accounts[0].deploy(Foundation)
    return c


@pytest.fixture(scope="module")
def stake_hub(accounts, validator_set, pledge_agent, hash_power_agent, btc_agent, btc_stake, btc_lst_stake,
              candidate_hub, core_agent):
    aaaa = candidate_hub.getCandidates()
    print('aaaa', aaaa)
    c = accounts[0].deploy(StakeHubMock)
    print('0x8093Bf791e937997B70B6cC05641cE1b94DAC4F7', core_agent)
    print('0x8093Bf791e937997B70B6cC05641cE1b94DAC4F7', btc_agent)
    core_agent.updateContractStakeHub(validator_set, core_agent, pledge_agent, hash_power_agent, btc_agent,
                                      candidate_hub, c)
    btc_agent.updateContractStakeHub(validator_set, core_agent, pledge_agent, hash_power_agent, btc_agent,
                                     candidate_hub, c)
    btc_stake.updateContractStakeHub(validator_set, core_agent, pledge_agent, hash_power_agent, btc_agent,
                                     candidate_hub, c)
    c.updateContractStakeHub(validator_set, core_agent, pledge_agent, hash_power_agent, btc_agent, candidate_hub, c)
    c.setLiabilityOperators(btc_stake, btc_lst_stake)
    tx = c.init()
    # print(c.getAssets())
    print('.event', tx.events)
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def btc_stake(accounts, candidate_hub):
    c = accounts[0].deploy(BitcoinStakeMock)
    c.updateContractHub(candidate_hub)
    c.init()
    if is_development:
        c.developmentInit()
    return c


@pytest.fixture(scope="module")
def btc_agent(accounts, btc_stake, btc_lst_stake):
    c = accounts[0].deploy(BitcoinAgentMock)
    c.init()
    if is_development:
        c.developmentInit()
    c.setBtcStake(btc_stake, btc_lst_stake)

    return c


@pytest.fixture(scope="module")
def btc_lst_stake(accounts, candidate_hub):
    c = accounts[0].deploy(BitcoinLSTStakeMock)
    c.updateContractHub(candidate_hub.address)
    c.init()
    return c


@pytest.fixture(scope="module")
def hash_power_agent(accounts):
    c = accounts[0].deploy(HashPowerAgent)
    c.init()
    return c


# test contract
@pytest.fixture(scope="module")
def test_lib_memory(accounts):
    c = accounts[0].deploy(TestLibMemory)
    return c


@pytest.fixture(scope="module", autouse=True)
def set_system_contract_address(
        candidate_hub,
        btc_light_client,
        gov_hub,
        relay_hub,
        slash_indicator,
        system_reward,
        validator_set,
        pledge_agent,
        burn,
        foundation,
        stake_hub,
        btc_stake,
        btc_agent,
        btc_lst_stake,
        core_agent,
        hash_power_agent
):
    args = [validator_set.address, slash_indicator.address, system_reward.address,
            btc_light_client.address, relay_hub.address, candidate_hub.address,
            gov_hub.address, pledge_agent.address, burn.address, foundation]

    candidate_hub.updateContractAddr(*args)
    btc_light_client.updateContractAddr(*args)
    gov_hub.updateContractAddr(*args)
    relay_hub.updateContractAddr(*args)
    slash_indicator.updateContractAddr(*args)
    system_reward.updateContractAddr(*args)
    validator_set.updateContractAddr(*args)
    pledge_agent.updateContractAddr(*args)
    burn.updateContractAddr(*args)
    foundation.updateContractAddr(*args)
    stake_hub.updateContractAddr(*args)
    btc_stake.updateContractAddr(*args)
    btc_agent.updateContractAddr(*args)
    btc_lst_stake.updateContractAddr(*args)
    hash_power_agent.updateContractAddr(*args)
    args1 = [stake_hub, btc_stake, btc_agent, btc_lst_stake, core_agent, hash_power_agent]
    candidate_hub.updateStakeContractAddr(*args1)
    btc_light_client.updateStakeContractAddr(*args1)
    gov_hub.updateStakeContractAddr(*args1)
    relay_hub.updateStakeContractAddr(*args1)
    slash_indicator.updateStakeContractAddr(*args1)
    system_reward.updateStakeContractAddr(*args1)
    validator_set.updateStakeContractAddr(*args1)
    pledge_agent.updateStakeContractAddr(*args1)
    burn.updateStakeContractAddr(*args1)
    foundation.updateStakeContractAddr(*args1)
    stake_hub.updateStakeContractAddr(*args1)
    btc_stake.updateStakeContractAddr(*args1)
    btc_agent.updateStakeContractAddr(*args1)
    btc_lst_stake.updateStakeContractAddr(*args1)
    # core_agent.updateContractAddr(*args)
    hash_power_agent.updateStakeContractAddr(*args1)

    system_reward.init()
    candidate_hub.setControlRoundTimeTag(True)
    # used for distribute reward
    # accounts[-2].transfer(validator_set.address, Web3.to_wei(100000, 'ether'))


@pytest.fixture(scope="module")
def min_init_delegate_value(pledge_agent):
    return pledge_agent.requiredCoinDeposit()
