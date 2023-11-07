// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;

interface IERC20Errors {
    /**
     * @dev Indicates an error related to the current `balance` of a `sender`. Used in transfers.
     * @param sender Address whose tokens are being transferred.
     * @param balance Current balance for the interacting account.
     * @param needed Minimum amount required to perform a transfer.
     */
    error ERC20InsufficientBalance(address sender, uint256 balance, uint256 needed);

    /**
     * @dev Indicates a failure with the token `sender`. Used in transfers.
     * @param sender Address whose tokens are being transferred.
     */
    error ERC20InvalidSender(address sender);

    /**
     * @dev Indicates a failure with the token `receiver`. Used in transfers.
     * @param receiver Address to which tokens are being transferred.
     */
    error ERC20InvalidReceiver(address receiver);

    /**
     * @dev Indicates a failure with the `spender`’s `allowance`. Used in transfers.
     * @param spender Address that may be allowed to operate on tokens without being their owner.
     * @param allowance Amount of tokens a `spender` is allowed to operate with.
     * @param needed Minimum amount required to perform a transfer.
     */
    error ERC20InsufficientAllowance(address spender, uint256 allowance, uint256 needed);

    /**
     * @dev Indicates a failure with the `approver` of a token to be approved. Used in approvals.
     * @param approver Address initiating an approval operation.
     */
    error ERC20InvalidApprover(address approver);

    /**
     * @dev Indicates a failure with the `spender` to be approved. Used in approvals.
     * @param spender Address that may be allowed to operate on tokens without being their owner.
     */
    error ERC20InvalidSpender(address spender);
}

interface IEarnErrors {
    error EarnInvalidValidator(address validator);

    error EarnInvalidDelegateAmount(address account, uint256 amount);

    error EarnDelegateFailed(address account, address validator, uint256 amount);

    error EarnMintFailed(address account, uint256 amount, uint256 stCore);

    error EarnInvalidExchangeAmount(address account, uint256 amount);

    error EarnBurnFailed(address account, uint256 amount, uint256 stCore);

    error EarnERC20InsufficientTotalSupply(address account, uint256 stCore, uint256 totalSupply);

    error EarnInvalidRedeemRecordId(address account, uint256 id);

    error EarnRedeemLocked(address account, uint256 unlockTime, uint256 blockTime);

    error EarnInsufficientBalance(uint256 balance, uint256 amount);

    error EarnUnDelegateFailed(address validator, uint256 amount);

    error EarnDelegateInfoNotExist(address validator, uint256 amount);

    error EarnInsufficientUndelegateAmount(address validator, uint256 amount);
}