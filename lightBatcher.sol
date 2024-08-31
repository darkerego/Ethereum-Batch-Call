//SPDX-License-Identifier: Unlicense
pragma solidity ^0.8.17;
pragma experimental ABIEncoderV2;



contract EvmCallBatcher{
    address private admin;
    address private thisAddress;

    

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

    


   function execute(address r, uint256 v, bytes memory d) internal returns(bool success, bytes memory retData) {
       /*
       Arbitrary call in yul.
       */
    assembly {
        let success_ := call(gas(), r, v, add(d, 0x00), mload(d), 0x00, 0x0)
        success := eq(success_, 0x1)
        let retSz := returndatasize()
        retData := mload(0x40)

            returndatacopy(mload(0x40), 0 , returndatasize())
            if iszero(success) {
                revert(retData, retSz)}
      }
      success = bool(success);
    }

    
    

    function batchArbitraryCalls(bytes[] calldata _calls) external payable {
        /*
        Gas effecient transaction batching. Takes an array of abi encoded calls.  This is 
        intended to be a public function, so in order to be gas effecient, the only safety 
        check that is performed is making sure that if this contract has ether in it, 
        the balance is not lower than it was before this is called.
       
        TODO: this entire function in assembly too.
        */
        auth();
        uint256 b = bal() - msg.value;
        for(uint256 i = 0; i < _calls.length; i++) {
            (address r, uint256 v, bytes memory d) = abi.decode(_calls[i], (address, uint256, bytes));
            execute(r,v,d);
        }
        if(bal() < b){revert();}
        }
}
