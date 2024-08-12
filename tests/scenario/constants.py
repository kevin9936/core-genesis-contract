#round
MIN_ROUND = 7
ROUND_SECONDS = 86400

# decimals
FEE_DECIMALS = 100
PERCENT_DECIMALS = 10000
BTC_DECIMALS = 10**8
CORE_DECIMALS = 10**18
CHANGE_OUTPUT_MAX_AMOUNT = 10**6

CORE_AMOUNT_PER_REWARD = 10 ** 6
BTC_AMOUNT_PER_REWARD = 10 ** 8

# account mgr
CONSENSUS_ADDR_NAME_PREFIX = "C_"
FEE_ADDR_NAME_PREFIX = "F_"
OPERATOR_NAME_PREFIX = "P"
DELEGATOR_NAME_PREFIX = "U"
SPONSOR_NAME_PREFIX = "S"

OPERATOR_ADDR_FROM_IDX = 0
OPERATOR_ADDR_COUNT = 30
DELEGATOR_ADDR_FROM_IDX = 30
DELEGATOR_ADDR_COUNT = 60
BACKUP_ADDR_FROM_IDX = 90
BACKUP_ADDR_COUNT = 9
SPONSOR_ADDR_FROM_IDX = 99
SPONSOR_ADDR_COUNT = 1


# task genegator
CHAIN_TASK_BASE_TYPE = 1
CANDIDATE_TASK_BASE_TYPE = 30
DELEGATOR_TASK_BASE_TYPE = 60
PROBABILITY_DECIMALS = 100
DEFAULT_PROBABILITY = 30

MAX_BLOCK_COUNT_PER_VALIDATOR = 2

MAX_CORE_STAKE_GRADE_FLAG = 7
GRADE_FLAG_KEY = "gradeActive"
GRADES_KEY = "grades"
GRADE_PERCENT_KEY = "percentage"

MIN_GRADE_COUNT = 3
MAX_GRADE_COUNT = 10
MAX_CORE_STAKE_GRADE_LEVEL = 10**6
MAX_CORE_STAKE_GRADE_PERCENT = 10**5

MAX_BTC_STAKE_GRADE_LEVEL = 4000

MAX_CANDIDATE_COMMISSION = 300

BITCOIN_TX_SYMBOL_PREFIX = "tx_"