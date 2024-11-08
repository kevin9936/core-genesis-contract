import brownie
from .utils import *

MINT_VALUE = 100000
BURN_VALUE = 50000
TRANSFER_VALUE = 60000


def test_bitcoin_lst_token_init_once_only(lst_token):
    assert lst_token.alreadyInit() is True
    with brownie.reverts("the contract already init"):
        lst_token.init()


def test_total_supply(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[0], MINT_VALUE)
    lst_token.mint(accounts[1], MINT_VALUE)
    amount = lst_token.totalSupply()
    assert amount == MINT_VALUE * 2


def test_balanceOf(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[0], MINT_VALUE)
    lst_token.mint(accounts[1], MINT_VALUE)
    amount0 = lst_token.balanceOf(accounts[0])
    amount1 = lst_token.balanceOf(accounts[1])
    assert amount0 == amount1 == MINT_VALUE


def test_approve_success(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[2], MINT_VALUE)
    lst_token.approve(accounts[1], MINT_VALUE, {'from': accounts[2]})
    assert lst_token.allowance(accounts[2], accounts[1]) == MINT_VALUE
    transfer_amount = 1000
    lst_token.transfer(accounts[3], transfer_amount, {'from': accounts[2]})
    lst_token.transferFrom(accounts[2], accounts[4], transfer_amount * 2, {'from': accounts[1]})
    amount0 = lst_token.balanceOf(accounts[3])
    amount1 = lst_token.balanceOf(accounts[4])
    assert amount0 == transfer_amount
    assert amount1 == transfer_amount * 2


def test_increase_allowance_success(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.approve(accounts[1], MINT_VALUE)
    lst_token.increaseAllowance(accounts[1], MINT_VALUE)
    assert lst_token.allowance(accounts[0], accounts[1]) == MINT_VALUE * 2


def test_decrease_allowance_success(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.approve(accounts[1], MINT_VALUE * 2)
    lst_token.increaseAllowance(accounts[1], MINT_VALUE)
    lst_token.increaseAllowance(accounts[1], MINT_VALUE)
    assert lst_token.allowance(accounts[0], accounts[1]) == MINT_VALUE * 4
    lst_token.decreaseAllowance(accounts[1], MINT_VALUE)
    assert lst_token.allowance(accounts[0], accounts[1]) == MINT_VALUE * 3


def test_bitcoin_lst_token_mint(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[0], MINT_VALUE)
    amount = lst_token.balanceOf(accounts[0])
    assert amount == MINT_VALUE


def test_revert_on_mint_with_zero_address(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    with brownie.reverts("ERC20: mint to the zero address"):
        lst_token.mint(ZERO_ADDRESS, MINT_VALUE)
    amount = lst_token.balanceOf(ZERO_ADDRESS)
    assert amount == 0


def test_bitcoin_lst_token_NoBtcLSTStake_mint(lst_token):
    with brownie.reverts("only invoked by bitcoin lst stake"):
        lst_token.mint(accounts[0], MINT_VALUE)
    amount = lst_token.balanceOf(accounts[0])
    assert amount == 0


def test_bitcoin_lst_token_burn(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[0], MINT_VALUE)
    lst_token.burn(accounts[0], BURN_VALUE)
    amount = lst_token.balanceOf(accounts[0])
    assert amount == MINT_VALUE - BURN_VALUE


def test_revert_on_burn_with_zero_address(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    with brownie.reverts("ERC20: burn from the zero address"):
        lst_token.burn(ZERO_ADDRESS, MINT_VALUE)


def test_bitcoin_lst_token_NoBtcLSTStake_burns(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[0], MINT_VALUE)
    update_system_contract_address(lst_token, btc_lst_stake=accounts[1])
    with brownie.reverts("only invoked by bitcoin lst stake"):
        lst_token.burn(accounts[0], BURN_VALUE)


def test_bitcoin_lst_token_transfer(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[0], MINT_VALUE)
    lst_token.transfer(accounts[1], TRANSFER_VALUE)
    amount = lst_token.balanceOf(accounts[1])
    assert amount == TRANSFER_VALUE


def test_bitcoin_lst_token_gov_updateParam(lst_token):
    update_system_contract_address(lst_token, gov_hub=accounts[0])
    with brownie.reverts("UnsupportedGovParam: test"):
        lst_token.updateParam("test", "0x00")


def test_bitcoin_lst_token_nogov_updateParam(lst_token):
    with brownie.reverts("the msg sender must be governance contract"):
        lst_token.updateParam("test", "0x00")


def test_bitcoin_lst_token_allow_transferFrom(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[1], MINT_VALUE)
    lst_token.allowance(accounts[1], accounts[0])
    lst_token.approve(accounts[0], TRANSFER_VALUE, {"from": accounts[1]})
    lst_token.transferFrom(accounts[1], accounts[2], TRANSFER_VALUE, {'from': accounts[0]})
    with brownie.reverts("ERC20: transfer amount exceeds balance"):
        lst_token.transfer(accounts[2], TRANSFER_VALUE, {'from': accounts[0]})
    amount = lst_token.balanceOf(accounts[2])
    assert amount == TRANSFER_VALUE


def test_transferFrom_without_approval(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[1], MINT_VALUE)
    with brownie.reverts("ERC20: insufficient allowance"):
        lst_token.transferFrom(accounts[1], accounts[2], TRANSFER_VALUE, {'from': accounts[0]})
    amount = lst_token.balanceOf(accounts[2])
    assert amount == 0


def test_transfer_amount_exceeds_approved_limit(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[1], MINT_VALUE)
    lst_token.approve(accounts[0], TRANSFER_VALUE, {"from": accounts[1]})
    with brownie.reverts("ERC20: insufficient allowance"):
        lst_token.transferFrom(accounts[1], accounts[2], TRANSFER_VALUE * 2, {'from': accounts[0]})
    amount = lst_token.balanceOf(accounts[2])
    assert amount == 0


def test_insufficient_assets_during_transfer(lst_token):
    update_system_contract_address(lst_token, btc_lst_stake=accounts[0])
    lst_token.mint(accounts[1], MINT_VALUE)
    with brownie.reverts("ERC20: insufficient allowance"):
        lst_token.transferFrom(accounts[1], accounts[2], TRANSFER_VALUE)
