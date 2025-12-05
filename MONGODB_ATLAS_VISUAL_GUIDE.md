# MongoDB Atlas Setup - Visual Guide

## 🌍 Step 1: Create MongoDB Atlas Account

### Go to https://www.mongodb.com/cloud/atlas

```
┌─────────────────────────────────────────┐
│   MongoDB Atlas - Welcome              │
│                                         │
│   [Sign Up Free]  [Sign In]            │
│                                         │
│   Free tier: 512MB storage ✓           │
└─────────────────────────────────────────┘
```

---

## 📦 Step 2: Create Your First Cluster

After signing in:

```
1. Click "Build a Database"
         ↓
2. Choose Deployment:
   ✓ M0 Cluster (Free - 512MB)
   ☐ M2/M5 (Paid)
         ↓
3. Select Provider & Region:
   Cloud: AWS ✓
   Region: us-east-1 (or nearest to you)
         ↓
4. Click "Create Cluster"
   ⏳ Wait 5-10 minutes...
         ↓
   ✓ Cluster deployed!
```

---

## 👤 Step 3: Create Database User

```
Cluster → Security → Database Access

1. Click "Add New Database User"
         ↓
2. Enter Credentials:
   Username: invoicely_user
   Password: [Generate Secure Password]
            ↓ (Copy and save it!)
         ↓
3. Database User Privileges:
   ✓ Atlas admin
         ↓
4. Click "Add User"
   ✓ User created!
```

**Example Credentials:**
```
Username: invoicely_user
Password: 7mK9pQ2xL8nB5vR3wT (SAVE THIS!)
```

---

## 🌐 Step 4: Configure Network Access

```
Cluster → Security → Network Access

1. Click "Add IP Address"
         ↓
2. Choose:
   ✓ Allow access from anywhere (0.0.0.0/0)
     [For development only]
         ↓
   OR (Production):
   ☐ Add specific IP address
     Enter: 123.45.67.89
         ↓
3. Click "Add Entry"
   ✓ Network access configured!
```

---

## 🔗 Step 5: Get Connection String

```
Cluster → Click "Connect"
         ↓
Choose "Drivers" (Python recommended)
         ↓
Select: Python 3.12+
         ↓
Copy Connection String:

mongodb+srv://invoicely_user:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

---

## 📄 Step 6: Create .env File

In `backend/` directory:

**File: `.env`**
```env
MONGODB_URL=mongodb+srv://invoicely_user:7mK9pQ2xL8nB5vR3wT@cluster0.w8abc.mongodb.net/?retryWrites=true&w=majority

MONGODB_DATABASE_NAME=invoicely

GEMINI_API_KEY=your_api_key_here
```

⚠️ Replace these with your actual values:
- `invoicely_user` → Your username
- `7mK9pQ2xL8nB5vR3wT` → Your password
- `cluster0.w8abc.mongodb.net` → Your cluster URL

---

## ✅ Step 7: Test Connection

```bash
cd backend

# Test MongoDB connection
python test_connection.py
```

Expected output:
```
✓ MongoDB Atlas connection successful!
```

---

## 🚀 Step 8: Run Application

```bash
python main.py
```

Expected output:
```
✓ MongoDB Atlas connection successful!
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 🧪 Step 9: Verify Data Storage

### Via Web Application:
1. Open: http://localhost:3000
2. Upload a PDF invoice
3. Check if extraction succeeds

### Via MongoDB Atlas Dashboard:
1. Go to: Cluster → Collections
2. Navigate to: `invoicely` → `invoices`
3. See your uploaded invoice data in JSON format!

```json
{
  "_id": ObjectId("..."),
  "invoice_number": "INV-001",
  "vendor_name": "Acme Corp",
  "total_amount": 1500.00,
  "is_valid": true,
  "score": 85,
  "created_at": "2025-12-05T10:30:00Z",
  ...
}
```

---

## 🔐 Security Checklist

- [ ] Used strong password (uppercase, lowercase, numbers, symbols)
- [ ] Network access limited (or 0.0.0.0/0 for dev only)
- [ ] `.env` file created with connection string
- [ ] `.env` is in `.gitignore` (NOT committed)
- [ ] Connection tested successfully
- [ ] Application running without errors

---

## 🎯 Connection Flow

```
Your Application
      ↓
[database.py]
      ↓
Detects: mongodb+srv:// ✓
      ↓
Enables: TLS 1.2+ encryption
      ↓
Connects to: MongoDB Atlas cluster
      ↓
Authenticates: invoicely_user:password
      ↓
✓ Connection successful!
```

---

## 📊 What You Get (Free Tier)

```
MongoDB Atlas Cluster (Free)
├── 1 Cluster
├── 512 MB Storage
├── 3 Nodes (High Availability)
├── Automatic Backups (7-day snapshot)
├── TLS 1.2+ Encryption (included)
├── 24/7 Monitoring & Alerts
└── Unlimited Connections
```

---

## ⚡ Quick Commands

```bash
# Create .env from example
cp backend/.env.example backend/.env

# Edit .env with your connection string
# (Use any text editor)

# Test connection
python test_connection.py

# Run application
python main.py

# View logs
# Check console for: "✓ MongoDB Atlas connection successful!"
```

---

## 🆘 Troubleshooting

### ❌ "Timeout" or "Connection refused"
✅ Solution: 
- Check cluster is running (green checkmark in Atlas)
- Verify network access includes your IP
- Wait 1-2 minutes for cluster to be ready

### ❌ "Authentication failed"
✅ Solution:
- Double-check username/password
- Verify password special characters are correct
- Reset password in Atlas and retry

### ❌ "Invalid URI schema"
✅ Solution:
- Ensure connection string starts with `mongodb+srv://`
- Check for typos in URL

### ❌ "Database not found"
✅ Solution:
- ✓ Already handled! App creates `invoicely` database automatically

---

## 🎉 Success!

You now have:
- ✓ MongoDB Atlas cluster running in the cloud
- ✓ Secure TLS 1.2+ encrypted connection
- ✓ Application connected and storing data
- ✓ Free tier with 512MB storage
- ✓ Production-ready database setup

**Next Steps:**
1. Upload test PDFs via web interface
2. Monitor data in MongoDB Atlas dashboard
3. Scale up when needed (paid tier)
4. Deploy application to production!

