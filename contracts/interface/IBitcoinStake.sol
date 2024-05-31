// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;
import "../lib/BitcoinHelper.sol";

interface IBitcoinStake {
  /// Bitcoin delegate, it is called by relayer via BitcoinAgent.verifyMintTx
  ///
  /// @param txid the bitcoin tx hash
  /// @param payload bytes from OP_RETURN, it is used to parse/verify detail context
  ///                under satoshi+ protocol
  /// @param script it is used to verify the target txout
  /// @param amount amount of the target txout
  /// @param outputIndex The index of the target txout.
  /// @return delegator a Coredao address who delegate the Bitcoin
  /// @return fee pay for relayer's fee.
  function delegate(bytes32 txid, bytes29 payload, bytes memory script, uint256 amount, uint256 outputIndex) external returns (address delegator, uint256 fee);

  /// Bitcoin undelegate, it is called by relayer via BitcoinAgent.verifyBurnTx
  ///
  /// @param txid the bitcoin tx hash
  /// @param outpoints outpoints from tx inputs.
  /// @param voutView tx outs as bytes29.
  function undelegate(bytes32 txid, BitcoinHelper.OutPoint[] memory outpoints, bytes29 voutView) external;

  /// Do some preparement before new round.
  /// @param round The new round tag
  function prepare(uint256 round) external;

  /// Get real stake amount
  /// @param candidates List of candidate operator addresses
  /// @return amounts List of amounts of all special candidates in this round
  function getStakeAmounts(address[] calldata candidates) external view returns (uint256[] memory amounts);

  /// Start new round, this is called by the CandidateHub contract
  /// @param validators List of elected validators in this round
  /// @param roundTag The new round tag
  function setNewRound(address[] calldata validators, uint256 roundTag) external;

  /// Receive round rewards from BitcoinAgent. It is triggered at the beginning of turn round
  /// @param validators List of validator operator addresses
  /// @param rewardList List of reward amount
  function distributeReward(address[] calldata validators, uint256[] calldata rewardList) external payable;

  /// Claim reward for delegator
  /// @return rewardAmount Amount claimed
  function claimReward() external returns (uint256 rewardAmount);
}