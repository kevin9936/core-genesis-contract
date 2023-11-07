// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;

import "./Structs.sol";

library IterableAddressDelegateMapping {
    // Iterable mapping from address to uint;
    struct Map {
        address[] keys;
        mapping(address => DelegateInfo) values;
        mapping(address => uint) indexOf;
        mapping(address => bool) inserted;
    }

    function get(Map storage map, address key) public view returns (DelegateInfo storage) {
        return map.values[key];
    }

    function getKeyAtIndex(Map storage map, uint index) public view returns (address) {
        return map.keys[index];
    }

    function size(Map storage map) public view returns (uint) {
        return map.keys.length;
    }

    function set(Map storage map, address key, DelegateInfo memory val, bool increase) public {
        if (map.inserted[key]) {
            // map.values[key] = val;
            if (increase) {
                map.values[key].amount += val.amount;
                map.values[key].earning += val.earning;
            } else {
                map.values[key].amount -= val.amount;
                map.values[key].earning -= val.earning;
            }
            map.values[key].unDelegateFailed = val.unDelegateFailed;
        } else {
            map.inserted[key] = true;
            map.values[key] = val;
            map.indexOf[key] = map.keys.length;
            map.keys.push(key);
        }
    }

    function remove(Map storage map, address key) public {
        if (!map.inserted[key]) {
            return;
        }

        delete map.inserted[key];
        delete map.values[key];

        uint index = map.indexOf[key];
        address lastKey = map.keys[map.keys.length - 1];

        map.indexOf[lastKey] = index;
        delete map.indexOf[key];

        map.keys[index] = lastKey;
        map.keys.pop();
    }

    function exist(Map storage map, address key) view public returns(bool) {
        return map.inserted[key];
    } 
}