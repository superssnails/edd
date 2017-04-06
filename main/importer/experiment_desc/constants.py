# coding: utf-8
from __future__ import unicode_literals

from collections import OrderedDict

from requests import codes

# error conditions that are detected / handled during Experiment Description upload process.
# These values must remain unique, and are used both as dictionary keys within the back-end code
# and for user display in the front end
# TODO: consider creating an class to encapsulate error title/subtitle/(HTTP status code?)
# associations implied here and elsewhere in the code.  This approach evolved from the ground up,
# but might be clarified by a refactor.

####################################################################################################
# User data entry errors
####################################################################################################
# generic errors (apply regardless of input format)
NO_INPUT = "No line description data were found in the input"
DUPLICATE_INPUT_LINE_NAMES = 'Duplicate line names in the input'
EXISTING_LINE_NAMES = 'Input would duplicate existing line names'
DUPLICATE_INPUT_ASSAY_NAMES = 'Duplicate assay names within the input for a single protocol'
EXISTING_ASSAY_NAMES = 'Inputs would duplicate existing assay names'

NON_STRAIN_TITLE = 'Non-strain ICE entry'
NON_STRAIN_ICE_ENTRY = 'Non-strain ICE entries'
PART_NUMBER_NOT_FOUND = 'Part number(s) not found in ICE'


# Experiment Description file-specific errors
BAD_FILE_CATEGORY = 'Incorrect File'
EMPTY_WORKBOOK = 'Empty workbook'
DUPLICATE_ASSAY_METADATA = 'Several columns specify the same assay metadata'
DUPLICATE_LINE_METADATA = 'Duplicate line metadata columns'
INVALID_CELL_TYPE_TITLE = 'Invalid cell type'
INVALID_CELL_TYPE = 'Cells have invalid type'
INVALID_REPLICATE_COUNT = 'Invalid replicate count'
ZERO_REPLICATES = 'Zero replicates are not allowed. If no lines are desired, remove row(s) from ' \
                  'the file.'
MISSING_REQUIRED_LINE_NAME = 'Rows missing required line name'
MISSING_REQUIRED_COLUMN_TITLE = 'Incorrect file format'
INVALID_COLUMN_HEADER_TITLE = 'Invalid column headers'
UNMATCHED_ASSAY_COL_HEADERS_KEY = 'Invalid column header(s) (Unmatched assay metadata suffix)'
INVALID_COLUMN_HEADER = 'Invalid column header(s)'
INCORRECT_TIME_FORMAT = 'Incorrect time format'
# only supported for strains, since some metadata columns purposefully allow comma-delimited entry
INCONSISTENT_COMBINATORIAL_VALUE = 'Combinatorial value provided for single-valued column'
UNPARSEABLE_COMBINATORIAL_VALUE = 'Unparseable combinatorial value'

INTERNAL_EDD_ERROR_TITLE = 'Internal EDD error'


# either user input error in Experiment Description/ICE part permissions, or an ICE error (known ICE
# errors exist in ICE 5.2.2 as of 3-1-17)
SINGLE_PART_ACCESS_ERROR_CATEGORY = 'ICE Part Access Problem'
FORBIDDEN_PART_KEY = 'Missing ICE read permission for part number(s)'

# Experiment Description file-specific warnings
MULTIPLE_WORKSHEETS_FOUND = 'Multiple worksheets were found in the document'
LINE_META_CAPITALIZATION_ONLY_DIFFERENCE = ('Found some line metadata types that differ only by '
                                            'case. Case-insensitive matching in parsing code will '
                                            'arbitrarily choose one')
ASSAY_META_CAPITALIZATION_ONLY_DIFFERENCE = ('Found some assay metadata types that differ only by '
                                             'case. Case-insensitive matching in parsing code will '
                                             'arbitrarily choose one')
UNSUPPORTED_LINE_METADATA = 'Unsupported line metadata'
IGNORED_INPUT_CATEGORY = 'User Input Ignored'
ROWS_MISSING_REPLICATE_COUNT = 'Rows missing replicate count (assumed 1 line)'

####################################################################################################
# Self/client consistency checks.  Experiment Description code is written defensively to help to
# detect coding errors in EDD's eventual Experiment Description GUI, an API client,
# or in development / maintenance of complex Experiment Description back-end code)
####################################################################################################
FOUND_PART_NUMBER_DOESNT_MATCH_QUERY = 'Found part number does not match query'
INVALID_ASSAY_META_PK = 'Invalid assay metadata pks'
INVALID_LINE_META_PK = 'Invalid line metadata pks'
INVALID_PROTOCOL_META_PK = 'Invalid protocol pks'
PARSE_ERROR = 'Parse error'
UNMATCHED_PART_NUMBER = 'Unmatched part number(s). This indicates a coding error in EDD.'

# Combinatorial GUI or API - specific errors
INVALID_AUTO_NAMING_INPUT = 'Invalid element for automatic naming'

####################################################################################################
# ICE-related errors
####################################################################################################

# anticipated systemic (e.g. communication) error or error that isn't otherwise planned for /
# handled separately (e.g. EDD/ICE configuration errors or ICE bugs)
SYSTEMIC_ICE_ERROR_CATEGORY = 'ICE-related Error'
GENERIC_ICE_RELATED_ERROR = ("ICE couldn't be contacted to find strains referenced in your "
                             "file, and EDD administrators have been notified of the problem.")

# Proactively check for part numbers that don't match EDD's part number pattern. This will help
# users detect bad data entry when diagnosing other parsing-related errors, and will also help
# us keep EDD's pattern configuration data up to date with use
PART_NUM_PATTERN_TITLE = 'Unrecognized part number pattern'
PART_NUMBER_PATTERN_UNMATCHED_WARNING = ("One or more part numbers didn't match the expected "
                                         "pattern. This probably indicates a data entry error")

####################################################################################################
# Generic errors... likely require admin investigation / determination re: cause
####################################################################################################

UNPREDICTED_ERROR = 'An unpredicted error occurred'
UNSUPPORTED_FILE_TYPE = 'Unsupported file type'  # TODO RESOLVE WITH incorrect file format

# Errors caused by outstanding curation work in JBEI's database / resulting lack of constraints in
# EDD's DB schema...see EDD-158
NON_UNIQUE_STRAIN_UUIDS = 'Non-unique strain uuids'
SUSPECTED_MATCH_STRAINS = 'Suspected match strain(s)'

####################################################################################################
# Request parameters
####################################################################################################
# TODO: Restore earlier values after making these POST data instead.
# IGNORE_ICE_RELATED_ERRORS_PARAM = 'ignoreIceRelatedErrors'
# ALLOW_DUPLICATE_NAMES_PARAM = 'allowDuplicateNames'
IGNORE_ICE_RELATED_ERRORS_PARAM = 'IGNOREICERELATEDERRORS'
ALLOW_DUPLICATE_NAMES_PARAM = 'ALLOWDUPLICATENAMES'

####################################################################################################
# Http error codes used / considered in this package.
####################################################################################################
OK = codes.ok
INTERNAL_SERVER_ERROR = codes.internal_server_error
BAD_REQUEST = codes.bad_request
NOT_FOUND = codes.not_found
METHOD_NOT_ALLOWED = codes.method_not_allowed
NOT_ACCEPTABLE = codes.not_acceptable
TOO_MANY_REQUESTS = codes.too_many_requests
SERVICE_UNAVAILABLE = codes.service_unavailable
FORBIDDEN = codes.forbidden
CONFLICT = codes.conflict

####################################################################################################
# Categorization and display priority order for predicted errors / warnings
####################################################################################################
# Define display priority order for all errors defined in this file.  The back-end will provide
# errors in this order for display in the user interface. Generally, we list user errors first
# so that even in the case of EDD / ICE errors, users and client code can see / resolve their own
# errors first. There's also some dependence here on the order in which the back end code executes
# major steps.
ERROR_PRIORITY_ORDER = OrderedDict()

# Experiment Description file-specific errors
ERROR_PRIORITY_ORDER[BAD_FILE_CATEGORY] = (
        # file-wide errors
        EMPTY_WORKBOOK,
        UNSUPPORTED_FILE_TYPE,
        MULTIPLE_WORKSHEETS_FOUND,

        # errors in defining column headers
        MISSING_REQUIRED_COLUMN_TITLE,
        INVALID_COLUMN_HEADER,
        UNMATCHED_ASSAY_COL_HEADERS_KEY,  # TODO: specifically mention assay col header suffix

        DUPLICATE_LINE_METADATA,    # TODO: check/rename these two to append "COLS"
        DUPLICATE_ASSAY_METADATA,
)
INVALID_FILE_VALUE_CATEGORY = 'Invalid Cell Values'
ERROR_PRIORITY_ORDER[INVALID_FILE_VALUE_CATEGORY] = (
    # cell-specific values
    MISSING_REQUIRED_LINE_NAME,
    INVALID_CELL_TYPE,
    INCONSISTENT_COMBINATORIAL_VALUE,
    INCORRECT_TIME_FORMAT,
    UNPARSEABLE_COMBINATORIAL_VALUE,
)

# these apply equally to JSON or Excel
BAD_GENERIC_INPUT_CATEGORY = 'Invalid Values'
ERROR_PRIORITY_ORDER[BAD_GENERIC_INPUT_CATEGORY] = (
        NO_INPUT,
        INVALID_REPLICATE_COUNT,
        ZERO_REPLICATES
)

##################################
# User-created ICE errors
#################################
USER_CREATED_ICE_PART_ERRORS = (
    PART_NUMBER_NOT_FOUND,
    NON_STRAIN_ICE_ENTRY,
    FORBIDDEN_PART_KEY,)
ERROR_PRIORITY_ORDER[SINGLE_PART_ACCESS_ERROR_CATEGORY] = USER_CREATED_ICE_PART_ERRORS

################################
# ICE-related software/configuration/communication errors
################################
ERROR_PRIORITY_ORDER[SYSTEMIC_ICE_ERROR_CATEGORY] = (GENERIC_ICE_RELATED_ERROR,)


ERROR_PRIORITY_ORDER[NON_STRAIN_TITLE] = (  # TODO: rename to NON_STRAIN_PART_CATEGORY
    NON_STRAIN_ICE_ENTRY
)

NAMING_OVERLAP_CATEGORY = 'Naming Overlap'

# User-created naming overlaps (depend on prior ICE communication since strain names could be used
# in line/assay naming)
_NAMING_OVERLAPS = (
    DUPLICATE_INPUT_LINE_NAMES,
    EXISTING_LINE_NAMES,  # TODO make var name study-specific

    # TODO: included here for safety, but unlikely at present that these will be created...wait
    # until we implement/use a combinatorial GUI under EDD-257, then remove if never witnessed.
    DUPLICATE_INPUT_ASSAY_NAMES,
    EXISTING_ASSAY_NAMES,
)
ERROR_PRIORITY_ORDER[NAMING_OVERLAP_CATEGORY] = _NAMING_OVERLAPS

################################
# Generic errors... users can't help with these
################################
ERROR_PRIORITY_ORDER[INTERNAL_EDD_ERROR_TITLE] = (
    INVALID_AUTO_NAMING_INPUT,  # Combinatorial GUI- or other API-client errors

    UNPREDICTED_ERROR,
    # Errors caused by outstanding curation work in JBEI's database / resulting lack of constraints
    # in EDD's DB schema...see EDD-158
    NON_UNIQUE_STRAIN_UUIDS,
    SUSPECTED_MATCH_STRAINS,

    ##################################
    # EDD self/client consistency checks
    ##################################
    FOUND_PART_NUMBER_DOESNT_MATCH_QUERY,
    INVALID_ASSAY_META_PK,
    INVALID_LINE_META_PK,
    INVALID_PROTOCOL_META_PK,
    PARSE_ERROR,
    UNMATCHED_PART_NUMBER,
)

WARNING_PRIORITY_ORDER = OrderedDict()
WARNING_PRIORITY_ORDER[IGNORED_INPUT_CATEGORY] = (
    # Experiment Description file-specific warnings
    UNSUPPORTED_LINE_METADATA,
    ROWS_MISSING_REPLICATE_COUNT,
    LINE_META_CAPITALIZATION_ONLY_DIFFERENCE,
    ASSAY_META_CAPITALIZATION_ONLY_DIFFERENCE,
)

WARNING_PRIORITY_ORDER[SINGLE_PART_ACCESS_ERROR_CATEGORY] = USER_CREATED_ICE_PART_ERRORS
WARNING_PRIORITY_ORDER[NAMING_OVERLAP_CATEGORY] = _NAMING_OVERLAPS
WARNING_PRIORITY_ORDER[SYSTEMIC_ICE_ERROR_CATEGORY] = (GENERIC_ICE_RELATED_ERROR,)
WARNING_PRIORITY_ORDER[INTERNAL_EDD_ERROR_TITLE] = (PART_NUMBER_PATTERN_UNMATCHED_WARNING,)

