//SPDX-License-Identifier: Unlicense
pragma solidity ^0.8.17;
pragma experimental ABIEncoderV2;
import "libs/IERC20.sol";



contract Batch{
    address private admin;
    address public thisAddress;

    

    constructor(){
        /*
        Set the admin address and store 
        address(this) to save gas later.
        */
        assembly {
            let sender := caller()
            sstore(admin.slot, sender)
            sstore(thisAddress.slot, address())
        }
    }

    function auth() internal view {
        /*
        Theoretically cheaper than using a require statement.
        */
        if(msg.sender != admin){
            revert();
        }
    }

    function recoverEth() external {
        /*Allows the admin to withdraw Ethereum*/
        auth();
        execute(msg.sender, bal(), "");
        }

    function recoverTokens(address tokenAddress) external {
        /*Allows the admin to withdraw ERC20 tokens*/
        auth();
        uint256 b = IERC20(tokenAddress).balanceOf(thisAddress);
        // TODO: the balance in assembly, maybe depending on gas effeciency
        transfer(tokenAddress, msg.sender, b);
    }

    function bal() internal view returns (uint256) {
        /*
        Most gas effecient way to get the balance of this contract.
        */
        uint256 self;
        assembly {
            self :=selfbalance()
        }
        return self;
    }

    function transfer(address tokenAddress, address to, uint256 amount) internal {
        /*
        Assembly ERC20 token transfer. This is mostly just for fun, as i don't think 
        we are really saving much gas doing this.
        */
        
        bytes4 _selector = 0xa9059cbb;  // bytes4(keccak('transfer(address,uint256)'))
        assembly {
            // We need 0x44 bytes for the calldata in memory.
            // We use the free memory pointer to find where to save it.
            let calldataOffset := mload(0x40)
            
            // We move the free memory pointer, but if this function is
            // 'external' we don't really need to
            mstore(0x40, add(calldataOffset, 0x44))
            
            // Store salldata to memory
            mstore(calldataOffset, _selector)
            mstore(add(calldataOffset, 0x04), to)
            mstore(add(calldataOffset, 0x24), amount)
            
            let result := call(
                gas(),
                tokenAddress,
                0,               // msg.value
                calldataOffset,
                0x44,
                0,               // return data offset
                0                // return data length
            )
            
            // Revert if call failed
            if eq(result, 0) {
                // Forward the error
                returndatacopy(0, 0, returndatasize())
                revert(0, returndatasize())
            }
        }
    }


   function execute(address r, uint256 v, bytes memory d) internal {
       /*
       Arbitrary call in yul.
       */
    assembly {
        let success_ := call(gas(), r, v, add(d, 0x00), mload(d), 0x20, 0x0)
        let success := eq(success_, 0x1)
        if iszero(success) {
            revert(mload(d), add(d, 0x20))
        }
      }
    }

    function forward(address r, uint256 v, bytes memory d) external payable {
        /*
        Simply forward a single call
        */
        uint256 b = bal() - msg.value;
        execute(r,v,d);
        if(bal() < b){revert();}

    }
    

    function batchCall(bytes[] calldata _calls) external payable {
        /*
        Gas effecient transaction batching. Takes an array of abi encoded calls.  This is 
        intended to be a public function, so in order to be gas effecient, the only safety 
        check that is performed is making sure that if this contract has ether in it, 
        the balance is not lower than it was before this is called.
       
        TODO: this entire function in assembly too.
        */
        uint256 b = bal() - msg.value;
        for(uint256 i = 0; i < _calls.length; i++) {
            (address r, uint256 v, bytes memory d) = abi.decode(_calls[i], (address, uint256, bytes));
            execute(r,v,d);
        }
        if(bal() < b){revert();}
        }
}
