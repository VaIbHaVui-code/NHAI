require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const Sign = require('./models/Sign');

const app = express();

// Middleware
app.use(cors());
app.use(express.json()); // Allows server to read JSON

// Connect to MongoDB
mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log("✅ Connected to MongoDB"))
  .catch(err => console.error("❌ Connection failed:", err));

// --- API ENDPOINTS ---

// 1. POST: Receive data from AI Engine
app.post('/api/signs', async (req, res) => {
  try {
    const newSign = new Sign(req.body);
    await newSign.save();
    res.status(201).json({ success: true, message: "Sign data saved!" });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// 2. GET: Serve data to React Dashboard
app.get('/api/signs', async (req, res) => {
  try {
    const signs = await Sign.find().sort({ detected_at: -1 });
    res.json({ success: true, records: signs });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 3. DELETE: Resolve/Remove a sign (Member 3 needs this!)
app.delete('/api/signs/:id', async (req, res) => {
  await Sign.findByIdAndDelete(req.params.id);
  res.json({ success: true });
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`🚀 Server running on port ${PORT}`));