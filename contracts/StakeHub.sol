// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;

import "./interface/IParamSubscriber.sol";
import "./interface/IStakeHub.sol";
import "./interface/IAgent.sol";
import "./interface/ISystemReward.sol";
import "./System.sol";

/// This contract manages all stake implementation agent on Core blockchain
/// Currently, it supports three types of stake: Core, Hash, and BTC/BTCLST.
/// Each one have a hardcap of rewards.
/// As a transitional version, pledgeagent.sol retains the logic of core,
/// hash, and BTC.
contract StakeHub is IStakeHub, System, IParamSubscriber {

  uint256 public constant HASH_UNIT_CONVERSION = 1e18;
  uint256 public constant INIT_HASH_FACTOR = 1e6;
  uint256 public constant BTC_UNIT_CONVERSION = 1e10;
  uint256 public constant INIT_BTC_FACTOR = 2e4;
  uint256 public constant DENOMINATOR = 1e4;

  // Collateral list.
  Collateral[] collaterals;

  // key: candidate op address
  // value: collaterals' stake amount list.
  //        The order is core, hash, btc.
  mapping(address => uint256[]) public candidateAmountMap;

  // key: candidate op address
  // value: hybrid score for each candidate.
  mapping(address => uint256) public candidateScoreMap;

  // key: round tag
  // value: useful state information of round
  mapping(uint256 => mapping(address => CollateralState) ) public stateMap;

  struct Collateral {
    string  name;
    address agent;
    uint256 factor;
    uint256 hardcap;
  }

  struct CollateralState {
    uint256 amount;
    uint256 factor;
    uint256 discount;
  }

  // key: delegator
  // value: score = sum(delegated core * delegated time)
  // When user claim reward of btc, it will cost score.
  // If the score is not enough, reward should be discount.
  mapping(address => uint256) rewardScoreMap;

  /*********************** events **************************/
  event roundReward(string indexed name, address indexed validator, uint256 amounted);
  event paramChange(string key, bytes value);

  function init() external onlyNotInit {
    // add three collaterals into list
    collaterals.push(Collateral("CORE", CORE_AGENT_ADDR, 1, 6000));
    collaterals.push(Collateral("HASHPOWER", HASH_AGENT_ADDR, HASH_UNIT_CONVERSION * INIT_HASH_FACTOR, 2000));
    collaterals.push(Collateral("BTC", BTC_AGENT_ADDR, BTC_UNIT_CONVERSION * INIT_BTC_FACTOR, 4000));

    // TODO init hardfork round of candidateAmountMap
    alreadyInit = true;
  }

  /*********************** Interface implementations ***************************/
  /// Receive round rewards from ValidatorSet, which is triggered at the beginning of turn round
  /// @param validators List of validator operator addresses
  /// @param rewardList List of reward amount
  function addRoundReward(
    address[] calldata validators,
    uint256[] calldata rewardList,
    uint256 roundTag
  ) external payable override onlyValidator
  {
    uint256 validatorSize = validators.length;
    require(validatorSize == rewardList.length, "the length of validators and rewardList should be equal");
    uint256 collateralSize = collaterals.length;
    uint256[] memory rewards = new uint256[](validatorSize);
    uint256 burnReward;

    address validator;
    uint256 rewardValue;
    for (uint256 i = 0; i < collateralSize; ++i) {
      CollateralState memory cs = stateMap[roundTag][collaterals[i].agent];
      rewardValue = 0;
      for (uint256 j = 0; j < validatorSize; ++j) {
        validator = validators[j];
        uint256 r = rewardList[j] * candidateAmountMap[validator][i] * cs.factor / candidateScoreMap[validator];
        rewards[j] = r * cs.discount / DENOMINATOR;
        rewardValue += rewards[j];
        if (cs.discount != DENOMINATOR) {
          burnReward += (r - rewards[j]);
        }
        emit roundReward(collaterals[i].name, validator, rewards[j]);
      }
      IAgent(collaterals[i].agent).distributeReward{ value: rewardValue }(validators, rewards, roundTag);
    }
    // burn overflow reward of hardcap
    ISystemReward(SYSTEM_REWARD_ADDR).receiveRewards{ value: burnReward }();
  }

  /// Calculate hybrid score for all candidates
  /// @param candidates List of candidate operator addresses
  /// @param roundTag The new round tag
  /// @return scores List of hybrid scores of all validator candidates in this round
  function getHybridScore(
    address[] calldata candidates,
    uint256 roundTag
  ) external override onlyCandidate returns (uint256[] memory scores) {
    uint256 candidateSize = candidates.length;
    uint256 collateralSize = collaterals.length;

    uint256 hardcapSum;
    for (uint256 i = 0; i < collateralSize; ++i) {
      hardcapSum += collaterals[i].hardcap;
      IAgent(collaterals[i].agent).prepare(roundTag);
    }

    uint256[] memory collateralScores = new uint256[](collateralSize);
    scores = new uint256[](candidateSize);
    uint256 t;
    address candiate;
    for (uint256 i = 0; i < collateralSize; ++i) {
      (uint256[] memory amounts, uint256 totalAmount) =
        IAgent(collaterals[i].agent).getStakeAmounts(candidates, roundTag);
      t = collaterals[i].factor;
      collateralScores[i] = totalAmount * t;
      for (uint256 j = 0; j < candidateSize; ++j) {
        scores[j] += amounts[j] * t;
        candiate = candidates[j];
        if (candidateAmountMap[candiate].length <= i) {
          candidateAmountMap[candiate].push(amounts[j]);
        } else {
          candidateAmountMap[candiate][i] = amounts[j];
        }
      }
      stateMap[roundTag][collaterals[i].agent] = CollateralState(totalAmount, t, DENOMINATOR);
    }

    for (uint256 j = 0; j < candidateSize; ++j) {
      candidateScoreMap[candidates[j]] = scores[j];
    }

    t = collateralScores[0] + collateralScores[1] + collateralScores[2];
    for (uint256 i = 0; i < collateralSize; ++i) {
      // stake_proportion = collateralScores[i] / t
      // hardcap_proportion = hardcap / hardcapSum
      // if stake_proportion > hardcap_proportion;
      //    then discount = stake_proportion / hardcap_proportion
      // if condition transform ==>  collateralScores[i] * hardcapSum > hardcap * t
      if (collateralScores[i] * hardcapSum > collaterals[i].hardcap * t) {
        stateMap[roundTag][collaterals[i].agent].discount = collaterals[i].hardcap * t * DENOMINATOR / (hardcapSum * collateralScores[i]);
      }
    }
  }

  /// Start new round, this is called by the CandidateHub contract
  /// @param validators List of elected validators in this round
  /// @param roundTag The new round tag
  function setNewRound(address[] calldata validators, uint256 roundTag) external override onlyCandidate {
    uint256 collateralSize = collaterals.length;
    for (uint256 i = 0; i < collateralSize; ++i) {
      IAgent(collaterals[i].agent).setNewRound(validators, roundTag);
    }
  }

  /// Claim reward for miner
  /// The param represents list of validators to claim rewards on.
  /// this contract implement is ignore.
  /// @return rewardAmount Amount claimed
  function claimReward() external returns (uint256 rewardAmount) {
    // TODO will implement at next version.
    // delegator  core, btc, agents
  }

  /*********************** Governance ********************************/
  /// Update parameters through governance vote
  /// @param key The name of the parameter
  /// @param value the new value set to the parameter
  function updateParam(string calldata key, bytes calldata value) external override onlyInit onlyGov {
    if (value.length != 32) {
      revert MismatchParamLength(key);
    }
    // TODO
    emit paramChange(key, value);
  }

  /*********************** Public view ********************************/

  /// Get a collateral's round state information
  /// @param roundTag The round tag
  /// @param agent The operator address of validator
  /// @return CollateralState The collateral information
  function getCollateralRoundState(uint256 roundTag, address agent) external view returns (CollateralState memory) {
    return stateMap[roundTag][agent];
  }
}