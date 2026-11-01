const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("RecordRegistry Contract Tests (TC-01..TC-05)", function () {
  let recordRegistry;
  let owner;
  let authorizedIssuer;
  let unauthorizedUser;

  // Sample fixture data (matching DATABASE.md §8)
  const RECORD_ID_101 = "CERT-101";
  const RECORD_ID_102 = "CERT-102";
  const RECORD_ID_103 = "CERT-103";
  const UNKNOWN_ID = "CERT-999";

  // 32-byte sha256 hashes (simulated)
  const HASH_ORIGINAL = ethers.keccak256(ethers.toUtf8Bytes("Original Certificate Content 101"));
  const HASH_MODIFIED = ethers.keccak256(ethers.toUtf8Bytes("Tampered Certificate Content 101"));
  const HASH_CERT_103 = ethers.keccak256(ethers.toUtf8Bytes("Certificate Content 103"));

  const DOC_TYPE_DEGREE = 1;
  const REASON_ISSUED_IN_ERROR = 1;

  beforeEach(async function () {
    [owner, authorizedIssuer, unauthorizedUser] = await ethers.getSigners();

    const RecordRegistryFactory = await ethers.getContractFactory("RecordRegistry");
    recordRegistry = await RecordRegistryFactory.deploy();
    await recordRegistry.waitForDeployment();

    // Authorize an issuer
    await recordRegistry.connect(owner).authorizeIssuer(authorizedIssuer.address);
  });

  describe("Access Control & Authorization", function () {
    it("should set deployer as owner and authorize deployer", async function () {
      expect(await recordRegistry.owner()).to.equal(owner.address);
      expect(await recordRegistry.authorizedIssuers(owner.address)).to.be.true;
    });

    it("should allow owner to authorize and deauthorize issuers", async function () {
      const [, , , newIssuer] = await ethers.getSigners();
      await expect(recordRegistry.connect(owner).authorizeIssuer(newIssuer.address))
        .to.emit(recordRegistry, "IssuerAuthorized")
        .withArgs(newIssuer.address);

      expect(await recordRegistry.authorizedIssuers(newIssuer.address)).to.be.true;

      await expect(recordRegistry.connect(owner).deauthorizeIssuer(newIssuer.address))
        .to.emit(recordRegistry, "IssuerDeauthorized")
        .withArgs(newIssuer.address);

      expect(await recordRegistry.authorizedIssuers(newIssuer.address)).to.be.false;
    });

    it("should prevent non-owners from managing issuers", async function () {
      await expect(
        recordRegistry.connect(unauthorizedUser).authorizeIssuer(unauthorizedUser.address)
      ).to.be.revertedWithCustomError(recordRegistry, "UnauthorizedCaller");
    });
  });

  describe("TC-01: Registered certificate, original file", function () {
    it("should register a record and verify successfully with matching hash", async function () {
      const tx = await recordRegistry
        .connect(authorizedIssuer)
        .registerRecord(RECORD_ID_101, HASH_ORIGINAL, DOC_TYPE_DEGREE);

      const expectedKey = ethers.keccak256(ethers.toUtf8Bytes(RECORD_ID_101));
      await expect(tx)
        .to.emit(recordRegistry, "RecordRegistered")
        .withArgs(
          expectedKey,
          RECORD_ID_101,
          authorizedIssuer.address,
          HASH_ORIGINAL,
          DOC_TYPE_DEGREE,
          (val) => val > 0
        );

      const [exists, hashMatch, revoked] = await recordRegistry.verifyHash(
        RECORD_ID_101,
        HASH_ORIGINAL
      );
      expect(exists).to.be.true;
      expect(hashMatch).to.be.true;
      expect(revoked).to.be.false;

      const record = await recordRegistry.getRecord(RECORD_ID_101);
      expect(record.fileHash).to.equal(HASH_ORIGINAL);
      expect(record.issuer).to.equal(authorizedIssuer.address);
      expect(record.docType).to.equal(DOC_TYPE_DEGREE);
      expect(record.exists).to.be.true;
      expect(record.revoked).to.be.false;
    });
  });

  describe("TC-02: Modified file (hash mismatch)", function () {
    it("should detect hash mismatch when verifying with altered file hash", async function () {
      await recordRegistry
        .connect(authorizedIssuer)
        .registerRecord(RECORD_ID_101, HASH_ORIGINAL, DOC_TYPE_DEGREE);

      const [exists, hashMatch, revoked] = await recordRegistry.verifyHash(
        RECORD_ID_101,
        HASH_MODIFIED
      );
      expect(exists).to.be.true;
      expect(hashMatch).to.be.false; // Mismatch detected!
      expect(revoked).to.be.false;
    });
  });

  describe("TC-03: Unknown record ID", function () {
    it("should return exists=false and hashMatch=false for unregistered record ID", async function () {
      const [exists, hashMatch, revoked] = await recordRegistry.verifyHash(
        UNKNOWN_ID,
        HASH_ORIGINAL
      );
      expect(exists).to.be.false;
      expect(hashMatch).to.be.false;
      expect(revoked).to.be.false;

      const [statusExists, isRev] = await recordRegistry.isRevoked(UNKNOWN_ID);
      expect(statusExists).to.be.false;
      expect(isRev).to.be.false;
    });
  });

  describe("TC-04: Revoked certificate", function () {
    it("should revoke a registered record and report revoked status", async function () {
      await recordRegistry
        .connect(authorizedIssuer)
        .registerRecord(RECORD_ID_103, HASH_CERT_103, DOC_TYPE_DEGREE);

      const expectedKey = ethers.keccak256(ethers.toUtf8Bytes(RECORD_ID_103));
      const revokeTx = await recordRegistry
        .connect(authorizedIssuer)
        .revokeRecord(RECORD_ID_103, REASON_ISSUED_IN_ERROR);

      await expect(revokeTx)
        .to.emit(recordRegistry, "RecordRevoked")
        .withArgs(
          expectedKey,
          RECORD_ID_103,
          REASON_ISSUED_IN_ERROR,
          authorizedIssuer.address,
          (val) => val > 0
        );

      const [exists, hashMatch, revoked] = await recordRegistry.verifyHash(
        RECORD_ID_103,
        HASH_CERT_103
      );
      expect(exists).to.be.true;
      expect(hashMatch).to.be.true;
      expect(revoked).to.be.true;

      const [statusExists, isRev] = await recordRegistry.isRevoked(RECORD_ID_103);
      expect(statusExists).to.be.true;
      expect(isRev).to.be.true;

      const record = await recordRegistry.getRecord(RECORD_ID_103);
      expect(record.revoked).to.be.true;
      expect(record.reasonCode).to.equal(REASON_ISSUED_IN_ERROR);
      expect(record.revokedAt).to.be.gt(0);
    });

    it("should revert if revoking an unknown record ID", async function () {
      await expect(
        recordRegistry.connect(authorizedIssuer).revokeRecord(UNKNOWN_ID, REASON_ISSUED_IN_ERROR)
      ).to.be.revertedWithCustomError(recordRegistry, "RecordNotFound");
    });

    it("should revert if revoking an already revoked record ID", async function () {
      await recordRegistry
        .connect(authorizedIssuer)
        .registerRecord(RECORD_ID_103, HASH_CERT_103, DOC_TYPE_DEGREE);

      await recordRegistry
        .connect(authorizedIssuer)
        .revokeRecord(RECORD_ID_103, REASON_ISSUED_IN_ERROR);

      await expect(
        recordRegistry.connect(authorizedIssuer).revokeRecord(RECORD_ID_103, REASON_ISSUED_IN_ERROR)
      ).to.be.revertedWithCustomError(recordRegistry, "RecordAlreadyRevoked");
    });
  });

  describe("TC-05: Unauthorized registration or revocation", function () {
    it("should reject registration from unauthorized caller", async function () {
      await expect(
        recordRegistry
          .connect(unauthorizedUser)
          .registerRecord(RECORD_ID_102, HASH_ORIGINAL, DOC_TYPE_DEGREE)
      ).to.be.revertedWithCustomError(recordRegistry, "UnauthorizedCaller");
    });

    it("should reject revocation from unauthorized caller", async function () {
      await recordRegistry
        .connect(authorizedIssuer)
        .registerRecord(RECORD_ID_101, HASH_ORIGINAL, DOC_TYPE_DEGREE);

      await expect(
        recordRegistry
          .connect(unauthorizedUser)
          .revokeRecord(RECORD_ID_101, REASON_ISSUED_IN_ERROR)
      ).to.be.revertedWithCustomError(recordRegistry, "UnauthorizedCaller");
    });
  });

  describe("Edge cases and validation", function () {
    it("should reject duplicate registration for the same ID", async function () {
      await recordRegistry
        .connect(authorizedIssuer)
        .registerRecord(RECORD_ID_101, HASH_ORIGINAL, DOC_TYPE_DEGREE);

      await expect(
        recordRegistry
          .connect(authorizedIssuer)
          .registerRecord(RECORD_ID_101, HASH_ORIGINAL, DOC_TYPE_DEGREE)
      ).to.be.revertedWithCustomError(recordRegistry, "RecordAlreadyExists");
    });

    it("should reject empty record ID", async function () {
      await expect(
        recordRegistry.connect(authorizedIssuer).registerRecord("", HASH_ORIGINAL, DOC_TYPE_DEGREE)
      ).to.be.revertedWithCustomError(recordRegistry, "InvalidRecordId");
    });

    it("should reject zero file hash", async function () {
      await expect(
        recordRegistry
          .connect(authorizedIssuer)
          .registerRecord(RECORD_ID_101, ethers.ZeroHash, DOC_TYPE_DEGREE)
      ).to.be.revertedWithCustomError(recordRegistry, "InvalidFileHash");
    });

    it("should reject zero reason code on revocation", async function () {
      await recordRegistry
        .connect(authorizedIssuer)
        .registerRecord(RECORD_ID_101, HASH_ORIGINAL, DOC_TYPE_DEGREE);

      await expect(
        recordRegistry.connect(authorizedIssuer).revokeRecord(RECORD_ID_101, 0)
      ).to.be.revertedWithCustomError(recordRegistry, "InvalidReasonCode");
    });
  });
});

