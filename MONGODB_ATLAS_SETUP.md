# MongoDB Atlas Connection Setup Guide

## 📋 Step-by-Step Instructions

### **Step 1: Create MongoDB Atlas Account & Cluster**

1. **Go to MongoDB Atlas**: https://www.mongodb.com/cloud/atlas
2. **Sign up** (free tier available) or **Log in** to your account
3. **Create a new Project**:
   - Click "Create a project"
   - Enter project name (e.g., "Invoice QC Service")
   - Click "Create project"

4. **Create a Cluster**:
   - Click "Build a Database"
   - Choose **M0 Cluster** (free tier, perfect for development)
   - Select cloud provider: **AWS** (or your preference)
   - Select region closest to you (e.g., **us-east-1**)
   - Click "Create Cluster" (takes ~5 minutes)

---

### **Step 2: Create Database User**

1. **In Cluster view**, go to **Security → Database Access**
2. **Add New Database User**:
   - **Username**: `invoicely_user` (or your choice)
   - **Password**: Generate secure password (or create your own)
     - ✅ Use auto-generated password (recommended)
     - Copy and save it securely
   - **Database User Privileges**: `Atlas admin`
   - Click **Add User**

> ⚠️ **Save the password!** You'll need it in the connection string.

---

### **Step 3: Configure Network Access**

1. **Go to Security → Network Access**
2. **Add IP Address**:
   - Click **"Add IP Address"**
   - **Allow access from anywhere**: `0.0.0.0/0` (development)
     - ✅ For production: use your server's IP only
   - Click **Add Entry**

> ⚠️ **For production**, always restrict to specific IPs instead of 0.0.0.0/0

---

### **Step 4: Get Connection String**

1. **Go to your Cluster**
2. **Click "Connect"** button
3. **Choose "Drivers"** (not Compass)
4. **Select Python 3.12+** (or your version)
5. **Copy the connection string**

Example format:
```
mongodb+srv://invoicely_user:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

---

### **Step 5: Configure Your Application**

#### **Option A: Create `.env` File (Recommended)**

1. Navigate to `backend/` directory
2. Create a `.env` file (copy from `.env.example`):

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS/Linux
cp .env.example .env
```

3. **Edit `.env` file** with your connection details:

```env
# Replace with your actual connection string
MONGODB_URL=mongodb+srv://invoicely_user:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority

MONGODB_DATABASE_NAME=invoicely

# Optional - for advanced features
GEMINI_API_KEY=your_api_key_here
```

> ⚠️ **Never commit `.env` to git!** It's already in `.gitignore`

---

### **Step 6: Test Connection**

Run the connection test:

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

### **Step 7: Run Application**

```bash
# Start the FastAPI backend
python main.py
```

Expected output:
```
✓ MongoDB Atlas connection successful!
INFO:     Started server process [1234]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 🔑 Connection String Breakdown

```
mongodb+srv://invoicely_user:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
                 │                 │         │                    │
              USERNAME          PASSWORD   CLUSTER URL        QUERY PARAMS
```

### Query Parameters Explained:
- `retryWrites=true` - Auto-retry failed writes
- `w=majority` - Write to majority of replicas (ensures durability)

---

## 🛠️ Troubleshooting

### **Connection Timeout Error**
```
ServerSelectionTimeoutError: SSL handshake failed
```
**Solution**: 
- Verify username and password are correct
- Check network access is allowed (0.0.0.0/0 or your IP)
- Ensure cluster is running (click on cluster name)

### **Authentication Failed**
```
pymongo.errors.OperationFailure: authentication failed
```
**Solution**:
- Double-check username and password in connection string
- Verify special characters are URL-encoded (use `%40` for `@`, etc.)
- Reset password and try again

### **Database Not Found**
```
ConfigurationError: No default database defined
```
**Solution**: ✅ Already fixed in updated code - uses `MONGODB_DATABASE_NAME`

### **Connection String Format Wrong**
```
Invalid URI schema
```
**Solution**:
- Must start with `mongodb+srv://` (not `mongodb://`)
- Check for typos in cluster URL

---

## 📊 MongoDB Atlas Free Tier Limits

| Feature | Free Tier Limit |
|---------|-----------------|
| **Clusters** | 1 |
| **Database Size** | 512 MB |
| **Connections** | Unlimited |
| **CPU** | Shared |
| **Backup** | 7-day snapshot |
| **Regions** | 3 major cloud providers |

Perfect for development and testing!

---

## 🚀 Next Steps

### **1. Verify Connection Works**
```bash
cd backend
python test_connection.py
```

### **2. Run Application**
```bash
python main.py
```

### **3. Test Upload**
- Open: `http://localhost:3000`
- Upload a PDF invoice
- Check if data is stored in MongoDB Atlas

### **4. View Data in Atlas**
1. Go to **MongoDB Atlas Dashboard**
2. Click **Cluster → Collections**
3. Browse `invoicely.invoices` collection
4. See your uploaded invoice data!

---

## 🔐 Security Best Practices

✅ **DO:**
- Use strong, unique passwords
- Restrict network access to known IPs (production)
- Never commit `.env` file to git
- Use separate users for dev/prod (different credentials)
- Rotate passwords periodically

❌ **DON'T:**
- Commit connection string to GitHub
- Use `0.0.0.0/0` network access in production
- Share `.env` file with others
- Use simple/predictable passwords
- Hardcode credentials in code

---

## 📝 Example `.env` File

```env
# ===== MongoDB Atlas =====
MONGODB_URL=mongodb+srv://invoicely_user:SecurePassword123@cluster0.w8abc.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE_NAME=invoicely

# ===== Optional API Keys =====
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxx
```

---

## ✨ You're All Set!

Your MongoDB Atlas cluster is now connected to your application with:
- ✅ TLS 1.2+ encryption (automatic with Atlas)
- ✅ Automatic failover and high availability
- ✅ Free tier with 512MB storage
- ✅ MongoDB Atlas monitoring and alerts
- ✅ Backup and restore capabilities

**Need help?** Check the troubleshooting section or refer to [MongoDB Atlas Documentation](https://docs.atlas.mongodb.com/)

