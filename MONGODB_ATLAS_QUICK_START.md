# MongoDB Atlas Connection - Quick Reference

## 🚀 Quick Setup (5 Minutes)

### 1. Create Account & Cluster
- Go to: https://www.mongodb.com/cloud/atlas
- Sign up (free)
- Click "Build a Database" → Choose M0 (free tier)
- Select region & create cluster (5 minutes)

### 2. Create Database User
- Security → Database Access
- Add User: `invoicely_user` with password
- Copy password (you'll need it!)

### 3. Enable Network Access
- Security → Network Access  
- Add IP: `0.0.0.0/0` (development only)

### 4. Get Connection String
- Click "Connect" → "Drivers" → Copy string

### 5. Update `.env` File
```env
MONGODB_URL=mongodb+srv://invoicely_user:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE_NAME=invoicely
```

### 6. Test Connection
```bash
cd backend
python test_connection.py
```

Expected: `✓ MongoDB Atlas connection successful!`

---

## 📋 Connection String Template

```
mongodb+srv://USERNAME:PASSWORD@CLUSTER_URL/?retryWrites=true&w=majority
```

### Replace These:
- `USERNAME` → Your database user (e.g., `invoicely_user`)
- `PASSWORD` → Your password (URL-encode special chars)
- `CLUSTER_URL` → From Atlas (e.g., `cluster0.w8abc.mongodb.net`)

---

## ⚠️ Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| **Timeout Error** | Check network access (0.0.0.0/0) |
| **Auth Failed** | Verify username/password |
| **Connection Refused** | Ensure cluster is running |
| **SSL Error** | App auto-detects and uses TLS 1.2+ |

---

## 📊 Atlas Free Tier
- 1 cluster
- 512 MB storage
- Unlimited connections
- Perfect for development

---

## 🔐 Security Checklist

- [ ] Cluster created
- [ ] Database user created
- [ ] Network access configured
- [ ] Connection string copied
- [ ] `.env` file updated
- [ ] Connection tested
- [ ] `.env` NOT committed to git
- [ ] Strong password used

---

## ✅ Verification

Once connected, you should see:

**Console Output:**
```
✓ MongoDB Atlas connection successful!
```

**In MongoDB Atlas:**
- Dashboard shows cluster status: ✓ Active
- Collections appear in cluster

**In Application:**
- Upload test PDF
- Check: Collections → invoices
- See your invoice data!

---

**Ready?** Follow the 6 steps above and you're done! 🎉
