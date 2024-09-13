pragma solidity 0.8.4;

import "../PledgeAgent.sol";

contract PledgeAgentMock is PledgeAgent {
    event delegatedCoinOld(address indexed agent, address indexed delegator, uint256 amount, uint256 totalAmount);
    event transferredCoinOld(
        address indexed sourceCandidate,
        address indexed targetCandidate,
        address indexed delegator,
        uint256 amount,
        uint256 realAmount
    );
    event undelegatedCoinOld(address indexed candidate, address indexed delegator, uint256 amount);
    event roundReward(address indexed agent, uint256 coinReward, uint256 powerReward, uint256 btcReward);
    event delegatedBtcOld(bytes32 indexed txid, address indexed agent, address indexed delegator, bytes script, uint256 btcvalue);

    error InactiveAgent(address candidate);
    error InactiveCandidate(address candidate);
    error SameCandidate(address candidate);

    function developmentInit() external {
        requiredCoinDeposit = requiredCoinDeposit / 1e16;
        btcFactor = 2;
        minBtcLockRound = 3;
        minBtcValue = 100;
        roundTag = 1;
    }

    function setAgentRound(address agent, uint256 power, uint256 coin) external {
    }

    function setAgentReward(address agent, uint index,
        uint256 totalReward,
        uint256 claimedReward,
        uint256 totalScore,
        uint256 coin,
        uint256 power,
        uint256 round) external {}


    function setCoinDelegator(address agent) external {}

    function setBtcDelegator(address agent) external {}

    function getRewardLength(address agent) external view returns (uint) {
        return agentsMap[agent].rewardSet.length;
    }

    function getAgent2valueMap(uint256 round, address agent) external view returns (uint256 value) {
        BtcExpireInfo storage expireInfo = round2expireInfoMap[round];
        value = expireInfo.agent2valueMap[agent];
        return value;
    }

    function getAgentAddrList(uint256 round) external view returns (address[] memory) {
        BtcExpireInfo storage expireInfo = round2expireInfoMap[round];
        uint256 length = expireInfo.agentAddrList.length;
        address[] memory agentAddresses = new address[](length);
        for (uint256 i = 0; i < length; i++) {
            agentAddresses[i] = expireInfo.agentAddrList[i];
        }
        return agentAddresses;
    }


    function getDebtDepositMap(uint256 rRound, address delegator) external view returns (uint) {
        uint256 debt = debtDepositMap[rRound][delegator];
        return debt;
    }

    function setPowerFactor(uint newPowerFactor) external {
        powerFactor = newPowerFactor;
    }

    function setBtcFactor(uint newBtcFactor) external {
        btcFactor = newBtcFactor;
    }


    function setRoundTag(uint value) external {
        roundTag = value;
    }

    function undelegateCoinOld(address agent, address delegator, uint256 amount, bool isTransfer) internal returns (uint256, uint256) {
        Agent storage a = agentsMap[agent];
        CoinDelegator storage d = a.cDelegatorMap[delegator];
        uint256 newDeposit = d.newDeposit;
        if (amount == 0) {
            amount = newDeposit;
        }
        require(newDeposit != 0, "delegator does not exist");
        if (newDeposit != amount) {
            require(amount >= requiredCoinDeposit, "undelegate amount is too small");
            require(newDeposit >= requiredCoinDeposit + amount, "remaining amount is too small");
        }
        uint256 rewardAmount = collectCoinReward(a, d);
        a.totalDeposit -= amount;
        uint256 deposit = d.changeRound < roundTag ? newDeposit : d.deposit;
        newDeposit -= amount;
        uint256 deductedInDeposit;
        uint256 deductedOutDeposit;
        if (newDeposit < d.transferInDeposit) {
            deductedInDeposit = d.transferInDeposit - newDeposit;
            d.transferInDeposit = newDeposit;
            if (!isTransfer) {
                debtDepositMap[roundTag][msg.sender] += deductedInDeposit;
            }
            deductedOutDeposit = deposit;
        } else if (newDeposit < d.transferInDeposit + deposit) {
            deductedOutDeposit = d.transferInDeposit + deposit - newDeposit;
        }
        if (deductedOutDeposit != 0) {
            deposit -= deductedOutDeposit;
            if (a.rewardSet.length != 0) {
                Reward storage r = a.rewardSet[a.rewardSet.length - 1];
                if (r.round == roundTag) {
                    if (isTransfer) {
                        d.transferOutDeposit += deductedOutDeposit;
                    } else {
                        r.coin -= deductedOutDeposit;
                    }
                } else {
                    deductedOutDeposit = 0;
                }
            } else {
                deductedOutDeposit = 0;
            }
        }

        if (newDeposit == 0 && d.transferOutDeposit == 0) {
            delete a.cDelegatorMap[delegator];
        } else {
            d.deposit = deposit;
            d.newDeposit = newDeposit;
            d.changeRound = roundTag;
        }

        if (rewardAmount != 0) {
            distributeReward(payable(delegator));
        }

        return (amount, deductedInDeposit + deductedOutDeposit);
    }

    function delegateCoinOld(address agent, address delegator, uint256 deposit, uint256 transferInDeposit) internal returns (uint256) {
        require(deposit >= requiredCoinDeposit, "deposit is too small");
        Agent storage a = agentsMap[agent];
        CoinDelegator storage d = a.cDelegatorMap[delegator];
        uint256 rewardAmount;
        if (d.changeRound != 0) {
            rewardAmount = collectCoinReward(a, d);
        }
        a.totalDeposit += deposit;

        if (d.newDeposit == 0 && d.transferOutDeposit == 0) {
            d.newDeposit = deposit;
            d.changeRound = roundTag;
            d.rewardIndex = a.rewardSet.length;
        } else {
            if (d.changeRound < roundTag) {
                d.deposit = d.newDeposit;
                d.changeRound = roundTag;
            }
            d.newDeposit += deposit;
        }

        if (transferInDeposit != 0) {
            d.transferInDeposit += transferInDeposit;
        }

        if (rewardAmount != 0) {
            distributeReward(payable(delegator));
        }
        return d.newDeposit;
    }

    function delegateCoinOld(address agent) external payable {
        if (!ICandidateHub(CANDIDATE_HUB_ADDR).canDelegate(agent)) {
            revert InactiveAgent(agent);
        }
        uint256 newDeposit = delegateCoinOld(agent, msg.sender, msg.value, 0);
        emit delegatedCoinOld(agent, msg.sender, msg.value, newDeposit);
    }


    function undelegateCoinOld(address agent) external {
        undelegateCoinOld(agent, 0);
    }

    function undelegateCoinOld(address agent, uint256 amount) public {
        (uint256 deposit,) = undelegateCoinOld(agent, msg.sender, amount, false);
        Address.sendValue(payable(msg.sender), deposit);
        emit undelegatedCoinOld(agent, msg.sender, deposit);
    }

    function transferCoinOld(address sourceAgent, address targetAgent) external {
        transferCoin(sourceAgent, targetAgent, 0);
    }

    function transferCoinOld(address sourceAgent, address targetAgent, uint256 amount) public {
        if (!ICandidateHub(CANDIDATE_HUB_ADDR).canDelegate(targetAgent)) {
            revert InactiveAgent(targetAgent);
        }
        if (sourceAgent == targetAgent) {
            revert SameCandidate(sourceAgent);
        }
        (uint256 deposit, uint256 deductedDeposit) = undelegateCoinOld(sourceAgent, msg.sender, amount, true);
        uint256 newDeposit = delegateCoinOld(targetAgent, msg.sender, deposit, deductedDeposit);

        emit transferredCoinOld(sourceAgent, targetAgent, msg.sender, deposit, newDeposit);
    }


    function addExpire(BtcReceipt storage br) internal {
        BtcExpireInfo storage expireInfo = round2expireInfoMap[br.endRound];
        if (expireInfo.agentExistMap[br.agent] == 0) {
            expireInfo.agentAddrList.push(br.agent);
            expireInfo.agentExistMap[br.agent] = 1;
        }
        expireInfo.agent2valueMap[br.agent] += br.value;
    }


    function delegateBtcMock(bytes32 txId, uint256 btcValue, address agent, address delegator, bytes memory script, uint32 lockTime, uint256 fee) external {
        BtcReceipt storage br = btcReceiptMap[txId];
        require(br.value == 0, "btc tx confirmed");
        br.endRound = lockTime / ROUND_INTERVAL;
        br.value = btcValue;
        require(br.value >= (minBtcValue == 0 ? INIT_MIN_BTC_VALUE : minBtcValue), "staked value does not meet requirement");
        br.delegator = delegator;
        br.agent = agent;
        if (!ICandidateHub(CANDIDATE_HUB_ADDR).isCandidateByOperate(br.agent)) {
            revert InactiveAgent(br.agent);
        }
        emit delegatedBtcOld(txId, br.agent, br.delegator, script, btcValue);
        if (fee != 0) {
            br.fee = fee;
            br.feeReceiver = payable(msg.sender);
        }
        Agent storage a = agentsMap[br.agent];
        br.rewardIndex = a.rewardSet.length;
        addExpire(br);
        a.totalBtc += br.value;
    }

    function distributePowerRewardOld(address candidate, address[] calldata miners) external onlyCandidate {
        Agent storage a = agentsMap[candidate];
        uint256 l = a.rewardSet.length;
        if (l == 0) {
            return;
        }
        Reward storage r = a.rewardSet[l - 1];
        if (r.totalReward == 0 || r.round != roundTag) {
            return;
        }
        RoundState storage rs = stateMap[roundTag];
        uint256 reward = (rs.coin + rs.btc * rs.btcFactor) * POWER_BLOCK_FACTOR * rs.powerFactor / 10000 * r.totalReward / r.score;
        uint256 minerSize = miners.length;

        uint256 powerReward = reward * minerSize;
        uint256 undelegateCoinReward;
        uint256 btcScore = a.btc * rs.btcFactor;
        if (a.coin + btcScore > r.coin) {
            undelegateCoinReward = r.totalReward * (a.coin + btcScore - r.coin) * rs.power / r.score;
        }
        uint256 remainReward = r.remainReward;
        require(remainReward >= powerReward + undelegateCoinReward, "there is not enough reward");

        for (uint256 i = 0; i < minerSize; i++) {
            rewardMap[miners[i]] += reward;
        }

        if (r.coin == 0) {
            delete a.rewardSet[l - 1];
            undelegateCoinReward = remainReward - powerReward;
        } else if (powerReward != 0 || undelegateCoinReward != 0) {
            r.remainReward -= (powerReward + undelegateCoinReward);
        }

        if (undelegateCoinReward != 0) {
            ISystemReward(SYSTEM_REWARD_ADDR).receiveRewards{value: undelegateCoinReward}();
        }
    }

    function getHybridScoreOld(
        address[] calldata candidates,
        uint256[] calldata powers,
        uint256 round
    ) external onlyCandidate returns (uint256[] memory scores) {
        uint256 candidateSize = candidates.length;
        require(candidateSize == powers.length, "the length of candidates and powers should be equal");

        for (uint256 r = roundTag + 1; r <= round; ++r) {
            BtcExpireInfo storage expireInfo = round2expireInfoMap[r];
            uint256 j = expireInfo.agentAddrList.length;
            while (j > 0) {
                j--;
                address agent = expireInfo.agentAddrList[j];
                agentsMap[agent].totalBtc -= expireInfo.agent2valueMap[agent];
                expireInfo.agentAddrList.pop();
                delete expireInfo.agent2valueMap[agent];
                delete expireInfo.agentExistMap[agent];
            }
            delete round2expireInfoMap[r];
        }

        uint256 totalPower = 1;
        uint256 totalCoin = 1;
        uint256 totalBtc;
        for (uint256 i = 0; i < candidateSize; ++i) {
            Agent storage a = agentsMap[candidates[i]];
            a.power = powers[i] * POWER_BLOCK_FACTOR;
            a.btc = a.totalBtc;
            a.coin = a.totalDeposit;
            totalPower += a.power;
            totalCoin += a.coin;
            totalBtc += a.btc;
        }

        uint256 bf = (btcFactor == 0 ? INIT_BTC_FACTOR : btcFactor) * BTC_UNIT_CONVERSION;
        uint256 pf = powerFactor;

        scores = new uint256[](candidateSize);
        for (uint256 i = 0; i < candidateSize; ++i) {
            Agent storage a = agentsMap[candidates[i]];
            scores[i] = a.power * (totalCoin + totalBtc * bf) * pf / 10000 + (a.coin + a.btc * bf) * totalPower;
        }

        RoundState storage rs = stateMap[round];
        rs.power = totalPower;
        rs.coin = totalCoin;
        rs.powerFactor = pf;
        rs.btc = totalBtc;
        rs.btcFactor = bf;
    }

    function setNewRoundOld(address[] calldata validators, uint256 round) external onlyCandidate {
        RoundState storage rs = stateMap[round];
        uint256 validatorSize = validators.length;
        for (uint256 i = 0; i < validatorSize; ++i) {
            Agent storage a = agentsMap[validators[i]];
            uint256 btcScore = a.btc * rs.btcFactor;
            uint256 score = a.power * (rs.coin + rs.btc * rs.btcFactor) * rs.powerFactor / 10000 + (a.coin + btcScore) * rs.power;
            a.rewardSet.push(Reward(0, 0, score, a.coin + btcScore, round));
        }

        roundTag = round;
    }

    function addRoundRewardOld(address[] calldata agentList, uint256[] calldata rewardList)
    external
    payable
    onlyValidator
    {
        uint256 agentSize = agentList.length;
        require(agentSize == rewardList.length, "the length of agentList and rewardList should be equal");
        RoundState memory rs = stateMap[roundTag];
        for (uint256 i = 0; i < agentSize; ++i) {
            Agent storage a = agentsMap[agentList[i]];
            if (a.rewardSet.length == 0) {
                continue;
            }
            Reward storage r = a.rewardSet[a.rewardSet.length - 1];
            uint256 roundScore = r.score;
            if (roundScore == 0) {
                delete a.rewardSet[a.rewardSet.length - 1];
                continue;
            }
            if (rewardList[i] == 0) {
                continue;
            }
            r.totalReward = rewardList[i];
            r.remainReward = rewardList[i];
            uint256 coinReward = rewardList[i] * a.coin * rs.power / roundScore;
            uint256 powerReward = rewardList[i] * a.power * rs.coin / 10000 * rs.powerFactor / roundScore;
            uint256 btcReward = rewardList[i] * a.btc * rs.btcFactor * rs.power / roundScore;
            emit roundReward(agentList[i], coinReward, powerReward, btcReward);
        }
    }

    receive() external payable {
    }


}
