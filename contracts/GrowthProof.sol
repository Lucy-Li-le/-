// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract GrowthProof {
    mapping(address => bytes32[]) private growthRecords;

    event GrowthRecorded(
        address indexed user,
        bytes32 indexed growthHash,
        uint256 timestamp
    );

    function recordGrowth(bytes32 growthHash) external {
        require(growthHash != bytes32(0), "growth hash is empty");

        growthRecords[msg.sender].push(growthHash);

        emit GrowthRecorded(
            msg.sender,
            growthHash,
            block.timestamp
        );
    }

    function getGrowthCount(address user)
        external
        view
        returns (uint256)
    {
        return growthRecords[user].length;
    }

    function getGrowthHash(address user, uint256 index)
        external
        view
        returns (bytes32)
    {
        return growthRecords[user][index];
    }
}

