// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

library BTCUtils {
    struct BTCTx {
        bytes32 txid;        // Transaction ID
        uint32 lockTime;      // Script lockTime 
        uint256 blockTimestamp;      // Block entry time
        uint64 btcAmount;   // Stake Amount
        uint32 outputIndex;   // out put index of the stake
        address delegator;   // stake delegator
        address candidate;   // stake candidate 
        address relay;   // porter
    }


    function calculateTxId(bytes memory _tx) internal pure returns (bytes32) {
        return sha256(abi.encodePacked(sha256(_tx)));
    }

    function uintToHexNoPadding(uint256 value) public pure returns (string memory) {
        bytes memory result;
        while (value > 0) {
            result = abi.encodePacked(uint8(value & 0xFF), result);
            value >>= 8;
        }
        for (uint i = 0; i < result.length / 2; i++) {
            bytes1 temp = result[i];
            result[i] = result[result.length - 1 - i];
            result[result.length - 1 - i] = temp;
        }
        return bytesToHex(result);
    }


    function uintToLittleEndianHex(uint256 value) public pure returns (string memory) {
        return bytesToHex(abi.encodePacked(reverseBytes(uint64(value))));
    }

    function reverseBytes(uint64 value) internal pure returns (uint64) {
        uint64 reversed = 0;
        for (uint256 i = 0; i < 8; i++) {
            reversed = (reversed << 8) | (value & 0xFF);
            value >>= 8;
        }
        return reversed;
    }

    function bytesToHex(bytes memory data) internal pure returns (string memory) {
        bytes memory hexBytes = new bytes(data.length * 2);
        for (uint i = 0; i < data.length; i++) {
            hexBytes[i * 2] = nibbleToHexChar(data[i] >> 4);
            hexBytes[i * 2 + 1] = nibbleToHexChar(data[i] & 0x0F);
        }
        return string(hexBytes);
    }

    function nibbleToHexChar(bytes1 nibble) internal pure returns (bytes1) {
        uint8 nibbleValue = uint8(nibble);
        if (nibbleValue < 10) {
            return bytes1(nibbleValue + 0x30);
        } else {
            return bytes1(nibbleValue + 0x57);
        }
    }

    function convertHexStringToBytes(string memory hexStr) public pure returns (bytes memory) {
        bytes memory hexBytes = bytes(hexStr);
        bytes memory result = new bytes(hexBytes.length / 2);
        for (uint i = 0; i < result.length; i++) {
            result[i] = bytes1(uint8(parseHexChar(hexBytes[2 * i])) * 16 + uint8(parseHexChar(hexBytes[2 * i + 1])));
        }
        return result;
    }

    function parseHexChar(bytes1 hexChar) public pure returns (uint8) {
        if (hexChar >= 0x30 && hexChar <= 0x39) {
            return uint8(hexChar) - 0x30;
        } else if (hexChar >= 0x41 && hexChar <= 0x46) {
            return uint8(hexChar) - 0x41 + 10;
        } else if (hexChar >= 0x61 && hexChar <= 0x66) {
            return uint8(hexChar) - 0x61 + 10;
        }
        revert("Invalid hex character");
    }

    function calculateOpReturn(address candidate, address delegator, uint64 btcAmount, bytes memory script) public returns (bytes memory) {
        bytes memory input = hex"0200000001b78d73bfd3276fe2520fcd99672ba668547a9ca8bb9600f21a333ca955ee7256000000006a473044022046e23b8f6b749a15b0571848fe2b86bfbe7e158b23f37fb0335be0a71f48a5dd022076640b2d39659c26224c9e67101b34e1394a38ff08a4bdd88d7503f63e54adc5012103b3e19c8169b81d15ec21f9d0f3ed4b2f18c7c9e1149ce5f7ddebed7732724b9fffffffff02";
        bytes20 btcAddress = ripemd160(abi.encode(sha256(script)));
        bytes memory outputAddress = abi.encodePacked(hex"17a914", btcAddress, hex"87");
        bytes memory opReturn0 = hex"0000000000000000366a345341542b01045c";
        // delegator & candidate & fee & lock_data
        bytes memory opReturn1 = abi.encodePacked(delegator, candidate, hex"01", hex"80db8767");
        string memory btcAmount = uintToLittleEndianHex(btcAmount);
        bytes memory hexBtcAmount = convertHexStringToBytes(btcAmount);
        bytes memory concatenatedHex = abi.encodePacked(input, hexBtcAmount, outputAddress, opReturn0, opReturn1, hex"00000000");
        return concatenatedHex;
    }


}