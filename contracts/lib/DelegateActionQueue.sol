// SPDX-License-Identifier: Apache2.0
pragma solidity 0.8.4;

import "./Structs.sol";

library DelegateActionQueue {
    struct Queue {
        DelegateAction[] items;
    }

    function enqueue(Queue storage queue, DelegateAction memory item) public {
        queue.items.push(item);
    }

    function dequeue(Queue storage queue) public returns(DelegateAction memory) {
        require(queue.items.length != 0, "Queue is empty.");
        DelegateAction memory item = queue.items[0];
        for (uint256 i = 0; i < queue.items.length - 1; i++) {
            queue.items[i] = queue.items[i + 1];
        }
        queue.items.pop();
        return item;
    }

    function isEmpty(Queue storage queue) public view returns (bool) {
        return queue.items.length == 0;
    }

    function length(Queue storage queue) public view returns (uint256) {
        return queue.items.length;
    }
}