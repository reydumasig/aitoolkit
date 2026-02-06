import crypto from "crypto";
import express from "express";
import cors from "cors";
import multer from "multer";
import dotenv from "dotenv";
import axios from "axios";
import {
  BlobServiceClient,
  StorageSharedKeyCredential,
  generateBlobSASQueryParameters,
  BlobSASPermissions
} from "@azure/storage-blob";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

const upload = multer({ storage: multer.memoryStorage() });

const connStr = process.env.AZURE_STORAGE_CONNECTION_STRING;
const containerName = process.env.AZURE_STORAGE_CONTAINER || "opsassistant";
const aiUrl = process.env.AI_SERVICE_URL || "http://localhost:8000";

// Helper: create blob client
function getBlobServiceClient() {
  return BlobServiceClient.fromConnectionString(connStr);
}

// Helper: build SAS URL (read-only) for the blob so Python can fetch it
async function getReadSasUrl(blobServiceClient, blobName) {
  // Parse account name + key from connection string (simple approach)
  const parts = Object.fromEntries(
    connStr
      .split(";")
      .map(p => p.split("=", 2))
      .filter(x => x.length === 2)
  );
  const accountName = parts.AccountName;
  const accountKey = parts.AccountKey;

  const credential = new StorageSharedKeyCredential(accountName, accountKey);
  const expiresOn = new Date(Date.now() + 60 * 60 * 1000); // 1 hour

  const sas = generateBlobSASQueryParameters(
    {
      containerName,
      blobName,
      permissions: BlobSASPermissions.parse("r"),
      expiresOn
    },
    credential
  ).toString();

  return `https://${accountName}.blob.core.windows.net/${containerName}/${encodeURIComponent(blobName)}?${sas}`;
}

app.post("/upload", upload.array("files"), async (req, res) => {
  try {
    const files = req.files || [];
    if (!files.length) return res.status(400).json({ error: "Missing file(s)" });

    const bsc = getBlobServiceClient();
    const containerClient = bsc.getContainerClient(containerName);
    await containerClient.createIfNotExists();

    const results = [];
    for (const file of files) {
      const docType = (file.originalname.split(".").pop() || "").toLowerCase();
      const docId = crypto.randomUUID();
      const blobName = `${docId}_${file.originalname}`;

      const blockBlob = containerClient.getBlockBlobClient(blobName);
      await blockBlob.uploadData(file.buffer, {
        blobHTTPHeaders: { blobContentType: file.mimetype }
      });

      const sasUrl = await getReadSasUrl(bsc, blobName);

      // Trigger ingestion in Python
      await axios.post(`${aiUrl}/ingest`, {
        docId,
        docType,
        filename: file.originalname,
        blobUrl: sasUrl
      });

      results.push({ docId, filename: file.originalname, docType });
    }

    res.json({ items: results });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Upload failed", details: err.message });
  }
});

app.post("/generate/sop", async (req, res) => {
  try {
    const { docIds = [], style = "standard" } = req.body || {};
    const r = await axios.post(`${aiUrl}/generate/sop`, { docIds, style });
    res.json(r.data);
  } catch (err) {
    res.status(500).json({ error: "Generate SOP failed", details: err.message });
  }
});

app.post("/generate/process", async (req, res) => {
  try {
    const { docIds = [], includeRaci = false } = req.body || {};
    const r = await axios.post(`${aiUrl}/generate/process`, {
      docIds,
      includeRaci
    });
    res.json(r.data);
  } catch (err) {
    res.status(500).json({ error: "Generate Process failed", details: err.message });
  }
});

app.listen(process.env.PORT || 4001, () => {
  console.log(`API running on :${process.env.PORT || 4001}`);
});
