// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/**
 * @title RecordRegistry
 * @author Vipul Ahirrao (Student) / Dr. Dipak Bhadane (Mentor)
 * @notice Decentralized registry for certificate fingerprint (SHA-256) anchoring and revocation tracking.
 * @dev Anchors cryptographic digests of certificates without storing sensitive or personal data.
 *      Enforces access control for registration and revocation while exposing public read-only verification views.
 */
contract RecordRegistry {
    // --- Custom Errors ---
    error UnauthorizedCaller(address caller);
    error RecordAlreadyExists(bytes32 key);
    error RecordNotFound(bytes32 key);
    error RecordAlreadyRevoked(bytes32 key);
    error InvalidRecordId();
    error InvalidFileHash();
    error InvalidReasonCode();
    error InvalidAddress();

    // --- Data Structures ---
    /**
     * @dev Optimized storage packing:
     * Slot 0: fileHash (32 bytes)
     * Slot 1: issuer (20 bytes) + registeredAt (8 bytes) + docType (1 byte) + exists (1 byte) + revoked (1 byte) + reasonCode (1 byte) = 32 bytes
     * Slot 2: revokedAt (8 bytes)
     */
    struct Record {
        bytes32 fileHash;     // SHA-256 digest of raw document bytes
        address issuer;       // Authorized account that performed registration
        uint64 registeredAt;  // Block timestamp of registration
        uint8 docType;        // Minimal metadata category: 1=degree, 2=marksheet, 3=training, etc.
        bool exists;          // Distinguishes initialized records from empty storage
        bool revoked;         // Revocation flag
        uint8 reasonCode;     // Reason code for revocation (1=issued_in_error, 2=superseded, 3=fraud_suspected, 4=other)
        uint64 revokedAt;     // Block timestamp when revoked (0 if active)
    }

    // --- State Variables ---
    address public owner;
    mapping(address => bool) public authorizedIssuers;
    mapping(bytes32 => Record) private records;

    // --- Events ---
    event IssuerAuthorized(address indexed issuer);
    event IssuerDeauthorized(address indexed issuer);
    event RecordRegistered(
        bytes32 indexed key,
        string recordId,
        address indexed issuer,
        bytes32 fileHash,
        uint8 docType,
        uint64 registeredAt
    );
    event RecordRevoked(
        bytes32 indexed key,
        string recordId,
        uint8 reasonCode,
        address indexed revokedBy,
        uint64 revokedAt
    );

    // --- Modifiers ---
    modifier onlyOwner() {
        if (msg.sender != owner) {
            revert UnauthorizedCaller(msg.sender);
        }
        _;
    }

    modifier onlyAuthorized() {
        if (msg.sender != owner && !authorizedIssuers[msg.sender]) {
            revert UnauthorizedCaller(msg.sender);
        }
        _;
    }

    // --- Constructor ---
    constructor() {
        owner = msg.sender;
        authorizedIssuers[msg.sender] = true;
        emit IssuerAuthorized(msg.sender);
    }

    // --- Access Control Management ---
    /**
     * @notice Authorize an account to register and revoke records.
     * @param issuer Account address to authorize.
     */
    function authorizeIssuer(address issuer) external onlyOwner {
        if (issuer == address(0)) revert InvalidAddress();
        authorizedIssuers[issuer] = true;
        emit IssuerAuthorized(issuer);
    }

    /**
     * @notice Revoke registration authority from an account.
     * @param issuer Account address to deauthorize.
     */
    function deauthorizeIssuer(address issuer) external onlyOwner {
        if (issuer == address(0)) revert InvalidAddress();
        authorizedIssuers[issuer] = false;
        emit IssuerDeauthorized(issuer);
    }

    // --- Write Operations ---
    /**
     * @notice Register a certificate fingerprint and minimal metadata.
     * @param recordId Opaque string identifier (e.g. "CERT-101").
     * @param fileHash SHA-256 digest of the certificate raw bytes.
     * @param docType Document type category (1=degree, 2=marksheet, 3=training).
     */
    function registerRecord(
        string calldata recordId,
        bytes32 fileHash,
        uint8 docType
    ) external onlyAuthorized {
        if (bytes(recordId).length == 0) revert InvalidRecordId();
        if (fileHash == bytes32(0)) revert InvalidFileHash();

        bytes32 key = keccak256(bytes(recordId));
        if (records[key].exists) {
            revert RecordAlreadyExists(key);
        }

        uint64 currentTimestamp = uint64(block.timestamp);

        records[key] = Record({
            fileHash: fileHash,
            issuer: msg.sender,
            registeredAt: currentTimestamp,
            docType: docType,
            exists: true,
            revoked: false,
            reasonCode: 0,
            revokedAt: 0
        });

        emit RecordRegistered(
            key,
            recordId,
            msg.sender,
            fileHash,
            docType,
            currentTimestamp
        );
    }

    /**
     * @notice Permanently revoke a registered certificate record.
     * @param recordId Opaque string identifier of the record.
     * @param reasonCode Reason identifier (1=issued_in_error, 2=superseded, 3=fraud_suspected, 4=other).
     */
    function revokeRecord(
        string calldata recordId,
        uint8 reasonCode
    ) external onlyAuthorized {
        if (bytes(recordId).length == 0) revert InvalidRecordId();
        if (reasonCode == 0) revert InvalidReasonCode();

        bytes32 key = keccak256(bytes(recordId));
        Record storage rec = records[key];

        if (!rec.exists) {
            revert RecordNotFound(key);
        }
        if (rec.revoked) {
            revert RecordAlreadyRevoked(key);
        }

        uint64 currentTimestamp = uint64(block.timestamp);
        rec.revoked = true;
        rec.reasonCode = reasonCode;
        rec.revokedAt = currentTimestamp;

        emit RecordRevoked(
            key,
            recordId,
            reasonCode,
            msg.sender,
            currentTimestamp
        );
    }

    // --- Read-Only Verification Views ---
    /**
     * @notice Verify a computed file hash against the registered fingerprint.
     * @param recordId Opaque string identifier of the record.
     * @param fileHash SHA-256 digest computed from raw uploaded file bytes.
     * @return exists True if the record was ever registered.
     * @return hashMatch True if the record exists and computed fileHash matches registered hash.
     * @return revoked True if the record has been revoked.
     */
    function verifyHash(
        string calldata recordId,
        bytes32 fileHash
    ) external view returns (bool exists, bool hashMatch, bool revoked) {
        bytes32 key = keccak256(bytes(recordId));
        Record storage rec = records[key];

        if (!rec.exists) {
            return (false, false, false);
        }

        exists = true;
        hashMatch = (rec.fileHash == fileHash);
        revoked = rec.revoked;
    }

    /**
     * @notice Check whether a record exists and its revocation status.
     * @param recordId Opaque string identifier.
     * @return exists True if the record exists.
     * @return revoked True if the record exists and is revoked.
     */
    function isRevoked(
        string calldata recordId
    ) external view returns (bool exists, bool revoked) {
        bytes32 key = keccak256(bytes(recordId));
        Record storage rec = records[key];
        return (rec.exists, rec.revoked);
    }

    /**
     * @notice Retrieve full record details for public inspection.
     * @param recordId Opaque string identifier.
     */
    function getRecord(
        string calldata recordId
    )
        external
        view
        returns (
            bytes32 fileHash,
            address issuer,
            uint64 registeredAt,
            uint8 docType,
            bool exists,
            bool revoked,
            uint8 reasonCode,
            uint64 revokedAt
        )
    {
        bytes32 key = keccak256(bytes(recordId));
        Record storage rec = records[key];
        return (
            rec.fileHash,
            rec.issuer,
            rec.registeredAt,
            rec.docType,
            rec.exists,
            rec.revoked,
            rec.reasonCode,
            rec.revokedAt
        );
    }
}

