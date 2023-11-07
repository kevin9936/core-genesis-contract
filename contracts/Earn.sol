// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;

// import "./interface/IERC20.sol";
import "./interface/ICandidateHub.sol";
import {IEarnErrors} from "./interface/IErrors.sol";
import "./lib/IterableAddressDelegateMapping.sol";
import "./lib/DelegateActionQueue.sol";
import "./lib/Structs.sol";
import "./interface/IERC20.sol";

contract Earn {
    using IterableAddressDelegateMapping for IterableAddressDelegateMapping.Map;
    using DelegateActionQueue for DelegateActionQueue.Queue;

    // Exchange rate multiple
    uint16 constant private RATE_MULTIPLE = 10000; 

    // Address of system contract: CandidateHub
    address constant private CANDIDATE_HUB = 0x0000000000000000000000000000000000001005; 

    // Address of system contract: PledgeAgent
    address constant private PLEDGE_AGENT = payable(0x0000000000000000000000000000000000001007);

    // Address of stcore contract: STCore
    // address constant private STCORE = 0x0000000000000000000000000000000000002001; 
    address private STCORE; 


    // Exchange Rate per round 
    // mapping(uint256 => uint256) public roundExchangeRateMap;
    uint256 public exchangeRate = RATE_MULTIPLE;

    // Map of the amount pledged by the validator
    // mapping(address => uint256) public validatorDelegateAmountMap;
    IterableAddressDelegateMapping.Map private validatorDelegateMap;
    DelegateActionQueue.Queue private delegateQueue;
    IterableAddressDelegateMapping.Map private delegateFailedMap;
    // TODO: 在delegate、undelegate的时候有可能也会有奖励产生，考虑将这遗留的奖励质押到第一个validator上或者质押到对应的validator上
    // 如果质押到对应的validator上，可以合并到delegateFailedMap里

    // The time locked when user redeem Core
    uint16 public constant LOCK_DAY = 7;
    uint256 public constant INIT_DAY_INTERVAL = 86400;

    // Account redeem record
    uint256 public uniqueIndex = 1;
    mapping(address => RedeemRecord[]) redeemRecords;

    // Capital of delegate
    // TODO: 这个可以删掉
    DelegateCapital public capital;

    constructor(address _stCore) {
        STCORE = _stCore;
    }
    
    // 用户操作代理质押
    // 同时兑换到相应的STCore
    function delegateStaking(address validator) public payable {
        address account = msg.sender;
        uint256 amount = msg.value;

        // 判断质押的最小金额
        if (amount < 1 ether) {
            revert IEarnErrors.EarnInvalidDelegateAmount(account, amount);
        }

        // 判断validator是否是空地址
        if (validator == address(0)) {
            revert IEarnErrors.EarnInvalidValidator(validator);    
        }

        // 将用户打入合约的钱质押到系统合约，这里考虑判断validator的合法性
        bool success = _delegate(validator, amount);
        if (!success) {
            revert IEarnErrors.EarnDelegateFailed(account, validator,amount);
        }

        // 记录验证者上质押的金额
         // validatorDelegateAmountMap[validator] = validatorDelegateAmountMap[validator] + amount;
         DelegateInfo memory delegateInfo = DelegateInfo({
            amount: amount,
            earning: 0,
            unDelegateFailed: false,
            claimFailed: false
        });
        validatorDelegateMap.set(validator, delegateInfo,true);
        DelegateAction memory action = DelegateAction({
            validator: validator,
            amount: amount
        });
        delegateQueue.enqueue(action);

        // 购买产品打到合约里的钱，通过税率转换成STCore，增发给用户
        uint256 stCore = _exchangeSTCore(amount);
        bytes memory callData = abi.encodeWithSignature("mint(address,uint256)", account, stCore);
        (success, ) = STCORE.call(callData);
        if (!success) {
            revert IEarnErrors.EarnMintFailed(account, amount, stCore);
        }
    }

    // 切换轮次时调用的方法，包括计算每日利率等
    // 这个方法不能revert
    function trigger() public {
        uint _earnings = 0;

        // 领取奖励
        for (uint i = 0; i < validatorDelegateMap.size(); i++) {
            address key = validatorDelegateMap.getKeyAtIndex(i);
            DelegateInfo storage delegateInfo = validatorDelegateMap.get(key);

            uint256 balanceBeforeClaim = address(this).balance;
            bool success = _claim(key);
            uint256 balanceAfterClaim = address(this).balance;
            delegateInfo.earning = balanceAfterClaim - balanceBeforeClaim;
            _earnings += delegateInfo.earning;
            if (!success) {
                // TODO: 领取奖励失败，考虑如何处理
                delegateInfo.claimFailed = true;
            }
        }

        // 合并上一轮质押失败的，将收益合并到即将需要质押的map里
        uint256 deleteSize = 0;
        address[] memory deleteKeys = new address[](delegateFailedMap.size());
        for (uint i = 0; i < delegateFailedMap.size(); i++) {
            address key = delegateFailedMap.getKeyAtIndex(i);
            DelegateInfo memory delegateInfo = delegateFailedMap.get(key);
            validatorDelegateMap.set(key, delegateInfo, true);
            deleteKeys[deleteSize] = key;
            deleteSize++;
        }
        for (uint i = 0; i < deleteSize; i++) {
            delegateFailedMap.remove(deleteKeys[i]);
        }

        // 奖励复投
        for (uint i = 0; i < validatorDelegateMap.size(); i++) {
            address key = validatorDelegateMap.getKeyAtIndex(i);
            DelegateInfo storage delegateInfo = validatorDelegateMap.get(key);

            if (delegateInfo.earning > 0 && !delegateInfo.claimFailed) {
                if(delegateInfo.earning > 1 ether) {
                    // 奖励复投
                     bool success = _delegate(key, delegateInfo.earning);
                     if (success) {
                        delegateInfo.amount += delegateInfo.earning;
                        delegateInfo.earning = 0;
                     } else {
                        // 奖励复投失败，将收益放到质押失败的Map里，清空收益
                        DelegateInfo memory delegateFailed = DelegateInfo({
                            amount: 0,
                            earning: delegateInfo.earning,
                            unDelegateFailed: false,
                            claimFailed: false
                        });
                        delegateFailedMap.set(key, delegateFailed, true);
                        delegateInfo.earning = 0;
                     }
                } else {
                    // 收益小于1Core，将收益放到质押失败的Map里，清空收益
                     DelegateInfo memory delegateFailed = DelegateInfo({
                        amount: 0,
                        earning: delegateInfo.earning,
                        unDelegateFailed: false,
                        claimFailed: false
                    });
                    delegateFailedMap.set(key, delegateFailed, true);
                    delegateInfo.earning = 0;
                }
            }
        }

        // 计算兑换率
        uint256 totalSupply = IERC20(STCORE).totalSupply();
        if (totalSupply > 0) {
            uint256 _capital = 0;
            for (uint i = 0; i < validatorDelegateMap.size(); i++) {
                address key = validatorDelegateMap.getKeyAtIndex(i);
                DelegateInfo memory delegateInfo = validatorDelegateMap.get(key);
                _capital += delegateInfo.amount;
            }
            if (_capital > 0) {
                exchangeRate = _capital * RATE_MULTIPLE / totalSupply;
            }
        }

        // // 计算汇率
        // uint256 delegateCapital = capital.beforeLast;
        // if (delegateCapital > 0) {
        //      exchangeRate = (delegateCapital + _earnings) * RATE_MULTIPLE / delegateCapital;
        // }

        //  // 更新本金
        // uint256 _capital = 0;
        // for (uint i = 0; i < validatorDelegateMap.size(); i++) {
        //     address key = validatorDelegateMap.getKeyAtIndex(i);
        //     DelegateInfo memory delegateInfo = validatorDelegateMap.get(key);
        //     _capital += delegateInfo.amount;
        // }
        // capital.beforeLast = capital.last;
        // capital.last = _capital;

        // // 取消质押
        // for (uint i = 0; i < validatorDelegateMap.size(); i++) {
        //     address key = validatorDelegateMap.getKeyAtIndex(i);
        //     DelegateInfo storage delegateInfo = validatorDelegateMap.get(key);

        //     uint256 balanceBeforeUnDelegate = address(this).balance;
        //     bool success = _unDelegate(key, 0);
        //     if (success) {
        //         uint256 balanceAfterUnDelegate = address(this).balance;
        //         delegateInfo.earning = balanceAfterUnDelegate - balanceBeforeUnDelegate - delegateInfo.amount;
        //         delegateInfo.unDelegateFailed = false;
        //     } else {
        //         // TODO: 此处万一取消质押失败，如何处理
        //         delegateInfo.unDelegateFailed = true;
        //     }
        // }

        // // 合并上一轮质押失败的，到即将需要质押的map里
        // uint256 deleteSize = 0;
        // address[] memory deleteKeys = new address[](delegateFailedMap.size());
        // for (uint i = 0; i < delegateFailedMap.size(); i++) {
        //     address key = delegateFailedMap.getKeyAtIndex(i);
        //     DelegateInfo memory delegateInfo = delegateFailedMap.get(key);
        //     if (!validatorDelegateMap.get(key).unDelegateFailed) {
        //         // 前一步没有取消质押失败，才合并
        //         validatorDelegateMap.set(key, delegateInfo, true);
        //         deleteKeys[deleteSize] = key;
        //         deleteSize++;
        //     }
        // }
        // for (uint i = 0; i < deleteSize; i++) {
        //     delegateFailedMap.remove(deleteKeys[i]);
        // }

        // // 复投质押
        // deleteSize = 0;
        // deleteKeys = new address[](validatorDelegateMap.size());
        // for (uint i = 0; i < validatorDelegateMap.size(); i++) {
        //     address key = validatorDelegateMap.getKeyAtIndex(i);
        //     DelegateInfo memory delegateInfo = validatorDelegateMap.get(key);
        //     if (!delegateInfo.unDelegateFailed) {
        //         // 取消质押成功的，重新质押
        //         bool success = _delegate(key, delegateInfo.amount + delegateInfo.earning);
        //         if (!success) {
        //             // 质押失败，将记录移到另一个Map
        //              DelegateInfo memory delegateFailed = DelegateInfo({
        //                 amount: delegateInfo.amount + delegateInfo.earning,
        //                 earning: 0,
        //                 unDelegateFailed: false,
        //                 claimFailed: false
        //             });

        //             delegateFailedMap.set(key, delegateFailed, true);
        //             deleteKeys[deleteSize] = key;
        //             deleteSize++;
        //         }
        //     }
        // }
        // // 将质押失败的记录从原map中移除
        // for (uint i = 0; i < deleteSize; i++) {
        //     validatorDelegateMap.remove(deleteKeys[i]);
        // }

    }


    // 用户使用STCore兑换Core
    function redeem(uint256 stCore) public {
         address account = msg.sender;

        // 兑换金额不得小于 1 ether
        if (stCore < 1 ether) {
            revert IEarnErrors.EarnInvalidExchangeAmount(account, stCore);
        }
       
        // 计算可兑换的Core的数量，Core不能小于等于0
        uint256 core = _exchangeCore(stCore);
        if (core <= 0) {
            revert IEarnErrors.EarnInvalidExchangeAmount(account, stCore);
        }

        // 销毁对应的STCore
        uint256 totalSupply = IERC20(STCORE).totalSupply();
        if (stCore > totalSupply) {
            revert IEarnErrors.EarnERC20InsufficientTotalSupply(account, stCore, totalSupply);
        }
        bytes memory callData = abi.encodeWithSignature("burn(address,uint256)", account, stCore);
        (bool success, ) = STCORE.call(callData);
        if (!success) {
            revert IEarnErrors.EarnBurnFailed(account, core, stCore);
        }

        // 从已经质押的Validator上赎回对应的Core
        _unDelegateStratege(core);

        // 记录用户带锁定的赎回记录
        RedeemRecord memory redeemRecord = RedeemRecord({
            id : uniqueIndex++,
            redeemTime: block.timestamp,
            unlockTime: block.timestamp + INIT_DAY_INTERVAL * LOCK_DAY,
            amount: core,
            stCore: stCore
        });
        RedeemRecord[] storage records = redeemRecords[account];
        records.push(redeemRecord);
    }

    // 用户赎回解锁后的Core
    function withdraw(uint256 id) public {
        address account = msg.sender;
        
        // 赎回记录的ID不能小于1 
        if (id < 1) {
            revert IEarnErrors.EarnInvalidRedeemRecordId(account, id);
        }

        // 如果到锁定时间，则将到期的Core打给用户
        RedeemRecord[] storage records = redeemRecords[account];
        
        if (records.length <= 0) {
            revert IEarnErrors.EarnInvalidRedeemRecordId(account, id);
        }

        bool findRecord = false;
        uint index = 0;
        uint256 amount = 0;
        for (uint i = 0; i < records.length - 1; i++) {
            RedeemRecord memory record = records[i];
            if (record.id == id) {
                // 找到赎回记录
                if (!findRecord) {
                    findRecord = true;
                }
                if (record.unlockTime >= block.timestamp) {
                    // 没有到期，revert
                    revert IEarnErrors.EarnRedeemLocked(account, record.unlockTime, block.timestamp);
                }
                // 到期，成功赎回
                index = i;
                amount = record.amount;
            }
        }

        // 没有找到赎回记录
        if (!findRecord) {
            revert IEarnErrors.EarnInvalidRedeemRecordId(account, id);
        }

        // 删除Record、并且转账
        for (uint i = index; i < records.length - 1; i++) {
            records[i] = records[i + 1];
        }
        records.pop();
        if (address(this).balance < amount) {
            revert IEarnErrors.EarnInsufficientBalance(address(this).balance, amount);
        }
        payable(account).transfer(amount);
    }

    function getRedeemAmount() public view returns (uint256 unlockedAmount, uint256 lockedAmount) {
        RedeemRecord[] memory records = redeemRecords[msg.sender];        
        for (uint i = 0; i < records.length - 1; i++) {
            RedeemRecord memory record = records[i];
             if (record.unlockTime >= block.timestamp) {
                unlockedAmount += record.amount;
            } else {
                lockedAmount += record.amount;
            }
        }
    }

    // Core兑换STCore
    function _exchangeSTCore(uint256 core) internal view returns (uint256) {
        // uint256 prevExchangeRate = _getExchangeRate(_currentRound() - 1);
        // return core * prevExchangeRate / RATE_MULTIPLE;
        return core * exchangeRate / RATE_MULTIPLE;
    }

    // STCore兑换Core
    function _exchangeCore(uint256 stCore) internal view returns(uint256) {
        // uint256 prevExchangeRate = _getExchangeRate(_currentRound() - 1);
        // return stCore / prevExchangeRate / RATE_MULTIPLE;
        return stCore / exchangeRate / RATE_MULTIPLE;
    }

    // TODO: 取消质押，策略需要改，目前采用Queue的方式实现
    function _unDelegateStratege(uint256 amount) internal {
        uint256 unDelegateAmount = 0;

        while (true) {
            // 当前循环需要处理的金额
            uint256 processAmount = amount - unDelegateAmount;

            DelegateAction memory action = delegateQueue.dequeue();
            if (processAmount == action.amount) {
                // 取消质押的金额等于队列里弹出的操作金额
                bool success = _unDelegate(action.validator, action.amount);
                if (!success) {
                    revert IEarnErrors.EarnUnDelegateFailed(action.validator, action.amount);
                }
                _adjustDelegateMap(action.validator, action.amount);
                break;
            } else if (processAmount > action.amount){
                // 取消质押的金额大于队列里弹出的操作金额
                // 需要继续循环
                bool success = _unDelegate(action.validator, processAmount);
                if (!success) {
                    revert IEarnErrors.EarnUnDelegateFailed(action.validator, processAmount);
                }
                _adjustDelegateMap(action.validator, processAmount);
                unDelegateAmount += processAmount;
            } else if(processAmount < action.amount) {
                // 取消质押的金额小于队里里弹出的操作
                // 跳出循环
                bool success = _unDelegate(action.validator, processAmount);
                if (!success) {
                    revert IEarnErrors.EarnUnDelegateFailed(action.validator, processAmount);
                }
                _adjustDelegateMap(action.validator, processAmount);

                // 再次入队列
                DelegateAction memory reAction = DelegateAction({
                    validator: action.validator,
                    amount: action.amount - processAmount
                });
                delegateQueue.enqueue(reAction);
                break;
            }
        }
    }

    // 取消质押时有可能会产生收益
    function _unDelegate(address validator, uint256 amount) internal returns (bool) {
        uint256 balanceBefore = address(this).balance;
        bytes memory callData = abi.encodeWithSignature("undelegateCoin(address,uint256)", validator, amount);
        (bool success, ) = PLEDGE_AGENT.call(callData);
        if (success) {
            uint256 balanceAfter = address(this).balance;
            uint256 earning = balanceAfter - balanceBefore;
            if (earning > 0) {
                DelegateInfo memory delegateFailed = DelegateInfo({
                    amount: 0,
                    earning: earning,
                    unDelegateFailed: false,
                    claimFailed: false
                });
                delegateFailedMap.set(validator, delegateFailed, true);
            }
        }
        return success;
    }

    // 质押时有可能会产生收益
    function _delegate(address validator, uint256 amount) internal returns (bool) {
        uint256 balanceBefore = address(this).balance;
        bytes memory callData = abi.encodeWithSignature("delegateCoin(address)", validator);
        (bool success, ) = PLEDGE_AGENT.call{value: amount}(callData);
        if (success) {
            uint256 balanceAfter = address(this).balance;
            uint256 earning = balanceAfter - balanceBefore;
            if (earning > 0) {
                DelegateInfo memory delegateFailed = DelegateInfo({
                    amount: 0,
                    earning: earning,
                    unDelegateFailed: false,
                    claimFailed: false
                });
                delegateFailedMap.set(validator, delegateFailed, true);
            }
        }
        return success;
    }

    function _claim(address validator) internal returns (bool){
        address[] memory addresses = new address[](1);
        addresses[0] = validator;
        bytes memory callData = abi.encodeWithSignature("claimReward(address[])", addresses);
        (bool success, ) = PLEDGE_AGENT.call(callData);
        return success;
    }


    function _adjustDelegateMap(address validator, uint256 amount) internal {
        if (!validatorDelegateMap.exist(validator)) {
            revert IEarnErrors.EarnDelegateInfoNotExist(validator, amount);
        }

        DelegateInfo memory delegateInfo = validatorDelegateMap.get(validator);
        if (delegateInfo.amount == amount) {
            // 验证者记录的金额等于取消质押的金额
            validatorDelegateMap.remove(validator);
        } else if (delegateInfo.amount > amount) {
            // 验证者记录的金额大于取消质押的金额
            DelegateInfo memory unDelegateInfo = DelegateInfo({
                amount: amount,
                earning: 0,
                unDelegateFailed: false,
                claimFailed: false
            });
            validatorDelegateMap.set(validator, unDelegateInfo, false);
        } else {
            // 验证者记录的金额大于取消质押的金额，失败
            // TODO: 考虑是否要revert，或者直接执行remove
            revert IEarnErrors.EarnInsufficientUndelegateAmount(validator, amount);
        }
    }

    // 获取当前轮次
    // function _currentRound() internal view returns (uint256) {
    //     return ICandidateHub(CANDIDATE_HUB).getRoundTag();
    // }

    // 获取指定轮次的兑换率
    // function _getExchangeRate(uint256 round) internal view returns (uint256) {
    //     uint256 exchangeRate = roundExchangeRateMap[round];
    //     if (exchangeRate == 0) {
    //         exchangeRate = RATE_MULTIPLE;
    //     }
    //     return exchangeRate;
    // }  
}