'use client'

import { useState, useEffect, useRef } from 'react'
import { 
  useAccount, 
  useChainId, 
  useWriteContract,
  useBalance,
  useSwitchChain
} from 'wagmi'
import { erc20Abi } from 'viem'
import { contractAddresses, supportedChains, getChainColor } from '@/lib/chains'
import { parseUnits } from 'viem'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { initiateSponsorshipPayment, getPaymentStatus, reportTransaction } from '@/lib/api'
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'

const SPONSORSHIP_AMOUNT = 3 // 3 USDC
const POLLING_INTERVAL = 5000 // 5 seconds

interface SponsorshipButtonProps {
  taxonId: string
  speciesName: string
  onSponsorshipComplete?: () => void
  className?: string
  
  // New props for integration with ResearchCard
  setIsResearching: (isResearching: boolean) => void
  setProgressMessage: (message: string) => void
  setProgressPercent: (percent: number) => void
}

// Transaction-related messages for the first phase
const transactionMessages = [
  "Connecting to blockchain...",
  "Preparing USDC transfer...",
  "Sending transaction...",
  "Waiting for confirmation...",
  "Verifying payment...",
  "Processing transaction...",
  "Preparing research process..."
];

// Research-related messages from useResearchProcess
const researchMessages = [
  "Scanning the forest canopy...",
  "Consulting botanical references...",
  "Exploring native habitats...",
  "Analyzing growth patterns...",
  "Documenting ecological relationships...",
  "Examining soil preferences...",
  "Cataloging cultural significance...",
  "Mapping geographical distribution...",
  "Calculating conservation status...",
  "Determining stewardship practices..."
];

type SponsorshipStatus = 
  'idle' | 
  'connecting' | 
  'switching_chain' | 
  'preparing' | 
  'transferring' | 
  'tx_confirming' |  // New: Transaction confirmation phase
  'researching' |    // New: Research phase
  'completed' | 
  'error' | 
  'needs_verification'

export function SponsorshipButton({ 
  taxonId, 
  speciesName,
  onSponsorshipComplete,
  className = '',
  setIsResearching,
  setProgressMessage,
  setProgressPercent
}: SponsorshipButtonProps) {
  const { address, isConnected } = useAccount()
  const chainId = useChainId()
  const { switchChain } = useSwitchChain()
  
  const [status, setStatus] = useState<SponsorshipStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [sponsorshipId, setSponsorshipId] = useState<string | null>(null)
  const [transactionHash, setTransactionHash] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [treasuryAddress, setTreasuryAddress] = useState<string | null>(null)
  const messageIntervalRef = useRef<NodeJS.Timeout | null>(null)
  
  // Get chain configuration
  const currentChainConfig = contractAddresses[chainId?.toString() || '0']
  const usdcAddress = currentChainConfig?.usdcAddress
  
  // Check if current chain is supported
  const isChainSupported = !!usdcAddress
  
  // Get USDC balance - enhanced with retry and better error handling
  const { data: usdcBalance, refetch: refetchBalance, error: balanceError } = useBalance({
    address,
    token: usdcAddress as `0x${string}` | undefined,
    chainId,
    query: {
      enabled: isConnected && isChainSupported && !!usdcAddress,
      refetchInterval: 5000,
      staleTime: 2000, // Consider data stale after 2 seconds
      retry: 3,        // Retry failed requests 3 times
      retryDelay: 1000 // Wait 1 second between retries
    }
  })
  
  // Log balance errors for troubleshooting
  useEffect(() => {
    if (balanceError && isConnected && isChainSupported && usdcAddress) {
      console.error("USDC Balance Error:", {
        error: balanceError,
        chain: chainId,
        usdcAddress,
        walletAddress: address
      });
      
      // Attempt a manual refetch after error
      const timeout = setTimeout(() => {
        console.log("Attempting balance refetch after error...");
        refetchBalance();
      }, 2000);
      
      return () => clearTimeout(timeout);
    }
  }, [balanceError, isConnected, isChainSupported, usdcAddress, refetchBalance, chainId, address]);
  
  // USDC Transfer function - updated for wagmi v2
  const { writeContract: transferUsdc, data: transferTxHash, isPending: isTransferring, isSuccess: isTransferSuccess } = useWriteContract()
  
  // Check if user has sufficient USDC balance with enhanced debug logging
  const hasSufficientBalance = usdcBalance ? 
    parseFloat(usdcBalance.formatted) >= SPONSORSHIP_AMOUNT : false
    
  // Add debug logging for troubleshooting balance issues
  useEffect(() => {
    if (isConnected && isChainSupported) {
      console.log(`USDC Balance Check - Chain ${chainId}:`, {
        address: address,
        usdcAddress: usdcAddress,
        balanceReceived: !!usdcBalance,
        balanceFormatted: usdcBalance?.formatted,
        balanceValue: usdcBalance?.value?.toString(),
        sufficientBalance: hasSufficientBalance,
        requiredAmount: SPONSORSHIP_AMOUNT
      });
    }
  }, [usdcBalance, isConnected, isChainSupported, chainId, address, hasSufficientBalance]);
    
  // Start cycling messages based on current phase
  const startMessageCycling = (phase: 'transaction' | 'research') => {
    // Clear any existing interval
    if (messageIntervalRef.current) {
      clearInterval(messageIntervalRef.current);
    }
    
    let messageIndex = 0;
    const messages = phase === 'transaction' ? transactionMessages : researchMessages;
    
    // Set initial progress bar percentage
    setProgressPercent(phase === 'transaction' ? 33 : 33); // Transaction phase shows 33%
    
    // Set initial message
    setProgressMessage(messages[0]);
    
    // Start cycling messages
    messageIntervalRef.current = setInterval(() => {
      messageIndex = (messageIndex + 1) % messages.length;
      setProgressMessage(messages[messageIndex]);
      
      // During research phase, gradually increase the progress percentage
      if (phase === 'research') {
        setProgressPercent(prev => {
          // Ensure we don't exceed 100%
          const increment = (100 - 33) / (researchMessages.length * 2); // Spread progress over multiple cycles
          return Math.min(100, prev + increment);
        });
      }
    }, 3000);
  };
  
  // Clean up message cycling
  const stopMessageCycling = () => {
    if (messageIntervalRef.current) {
      clearInterval(messageIntervalRef.current);
      messageIntervalRef.current = null;
    }
  };
  
  // Handle "Sponsor" button click
  const handleSponsor = async () => {
    try {
      setError(null)
      
      // Check wallet connection
      if (!isConnected) {
        setStatus('connecting')
        return
      }
      
      // Check chain support
      if (!isChainSupported) {
        setStatus('switching_chain')
        
        // Find a supported chain
        const supported = supportedChains.filter(chain => {
          const config = contractAddresses[chain.id.toString()]
          return config?.usdcAddress;
        })
        
        if (supported.length === 0) {
          setError('No supported chains available. Please try again later.')
          setStatus('error')
          return
        }
        
        // Switch to first supported chain
        try {
          await switchChain({ chainId: supported[0].id })
        } catch (switchError: any) {
          setError(`Failed to switch chain: ${switchError.message}`)
          setStatus('error')
          return
        }
        return
      }
      
      // Check balance with improved error handling and retry option
      if (!usdcBalance) {
        setError(`Unable to check USDC balance. Network issues may be occurring. Please try again or switch networks.`)
        setStatus('error')
        console.error("Balance check failed - usdcBalance is null or undefined");
        return
      }
      
      if (!hasSufficientBalance) {
        // Check if balance is very close (within 0.1 USDC) - could be rounding issue
        const isVeryClose = usdcBalance && 
          (SPONSORSHIP_AMOUNT - parseFloat(usdcBalance.formatted) < 0.1);
          
        if (isVeryClose) {
          console.warn("Balance is very close to required amount - possible rounding issue");
          // Proceed anyway if it's a tiny difference that could be rounding
          console.log("Proceeding despite very small balance difference");
        } else {
          setError(`Insufficient USDC balance. You need at least ${SPONSORSHIP_AMOUNT} USDC. Your current balance: ${usdcBalance?.formatted || '0'} USDC`)
          setStatus('error')
          console.log(`Balance check failed - has ${usdcBalance?.formatted} USDC, needs ${SPONSORSHIP_AMOUNT} USDC`);
          return
        }
      }
      
      // Prepare sponsorship by registering intent with backend
      setStatus('preparing')
      try {
        // First, check if we can fall back to a treasury address from the chain config if the API fails
        const fallbackTreasuryAddress = currentChainConfig?.treasuryAddress;
        console.log(`Chain ${chainId} treasury address from config: ${fallbackTreasuryAddress}`);
        
        try {
          const response = await initiateSponsorshipPayment({
            taxon_id: taxonId,
            wallet_address: address!,
            chain: chainId.toString()
          });
          
          if (!response || !response.treasury_address) {
            throw new Error('Invalid response from server: missing treasury address');
          }
          
          setSponsorshipId(response.sponsorship_id)
          setTreasuryAddress(response.treasury_address)
          
          // Proceed to transfer USDC
          handleTransfer(response.treasury_address)
        } catch (err: any) {
          console.error('Failed to initiate sponsorship via API:', err);
          
          // Fall back to using the treasury address from the chain config if available
          if (fallbackTreasuryAddress) {
            console.log(`Falling back to treasury address from chain config: ${fallbackTreasuryAddress}`);
            setTreasuryAddress(fallbackTreasuryAddress);
            
            // Proceed with the transfer using the fallback address
            handleTransfer(fallbackTreasuryAddress);
          } else {
            throw new Error('No treasury address available. Please try a different chain.');
          }
        }
      } catch (err: any) {
        console.error('Sponsorship preparation failed:', err)
        setError(err.message || 'Failed to prepare sponsorship')
        setStatus('error')
        setIsResearching(false)
      }
    } catch (err: any) {
      console.error('Sponsorship error:', err)
      setError(err.message || 'Failed to sponsor research')
      setStatus('error')
      setIsResearching(false)
    }
  }
  
  // Handle USDC transfer - updated for wagmi v2
  const handleTransfer = (treasuryAddr: string) => {
    setStatus('transferring')
    
    // Start the research UI display
    setIsResearching(true)
    startMessageCycling('transaction')
    
    try {
      // Ensure treasury address is valid before proceeding
      if (!treasuryAddr || !treasuryAddr.startsWith('0x')) {
        console.error(`Invalid treasury address: ${treasuryAddr}`)
        setError('Invalid treasury address configuration. Please try another chain.')
        setStatus('error')
        setIsResearching(false)
        stopMessageCycling()
        return;
      }
      
      console.log(`Transferring ${SPONSORSHIP_AMOUNT} USDC to treasury address: ${treasuryAddr}`)
      
      // Send USDC to treasury address
      transferUsdc({
        address: usdcAddress as `0x${string}`,
        abi: erc20Abi,
        functionName: 'transfer',
        args: [
          treasuryAddr as `0x${string}`,
          parseUnits(SPONSORSHIP_AMOUNT.toString(), 6) // USDC has 6 decimals
        ]
      })
    } catch (err: any) {
      console.error('Transfer error:', err)
      setError(err.message || 'Failed to transfer USDC')
      setStatus('error')
      setIsResearching(false)
      stopMessageCycling()
    }
  }
  
  // Set up poller for transaction confirmation
  const startPollingForStatus = async (txHash: string) => {
    setIsPolling(true)
    setStatus('tx_confirming')
    
    let retries = 0
    const maxRetries = 10 // 10 x 5 seconds = 50 seconds max
    let notFoundCount = 0
    const maxNotFoundCount = 3 // Consider success after multiple not_found responses
    
    const pollStatus = async () => {
      try {
        const status = await getPaymentStatus(txHash)
        console.log('Polled payment status:', status)
        
        // Check for any indication of success:
        // 1. status is explicitly 'completed' or 'confirmed'
        // 2. status is a valid object with research_status that indicates progress
        const isSuccessfulStatus = 
          status.status === 'completed' || 
          status.status === 'confirmed' ||
          (status.species && status.species.length > 0 && 
           (status.species[0].research_status === 'completed' || 
            status.species[0].research_status === 'researching'));
        
        if (isSuccessfulStatus) {
          console.log('Payment confirmed by backend, transaction is valid');
          
          // Switch to research phase
          setStatus('researching')
          
          // Change to research message cycling
          startMessageCycling('research')
          
          // Call the callback to trigger the actual research process
          if (onSponsorshipComplete) {
            // Call immediately
            onSponsorshipComplete()
            
            // Setup more frequent checks for the first 30 seconds
            // UI updates are critical during this phase
            const earlyChecks = [2000, 4000, 6000, 8000, 10000]; // Every 2 seconds for first 10s
            const lateChecks = [15000, 20000, 25000, 30000];    // Every 5 seconds for next 20s
            
            // Combine early and late checks for comprehensive polling
            [...earlyChecks, ...lateChecks].forEach((delay, index) => {
              setTimeout(() => {
                console.log(`Additional data refresh #${index + 1} after ${delay/1000}s`);
                onSponsorshipComplete();
              }, delay);
            });
          }
          
          return
        }
        
        // If transaction was not found, increment counter
        if (status.status === 'not_found') {
          notFoundCount++
          console.log(`Transaction not found in backend (${notFoundCount}/${maxNotFoundCount})`)
          
          // If we've checked multiple times and it's still not found,
          // the backend might not be tracking it but the transaction is still valid
          if (notFoundCount >= maxNotFoundCount) {
            console.log('Transaction confirmed on chain but not found in backend after multiple attempts')
            
            // Switch to research phase
            setStatus('researching')
            
            // Change to research message cycling
            startMessageCycling('research')
            
            if (onSponsorshipComplete) {
              onSponsorshipComplete()
              
              // Set up more modest polling - just 3 additional attempts over 15 seconds
              // This should be enough to catch when the backend updates the status
              const additionalChecks = [5000, 10000, 15000]; // 5s, 10s, 15s after completion
              
              additionalChecks.forEach((delay, index) => {
                setTimeout(() => {
                  console.log(`Additional data refresh #${index + 1} after ${delay/1000}s`);
                  onSponsorshipComplete();
                }, delay);
              });
            }
            
            return
          }
        }
        
        retries++
        if (retries >= maxRetries) {
          console.log('Max retries reached, stopping polling')
          // Don't automatically mark as completed, show needs verification status instead
          setStatus('needs_verification')
          setError('Transaction was sent, but research process could not be verified. Please check again later.')
          setIsPolling(false)
          setIsResearching(false)
          stopMessageCycling()
          return
        }
        
        // Continue polling
        setTimeout(pollStatus, POLLING_INTERVAL)
      } catch (error) {
        console.error('Error polling for status:', error)
        retries++
        
        // If we've had too many errors (including network errors),
        // consider it as a pending status that needs manual verification
        if (retries >= maxRetries / 2) {
          console.log('Too many polling errors, showing needs verification status')
          setStatus('needs_verification')
          setError('Transaction sent but verification failed. The research might still be processing. Please check again later.')
          setIsPolling(false)
          setIsResearching(false)
          stopMessageCycling()
          return
        }
        
        // Continue polling despite errors
        setTimeout(pollStatus, POLLING_INTERVAL)
      }
    }
    
    // Start polling
    pollStatus()
  }
  
  // Handle transfer transaction completion
  useEffect(() => {
    if (isTransferSuccess && transferTxHash) {
      toast.success('USDC transfer complete')
      setTransactionHash(transferTxHash)
      
      // Report the transaction hash to the backend to link it with the sponsorship
      // Always send all available data to ensure the backend can process it even if there are DB issues
      reportTransaction(
        sponsorshipId || '', 
        transferTxHash,
        taxonId,
        address,
        chainId?.toString()
      )
        .then(response => {
          console.log('Transaction reported successfully:', response)
          
          // Start polling for transaction status
          startPollingForStatus(transferTxHash)
        })
        .catch(error => {
          console.error('Failed to report transaction:', error)
          // Still start polling even if reporting fails
          startPollingForStatus(transferTxHash)
        })
    }
  }, [isTransferSuccess, transferTxHash, sponsorshipId])
  
  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopMessageCycling();
    };
  }, []);
  
  // Button text based on status
  const getButtonText = () => {
    if (!isConnected) {
      return 'Connect Wallet to Fund Research'
    }
    
    switch (status) {
      case 'idle':
        return 'Sponsor This Tree'
      case 'connecting':
        return 'Connect Wallet'
      case 'switching_chain':
        return 'Switch Network'
      case 'preparing':
      case 'transferring':
      case 'tx_confirming':
      case 'researching':
        return 'Processing...'
      case 'completed':
        return 'Sponsorship Complete!'
      case 'needs_verification':
        return 'Needs Verification'
      case 'error':
        return 'Sponsorship Failed'
      default:
        return 'Sponsor This Tree'
    }
  }
  
  // Disable button based on status - updated for wagmi v2
  const isButtonDisabled = [
    'preparing', 
    'transferring', 
    'tx_confirming',
    'researching',
    'completed',
    'needs_verification'
  ].includes(status) || isTransferring || isPolling
  
  return (
    <div className="w-full flex flex-col gap-2">
      <Button
        onClick={handleSponsor}
        disabled={isButtonDisabled}
        className={`${className} relative overflow-hidden px-6 py-3 backdrop-blur-md rounded-xl text-white font-semibold transition-colors ${
          status === 'completed' ? 'bg-green-600/80 hover:bg-green-600' : 
          status === 'error' ? 'bg-red-600/80 hover:bg-red-600' : 
          status === 'needs_verification' ? 'bg-yellow-600/80 hover:bg-yellow-600' : 
          ''
        }`}
      >
        {(isButtonDisabled && status !== 'completed' && status !== 'needs_verification') && (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        )}
        {status === 'completed' && (
          <CheckCircle2 className="mr-2 h-4 w-4" />
        )}
        {status === 'error' && (
          <AlertCircle className="mr-2 h-4 w-4" />
        )}
        {status === 'needs_verification' && (
          <AlertCircle className="mr-2 h-4 w-4" />
        )}
        {getButtonText()}
      </Button>
      
      {/* Display errors with retry option */}
      {error && status !== 'researching' && (
        <div className="text-red-500 text-base mt-2">
          <div className="mb-1">{error}</div>
          {status === 'error' && (
            <div className="flex gap-2 mt-2">
              <button 
                onClick={() => {
                  setError(null);
                  setStatus('idle');
                  refetchBalance();
                }}
                className="text-xs bg-white/10 hover:bg-white/20 text-white py-1 px-2 rounded"
              >
                Retry Balance Check
              </button>
              <button 
                onClick={() => window.location.reload()}
                className="text-xs bg-white/10 hover:bg-white/20 text-white py-1 px-2 rounded"
              >
                Refresh Page
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}