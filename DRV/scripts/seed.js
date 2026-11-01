const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer, authorizedIssuer] = await ethers.getSigners();
  console.log("Seeding test records with account:", deployer.address);

  // Load deployed contract address
  const deployFile = path.join(__dirname, "..", "deployments", "localhost.json");
  let contractAddress;
  if (fs.existsSync(deployFile)) {
    const info = JSON.parse(fs.readFileSync(deployFile, "utf-8"));
    contractAddress = info.contractAddress;
  }

  // If running on an ephemeral network or contract has no bytecode at address, deploy fresh
  let code = "0x";
  if (contractAddress) {
    code = await ethers.provider.getCode(contractAddress);
  }

  if (!contractAddress || code === "0x") {
    console.log("No deployed contract found at address on current network, deploying fresh RecordRegistry...");
    const RecordRegistry = await ethers.getContractFactory("RecordRegistry");
    const registry = await RecordRegistry.deploy();
    await registry.waitForDeployment();
    contractAddress = await registry.getAddress();
  }

  const registry = await ethers.getContractAt("RecordRegistry", contractAddress);
  console.log("Using RecordRegistry at:", contractAddress);

  // Fixtures per DATABASE.md §8:
  // CERT-101: registered, file untouched (TC-01 -> MATCH)
  // CERT-103: registered, then revoked (TC-04 -> REVOKED)
  // CERT-104: registered (for query test)
  const fixtures = [
    {
      id: "CERT-101",
      // Known sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 (empty string or mock sha256)
      hash: "0x" + "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
      docType: 1, // Degree
      revoke: false,
    },
    {
      id: "CERT-102",
      hash: "0x" + "b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1",
      docType: 2, // Marksheet
      revoke: false,
    },
    {
      id: "CERT-103",
      hash: "0x" + "c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2",
      docType: 1, // Degree
      revoke: true,
      reasonCode: 1, // issued_in_error
    },
    {
      id: "CERT-104",
      hash: "0x" + "9f2c41ab7d03e6c158b9a0fe2c47d1e3a6b80c951e7f3d42c08a5b17e92d64f0",
      docType: 1, // Degree (matches API.md example)
      revoke: false,
    },
  ];

  for (const f of fixtures) {
    const [exists] = await registry.isRevoked(f.id);
    if (!exists) {
      console.log(`Registering ${f.id}...`);
      const tx = await registry.registerRecord(f.id, f.hash, f.docType);
      await tx.wait();
      console.log(`  Registered ${f.id} (tx: ${tx.hash})`);

      if (f.revoke) {
        console.log(`Revoking ${f.id} with reason ${f.reasonCode}...`);
        const revTx = await registry.revokeRecord(f.id, f.reasonCode);
        await revTx.wait();
        console.log(`  Revoked ${f.id} (tx: ${revTx.hash})`);
      }
    } else {
      console.log(`Record ${f.id} is already registered, skipping.`);
    }
  }

  console.log("Seeding complete!");
}

if (require.main === module) {
  main()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error("Seeding failed:", error);
      process.exit(1);
    });
}

module.exports = { main };
