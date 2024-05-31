// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;

import "./interface/IBitcoinStake.sol";
import "./interface/IParamSubscriber.sol";
import "./interface/ILightClient.sol";
import "./interface/IValidatorSet.sol";
import "./interface/ICandidateHub.sol";
import "./lib/Address.sol";
import "./lib/BytesLib.sol";
import "./lib/BytesToTypes.sol";
import "./lib/Memory.sol";
import "./lib/BitcoinHelper.sol";
import "./lib/SatoshiPlusHelper.sol";
import "./System.sol";

contract BitcoinLSTStake is IBitcoinStake, System, IParamSubscriber {
  using BitcoinHelper for *;
  using TypedMemView for *;
  using BytesLib for *;

  uint32 public constant WST_ACTIVE = 1;
  uint32 public constant WST_INACTIVE = 2;

  bytes1 constant OP_DUP = 0x76;
  bytes1 constant OP_HASH160 = 0xa9;
  bytes1 constant OP_DATA_20 = 0x14;
  bytes1 constant OP_DATA_32 = 0x20;
  bytes1 constant OP_EQUALVERIFY = 0x88;
  bytes1 constant OP_CHECKSIG = 0xac;
  bytes1 constant OP_EQUAL = 0x87;
  bytes1 constant OP_0 = 0;
  bytes1 constant OP_1 = 0x51;

  uint64 public constant WTYPE_UNKNOWN = 0;
  // 25 OP_DUP OP_HASH160 OP_DATA_20 <hash160> OP_EQUALVERIFY OP_CHECKSIG
  uint64 public constant WTYPE_P2PKH = 1;
  // 23 OP_HASH160 OP_DATA_20 <hash160> OP_EQUAL
  uint64 public constant WTYPE_P2SH = 2;
  // 22 witnessVer OP_0 OP_DATA_20 <hash160>
  uint64 public constant WTYPE_P2WPKH = 4;
  // 34 witnessVer OP_0 OP_DATA_32 <32-byte-hash>
  uint64 public constant WTYPE_P2WSH = 8;
  // 34 witnessVer OP_1 OP_DATA_32 <32-byte-hash>
  uint64 public constant WTYPE_P2TAPROOT = 16;

  uint256 public constant INIT_UTXO_FEE = 1e4;

  // The lst token contract's address.
  address public lstToken;

  // key: roundtag
  // value: reward per BTC accumulated
  mapping(uint256 => uint256) accuredRewardPerBTCMap;

  // wallet lists
  WalletInfo[] public wallets;

  // The btc fee which is cost when redeem btc.
  uint256 public utxoFee;

  // delegated real value.
  uint256 public totalAmount;

  uint256 public roundTag;

  // Initial round
  uint256 public initRound;

  Redeem[] public redeemRequests;

  uint256 public surplus;

  struct Redeem {
    address delegator;
    uint256 amount;
    bytes32 pkscript0;
    bytes32 pkscript1;
  }

  struct WalletInfo {
    bytes32 hash; //it may be 20-byte-hash or 32-bytes-hash.
    uint64 typeMask;
    uint32 status;
  }

  event paramChange(string key, bytes value);
  event delegated(bytes32 indexed txid, address indexed delegator, uint256 amount);
  event redeemed(address indexed delegator, uint256 amount, uint256 utxoFee, bytes pkscript);
  event undelegated(bytes32 indexed txid, address indexed delegator, uint256 amount, bytes pkscript);

  function init() external onlyNotInit {
    utxoFee = INIT_UTXO_FEE;
    initRound = ICandidateHub(CANDIDATE_HUB_ADDR).getRoundTag();
    roundTag = initRound;
    alreadyInit = true;
  }

  /*********************** Interface implementations ***************************/

  /// Bitcoin delegate, it is called by relayer via BitcoinAgent.verifyMintTx
  ///
  /// User workflow to delegate BTC to Core blockchain
  ///  1. A user creates a bitcoin transaction.
  ///  2. Relayer commit BTC tx to Core chain.
  ///  3. Contract mint btc lst token.
  ///
  /// @param txid the bitcoin tx hash
  /// @param payload bytes from OP_RETURN, it is used to parse/verify detail context
  ///                under satoshi+ protocol
  /// @param script it is used to verify the target txout
  /// @param amount amount of the target txout
  /// @param outputIndex The index of the target txout.
  /// @return delegator a Coredao address who delegate the Bitcoin
  /// @return fee pay for relayer's fee.
  function delegate(bytes32 txid, bytes29 payload, bytes memory script, uint256 amount, uint256 outputIndex) external override onlyBtcAgent returns (address delegator, uint256 fee) {
    (delegator, fee) = parsePayload(payload);
    // check in wallet Status
    (bytes32 _hash, uint64 _type) = extractPkScriptAddr(script);
    require(_type != WTYPE_UNKNOWN, "Unknown LST wallet");
    bool _match;
    for (uint256 i = 0; i != wallets.length; ++i) {
      if (wallets[i].hash == _hash && wallets[i].typeMask == _type && wallets[i].status == WST_ACTIVE) {
        _match = true;
        break;
      }
    }
    require(_match, "not target wallet.");
    // TODO lstToken.mint(delegator, amount);
    emit delegated(txid, delegator, amount);
    totalAmount += amount;
  }

  /// Bitcoin undelegate, it is called by relayer via BitcoinAgent.verifyBurnTx
  /// This method is used to clear redeem requests.
  ///
  /// @param txid the bitcoin tx hash
  /// @param outpoints outpoints from tx inputs.
  /// @param voutView tx outs as bytes29.
  function undelegate(bytes32 txid, BitcoinHelper.OutPoint[] memory outpoints, bytes29 voutView) external override onlyBtcAgent {
    // Finds total number of outputs
    uint _numberOfOutputs = uint256(voutView.indexCompactInt(0));
    uint64 _amount;
    bytes29 _pkScript;
    uint256 rIndex; // redeemIndex;
    uint256 redeemSize;
    bytes32 pk0;
    bytes32 pk1;
    uint8 pklen;

    for (uint index = 0; index < _numberOfOutputs; ++index) {
      (_amount, _pkScript) = voutView.parseOutputValueAndScript(index);
      pklen = uint8(_pkScript.length);
      if (pklen <= 32) {
        pk0 = _pkScript.index(0, pklen);
        pk1 = 0;
      } else {
        pk0 = _pkScript.index(0, 32);
        pk1 = _pkScript.index(32, pklen - 32);
      }
      redeemSize = redeemRequests.length;
      for (rIndex = 0; rIndex < redeemSize; ++rIndex) {
        Redeem storage rd = redeemRequests[rIndex];
        if (rd.amount == _amount && rd.pkscript0 == pk0 && rd.pkscript1 == pk1) {
          // emit event
          emit undelegated(txid, rd.delegator, _amount, _pkScript.clone());
          totalAmount -= _amount;
          if (rIndex + 1 < redeemSize) {
            redeemRequests[rIndex].pkscript0 = redeemRequests[redeemSize].pkscript0;
            redeemRequests[rIndex].pkscript1 = redeemRequests[redeemSize].pkscript1;
            redeemRequests[rIndex].amount = redeemRequests[redeemSize].amount;
            redeemRequests[rIndex].delegator = redeemRequests[redeemSize].delegator;
          }
          redeemRequests.pop();
          break;
        }
      }
    }
  }

  /// Receive round rewards from BitcoinAgent. It is triggered at the beginning of turn round
  /// @param validators List of validator operator addresses
  /// @param rewardList List of reward amount
  function distributeReward(address[] calldata validators, uint256[] calldata rewardList) external override payable onlyBtcAgent {
    uint256 reward;
    uint256 validatorSize = validators.length;
    for (uint256 i = 0; i < validatorSize; ++i) {
      reward += rewardList[i];
    }
    accuredRewardPerBTCMap[roundTag] += accuredRewardPerBTCMap[roundTag-1] + reward * SatoshiPlusHelper.BTC_DECIMAL / totalAmount;
  }

  /// Get stake amount.
  ///
  /// @param candidates List of candidate operator addresses
  /// @return amounts List of amounts of all special candidates in this round
  function getStakeAmounts(address[] calldata candidates) external override view returns (uint256[] memory amounts) {
    // Use a simple stake strategy: average on old validators.
    uint256 length = candidates.length;
    amounts = new uint256[](length);
    uint256 sustainValidatorCount;
    for (uint256 i = 0; i < length; i++) {
      if (IValidatorSet(VALIDATOR_CONTRACT_ADDR).isValidator(candidates[i])) {
        amounts[i] = 1;
        sustainValidatorCount++;
      }
    }
    if (sustainValidatorCount != 0) {
      uint256 avgAmount = totalAmount / sustainValidatorCount;
      for (uint256 i = 0; i < length; i++) {
        if (amounts[i] == 1) {
          amounts[i] = avgAmount;
        }
      }
    }
  }

  /// Start new round, this is called by the CandidateHub contract
  /// @param round The new round tag
  function setNewRound(address[] calldata /*validators*/, uint256 round) external override onlyBtcAgent {
    roundTag = round;
  }

  /// Do some preparement before new round.
  function prepare(uint256) external override {
    // nothing.
  }

  /// Claim reward for delegator
  /// @return rewardAmount Amount claimed
  function claimReward() external override returns (uint256 rewardAmount) {
    // TODO
    // (accuredRewardPerBTCMap[roundTag-1] - accuredRewardPerBTCMap[xxx]) * amount / BTC_DECIMAL;
  }

  /*********************** External implementations ***************************/
  /// Redeem bitcoin, create a redeem request and burn lst token.
  ///
  /// @param amount redeem amount
  /// @param pkscript pkscript used in txout
  function redeem(uint256 amount, bytes calldata pkscript) external {
    // TODO check there is enough balance.
    // require(amount + utxoFee <= lstToken.balanceOf(msg.sender), "Not enough btc token");
    if (amount == 0) {
      // TODO
      // require (lstToken.balanceOf(msg.sender) >= 2 * utxoFee, "The redeem amount is too small.");
      // amount = lstToken.balanceOf(msg.sender) - utxoFee;
    }
    // TODO
    // lstToken.burn(msg.sender, amount + utxoFee);

    require(pkscript.length <= 64, "invalid pkscript");
    uint8 pklen = uint8(pkscript.length);
    require(pklen <= 64, "valid pkscript should be less than 64.");
    bytes32 pk0;
    bytes32 pk1;
    if (pklen <= 32) {
      pk0 = pkscript.indexBytes32(0, pklen);
    } else {
      pk0 = pkscript.indexBytes32(0, 32);
      pk1 = pkscript.indexBytes32(32, pklen - 32);
    }
    // push btcaddress into redeem.
    redeemRequests.push(Redeem(msg.sender, amount, pk0, pk1));
    surplus += utxoFee;
    // TODO burn lst token.

    emit redeemed(msg.sender, amount, utxoFee, pkscript);
  }

  /*********************** Governance ********************************/
  /// Update parameters through governance vote
  /// @param key The name of the parameter
  /// @param value the new value set to the parameter
  function updateParam(string calldata key, bytes calldata value) external override onlyInit onlyGov {
    if (value.length != 32) {
      revert MismatchParamLength(key);
    }
    if (Memory.compareStrings(key, "add")) {
      addWallet(value);
    } else if (Memory.compareStrings(key, "remove")) {
      removeWallet(value);
    } else if (Memory.compareStrings(key, "setlstAddress")) {
      setLstAddress(value);
    } else {
      require(false, "unknown param");
    }
    emit paramChange(key, value);
  }

  /*********************** Inner Methods *****************************/
  function addWallet(bytes memory pkscript) internal {
    // decode address -> bytes32addr, networkId
    // verify bitcoin networkId
    // wallets.push(bytes32addr)
    // walletStatus[addr] = INACTIVE
  }

  function removeWallet(bytes memory pkscript) internal {
    // decode address -> bytes32addr, networkId
    // verify bitcoin networkId
    // walletStatus[addr] = ST_INACTIVE
  }

  function setLstAddress(bytes memory addr) internal {
    // lstToken = addr.indexUint(0,20);
  }

  function extractPkScriptAddr(bytes memory pkScript) internal pure returns (bytes32 whash, uint64 txType) {
    uint256 len = pkScript.length;
    if (len == 25) {
      // pay-to-pubkey-hash
      // OP_DUP OP_HASH160 OP_DATA_20 <hash160> OP_EQUALVERIFY OP_CHECKSIG
      if (pkScript[0] == OP_DUP && pkScript[1] == OP_HASH160 &&
          pkScript[2] == OP_DATA_20 && pkScript[23] == OP_EQUALVERIFY &&
          pkScript[24] == OP_CHECKSIG) {
        return (pkScript.indexBytes32(3, 20), WTYPE_P2PKH);
      }
    } else if (len == 23) {
      // pay-to-script-hash
      // 23 OP_HASH160 OP_DATA_20 <hash160> OP_EQUAL
      if (pkScript[0] == OP_HASH160 && pkScript[1] == OP_DATA_20 &&
          pkScript[22] == OP_EQUAL) {
        return (pkScript.indexBytes32(2, 20), WTYPE_P2SH);
      }
    } else if (len == 22) {
      // 22 OP_0 OP_DATA_20 <hash160>
      if (pkScript[0] == OP_0 && pkScript[1] == OP_DATA_20) {
        return (pkScript.indexBytes32(2, 20), WTYPE_P2WPKH);
      }
    } else if (len == 34) {
      // 34 OP_0 OP_DATA_32 <hash160>
      if (pkScript[0] == OP_0 && pkScript[1] == OP_DATA_32) {
        return (pkScript.indexBytes32(2, 32), WTYPE_P2WSH);
      }
      // 34 OP_1 OP_DATA_20 <hash160>
      if (pkScript[0] == OP_1 && pkScript[1] == OP_DATA_32) {
        return (pkScript.indexBytes32(2, 20), WTYPE_P2TAPROOT);
      }
    }
    return (0, WTYPE_UNKNOWN);
  }

  function parsePayload(bytes29 payload) internal pure returns (address delegator, uint256 fee) {
    require(payload.len() >= 28, "payload length is too small");
    delegator = payload.indexAddress(7);
    fee = payload.indexUint(27, 1);
  }
}